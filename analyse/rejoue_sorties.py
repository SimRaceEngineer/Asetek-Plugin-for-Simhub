#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""rejoue_sorties.py -- break-even et trailing, mesures barre par barre.

CE QUE LES DEUX AUTRES ETUDES NE POUVAIENT PAS FAIRE
----------------------------------------------------
mfe_partage.py a chiffre le GISEMENT : 48 % des perdants passaient par
+0.25R avant de mourir, 76 119 EUR de pertes concernees. C etait une
borne haute -- elle ne comptait pas ce qu un break-even aurait coute
aux gagnants qui repassent par le meme niveau avant de repartir.

tp_fixe.py a pu trancher le take-profit sans rejeu, parce qu un TP est
rempli si et seulement si le MFE atteint le niveau. Verdict : negatif
partout. La raison tient en une ligne du detail -- sur 240007, 64
gagnants rabotes coutent 3 654 quand 94 releves rapportent 3 533. La
queue porte le resultat, et un plafond la coupe.

Un break-even et un trailing, eux, dependent de l ORDRE dans lequel le
prix touche deux niveaux. Le journal ne garde que les deux extremes,
pas leur chronologie. Il faut donc rejouer le chemin.

CE QU IL REJOUE, ET CONTRE QUOI
-------------------------------
Pour chaque position fermee du compte moteur, on relit les barres M1
de son ouverture a sa fermeture et on applique une politique de
sortie. Si la politique declenche AVANT la sortie reelle, elle la
remplace. Sinon le trade finit ou il a fini.

C est le bon contrefactuel : on ne modelise pas le stop d origine --
inutile, puisque la sortie reelle l embarque deja. On ne change que ce
que la politique change.

LES POLITIQUES
    BE(x)          des que le prix atteint +x.R, le stop passe a l entree.
    TRAIL(d, a)    arme a +a.R, le stop suit a d.R sous le plus haut.
    BE(x)+TRAIL    les deux, le plus protecteur des deux l emporte.

Dans tous les cas le stop ne RECULE JAMAIS -- c est le cliquet, pose
dans la stack depuis le 27/08 au matin, et ici par construction.

LA CONVENTION DE BARRE, REPRISE DE bilan_c14.py
-----------------------------------------------
Un niveau calcule sur la barre i ne devient actif qu a la barre i+1.
On ne declenche donc jamais un stop sur le creux de la minute ou il
vient d etre demande -- ce serait se donner une information qu on n
avait pas.

Consequence assumee : le rejeu est PRUDENT pour le declenchement (il
en rate) et le prix de sortie est le niveau du stop, pas mieux.

CE QU IL FAUT SAVOIR SUR LE PRIX
--------------------------------
Les barres M1 de MT5 sont construites sur le BID. Un stop d ACHAT qui
se declenche sur le bas de barre est donc exact ; un stop de VENTE sur
le haut de barre est optimiste d un spread. Le panneau donne le
compte des deux sens pour que le biais soit visible au lieu d etre
suppose negligeable.

R -- LA MEME CONVENTION QUE LES DEUX AUTRES ETUDES
--------------------------------------------------
R est la PERTE MOYENNE REALISEE du magic, en euros, convertie en
points pour chaque position via son propre eur_pt. Ce n est pas une
distance de stop : c est ou les sorties ont reellement atterri.

LES CONTROLES
-------------
    barres manquantes   un ticket sans barres n est pas rejoue, et il
                        est COMPTE. Une etude qui perd la moitie de sa
                        population sans le dire ne mesure rien.
    eur_pt degenere     une position d amplitude nulle ne donne pas de
                        conversion : comptee a part.
    MFE croise          le MFE recalcule depuis les barres est compare
                        a celui du journal. S ils divergent, ce sont
                        les barres ou le journal qui mentent, et il
                        faut le savoir AVANT de lire les resultats.

LECTURE SEULE -- il importe MetaTrader5 pour LIRE l historique et les
barres, et n envoie aucun ordre. Il vise explicitement le terminal du
MOTEUR : mt5.initialize() sans chemin s attache au terminal par
defaut, qui sur cette machine est l autre.

OU IL ECRIT
-----------
    panels\panel_rejoue_sorties.txt
    cartes\rejoue_sorties.html       visible dans la liste /cartes

