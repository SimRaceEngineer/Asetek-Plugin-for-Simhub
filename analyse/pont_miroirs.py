#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pont_miroirs.py -- copie stricte des miroirs paper sur le compte dedie.

LE BUT
------
Les memes entrees, les memes sorties, au delai d execution pres. Rien
de plus : aucun filtre, aucune regle ajoutee, aucun magic ecarte. Le
tri des bons et des moins bons papers viendra apres, sur des chiffres
propres.

POURQUOI DEUX PROCESSUS
-----------------------
Un processus Python ne peut etre connecte qu a UN terminal MT5. Il faut
donc lire sur celui du moteur et ecrire sur celui du compte dedie.

  --lecteur    s attache au terminal du moteur, LIT les positions des
               miroirs, ecrit un instantane. N ENVOIE JAMAIS D ORDRE.
  --envoyeur   s attache au terminal dedie, lit l instantane, et fait
               correspondre le compte dedie a ce qu il decrit.

Le lecteur ne touche a rien. L envoyeur ne voit meme pas le compte du
moteur. Aucune interference n est possible dans un sens ni dans l autre.

CE QUI EST COPIE
----------------
Toute position dont le magic appartient aux miroirs paper :

    220000 - 249999      miroir 1, le magic du paper lui-meme
   4220000 - 4249999     miroir 2, le magic prefixe d un 4

Pour chacune : le symbole, le sens, le volume, le magic, le SL et le
TP. Une reduction de volume est reproduite a l identique. Une
disparition ferme le reste. Un SL qui bouge est reporte.

AU DEMARRAGE
------------
Les positions deja ouvertes ne sont PAS rejouees : leur prix d entree
appartient au passe, et les copier au marche donnerait une entree
fausse. Elles servent de reference, et seuls les changements suivants
sont suivis. `--reprendre` force la copie initiale si vous la voulez.

Lance avant 14:00, le pont part donc d une page blanche.

SECURITE
--------
- Le lecteur refuse le terminal dedie. L envoyeur refuse celui du
  moteur. Ces deux refus passent avant tout autre controle.
- L envoyeur exige --compte, refuse un compte qui n est pas une demo,
  et refuse si AutoTrading est eteint.
- Simulation par defaut des deux cotes. Il faut --reel pour envoyer.
- L envoyeur ne ferme que des positions qu il a lui-meme ouvertes : il
  tient sa table magic -> ticket.

USAGE
-----
    python pont_miroirs.py --lecteur
    python pont_miroirs.py --envoyeur --compte 182109
    python pont_miroirs.py --envoyeur --compte 182109 --reel
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime

TERMINAL_MOTEUR = r"C:\Program Files\TF Global Markets MetaTrader 5 Termina-LOCALSTACKl\terminal64.exe"
TERMINAL_DEDIE = r"C:\Program Files\TF Global Markets MetaTrader 5 Terminal\terminal64.exe"
RACINE = r"C:\SVPS\Scalp-EA-main"
INSTANTANE = os.path.join(RACINE, "docs", "pont_miroirs", "etat.json")
LIENS = os.path.join(RACINE, "docs", "pont_miroirs", "liens.json")
JOURNAL = os.path.join(RACINE, "logs", "pont_miroirs.log")

# Les deux plages de magics des miroirs paper.
PLAGES = ((220000, 249999), (4220000, 4249999))

PERIODE = 0.05          # 20 regards par seconde
BATTEMENT = 1.0         # s ; on reecrit au moins a cette cadence
RASSIS = 5.0            # s ; au-dela, le lecteur est considere mort
ATTENTE_LECTEUR = 45.0  # s ; delai laisse au lecteur pour joindre MT5
EPS = 1e-9

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


