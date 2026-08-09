# -*- coding: utf-8 -*-
"""
preopen.py -- la pre-ouverture US comme reference, a la place du matin.

POURQUOI
    Le range 8h-14h est large et vieux au moment ou on s en sert. Et on a
    mesure qu il etait un mauvais etalon : une cible en points fixes le
    bat 5 fois sur 6. L heure qui precede l ouverture cash americaine est
    une reference plus courte, plus fraiche, et peut-etre mieux calibree.

L HEURE N EST PAS CODEE EN DUR, ET C EST VOLONTAIRE
    Les bougies MT5 sont en heure COURTIER. Si le courtier est a GMT+3,
    "14h30" dans ta tete n est pas 14h30 dans les bougies, et toute
    l etude serait decalee d une heure sans que rien ne le signale.
    Le script localise donc l ouverture americaine DANS LES DONNEES, par
    le pic de volume, et definit la pre-ouverture relativement a elle.
    Le profil intraday est affiche : verifie-le avant de lire la suite.

CE QU IL MESURE
    1. profil intraday et localisation de l ouverture US
    2. probabilite de casser chaque borne de la pre-ouverture
    3. distribution de l extension, survie et hazard par bandes
    4. la direction de la pre-ouverture annonce-t-elle le cote ?
    5. la pre-ouverture est-elle un MEILLEUR etalon que le matin ?

    Ecrit preopen_jour.csv, une ligne par jour et par actif.
"""
import io, os, sys, math, datetime as dt

ACTIFS = ["US30", "SPX500", "NAS100"]
JOURS = 190
PRE_MIN = 60          # duree de la fenetre de pre-ouverture, en minutes
FIN = 22              # fin de la seance retenue, heure courtier
SORTIE = "preopen_jour.csv"
CSV_MATIN = "profil_jour.csv"
BANDES = [x * 0.25 for x in range(1, 13)]
PART_CAL = 0.60


def moy(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / float(len(xs)) if xs else None


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def et(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    m = moy(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def p_norm(z):
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))


def p_prop(k1, n1, k2, n2):
    if n1 < 3 or n2 < 3:
        return None
    p = (k1 + k2) / float(n1 + n2)
    se = math.sqrt(p * (1 - p) * (1.0 / n1 + 1.0 / n2))
    if se == 0:
        return None
    return p_norm((k1 / float(n1) - k2 / float(n2)) / se)


# --------------------------------------------------------------- chargement
def charger():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        print("MT5 injoignable"); sys.exit(1)
    fin = dt.datetime.now()
    deb = fin - dt.timedelta(days=JOURS)
    out = {}
    for sym in ACTIFS:
        mt5.symbol_select(sym, True)
        bars = []
        # par tranches de 30 jours : une demande de 180 jours en M1 renvoyait
        # vide (profondeur d historique du terminal). En M5 par tranches, ca passe.
        t = deb
        while t < fin:
            t2 = min(t + dt.timedelta(days=30), fin)
            r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, t, t2)
            if r is not None and len(r):
                bars.extend(r)
            t = t2
        if not bars:
            print("  %-8s aucune bougie" % sym); continue
        vus = set()
        prop = []
        for x in bars:
            k = int(x["time"])
            if k in vus:
                continue
            vus.add(k)
            prop.append((dt.datetime.utcfromtimestamp(k), float(x["high"]),
                         float(x["low"]), float(x["open"]), float(x["close"]),
                         float(x["tick_volume"])))
        prop.sort()
        out[sym] = prop
        print("  %-8s %d bougies M5" % (sym, len(prop)))
    mt5.shutdown()
    return out


