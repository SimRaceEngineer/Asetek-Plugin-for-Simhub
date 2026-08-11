# -*- coding: utf-8 -*-
"""
amplitude_pnl.py -- l amplitude ordonne-t-elle le resultat ? sur toute l histoire

  python amplitude_pnl.py

CE QU ON CHERCHE
    Le 11/08, sur seize seances, une seule variable ordonnait les trois
    periodes sans exception :

        amplitude US500 >= 130  ->  +10,40 EUR/trade   (4 seances)
        amplitude 80 a 130      ->   -0,14             (4)
        amplitude < 80          ->   -5,47             (8)

    Seize seances ne suffisent pas. La base magic_daily_stats couvre le
    26/05 au 11/08 -- une cinquantaine de seances de bourse -- et permet de
    reposer la question sur un echantillon qui compte.

    Ce n est PAS une decouverte nouvelle : c est l hypothese de
    h1_seance.py, que le gel V7 oppose a celle de volatilite.py ("les
    periodes calmes sont les plus rentables"). Les deux ne peuvent pas etre
    vraies. Ce script apporte des seances, pas une idee.

DEUX LECTURES, ET IL FAUT LES TENIR SEPAREES
    A. L amplitude DU JOUR MEME. Descriptive. Elle dit si le resultat suit
       le mouvement, mais on ne connait l amplitude d une seance qu une
       fois close : on ne peut rien en faire.

    B. L amplitude des N seances PRECEDENTES. Causale. C est la seule qui
       pourrait devenir une regle, et c est deja la forme de regime_ampl
       au gel V7.

    Si A est fort et B est nul, il n y a rien a trader : le dispositif
    profite du mouvement du jour sans qu on puisse le prevoir. C est le
    resultat le plus probable, et le dire tot evite de fabriquer une regle
    sur un effet qui n en est pas une.

VERIFICATION CROISEE
    Le script compare, sur les quinze dernieres seances, le P&L de la base
    avec celui de l historique MT5. Deux sources qui divergent, c est une
    des deux qui ment, et on ne saurait pas laquelle. Si l ecart depasse
    quelques pour cent, tout le reste est suspendu.

NORMALISATION
    Une amplitude de 500 points ne veut pas dire la meme chose sur US30 et
    sur US500. Chaque actif est donc ramene a SA propre mediane sur toute
    la periode, et les trois sont moyennes. Le composite vaut 1 pour une
    seance ordinaire.
"""
import argparse
import datetime as dt
import os
import sqlite3
import sys

try:
    import MetaTrader5 as mt5
except ImportError:
    print("MetaTrader5 introuvable. Lance ce script sur le VPS.")
    sys.exit(1)

BASE = os.path.join("docs", "magic_stats", "history.sqlite")
ACTIFS = {
    "US30": ["US30", "US30.cash", "us30.cash", "DJ30", "WS30"],
    "US500": ["SPX500", "SPX500.cash", "spx500.cash", "US500", "SP500"],
    "US100": ["NAS100", "NAS100.cash", "nas100.cash", "US100", "NDX100"],
}
FAMILLES = ("206", "207", "208")
N_PREC = 3          # seances precedentes pour la lecture causale


def _jour(ts):
    """Horodatage MT5 -> 'AAAA-MM-JJ'. Conscient du fuseau : utcfromtimestamp
    est deprecie en 3.14 et crachait deux avertissements a chaque lancement."""
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()


def mediane(v):
    s = sorted(v)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def lire_base(chemin):
    """{jour: {pnl,trades,wins}} et {jour: {famille: {pnl,trades,wins}}}."""
    if not os.path.isfile(chemin):
        print("KO : %s introuvable." % chemin)
        sys.exit(1)
    c = sqlite3.connect(chemin)
    tot, fam = {}, {}
    for d, m, p, t, w in c.execute(
            "select date, magic, pnl, trades, wins from magic_daily_stats"):
        e = tot.setdefault(d, {"pnl": 0.0, "trades": 0, "wins": 0})
        e["pnl"] += p or 0.0
        e["trades"] += t or 0
        e["wins"] += w or 0
        f = str(m)[:3]
        g = fam.setdefault(d, {}).setdefault(f, {"pnl": 0.0, "trades": 0, "wins": 0})
        g["pnl"] += p or 0.0
        g["trades"] += t or 0
        g["wins"] += w or 0
    c.close()
    return tot, fam


def amplitudes(depuis, jusqu):
    """{jour: composite}. 1 = seance ordinaire pour les trois actifs."""
    brut = {}
    for actif, noms in ACTIFS.items():
        sym = next((n for n in noms if mt5.symbol_info(n) is not None), None)
        if not sym:
            continue
        r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, depuis, jusqu)
        if r is None or not len(r):
            continue
        par = {}
        for b in r:
            j = _jour(int(b["time"]))
            e = par.setdefault(j, [-1e18, 1e18])
            e[0] = max(e[0], float(b["high"]))
            e[1] = min(e[1], float(b["low"]))
        med = mediane([h - l for h, l in par.values()])
        if not med:
            continue
        for j, (h, l) in par.items():
            brut.setdefault(j, []).append((h - l) / med)
    return dict((j, sum(v) / len(v)) for j, v in brut.items() if v)