def dire(role, message):
    """Ecrit dans la console SI elle existe, et toujours dans le journal.

    Lance sans console -- pythonw, une tache planifiee, un DETACHED
    PROCESS -- `sys.stdout` peut etre None ou pointer un descripteur
    invalide. Un print qui leve tuerait la boucle sans laisser de trace :
    c est ce qui a tue le miroir le 24/08 a 18:08. Le journal, lui, ne
    depend d aucune console.
    """
    ligne = "%s  [%s] %s" % (
        datetime.now().strftime("%H:%M:%S.%f")[:-3], role, message)
    try:
        if sys.stdout is not None:
            sys.stdout.write(ligne + "\n")
            sys.stdout.flush()
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
        with io.open(JOURNAL, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (datetime.now().strftime("%Y-%m-%d"), ligne))
    except Exception:
        pass


def noter_pid(role):
    """Depose le PID pour qu on puisse arreter CE processus-la, et lui
    seul. On n arrete jamais les python par leur nom."""
    try:
        chemin = os.path.join(os.path.dirname(JOURNAL), "pont_miroirs_pids.txt")
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with io.open(chemin, "a", encoding="utf-8") as f:
            f.write("%s  %-9s pid %d\n"
                    % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                       role, os.getpid()))
    except Exception:
        pass


def masque(v):
    t = str(v)
    return t if len(t) <= 4 else t[:2] + "*" * (len(t) - 4) + t[-2:]


def est_miroir(magic):
    try:
        m = int(magic)
    except Exception:
        return False
    return any(a <= m <= b for a, b in PLAGES)


def ecrire_atomique(chemin, obj):
    """Ecrit par fichier temporaire puis os.replace.

    os.replace remplace en une operation, sans passer par un instant ou
    le fichier n existe pas -- contrairement a remove puis rename, qui
    ouvrait une fenetre pendant laquelle un lecteur voyait un fichier
    absent, et qui echouait par PermissionError des que les deux
    processus se croisaient. C est ce qui a tue le lecteur le 25/08 a
    13:15:37, quinze secondes apres son demarrage.

    Une ecriture qui echoue ne doit jamais tuer la boucle : on reessaie,
    puis on renonce a ce tour-la. Rendre False, pas lever.
    """
    try:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
    except Exception:
        pass
    tmp = "%s.%d.tmp" % (chemin, os.getpid())
    for _ in range(3):
        try:
            with io.open(tmp, "w", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False))
            os.replace(tmp, chemin)
            return True
        except Exception:
            time.sleep(0.02)
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except Exception:
        pass
    return False


def lire_json(chemin, essais=8):
    """Le renommage laisse une fenetre courte ou le fichier n existe pas.
    On reessaie : conclure "plus rien d ouvert" fermerait tout."""
    for _ in range(essais):
        try:
            with io.open(chemin, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, PermissionError, ValueError):
            time.sleep(0.01)
    return None


