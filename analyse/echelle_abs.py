# -*- coding: utf-8 -*-
"""
echelle_abs.py -- l objectif doit-il etre un MULTIPLE du range du matin,
                  ou un nombre de POINTS fixe ?

LA QUESTION
    On a mesure que l extension du PM, exprimee en ranges du matin, vaut
    1,66 les matinees etroites et 0,75 les matinees larges (p=0,000).
    Deux lectures s opposent :

      a) le marche fait vraiment moins de chemin relatif apres une matinee
         large -- alors le range du matin reste le bon etalon ;
      b) le mouvement absolu de l apres-midi est a peu pres constant, et
         le rapport ne varie que parce que son denominateur varie -- alors
         normaliser par le range du matin AJOUTE du bruit au lieu d en
         retirer, et l objectif devrait etre en points.

    Ce script tranche, et il le tranche en euros de gain espere, pas en
    coefficient de correlation.

TROIS MESURES, DE LA PLUS FAIBLE A LA PLUS DECISIVE

  1. correlation de rang entre le range du matin et l extension ABSOLUE.
     Proche de 0 = le matin ne dit rien de l amplitude de l apres-midi.
     Proche de 1 = proportionnalite, le multiple est justifie.

  2. dispersion. Si normaliser sert a quelque chose, le coefficient de
     variation du RAPPORT doit etre plus petit que celui de l ABSOLU.
     S il est plus grand, la normalisation degrade.

  3. le test qui decide : on calcule le gain espere x*S(x) des DEUX
     parametrages, ramene aux memes unites (des points), et on compare
     leurs maxima. Celui qui capture le plus a raison.
"""
import io, os, sys, math

FIC = "profil_jour.csv"
# MEME nombre de candidats pour les deux parametrages. Avec 40 valeurs
# de points contre 10 multiples, le fixe gagnait par simple surapprentissage :
# verifie sur donnees proportionnelles par construction, il sortait
# vainqueur a +6,6% alors que la bonne reponse etait "multiple".
MULT = [i * 0.1 for i in range(1, 41)]
PART_CAL = 0.60          # part des seances servant a choisir le parametre
BANDES = [(0.0, 0.75, "ETROIT"), (0.75, 1.30, "NORMAL"), (1.30, 9.9, "LARGE")]
FENETRE = 20


def f(v):
    if v is None:
        return None
    v = v.strip().replace(",", ".")
    if v == "" or v.upper() in ("NA", "NONE", "NAN"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def lire(chemin):
    if not os.path.isfile(chemin):
        print("introuvable : %s" % chemin)
        sys.exit(1)
    lg = [l.rstrip("\n") for l in io.open(chemin, encoding="utf-8-sig") if l.strip()]
    sep = ";" if lg[0].count(";") >= lg[0].count(",") else ","
    ent = [c.strip() for c in lg[0].split(sep)]
    out = []
    for l in lg[1:]:
        c = l.split(sep)
        if len(c) < len(ent):
            c += [""] * (len(ent) - len(c))
        out.append(dict(zip(ent, c)))
    return out


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
    m = sum(xs) / float(len(xs))
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def rangs(xs):
    """rangs moyens, ex aequo traites correctement"""
    idx = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]:
            j += 1
        moyen = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[idx[k]] = moyen
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 5:
        return None, None
    ra, rb = rangs(a), rangs(b)
    ma, mb = moy(ra), moy(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    if da == 0 or db == 0:
        return None, None
    rho = num / (da * db)
    n = len(a)
    if abs(rho) >= 1.0 or n < 8:
        return rho, None
    t = rho * math.sqrt((n - 2) / (1 - rho * rho))
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t) / math.sqrt(2.0))))
    return rho, p


def prep(rows):
    out = []
    for r in rows:
        d = {"jour": r.get("jour", "").strip(), "asset": r.get("asset", "").strip()}
        for k in ("am_high", "am_low", "am_range", "pm_high", "pm_low"):
            d[k] = f(r.get(k))
        if not d["am_range"] or d["am_range"] <= 0:
            continue
        if d["am_low"] is None or d["am_high"] is None:
            continue
        # extension ABSOLUE en points, et RAPPORT en ranges du matin
        d["abs_bas"] = (max(0.0, d["am_low"] - d["pm_low"])
                        if d["pm_low"] is not None else None)
        d["abs_haut"] = (max(0.0, d["pm_high"] - d["am_high"])
                         if d["pm_high"] is not None else None)
        for s in ("bas", "haut"):
            a = d["abs_" + s]
            d["rap_" + s] = (a / d["am_range"]) if a is not None else None
        out.append(d)
    # bande de largeur, mediane glissante sans le jour courant
    par = {}
    for d in out:
        par.setdefault(d["asset"], []).append(d)
    for a in par:
        s = sorted(par[a], key=lambda x: x["jour"])
        for i, d in enumerate(s):
            h = [x["am_range"] for x in s[max(0, i - FENETRE):i]]
            d["bande"] = ""
            if len(h) >= 10:
                q = d["am_range"] / med(h)
                for lo, hi, nom in BANDES:
                    if lo <= q < hi:
                        d["bande"] = nom
                        break
    return out


