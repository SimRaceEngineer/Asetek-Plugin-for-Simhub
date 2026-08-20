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

MAX_MIROIRS = 60
POLL_SEC = 0.5
DEVIATION = 20
LOG_MAX = 4000

DOSSIER_DOCS = "docs"
CSV_JOURNAL = os.path.join(DOSSIER_DOCS, "miroir_papers.csv")
TXT_JOURNAL = os.path.join(DOSSIER_DOCS, "miroir_papers.log")
VERROU = os.path.join(DOSSIER_DOCS, "miroir_papers.lock")
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
    try:
        with open(chemin, encoding="utf-8") as f:
            d = json.load(f)
        return {int(k): v for k, v in d.items()}, None
    except FileNotFoundError:
        return {}, None
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


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


def marge_tient(mt5, symbole, achat, lot, prix):
    """(bool, message). Non calculable => on laisse passer, et on le dit."""
    try:
        besoin = mt5.order_calc_margin(
            mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL,
            symbole, lot, prix)
    except Exception as e:
        return True, "marge non calculable (%s)" % e
    if not besoin:
        return True, "marge non calculable"
    ai = mt5.account_info()
    libre = float(getattr(ai, "margin_free", 0) or 0)
    if not libre:
        return True, "marge libre inconnue"
    if besoin > libre * MARGE_MAXI:
        return False, ("besoin %.2f > %.0f %% de %.2f libre"
                       % (besoin, MARGE_MAXI * 100, libre))
    return True, None


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
        self.liens = {}
        self.dernier = {}
        self.premier_tour = True

    # -- envoi -----------------------------------------------------------
    def envoie(self, pos, rec, magic, nom, t_signal):
        mt5 = self.mt5
        info = mt5.symbol_info(pos.symbol)
        tick = mt5.symbol_info_tick(pos.symbol)
        if info is None or tick is None:
            return None, "pas de cotation"
        achat = (pos.type == 0)
        prix = tick.ask if achat else tick.bid
        spread = (tick.ask - tick.bid) / info.point if info.point else 0.0
        lot = calcule_lot(info, pos)

        ok_marge, note = marge_tient(mt5, pos.symbol, achat, lot, prix)
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

    # -- un tour ---------------------------------------------------------
    def tour(self):
        mt5 = self.mt5
        t_signal = time.time()
        ouverts, err = lit_open(self.chemin)
        if ouverts is None:
            dit("  etat illisible : %s" % err)
            return

        for tk, rec in ouverts.items():
            if not isinstance(rec, dict):
                continue
            p = mt5.positions_get(ticket=tk)
            if p:
                self.dernier[tk] = {
                    "prix_courant": p[0].price_current,
                    "prix_open": p[0].price_open,
                    "volume": p[0].volume, "symbole": p[0].symbol,
                    "magic": p[0].magic, "achat": (p[0].type == 0),
                }

        if self.premier_tour:
            self.vus = set(ouverts.keys())
            self.premier_tour = False
            dit("  %d trade(s) deja ouvert(s) : ignores (entree passee)"
                % len(ouverts))
            return

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

            pris = []
            for entree in self.jeu:
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
                tm, e = self.envoie(pos, rec, magic, nom, t_signal)
                if tm:
                    self.liens.setdefault(tk, []).append((magic, tm))
                    dit("    M%s envoye, ticket %s" % (magic, tm))
                else:
                    dit("    M%s REFUSE : %s" % (magic, e))


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
    print("  refus au-dela de %.0f %% de la marge libre, avant chaque ordre."
          % (MARGE_MAXI * 100))
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
            while True:
                try:
                    m.tour()
                except Exception:
                    dit("  tour en erreur :\n%s" % traceback.format_exc())
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
