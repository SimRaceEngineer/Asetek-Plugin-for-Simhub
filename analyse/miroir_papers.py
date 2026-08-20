#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
miroir_papers.py -- passer 19 magics paper en ordres reels, et mesurer
                    ce que le paper ne pouvait pas voir.

CE QU IL FAIT
-------------
Un magic paper n est pas une strategie : c est un FILTRE sur le flux
d entrees reel. Son PnL vaut pnl_reel x (lot / volume) -- le PnL du
trade parent, remis a l echelle. Il n a pas de sortie propre.

Le miroir reproduit donc exactement ca, mais en vrai :
  - il surveille les nouveaux tickets des bras 206xxx / 207xxx,
  - pour chaque nouveau trade parent, il evalue les 19 predicats,
  - pour ceux qui passent, il envoie un ordre reel au lot minimum
    avec le magic paper, meme sens, meme SL que le parent,
  - il ferme sa ligne quand le parent ferme.

Ce que le paper supposait et qui devient mesurable :
  - la LATENCE entre l entree du parent et la decision du filtre,
  - le PRIX reellement obtenu a ce moment-la,
  - le SPREAD paye a cet instant precis,
  - le SLIPPAGE entre prix demande et prix obtenu.

TROIS MODES
-----------
  (aucun flag)  SONDE. Ne touche a rien. Cherche ou vivent les
                predicats, verifie les 19, et montre ce qu il ferait
                sur les positions actuellement ouvertes.
  --tourner     BOUCLE INERTE. Tourne en continu, journalise chaque
                decision, N ENVOIE AUCUN ORDRE.
  --armer       BOUCLE REELLE. Envoie. Ferme. Journalise tout.

Ne lance --armer qu apres avoir lu le rapport de la sonde.

JOURNAL
-------
  docs/miroir_papers.csv   une ligne par decision, puis completee
                           a la fermeture. C est ce fichier qui
                           repond a la question live/paper.