def section1(rows, sens):
    print()
    print("=" * 84)
    print("  1. le range du matin annonce-t-il l amplitude absolue du PM ? (%s)" % sens)
    print("=" * 84)
    print("%-10s %6s %10s %9s %14s" % ("actif", "N", "rho", "p", "lecture"))
    print("-" * 84)
    par = {}
    for d in rows:
        par.setdefault(d["asset"], []).append(d)
    for a in sorted(par):
        g = [d for d in par[a] if d["abs_" + sens] and d["abs_" + sens] > 0]
        if len(g) < 10:
            continue
        rho, p = spearman([d["am_range"] for d in g], [d["abs_" + sens] for d in g])
        if rho is None:
            continue
        if rho < 0.2:
            lec = "independant"
        elif rho < 0.5:
            lec = "faible"
        else:
            lec = "proportionnel"
        print("%-10s %6d %10.3f %9s %14s"
              % (a, len(g), rho, "%.3f" % p if p is not None else "-", lec))
    print("-" * 84)
    print("rho proche de 1 : proportionnalite, le multiple est justifie.")
    print("/!\\ PUISSANCE FAIBLE dans l autre sens : l extension est aussi")
    print("dispersee qu une exponentielle, ce qui noie le signal du range du")
    print("matin. Sur des donnees proportionnelles PAR CONSTRUCTION, ce test")
    print("ne renvoie que rho = 0,03 a 0,15. Un rho faible ne prouve donc PAS")
    print("l independance. Seule la section 3 tranche.")


def section2(rows, sens):
    print()
    print("=" * 84)
    print("  2. normaliser par le range du matin reduit-il la dispersion ? (%s)" % sens)
    print("=" * 84)
    print("%-10s %6s %11s %11s %11s %11s %s"
          % ("actif", "N", "CV absolu", "CV rapport", "med abs", "med rap", "verdict"))
    print("-" * 84)
    par = {}
    for d in rows:
        par.setdefault(d["asset"], []).append(d)
    for a in sorted(par):
        g = [d for d in par[a] if d["abs_" + sens] and d["abs_" + sens] > 0]
        if len(g) < 10:
            continue
        A = [d["abs_" + sens] for d in g]
        R = [d["rap_" + sens] for d in g]
        cva = et(A) / moy(A) if moy(A) else 0
        cvr = et(R) / moy(R) if moy(R) else 0
        v = "normaliser AIDE" if cvr < cva * 0.95 else (
            "normaliser NUIT" if cvr > cva * 1.05 else "indifferent")
        print("%-10s %6d %11.3f %11.3f %11.1f %11.2f  %s"
              % (a, len(g), cva, cvr, med(A), med(R), v))
    print("-" * 84)
    print("Si le CV du rapport n est pas plus petit que celui de l absolu,")
    print("diviser par le range du matin n a rien range du tout.")


