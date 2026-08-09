# -*- coding: utf-8 -*-
"""
h1_annonce.py -- QUAND la premiere heure US a-t-elle vraiment annonce
                 la volatilite du reste de la seance ?

POURQUOI CE FICHIER EN PLUS DE h1_seance.py
    h1_seance donne un rho moyen. Une correlation moyenne peut tres bien
    cacher un lien qui ne fonctionne qu a certaines periodes, ou qu au
    dela d un certain seuil. Et on vient de voir avec juillet contre aout
    que ce corpus contient au moins deux regimes tres differents.

    Ici on ne demande plus "y a-t-il un lien" mais "QUAND a-t-il tenu, a
    partir de quel seuil, et a quoi ressemblent les ratés".

CINQ QUESTIONS
    1. taux de reussite plutot que correlation : sachant que la premiere
       heure est dans le cinquieme le plus haut, quelle part des seances
       a effectivement un reste ample ? Et de combien au-dessus du hasard ?
    2. a partir de quel seuil la prediction devient-elle fiable ?
    3. le lien est-il STABLE dans le temps, ou concentre sur une periode ?
       C est la vraie question posee.
    4. a quoi ressemblent les RATES -- grande premiere heure suivie d un
       reste calme ?
    5. le lien est-il renforce quand la premiere heure casse aussi le
       range du matin ?

    Les amplitudes sont converties en RANGS PAR ACTIF avant tout
    regroupement : melanger des points d US30 et de SPX500 n aurait aucun
    sens, on l a deja constate deux fois.

Lit h1_seance.csv. Aucun MT5, instantane.
"""
import io, os, sys, math

FIC = "h1_seance.csv"
MIN_N = 12


