#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""executeur_papers.py -- porter les decisions de papier_tf en reel.

CE QUE C EST
------------
Un processus separe, attache au SEUL terminal du compte dedie. Il lit
l etat de papier_tf et rejoue chacun de ses mouvements sur ce compte.

Il ne decide rien. Il ne calcule aucun signal. Il ne filtre rien, sauf
la condition PM. Il ne modifie pas papier_tf.

CE QU IL REPRODUIT
------------------
`docs/papier_tf/etat.json` contient les cellules ouvertes du papier,
indexees par magic, chacune portant un `id` unique de la forme
`207360@2026-08-25T08:00:17`. Trois evenements s en deduisent :

  ENTREE     un `id` apparait
  REDUCTION  `reste` diminue a `id` constant  (le partiel 70 % du 207)
  SORTIE     un `id` disparait

CE QU IL RESPECTE
-----------------
**La condition PM porte sur les ENTREES seulement.** Une position
ouverte a 18:50 et fermee par le papier a 19:30 doit etre fermee a
19:30. Fermer hors fenetre n est pas une entorse a la regle : c est la
seule facon de ne pas laisser une position reelle sans personne pour la
gerer.

Au demarrage, les cellules deja ouvertes ne sont pas rejouees -- leur
prix d entree appartient au passe. L etat courant devient la reference,
et seuls les changements ulterieurs sont suivis.

PREALABLE
---------
papier_tf.py doit ecrire son etat a chaque tour, et non toutes les dix
minutes. C est la desindentation de la ligne 661 -- `ecrire_etat` sort
du bloc de veille et rejoint le corps de la boucle. Sans elle, cet
executeur voit les entrees avec jusqu a dix minutes de retard.

La sonde le verifie au demarrage et refuse de partir si l etat est
rassis.

SECURITE
--------
- Refuse le terminal du moteur, avant toute autre chose.
- Refuse un compte qui n est pas une demo.
- Refuse si le numero de compte ne correspond pas a --compte.
- **Simulation par defaut.** Il faut --reel pour qu un ordre parte.
- Ne ferme jamais une position qu il n a pas lui-meme ouverte : il tient
  sa propre table de correspondance id -> ticket.

USAGE
-----
    python executeur_papers.py --compte 182109              (simulation)
    python executeur_papers.py --compte 182109 --reel
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime

TERMINAL_DEFAUT = r"C:\Program Files\TF Global Markets MetaTrader 5 Terminal\terminal64.exe"
TERMINAL_MOTEUR = r"C:\Program Files\TF Global Markets MetaTrader 5 Termina-LOCALSTACKl\terminal64.exe"
RACINE = r"C:\SVPS\Scalp-EA-main"
ETAT_PAPIER = os.path.join(RACINE, "docs", "papier_tf", "etat.json")
LIENS = os.path.join(RACINE, "logs", "executeur_papers_liens.json")
JOURNAL = os.path.join(RACINE, "logs", "executeur_papers.log")

PM_DEBUT = (14, 0)
PM_FIN = (19, 0)

PERIODE = 0.25          # secondes entre deux regards sur le fichier
ETAT_RASSIS = 90.0      # s ; au-dela, papier_tf n ecrit pas a chaque tour
EPS = 1e-9

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


# ====================================================================
# JOURNAL
# ====================================================================
def dire(message):
    ligne = "%s  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        message)
    print(ligne)
    sys.stdout.flush()
    try:
        with io.open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
    except Exception:
        pass


def masque(valeur):
    t = str(valeur)
    if len(t) <= 4:
        return "*" * len(t)
    return t[:2] + "*" * (len(t) - 4) + t[-2:]


# ====================================================================
# LECTURE DE L ETAT DU PAPIER
# ====================================================================
def lire_etat(chemin):
    """ecrire_etat supprime puis renomme : il existe une fenetre, courte
    mais reelle, ou le fichier n existe pas. On reessaie plutot que de
    conclure que le papier n a plus rien d ouvert -- conclure cela
    reviendrait a tout fermer."""
    for _ in range(8):
        try:
            with io.open(chemin, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, PermissionError):
            time.sleep(0.02)
        except ValueError:
            time.sleep(0.02)
    return None


def resume(etat):
    """Ne garde de chaque cellule que ce dont l executeur a besoin."""
    out = {}
    for k, c in (etat or {}).items():
        try:
            out[str(k)] = {
                "id": c["id"],
                "sym": c["sym"],
                "sens": int(c["sens"]),
                "lot": float(c["lot"]),
                "reste": float(c["reste"]),
                "entree": float(c["entree"]),
                "sl": float(c.get("sl") or 0.0),
                "bras": str(c.get("bras", "")),
                "mn": c.get("mn"),
            }
        except (KeyError, TypeError, ValueError):
            continue
    return out