def section3(rows, sens):
    """Le test qui decide. On compare, EN POINTS, le gain espere des deux
    parametrages. Pour le multiple, la cible vaut x*am_range et varie
    chaque jour ; pour le fixe, elle vaut k points tous les jours. Dans
    les deux cas on n est paye que si l extension atteint la cible."""
    print()
    print("=" * 84)
    print("  3. quel parametrage capture le plus ? -- en points, %s" % sens)
    print("=" * 84)
    par = {}
    for d in rows:
        par.setdefault(d["asset"], []).append(d)
    for a in sorted(par):
        g = [d for d in par[a] if d["abs_" + sens] is not None]
        casse = [d for d in g if d["abs_" + sens] > 0]
        if len(casse) < 20:
            continue
        casse.sort(key=lambda d: d["jour"])
        coup = int(len(casse) * PART_CAL)
        cal, val = casse[:coup], casse[coup:]
        if len(val) < 10:
            continue
        rm = med([d["am_range"] for d in cal])

        def gain_mult(x, lot):
            return moy([(x * d["am_range"]) if d["abs_" + sens] >= x * d["am_range"]
                        else 0.0 for d in lot]) or 0.0

        def gain_fixe(k, lot):
            return moy([k if d["abs_" + sens] >= k else 0.0 for d in lot]) or 0.0

        # choix du parametre sur la periode de calage UNIQUEMENT
        bx = max(MULT, key=lambda x: gain_mult(x, cal))
        bk = max([x * rm for x in MULT], key=lambda k: gain_fixe(k, cal))
        # evaluation sur la periode reservee
        gm, gf = gain_mult(bx, val), gain_fixe(bk, val)
        tm = sum(1 for d in val if d["abs_" + sens] >= bx * d["am_range"]) / float(len(val))
        tf = sum(1 for d in val if d["abs_" + sens] >= bk) / float(len(val))
        ecart = 100.0 * (gf - gm) / max(1e-9, gm)

        print()
        print("%-10s %d cassures : %d de calage, %d d evaluation"
              % (a, len(casse), len(cal), len(val)))
        print("  multiple  : x = %.2f choisi sur le calage (%.0f pts au range median)"
              % (bx, bx * rm))
        print("              hors echantillon : touche %.0f%%, capture %.1f pts/cassure"
              % (100 * tm, gm))
        print("  points    : k = %.0f pts choisi sur le calage" % bk)
        print("              hors echantillon : touche %.0f%%, capture %.1f pts/cassure"
              % (100 * tf, gf))
        print("  ecart     : %.1f%% en faveur du %s"
              % (abs(ecart), "fixe" if ecart > 0 else "multiple"))
    print("-" * 84)
    print("Le parametre est choisi sur les %d%% premieres cassures et note sur"
          % int(100 * PART_CAL))
    print("les suivantes : les deux parametrages ont exactement le meme nombre")
    print("de candidats et la meme liberte, donc l ecart n est pas un artefact")
    print("de surapprentissage.")
    print()
    print("BRUIT DE FOND MESURE : sur des donnees proportionnelles PAR")
    print("CONSTRUCTION, cette version renvoie multiple / multiple / fixe avec")
    print("des ecarts de 8 a 15%. A 30-40 cassures d evaluation par actif, un")
    print("ecart isole de 15% ne veut donc RIEN dire. Seul un resultat de meme")
    print("sens sur les trois actifs, et dans les deux directions, est lisible.")
    print()
    print("Un ecart de quelques pourcents ne tranche rien : les deux se valent")
    print("alors, et le multiple reste preferable parce qu il s adapte seul aux")
    print("changements de volatilite. Un ecart franc et de meme sens sur les")
    print("trois actifs tranche.")


def section4(rows, sens):
    print()
    print("=" * 84)
    print("  4. extension absolue par bande de largeur du matin (%s)" % sens)
    print("=" * 84)
    print("Si l absolu est stable d une bande a l autre alors que le rapport")
    print("varie, c est le denominateur qui bougeait, pas le marche.")
    print()
    print("%-10s %-9s %6s %12s %12s %12s"
          % ("actif", "bande", "N", "range AM med", "abs med (pts)", "rapport med"))
    print("-" * 84)
    par = {}
    for d in rows:
        if d.get("bande"):
            par.setdefault(d["asset"], []).append(d)
    for a in sorted(par):
        for _lo, _hi, nom in BANDES:
            g = [d for d in par[a] if d["bande"] == nom
                 and d["abs_" + sens] and d["abs_" + sens] > 0]
            if len(g) < 8:
                continue
            print("%-10s %-9s %6d %12.1f %12.1f %12.2f"
                  % (a, nom, len(g), med([d["am_range"] for d in g]),
                     med([d["abs_" + sens] for d in g]),
                     med([d["rap_" + sens] for d in g])))
        print()
    print("-" * 84)


def main():
    chemin = sys.argv[1] if len(sys.argv) > 1 else FIC
    rows = prep(lire(chemin))
    if not rows:
        print("aucune ligne exploitable.")
        return 1
    print("%d lignes, %d actifs, %s -> %s"
          % (len(rows), len({d["asset"] for d in rows}),
             min(d["jour"] for d in rows), max(d["jour"] for d in rows)))
    for sens in ("bas", "haut"):
        section1(rows, sens)
        section2(rows, sens)
        section4(rows, sens)
        section3(rows, sens)
    print()
    print("=" * 84)
    print("  ce qu il faut retenir")
    print("=" * 84)
    print("La section 3 decide. Les sections 1, 2 et 4 expliquent pourquoi.")
    print("Si le fixe gagne franchement, l ecart 1,66 contre 0,75 entre")
    print("matinees etroites et larges etait un artefact de denominateur,")
    print("et le seuil doit se poser en points, pas en multiple.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
