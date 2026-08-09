# -*- coding: utf-8 -*-
"""
ordre_cassures.py -- dans les seances qui cassent LES DEUX bornes,
                     laquelle cede en premier, et est-ce la bonne ?

POURQUOI CETTE MESURE
    Environ la moitie des seances cassent le plus haut ET le plus bas du
    matin. Tout ce qu on a mesure jusqu ici ignore la chronologie : on sait
    que les deux niveaux sont touches, jamais dans quel ordre.

    C est pourtant la question qui compte pour eviter les ordres a
    contre-sens. Si la premiere cassure est le plus souvent un faux
    depart, la suivre est exactement ce qu il ne faut pas faire.

CE QU ON MESURE
    1. dans les seances a double cassure, qui cede en premier
    2. la direction du matin annonce-t-elle laquelle ?
    3. LA QUESTION UTILE : la premiere cassure est-elle celle qui va le
       plus loin, ou le faux depart ?
    4. a quelle heure tombe la premiere cassure

LIMITE DE RESOLUTION, ASSUMEE
    On travaille en M5. Quand les deux bornes cedent dans la MEME bougie,
    l ordre est indeterminable et la seance est comptee a part, jamais
    attribuee arbitrairement. Le nombre d indetermines est affiche : s il
    est gros, la mesure ne vaut pas grand-chose et il faudra du M1.

HORAIRES
    Heure COURTIER, mesuree a UTC+3 par la localisation de l ouverture US
    (preopen.py) : une heure d avance sur Paris. Ouverture cash US a 16h30
    courtier.
"""
import io, os, sys, math, datetime as dt

ACTIFS = ["US30", "SPX500", "NAS100"]
JOURS = 190
DEBUT_AM = 8
FIN_AM = 14          # meme convention que profil_jour.py
FIN = 22
SORTIE = "ordre_cassures.csv"


def moy(xs):
    return sum(xs) / float(len(xs)) if xs else None


def med(xs):
    xs = sorted(xs)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def p_norm(z):
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))


def p_prop(k1, n1, k2, n2):
    if n1 < 5 or n2 < 5:
        return None
    p = (k1 + k2) / float(n1 + n2)
    se = math.sqrt(p * (1 - p) * (1.0 / n1 + 1.0 / n2))
    if se == 0:
        return None
    return p_norm((k1 / float(n1) - k2 / float(n2)) / se)


def p_binom_demi(k, n):
    """Test bilateral contre 50/50 : la premiere cassure est-elle equilibree ?"""
    if n == 0:
        return None
    c = [1]
    for _ in range(n):
        c = [1] + [c[j] + c[j + 1] for j in range(len(c) - 1)] + [1]
    tot = float(sum(c))
    q = sum(c[i] for i in range(n + 1) if i >= max(k, n - k) or i <= min(k, n - k))
    return min(1.0, q / tot)


def charger():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        print("MT5 injoignable"); sys.exit(1)
    fin = dt.datetime.now()
    deb = fin - dt.timedelta(days=JOURS)
    out = {}
    for sym in ACTIFS:
        mt5.symbol_select(sym, True)
        bars, t = [], deb
        while t < fin:
            t2 = min(t + dt.timedelta(days=30), fin)
            r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, t, t2)
            if r is not None and len(r):
                bars.extend(r)
            t = t2
        if not bars:
            print("  %-8s aucune bougie" % sym); continue
        vus, prop = set(), []
        for x in bars:
            k = int(x["time"])
            if k in vus:
                continue
            vus.add(k)
            prop.append((dt.datetime.utcfromtimestamp(k), float(x["high"]),
                         float(x["low"]), float(x["open"]), float(x["close"])))
        prop.sort()
        out[sym] = prop
        print("  %-8s %d bougies M5" % (sym, len(prop)))
    mt5.shutdown()
    return out