# ====================================================================
# LECTEUR
# ====================================================================
def lecteur(args):
    if os.path.abspath(args.terminal) == os.path.abspath(TERMINAL_DEDIE):
        dire("lecteur", "REFUS : c est le terminal dedie, pas celui du moteur.")
        return 2
    if not mt5.initialize(path=args.terminal):
        dire("lecteur", "initialize a echoue : %s" % (mt5.last_error(),))
        return 1
    try:
        ai = mt5.account_info()
        if ai is None:
            dire("lecteur", "compte illisible.")
            return 1
        noter_pid("lecteur")
        dire("lecteur", "compte %s  %s  -- LECTURE SEULE, aucun ordre"
             % (masque(ai.login), ai.server))
        dire("lecteur", "plages copiees : %s"
             % ", ".join("%d-%d" % p for p in PLAGES))
        dire("lecteur", "instantane : %s" % INSTANTANE)

        derniere_signature = None
        derniere_ecriture = 0.0
        dernier_dit = time.time()
        echecs = 0
        while True:
            try:
                positions = mt5.positions_get() or []
            except Exception as e:
                dire("lecteur", "positions_get a leve : %s" % e)
                time.sleep(0.5)
                continue
            etat = {}
            for p in positions:
                if not est_miroir(p.magic):
                    continue
                etat[str(p.ticket)] = {
                    "ticket": int(p.ticket), "magic": int(p.magic),
                    "sym": p.symbol, "sens": int(p.type),
                    "volume": round(float(p.volume), 2),
                    "sl": round(float(p.sl), 2), "tp": round(float(p.tp), 2),
                    "ouvert": int(p.time),
                }
            signature = json.dumps(etat, sort_keys=True)
            change = (signature != derniere_signature)
            # On n ecrit que si l etat change, plus un battement par
            # seconde : l horodatage doit rester frais pour que
            # l envoyeur distingue "rien n a bouge" de "le lecteur est
            # mort", mais reecrire vingt fois par seconde ne servait
            # qu a se cogner contre le lecteur d en face.
            maintenant = time.time()
            if change or (maintenant - derniere_ecriture) >= BATTEMENT:
                if ecrire_atomique(INSTANTANE, {"ts": maintenant,
                                                "positions": etat}):
                    derniere_ecriture = maintenant
                    echecs = 0
                else:
                    echecs += 1
                    if echecs in (1, 20, 100):
                        dire("lecteur", "ecriture impossible (%d fois) -- je"
                             " continue" % echecs)
            if change:
                dire("lecteur", "%d position(s) miroir" % len(etat))
                derniere_signature = signature
            if maintenant - dernier_dit >= 300:
                dernier_dit = maintenant
                dire("lecteur", "battement : %d position(s)" % len(etat))
            time.sleep(PERIODE)
    except KeyboardInterrupt:
        dire("lecteur", "arret demande.")
        return 0
    finally:
        mt5.shutdown()


# ====================================================================
# ENVOYEUR
# ====================================================================
BALANCE_PAR_LOT = 20000.0
LOT_MINI = 0.10


def notre_lot(sym):
    """La regle des papers -- balance / 20000, plancher 0.10 -- mais
    appliquee a la balance du compte DEDIE, relue avant chaque prise.

    C est tout l interet d un compte neuf : la taille suit sa propre
    equite. Copier le volume du miroir revenait a dimensionner sur la
    balance du compte du moteur, qui n a rien a voir -- d ou les 0,75
    observes le 25/08 alors que 25 000 / 20 000 fait 1,25.
    """
    try:
        bal = float(mt5.account_info().balance)
    except Exception:
        bal = BALANCE_PAR_LOT
    brut = max(LOT_MINI, bal / BALANCE_PAR_LOT)
    try:
        si = mt5.symbol_info(sym)
        pas = float(si.volume_step) or 0.01
        v = max(float(si.volume_min) or LOT_MINI,
                round(round(brut / pas) * pas, 2))
        return min(v, float(si.volume_max) or 100.0)
    except Exception:
        return round(brut, 2)


def _tk(lien):
    """Le lien etait un simple ticket avant le 25/08 15h ; il porte
    maintenant aussi le rapport de taille. On lit les deux formes."""
    return int(lien["ticket"]) if isinstance(lien, dict) else int(lien)


def _k(lien):
    return float(lien.get("k", 1.0)) if isinstance(lien, dict) else 1.0


def prix(sym, achat):
    t = mt5.symbol_info_tick(sym)
    if t is None:
        return None
    return t.ask if achat else t.bid


# Le mode de remplissage ne s invente pas. Le 25/08 a 14:00, chaque
# ordre est reparti en rc=10030 "Unsupported filling mode" parce que
# IOC etait code en dur : ce courtier veut autre chose sur ces symboles.
# On lit donc le masque du symbole, on essaie dans l ordre, et on retient
# celui qui a marche.
_REMPLISSAGE = {}
NOM_REMPLISSAGE = {0: "FOK", 1: "IOC", 2: "RETURN"}