# ====================================================================
# LE DIFF -- c est ici que tout se joue, et c est testable hors MT5
# ====================================================================
def diff_etats(ancien, nouveau):
    """Renvoie la liste des evenements, sorties avant entrees.

    Une cellule qui se ferme et se rouvre dans le meme tour change d id :
    il faut alors emettre la sortie de l ancienne AVANT l entree de la
    nouvelle, sinon on se retrouve avec deux positions sur un magic qui
    n en porte qu une.
    """
    evts = []

    for k, a in ancien.items():
        n = nouveau.get(k)
        if n is None or n["id"] != a["id"]:
            evts.append({"type": "SORTIE", "k": k, "cell": a,
                         "volume": a["reste"]})

    for k, n in nouveau.items():
        a = ancien.get(k)
        if a is None or a["id"] != n["id"]:
            evts.append({"type": "ENTREE", "k": k, "cell": n,
                         "volume": n["lot"]})
        elif n["reste"] < a["reste"] - EPS:
            evts.append({"type": "REDUCTION", "k": k, "cell": n,
                         "volume": round(a["reste"] - n["reste"], 2)})

    return evts


def dans_pm(maintenant=None):
    d = maintenant or datetime.now()
    return PM_DEBUT <= (d.hour, d.minute) < PM_FIN


# ====================================================================
# TABLE DE CORRESPONDANCE id -> ticket
# ====================================================================
def charger_liens():
    try:
        with io.open(LIENS, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def ecrire_liens(liens):
    try:
        tmp = LIENS + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(liens, ensure_ascii=False, indent=1))
        if os.path.exists(LIENS):
            os.remove(LIENS)
        os.rename(tmp, LIENS)
    except Exception as e:
        dire("liens non sauvegardes : %s" % e)


# ====================================================================
# ENVOI
# ====================================================================
def prix_courant(sym, pour_achat):
    t = mt5.symbol_info_tick(sym)
    if t is None:
        return None
    return t.ask if pour_achat else t.bid


