# -*- coding: utf-8 -*-
"""
amplitude_familles.py -- la lecture causale, par famille, sur une seule source

  python amplitude_familles.py
  python amplitude_familles.py --depuis 2026-05-26

CE QUI MANQUAIT
    amplitude_pnl.py a montre, le 11/08, que l amplitude ordonne le
    resultat -- et que l ordre survit a la lecture causale :

        3 seances precedentes calmes  ->  -3,28 EUR/trade, WR 44%
        moyennes                      ->  -2,13            45%
        agitees                       ->  -0,38            52%

    Il a aussi montre, mais seulement en lecture DU JOUR MEME, que les
    jumeaux changent de SIGNE :

        M206  -8,18 / -4,02 / +16,00      M207  -7,06 / -2,15 / +11,68

    L amplitude du jour meme ne se connait qu une fois la seance close :
    invendable. La question qui reste est donc la seule qui vaille, et
    personne ne l a encore posee : le changement de signe survit-il quand
    on ne regarde QUE les seances precedentes ?

    Ce script pose cette question-la. Il n en pose pas d autre.

POURQUOI M206 ET M207 SONT LE BON TERRAIN
    Fin juillet la flotte a ete taillee : M186, M178, M354, M187, M201,
    M205, M203 et une quinzaine d autres sont a l arret. Comparer "avant"
    et "depuis" melange donc un changement de regime et un changement de
    dispositif, et on ne peut pas les separer.

    M206 et M207 tradent sur TOUTE la fenetre. Pour eux, et pour eux
    seuls, le confondant tombe.

UNE SEULE SOURCE
    Tout vient de l historique MT5, y compris la ventilation par magic.
    amplitude_pnl.py croisait magic_daily_stats et MT5 ; le 11/08 les deux
    divergeaient sur une seance -- la base avait range les 9 tickets du
    28/07 sous le 29/07, 3760,48 EUR deplaces d un jour. Le total des deux
    jours concordait, donc rien n etait faux, mais il a fallu le
    demontrer. Lire une seule source supprime la question.

N_PREC EST FIXE A 3, ET IL NE BOUGERA PAS
    C est la valeur deja retenue par amplitude_pnl.py avant de connaitre
    le resultat. Essayer 2, 3, 5, 10 et garder le meilleur fabriquerait un
    seuil qui ne survivrait pas a septembre. Si 3 ne montre rien, la
    reponse est "rien", pas "essayons 4".
"""
import argparse
import datetime as dt
import sys

try:
    import MetaTrader5 as mt5
except ImportError:
    print("MetaTrader5 introuvable. Lance ce script sur le VPS.")
    sys.exit(1)

ACTIFS = {
    "US30": ["US30", "US30.cash", "us30.cash", "DJ30", "WS30"],
    "US500": ["SPX500", "SPX500.cash", "spx500.cash", "US500", "SP500"],
    "US100": ["NAS100", "NAS100.cash", "nas100.cash", "US100", "NDX100"],
}
N_PREC = 3       # seances precedentes. Fixe. Voir l en-tete.
MINI = 300       # trades minimum pour qu une famille soit affichee


def _jour(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()


def mediane(v):
    s = sorted(v)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def lire_deals(depuis, jusqu):
    """({jour: [pnl,trades,wins]}, {famille: {jour: [pnl,trades,wins]}})"""
    d = mt5.history_deals_get(depuis, jusqu)
    if d is None:
        print("history_deals_get a renvoye None : %s" % (mt5.last_error(),))
        sys.exit(1)
    tot, fam = {}, {}
    for x in d:
        try:
            if x.entry != mt5.DEAL_ENTRY_OUT:
                continue
        except AttributeError:
            continue
        j = _jour(int(x.time))
        net = float(x.profit) + float(x.swap) + float(x.commission)
        m = int(x.magic or 0)
        f = ("M%s" % str(m)[:3]) if m else "M-"
        for c in (tot.setdefault(j, [0.0, 0, 0]),
                  fam.setdefault(f, {}).setdefault(j, [0.0, 0, 0])):
            c[0] += net
            c[1] += 1
            c[2] += 1 if net > 0 else 0
    return tot, fam


def amplitudes(depuis, jusqu):
    """{jour: composite}. 1 = seance ordinaire pour les trois actifs.

    Chaque actif est ramene a SA mediane avant moyenne : 500 points ne
    veulent pas dire la meme chose sur US30 et sur US500.
    """
    brut = {}
    for _, noms in ACTIFS.items():
        sym = next((n for n in noms if mt5.symbol_info(n) is not None), None)
        if not sym:
            continue
        r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, depuis, jusqu)
        if r is None or not len(r):
            continue
        par = {}
        for b in r:
            e = par.setdefault(_jour(int(b["time"])), [-1e18, 1e18])
            e[0] = max(e[0], float(b["high"]))
            e[1] = min(e[1], float(b["low"]))
        med = mediane([h - l for h, l in par.values()])
        if not med:
            continue
        for j, (h, l) in par.items():
            brut.setdefault(j, []).append((h - l) / med)
    return dict((j, sum(v) / len(v)) for j, v in brut.items() if v)


def causale(amp):
    """{jour: moyenne des N_PREC seances precedentes}. Jour courant exclu."""
    out, tri = {}, sorted(amp)
    for i, j in enumerate(tri):
        if i >= N_PREC:
            out[j] = sum(amp[tri[k]] for k in range(i - N_PREC, i)) / float(N_PREC)
    return out