USAGE
-----
    python rejoue_sorties.py
    python rejoue_sorties.py --limite 300        essai rapide
    python rejoue_sorties.py --jours 30
"""

from __future__ import annotations

import argparse
import bisect
import io
import json
import os
import sys
import time
from datetime import datetime

JOURNAL = os.path.join("docs", "papers_live", "trades.jsonl")
SORTIE_T = os.path.join("panels", "panel_rejoue_sorties.txt")
SORTIE_H = os.path.join("cartes", "rejoue_sorties.html")
CACHE = os.path.join("docs", "rejoue_sorties")

TERMINAL_MOTEUR = (r"C:\Program Files\TF Global Markets MetaTrader 5 "
                   r"Termina-LOCALSTACKl\terminal64.exe")

# Le decalage a appliquer a la REQUETE de barres se MESURE, il ne se
# suppose pas -- lecon du 25/08.
DECALAGES = (0, 3600, -3600, 7200, -7200, 10800, -10800)
_dec_ok = [None]

BE_SEUILS = (0.20, 0.30, 0.40, 0.50, 0.60)
TR_DIST = (0.50, 0.75, 1.00, 1.50)
TR_ARME = 0.50
COMBOS = ((0.30, 1.00), (0.30, 1.50), (0.50, 1.00), (0.50, 1.50))

LARGE = 118


def dt(ts):
    return datetime.utcfromtimestamp(float(ts))


def barre(c="="):
    return c * LARGE


def lire_jsonl(chemin):
    out, ko = [], 0
    if not os.path.isfile(chemin):
        return out, ko
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for l in f:
            l = l.strip()
            if not l:
                continue
            try:
                o = json.loads(l)
            except ValueError:
                ko += 1
                continue
            if isinstance(o, dict):
                out.append(o)
    return out, ko


def noms_des_papers():
    try:
        import papers_moteur as PM
        pe, pr, manque = PM._charge_modules()
        if manque:
            return {}, "modules absents : %s" % ", ".join(manque)
        return dict((j[0], j[1]) for j in PM.papers(pe, pr)), ""
    except Exception as e:
        return {}, str(e)[:120]


# ----------------------------------------------------------------------
# MT5 -- historique et barres
# ----------------------------------------------------------------------
def deals_fenetre(mt5, t0, t1, dire):
    """{position_id: [deals]}. Jour par jour : un seul appel large ne
    ramene qu une tranche -- le terminal ne sert que ce qu il a en cache."""
    par_pos = {}
    j, vus, gardes = t0, 0, 0
    while j < t1:
        k = min(j + 86400.0, t1)
        try:
            mt5.history_select(dt(j), dt(k))
        except Exception:
            pass
        lot = mt5.history_deals_get(dt(j), dt(k))
        vus += 0 if lot is None else len(lot)
        for d in (lot or []):
            pid = int(d.position_id)
            if pid == 0:
                continue        # operation de balance : ni position ni symbole
            par_pos.setdefault(pid, []).append(d)
            gardes += 1
        j = k
    dire("  historique : %d deal(s) lus, %d rattaches a %d position(s)"
         % (vus, gardes, len(par_pos)))
    return par_pos


def resume_position(mt5, deals):
    """(sens, entree, sortie, profit, t_ouv, t_fer, symbole) ou None."""
    ins = [d for d in deals if d.entry == mt5.DEAL_ENTRY_IN]
    outs = [d for d in deals if d.entry in (mt5.DEAL_ENTRY_OUT,
                                            mt5.DEAL_ENTRY_OUT_BY)]
    if not ins or not outs:
        return None
    vin = sum(float(d.volume) for d in ins) or 1.0
    entree = sum(float(d.price) * float(d.volume) for d in ins) / vin
    vout = sum(float(d.volume) for d in outs) or 1.0
    sortie = sum(float(d.price) * float(d.volume) for d in outs) / vout
    profit = sum(float(d.profit) for d in outs)
    sens = 1 if ins[0].type == mt5.DEAL_TYPE_BUY else -1
    return (sens, entree, sortie, profit,
            min(int(d.time) for d in ins), max(int(d.time) for d in outs),
            ins[0].symbol)


def charge_barres(mt5, sym, t0, t1, cache, dire):
    """Toutes les M1 du symbole sur la periode, une fois pour toutes.

    On les prend par tranches d un jour et on garde le tout en memoire :
    7 000 positions demanderaient 7 000 appels, trois symboles en
    demandent une centaine.
    """
    chem = os.path.join(cache, "%s.json" % sym.replace("/", "_"))
    if os.path.isfile(chem):
        try:
            with io.open(chem, encoding="utf-8") as f:
                d = json.load(f)
            if d.get("t0") <= t0 and d.get("t1") >= t1 and d.get("bars"):
                dire("  %-8s %6d barre(s) relues du cache" % (sym, len(d["bars"])))
                return d["bars"]
        except Exception:
            pass

    out, j = [], t0
    essais = ([_dec_ok[0]] if _dec_ok[0] is not None else []) + list(DECALAGES)
    while j < t1:
        k = min(j + 86400.0, t1)
        pris = None
        for dec in essais:
            if dec is None:
                continue
            try:
                r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1,
                                         dt(j - 120 + dec), dt(k + 120 + dec))
            except Exception:
                continue
            if r is None or len(r) == 0:
                continue
            deb, fin = int(r[0]["time"]), int(r[-1]["time"])
            if fin >= j - 600 and deb <= k + 600:
                _dec_ok[0] = dec
                essais = [dec]
                pris = r
                break
        for b in (pris if pris is not None else []):
            out.append([int(b["time"]), float(b["high"]), float(b["low"])])
        j = k

    out.sort(key=lambda x: x[0])
    dedup, vu = [], -1
    for b in out:
        if b[0] != vu:
            dedup.append(b)
            vu = b[0]
    dire("  %-8s %6d barre(s) chargee(s)" % (sym, len(dedup)))
    try:
        if not os.path.isdir(cache):
            os.makedirs(cache)
        with io.open(chem, "w", encoding="utf-8") as f:
            json.dump({"t0": t0, "t1": t1, "bars": dedup}, f)
    except Exception:
        pass                    # un cache qui tombe n arrete pas la mesure
    return dedup


def tranche(bars, temps, t0, t1):
    i = bisect.bisect_left(temps, t0 - 60)
    j = bisect.bisect_right(temps, t1 + 60)
    return bars[i:j]


# ----------------------------------------------------------------------
# le rejeu
# ----------------------------------------------------------------------
def rejoue(bars, sens, entree, r_pts, be, trail, arme):
    """Prix de sortie impose par la politique, ou None si elle ne fait rien.

    Le stop ne recule jamais : c est le cliquet, par construction.

    Un niveau calcule sur la barre i ne devient actif qu a la barre
    i+1 -- on ne se donne pas l information de la minute en cours.
    """
    stop = None
    attente = None
    best = entree
    arme_ok = (arme is None)

    for b in bars:
        # 1. ce qui a ete demande a la barre precedente devient actif,
        #    et seulement dans le sens qui protege
        if attente is not None:
            if stop is None:
                stop = attente
            elif (attente - stop) * sens > 0:
                stop = attente
            attente = None

        # 2. le stop actif est teste sur CETTE barre
        if stop is not None:
            if sens > 0 and b[2] <= stop:
                return stop
            if sens < 0 and b[1] >= stop:
                return stop

        # 3. l extreme favorable de cette barre met a jour la demande
        ex = b[1] if sens > 0 else b[2]
        if (ex - best) * sens > 0:
            best = ex
        avance = (best - entree) * sens
        # Le trailing ne s arme pas avant que son PREMIER niveau soit au
        # moins a l entree. Arme a 0.50R avec une distance de 1.50R, il
        # posait son stop a -1.00R : ce n est pas une protection, c est
        # une perte inventee que le trade n a jamais subie. Ce defaut
        # expliquait a lui seul que toutes les colonnes de trailing
        # perdent, le 27/08.
        seuil_arme = arme if arme is None else max(arme, trail or 0.0)
        if not arme_ok and seuil_arme is not None \
                and avance >= seuil_arme * r_pts:
            arme_ok = True

        niveau = None
        if be is not None and avance >= be * r_pts:
            niveau = entree
        if trail is not None and arme_ok:
            t = best - sens * trail * r_pts
            # Ceinture : meme arme au bon moment, un stop ne descend
            # jamais sous l entree.
            if (t - entree) * sens < 0:
                t = entree
            if niveau is None or (t - niveau) * sens > 0:
                niveau = t
        if niveau is not None:
            attente = niveau
    return None


def mfe_des_barres(bars, sens, entree):
    if not bars:
        return 0.0
    ex = max(b[1] for b in bars) if sens > 0 else min(b[2] for b in bars)
    return max(0.0, (ex - entree) * sens)


# ----------------------------------------------------------------------
def politiques():
    P = [("reel", None, None, None)]
    for x in BE_SEUILS:
        P.append(("BE %.2fR" % x, x, None, None))
    for d in TR_DIST:
        P.append(("TR %.2fR" % d, None, d, TR_ARME))
    for x, d in COMBOS:
        P.append(("BE%.1f+TR%.1f" % (x, d), x, d, TR_ARME))
    return P


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--journal", default=JOURNAL)
    ap.add_argument("--terminal", default=TERMINAL_MOTEUR)
    ap.add_argument("--jours", type=int, default=35)
    ap.add_argument("--limite", type=int, default=0,
                    help="n arrete apres N tickets rejoues (essai rapide)")
    ap.add_argument("--cache", default=CACHE)
    ap.add_argument("--min-n", type=int, default=50, dest="min_n")
    a = ap.parse_args()

    L = []

    def dire(msg):
        print(msg, flush=True)
        L.append(msg)

    dire(barre())
    dire("REJEU DES SORTIES -- BREAK-EVEN ET TRAILING, BARRE PAR BARRE")
    dire(barre())

    journal, ko = lire_jsonl(a.journal)
    if not journal:
        print("ABANDON : %s vide ou absent." % a.journal)
        return 2
    noms, souci = noms_des_papers()
    if souci:
        dire("  noms des papers : indisponibles (%s), magics seuls." % souci)

    if not os.path.exists(a.terminal):
        print("ABANDON : terminal introuvable --")
        print("  %s" % a.terminal)
        print("Je ne me rabats PAS sur le terminal par defaut : c est")
        print("l autre compte, et la mesure serait fausse sans le dire.")
        return 2

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("ABANDON : MetaTrader5 non installe.")
        return 2
    if not mt5.initialize(path=a.terminal):
        print("ABANDON : initialize a echoue -- %s" % (mt5.last_error(),))
        return 2

    info = mt5.account_info()
    s = str(info.login) if info else "?"
    dire("  compte : %s   %s" % (s[:2] + "**" + s[-2:], info.server if info else "?"))
    dire("  source : %s   (%d prise(s), %d magic(s))"
         % (a.journal, len(journal), len(set(x.get("magic") for x in journal))))

    t1 = time.time()
    t0 = t1 - 86400.0 * a.jours
    par_pos = deals_fenetre(mt5, t0, t1, dire)

    # --- R par magic, et la table magic -> prises
    par_magic = {}
    for x in journal:
        par_magic.setdefault(x.get("magic"), []).append(x)
    R_eur = {}
    for m, pp in par_magic.items():
        pertes = [-p["pnl"] for p in pp if (p.get("pnl") or 0.0) < 0]
        R_eur[m] = (sum(pertes) / len(pertes)) if pertes else None

    # --- les tickets dont on a besoin
    besoin = {}
    for x in journal:
        tk = x.get("ticket")
        if tk is not None:
            besoin.setdefault(int(tk), []).append(x)
    dire("  tickets cites par le journal : %d" % len(besoin))

    # --- barres, une fois par symbole
    symboles = set()
    for tk in besoin:
        d = par_pos.get(tk)
        if d:
            r = resume_position(mt5, d)
            if r:
                symboles.add(r[6])
    dire("")
    dire("  symboles : %s" % (", ".join(sorted(symboles)) or "aucun"))
    cache_b, cache_t = {}, {}
    for sym in sorted(symboles):
        b = charge_barres(mt5, sym, t0, t1, a.cache, dire)
        cache_b[sym] = b
        cache_t[sym] = [x[0] for x in b]

    # --- rejeu, une fois par ticket
    P = politiques()
    res = {}        # magic -> nom politique -> delta EUR cumule
    detail = []     # (magic, pnl reel, {politique: delta}) par prise
    for m in par_magic:
        res[m] = dict((p[0], 0.0) for p in P)

    n_ok = n_sans_deal = n_sans_barre = n_sans_eurpt = n_sans_R = 0
    n_absent = n_incomplet = 0
    ts_absents, ts_trouves = [], []
    n_vus = 0
    vus_n, vus_pnl = {}, {}     # ce qui a REELLEMENT ete rejoue
    mfe_ratio = []
    sens_buy = sens_sell = 0
    for tk, prises in besoin.items():
        n_vus += 1
        d = par_pos.get(tk)
        if not d:
            # Le ticket n existe pas du tout dans l historique lu.
            n_absent += 1
            n_sans_deal += 1
            ts_absents.append(str(prises[0].get("ts") or ""))
            continue
        r = resume_position(mt5, d)
        if not r:
            # Il existe, mais sans entree ou sans sortie : position
            # encore ouverte, ou deals hors de la fenetre lue.
            n_incomplet += 1
            n_sans_deal += 1
            continue
        ts_trouves.append(str(prises[0].get("ts") or ""))
        sens, entree, sortie, profit, t_ouv, t_fer, sym = r
        amp = (sortie - entree) * sens
        if abs(amp) < 1e-9:
            n_sans_eurpt += 1
            continue
        eur_pt = profit / amp
        if abs(eur_pt) < 1e-12:
            n_sans_eurpt += 1
            continue
        bars = tranche(cache_b.get(sym, []), cache_t.get(sym, []), t_ouv, t_fer)
        if not bars:
            n_sans_barre += 1
            continue
        n_ok += 1
        if a.limite and n_ok > a.limite:
            n_ok -= 1
            break
        if sens > 0:
            sens_buy += 1
        else:
            sens_sell += 1

        # Controle croise du MFE, EN POINTS. Le comparer en euros
        # revenait a confronter deux echelles de lot : les barres
        # donnent un prix, le journal porte deja le lot du paper.
        # C etait mon erreur du 27/08, et elle faisait echouer le
        # controle sur une difference qui n existait pas.
        mb_pts = mfe_des_barres(bars, sens, entree)

        for p in prises:
            m = p.get("magic")
            Re = R_eur.get(m)
            # f = le rapport du lot du paper a celui du ticket reel. Il
            # est POSITIF par construction ; s il ne l est pas, les deux
            # PnL ne parlent pas du meme trade et on ne devine pas.
            f = (p["pnl"] / profit) if abs(profit) > 1e-9 else None
            if not Re or f is None or f <= 0:
                n_sans_R += 1
                continue
            ep = f * eur_pt                 # euros par point, cote paper
            if abs(ep) < 1e-12:
                n_sans_R += 1
                continue
            r_pts = Re / abs(ep)
            mj_pts = abs(p.get("mfe") or 0.0) / abs(ep)
            if mj_pts > 1e-9 and mb_pts > 1e-9:
                mfe_ratio.append(mb_pts / mj_pts)
            vus_n[m] = vus_n.get(m, 0) + 1
            vus_pnl[m] = vus_pnl.get(m, 0.0) + p["pnl"]
            dd = {}
            for nom, be, trail, arme in P:
                if be is None and trail is None:
                    continue
                px = rejoue(bars, sens, entree, r_pts, be, trail, arme)
                if px is None:
                    continue                # la politique ne fait rien
                d = (px - entree) * sens * ep - p["pnl"]
                res[m][nom] += d
                dd[nom] = d
            detail.append((m, p["pnl"], dd))

    mt5.shutdown()

    # ---------------- controles
    dire("")
    dire(barre("-"))
    dire("LES CONTROLES -- a lire AVANT les resultats")
    dire(barre("-"))
    dire("  tickets rejoues        : %d" % n_ok)
    dire("  sans deal retrouve     : %d" % n_sans_deal)
    dire("     absent de l historique : %d" % n_absent)
    dire("     deals incomplets       : %d" % n_incomplet)
    # D ou vient le manque ? Deux causes possibles, deux signatures
    # differentes -- on les separe au lieu de choisir.
    croise = len(set(besoin) & set(par_pos))
    dire("     tickets du journal presents dans l historique : %d / %d"
         % (croise, len(besoin)))
    if ts_absents:
        ts_absents.sort()
        dire("     absents, du %s au %s"
             % (ts_absents[0][:16] or "?", ts_absents[-1][:16] or "?"))
    if ts_trouves:
        ts_trouves.sort()
        dire("     trouves, du %s au %s"
             % (ts_trouves[0][:16] or "?", ts_trouves[-1][:16] or "?"))
    dire("     Si les absents couvrent la MEME plage que les trouves, ce")
    dire("     n est pas une fenetre trop courte : c est que le ticket du")
    dire("     journal n est pas le position_id de MT5. Si au contraire")
    dire("     ils se massent a un bout, il faut elargir --jours.")
    dire("  sans barre M1          : %d" % n_sans_barre)
    dire("  conversion impossible  : %d" % n_sans_eurpt)
    dire("  prise sans R ou sans f : %d" % n_sans_R)
    perdus = n_sans_deal + n_sans_barre + n_sans_eurpt
    # Le denominateur est ce qu on a EXAMINE, pas ce que le journal
    # cite : en mode essai la boucle s arrete avant la fin, et
    # rapporter la perte sur la population entiere la ferait paraitre
    # dix fois plus petite qu elle n est.
    part = 100.0 * perdus / max(1, n_vus)
    dire("  population perdue      : %d / %d examine(s)  (%.1f %%)"
         % (perdus, n_vus, part))
    if a.limite:
        dire("")
        dire("  !! MODE ESSAI : --limite %d. %d ticket(s) examines sur"
             % (a.limite, n_vus))
        dire("     %d cites par le journal. Les totaux ci-dessous ne sont"
             % len(besoin))
        dire("     PAS ceux du mois. Relancer sans --limite pour conclure.")
    if part > 25.0:
        dire("")
        dire("  !! PLUS D UN QUART DE LA POPULATION MANQUE. Les ecarts")
        dire("     ci-dessous portent sur ce qui reste, pas sur le mois.")
        dire("     Ne pas les comparer aux totaux des autres panneaux.")
    if mfe_ratio:
        mfe_ratio.sort()
        med = mfe_ratio[len(mfe_ratio) // 2]
        dire("  MFE barres / journal   : mediane %.2f sur %d ticket(s)"
             % (med, len(mfe_ratio)))
        if med < 0.8 or med > 1.25:
            dire("     ECART : les barres et le journal ne mesurent pas la")
            dire("     meme chose. Tout ce qui suit est a suspecter.")
    dire("  sens                   : %d achat(s), %d vente(s)"
         % (sens_buy, sens_sell))
    dire("     Les M1 sont construites sur le BID : un stop d ACHAT")
    dire("     declenche sur le bas de barre est exact, un stop de VENTE")
    dire("     sur le haut de barre est optimiste d un spread.")

    # ---------------- resultats
    # On affiche l effectif et le PnL des prises REJOUEES, pas ceux du
    # journal entier : comparer un ecart partiel a une reference
    # complete donnerait un rapport faux sans en avoir l air.
    lignes = [(m, vus_n[m], vus_pnl[m]) for m in vus_n
              if vus_n[m] >= a.min_n]
    lignes.sort(key=lambda t: -t[1])

    def table(titre, choix):
        dire("")
        dire(barre())
        dire(titre)
        dire(barre())
        e = "%-7s %-22s %6s %9s" % ("MAGIC", "PAPER", "n rej", "PnL rej")
        for nom in choix:
            e += " %9s" % nom
        dire(e)
        dire(barre("-"))
        tot = dict((n, 0.0) for n in choix)
        for m, nn, reel in lignes:
            ln = "%-7s %-22s %6d %+9.0f" % (m, (noms.get(m) or "")[:22],
                                            nn, reel)
            for nom in choix:
                v = res[m][nom]
                tot[nom] += v
                ln += " %+9.0f" % v
            dire(ln)
        dire(barre("-"))
        ln = "%-7s %-22s %6d %+9.0f" % ("", "TOTAL affiches",
                                        sum(t[1] for t in lignes),
                                        sum(t[2] for t in lignes))
        for nom in choix:
            ln += " %+9.0f" % tot[nom]
        dire(ln)
        # Le tableau de la queue porte sur TOUTES les prises rejouees,
        # celui-ci sur les seuls magics affiches. Deux totaux de portees
        # differentes sur la meme page se comparent tout seuls, et a
        # tort : on affiche donc les deux.
        ln = "%-7s %-22s %6d %+9.0f" % ("", "TOUS MAGICS",
                                        sum(vus_n.values()),
                                        sum(vus_pnl.values()))
        for nom in choix:
            ln += " %+9.0f" % sum(res[m][nom] for m in vus_n)
        dire(ln)
        dire(barre("-"))
        dire("  n rej / PnL rej : effectif et PnL des prises REJOUEES.")
        dire("  L ecart se compare a cette colonne-la, pas au mois entier.")
        dire("  Le stop ne recule jamais : c est le cliquet.")

    table("BREAK-EVEN SEUL -- le stop passe a l entree a +x.R",
          [p[0] for p in P if p[1] is not None and p[2] is None])
    table("TRAILING SEUL -- arme au plus tard a +d.R, suit a d.R sous le pic",
          [p[0] for p in P if p[1] is None and p[2] is not None])
    table("LES DEUX ENSEMBLE -- le plus protecteur des deux l emporte",
          [p[0] for p in P if p[1] is not None and p[2] is not None])

    # ---------------- la queue, la question laissee par tp_fixe
    gag = sorted([d for d in detail if d[1] > 0], key=lambda x: -x[1])
    if gag:
        k = max(1, len(gag) // 20)
        tete = gag[:k]
        somme = sum(d[1] for d in tete)
        total_g = sum(d[1] for d in gag)
        dire("")
        dire(barre())
        dire("LA QUEUE -- ce que chaque politique fait aux 5 % du haut")
        dire(barre())
        dire("  tp_fixe.py a montre qu un plafond detruit plus qu il ne")
        dire("  rapporte : la queue porte le resultat. Un trailing SUIT au")
        dire("  lieu de plafonner -- mais il peut la couper quand meme.")
        dire("  C est la seule chose que ce tableau mesure.")
        dire("")
        dire("  %d gagnant(s) de tete sur %d, soit %+.0f EUR"
             % (k, len(gag), somme))
        dire("  (%.0f %% du gain brut des gagnants)"
             % (100.0 * somme / total_g if total_g else 0.0))
        dire("")
        dire(barre("-"))
        dire("%-16s %12s %12s %12s" % ("POLITIQUE", "sur la queue",
                                       "sur le reste", "total"))
        dire(barre("-"))
        for nom, be, trail, arme in P:
            if be is None and trail is None:
                continue
            dq = sum(d[2].get(nom, 0.0) for d in tete)
            dt_ = sum(v.get(nom, 0.0) for _, _, v in detail)
            dire("%-16s %+12.0f %+12.0f %+12.0f"
                 % (nom, dq, dt_ - dq, dt_))
        dire(barre("-"))
        dire("  Une politique qui gagne sur le reste et perd lourdement")
        dire("  sur la queue reproduit le defaut du take-profit fixe,")
        dire("  sous un autre nom.")

    dire("")
    dire(barre())
    dire("CE QUE CE PANNEAU NE DIT PAS")
    dire(barre())
    dire("  Il ne modelise pas le stop d origine : la sortie reelle l")
    dire("  embarque deja. Une politique qui ne declenche pas laisse le")
    dire("  trade finir ou il a fini.")
    dire("")
    dire("  Il ne modelise pas la place liberee : un trade ferme plus")
    dire("  tot aurait peut-etre laisse le moteur en prendre un autre.")
    dire("")
    dire("  Le prix de sortie est le NIVEAU du stop. En reel, un stop")
    dire("  saute pendant un choc ; la mesure est donc optimiste sur")
    dire("  les barres violentes, dans les deux sens.")
    dire("")
    dire("  R vient des pertes REALISEES sous les stops-placeholder.")
    dire("  Si les sorties changent, R change et la grille est a relire.")

    txt = "\n".join(L)
    for d2 in ("panels", "cartes"):
        if not os.path.isdir(d2):
            os.makedirs(d2)
    io.open(SORTIE_T, "w", encoding="utf-8", newline="").write(txt + "\n")
    h = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    io.open(SORTIE_H, "w", encoding="utf-8", newline="").write(
        '<!doctype html><html><head><meta charset="utf-8">'
        '<title>Rejeu des sorties</title></head>'
        '<body style="margin:0;background:#0e1116">'
        '<pre style="font:12px Consolas,monospace;color:#c9d1d9;'
        'background:#0e1116;padding:16px 20px;margin:0;'
        'white-space:pre">' + h + '</pre></body></html>\n')
    print("")
    print("  ecrit : %s" % SORTIE_T)
    print("  ecrit : %s   (liste /cartes)" % SORTIE_H)
    return 0


if __name__ == "__main__":
    sys.exit(main())