# ------------------------------------------------- 1. ou est l ouverture US ?
def localiser(prop):
    """Pic de volume moyen par creneau de 5 minutes, cherche entre 12h et 18h.
    L ouverture cash americaine produit le plus gros pic de la journee, tres
    au-dessus du reste : c est un reperage robuste, qui ne suppose aucun
    fuseau."""
    vol, n = {}, {}
    for t, h, l, o, c, v in prop:
        k = t.hour * 60 + (t.minute // 5) * 5
        vol[k] = vol.get(k, 0.0) + v
        n[k] = n.get(k, 0) + 1
    prof = dict((k, vol[k] / n[k]) for k in vol if n[k] >= 20)
    cand = [(v, k) for k, v in prof.items() if 12 * 60 <= k <= 18 * 60]
    if not cand:
        return None, prof
    return max(cand)[1], prof


def afficher_profil(prof, ouv, sym):
    print()
    print("  %s -- profil de volume, creneaux les plus charges" % sym)
    top = sorted(prof.items(), key=lambda kv: -kv[1])[:8]
    for k, v in top:
        mark = "   <== ouverture retenue" if k == ouv else ""
        print("    %02d:%02d  volume moyen %8.0f%s" % (k // 60, k % 60, v, mark))
    base = med(list(prof.values()))
    if ouv is not None and base:
        print("    le pic vaut %.1f fois le volume median de la journee"
              % (prof[ouv] / base))


# ------------------------------------------------------ 2. construire la table
def construire(prop, ouv):
    deb_pre = ouv - PRE_MIN
    par = {}
    for t, h, l, o, c, v in prop:
        k = t.hour * 60 + t.minute
        j = t.strftime("%Y-%m-%d")
        if deb_pre <= k < ouv:
            d = par.setdefault(j, {"pre": [], "post": []})
            d["pre"].append((t, h, l, o, c))
        elif ouv <= k < FIN * 60:
            d = par.setdefault(j, {"pre": [], "post": []})
            d["post"].append((t, h, l, o, c))
    out = []
    for j in sorted(par):
        pre, post = par[j]["pre"], par[j]["post"]
        if len(pre) < PRE_MIN // 5 - 2 or len(post) < 12:
            continue
        pre.sort(); post.sort()
        ph = max(x[1] for x in pre)
        pl = min(x[2] for x in pre)
        pr = ph - pl
        if pr <= 0:
            continue
        sens = "UP" if pre[-1][4] > pre[0][3] else "DOWN"
        oh = max(x[1] for x in post)
        ol = min(x[2] for x in post)
        out.append({"jour": j, "pre_high": ph, "pre_low": pl, "pre_range": pr,
                    "pre_dir": sens, "post_high": oh, "post_low": ol,
                    "casse_bas": 1 if ol < pl else 0,
                    "casse_haut": 1 if oh > ph else 0,
                    "ext_bas": max(0.0, (pl - ol) / pr),
                    "ext_haut": max(0.0, (oh - ph) / pr)})
    return out


# ------------------------------------------------------------- 3. survie
def survie(lot, sens):
    cle = "ext_" + sens
    g = [d[cle] for d in lot if d["casse_" + sens] == 1]
    if len(g) < 20:
        print("    trop peu de cassures (%d)" % len(g))
        return
    n = float(len(g))
    print("    %-6s %d cassures" % (sens, len(g)))
    print("      %6s %8s %10s %10s" % ("x", "S(x)", "x*S(x)", "base"))
    for x in BANDES:
        k = sum(1 for e in g if e >= x)
        print("      %6.2f %7.0f%% %10.3f %10d" % (x, 100.0 * k / n, x * k / n, k))
    print("      -- hazard par bandes de 0,25 (continuer encore une bande) --")
    for i in range(len(BANDES) - 1):
        a = sum(1 for e in g if e >= BANDES[i])
        b = sum(1 for e in g if e >= BANDES[i + 1])
        if a >= 8:
            print("      %.2f -> %.2f : %3.0f%% continuent  (base %d)"
                  % (BANDES[i], BANDES[i + 1], 100.0 * b / a, a))


# --------------------------------------------- 5. meilleur etalon que le matin ?
def lire_matin():
    if not os.path.isfile(CSV_MATIN):
        return {}
    lg = [l.rstrip("\n") for l in io.open(CSV_MATIN, encoding="utf-8-sig") if l.strip()]
    sep = ";" if lg[0].count(";") >= lg[0].count(",") else ","
    ent = [c.strip() for c in lg[0].split(sep)]
    out = {}
    for l in lg[1:]:
        c = l.split(sep)
        if len(c) < len(ent):
            c += [""] * (len(ent) - len(c))
        d = dict(zip(ent, c))
        try:
            r = float((d.get("am_range") or "").replace(",", "."))
        except ValueError:
            continue
        if r > 0:
            out[(d.get("jour", "").strip(), d.get("asset", "").strip())] = r
    return out


def comparer_etalons(lot, sym, matin, sens):
    """Meme protocole que echelle_abs.py : on choisit la cible sur les 60%
    premieres cassures et on la note sur les suivantes, avec le MEME nombre
    de candidats pour chaque etalon. Trois etalons en lice : le range de
    pre-ouverture, le range du matin, et un nombre de points fixe."""
    cle = "ext_" + sens
    abs_cle = lambda d: d[cle] * d["pre_range"]
    g = [d for d in lot if d["casse_" + sens] == 1]
    g = [d for d in g if (d["jour"], sym) in matin] if matin else g
    if len(g) < 40:
        print("    %s : trop peu de cassures appariees (%d)" % (sens, len(g)))
        return
    g.sort(key=lambda d: d["jour"])
    coup = int(len(g) * PART_CAL)
    cal, val = g[:coup], g[coup:]
    grille = [i * 0.1 for i in range(1, 41)]
    rm = med([d["pre_range"] for d in cal])

    def gain(lot2, taille):
        return moy([taille(d) if abs_cle(d) >= taille(d) else 0.0 for d in lot2]) or 0.0

    res = {}
    bx = max(grille, key=lambda x: gain(cal, lambda d: x * d["pre_range"]))
    res["pre-ouverture"] = (bx, gain(val, lambda d: bx * d["pre_range"]))
    if matin:
        bm = max(grille, key=lambda x: gain(cal, lambda d: x * matin[(d["jour"], sym)]))
        res["range du matin"] = (bm, gain(val, lambda d: bm * matin[(d["jour"], sym)]))
    bk = max([x * rm for x in grille], key=lambda k: gain(cal, lambda d: k))
    res["points fixes"] = (bk, gain(val, lambda d: bk))

    print("    %s -- capture hors echantillon, en points par cassure :" % sens)
    for nom, (par, gv) in sorted(res.items(), key=lambda kv: -kv[1][1]):
        print("      %-16s parametre %8.2f   capture %7.1f" % (nom, par, gv))
    best = max(res.items(), key=lambda kv: kv[1][1])
    print("      -> meilleur etalon : %s" % best[0])


# ------------------------------------------------------------------- main
def main():
    print("=== chargement M5 ===")
    data = charger()
    if not data:
        return 1
    matin = lire_matin()
    print("range du matin disponible pour %d couples jour/actif" % len(matin))

    tables, ouvertures = {}, {}
    print()
    print("=" * 84)
    print("  1. localisation de l ouverture US -- VERIFIE CE PROFIL")
    print("=" * 84)
    for sym in sorted(data):
        ouv, prof = localiser(data[sym])
        if ouv is None:
            print("  %s : ouverture introuvable" % sym); continue
        ouvertures[sym] = ouv
        afficher_profil(prof, ouv, sym)
        print("    pre-ouverture retenue : %02d:%02d -> %02d:%02d (heure courtier)"
              % ((ouv - PRE_MIN) // 60, (ouv - PRE_MIN) % 60, ouv // 60, ouv % 60))
        tables[sym] = construire(data[sym], ouv)
        print("    %d seances exploitables" % len(tables[sym]))

    if len(set(ouvertures.values())) > 1:
        print()
        print("/!\\ les trois indices ne donnent pas la meme heure d ouverture :")
        print("    %s" % ", ".join("%s=%02d:%02d" % (s, v // 60, v % 60)
                                   for s, v in sorted(ouvertures.items())))
        print("    ce n est pas anormal (volumes differents) mais verifie que")
        print("    l ecart reste de quelques minutes, pas d une heure.")

    cols = ["jour", "asset", "pre_high", "pre_low", "pre_range", "pre_dir",
            "post_high", "post_low", "casse_bas", "casse_haut", "ext_bas", "ext_haut"]
    with io.open(SORTIE, "w", encoding="utf-8") as fo:
        fo.write(";".join(cols) + "\n")
        for sym in sorted(tables):
            for d in tables[sym]:
                d["asset"] = sym
                fo.write(";".join(str(d.get(c, "")) for c in cols) + "\n")
    print()
    print("ecrit %s : %d lignes" % (SORTIE, sum(len(v) for v in tables.values())))

    print()
    print("=" * 84)
    print("  2. casser la pre-ouverture")
    print("=" * 84)
    print("%-10s %6s %9s %9s %9s %9s" % ("actif", "N", "P(bas)", "ext med", "P(haut)", "ext med"))
    print("-" * 84)
    for sym in sorted(tables):
        t = tables[sym]
        if len(t) < 20:
            continue
        eb = [d["ext_bas"] for d in t if d["casse_bas"] == 1]
        eh = [d["ext_haut"] for d in t if d["casse_haut"] == 1]
        print("%-10s %6d %8.0f%% %9.2f %8.0f%% %9.2f"
              % (sym, len(t), 100.0 * sum(d["casse_bas"] for d in t) / len(t), med(eb) or 0,
                 100.0 * sum(d["casse_haut"] for d in t) / len(t), med(eh) or 0))
    print("-" * 84)
    print("A comparer au range du matin : environ 70-73%% en bas et 77-78%% en")
    print("haut. Un taux nettement plus eleve ici signifie que la fenetre est")
    print("trop courte et que la casser ne veut plus dire grand-chose.")

    print()
    print("=" * 84)
    print("  3. survie et hazard")
    print("=" * 84)
    for sym in sorted(tables):
        print("  %s" % sym)
        for sens in ("bas", "haut"):
            survie(tables[sym], sens)
        print()
    print("Hazard plat = sans memoire, comme pour le range du matin.")
    print("Hazard DECROISSANT = la pre-ouverture, elle, aurait un epuisement,")
    print("et ce serait le premier resultat de ce type de toute l etude.")

    print()
    print("=" * 84)
    print("  4. la direction de la pre-ouverture annonce-t-elle le cote ?")
    print("=" * 84)
    print("Rappel : la direction du MATIN donne 88%% contre 56%% sur la casse basse.")
    print("%-10s %-6s %6s %9s %9s" % ("actif", "pre", "N", "P(bas)", "P(haut)"))
    print("-" * 84)
    for sym in sorted(tables):
        t = tables[sym]
        cel = {}
        for d in t:
            cel.setdefault(d["pre_dir"], []).append(d)
        for s in ("DOWN", "UP"):
            g = cel.get(s, [])
            if len(g) < 15:
                continue
            print("%-10s %-6s %6d %8.0f%% %8.0f%%"
                  % (sym, s, len(g),
                     100.0 * sum(d["casse_bas"] for d in g) / len(g),
                     100.0 * sum(d["casse_haut"] for d in g) / len(g)))
        a, b = cel.get("DOWN", []), cel.get("UP", [])
        if len(a) >= 10 and len(b) >= 10:
            p = p_prop(sum(d["casse_bas"] for d in a), len(a),
                       sum(d["casse_bas"] for d in b), len(b))
            print("%-10s ecart sur la casse basse : %+.1f points, p=%s"
                  % ("", 100.0 * (sum(d["casse_bas"] for d in a) / float(len(a))
                                  - sum(d["casse_bas"] for d in b) / float(len(b))),
                     "%.3f" % p if p is not None else "-"))
    print("-" * 84)

    print()
    print("=" * 84)
    print("  5. quel etalon capture le plus ? pre-ouverture, matin, ou points fixes")
    print("=" * 84)
    if not matin:
        print("profil_jour.csv absent : le range du matin ne peut pas concourir.")
    for sym in sorted(tables):
        print("  %s" % sym)
        for sens in ("bas", "haut"):
            comparer_etalons(tables[sym], sym, matin, sens)
        print()
    print("Meme protocole que echelle_abs.py : parametre choisi sur les 60%")
    print("premieres cassures, note sur les suivantes, meme nombre de candidats")
    print("pour les trois etalons. Bruit de fond mesure a cette taille : ~15%.")
    print("Il faut donc le meme gagnant sur les trois actifs ET les deux sens.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