def f(v):
    if v is None:
        return None
    v = v.strip().replace(",", ".")
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def moy(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / float(len(xs)) if xs else None


def med(xs):
    xs = sorted(x for x in xs if x is not None)
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
    return p_norm((k1 / float(n1) - k2 / float(n2)) / se) if se else None


def lire():
    if not os.path.isfile(FIC):
        print("introuvable : %s -- lance d abord h1_seance.py" % FIC)
        sys.exit(1)
    lg = [l.rstrip("\n") for l in io.open(FIC, encoding="utf-8-sig") if l.strip()]
    sep = ";" if lg[0].count(";") >= lg[0].count(",") else ","
    ent = [c.strip() for c in lg[0].split(sep)]
    rows = []
    for l in lg[1:]:
        c = l.split(sep)
        if len(c) < len(ent):
            c += [""] * (len(ent) - len(c))
        d = dict(zip(ent, c))
        h1, rds = f(d.get("h1_range")), f(d.get("rds_range"))
        if not h1 or not rds or h1 <= 0 or rds <= 0:
            continue
        rows.append({"jour": (d.get("jour") or "").strip(),
                     "asset": (d.get("asset") or "").strip(),
                     "h1": h1, "rds": rds,
                     "am_range": f(d.get("am_range")),
                     "h1_eff": f(d.get("h1_eff")),
                     "casse": (1 if d.get("h1_casse_haut") == "1" else 0)
                              + (1 if d.get("h1_casse_bas") == "1" else 0)})
    # rangs PAR ACTIF : melanger des points d US30 et de SPX500 n a aucun sens
    par = {}
    for r in rows:
        par.setdefault(r["asset"], []).append(r)
    for a, g in par.items():
        for cle in ("h1", "rds", "am_range"):
            vals = [x[cle] for x in g if x[cle] is not None]
            if not vals:
                continue
            s = sorted(vals)
            for x in g:
                if x[cle] is None:
                    x["q_" + cle] = None
                else:
                    # quantile dans [0,1] au sein de l actif
                    i = sum(1 for v in s if v < x[cle])
                    x["q_" + cle] = i / float(max(1, len(s) - 1))
    print("%s : %d seances, %d actifs, %s -> %s"
          % (FIC, len(rows), len(par),
             min(r["jour"] for r in rows), max(r["jour"] for r in rows)))
    return rows


def section1(rows):
    print()
    print("=" * 86)
    print("  1. taux de reussite : cinquieme haut de H1 contre reste ample")
    print("=" * 86)
    print("Un rho ne dit pas ce qu on gagne a s en servir. Un taux, si.")
    print("'reste ample' = au-dessus de la mediane de l actif.")
    print()
    print("  %-9s %-16s %6s %14s %10s"
          % ("actif", "H1 dans le", "N", "reste ample", "vs base"))
    print("  " + "-" * 62)
    par = {}
    for r in rows:
        par.setdefault(r["asset"], []).append(r)
    for a in sorted(par):
        g = [x for x in par[a] if x.get("q_h1") is not None]
        base = sum(1 for x in g if x["q_rds"] >= 0.5) / float(len(g))
        for lo, hi, lib in ((0.8, 1.01, "cinquieme HAUT"),
                            (0.6, 0.8, "4e cinquieme"),
                            (0.4, 0.6, "milieu"),
                            (0.0, 0.2, "cinquieme BAS")):
            s = [x for x in g if lo <= x["q_h1"] < hi]
            if len(s) < MIN_N:
                continue
            k = sum(1 for x in s if x["q_rds"] >= 0.5)
            print("  %-9s %-16s %6d %13.0f%% %+9.0f pt"
                  % (a, lib, len(s), 100.0 * k / len(s),
                     100.0 * (k / float(len(s)) - base)))
        print("  %-9s %-16s %6d %13.0f%%   <- reference" % (a, "toutes", len(g), 100.0 * base))
        print("  " + "-" * 62)


def section2(rows):
    print()
    print("=" * 86)
    print("  2. a partir de quel seuil la prediction devient-elle fiable ?")
    print("=" * 86)
    print("  %-9s %-14s %6s %14s %12s %8s"
          % ("actif", "H1 au-dessus", "N", "reste ample", "reste median", "p"))
    print("  " + "-" * 66)
    par = {}
    for r in rows:
        par.setdefault(r["asset"], []).append(r)
    for a in sorted(par):
        g = [x for x in par[a] if x.get("q_h1") is not None]
        for seuil in (0.5, 0.6, 0.7, 0.8, 0.9):
            s = [x for x in g if x["q_h1"] >= seuil]
            autres = [x for x in g if x["q_h1"] < seuil]
            if len(s) < MIN_N or len(autres) < MIN_N:
                continue
            k = sum(1 for x in s if x["q_rds"] >= 0.5)
            ka = sum(1 for x in autres if x["q_rds"] >= 0.5)
            p = p_prop(k, len(s), ka, len(autres))
            print("  %-9s %-14s %6d %13.0f%% %12.0f %8s"
                  % (a, "%.0f%%" % (100 * seuil), len(s), 100.0 * k / len(s),
                     med([x["rds"] for x in s]),
                     "%.3f" % p if p is not None else "-"))
        print("  " + "-" * 66)
    print("  'reste median' est en points de l actif : il chiffre ce que")
    print("  vaut concretement le signal, pas seulement sa fiabilite.")


def section3(rows):
    print()
    print("=" * 86)
    print("  3. LE LIEN EST-IL STABLE DANS LE TEMPS ? -- la vraie question")
    print("=" * 86)
    print("Un rho moyen peut cacher un lien qui ne marche qu a une periode.")
    print("Taux de reussite du cinquieme haut, mois par mois, tous actifs.")
    print()
    print("  %-10s %6s %14s %10s %14s"
          % ("mois", "N haut", "reste ample", "base", "vs base"))
    print("  " + "-" * 60)
    mois = {}
    for r in rows:
        if r.get("q_h1") is None:
            continue
        mois.setdefault(r["jour"][:7], []).append(r)
    for m in sorted(mois):
        g = mois[m]
        if len(g) < 15:
            continue
        base = sum(1 for x in g if x["q_rds"] >= 0.5) / float(len(g))
        s = [x for x in g if x["q_h1"] >= 0.8]
        if len(s) < 5:
            print("  %-10s %6d   (trop peu dans le cinquieme haut)" % (m, len(s)))
            continue
        k = sum(1 for x in s if x["q_rds"] >= 0.5)
        print("  %-10s %6d %13.0f%% %9.0f%% %+13.0f pt"
              % (m, len(s), 100.0 * k / len(s), 100.0 * base,
                 100.0 * (k / float(len(s)) - base)))
    print("  " + "-" * 60)
    print("  Une colonne 'vs base' positive PARTOUT = lien stable, utilisable.")
    print("  Positive sur un ou deux mois seulement = le rho moyen etait porte")
    print("  par une periode, et le signal n est pas fiable.")


def section4(rows):
    print()
    print("=" * 86)
    print("  4. a quoi ressemblent les RATES ?")
    print("=" * 86)
    print("Grande premiere heure suivie d un reste calme : ces seances ont-elles")
    print("un trait commun qui permettrait de les ecarter a l avance ?")
    print()
    hauts = [r for r in rows if r.get("q_h1") is not None and r["q_h1"] >= 0.8]
    ok = [r for r in hauts if r["q_rds"] >= 0.5]
    rate = [r for r in hauts if r["q_rds"] < 0.5]
    if len(rate) < 8:
        print("  moins de 8 rates : rien a caracteriser.")
        return
    print("  %d reussites, %d rates sur %d grandes premieres heures"
          % (len(ok), len(rate), len(hauts)))
    print()
    print("  %-22s %12s %12s" % ("", "reussites", "rates"))
    print("  " + "-" * 48)
    for cle, lib in (("h1_eff", "efficience de H1"),
                     ("q_am_range", "rang du range matin"),
                     ("casse", "bornes AM cassees")):
        a = med([r.get(cle) for r in ok if r.get(cle) is not None])
        b = med([r.get(cle) for r in rate if r.get(cle) is not None])
        if a is None or b is None:
            continue
        print("  %-22s %12.2f %12.2f" % (lib, a, b))
    print("  " + "-" * 48)
    print("  Un ecart net sur une ligne donnerait un filtre supplementaire.")
    print("  Des colonnes identiques : les rates sont indiscernables a l avance.")


def section5(rows):
    print()
    print("=" * 86)
    print("  5. le lien est-il renforce quand H1 casse aussi le range du matin ?")
    print("=" * 86)
    print("  %-18s %6s %14s" % ("H1 a casse", "N", "reste ample"))
    print("  " + "-" * 42)
    hauts = [r for r in rows if r.get("q_h1") is not None and r["q_h1"] >= 0.8]
    for c, lib in ((0, "aucune borne"), (1, "une borne"), (2, "les deux")):
        s = [r for r in hauts if r["casse"] == c]
        if len(s) < 8:
            continue
        k = sum(1 for x in s if x["q_rds"] >= 0.5)
        print("  %-18s %6d %13.0f%%" % (lib, len(s), 100.0 * k / len(s)))
    print("  " + "-" * 42)


def main():
    rows = lire()
    if len(rows) < 60:
        print("trop peu de seances."); return 1
    section1(rows)
    section2(rows)
    section3(rows)
    section4(rows)
    section5(rows)
    print()
    print("=" * 86)
    print("  ce qui deciderait")
    print("=" * 86)
    print("La section 3 est la reponse a ta question. Si le lien tient mois")
    print("apres mois, la premiere heure est un capteur utilisable. S il ne")
    print("tient que sur un ou deux mois, le rho de 0,26 a 0,51 etait porte")
    print("par une periode et le gel V6 partira avec une hypothese faible.")
    print()
    print("La section 2 dit ce que le signal vaut en POINTS, pas seulement en")
    print("fiabilite : un signal fiable a 60%% qui ne change l amplitude que de")
    print("dix points ne sert a rien.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