def bloc(lab, lignes):
    """lignes = [(etiquette, pnl, trades, wins, n_seances)]"""
    print()
    print("=" * 84)
    print("  " + lab)
    print("=" * 84)
    print("%-26s %8s %8s %11s %6s" % ("tranche", "seances", "trades",
                                      "EUR/trade", "WR"))
    print("-" * 84)
    for et, p, t, w, ns in lignes:
        print("%-26s %8d %8d %11.2f %5.0f%%"
              % (et, ns, t, p / t if t else 0.0, 100.0 * w / t if t else 0))
    print("-" * 84)


def tranches(jours, amp, tot, fam=None, cle=None):
    """Repartit les seances en trois tiers d amplitude et agrege."""
    ok = [j for j in jours if j in amp and j in tot]
    if len(ok) < 9:
        return []
    tri = sorted(ok, key=lambda j: amp[j])
    t = len(tri) // 3
    groupes = (("calme  (tiers bas)", tri[:t]),
               ("moyen  (tiers milieu)", tri[t:len(tri) - t]),
               ("agite  (tiers haut)", tri[len(tri) - t:]))
    out = []
    for et, sel in groupes:
        p, tr, w = 0.0, 0, 0
        for j in sel:
            src = (fam or tot)[j]
            if fam is not None:
                src = src.get(cle)
                if not src:
                    continue
            p += src["pnl"]
            tr += src["trades"]
            w += src["wins"]
        a = [amp[j] for j in sel]
        out.append(("%s  %.2f-%.2f" % (et, min(a), max(a)), p, tr, w, len(sel)))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default=BASE)
    a = p.parse_args()

    if not mt5.initialize():
        print("mt5.initialize() a echoue : %s" % (mt5.last_error(),))
        return 1

    tot, fam = lire_base(a.base)
    js = sorted(tot)
    print("=== SCALP-EA / AMPLITUDE ET RESULTAT ===")
    print("base : %s -> %s, %d seances" % (js[0], js[-1], len(js)))

    d0 = dt.datetime.strptime(js[0], "%Y-%m-%d") - dt.timedelta(days=5)
    d1 = dt.datetime.now() + dt.timedelta(days=1)
    amp = amplitudes(d0, d1)
    print("barres  : %d seances avec amplitude" % len(amp))

    # ------------------------------------------------ verification croisee
    print()
    print("VERIFICATION CROISEE base / historique MT5, quinze dernieres seances")
    d = mt5.history_deals_get(dt.datetime.now() - dt.timedelta(days=25), d1)
    mt5_j = {}
    for x in (d or []):
        try:
            if x.entry != mt5.DEAL_ENTRY_OUT:
                continue
        except AttributeError:
            continue
        k = _jour(int(x.time))
        mt5_j[k] = mt5_j.get(k, 0.0) + float(x.profit) + float(x.swap) + float(x.commission)
    comm = [j for j in js if j in mt5_j][-15:]
    if not comm:
        print("  aucune seance commune -- verification impossible")
    else:
        print("  %-12s %12s %12s %10s" % ("jour", "base", "MT5", "ecart"))
        pires = 0.0
        for j in comm:
            b, m = tot[j]["pnl"], mt5_j[j]
            e = abs(b - m) / max(1.0, abs(m))
            pires = max(pires, e)
            print("  %-12s %12.2f %12.2f %9.1f%%" % (j, b, m, 100.0 * e))
        print()
        if pires > 0.05:
            print("  *** ECART SUPERIEUR A 5%% -- LES DEUX SOURCES DIVERGENT ***")
            print("  On ne saurait pas laquelle croire. Tout ce qui suit est")
            print("  suspendu tant que ce n est pas explique.")
        else:
            print("  Ecart maximum %.1f%% : les deux sources concordent." % (100.0 * pires))

    # ------------------------------------------------------ lecture A
    bloc("A. AMPLITUDE DU JOUR MEME -- descriptive, non exploitable",
         tranches(js, amp, tot))
    print("On ne connait l amplitude d une seance qu une fois close. Cette")
    print("lecture dit si le resultat suit le mouvement, pas ce qu on peut en")
    print("faire.")

    # ------------------------------------------------------ lecture B
    ampc = {}
    tri = sorted(amp)
    for i, j in enumerate(tri):
        if i >= N_PREC:
            prec = [amp[tri[k]] for k in range(i - N_PREC, i)]
            ampc[j] = sum(prec) / len(prec)
    bloc("B. AMPLITUDE DES %d SEANCES PRECEDENTES -- causale, gelable" % N_PREC,
         tranches(js, ampc, tot))
    print("Jour courant exclu, aucun jour futur. C est la seule des deux qui")
    print("puisse devenir une regle. Si elle est plate alors que A est forte,")
    print("il n y a rien a trader : le dispositif profite du mouvement du jour")
    print("sans qu on puisse le prevoir.")

    # ------------------------------------------------------ par famille
    for f in FAMILLES:
        lg = tranches(js, amp, tot, fam, f)
        if lg and sum(x[2] for x in lg) > 200:
            bloc("M%s -- amplitude du jour meme" % f, lg)

    print()
    print("RESERVES")
    print("  Unite = la seance, pas le ticket : les trades d une meme journee")
    print("  sont correles, et compter en tickets gonflerait la confiance.")
    print("  Les tiers sont decoupes sur l echantillon complet, donc en")
    print("  connaissant l avenir. Pour un gel il faudra un seuil glissant,")
    print("  comme regime_ampl au gel V7.")
    print("  Enfin la base agrege par jour COURTIER et les barres par jour")
    print("  UTC-serveur : un decalage d une seance est possible aux bornes.")
    mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
