#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
miroir_papers.py -- les magics paper en ordres reels.

REGLES : papers_moteur.papers(pe, pr) rend la liste complete
(magic, nom, actif, sens, predicat) -- les SEPT, les LEADERS, les
SANS_PREUVE et la serie 240000 de papers_regles. La decision est prise
par papers_moteur.accepte(entry, t), qui filtre deja actif et sens.
Le miroir ne reecrit aucune regle : il appelle celles du moteur.

SOURCE : churn_trade_logger._save_open() ecrit un JSON atomique
{ticket: record} A L ENTREE du trade, avec l instantane complet
(churn_entry, rails_entry, hlc_churn_entry, epoch_entry, ll_entry).
C est le meme dictionnaire que celui des predicats. Le miroir le LIT.
Il n appelle aucune fonction du journaliseur, n en recalcule aucune,
et ne modifie rien : deux calculs du meme etat pourraient differer,
une lecture non.

Pour chaque nouveau trade parent (206xxx / 207xxx) capture en direct,
il evalue les regles, envoie un ordre reel avec le magic paper --
meme sens, meme SL que le parent -- et ferme quand le parent ferme.

Mesure alors ce que le paper ne pouvait pas voir : latence entre
l entree du parent et l envoi, prix obtenu, spread paye, slippage.

MODES
  (rien)      sonde : lecture seule, montre la table et l etat courant
  --tourner   boucle inerte : journalise, n envoie rien
  --armer     boucle reelle