def construire(prop):
    par = {}
    for t, h, l, o, c in prop:
        j = t.strftime("%Y-%m-%d")
        if DEBUT_AM <= t.hour < FIN_AM:
            par.setdefault(j, {"am": [], "pm": []})["am"].append((t, h, l, o, c))
        elif FIN_AM <= t.hour < FIN:
            par.setdefault(j, {"am": [], "pm": []})["pm"].append((t, h, l, o, c))
    out = []
    for j in sorted(par):
        am, pm = par[j]["am"], par[j]["pm"]
        if len(am) < 20 or len(pm) < 20:
            continue
        am.sort(); pm.sort()
        ah = max(x[1] for x in am)
        al = min(x[2] for x in am)
        ar = ah - al
        if ar <= 0:
            continue
        sens = "UP" if am[-1][4] > am[0][3] else "DOWN"
        t_bas = t_haut = None
        i_bas = i_haut = None
        for i, (t, h, l, o, c) in enumerate(pm):
            if t_bas is None and l < al:
                t_bas, i_bas = t, i
            if t_haut is None and h > ah:
                t_haut, i_haut = t, i
            if t_bas is not None and t_haut is not None:
                break
        ph = max(x[1] for x in pm)
        pl = min(x[2] for x in pm)
        # on conserve les bougies du PM sous forme d increments : indispensable
        # pour le temoin par permutation (voir null_permute)
        inc = []
        prev = pm[0][3]
        for t, h, l, o, c in pm:
            inc.append((c - prev, h - c, c - l))
            prev = c
        d = {"jour": j, "am_dir": sens, "am_range": ar,
             "am_high": ah, "am_low": al, "depart": pm[0][3], "inc": inc,
             "ext_bas": max(0.0, (al - pl) / ar), "ext_haut": max(0.0, (ph - ah) / ar),
             "t_bas": t_bas.strftime("%H:%M") if t_bas else "",
             "t_haut": t_haut.strftime("%H:%M") if t_haut else ""}
        if t_bas is not None and t_haut is not None:
            if i_bas < i_haut:
                d["premier"] = "BAS"
            elif i_haut < i_bas:
                d["premier"] = "HAUT"
            else:
                d["premier"] = "INDETERMINE"   # meme bougie M5
        elif t_bas is not None:
            d["premier"] = "BAS_SEUL"
        elif t_haut is not None:
            d["premier"] = "HAUT_SEUL"
        else:
            d["premier"] = "AUCUNE"
        out.append(d)
    return out


def rejouer(d, ordre):
    """Rejoue l apres-midi avec les bougies dans l ordre donne. Renvoie
    (premier, ext_bas, ext_haut) ou None si une seule borne cede."""
    c = d["depart"]
    ah, al, ar = d["am_high"], d["am_low"], d["am_range"]
    ib = ih = None
    hi, lo = c, c
    for i, k in enumerate(ordre):
        dc, up, dn = d["inc"][k]
        c += dc
        h, l = c + up, c - dn
        if h > hi:
            hi = h
        if l < lo:
            lo = l
        if ib is None and l < al:
            ib = i
        if ih is None and h > ah:
            ih = i
    if ib is None or ih is None or ib == ih:
        return None
    return ("BAS" if ib < ih else "HAUT",
            max(0.0, (al - lo) / ar), max(0.0, (hi - ah) / ar))


def null_permute(rows, K=20):
    """LE TEMOIN QUI COMPTE.

    Tester "la premiere cassure est-elle la plus ample" contre 50/50 est
    FAUX. Pour casser la SECONDE borne, le prix doit refaire tout le chemin
    en sens inverse et la depasser : la seconde cassure est donc plus ample
    par pure geometrie, sans aucun comportement de marche. Verifie sur
    marche aleatoire : 26%, avec p=0,000 contre 50/50.

    On construit donc le vrai temoin en melangeant l ORDRE des bougies de
    l apres-midi tout en conservant leurs amplitudes. La chronologie
    disparait, la geometrie reste.

    APPARIEMENT SEANCE PAR SEANCE, indispensable. Une premiere version
    mettait tous les rejeux dans un pool commun : les seances a faible
    range matinal cassent les deux bornes dans presque tous leurs rejeux
    et ecrasaient alors le temoin, alors que dans le reel chaque seance ne
    compte qu une fois. Resultat : sur marche aleatoire, temoin 39% contre
    26% reels, p=0,030 -- un effet parfaitement fictif. On calcule donc un
    taux PAR SEANCE, puis on moyenne sur les seules seances qui ont
    reellement produit une double cassure ordonnee.

    rows doit etre la liste des seances a double cassure REELLE."""
    import random
    random.seed(20260809)
    taux_bon, taux_bas, utilisees, rejeux = [], [], 0, 0
    for d in rows:
        n = len(d.get("inc") or [])
        if n < 10:
            continue
        idx = list(range(n))
        b = t = ba = 0
        for _ in range(K):
            random.shuffle(idx)
            r = rejouer(d, idx)
            if r is None:
                continue
            prem, eb, eh = r
            t += 1
            if prem == "BAS":
                ba += 1
            if ("BAS" if eb > eh else "HAUT") == prem:
                b += 1
        if t >= 3:                       # cette seance a un taux exploitable
            taux_bon.append(100.0 * b / t)
            taux_bas.append(100.0 * ba / t)
            utilisees += 1
            rejeux += t
    if not taux_bon:
        return None, None, 0
    return moy(taux_bon), moy(taux_bas), rejeux