"""

from __future__ import annotations

import csv
import os
import sys
import time
import types
import traceback
import datetime

SEP = "=" * 92

# --- les 19 magics demandes -------------------------------------------------
MAGICS = [240007, 220014, 230207, 240004, 230201, 240005, 240002,
          230205, 240001, 220004, 230210, 240008, 240003, 240006,
          230106, 230307, 230102, 230202, 230107]

# les deux temoins sans regle : ils prennent tout leur actif+sens
TEMOINS = {220004, 220014}

# --- les bras dont on miroite les entrees -----------------------------------
# 206102 // 1000 == 206
PARENTS = (206, 207)

# --- garde-fous -------------------------------------------------------------
MAX_MIROIRS = 60        # jamais plus de miroirs ouverts en meme temps
POLL_SEC = 1.0          # la latence mesuree ne peut pas descendre sous ca
DEVIATION = 20          # points de tolerance au slippage
LOG_MAX = 4000          # lignes conservees dans le journal texte

DOSSIER_DOCS = "docs"
CSV_JOURNAL = os.path.join(DOSSIER_DOCS, "miroir_papers.csv")
TXT_JOURNAL = os.path.join(DOSSIER_DOCS, "miroir_papers.log")
VERROU = os.path.join(DOSSIER_DOCS, "miroir_papers.lock")
VERROU_PERIME = 15 * 60

COLONNES = [
    "horodatage", "evenement",
    "ticket_parent", "magic_parent", "symbole", "sens",
    "prix_parent", "volume_parent", "sl_parent",
    "magic_paper", "decision", "raison",
    "latence_ms", "prix_demande", "prix_obtenu", "slippage_pts",
    "spread_pts", "bid", "ask",
    "retcode", "ticket_miroir", "volume_miroir",
    "prix_sortie_miroir", "pnl_miroir", "pnl_parent_pts",
]


# ============================================================================
# journalisation
# ============================================================================
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
    """Borne le journal texte, comme papers_boucle."""
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


def csv_ligne(donnees):
    try:
        os.makedirs(DOSSIER_DOCS, exist_ok=True)
        neuf = not os.path.exists(CSV_JOURNAL)
        with open(CSV_JOURNAL, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLONNES, extrasaction="ignore")
            if neuf:
                w.writeheader()
            donnees.setdefault("horodatage", maintenant())
            w.writerow(donnees)
    except Exception as e:
        dit("  journal csv impossible : %s" % e)


# ============================================================================
# trouver les predicats -- on cherche, on ne suppose pas
# ============================================================================
def fichiers_citant(magics, racine="."):
    """Quels fichiers .py citent ces magics ? Reponse par lecture."""
    cibles = [str(m) for m in magics]
    trouves = {}
    for courant, sous, fichiers in os.walk(racine):
        sous[:] = [s for s in sous
                   if s not in (".git", "__pycache__", "docs", "_legacy")]
        for f in fichiers:
            if not f.endswith(".py"):
                continue
            p = os.path.join(courant, f)
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    texte = fh.read()
            except Exception:
                continue
            combien = sum(1 for c in cibles if c in texte)
            if combien >= 3:
                trouves[p] = combien
    return trouves


def tables_du_module(mod):
    """Les dicts du module dont les cles couvrent nos magics."""
    sortie = []
    for nom in dir(mod):
        if nom.startswith("__"):
            continue
        try:
            obj = getattr(mod, nom)
        except Exception:
            continue
        if not isinstance(obj, dict) or not obj:
            continue
        cles = list(obj.keys())
        entieres = [k for k in cles if isinstance(k, int)]
        couvre = [m for m in MAGICS if m in entieres]
        if len(couvre) >= 3:
            appelables = sum(1 for v in obj.values() if callable(v))
            sortie.append((nom, len(cles), len(couvre), appelables))
    return sortie


def importe(nom):
    try:
        return __import__(nom), None
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


# ============================================================================
# representer un trade parent pour un predicat
# ============================================================================
def etats_possibles(pos):
    """Deux representations du meme trade parent.

    Je ne sais pas si les predicats attendent un dict ou un objet.
    On fabrique les deux, on essaie l un puis l autre, et on retient
    celui qui a marche.
    """
    sens = "BUY" if pos.type == 0 else "SELL"
    base = {
        "ticket": pos.ticket,
        "magic": pos.magic,
        "symbol": pos.symbol,
        "symbole": pos.symbol,
        "actif": pos.symbol,
        "asset": pos.symbol,
        "type": pos.type,
        "sens": sens,
        "direction": sens,
        "side": sens,
        "price_open": pos.price_open,
        "prix": pos.price_open,
        "prix_ouverture": pos.price_open,
        "volume": pos.volume,
        "lot": pos.volume,
        "sl": pos.sl,
        "tp": pos.tp,
        "time": pos.time,
        "ts": pos.time,
        "comment": pos.comment,
        "commentaire": pos.comment,
        "profit": pos.profit,
    }
    objet = types.SimpleNamespace(**base)
    return base, objet


def evalue(predicat, dict_etat, obj_etat, memo, cle):
    """Appelle le predicat sans savoir ce qu il attend.

    La forme retenue est memorisee PAR PREDICAT : rien ne garantit
    que les 19 aient tous la meme signature, et un memo global
    faisait osciller les essais d un magic a l autre.
    """
    connue = memo.get(cle)
    essais = [connue] if connue else ["dict", "objet"]
    derniere = None
    for forme in essais:
        arg = dict_etat if forme == "dict" else obj_etat
        try:
            r = predicat(arg)
            memo[cle] = forme
            return bool(r), None
        except Exception as e:
            derniere = "%s: %s" % (type(e).__name__, e)
    if connue:
        # la forme memorisee ne marche plus : on repart de zero
        memo.pop(cle, None)
        return evalue(predicat, dict_etat, obj_etat, memo, cle)
    return None, derniere


# ============================================================================
# verrou atomique
# ============================================================================
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


# ============================================================================
# le miroir
# ============================================================================
class Miroir(object):

    def __init__(self, mt5, table, armer):
        self.mt5 = mt5
        self.table = table          # magic -> predicat
        self.armer = armer
        self.memo = {}
        self.vus = set()            # tickets parents deja traites
        self.liens = {}             # ticket_parent -> [(magic, ticket_miroir)]
        # dernier etat connu de chaque parent : quand il disparait, on ne
        # peut plus l interroger, or c est son PnL qui sert de reference.
        self.dernier = {}           # ticket_parent -> dict
        self.premier_tour = True

    # -- envoi ------------------------------------------------------------
    def envoie(self, pos, magic_paper, t_signal):
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
            "magic": int(magic_paper),
            "comment": "mir%d" % (pos.magic % 1000),
            "type_time": mt5.ORDER_TIME_GTC,
            # FOK d abord : la reconnaissance a montre que l IOC
            # n est pas supporte sur ces trois symboles.
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

        latence = (time.time() - t_signal) * 1000.0
        rc = res.retcode if res else None
        obtenu = res.price if res and res.retcode == 10009 else None
        slip = None
        if obtenu is not None and info.point:
            slip = (obtenu - prix) / info.point
            if not achat:
                slip = -slip

        commun = {
            "evenement": "ENVOI" if self.armer else "SIMULE",
            "ticket_parent": pos.ticket,
            "magic_parent": pos.magic,
            "symbole": pos.symbol,
            "sens": "BUY" if achat else "SELL",
            "prix_parent": pos.price_open,
            "volume_parent": pos.volume,
            "sl_parent": pos.sl,
            "magic_paper": magic_paper,
            "decision": "PRIS",
            "latence_ms": round(latence, 1),
            "prix_demande": prix,
            "prix_obtenu": obtenu,
            "slippage_pts": None if slip is None else round(slip, 1),
            "spread_pts": round(spread, 1),
            "bid": tick.bid,
            "ask": tick.ask,
            "retcode": rc,
            "ticket_miroir": res.order if res and res.retcode == 10009 else None,
            "volume_miroir": lot,
        }
        csv_ligne(commun)

        if res and res.retcode == 10009:
            return res.order, None
        cm = res.comment if res else "pas de reponse"
        return None, "retcode=%s %s" % (rc, cm)

    # -- fermeture --------------------------------------------------------
    def ferme(self, ticket_miroir, magic_paper, ticket_parent, ref=None):
        mt5 = self.mt5
        ref = ref or {}
        pnl_parent = self._pnl_parent_pts(ref)
        trouve = mt5.positions_get(ticket=ticket_miroir)
        if not trouve:
            # le miroir est parti avant le parent : SL touche, ou ferme
            # a la main. On le consigne, sinon la ligne reste orpheline.
            csv_ligne({
                "evenement": "MIROIR_DEJA_FERME",
                "ticket_parent": ticket_parent, "magic_paper": magic_paper,
                "ticket_miroir": ticket_miroir,
                "symbole": ref.get("symbole"),
                "pnl_parent_pts": pnl_parent,
            })
            return False, "deja fermee"
        p = trouve[0]
        info = mt5.symbol_info(p.symbol)
        tick = mt5.symbol_info_tick(p.symbol)
        if info is None or tick is None:
            return False, "pas de cotation"
        achat = (p.type == 0)
        prix = tick.bid if achat else tick.ask
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket_miroir,
            "symbol": p.symbol,
            "volume": p.volume,
            "type": mt5.ORDER_TYPE_SELL if achat else mt5.ORDER_TYPE_BUY,
            "price": prix,
            "deviation": DEVIATION,
            "magic": int(magic_paper),
            "comment": "mirX",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        res = mt5.order_send(req)
        if res and res.retcode == 10030:
            req["type_filling"] = mt5.ORDER_FILLING_IOC
            res = mt5.order_send(req)
        ok = bool(res and res.retcode == 10009)
        csv_ligne({
            "evenement": "SORTIE",
            "ticket_parent": ticket_parent,
            "symbole": p.symbol,
            "magic_paper": magic_paper,
            "ticket_miroir": ticket_miroir,
            "prix_sortie_miroir": res.price if ok else None,
            "pnl_miroir": p.profit,
            "pnl_parent_pts": pnl_parent,
            "volume_parent": ref.get("volume"),
            "magic_parent": ref.get("magic"),
            "retcode": res.retcode if res else None,
        })
        return ok, None if ok else (res.comment if res else "pas de reponse")

    def _pnl_parent_pts(self, ref):
        """PnL du parent en points d indice, dernier etat connu.

        C est la reference : le paper vaut pnl_parent x (lot/volume).
        Sans elle, la colonne pnl_miroir ne se compare a rien.
        """
        if not ref:
            return None
        info = self.mt5.symbol_info(ref.get("symbole") or "")
        pt = getattr(info, "point", 0) or 0
        if not pt:
            return None
        ecart = (ref.get("prix_courant") or 0) - (ref.get("prix_open") or 0)
        if not ref.get("achat", True):
            ecart = -ecart      # sur un SELL, un prix qui baisse est un gain
        return round(ecart / pt, 1)

    # -- un tour ----------------------------------------------------------
    def tour(self):
        mt5 = self.mt5
        t_signal = time.time()
        positions = mt5.positions_get() or []
        vivants = set(p.ticket for p in positions)

        parents = [p for p in positions if p.magic // 1000 in PARENTS]

        for p in parents:
            self.dernier[p.ticket] = {
                "profit": p.profit, "prix_courant": p.price_current,
                "prix_open": p.price_open, "volume": p.volume,
                "symbole": p.symbol, "magic": p.magic,
                "achat": (p.type == 0),
            }

        if self.premier_tour:
            # on n emboite pas les 27 positions deja ouvertes :
            # leur entree est passee, leur latence n est pas mesurable.
            self.vus = set(p.ticket for p in parents)
            self.premier_tour = False
            dit("  %d parent(s) deja ouvert(s) : ignores (entree passee)"
                % len(parents))
            return

        # --- fermetures : le parent a disparu -----------------------------
        for tp in list(self.liens.keys()):
            if tp in vivants:
                continue
            ref = self.dernier.pop(tp, {})
            for magic_paper, tm in self.liens.pop(tp, []):
                if not self.armer:
                    dit("  [SIMULE] sortie miroir M%s (parent %s ferme)"
                        % (magic_paper, tp))
                    continue
                ok, err = self.ferme(tm, magic_paper, tp, ref)
                dit("  sortie M%s ticket %s : %s"
                    % (magic_paper, tm, "ok" if ok else err))

        # --- nouvelles entrees --------------------------------------------
        ouverts = sum(len(v) for v in self.liens.values())
        for p in parents:
            if p.ticket in self.vus:
                continue
            self.vus.add(p.ticket)
            d, o = etats_possibles(p)
            sens = "BUY" if p.type == 0 else "SELL"
            dit("  parent %s M%s %s %s @ %.2f vol %.2f"
                % (p.ticket, p.magic, p.symbol, sens, p.price_open, p.volume))

            pris = []
            for magic_paper in MAGICS:
                pred = self.table.get(magic_paper)
                if pred is None:
                    continue
                r, err = evalue(pred, d, o, self.memo, magic_paper)
                if r is None:
                    dit("    M%s predicat en erreur : %s" % (magic_paper, err))
                    csv_ligne({"evenement": "ERREUR",
                               "ticket_parent": p.ticket,
                               "magic_paper": magic_paper,
                               "symbole": p.symbol, "sens": sens,
                               "decision": "ERREUR", "raison": err})
                    continue
                if not r:
                    continue
                if ouverts + len(pris) >= MAX_MIROIRS:
                    dit("    plafond de %d miroirs atteint, M%s NON pris"
                        % (MAX_MIROIRS, magic_paper))
                    csv_ligne({"evenement": "PLAFOND",
                               "ticket_parent": p.ticket,
                               "magic_paper": magic_paper,
                               "decision": "REFUSE", "raison": "plafond"})
                    continue
                pris.append(magic_paper)

            if not pris:
                dit("    aucun des 19 ne prend ce trade")
                continue
            dit("    pris par : %s"
                % ", ".join("M%s%s" % (m, "*" if m in TEMOINS else "")
                            for m in pris))

            for magic_paper in pris:
                if not self.armer:
                    info = mt5.symbol_info(p.symbol)
                    tick = mt5.symbol_info_tick(p.symbol)
                    sp = ((tick.ask - tick.bid) / info.point
                          if tick and info and info.point else 0)
                    csv_ligne({
                        "evenement": "SIMULE",
                        "ticket_parent": p.ticket, "magic_parent": p.magic,
                        "symbole": p.symbol, "sens": sens,
                        "prix_parent": p.price_open,
                        "volume_parent": p.volume, "sl_parent": p.sl,
                        "magic_paper": magic_paper, "decision": "PRIS",
                        "latence_ms": round((time.time() - t_signal) * 1000, 1),
                        "prix_demande": (tick.ask if p.type == 0 else tick.bid)
                                        if tick else None,
                        "spread_pts": round(sp, 1),
                        "bid": tick.bid if tick else None,
                        "ask": tick.ask if tick else None,
                        "volume_miroir": info.volume_min if info else None,
                    })
                    continue
                tm, err = self.envoie(p, magic_paper, t_signal)
                if tm:
                    self.liens.setdefault(p.ticket, []).append((magic_paper, tm))
                    dit("    M%s envoye, ticket %s" % (magic_paper, tm))
                else:
                    dit("    M%s REFUSE : %s" % (magic_paper, err))


# ============================================================================
# sonde
# ============================================================================
def sonde(mt5=None):
    print(SEP)
    print("SONDE -- OU VIVENT LES 19 PREDICATS")
    print(SEP)
    print()
    print("  Rien n est envoye, rien n est ferme, rien n est modifie.")
    print()

    print("  Fichiers citant au moins 3 des 19 magics :")
    print()
    cands = fichiers_citant(MAGICS)
    if not cands:
        print("    aucun. Les predicats ne sont pas dans ce dossier.")
    for p in sorted(cands, key=lambda k: -cands[k]):
        print("    %-52s %2d magics cites" % (p, cands[p]))
    print()

    print(SEP)
    print("CE QUE CES MODULES EXPOSENT")
    print(SEP)
    table = {}
    origine = None
    for p in sorted(cands, key=lambda k: -cands[k]):
        nom = os.path.splitext(os.path.basename(p))[0]
        if os.sep in os.path.dirname(p).strip("."):
            continue
        mod, err = importe(nom)
        print()
        print("  %s" % nom)
        if mod is None:
            print("    import impossible : %s" % err)
            continue
        trouvees = tables_du_module(mod)
        if not trouvees:
            print("    aucun dictionnaire indexe par nos magics")
            continue
        for tnom, ncles, ncouvre, nappel in trouvees:
            print("    %-28s %3d cles, couvre %2d/19, %d appelable(s)"
                  % (tnom, ncles, ncouvre, nappel))
            if nappel and ncouvre > (0 if origine is None else -1):
                if origine is None or ncouvre > origine[2]:
                    origine = (nom, tnom, ncouvre)
                    table = dict(getattr(mod, tnom))
    print()

    print(SEP)
    print("COUVERTURE DES 19")
    print(SEP)
    print()
    if not table:
        print("  Aucune table de predicats trouvee automatiquement.")
        print("  Colle-moi la liste ci-dessus, je te dirai quoi extraire.")
        return None
    print("  table retenue : %s.%s" % (origine[0], origine[1]))
    print()
    manquants = []
    for m in MAGICS:
        pred = table.get(m)
        etat = "ok" if callable(pred) else "ABSENT"
        if not callable(pred):
            manquants.append(m)
        marque = " (temoin sans regle)" if m in TEMOINS else ""
        print("    M%-8s %s%s" % (m, etat, marque))
    print()
    if manquants:
        print("  %d magic(s) sans predicat : %s"
              % (len(manquants), ", ".join(str(x) for x in manquants)))
        print("  Le miroir les ignorera. Dis-moi si c est acceptable.")
    else:
        print("  Les 19 ont un predicat.")
    print()
    return table


def sonde_a_blanc(mt5, table):
    """Evalue les predicats sur les positions parentes deja ouvertes."""
    print(SEP)
    print("CE QUE LE MIROIR FERAIT SUR LES POSITIONS ACTUELLES")
    print(SEP)
    print()
    positions = mt5.positions_get() or []
    parents = [p for p in positions if p.magic // 1000 in PARENTS]
    if not parents:
        print("  aucun parent 206xxx/207xxx ouvert.")
        return
    memo = {}
    for p in parents:
        d, o = etats_possibles(p)
        sens = "BUY" if p.type == 0 else "SELL"
        pris, erreurs = [], []
        for m in MAGICS:
            pred = table.get(m)
            if pred is None:
                continue
            r, err = evalue(pred, d, o, memo, m)
            if r is None:
                erreurs.append((m, err))
            elif r:
                pris.append(m)
        print("  parent %s M%s %-8s %-4s @ %9.2f  ->  %d/19"
              % (p.ticket, p.magic, p.symbol, sens, p.price_open, len(pris)))
        if pris:
            print("      %s" % ", ".join("M%s%s" % (m, "*" if m in TEMOINS else "")
                                          for m in pris))
        for m, err in erreurs[:3]:
            print("      M%s erreur : %s" % (m, err))
    print()
    formes = {}
    for m, f in memo.items():
        formes.setdefault(f, []).append(m)
    if not formes:
        print("  aucun predicat n a pu etre appele.")
    for f in sorted(formes):
        print("  appeles avec un %-6s : %s"
              % (f, ", ".join("M%s" % x for x in sorted(formes[f]))))
    print()


# ============================================================================
# main
# ============================================================================
def main():
    args = sys.argv[1:]
    armer = "--armer" in args
    tourner = "--tourner" in args or armer

    print(SEP)
    print("MIROIR PAPERS -- 19 MAGICS")
    print(SEP)
    print()
    if armer:
        print("  MODE ARME : DES ORDRES REELS VONT ETRE ENVOYES.")
    elif tourner:
        print("  MODE INERTE : boucle active, aucun ordre envoye.")
    else:
        print("  MODE SONDE : lecture seule, aucune boucle.")
    print()

    table = sonde()

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("  MetaTrader5 absent de ce python : on s arrete a la sonde.")
        return

    if not mt5.initialize():
        print("  connexion MT5 impossible : %s" % (mt5.last_error(),))
        return

    try:
        ti = mt5.terminal_info()
        ai = mt5.account_info()
        print(SEP)
        print("TERMINAL")
        print(SEP)
        print("  %s" % (getattr(ti, "path", "?")))
        print("  %s / %s"
              % (getattr(ai, "server", "?"),
                 {0: "DEMO", 1: "CONCOURS", 2: "REEL"}.get(
                     getattr(ai, "trade_mode", -1), "?")))
        if getattr(ai, "margin_mode", -1) != 2:
            print()
            print("  Le compte n est PAS en hedging. Les miroirs")
            print("  fusionneraient. On s arrete.")
            return
        print()

        if table:
            sonde_a_blanc(mt5, table)

        if not tourner:
            print(SEP)
            print("  Sonde terminee. Rien n a ete envoye.")
            print("  Colle-moi ce rapport avant de lancer --tourner.")
            print(SEP)
            return

        if not table:
            print("  Pas de table de predicats : la boucle n a rien a evaluer.")
            return

        if not prend_verrou():
            print("  une autre instance tourne deja (verrou present).")
            return

        try:
            if armer:
                print(SEP)
                print("  ARMEMENT DANS 10 SECONDES -- Ctrl+C pour annuler")
                print("  lot minimum, meme sens et meme SL que le parent,")
                print("  plafond de %d miroirs simultanes." % MAX_MIROIRS)
                print(SEP)
                for i in range(10, 0, -1):
                    sys.stdout.write("\r  %2d " % i)
                    sys.stdout.flush()
                    time.sleep(1)
                print()

            m = Miroir(mt5, table, armer)
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
    print(SEP)
    print("  Journal : %s" % CSV_JOURNAL)
    print(SEP)


if __name__ == "__main__":
    main()