JOURNAL  docs/miroir_papers.csv
"""

from __future__ import annotations

import csv
import json
import os
import sys
import threading
import time
import traceback
import datetime

SEP = "=" * 92

PARENTS = (206, 207)

# --- VOLUME DU MIROIR -------------------------------------------------------
# "parent" : meme volume que le trade parent. Seul choix qui mesure la
#            VRAIE qualite d execution -- un remplissage a 0.01 n a rien
#            a voir avec un remplissage a 0.91.
# "min"    : volume minimum du symbole. Sans risque, mais le slippage
#            mesure est alors systematiquement sous-estime.
# un nombre (ex 0.10) : volume fixe.
# une fraction ecrite "0.25x" : cette part du volume parent.
LOT = "parent"

# Refus si un ordre consommerait plus que cette part de la marge LIBRE
# du moment. Verifie avant CHAQUE envoi, donc cumulatif : la marge libre
# decroit a chaque ordre passe. 0.25 laisse toujours les trois quarts.
MARGE_MAXI = 0.25

# Plancher de NIVEAU de marge, verifie sur la position PROJETEE.
# MARGE_MAXI seul ne borne pas le cumul : chaque ordre du miroir ne
# coute que ~220 EUR quand la marge libre en fait 15 000, donc la regle
# des 25 % ne mord jamais et laisse ouvrir les 60 miroirs. Soixante
# miroirs au lot du parent, c est le niveau de marge qui s effondre
# vers 130 %, pas la marge libre qui manque. Ce plancher-ci mord.
NIVEAU_MINI = 300.0     # en %, 0 pour desactiver

# --- MIROIR 2 : la meme entree, l ancien regime de sortie ------------------
# Le miroir 1 (magics 220xxx/230xxx/240xxx) est exempte de M154_FOLLOW,
# IGN_COVER et PREOPEN_75 : il sort quand son parent sort, point.
# Le miroir 2 porte le meme magic prefixe d un 4 -- 240004 -> 4240004 --
# donc hors de la plage 220000-249999 de papers_exempt, donc soumis aux
# autres modules comme avant. Meme entree, meme lot, meme instant : le
# seul ecart entre les deux est ce qui decide de la SORTIE.
#
# UNE SEULE difference separe les branches : qui decide de la SORTIE.
# Tout le reste est tenu identique -- meme lot, meme SL a l entree,
# meme recopie du SL apres l entree, meme suivi du volume sur solde
# partiel. C est la condition pour que l ecart mesure entre les deux
# soit attribuable au regime de sortie et a rien d autre.
MIROIR2 = True

MAX_MIROIRS = 60        # compte les DEUX branches
POLL_SEC = 0.5

# Surveillance. Le 21/08 la boucle a tourne six heures sans ecrire une
# ligne : impossible de distinguer  vivante et sans rien a faire  de
# bloquee dans un appel MT5. Un battement periodique tranche, et le
# chien de garde nomme le blocage au lieu de laisser un silence.
BATTEMENT_SEC = 60.0    # une ligne de vie, meme quand rien ne bouge
TOUR_LENT = 2.0         # au-dela, le tour est signale
TOUR_BLOQUE = 30.0      # au-dela, l appel en cours ne rend pas la main
RELIRE_ESSAIS = 4       # open_state.json est remplace atomiquement
RELIRE_PAUSE = 0.05     # par l ecrivain : une lecture peut tomber dessus

# Le miroir doit rester la copie de son parent APRES l entree : les
# parents sont trailes et soldes partiellement, et depuis que les
# autres modules ne touchent plus aux magics paper, personne d autre
# ne le fera. La comparaison porte sur l etat REEL des deux positions,
# pas sur un changement observe : c est ce qui la rend auto-reparatrice
# apres un arret.
SYNC_SEC = 2.0          # pas la peine d y revenir deux fois par seconde
TOLERANCE_PRIX = 1e-4   # en-dessous, c est du bruit de flottant
SL_ESSAIS_MAX = 3       # un SL refuse 3 fois n est plus retente
DEVIATION = 20
LOG_MAX = 4000

DOSSIER_DOCS = "docs"
CSV_JOURNAL = os.path.join(DOSSIER_DOCS, "miroir_papers.csv")
TXT_JOURNAL = os.path.join(DOSSIER_DOCS, "miroir_papers.log")
VERROU = os.path.join(DOSSIER_DOCS, "miroir_papers.lock")
# La table parent -> miroirs doit SURVIVRE a un arret. Sans elle, une
# fenetre fermee laisse des positions ouvertes que plus personne ne
# ferme : seul le SL du parent les protege, et le redemarrage les
# ignore au lieu de les adopter.
LIENS = os.path.join(DOSSIER_DOCS, "miroir_liens.json")
VERROU_PERIME = 15 * 60

COLONNES = [
    "horodatage", "evenement", "ticket_parent", "magic_parent",
    "symbole", "actif", "sens", "prix_parent", "volume_parent", "sl_parent",
    "magic_paper", "regle", "decision", "raison",
    "latence_ms", "prix_demande", "prix_obtenu", "slippage_pts",
    "spread_pts", "bid", "ask",
    "retcode", "ticket_miroir", "volume_miroir",
    "prix_sortie_miroir", "pnl_miroir", "pnl_parent_pts",
]

SENS_VERS_DIR = {"achat": "BUY", "vente": "SELL"}


# ---------------------------------------------------------------- journal
def maintenant():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def dit(msg):
    ligne = "%s  %s" % (maintenant(), msg)
    print(ligne)
    sys.stdout.flush()
    try:
        os.makedirs(DOSSIER_DOCS, exist_ok=True)
        with open(TXT_JOURNAL, "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
    except Exception:
        pass


def taille_journal():
    try:
        if not os.path.exists(TXT_JOURNAL):
            return
        with open(TXT_JOURNAL, encoding="utf-8", errors="replace") as f:
            lignes = f.readlines()
        if len(lignes) > LOG_MAX:
            with open(TXT_JOURNAL, "w", encoding="utf-8") as f:
                f.writelines(lignes[-LOG_MAX:])
    except Exception:
        pass


def csv_ligne(d):
    try:
        os.makedirs(DOSSIER_DOCS, exist_ok=True)
        neuf = not os.path.exists(CSV_JOURNAL)
        with open(CSV_JOURNAL, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLONNES, extrasaction="ignore")
            if neuf:
                w.writeheader()
            d.setdefault("horodatage", maintenant())
            w.writerow(d)
    except Exception as e:
        dit("  journal csv impossible : %s" % e)


# ---------------------------------------------------------------- les regles
def charge_jeu():
    """Le jeu de papers du moteur. Rien n est reecrit ici.

    Rend (entrees, accepte, fenetre, notes) ou :
      entrees : liste de (magic, nom, actif, sens, predicat)
      accepte : la fonction du moteur, accepte(entry, ticket) -> bool
      fenetre : la fonction du moteur, dans_fenetre(ticket) -> bool
                (ou None si le moteur n en a pas)
    """
    notes = []
    try:
        import papers_moteur as pm
    except Exception as e:
        return None, None, None, ["papers_moteur illisible : %s: %s"
                                  % (type(e).__name__, e)]

    charge = getattr(pm, "_charge_modules", None)
    fabrique = getattr(pm, "papers", None)
    accepte = getattr(pm, "accepte", None)
    fenetre = getattr(pm, "dans_fenetre", None)

    for nom, obj in (("_charge_modules", charge), ("papers", fabrique),
                     ("accepte", accepte)):
        if not callable(obj):
            return None, None, None, ["papers_moteur sans %s" % nom]

    try:
        mods = charge()
    except Exception as e:
        return None, None, None, ["_charge_modules a echoue : %s: %s"
                                  % (type(e).__name__, e)]
    if not isinstance(mods, (tuple, list)):
        mods = (mods,)
    notes.append("_charge_modules rend %d objet(s)" % len(mods))

    # On identifie les deux modules par ce qu ils PORTENT, pas par leur
    # rang : papers() lit pe.CLES et pr.REGLES. Supposer l ordre ou le
    # nombre, c est ce qui a fait echouer la v4.
    pe = pr = None
    for m in mods:
        if pe is None and hasattr(m, "CLES"):
            pe = m
        if pr is None and hasattr(m, "REGLES"):
            pr = m

    essais = []
    if pe is not None and pr is not None:
        essais.append(("CLES + REGLES", (pe, pr)))
    if len(mods) >= 2:
        essais.append(("les deux premiers", (mods[0], mods[1])))
    essais.append(("tous", tuple(mods)))

    entrees, derniere = None, "aucun essai"
    for comment, args in essais:
        try:
            entrees = list(fabrique(*args))
            notes.append("papers() appele avec %s" % comment)
            break
        except Exception as e:
            derniere = "%s (%s: %s)" % (comment, type(e).__name__, e)
    if entrees is None:
        return None, None, None, ["papers() a echoue -- dernier essai : %s"
                                  % derniere,
                                  "_charge_modules a rendu %d objet(s) : %s"
                                  % (len(mods),
                                     ", ".join(getattr(m, "__name__", type(m).__name__)
                                               for m in mods))]

    propres = []
    for e in entrees:
        try:
            magic, nom, actif, sens, pred = e[0], e[1], e[2], e[3], e[4]
        except Exception:
            continue
        if isinstance(magic, int) and callable(pred):
            propres.append((magic, nom, actif, sens, pred))

    notes.append("papers_moteur.papers() : %d paper(s)" % len(propres))
    if not callable(fenetre):
        notes.append("pas de dans_fenetre : aucune contrainte de session")
        fenetre = None
    else:
        f = getattr(pm, "FENETRE", None)
        notes.append("fenetre de session : " + (str(f) if f else "aucune"))
    return propres, accepte, fenetre, notes


def fichier_open():
    """Le chemin du JSON des trades ouverts, lu dans le module."""
    try:
        import churn_trade_logger as c
    except Exception as e:
        return None, "churn_trade_logger indisponible : %s" % e
    for nom in ("_OPEN_STATE", "OPEN_STATE", "_OPEN"):
        v = getattr(c, nom, None)
        if isinstance(v, str) and v:
            return v, None
    return None, "aucun chemin d etat trouve dans churn_trade_logger"


def lit_open(chemin):
    """Lit l etat des trades ouverts, en reessayant.

    L ecrivain (churn_trade_logger._save_open) remplace ce fichier par
    os.replace. Sous Windows une lecture qui tombe pendant le
    remplacement est refusee -- PermissionError -- et une lecture qui
    tombe pendant l ecriture du temporaire voit un JSON tronque. Les
    deux sont normales et durent quelques millisecondes. Les traiter
    comme des pannes coutait un tour de boucle a chaque collision :
    dans la nuit du 21/08 le log n a rien contenu d autre.
    """
    dernier = None
    for _ in range(RELIRE_ESSAIS):
        try:
            with open(chemin, encoding="utf-8") as f:
                d = json.load(f)
            return {int(k): v for k, v in d.items()}, None
        except FileNotFoundError:
            return {}, None
        except (PermissionError, OSError, ValueError) as e:
            dernier = e
            time.sleep(RELIRE_PAUSE)
        except Exception as e:
            return None, "%s: %s" % (type(e).__name__, e)
    return None, "%s apres %d essais : %s" % (type(dernier).__name__,
                                              RELIRE_ESSAIS, dernier)


# -- surveillance de la boucle -------------------------------------------
VEILLE = {"debut": None}


def demarre_chien():
    """Signale un tour qui ne rend pas la main. Il ne tue rien.

    Un appel MT5 bloquant ne leve aucune exception : la boucle a l air
    vivante et n ecrit plus rien. Ce fil le nomme.
    """
    def boucle():
        while True:
            time.sleep(5.0)
            t = VEILLE.get("debut")
            if t is not None and (time.time() - t) > TOUR_BLOQUE:
                dit("  TOUR BLOQUE depuis %.0f s -- appel qui ne rend pas"
                    " la main (MT5 ? fichier ?)" % (time.time() - t))
                VEILLE["debut"] = time.time()
    threading.Thread(target=boucle, daemon=True).start()


def battement(m, n_tours, secondes):
    """Une ligne qui prouve que la boucle tourne, meme sans rien a faire."""
    miroirs = sum(len(v) for v in getattr(m, "liens", {}).values())
    try:
        age = time.time() - os.path.getmtime(m.chemin)
        vieux = "%.0f s" % age
    except OSError:
        vieux = "?"
    return ("battement : %d tour(s) en %.0f s, %d parent(s) lie(s),"
            " %d miroir(s), etat vieux de %s"
            % (n_tours, secondes, len(getattr(m, "liens", {})),
               miroirs, vieux))


def magic_double(magic):
    """240004 -> 4240004. Hors de toute plage exemptee."""
    return int("4%d" % int(magic))


def est_miroir2(magic):
    """Le 4 de tete pousse le magic au-dela du million."""
    try:
        return int(magic) >= 1000000
    except (TypeError, ValueError):
        return False


def calcule_lot(info, pos):
    """Le volume du miroir, normalise au pas du symbole."""
    if LOT == "parent":
        v = float(pos.volume)
    elif LOT == "min":
        v = float(info.volume_min)
    elif isinstance(LOT, str) and LOT.endswith("x"):
        try:
            v = float(pos.volume) * float(LOT[:-1])
        except ValueError:
            v = float(info.volume_min)
    else:
        try:
            v = float(LOT)
        except (TypeError, ValueError):
            v = float(info.volume_min)
    pas = float(getattr(info, "volume_step", 0) or 0.01)
    v = round(round(v / pas) * pas, 8)
    v = max(float(info.volume_min), v)
    vmax = float(getattr(info, "volume_max", 0) or 0)
    if vmax:
        v = min(vmax, v)
    return v


def marge_tient(mt5, symbole, achat, lot, prix, combien=1):
    """(bool, message). Non calculable => on laisse passer, et on le dit.

    combien : nombre d ordres que l on s apprete a envoyer d un bloc.
    Avec le miroir 2, les deux partent ensemble ou pas du tout : les
    verifier un par un laisserait passer le premier et refuser le
    second, ce qui casserait la paire et donc la comparaison.
    """
    try:
        besoin = mt5.order_calc_margin(
            mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL,
            symbole, lot, prix)
    except Exception as e:
        return True, "marge non calculable (%s)" % e
    if not besoin:
        return True, "marge non calculable"
    besoin = besoin * max(1, int(combien))
    ai = mt5.account_info()
    libre = float(getattr(ai, "margin_free", 0) or 0)
    if not libre:
        return True, "marge libre inconnue"
    if besoin > libre * MARGE_MAXI:
        return False, ("besoin %.2f > %.0f %% de %.2f libre"
                       % (besoin, MARGE_MAXI * 100, libre))
    if NIVEAU_MINI:
        equite = float(getattr(ai, "equity", 0) or 0)
        marge = float(getattr(ai, "margin", 0) or 0)
        if equite and (marge + besoin) > 0:
            projete = 100.0 * equite / (marge + besoin)
            if projete < NIVEAU_MINI:
                return False, ("niveau de marge projete %.0f %% < %.0f %%"
                               % (projete, NIVEAU_MINI))
    return True, None


def ecrit_liens(liens):
    """Ecriture atomique : un arret pendant l ecriture ne corrompt rien."""
    try:
        os.makedirs(DOSSIER_DOCS, exist_ok=True)
        tmp = LIENS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in liens.items()}, f)
        os.replace(tmp, LIENS)
    except Exception as e:
        dit("  liens non sauvegardes : %s" % e)


def relit_liens():
    try:
        with open(LIENS, encoding="utf-8") as f:
            d = json.load(f)
        return {int(k): [(int(m), int(t)) for m, t in v] for k, v in d.items()}
    except FileNotFoundError:
        return {}
    except Exception as e:
        dit("  liens illisibles (%s) : on repart a vide" % e)
        return {}


# ---------------------------------------------------------------- verrou
def prend_verrou():
    os.makedirs(DOSSIER_DOCS, exist_ok=True)
    try:
        os.makedirs(VERROU)
        return True
    except OSError:
        pass
    try:
        age = time.time() - os.path.getmtime(VERROU)
    except OSError:
        return False
    if age > VERROU_PERIME:
        dit("  verrou perime (%.0f min), reprise" % (age / 60.0))
        try:
            os.rmdir(VERROU)
            os.makedirs(VERROU)
            return True
        except OSError:
            return False
    return False


def rend_verrou():
    try:
        os.rmdir(VERROU)
    except OSError:
        pass


# ---------------------------------------------------------------- miroir
class Miroir(object):

    def __init__(self, mt5, jeu, accepte, fenetre, chemin, armer):
        self.mt5 = mt5
        self.jeu = jeu
        self.accepte = accepte
        self.fenetre = fenetre
        self.chemin = chemin
        self.armer = armer
        self.vus = set()
        self.liens = relit_liens()
        self.dernier = {}
        self.premier_tour = True
        self.rotation = 0
        self.t_sync = 0.0
        self.sl_refus = {}

    # -- envoi -----------------------------------------------------------
    def envoie(self, pos, rec, magic, nom, t_signal, combien=1):
        mt5 = self.mt5
        info = mt5.symbol_info(pos.symbol)
        tick = mt5.symbol_info_tick(pos.symbol)
        if info is None or tick is None:
            return None, "pas de cotation"
        achat = (pos.type == 0)
        prix = tick.ask if achat else tick.bid
        spread = (tick.ask - tick.bid) / info.point if info.point else 0.0
        lot = calcule_lot(info, pos)

        ok_marge, note = marge_tient(mt5, pos.symbol, achat, lot, prix,
                                     combien)
        if not ok_marge:
            csv_ligne({
                "evenement": "MARGE", "ticket_parent": pos.ticket,
                "magic_parent": pos.magic, "symbole": pos.symbol,
                "actif": rec.get("asset"), "sens": "BUY" if achat else "SELL",
                "magic_paper": magic, "regle": nom,
                "decision": "REFUSE", "raison": note,
                "volume_miroir": lot})
            return None, "marge insuffisante : %s" % note

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL,
            "price": prix,
            "deviation": DEVIATION,
            "magic": int(magic),
            "comment": "mir%d" % (pos.magic % 1000),
            "type_time": mt5.ORDER_TIME_GTC,
            # FOK d abord : l IOC n est pas supporte sur US30/NAS100/SPX500
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        if pos.sl:
            req["sl"] = pos.sl
        if pos.tp:
            req["tp"] = pos.tp

        res = mt5.order_send(req)
        if res and res.retcode == 10030:
            req["type_filling"] = mt5.ORDER_FILLING_IOC
            res = mt5.order_send(req)

        rc = res.retcode if res else None
        obtenu = res.price if res and res.retcode == 10009 else None
        slip = None
        if obtenu is not None and info.point:
            slip = (obtenu - prix) / info.point
            if not achat:
                slip = -slip

        csv_ligne({
            "evenement": "ENVOI",
            "ticket_parent": pos.ticket, "magic_parent": pos.magic,
            "symbole": pos.symbol, "actif": rec.get("asset"),
            "sens": "BUY" if achat else "SELL",
            "prix_parent": pos.price_open, "volume_parent": pos.volume,
            "sl_parent": pos.sl,
            "magic_paper": magic, "regle": nom,
            "decision": "PRIS",
            "latence_ms": round((time.time() - t_signal) * 1000.0, 1),
            "prix_demande": prix, "prix_obtenu": obtenu,
            "slippage_pts": None if slip is None else round(slip, 1),
            "spread_pts": round(spread, 1),
            "bid": tick.bid, "ask": tick.ask,
            "retcode": rc,
            "ticket_miroir": res.order if res and res.retcode == 10009 else None,
            "volume_miroir": lot,
        })
        if res and res.retcode == 10009:
            return res.order, None
        return None, "retcode=%s %s" % (rc, res.comment if res else "sans reponse")

    # -- fermeture -------------------------------------------------------
    def _pnl_parent_pts(self, ref):
        if not ref:
            return None
        info = self.mt5.symbol_info(ref.get("symbole") or "")
        pt = getattr(info, "point", 0) or 0
        if not pt:
            return None
        ecart = (ref.get("prix_courant") or 0) - (ref.get("prix_open") or 0)
        if not ref.get("achat", True):
            ecart = -ecart
        return round(ecart / pt, 1)

    def ferme(self, tm, magic, tp, ref):
        mt5 = self.mt5
        pnl_parent = self._pnl_parent_pts(ref)
        trouve = mt5.positions_get(ticket=tm)
        if not trouve:
            csv_ligne({"evenement": "MIROIR_DEJA_FERME", "ticket_parent": tp,
                       "magic_paper": magic, "ticket_miroir": tm,
                       "symbole": ref.get("symbole"),
                       "pnl_parent_pts": pnl_parent})
            return False, "deja fermee"
        p = trouve[0]
        tick = mt5.symbol_info_tick(p.symbol)
        if tick is None:
            return False, "pas de cotation"
        achat = (p.type == 0)
        req = {
            "action": mt5.TRADE_ACTION_DEAL, "position": tm,
            "symbol": p.symbol, "volume": p.volume,
            "type": mt5.ORDER_TYPE_SELL if achat else mt5.ORDER_TYPE_BUY,
            "price": tick.bid if achat else tick.ask,
            "deviation": DEVIATION, "magic": int(magic), "comment": "mirX",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        res = mt5.order_send(req)
        if res and res.retcode == 10030:
            req["type_filling"] = mt5.ORDER_FILLING_IOC
            res = mt5.order_send(req)
        ok = bool(res and res.retcode == 10009)
        csv_ligne({"evenement": "SORTIE", "ticket_parent": tp,
                   "symbole": p.symbol, "magic_paper": magic,
                   "ticket_miroir": tm,
                   "prix_sortie_miroir": res.price if ok else None,
                   "pnl_miroir": p.profit, "pnl_parent_pts": pnl_parent,
                   "volume_parent": ref.get("volume"),
                   "magic_parent": ref.get("magic"),
                   "retcode": res.retcode if res else None})
        return ok, None if ok else (res.comment if res else "sans reponse")

    # -- suivi du parent -------------------------------------------------
    def synchronise(self, par_ticket):
        """Recopie sur les miroirs ce qui a bouge chez le parent.

        Deux choses bougent apres l entree : le SL, deplace par les
        trailings de la stack, et le volume, reduit par les soldes
        partiels. Tant que d autres modules fermaient les miroirs, ca
        n avait pas d importance. Depuis qu ils en sont exemptes, le
        miroir est SEUL a les gerer : s il ne suit pas, sa sortie n a
        plus rien a voir avec celle de son parent et la comparaison
        qu on cherche a faire perd son sens.

        Les DEUX branches en beneficient, miroir 2 compris : lui aussi
        doit rester une copie fidele de son parent partout ailleurs,
        sans quoi l ecart mesure entre les branches melangerait le
        regime de sortie avec un stop qui a diverge en cours de route.

        La regle compare les deux etats REELS plutot que de suivre les
        changements. C est ce qui la rend auto-reparatrice : apres un
        arret, le premier tour realigne au lieu d avoir rate le
        deplacement survenu pendant la coupure.
        """
        for tp, paires in list(self.liens.items()):
            parent = par_ticket.get(int(tp))
            if parent is None:
                continue
            for magic, tm in list(paires):
                m = par_ticket.get(int(tm))
                if m is None:
                    continue
                try:
                    self.aligne_sl(m, parent, magic, tp)
                    self.aligne_volume(m, parent, magic, tp)
                except Exception as e:
                    dit("  suivi M%s ticket %s en erreur : %s"
                        % (magic, tm, e))

    def aligne_sl(self, m, parent, magic, tp):
        """SL et TP du miroir = ceux du parent."""
        if self.sl_refus.get(int(m.ticket), 0) >= SL_ESSAIS_MAX:
            return
        sl = float(parent.sl or 0.0)
        cible_tp = float(parent.tp or 0.0)
        if (abs(float(m.sl or 0.0) - sl) < TOLERANCE_PRIX
                and abs(float(m.tp or 0.0) - cible_tp) < TOLERANCE_PRIX):
            return
        res = self.mt5.order_send({
            "action": self.mt5.TRADE_ACTION_SLTP, "symbol": m.symbol,
            "position": int(m.ticket), "sl": sl, "tp": cible_tp,
            "magic": int(magic)})
        ok = bool(res and res.retcode == 10009)
        if ok:
            self.sl_refus.pop(int(m.ticket), None)
        else:
            n = self.sl_refus.get(int(m.ticket), 0) + 1
            self.sl_refus[int(m.ticket)] = n
            if n == SL_ESSAIS_MAX:
                dit("  SL M%s ticket %s refuse %d fois -- abandon"
                    % (magic, m.ticket, n))
        dit("  SL suivi M%s ticket %s : %s -> %s  %s"
            % (magic, m.ticket, m.sl, sl, "ok" if ok else
               (res.comment if res else "sans reponse")))
        csv_ligne({"evenement": "SL_SUIVI", "ticket_parent": tp,
                   "magic_paper": magic, "ticket_miroir": int(m.ticket),
                   "symbole": m.symbol, "sl_parent": sl,
                   "decision": "OK" if ok else "REFUSE",
                   "retcode": res.retcode if res else None})

    def aligne_volume(self, m, parent, magic, tp):
        """Volume du miroir = volume courant du parent (solde partiel)."""
        if LOT != "parent":
            return
        info = self.mt5.symbol_info(m.symbol)
        pas = float(getattr(info, "volume_step", 0.01) or 0.01)
        mini = float(getattr(info, "volume_min", 0.01) or 0.01)
        trop = float(m.volume) - float(parent.volume)
        if trop < mini - 1e-9:
            return
        vol = round(round(trop / pas) * pas, 8)
        if vol < mini - 1e-9 or vol > float(m.volume) + 1e-9:
            return
        tick = self.mt5.symbol_info_tick(m.symbol)
        if tick is None:
            return
        achat = (m.type == 0)
        req = {"action": self.mt5.TRADE_ACTION_DEAL, "position": int(m.ticket),
               "symbol": m.symbol, "volume": vol,
               "type": self.mt5.ORDER_TYPE_SELL if achat
                       else self.mt5.ORDER_TYPE_BUY,
               "price": tick.bid if achat else tick.ask,
               "deviation": DEVIATION, "magic": int(magic),
               "comment": "mirPART", "type_time": self.mt5.ORDER_TIME_GTC,
               "type_filling": self.mt5.ORDER_FILLING_FOK}
        res = self.mt5.order_send(req)
        if res and res.retcode == 10030:
            req["type_filling"] = self.mt5.ORDER_FILLING_IOC
            res = self.mt5.order_send(req)
        ok = bool(res and res.retcode == 10009)
        dit("  solde partiel suivi M%s ticket %s : %s -> %s  %s"
            % (magic, m.ticket, m.volume, parent.volume,
               "ok" if ok else (res.comment if res else "sans reponse")))
        csv_ligne({"evenement": "PARTIEL_SUIVI", "ticket_parent": tp,
                   "magic_paper": magic, "ticket_miroir": int(m.ticket),
                   "symbole": m.symbol, "volume_miroir": vol,
                   "volume_parent": parent.volume,
                   "decision": "OK" if ok else "REFUSE",
                   "retcode": res.retcode if res else None})

    # -- un tour ---------------------------------------------------------
    def tour(self):
        mt5 = self.mt5
        t_signal = time.time()
        ouverts, err = lit_open(self.chemin)
        if ouverts is None:
            dit("  etat illisible : %s" % err)
            return

        # Un seul appel au lieu d un par ticket : avec quinze parents
        # ouverts la version precedente faisait quinze aller-retours MT5
        # par tour, deux fois par seconde. C est autant d occasions de
        # rester bloque dans l IPC.
        toutes = mt5.positions_get() or []
        par_ticket = dict((int(p.ticket), p) for p in toutes)
        for tk, rec in ouverts.items():
            if not isinstance(rec, dict):
                continue
            p = par_ticket.get(int(tk))
            if p is not None:
                self.dernier[tk] = {
                    "prix_courant": p.price_current,
                    "prix_open": p.price_open,
                    "volume": p.volume, "symbole": p.symbol,
                    "magic": p.magic, "achat": (p.type == 0),
                }

        if self.premier_tour:
            self.vus = set(ouverts.keys())
            self.premier_tour = False
            dit("  %d trade(s) deja ouvert(s) : ignores (entree passee)"
                % len(ouverts))
            if self.liens:
                repris = sum(len(v) for v in self.liens.values())
                dit("  %d miroir(s) repris du tour precedent, sur %d parent(s)"
                    % (repris, len(self.liens)))
                # ceux dont le parent a disparu pendant l arret sont
                # fermes tout de suite : c est exactement ce que la
                # boucle aurait fait si elle avait tourne.
                for tp in list(self.liens.keys()):
                    if tp not in ouverts:
                        ref = self.dernier.pop(tp, {})
                        for magic, tm in self.liens.pop(tp, []):
                            if not self.armer:
                                dit("  [inerte] orphelin M%s (parent %s ferme"
                                    " pendant l arret)" % (magic, tp))
                                continue
                            ok, e = self.ferme(tm, magic, tp, ref)
                            dit("  orphelin M%s ticket %s ferme : %s"
                                % (magic, tm, "ok" if ok else e))
                ecrit_liens(self.liens)
            # ce que le journal ne connait pas ne sera pas ferme d office
            connus = set(t for v in self.liens.values() for _m, t in v)
            magics = set(e[0] for e in self.jeu)
            inconnus = [p for p in toutes
                        if p.magic in magics and p.ticket not in connus]
            if inconnus:
                dit("  ATTENTION : %d position(s) portant un magic paper"
                    % len(inconnus))
                dit("  sans parent connu. Elles ne seront PAS fermees par")
                dit("  le miroir -- il ne sait pas a quoi les rattacher.")
                for p in inconnus[:10]:
                    dit("    ticket %s  M%s  %s  vol %s"
                        % (p.ticket, p.magic, p.symbol, p.volume))
            return

        # --- le miroir reste la copie de son parent
        if self.armer and (time.time() - self.t_sync) >= SYNC_SEC:
            self.t_sync = time.time()
            self.synchronise(par_ticket)

        # --- fermetures
        for tp in list(self.liens.keys()):
            if tp in ouverts:
                continue
            ref = self.dernier.pop(tp, {})
            for magic, tm in self.liens.pop(tp, []):
                if not self.armer:
                    dit("  [inerte] sortie M%s (parent %s ferme)" % (magic, tp))
                    continue
                ok, e = self.ferme(tm, magic, tp, ref)
                dit("  sortie M%s ticket %s : %s" % (magic, tm, "ok" if ok else e))
            ecrit_liens(self.liens)

        # --- entrees
        deja = sum(len(v) for v in self.liens.values())
        for tk, rec in ouverts.items():
            if tk in self.vus or not isinstance(rec, dict):
                continue
            self.vus.add(tk)
            magic_parent = rec.get("magic") or 0
            if magic_parent // 1000 not in PARENTS:
                continue
            dit("  parent %s M%s %s %s @ %s vol %s"
                % (tk, magic_parent, rec.get("asset"), rec.get("dir"),
                   rec.get("entry_price"), rec.get("volume")))

            if not rec.get("entry_captured_live"):
                dit("    instantane absent (entry_captured_live faux) -- ignore")
                csv_ligne({"evenement": "IGNORE", "ticket_parent": tk,
                           "magic_parent": magic_parent,
                           "actif": rec.get("asset"), "sens": rec.get("dir"),
                           "decision": "IGNORE",
                           "raison": "entry_captured_live faux"})
                continue

            if self.fenetre is not None and not self.fenetre(rec):
                dit("    hors fenetre de session -- ignore")
                csv_ligne({"evenement": "HORS_FENETRE", "ticket_parent": tk,
                           "magic_parent": magic_parent,
                           "actif": rec.get("asset"), "sens": rec.get("dir"),
                           "decision": "IGNORE", "raison": "hors fenetre"})
                continue

            # L ordre de parcours TOURNE d un parent a l autre. Sans
            # ca, le plafond refuserait toujours les memes papers -- les
            # derniers de la liste, c est-a-dire la serie 240000 -- et
            # l echantillon serait biaise par construction.
            if self.jeu:
                self.rotation = (self.rotation + 1) % len(self.jeu)
            k = self.rotation
            ordre = self.jeu[k:] + self.jeu[:k]

            pris = []
            for entree in ordre:
                try:
                    if not self.accepte(entree, rec):
                        continue
                except Exception as e:
                    dit("    M%s accepte() en erreur : %s" % (entree[0], e))
                    csv_ligne({"evenement": "ERREUR", "ticket_parent": tk,
                               "magic_paper": entree[0], "regle": entree[1],
                               "actif": rec.get("asset"), "sens": rec.get("dir"),
                               "decision": "ERREUR", "raison": str(e)})
                    continue
                if deja + len(pris) >= MAX_MIROIRS:
                    dit("    plafond %d atteint, M%s non pris"
                        % (MAX_MIROIRS, entree[0]))
                    csv_ligne({"evenement": "PLAFOND", "ticket_parent": tk,
                               "magic_paper": entree[0], "decision": "REFUSE",
                               "raison": "plafond"})
                    continue
                pris.append(entree)

            if not pris:
                dit("    aucun paper ne prend ce trade")
                continue
            dit("    pris par : %s" % ", ".join("M%s" % e[0] for e in pris))

            pos = mt5.positions_get(ticket=tk)
            if not pos:
                dit("    position deja fermee, rien a miroiter")
                continue
            pos = pos[0]

            for entree in pris:
                magic, nom = entree[0], entree[1]
                if not self.armer:
                    info = mt5.symbol_info(pos.symbol)
                    tick = mt5.symbol_info_tick(pos.symbol)
                    sp = ((tick.ask - tick.bid) / info.point
                          if tick and info and info.point else 0)
                    csv_ligne({
                        "evenement": "SIMULE", "ticket_parent": tk,
                        "magic_parent": magic_parent, "symbole": pos.symbol,
                        "actif": rec.get("asset"), "sens": rec.get("dir"),
                        "prix_parent": pos.price_open,
                        "volume_parent": pos.volume, "sl_parent": pos.sl,
                        "magic_paper": magic, "regle": nom,
                        "decision": "PRIS",
                        "latence_ms": round((time.time() - t_signal) * 1000, 1),
                        "prix_demande": (tick.ask if pos.type == 0 else tick.bid)
                                        if tick else None,
                        "spread_pts": round(sp, 1),
                        "bid": tick.bid if tick else None,
                        "ask": tick.ask if tick else None,
                        "volume_miroir": (calcule_lot(info, pos)
                                          if info else None)})
                    continue
                combien = 2 if MIROIR2 else 1
                tm, e = self.envoie(pos, rec, magic, nom, t_signal, combien)
                if not tm:
                    dit("    M%s REFUSE : %s" % (magic, e))
                    continue
                self.liens.setdefault(tk, []).append((magic, tm))
                dit("    M%s envoye, ticket %s" % (magic, tm))
                if not MIROIR2:
                    continue
                # La marge a deja ete verifiee pour DEUX ordres avant le
                # premier : le second ne peut donc pas se voir refuser
                # pour cette raison, et la paire reste entiere.
                m2 = magic_double(magic)
                tm2, e2 = self.envoie(pos, rec, m2, nom, t_signal, 1)
                if tm2:
                    self.liens.setdefault(tk, []).append((m2, tm2))
                    dit("    M%s envoye, ticket %s  (ancien regime)"
                        % (m2, tm2))
                else:
                    dit("    M%s REFUSE : %s  -- paire incomplete,"
                        " ce parent ne comptera pas" % (m2, e2))
            ecrit_liens(self.liens)


# ---------------------------------------------------------------- main
def main():
    args = sys.argv[1:]
    armer = "--armer" in args
    tourner = "--tourner" in args or armer

    print(SEP)
    print("MIROIR PAPERS")
    print(SEP)
    print()
    print("  mode : %s" % ("ARME -- DES ORDRES REELS PARTENT" if armer
                           else ("inerte -- aucun ordre" if tourner
                                 else "sonde -- lecture seule")))
    print()

    jeu, accepte, fenetre, notes = charge_jeu()
    for n in notes:
        print("  %s" % n)
    print()
    if not jeu:
        print("  Aucun paper chargeable. Le miroir n a rien a evaluer.")
        print("  Rien n a ete envoye.")
        return
    print(SEP)
    print("PAPERS QUI PRODUIRONT DES ORDRES")
    print(SEP)
    print()
    print("    magic     actif    sens      regle")
    print("    " + "-" * 80)
    for magic, nom, actif, sens, _p in sorted(jeu, key=lambda e: e[0]):
        print("    %-9s %-8s %-9s %s"
              % (magic, actif or "tous", sens or "les deux", nom))
    print()
    print("  %d paper(s) actif(s)." % len(jeu))
    print()
    if LOT == "parent":
        print("  volume : MEME QUE LE PARENT -- c est le seul reglage qui")
        print("           mesure la vraie qualite d execution.")
    elif LOT == "min":
        print("  volume : minimum du symbole. Le slippage mesure sera")
        print("           sous-estime : ce n est pas la taille reelle.")
    else:
        print("  volume : %s" % (LOT,))
    if MIROIR2:
        print()
        print("  MIROIR 2 ACTIF : chaque paper envoie DEUX ordres.")
        print("    magic tel quel  -> exempte, sort avec son parent")
        print("    magic prefixe 4 -> soumis aux autres modules, comme avant")
        print("    les deux partent ensemble ou pas du tout.")
        print()
    print("  refus au-dela de %.0f %% de la marge libre, avant chaque ordre."
          % (MARGE_MAXI * 100))
    if NIVEAU_MINI:
        print("  refus si le niveau de marge projete tombe sous %.0f %%."
              % NIVEAU_MINI)
    print()

    chemin, err = fichier_open()
    if not chemin:
        print("  %s" % err)
        return
    print("  etat des trades ouverts : %s" % chemin)
    ouverts, e = lit_open(chemin)
    if ouverts is None:
        print("  illisible : %s" % e)
        return
    print("  %d trade(s) dedans" % len(ouverts))
    print()

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("  MetaTrader5 absent de ce python.")
        return
    if not mt5.initialize():
        print("  connexion MT5 impossible : %s" % (mt5.last_error(),))
        return

    try:
        ai = mt5.account_info()
        print("  %s / %s" % (getattr(ai, "server", "?"),
                             {0: "DEMO", 1: "CONCOURS", 2: "REEL"}.get(
                                 getattr(ai, "trade_mode", -1), "?")))
        if getattr(ai, "margin_mode", -1) != 2:
            print("  compte NON hedging : les miroirs fusionneraient. Arret.")
            return
        print()

        if not tourner:
            print(SEP)
            print("  CE QUE LES REGLES DONNENT SUR LES TRADES OUVERTS")
            print(SEP)
            print()
            for tk, rec in sorted(ouverts.items()):
                if not isinstance(rec, dict):
                    continue
                if (rec.get("magic") or 0) // 1000 not in PARENTS:
                    continue
                dedans = fenetre(rec) if fenetre is not None else True
                pris = []
                for e in sorted(jeu, key=lambda x: x[0]):
                    try:
                        if accepte(e, rec):
                            pris.append(e[0])
                    except Exception:
                        pass
                print("    %s M%s %-6s %-4s live=%-5s fen=%-5s -> %s"
                      % (tk, rec.get("magic"), rec.get("asset"),
                         rec.get("dir"), rec.get("entry_captured_live"),
                         dedans,
                         ", ".join("M%s" % m for m in pris) or "aucun"))
            print()
            print(SEP)
            print("  Sonde terminee. Rien n a ete envoye.")
            print(SEP)
            return

        if not prend_verrou():
            print("  une autre instance tourne deja.")
            return
        try:
            if armer:
                print("  ARMEMENT DANS 10 SECONDES -- Ctrl+C pour annuler")
                for i in range(10, 0, -1):
                    sys.stdout.write("\r  %2d " % i)
                    sys.stdout.flush()
                    time.sleep(1)
                print()
            m = Miroir(mt5, jeu, accepte, fenetre, chemin, armer)
            dit("boucle demarree (%s), poll %.1f s"
                % ("ARMEE" if armer else "inerte", POLL_SEC))
            demarre_chien()
            n_tours = 0
            t_battement = time.time()
            while True:
                t0 = time.time()
                VEILLE["debut"] = t0
                try:
                    m.tour()
                except Exception:
                    dit("  tour en erreur :\n%s" % traceback.format_exc())
                VEILLE["debut"] = None
                duree = time.time() - t0
                n_tours += 1
                if duree > TOUR_LENT:
                    dit("  tour lent : %.1f s" % duree)
                ecoule = time.time() - t_battement
                if ecoule >= BATTEMENT_SEC:
                    dit(battement(m, n_tours, ecoule))
                    n_tours = 0
                    t_battement = time.time()
                taille_journal()
                time.sleep(POLL_SEC)
        except KeyboardInterrupt:
            dit("arret demande")
        finally:
            rend_verrou()
    finally:
        mt5.shutdown()

    print()
    print("  Journal : %s" % CSV_JOURNAL)


if __name__ == "__main__":
    main()