def main():
    print("=== chargement M5 ===")
    data = charger()
    if not data:
        return 1
    tables = {}
    for sym in sorted(data):
        tables[sym] = construire(data[sym])
        print("  %-8s %d seances" % (sym, len(tables[sym])))

    cols = ["jour", "asset", "am_dir", "am_range", "premier",
            "t_bas", "t_haut", "ext_bas", "ext_haut"]
    with io.open(SORTIE, "w", encoding="utf-8") as fo:
        fo.write(";".join(cols) + "\n")
        for sym in sorted(tables):
            for d in tables[sym]:
                d["asset"] = sym
                fo.write(";".join(str(d.get(c, "")) for c in cols) + "\n")
    tout = [d for sym in tables for d in tables[sym]]
    print("ecrit %s : %d lignes" % (SORTIE, len(tout)))

    print()
    print("=" * 86)
    print("  1. repartition des seances")
    print("=" * 86)
    cnt = {}
    for d in tout:
        cnt[d["premier"]] = cnt.get(d["premier"], 0) + 1
    for k in ("BAS", "HAUT", "INDETERMINE", "BAS_SEUL", "HAUT_SEUL", "AUCUNE"):
        if k in cnt:
            print("  %-14s %5d  %5.1f%%" % (k, cnt[k], 100.0 * cnt[k] / len(tout)))
    ind = cnt.get("INDETERMINE", 0)
    dbl = cnt.get("BAS", 0) + cnt.get("HAUT", 0) + ind
    print("  double cassure : %d seances, dont %d indeterminees (%.0f%%)"
          % (dbl, ind, 100.0 * ind / max(1, dbl)))
    if ind > 0.15 * max(1, dbl):
        print("  /!\\ trop d indeterminees en M5 : il faudrait du M1 pour trancher.")

    both = [d for d in tout if d["premier"] in ("BAS", "HAUT")]
    if len(both) < 30:
        print("\nmoins de 30 seances a double cassure ordonnee -- on s arrete.")
        return 0
    kb = sum(1 for d in both if d["premier"] == "BAS")
    print()
    print("  parmi les doubles cassures ordonnees : BAS d abord %d fois sur %d "
          "(%.0f%%), p=%s contre 50/50"
          % (kb, len(both), 100.0 * kb / len(both),
             "%.3f" % p_binom_demi(kb, len(both))))

    print()
    print("=" * 86)
    print("  2. la direction du matin annonce-t-elle laquelle cede en premier ?")
    print("=" * 86)
    print("  %-10s %6s %14s" % ("matin", "N", "BAS en premier"))
    print("  " + "-" * 40)
    grp = {}
    for d in both:
        grp.setdefault(d["am_dir"], []).append(d)
    for s in ("DOWN", "UP"):
        g = grp.get(s, [])
        if len(g) < 10:
            continue
        k = sum(1 for d in g if d["premier"] == "BAS")
        print("  %-10s %6d %13.0f%%" % (s, len(g), 100.0 * k / len(g)))
    a, b = grp.get("DOWN", []), grp.get("UP", [])
    if len(a) >= 10 and len(b) >= 10:
        ka = sum(1 for d in a if d["premier"] == "BAS")
        kb2 = sum(1 for d in b if d["premier"] == "BAS")
        p = p_prop(ka, len(a), kb2, len(b))
        print("  ecart %+.1f points, p=%s"
              % (100.0 * (ka / float(len(a)) - kb2 / float(len(b))),
                 "%.3f" % p if p is not None else "-"))

    print()
    print("=" * 86)
    print("  3. LA QUESTION UTILE : la premiere cassure va-t-elle le plus loin ?")
    print("=" * 86)
    print("Si la premiere cassure est le plus souvent le FAUX DEPART, la suivre")
    print("est exactement ce qu il ne faut pas faire -- et ce serait la premiere")
    print("regle de non-trading vraiment operationnelle de toute l etude.")
    bon = 0
    for d in both:
        gagne = "BAS" if d["ext_bas"] > d["ext_haut"] else "HAUT"
        if gagne == d["premier"]:
            bon += 1
    reel = 100.0 * bon / len(both)
    print()
    print("  la premiere cassure est aussi la plus ample : %d fois sur %d (%.0f%%)"
          % (bon, len(both), reel))
    print()
    print("  calcul du temoin par permutation des bougies du PM...")
    tn, tbas, ntot = null_permute(both)
    if tn is None:
        print("  temoin indisponible.")
        return 0
    print("  TEMOIN (chronologie detruite, geometrie conservee) : %.0f%% "
          "sur %d rejeux" % (tn, ntot))
    # ecart reel - temoin, approximation normale sur la proportion reelle
    se = math.sqrt(tn / 100.0 * (1 - tn / 100.0) / len(both)) * 100.0
    p = p_norm((reel - tn) / se) if se else None
    print("  ecart %+.1f points, p=%s" % (reel - tn, "%.3f" % p if p is not None else "-"))
    print()
    print("  NE PAS comparer a 50%% : sur une marche aleatoire ce chiffre vaut")
    print("  deja ~26%%, parce que casser la SECONDE borne oblige a refaire tout")
    print("  le chemin en sens inverse. La seconde cassure est plus ample par")
    print("  geometrie, pas par comportement.")
    print()
    print("  CALIBRAGE DU TEMOIN, mesure sur marche aleatoire pure :")
    print("  il reste un biais residuel d environ -4 a -5 points, toujours dans")
    print("  le sens 'reel sous temoin'. Sur 2100 seances simulees sans aucune")
    print("  structure, l ecart sortait a -4,5 avec p=0,086. Il faut donc")
    print("  RETRANCHER ce biais avant de lire : un ecart de -5 points ne vaut")
    print("  rien, seul un ecart nettement au-dela merite attention.")
    if p is not None and p < 0.05 and abs(reel - tn) > 8.0:
        if reel > tn:
            print("  -> la premiere cassure est PLUS souvent la bonne que ne le")
            print("     voudrait le hasard. Suivre le premier franchissement a")
            print("     un fondement.")
        else:
            print("  -> la premiere cassure est ENCORE PLUS souvent un faux depart")
            print("     que ne le voudrait le hasard. Ne pas ouvrir dans son sens.")
    else:
        print("  -> conforme au hasard. La chronologie n ajoute rien a la")
        print("     geometrie, et il n y a pas de regle a en tirer.")
    print()
    print("  (rappel section 1 : BAS en premier %.0f%% dans le reel, %.0f%% dans"
          % (100.0 * kb / len(both), tbas))
    print("   le temoin -- meme logique, ne pas comparer a 50%%.)")

    print()
    print("  par direction du matin :")
    for s in ("DOWN", "UP"):
        g = grp.get(s, [])
        if len(g) < 15:
            continue
        k = sum(1 for d in g
                if ("BAS" if d["ext_bas"] > d["ext_haut"] else "HAUT") == d["premier"])
        print("    matin %-6s %4d seances, premiere = plus ample %3.0f%%"
              % (s, len(g), 100.0 * k / len(g)))

    print()
    print("=" * 86)
    print("  4. a quelle heure tombe la premiere cassure")
    print("=" * 86)
    print("  (heure COURTIER, UTC+3 : retranche 1h pour ton heure locale.")
    print("   ouverture cash US a 16h30 courtier, soit 15h30 chez toi)")
    hs = sorted(d["t_bas"] if d["premier"] == "BAS" else d["t_haut"] for d in both)
    n = len(hs)
    print("  mediane %s   quartiles %s et %s   min %s   max %s"
          % (hs[n // 2], hs[n // 4], hs[(3 * n) // 4], hs[0], hs[-1]))
    avant = sum(1 for h in hs if h < "16:30")
    print("  %d sur %d (%.0f%%) tombent AVANT l ouverture cash US"
          % (avant, n, 100.0 * avant / n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