def modes_possibles(sym):
    try:
        masque = int(getattr(mt5.symbol_info(sym), "filling_mode", 0) or 0)
    except Exception:
        masque = 0
    ordre = []
    if masque & 1:                       # SYMBOL_FILLING_FOK
        ordre.append(getattr(mt5, "ORDER_FILLING_FOK", 0))
    if masque & 2:                       # SYMBOL_FILLING_IOC
        ordre.append(getattr(mt5, "ORDER_FILLING_IOC", 1))
    for m in (getattr(mt5, "ORDER_FILLING_FOK", 0),
              getattr(mt5, "ORDER_FILLING_IOC", 1),
              getattr(mt5, "ORDER_FILLING_RETURN", 2)):
        if m not in ordre:
            ordre.append(m)
    return ordre


def envoyer(req, sym):
    """order_send, en essayant les modes de remplissage jusqu au bon.

    Un refus autre que 10030 est un vrai refus : on le rend tel quel
    plutot que de reessayer, sinon on enverrait quatre fois un ordre
    refuse pour une raison qui n a rien a voir avec le remplissage.
    """
    connu = _REMPLISSAGE.get(sym)
    ordre = ([connu] if connu is not None else []) \
        + [m for m in modes_possibles(sym) if m != connu]
    dernier = None
    for m in ordre:
        req["type_filling"] = m
        dernier = mt5.order_send(req)
        if dernier is None:
            continue
        if dernier.retcode == mt5.TRADE_RETCODE_DONE:
            if _REMPLISSAGE.get(sym) != m:
                _REMPLISSAGE[sym] = m
                dire("envoyeur", "  remplissage retenu pour %s : %s"
                     % (sym, NOM_REMPLISSAGE.get(m, m)))
            return dernier
        if dernier.retcode != 10030:
            return dernier
    return dernier


def ouvrir(src, reel):
    achat = (src["sens"] == 0)
    p = prix(src["sym"], achat)
    if p is None:
        dire("envoyeur", "  pas de prix sur %s" % src["sym"])
        return None
    vol = notre_lot(src["sym"])
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": src["sym"],
        "volume": vol,
        "type": mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL,
        "price": p, "sl": src["sl"], "tp": src["tp"],
        "magic": src["magic"], "comment": "PONT%s" % src["ticket"],
        "type_time": mt5.ORDER_TIME_GTC,
    }
    if not reel:
        dire("envoyeur", "  [SIMULATION] ouvrir %s %s %.2f @ %.2f sl=%.2f"
             % (src["sym"], "BUY" if achat else "SELL", vol, p, src["sl"]))
        return None
    r = envoyer(req, src["sym"])
    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
        dire("envoyeur", "  OUVERTURE REFUSEE rc=%s %s"
             % (getattr(r, "retcode", "?"), getattr(r, "comment", mt5.last_error())))
        return None
    dire("envoyeur", "  ouvert : ticket %s  %.2f lot @ %.2f  (miroir %.2f)"
         % (r.order, vol, r.price, src["volume"]))
    return int(r.order), vol


def fermer(ticket, sym, sens_src, volume, reel):
    """volume None = tout ce qui reste. Sur une sortie totale c est plus
    sur que de recalculer : la position peut avoir ete entamee."""
    if reel:
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            return True
        reste = float(pos[0].volume)
        volume = reste if volume is None else min(volume, reste)
    elif volume is None:
        volume = 0.0
    volume = round(volume, 2)
    if volume <= 0:
        return True
    achat = (sens_src != 0)          # on ferme un SELL par un BUY
    p = prix(sym, achat)
    if p is None:
        return False
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL,
        "position": int(ticket), "price": p,
        "type_time": mt5.ORDER_TIME_GTC,
    }
    if not reel:
        dire("envoyeur", "  [SIMULATION] fermer %.2f sur %s" % (volume, ticket))
        return True
    r = envoyer(req, sym)
    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
        dire("envoyeur", "  FERMETURE REFUSEE rc=%s %s"
             % (getattr(r, "retcode", "?"), getattr(r, "comment", mt5.last_error())))
        return False
    dire("envoyeur", "  ferme %.2f @ %.2f" % (volume, r.price))
    return True


