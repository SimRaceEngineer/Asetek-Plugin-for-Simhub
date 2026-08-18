# -*- coding: utf-8 -*-
r"""
patch_rendement.py -- la colonne qui mesure H33 : le RENDEMENT du flux

  python patch_rendement.py --essai
  python patch_rendement.py
  puis : python refus_continuation.py

CE QU IL AJOUTE, ET POURQUOI

    H33 est pre-enregistree depuis le 18/08, AVANT toute mesure. Elle
    dit que ce qui annonce un refus n est pas le SIGNE du flux mais son
    RENDEMENT -- ce que le prix rend pour ce que le flux pousse.

    Elle est nee de la bougie du 14/08 a 16h30 :

        16:04   +809 contrats   27,9 x median   prix +1,75
        16:05  +1047 contrats   36,1 x median   prix +3,75
        16:06   +187 contrats                   prix +3,00

    +2 136 contrats nets a l achat, a trente-six fois le delta median
    du jour, pour trois points et demi -- puis vingt-deux points rendus.

    La colonne APPROCHE ne peut pas voir ca : c est une SOMME de delta
    sur soixante minutes, et l achat de 16:04 s y annule avec la vente
    qui suit. Elle sort a p 0,77 et 0,48 non pas parce qu il n y a rien,
    mais parce que ce n est pas cette variable-la.

LA MESURE, TELLE QUE H33 LA GELE -- rien n est rechoisi ici

    Dans la fenetre d approche [t-W, t[, on prend LA MINUTE AU PLUS
    FORT |delta|. Pas une somme, pas une moyenne : l extreme, qui est
    l endroit ou l absorption se voit.

        d = |delta| de cette minute  / mediane |delta| du jour
        p = |dprix| de cette minute  / mediane |dprix| du jour
        RENDEMENT = p / d

    Sur 16:05 : d = 36,1, p = 8,0, rendement 0,22. Une minute
    ordinaire vaut environ 1.

    Les deux medianes sont celles de la journee et de l actif. `u` --
    la mediane des |dprix| -- est deja calculee par l outil, c est le
    tampon. La mediane des |delta| est ajoutee a cote.

CE QUE LE PATCH NE CHANGE PAS

    Ni la definition de l evenement, ni W, ni H, ni k, ni la
    permutation, ni les exclusions. MES doit garder 497 tentatives et
    YM 486. Si ces deux nombres bougent, le patch a touche autre chose
    que prevu et il faut restaurer.

CE QUE LA SORTIE DIRA, ET COMMENT LA LIRE

    Le verdict traitera RENDEMENT comme APPROCHE : une variable
    mesuree AVANT que l issue se joue, donc non circulaire.

    Mais H33 porte sa reserve, et le patch l imprime : c est la
    TROISIEME variable testee sur les memes 827 evenements. Trois
    variables a 5 %, c est ~14 % de chance qu au moins une passe sous
    H0. Un p < 0,05 vaudra "a confirmer", pas "trouve", et la
    confirmation exigee est une periode disjointe.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import argparse
import io
import os
import shutil
import sys

CIBLE = "refus_continuation.py"
MARQUE = "rendement"

A1 = '''    vmed = med([b[3] for b in barres]) or 0.0
'''
B1 = '''    vmed = med([b[3] for b in barres]) or 0.0
    # H33 : le rendement du flux. `u` est deja la mediane des |dprix|,
    # il manquait celle des |delta| et le |dprix| minute par minute.
    md = med([abs(b[2]) for b in barres]) or 0.0
    dpx = {}
    for i in range(1, len(barres)):
        dpx[barres[i][0]] = abs(barres[i][1] - barres[i - 1][1])
'''

A2 = '''            "amplitude": (fin - niveau) / u,
        })
'''
B2 = '''            "amplitude": (fin - niveau) / u,
            "rendement": rendement(av, dpx, u, md),
        })
'''

A3 = '''def _min(n):
'''
B3 = '''def rendement(av, dpx, u, md):
    """Ce que le prix rend pour ce que le flux pousse, sur la minute la
    plus poussee de la fenetre d approche.

    L extreme et non la somme : une somme de delta sur soixante minutes
    annule un achat absorbe avec la vente qui le suit, et c est
    exactement ce qu on cherche a voir.

    Rend None quand la fenetre ne pousse pas du tout (delta nul
    partout) : diviser par zero n est pas un rendement, et mettre 0 ou
    1 a la place ferait passer une absence de mesure pour une mesure."""
    if not av or md <= 0 or u <= 0:
        return None
    b = max(av, key=lambda x: abs(x[2]))
    d = abs(b[2]) / md
    if d <= 0:
        return None
    return (dpx.get(b[0], 0.0) / u) / d


def _min(n):
'''

A4 = '''        if e["issue"] in ("REFUS", "CONTINUATION"):
            jours.setdefault(e["jour"], []).append((e["issue"], e[champ]))
'''
B4 = '''        if e["issue"] in ("REFUS", "CONTINUATION") \\
                and e.get(champ) is not None:
            jours.setdefault(e["jour"], []).append((e["issue"], e[champ]))
'''

A5 = '''        for champ, nom in (("approche", "APPROCHE"),
                           ("decision", "DECISION"),
                           ("vol", "VOLUME")):
'''
B5 = '''        for champ, nom in (("approche", "APPROCHE"),
                           ("rendement", "RENDEMENT"),
                           ("decision", "DECISION"),
                           ("vol", "VOLUME")):
'''

A6 = '''                dis("    %-12s %12.1f %10.4f %10d" % (nom, e, pv, nj))
'''
B6 = '''                dis("    %-12s %12.4g %10.4f %10d" % (nom, e, pv, nj))
'''

A7 = '''    dis("  Seules APPROCHE et VOLUME ne redisent pas l issue.")
'''
B7 = '''    dis("  APPROCHE, RENDEMENT et VOLUME ne redisent pas l issue.")
    dis()
    dis("  RENDEMENT (H33) : sur la minute au plus fort delta de la")
    dis("  fenetre d approche, ce que le prix rend pour ce que le flux")
    dis("  pousse. Une minute ordinaire vaut ~1 ; une absorption vaut")
    dis("  nettement moins. Mesuree AVANT que l issue se joue.")
    dis()
    dis("  RESERVE DE H33, ecrite avant la mesure : c est la TROISIEME")
    dis("  variable testee sur les memes evenements. Trois variables a")
    dis("  5 %, c est ~14 % de chance qu une passe sous H0. Un p < 0,05")
    dis("  vaut ICI `a confirmer sur periode disjointe`, pas `trouve`.")
'''

A8 = '''        ea, pa = r["approche"]
        ev, pv = r["vol"]
'''
B8 = '''        ea, pa = r["approche"]
        ev, pv = r["vol"]
        er, pr = r.get("rendement", (None, None))
        if er is not None and pr is not None and pr < 0.05:
            dis("  %-16s RENDEMENT : ecart %+.3f, p = %.4f." % (sym, er, pr))
            dis("  %-16s Les refus sont precedes d un flux qui rend" % "")
            dis("  %-16s MOINS -- signature d absorption, mesuree AVANT." % "")
            dis("  %-16s H33 passe ce tour. A CONFIRMER sur une periode" % "")
            dis("  %-16s disjointe : c est la troisieme variable testee" % "")
            dis("  %-16s sur ces memes evenements." % "")
        elif er is not None:
            dis("  %-16s RENDEMENT : ecart %+.3f, p = %.4f -- rien."
                % (sym, er, pr if pr is not None else 1.0))
'''

REMPLACEMENTS = [
    ("medianes du delta et des dprix", A1, B1),
    ("colonne rendement dans l evenement", A2, B2),
    ("fonction rendement()", A3, B3),
    ("exclusion des valeurs manquantes", A4, B4),
    ("rendement dans la boucle de test", A5, B5),
    ("format lisible pour les petits nombres", A6, B6),
    ("annonce de la colonne", A7, B7),
    ("lecture du rendement", A8, B8),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable." % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8").read()

    if "ecarte_sans_carnet" not in src:
        print("KO : patch_refus.py n a pas ete applique.")
        print("     Lancer d abord : python patch_refus.py")
        return 1
    if MARQUE in src:
        print("Deja applique. Rien n a ete touche.")
        return 0

    manque = []
    for nom, av, _ in REMPLACEMENTS:
        n = src.count(av)
        if n != 1:
            manque.append((nom, n))
    if manque:
        print("KO : ancres introuvables ou ambigues, rien n a ete ecrit.")
        for nom, n in manque:
            print("  %-40s %d occurrence(s), attendu 1" % (nom, n))
        return 1
    print("  les %d ancres sont uniques." % len(REMPLACEMENTS))

    out = src
    for nom, av, ap in REMPLACEMENTS:
        out = out.replace(av, ap, 1)

    try:
        compile(out, a.fichier, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (ligne %s : %s)."
              % (e.lineno, e.msg))
        print("Rien n a ete ecrit. L original est intact.")
        return 1

    print()
    print("Apres patch : une colonne RENDEMENT, mesuree sur la minute")
    print("au plus fort delta de la fenetre d approche, avec les")
    print("parametres geles par H33 le 18/08 avant toute mesure.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauv = a.fichier + ".avant_rendement"
    if not os.path.isfile(sauv):
        shutil.copy2(a.fichier, sauv)
    io.open(a.fichier, "w", encoding="utf-8", newline="").write(out)

    print()
    print("sauvegarde : %s" % sauv)
    print("%s : %d -> %d lignes."
          % (a.fichier, len(src.splitlines()), len(out.splitlines())))
    print()
    print("A VERIFIER SUR LA PROCHAINE SORTIE :")
    print("  MES-continu doit garder 497 tentatives, YM-continu 486.")
    print("  Le patch n ajoute qu une colonne : la definition de l")
    print("  evenement ne change pas d un iota.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
