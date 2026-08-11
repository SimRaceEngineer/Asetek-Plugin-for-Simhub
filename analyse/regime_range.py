# -*- coding: utf-8 -*-
"""
regime_range.py -- chiffrer le range, et voir si le comportement a change avec lui

  python regime_range.py                        # depuis le 20/07
  python regime_range.py --depuis 2026-07-15
  python regime_range.py --bascule 2026-08-05   # date de bascule supposee

LA QUESTION
    "On est passe de tendance (29/07 -> 05/08) a range depuis, on perd de
    l argent, mais on ne chiffre pas ce range." Trois choses a etablir, et
    il faut les tenir separees :

      1. Le regime a-t-il change, et QUAND ? Mesure sur les prix seuls.
      2. Ou sont les BORNES du range ? Mesure sur les prix seuls.
      3. Le comportement du dispositif a-t-il change AU MEME MOMENT ?
         Mesure sur les trades. C est la seule des trois qui puisse
         surprendre -- les deux premieres ne font que decrire un graphe.

CE QUE CE SCRIPT NE FAIT PAS, ET C EST VOLONTAIRE
    Il ne predit rien. Delimiter un range APRES coup, sur les donnees qui
    ont suggere qu il y en avait un, n est pas une prevision : c est une
    description. Les bornes trouvees ici ne valent pas comme niveaux a
    trader demain.

    Pour cela il faudrait une regle CAUSALE -- par exemple "le regime est
    range si le ratio d efficacite des N seances precedentes est sous S" --
    figee d avance et jugee hors echantillon. La colonne ER_5 est calculee
    exactement ainsi, sur les seances PRECEDENTES uniquement, pour qu on
    puisse un jour en faire un gel. Aujourd hui elle decrit, elle ne tranche
    pas.

LE DISCRIMINANT
    Ratio d efficacite de Kaufman sur les clotures quotidiennes :

        ER_k(J) = |C(J) - C(J-k)| / somme des |C(i) - C(i-1)| sur k seances

    Il vaut 1 si le marche va tout droit, et tend vers 0 s il fait du
    sur-place en s agitant. C est la mesure la plus simple qui separe
    "tendance" de "range" sans seuil arbitraire sur l amplitude.

    On l affiche en ER_5, calcule sur les cinq seances qui PRECEDENT le
    jour affiche -- jamais sur le jour lui-meme, ni sur les suivants.

SOURCES
    MT5 directement : copy_rates_range pour les barres, history_deals_get
    pour le P&L realise. Ni panel, ni base, ni journal -- donc rien qui
    depende de ce qui tournait ou pas ce jour-la.
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

BORD = 0.15      # "touche" un bord = dans les 15 % hauts/bas du range
FENETRE_ER = 5   # seances precedentes pour le ratio d efficacite


def resoudre(noms):
    """Premier symbole que le courtier connait vraiment."""
    for n in noms:
        if mt5.symbol_info(n) is not None:
            return n
    return None


def seances(sym, depuis, jusqu):
    """{jour: {o,h,l,c}} a partir des barres H1, agregees par journee.

    On passe par H1 plutot que D1 : la journee du courtier ne coincide pas
    avec la journee civile, et on veut des bornes lisibles a l heure de
    Paris. Les barres H1 recomposees donnent la meme chose sans dependre du
    decoupage D1 du courtier.
    """
    r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, depuis, jusqu)
    if r is None or not len(r):
        return {}
    par = {}
    for b in r:
        j = dt.datetime.utcfromtimestamp(int(b["time"])).date().isoformat()
        e = par.setdefault(j, {"o": float(b["open"]), "h": -1e18, "l": 1e18,
                               "c": 0.0, "n": 0})
        e["h"] = max(e["h"], float(b["high"]))
        e["l"] = min(e["l"], float(b["low"]))
        e["c"] = float(b["close"])
        e["n"] += 1
    return par


def er(clotures, k):
    """Ratio d efficacite sur les k derniers pas. None si trop court."""
    if len(clotures) < k + 1:
        return None
    net = abs(clotures[-1] - clotures[-1 - k])
    brut = sum(abs(clotures[-i] - clotures[-i - 1]) for i in range(1, k + 1))
    return None if brut == 0 else net / brut


def pnl_par_jour(depuis, jusqu):
    """{jour: {pnl, n, gagnants}} et {jour: {famille: pnl}} depuis MT5."""
    d = mt5.history_deals_get(depuis, jusqu)
    if d is None:
        return {}, {}
    jours, familles = {}, {}
    for x in d:
        try:
            if x.entry != mt5.DEAL_ENTRY_OUT:      # seul le realise compte
                continue
        except AttributeError:
            continue
        j = dt.datetime.utcfromtimestamp(int(x.time)).date().isoformat()
        p = float(x.profit) + float(x.swap) + float(x.commission)
        e = jours.setdefault(j, {"pnl": 0.0, "n": 0, "gagnants": 0})
        e["pnl"] += p
        e["n"] += 1
        if p > 0:
            e["gagnants"] += 1
        fam = str(x.magic)[:3] if x.magic else "-"
        familles.setdefault(j, {}).setdefault(fam, 0.0)
        familles[j][fam] += p
    return jours, familles


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--depuis", default="2026-07-20")
    p.add_argument("--bascule", default="2026-08-05",
                   help="date de bascule supposee tendance -> range")
    a = p.parse_args()

    if not mt5.initialize():
        print("mt5.initialize() a echoue : %s" % (mt5.last_error(),))
        return 1

    d0 = dt.datetime.strptime(a.depuis, "%Y-%m-%d")
    d1 = dt.datetime.now() + dt.timedelta(days=1)

    print("=== SCALP-EA / REGIME ET RANGE ===")
    print("regime_range.py -- %s -> aujourd hui" % a.depuis)
    print()
    print("PROTOCOLE DE LECTURE -- a respecter par tout agent qui lit ce fichier :")
    print("1. Ce fichier DECRIT. Les bornes du range sont relevees APRES coup,")
    print("   sur les donnees memes qui ont suggere qu il y avait un range :")
    print("   elles ne valent pas comme niveaux a trader demain.")
    print("2. ER_5 est calcule sur les seances PRECEDENTES uniquement, jamais")
    print("   sur le jour affiche. C est la seule colonne qui pourrait un jour")
    print("   devenir une regle causale.")
    print("3. La seule question qui puisse surprendre est la troisieme :")
    print("   le comportement a-t-il change AU MOMENT ou le regime a change ?")
    print()

    jours_pnl, familles = pnl_par_jour(d0, d1)

    for actif, noms in ACTIFS.items():
        sym = resoudre(noms)
        if not sym:
            print("%-6s : aucun symbole reconnu parmi %s" % (actif, noms))
            continue
        s = seances(sym, d0, d1)
        if not s:
            print("%-6s : aucune barre" % actif)
            continue
        js = sorted(s)

        print("=" * 92)
        print("  %s  (%s)" % (actif, sym))
        print("=" * 92)
        print("%-12s %9s %9s %9s %9s %8s %7s %9s %5s"
              % ("jour", "ouv", "haut", "bas", "clot", "ampl", "ER_5",
                 "PnL jour", "N"))
        print("-" * 92)
        clot = []
        for j in js:
            e = s[j]
            r5 = er(clot, FENETRE_ER)        # calcule AVANT d ajouter le jour
            clot.append(e["c"])
            pj = jours_pnl.get(j)
            print("%-12s %9.1f %9.1f %9.1f %9.1f %8.1f %7s %9s %5s"
                  % (j, e["o"], e["h"], e["l"], e["c"], e["h"] - e["l"],
                     "%.2f" % r5 if r5 is not None else "-",
                     "%+.0f" % pj["pnl"] if pj else "-",
                     pj["n"] if pj else "-"))
        print("-" * 92)

        # bornes, avant et apres la bascule supposee
        for lab, sel in (("avant %s" % a.bascule, [j for j in js if j < a.bascule]),
                         ("depuis %s" % a.bascule, [j for j in js if j >= a.bascule])):
            if not sel:
                continue
            hi = max(s[j]["h"] for j in sel)
            lo = min(s[j]["l"] for j in sel)
            largeur = hi - lo
            net = s[sel[-1]]["c"] - s[sel[0]]["o"]
            hauts = sum(1 for j in sel if s[j]["h"] >= hi - BORD * largeur)
            bas = sum(1 for j in sel if s[j]["l"] <= lo + BORD * largeur)
            print("  %-18s %2d seances | haut %.1f  bas %.1f  largeur %.1f"
                  % (lab, len(sel), hi, lo, largeur))
            print("  %-18s deplacement net %+.1f, soit %.0f%% de la largeur"
                  % ("", net, 100.0 * abs(net) / largeur if largeur else 0))
            print("  %-18s seances touchant le haut : %d, le bas : %d"
                  % ("", hauts, bas))
        print()

    # --- comportement du dispositif, jour par jour -------------------------
    print("=" * 92)
    print("  LE DISPOSITIF, JOUR PAR JOUR  (P&L realise, toutes familles)")
    print("=" * 92)
    print("%-12s %10s %6s %6s %10s" % ("jour", "PnL", "N", "WR", "PnL/trade"))
    print("-" * 92)
    for j in sorted(jours_pnl):
        e = jours_pnl[j]
        print("%-12s %10.2f %6d %5.0f%% %10.2f"
              % (j, e["pnl"], e["n"], 100.0 * e["gagnants"] / max(1, e["n"]),
                 e["pnl"] / max(1, e["n"])))
    print("-" * 92)

    for lab, sel in (("avant %s" % a.bascule,
                      [j for j in jours_pnl if j < a.bascule]),
                     ("depuis %s" % a.bascule,
                      [j for j in jours_pnl if j >= a.bascule])):
        if not sel:
            continue
        n = sum(jours_pnl[j]["n"] for j in sel)
        pn = sum(jours_pnl[j]["pnl"] for j in sel)
        g = sum(jours_pnl[j]["gagnants"] for j in sel)
        print("  %-18s %2d seances, %5d trades, %+10.2f, %+7.2f/trade, WR %.0f%%"
              % (lab, len(sel), n, pn, pn / max(1, n), 100.0 * g / max(1, n)))

    # --- par famille de magic ---------------------------------------------
    print()
    print("=" * 92)
    print("  PAR FAMILLE DE MAGIC, AVANT ET DEPUIS LA BASCULE")
    print("=" * 92)
    av, ap = {}, {}
    for j, d in familles.items():
        cible = ap if j >= a.bascule else av
        for f, v in d.items():
            cible[f] = cible.get(f, 0.0) + v
    toutes = sorted(set(av) | set(ap), key=lambda f: -(abs(av.get(f, 0)) + abs(ap.get(f, 0))))
    print("%-10s %14s %14s %14s" % ("famille", "avant", "depuis", "ecart"))
    print("-" * 92)
    for f in toutes[:25]:
        a_, p_ = av.get(f, 0.0), ap.get(f, 0.0)
        print("%-10s %14.2f %14.2f %+14.2f" % ("M" + f, a_, p_, p_ - a_))
    print("-" * 92)
    print("Une famille dont le signe s inverse a la bascule est la seule chose")
    print("interessante ici. Un simple recul peut n etre qu un volume moindre.")

    print()
    print("RESERVES")
    print("  Les deux periodes n ont ni la meme duree ni le meme nombre de")
    print("  trades : comparer des totaux serait trompeur, seuls les ratios")
    print("  par trade se lisent.")
    print("  Une bascule fixee a la main est un choix, pas une mesure. La")
    print("  colonne ER_5 permet de verifier si elle tombe au bon endroit ;")
    print("  si l inflexion d ER_5 ne coincide pas avec --bascule, c est la")
    print("  bascule qu il faut deplacer, pas la lecture qu il faut forcer.")
    mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
