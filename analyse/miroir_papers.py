#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
miroir_papers.py -- les magics paper en ordres reels.

SOURCE : churn_trade_logger._save_open() ecrit un JSON atomique
{ticket: record} A L ENTREE du trade, avec l instantane complet
(churn_entry, rails_entry, hlc_churn_entry, epoch_entry, ll_entry).
C est le meme dictionnaire que celui des predicats. Le miroir le LIT.
Il n appelle aucune fonction du journaliseur, n en recalcule aucune,
et ne modifie rien : deux calculs du meme etat pourraient differer,
une lecture non.

Pour chaque nouveau trade parent (206xxx / 207xxx) capture en direct,
il evalue les regles, envoie un ordre au LOT MINIMUM avec le magic
paper -- meme sens, meme SL que le parent -- et ferme quand le
parent ferme.

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
MAX_MIROIRS = 60
POLL_SEC = 0.5
DEVIATION = 20
LOG_MAX = 4000

DOSSIER_DOCS = "docs"
CSV_JOURNAL = os.path.join(DOSSIER_DOCS, "miroir_papers.csv")
TXT_JOURNAL = os.path.join(DOSSIER_DOCS, "miroir_papers.log")
VERROU = os.path.join(DOSSIER_DOCS, "miroir_papers.lock")
VERROU_PERIME = 15 * 60

# --- les deux temoins sans regle -------------------------------------------
# Ils prennent TOUT leur actif et leur sens, sans condition. Leur actif
# et leur sens ne sont ecrits nulle part dans le code : tant qu ils ne
# sont pas renseignes ici, le miroir les ignore et le dit. Il ne les
# devine pas.
#   exemple :  TEMOINS = {220004: ("US30", "BUY"), 220014: ("US30", "SELL")}
TEMOINS = {220004: ('US30', 'SELL'), 220014: ('US500', 'BUY')}

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


# ---------------------------------------------------------------- la table
class Regle(object):
    """Un magic, sa fonction, son sens impose, sa provenance."""

    def __init__(self, magic, nom, sens, fn, source):
        self.magic = magic
        self.nom = nom
        self.sens = sens            # "achat", "vente" ou None
        self.fn = fn
        self.source = source

    def dir_impose(self):
        return SENS_VERS_DIR.get(self.sens)

    def prend(self, rec):
        """(bool, raison). Une exception rend None, jamais un faux vrai."""
        d = self.dir_impose()
        if d and rec.get("dir") != d:
            return False, "sens impose %s" % d
        try:
            r = self.fn(rec)
        except Exception as e:
            return None, "%s: %s" % (type(e).__name__, e)
        if isinstance(r, tuple):        # gate_230207.decide -> (bool, raison)
            return bool(r[0]), (r[1] if len(r) > 1 else None)
        return bool(r), None