def regler_stops(ticket, sl, tp, reel):
    if not reel:
        dire("envoyeur", "  [SIMULATION] sl=%.2f tp=%.2f sur %s" % (sl, tp, ticket))
        return True
    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP,
                        "position": int(ticket), "sl": sl, "tp": tp})
    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
        dire("envoyeur", "  SL/TP REFUSE rc=%s" % getattr(r, "retcode", "?"))
        return False
    return True


def envoyeur(args):
    if os.path.abspath(args.terminal) == os.path.abspath(TERMINAL_MOTEUR):
        dire("envoyeur", "REFUS : c est le terminal du moteur.")
        return 2
    if not mt5.initialize(path=args.terminal):
        dire("envoyeur", "initialize a echoue : %s" % (mt5.last_error(),))
        return 1
    try:
        ai, ti = mt5.account_info(), mt5.terminal_info()
        if ai is None or ti is None:
            dire("envoyeur", "compte illisible.")
            return 1
        if int(ai.login) != int(args.compte):
            dire("envoyeur", "MAUVAIS COMPTE : attendu %s, trouve %s"
                 % (masque(args.compte), masque(ai.login)))
            return 1
        if ai.trade_mode != getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0):
            dire("envoyeur", "Ce compte n est pas une demo. Refus.")
            return 1
        if not ti.trade_allowed and args.reel:
            dire("envoyeur", "AutoTrading eteint : chaque ordre serait refuse")
            dire("envoyeur", "en rc=10027. Cliquer sur 'Trading Algo'.")
            return 1
        noter_pid("envoyeur")
        dire("envoyeur", "compte %s  %s  solde %.2f %s  -- %s"
             % (masque(ai.login), ai.server, ai.balance, ai.currency,
                "REEL" if args.reel else "SIMULATION"))

        liens = lire_json(LIENS) or {}

        # Le lanceur demarre les deux processus l un apres l autre. Le
        # lecteur peut mettre quelques secondes a joindre son terminal :
        # abandonner ici laisserait la copie a moitie ouverte, ce qui est
        # exactement l oubli qu on cherche a rendre impossible.
        paquet = None
        limite = time.time() + ATTENTE_LECTEUR
        annonce = False
        while paquet is None and time.time() < limite:
            paquet = lire_json(INSTANTANE, essais=1)
            if paquet is None:
                if not annonce:
                    dire("envoyeur", "j attends le premier instantane du lecteur")
                    annonce = True
                time.sleep(0.5)
        if paquet is None:
            dire("envoyeur", "aucun instantane apres %.0f s." % ATTENTE_LECTEUR)
            dire("envoyeur", "Le lecteur n a pas demarre. Rien n a ete envoye.")
            return 1
        precedent = paquet["positions"]
        if args.reprendre:
            dire("envoyeur", "--reprendre : les %d position(s) en cours seront"
                 % len(precedent))
            dire("envoyeur", "copiees au marche, donc a un prix different.")
            precedent = {}
        else:
            dire("envoyeur", "reference de depart : %d position(s), non copiee(s)"
                 % len(precedent))
        dire("envoyeur", "en ecoute.")

        dernier_battement = time.time()
        while True:
            time.sleep(PERIODE)
            paquet = lire_json(INSTANTANE)
            if paquet is None:
                continue
            age = time.time() - float(paquet.get("ts", 0))
            if age > RASSIS:
                dire("envoyeur", "instantane vieux de %.0f s -- lecteur mort ?"
                     % age)
                dire("envoyeur", "je ne ferme rien : un lecteur muet n est pas")
                dire("envoyeur", "un compte vide.")
                time.sleep(2.0)
                continue

            courant = paquet["positions"]

            # -- disparitions et reductions
            for tk, a in list(precedent.items()):
                n = courant.get(tk)
                lien = liens.get(tk)
                if n is None:
                    if lien:
                        dire("envoyeur", "SORTIE M%s %s (miroir %.2f)"
                             % (a["magic"], a["sym"], a["volume"]))
                        # None = tout ce qui reste. La position a pu etre
                        # entamee par un partiel ; recalculer un volume
                        # exposerait a en laisser un residu ouvert.
                        if fermer(_tk(lien), a["sym"], a["sens"], None,
                                  args.reel):
                            liens.pop(tk, None)
                            ecrire_atomique(LIENS, liens)
                    continue
                if n["volume"] < a["volume"] - EPS and lien:
                    delta = round(a["volume"] - n["volume"], 2)
                    # On ferme la meme PROPORTION, pas le meme volume :
                    # nos tailles different de k, et fermer 0,52 quand le
                    # miroir en ferme 0,52 ferait diverger les deux
                    # positions des le premier partiel.
                    notre = round(delta * _k(lien), 2)
                    dire("envoyeur", "REDUCTION M%s %s %.2f  (miroir %.2f)"
                         % (a["magic"], a["sym"], notre, delta))
                    fermer(_tk(lien), a["sym"], a["sens"], notre, args.reel)
                if lien and (abs(n["sl"] - a["sl"]) > EPS
                             or abs(n["tp"] - a["tp"]) > EPS):
                    dire("envoyeur", "STOPS M%s %s sl %.2f -> %.2f"
                         % (a["magic"], a["sym"], a["sl"], n["sl"]))
                    regler_stops(_tk(lien), n["sl"], n["tp"], args.reel)

            # -- apparitions
            for tk, n in courant.items():
                if tk in precedent:
                    continue
                dire("envoyeur", "ENTREE M%s %s %s %.2f"
                     % (n["magic"], n["sym"],
                        "BUY" if n["sens"] == 0 else "SELL", n["volume"]))
                res = ouvrir(n, args.reel)
                if res:
                    ticket_nous, vol_nous = res
                    src = float(n["volume"]) or 1.0
                    liens[tk] = {"ticket": ticket_nous,
                                 "k": round(vol_nous / src, 6)}
                    ecrire_atomique(LIENS, liens)

            precedent = courant
            if time.time() - dernier_battement >= 300:
                dernier_battement = time.time()
                dire("envoyeur", "battement : %d suivie(s), %d a nous"
                     % (len(precedent), len(liens)))

    except KeyboardInterrupt:
        dire("envoyeur", "arret demande.")
        return 0
    finally:
        mt5.shutdown()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lecteur", action="store_true")
    ap.add_argument("--envoyeur", action="store_true")
    ap.add_argument("--terminal", default=None)
    ap.add_argument("--compte", type=int, default=None)
    ap.add_argument("--reel", action="store_true")
    ap.add_argument("--reprendre", action="store_true")
    args = ap.parse_args()

    if args.lecteur == args.envoyeur:
        print("Choisir --lecteur OU --envoyeur.")
        return 2

    # Les deux refus croises passent avant tout le reste. Ils ne doivent
    # dependre de rien, pas meme de la presence du paquet MetaTrader5.
    if args.lecteur:
        args.terminal = args.terminal or TERMINAL_MOTEUR
        if os.path.abspath(args.terminal) == os.path.abspath(TERMINAL_DEDIE):
            print("REFUS : le lecteur ne s attache pas au terminal dedie.")
            return 2
    else:
        args.terminal = args.terminal or TERMINAL_DEDIE
        if os.path.abspath(args.terminal) == os.path.abspath(TERMINAL_MOTEUR):
            print("REFUS : l envoyeur ne s attache pas au terminal du moteur.")
            return 2
        if args.compte is None:
            print("--envoyeur exige --compte.")
            return 2

    if mt5 is None:
        print("MetaTrader5 introuvable dans cet interpreteur.")
        return 2

    return lecteur(args) if args.lecteur else envoyeur(args)


if __name__ == "__main__":
    sys.exit(main())