def envoyer_entree(cell, reel):
    sym = cell["sym"]
    achat = cell["sens"] > 0
    prix = prix_courant(sym, achat)
    if prix is None:
        dire("  prix indisponible sur %s -- entree abandonnee" % sym)
        return None

    sl = 0.0
    if cell["sl"]:
        sl = prix - cell["sl"] if achat else prix + cell["sl"]

    requete = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sym,
        "volume": round(cell["lot"], 2),
        "type": mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL,
        "price": prix,
        "sl": round(sl, 2) if sl else 0.0,
        "magic": int(cell["id"].split("@")[0]),
        "comment": cell["id"][:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    if not reel:
        dire("  [SIMULATION] %s %s vol %.2f @ %.2f sl %.2f"
             % (sym, "BUY" if achat else "SELL", requete["volume"], prix, sl))
        return None

    res = mt5.order_send(requete)
    if res is None:
        dire("  order_send a rendu None : %s" % (mt5.last_error(),))
        return None
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        dire("  ENTREE REFUSEE rc=%s (%s)" % (res.retcode, res.comment))
        return None
    dire("  entree faite : ticket %s @ %.2f" % (res.order, res.price))
    return res.order


def envoyer_sortie(ticket, cell, volume, reel, motif):
    sym = cell["sym"]
    pos = mt5.positions_get(ticket=ticket) if reel else None
    if reel:
        if not pos:
            dire("  ticket %s absent -- deja ferme ? rien a faire" % ticket)
            return True
        volume = min(volume, float(pos[0].volume))
    volume = round(volume, 2)
    if volume <= 0:
        return True

    achat_sortie = cell["sens"] < 0      # on ferme un SELL par un BUY
    prix = prix_courant(sym, achat_sortie)
    if prix is None:
        dire("  prix indisponible sur %s -- sortie abandonnee" % sym)
        return False

    requete = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sym,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if achat_sortie else mt5.ORDER_TYPE_SELL,
        "position": int(ticket),
        "price": prix,
        "magic": int(cell["id"].split("@")[0]),
        "comment": motif[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    if not reel:
        dire("  [SIMULATION] fermeture %s vol %.2f sur ticket %s (%s)"
             % (sym, volume, ticket, motif))
        return True

    res = mt5.order_send(requete)
    if res is None:
        dire("  order_send a rendu None : %s" % (mt5.last_error(),))
        return False
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        dire("  SORTIE REFUSEE rc=%s (%s)" % (res.retcode, res.comment))
        return False
    dire("  sortie faite : %.2f lot @ %.2f" % (volume, res.price))
    return True


# ====================================================================
# BOUCLE
# ====================================================================
def traiter(evts, liens, reel):
    for e in evts:
        cell = e["cell"]
        etiquette = "%s %s %s mn%s" % (e["k"], cell["sym"],
                                       "BUY" if cell["sens"] > 0 else "SELL",
                                       cell["mn"])
        if e["type"] == "ENTREE":
            if not dans_pm():
                dire("ENTREE ignoree, hors PM : %s  (%s)" % (etiquette, cell["id"]))
                continue
            dire("ENTREE %s  vol %.2f  (%s)" % (etiquette, e["volume"], cell["id"]))
            ticket = envoyer_entree(cell, reel)
            if ticket:
                liens[cell["id"]] = {"ticket": int(ticket), "sym": cell["sym"],
                                     "sens": cell["sens"]}
                ecrire_liens(liens)

        else:
            lien = liens.get(cell["id"])
            if lien is None:
                # Entree jamais prise -- hors PM, ou refusee. Il n y a
                # rien a fermer, et ce n est pas une anomalie.
                dire("%s sans position de notre fait : %s -- ignoree"
                     % (e["type"], cell["id"]))
                continue
            motif = "PARTIEL" if e["type"] == "REDUCTION" else "SORTIE"
            dire("%s %s  vol %.2f  ticket %s"
                 % (e["type"], etiquette, e["volume"], lien["ticket"]))
            ok = envoyer_sortie(lien["ticket"], cell, e["volume"], reel, motif)
            if ok and e["type"] == "SORTIE":
                liens.pop(cell["id"], None)
                ecrire_liens(liens)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--terminal", default=TERMINAL_DEFAUT)
    ap.add_argument("--compte", type=int, required=True)
    ap.add_argument("--etat", default=ETAT_PAPIER)
    ap.add_argument("--reel", action="store_true",
                    help="envoie reellement les ordres (defaut : simulation)")
    ap.add_argument("--sans-pm", action="store_true",
                    help="ignore la fenetre 14:00-19:00 (essais seulement)")
    args = ap.parse_args()

    # Cette protection passe avant tout, et ne depend de rien.
    if os.path.abspath(args.terminal) == os.path.abspath(TERMINAL_MOTEUR):
        print("REFUS : ce chemin est celui du terminal du moteur.")
        return 2

    if args.sans_pm:
        global PM_DEBUT, PM_FIN
        PM_DEBUT, PM_FIN = (0, 0), (23, 59)

    dire("=" * 62)
    dire("executeur_papers -- %s" % ("REEL" if args.reel else "SIMULATION"))
    dire("=" * 62)

    if mt5 is None:
        dire("MetaTrader5 introuvable dans cet interpreteur.")
        return 2
    if not os.path.isfile(args.etat):
        dire("etat du papier introuvable : %s" % args.etat)
        return 2
    if not mt5.initialize(path=args.terminal):
        dire("initialize a echoue : %s" % (mt5.last_error(),))
        return 1

    try:
        ai = mt5.account_info()
        ti = mt5.terminal_info()
        if ai is None or ti is None:
            dire("compte ou terminal illisible : %s" % (mt5.last_error(),))
            return 1
        if int(ai.login) != int(args.compte):
            dire("MAUVAIS COMPTE : attendu %s, trouve %s"
                 % (masque(args.compte), masque(ai.login)))
            return 1
        if ai.trade_mode != getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0):
            dire("Ce compte n est pas une demo. Refus.")
            return 1
        if not ti.trade_allowed:
            dire("AutoTrading eteint sur ce terminal. Chaque ordre serait")
            dire("refuse en rc=10027. Cliquer sur 'Trading Algo'.")
            return 1
        dire("compte %s  %s  solde %.2f %s"
             % (masque(ai.login), ai.server, ai.balance, ai.currency))

        # -- l etat du papier est-il vivant
        age = time.time() - os.path.getmtime(args.etat)
        dire("etat du papier : %.0f s" % age)
        if age > ETAT_RASSIS:
            dire("")
            dire("ARRET. L etat a plus de %.0f s. papier_tf n ecrit pas a"
                 % ETAT_RASSIS)
            dire("chaque tour : la ligne 661 est encore dans le bloc de")
            dire("veille. Sans la desindenter, les entrees arriveraient")
            dire("avec jusqu a dix minutes de retard -- ce ne serait pas")
            dire("une copie.")
            return 1

        liens = charger_liens()
        precedent = resume(lire_etat(args.etat))
        dire("reference de depart : %d cellule(s) ouverte(s), non rejouee(s)"
             % len(precedent))
        dire("%d lien(s) repris d une execution precedente" % len(liens))
        dire("fenetre PM : %02d:%02d -> %02d:%02d"
             % (PM_DEBUT[0], PM_DEBUT[1], PM_FIN[0], PM_FIN[1]))
        dire("en ecoute.")

        dernier_mtime = os.path.getmtime(args.etat)
        dernier_battement = time.time()

        while True:
            time.sleep(PERIODE)
            try:
                m = os.path.getmtime(args.etat)
            except OSError:
                continue
            if m != dernier_mtime:
                dernier_mtime = m
                brut = lire_etat(args.etat)
                if brut is None:
                    dire("etat illisible apres plusieurs essais -- on garde")
                    dire("la reference precedente et on attend.")
                    continue
                courant = resume(brut)
                evts = diff_etats(precedent, courant)
                if evts:
                    traiter(evts, liens, args.reel)
                precedent = courant

            if time.time() - dernier_battement >= 300:
                dernier_battement = time.time()
                dire("battement : %d cellule(s) suivie(s), %d position(s) a nous"
                     % (len(precedent), len(liens)))

    except KeyboardInterrupt:
        dire("arret demande.")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())