def tranches(amp, src):
    ok = [j for j in src if j in amp and src[j][1] > 0]
    if len(ok) < 9:
        return []
    tri = sorted(ok, key=lambda j: amp[j])
    t = len(tri) // 3
    out = []
    for et, sel in (("calme", tri[:t]),
                    ("moyen", tri[t:len(tri) - t]),
                    ("agite", tri[len(tri) - t:])):
        a = [amp[j] for j in sel]
        out.append((et, min(a), max(a),
                    sum(src[j][0] for j in sel),
                    sum(src[j][1] for j in sel),
                    sum(src[j][2] for j in sel), len(sel)))
    return out


def bloc(lab, lignes):
    print()
    print("=" * 88)
    print("  " + lab)
    print("=" * 88)
    if not lignes:
        print("  moins de neuf seances exploitables -- rien a dire.")
        return
    print("%-22s %6s %7s %12s %10s %5s"
          % ("tranche", "seanc", "trades", "total EUR", "EUR/trade", "WR"))
    print("-" * 88)
    for et, lo, hi, p, n, w, ns in lignes:
        print("%-22s %6d %7d %12.2f %10.2f %4.0f%%"
              % ("%s  %.2f-%.2f" % (et, lo, hi), ns, n, p,
                 p / n if n else 0.0, 100.0 * w / n if n else 0))
    print("-" * 88)
    a, z = lignes[0], lignes[-1]
    if a[4] and z[4]:
        print("  ecart calme -> agite : %+.2f EUR/trade, %+.0f points de WR"
              % (z[3] / z[4] - a[3] / a[4],
                 100.0 * z[5] / z[4] - 100.0 * a[5] / a[4]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--depuis", default="2026-05-26")
    a = p.parse_args()

    if not mt5.initialize():
        print("mt5.initialize() a echoue : %s" % (mt5.last_error(),))
        return 1

    d0 = dt.datetime.strptime(a.depuis, "%Y-%m-%d")
    d1 = dt.datetime.now() + dt.timedelta(days=1)

    tot, fam = lire_deals(d0, d1)
    amp = amplitudes(d0 - dt.timedelta(days=10), d1)
    ampc = causale(amp)

    print("=== SCALP-EA / AMPLITUDE PAR FAMILLE, LECTURE CAUSALE ===")
    print("source unique : historique MT5, %s -> aujourd hui" % a.depuis)
    js = sorted(tot)
    print("%d seances tradees, %d avec amplitude, %d avec amplitude causale"
          % (len(js), len([j for j in js if j in amp]),
             len([j for j in js if j in ampc])))

    bloc("TOUTES FAMILLES -- amplitude des %d seances precedentes" % N_PREC,
         tranches(ampc, tot))

    ordre = sorted(fam, key=lambda f: -sum(c[1] for c in fam[f].values()))
    for f in ordre:
        n = sum(c[1] for c in fam[f].values())
        if n < MINI:
            continue
        bloc("%s -- amplitude DU JOUR MEME (descriptive, non exploitable)" % f,
             tranches(amp, fam[f]))
        bloc("%s -- amplitude des %d seances PRECEDENTES (causale, gelable)"
             % (f, N_PREC), tranches(ampc, fam[f]))

    # ------------------------------------------------------ ou en est-on
    seuils = tranches(ampc, tot)
    print()
    print("=" * 88)
    print("  OU EN EST-ON -- dix dernieres seances")
    print("=" * 88)
    print("%-12s %8s %8s %-10s %12s %7s"
          % ("jour", "ampl", "causale", "tiers", "PnL", "trades"))
    print("-" * 88)
    for j in sorted(amp)[-10:]:
        c = ampc.get(j)
        et = "-"
        if c is not None and seuils:
            et = "calme" if c <= seuils[0][2] else (
                "agite" if c >= seuils[2][1] else "moyen")
        e = tot.get(j, [0.0, 0, 0])
        print("%-12s %8.2f %8s %-10s %12.2f %7d"
              % (j, amp[j], "%.2f" % c if c is not None else "-", et,
                 e[0], e[1]))
    print("-" * 88)
    if seuils:
        print("  bornes du tiers calme : %.2f a %.2f  |  agite a partir de %.2f"
              % (seuils[0][1], seuils[0][2], seuils[2][1]))
        print("  Une valeur causale SOUS %.2f sort par le bas de l echantillon :"
              % seuils[0][1])
        print("  on ne saurait pas quoi en dire, on n a jamais trade la-dedans.")

    print()
    print("RESERVES")
    print("  Les tiers sont decoupes sur l echantillon complet, donc en")
    print("  connaissant l avenir. Pour un gel il faudra un seuil glissant,")
    print("  calcule sur les seules seances passees.")
    print("  L unite qui compte est la seance, pas le ticket : les trades")
    print("  d une meme journee sont correles, et la colonne EUR/trade")
    print("  presente donc une confiance flatteuse.")
    print("  La colonne WR est le garde-fou : elle ne peut pas etre portee")
    print("  par trois gros tickets, contrairement au EUR/trade.")
    print("  Enfin les jours sont decoupes en UTC-serveur, cote barres comme")
    print("  cote deals : coherent avec lui-meme, decale d une heure ou deux")
    print("  par rapport au jour courtier.")
    mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