def charge_table():
    """Les regles reellement disponibles. Rien n est suppose."""
    table, notes = {}, []

    # --- serie 240000 : liste de tuples (magic, nom, sens, fonction)
    try:
        import papers_regles
        for t in getattr(papers_regles, "REGLES", []):
            try:
                magic, nom, sens, fn = t[0], t[1], t[2], t[3]
            except Exception:
                continue
            if isinstance(magic, int) and callable(fn):
                table[magic] = Regle(magic, nom, sens, fn, "papers_regles")
        notes.append("papers_regles : %d regle(s)" % len(table))
    except Exception as e:
        notes.append("papers_regles indisponible : %s" % e)

    # --- 230207 : une fonction posee a la racine de son module
    try:
        import gate_230207
        fn = getattr(gate_230207, "decide", None)
        if callable(fn):
            table[230207] = Regle(230207, "GATE 230207", None, fn,
                                  "gate_230207.decide")
            notes.append("gate_230207.decide : 1 regle")
        else:
            notes.append("gate_230207 sans fonction decide")
    except Exception as e:
        notes.append("gate_230207 indisponible : %s" % e)

    # --- les temoins, uniquement si renseignes
    for magic, spec in TEMOINS.items():
        try:
            actif, sens_dir = spec
        except Exception:
            continue

        def fabrique(a, s):
            def f(rec):
                return rec.get("asset") == a and rec.get("dir") == s
            return f
        table[magic] = Regle(magic, "TEMOIN %s %s" % (actif, sens_dir),
                             None, fabrique(actif, sens_dir), "TEMOINS")
    if TEMOINS:
        notes.append("temoins : %d" % len(TEMOINS))
    else:
        notes.append("temoins 220004/220014 NON DEFINIS -- ignores")

    return table, notes


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

    def __init__(self, mt5, table, chemin, armer):
        self.mt5 = mt5
        self.table = table
        self.chemin = chemin
        self.armer = armer
        self.vus = set()
        self.liens = {}
        self.dernier = {}
        self.premier_tour = True

    # -- envoi -----------------------------------------------------------
    def envoie(self, pos, rec, regle, t_signal):
        mt5 = self.mt5
        info = mt5.symbol_info(pos.symbol)
        tick = mt5.symbol_info_tick(pos.symbol)
        if info is None or tick is None:
            return None, "pas de cotation"
        achat = (pos.type == 0)
        prix = tick.ask if achat else tick.bid
        spread = (tick.ask - tick.bid) / info.point if info.point else 0.0
        lot = info.volume_min

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL,
            "price": prix,
            "deviation": DEVIATION,
            "magic": int(regle.magic),
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
            "magic_paper": regle.magic, "regle": regle.nom,
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

            pris = []
            for magic in sorted(self.table):
                regle = self.table[magic]
                r, raison = regle.prend(rec)
                if r is None:
                    dit("    M%s en erreur : %s" % (magic, raison))
                    csv_ligne({"evenement": "ERREUR", "ticket_parent": tk,
                               "magic_paper": magic, "regle": regle.nom,
                               "actif": rec.get("asset"), "sens": rec.get("dir"),
                               "decision": "ERREUR", "raison": raison})
                    continue
                if not r:
                    continue
                if deja + len(pris) >= MAX_MIROIRS:
                    dit("    plafond %d atteint, M%s non pris" % (MAX_MIROIRS, magic))
                    csv_ligne({"evenement": "PLAFOND", "ticket_parent": tk,
                               "magic_paper": magic, "decision": "REFUSE",
                               "raison": "plafond"})
                    continue
                pris.append(regle)

            if not pris:
                dit("    aucune regle ne prend ce trade")
                continue
            dit("    pris par : %s" % ", ".join("M%s" % r.magic for r in pris))

            pos = mt5.positions_get(ticket=tk)
            if not pos:
                dit("    position deja fermee, rien a miroiter")
                continue
            pos = pos[0]

            for regle in pris:
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
                        "magic_paper": regle.magic, "regle": regle.nom,
                        "decision": "PRIS",
                        "latence_ms": round((time.time() - t_signal) * 1000, 1),
                        "prix_demande": (tick.ask if pos.type == 0 else tick.bid)
                                        if tick else None,
                        "spread_pts": round(sp, 1),
                        "bid": tick.bid if tick else None,
                        "ask": tick.ask if tick else None,
                        "volume_miroir": info.volume_min if info else None})
                    continue
                tm, e = self.envoie(pos, rec, regle, t_signal)
                if tm:
                    self.liens.setdefault(tk, []).append((regle.magic, tm))
                    dit("    M%s envoye, ticket %s" % (regle.magic, tm))
                else:
                    dit("    M%s REFUSE : %s" % (regle.magic, e))


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

    table, notes = charge_table()
    for n in notes:
        print("  %s" % n)
    print()
    print(SEP)
    print("REGLES QUI PRODUIRONT DES ORDRES")
    print(SEP)
    print()
    print("    magic     sens impose   source                 regle")
    print("    " + "-" * 84)
    for magic in sorted(table):
        r = table[magic]
        print("    %-9s %-13s %-22s %s"
              % (r.magic, r.dir_impose() or "les deux", r.source, r.nom))
    print()
    print("  %d regle(s) active(s)." % len(table))
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
                pris = []
                for magic in sorted(table):
                    r, _ = table[magic].prend(rec)
                    if r:
                        pris.append(magic)
                print("    %s M%s %-6s %-4s live=%-5s -> %s"
                      % (tk, rec.get("magic"), rec.get("asset"),
                         rec.get("dir"), rec.get("entry_captured_live"),
                         ", ".join("M%s" % m for m in pris) or "aucune"))
            print()
            print(SEP)
            print("  Sonde terminee. Rien n a ete envoye.")
            print(SEP)
            return

        if not table:
            print("  aucune regle : la boucle n aurait rien a evaluer.")
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
            m = Miroir(mt5, table, chemin, armer)
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
