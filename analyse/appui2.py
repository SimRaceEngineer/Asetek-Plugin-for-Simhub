# -*- coding: utf-8 -*-
"""
appui2.py -- test d appui sur les niveaux de la veille, temoin par decalage.

DEUX TENTATIVES RATEES AVANT CELLE-CI, GARDEES EN MEMOIRE :

  1. temoin = le meme niveau pris sur une AUTRE seance (le 4a de
     croisements.py). L indice derive de milliers de points sur 128
     seances, donc ce temoin tombait a 10-30 ranges du matin. Le test
     mesurait la derive, pas le niveau. p=0,000 partout, artefact integral.

  2. temoin = un prix tire au hasard DANS la journee de la veille.
     Corrige la derive mais introduit un biais de position : le bas de la
     veille est la BORNE du domaine de tirage, donc quand l extreme passe
     dessous aucun temoin ne peut faire mieux. Verifie sur donnees
     aleatoires sans structure : p=0,001 pour le bas, p=0,000 pour le VAH,
     tandis que POC et cloture, qui sont centraux, sortaient a 0,49.
     C est la position dans le range qui parlait.

CE QUI MARCHE : LE DECALAGE
    Le temoin est le meme niveau deplace de DELTA range du matin, en haut
    et en bas. La question devient "ce point precis retient-il mieux qu un
    point situe 0,5 range a cote ?". Les deux subissent la meme procedure
    de contact et de franchissement, donc tout biais de position, d echelle
    et de derive s annule. Sous l hypothese nulle les deux taux sont egaux,
    quelle que soit la forme de la distribution des extremes.

CE QU ON MESURE
    contact     : l extreme du PM arrive a moins de SEUIL range au-dessus
                  (en dessous si on regarde vers le haut) du niveau.
    franchi     : l extreme depasse le niveau.
    P(franchir) : franchis / contacts. Un appui reel fait BAISSER ce taux
                  par rapport au temoin decale.
"""
import io, os, sys, math

FIC = "profil_jour.csv"
SEUILS = [0.10, 0.20, 0.35]          # definitions du "contact"
DECALAGES = [0.50, 1.00]             # temoins, en ranges du matin

BAS = [("prev_val", "VAL veille"), ("prev_poc", "POC veille"),
       ("prev_low", "bas veille"), ("prev_close", "cloture veille")]
HAUT = [("prev_vah", "VAH veille"), ("prev_poc", "POC veille"),
        ("prev_high", "haut veille"), ("prev_close", "cloture veille")]


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


def prep(rows):
    out = []
    for r in rows:
        d = {"jour": r.get("jour", "").strip(), "asset": r.get("asset", "").strip()}
        for k in ("am_high", "am_low", "am_range", "pm_high", "pm_low",
                  "prev_poc", "prev_vah", "prev_val",
                  "prev_high", "prev_low", "prev_close"):
            d[k] = f(r.get(k))
        if not d["am_range"] or d["am_range"] <= 0:
            continue
        if d["am_low"] is None or d["am_high"] is None:
            continue
        out.append(d)
    return out


def compte(rows, col_ou_val, sens, seuil, decalage=0.0):
    """Renvoie (contacts, franchis) pour le niveau, eventuellement decale.
    decalage > 0 eloigne le niveau de la borne du matin, < 0 le rapproche."""
    extreme = "pm_low" if sens == "bas" else "pm_high"
    borne = "am_low" if sens == "bas" else "am_high"
    contacts, franchis = 0, 0
    for d in rows:
        if d.get(extreme) is None or d.get(col_ou_val) is None:
            continue
        niv = d[col_ou_val]
        if sens == "bas":
            niv = niv - decalage * d["am_range"]
            if niv >= d[borne]:
                continue                       # niveau au-dessus du bas du matin
            marge = (d[extreme] - niv) / d["am_range"]
            if marge > seuil:
                continue                       # jamais arrive au contact
            contacts += 1
            if d[extreme] < niv:
                franchis += 1
        else:
            niv = niv + decalage * d["am_range"]
            if niv <= d[borne]:
                continue
            marge = (niv - d[extreme]) / d["am_range"]
            if marge > seuil:
                continue
            contacts += 1
            if d[extreme] > niv:
                franchis += 1
    return contacts, franchis


def test(rows, sens):
    niveaux = BAS if sens == "bas" else HAUT
    print()
    print("=" * 90)
    print("  arrive au contact, le prix franchit-il ? -- extreme vers le %s" % sens)
    print("=" * 90)
    print("temoin = le MEME niveau decale de %s range du matin, des deux cotes."
          % " et ".join("%.2f" % x for x in DECALAGES))
    print("appui reel = P(franchir) du vrai niveau nettement SOUS celle du temoin.")
    for seuil in SEUILS:
        print()
        print("  contact defini a %.2f range du matin" % seuil)
        print("  %-16s %9s %9s %11s %11s %8s"
              % ("niveau", "contacts", "franchis", "P(franchir)", "temoin", "p"))
        print("  " + "-" * 86)
        for col, lib in niveaux:
            c, k = compte(rows, col, sens, seuil, 0.0)
            tc, tk = 0, 0
            for dec in DECALAGES:
                for signe in (1.0, -1.0):
                    a, b = compte(rows, col, sens, seuil, signe * dec)
                    tc += a
                    tk += b
            if c < 8:
                print("  %-16s %9d   (trop peu de contacts)" % (lib, c))
                continue
            p = p_prop(k, c, tk, tc) if tc else None
            print("  %-16s %9d %9d %10.0f%% %10.0f%% %8s"
                  % (lib, c, k, 100.0 * k / c,
                     100.0 * tk / tc if tc else 0.0,
                     "%.3f" % p if p is not None else "-"))
    print("-" * 90)


def main():
    chemin = sys.argv[1] if len(sys.argv) > 1 else FIC
    rows = prep(lire(chemin))
    if not rows:
        print("aucune ligne exploitable.")
        return 1
    print("%d seances, %d actifs, %s -> %s"
          % (len(rows), len({d["asset"] for d in rows}),
             min(d["jour"] for d in rows), max(d["jour"] for d in rows)))
    print("rappel : hazard de fond ~91% de continuation par pas de 0,1 range AM.")
    test(rows, "bas")
    test(rows, "haut")
    print()
    print("Lecture : si le vrai niveau et son decale affichent le meme taux,")
    print("le niveau n a aucune vertu propre -- il vaut n importe quel point")
    print("situe un demi-range a cote. C est ce que disent deja le hazard")
    print("plat et le fade decroissant.")
    print()
    print("Ce fichier remplace le 4a de croisements.py, invalide (son temoin")
    print("etait tire sur une autre seance et mesurait la derive de l indice).")
    print("Le 4b de croisements.py reste valide et dit la meme chose.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
