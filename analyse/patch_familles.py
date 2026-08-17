# -*- coding: utf-8 -*-
r"""
patch_familles.py -- deux corrections a ecart_carnets.py

  python patch_familles.py

1. LE `-` QUI MENT

    Sortie reelle du 17/08 :

        2026-03-23   -87.9   publications HIGH : -
        2026-03-24   -65.3   publications HIGH : -
        2026-04-13   -64.7   publications HIGH : -

    Le calendrier commence au 1er juin. Ces trois journees sont HORS
    de sa couverture : il ne s est rien passe DANS LE FICHIER, pas dans
    le marche. Le tiret laisse croire l inverse, et il invite a lire
    "des ecarts extremes arrivent sans publication" alors que la
    donnee n existe pas.

    C est la regle ecrite ce matin dans PROTOCOLE.md -- absence de
    donnee n est pas donnee d absence -- qui revient six heures plus
    tard dans un fichier ecrit apres elle.

    Correctif : la plage du calendrier est affichee, et les journees
    qui en sortent portent `hors calendrier` au lieu de `-`.

2. LE MOTIF LAISSE A L OEIL

    Les journees nommees sont listees a plat, dans l ordre des dates.
    Il a fallu que l utilisateur les lise une par une pour voir que
    les trois CPI etaient negatifs et les trois NFP positifs.

        CPI      rangs   5,  23,  33   sur 110
        NFP      rangs 107,  62,  77
        Fed      rangs  74, 105
        Philly   rangs  96,  80

    Un tableau doit montrer ce qu il contient. Correctif : les
    journees sont REGROUPEES PAR FAMILLE d evenement, avec le rang
    median de chaque famille et le compte de journees du meme cote de
    la mediane.

    La famille est reconnue par le motif qui l a fait retenir -- pas
    par une classification inventee. Si un jour porte deux motifs, il
    compte dans le premier, et c est dit.

CE QUE CA NE FAIT PAS

    Aucun test. Trois occurrences par famille ne feront jamais un
    echantillon, et le tableau le repete. Ce que ca donne, c est un
    motif ASSEZ NET POUR ETRE PRE-ENREGISTRE, avec le sens attendu et
    la date de verification -- ce qui est la seule facon honnete de
    traiter une piste trouvee en regardant les donnees.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import io
import os
import shutil
import sys

CIBLE = "ecart_carnets.py"
MARQUE = "familles"

# ---------------------------------------------------------------- 1
A1 = '''            for d, v in ordre[:a.extremes]:
                evs = cal.get(d, [])
                dis("  %-12s %+8.1f %10.1f %10.1f   %s"
                    % (d, v, cent[sb][d], cent[sa][d],
                       ", ".join(e[:28] for e in evs[:2]) or "-"))
'''
B1 = '''            # UN TIRET NE VEUT PAS DIRE "AUCUNE PUBLICATION".
            #
            # Hors de la plage couverte par le calendrier, l absence
            # d evenement n est pas mesuree : elle est inconnue. Le
            # tiret invitait a lire "des ecarts extremes arrivent sans
            # publication" sur des journees ou le fichier ne dit rien.
            if cal:
                cd, cf = min(cal), max(cal)
            else:
                cd = cf = None
            for d, v in ordre[:a.extremes]:
                evs = cal.get(d, [])
                if evs:
                    quoi = ", ".join(e[:28] for e in evs[:2])
                elif cd and cd <= d <= cf:
                    quoi = "aucune"
                else:
                    quoi = "HORS CALENDRIER"
                dis("  %-12s %+8.1f %10.1f %10.1f   %s"
                    % (d, v, cent[sb][d], cent[sa][d], quoi))
            if cd:
                dis()
                dis("  Calendrier couvert : du %s au %s. `HORS"
                    % (cd, cf))
                dis("  CALENDRIER` ne veut pas dire `aucune publication`,")
                dis("  mais `on ne sait pas` -- et ces journees ne")
                dis("  peuvent servir ni d exemple ni de contre-exemple.")
'''

# ---------------------------------------------------------------- 2
A2 = '''            dis()
            dis("  `rang 1` = la seance ou %s est le plus vendu" % sb)
            dis("  relativement a %s. Un rang au milieu = journee" % sa)
            dis("  ordinaire pour l ecart entre les deux carnets.")
'''
B2 = '''            dis()
            dis("  `rang 1` = la seance ou %s est le plus vendu" % sb)
            dis("  relativement a %s. Un rang au milieu = journee" % sa)
            dis("  ordinaire pour l ecart entre les deux carnets.")

            # PAR FAMILLE D EVENEMENT.
            #
            # Une liste a plat dans l ordre des dates cache le motif :
            # il a fallu lire les quatorze lignes une par une pour voir
            # que les CPI etaient tous d un cote et les NFP tous de
            # l autre. Un tableau doit montrer ce qu il contient.
            #
            # La famille est le MOTIF qui a fait retenir la journee --
            # pas une classification inventee ici.
            familles = {}
            for d, e in sorted(vises):
                for m in motifs:
                    if m in e.lower():
                        familles.setdefault(m, []).append((d, e))
                        break
            if len(familles) > 1:
                milieu = (len(vals) + 1) / 2.0
                dis()
                dis("  PAR FAMILLE -- ce que la liste a plat cachait")
                dis("  %-14s %6s %12s %15s  %s"
                    % ("famille", "n", "rang median", "meme cote",
                       "rangs"))
                for m in sorted(familles, key=lambda k: -len(familles[k])):
                    g = familles[m]
                    rg = sorted(sum(1 for x in vals if x < ec[d]) + 1
                                for d, _ in g)
                    med = mediane([float(r) for r in rg])
                    bas = sum(1 for r in rg if r < milieu)
                    cote = "%d bas / %d haut" % (bas, len(rg) - bas)
                    dis("  %-14s %6d %12.0f %15s  %s"
                        % (m[:14], len(g), med, cote,
                           ", ".join(str(r) for r in rg)))
                dis()
                dis("  Une famille dont TOUS les rangs sont du meme cote")
                dis("  de %.0f est une piste. Avec trois occurrences, la"
                    % milieu)
                dis("  probabilite que ca arrive par hasard est de un sur")
                dis("  huit -- donc ni negligeable, ni concluant. C est")
                dis("  exactement ce qui se pre-enregistre et se verifie")
                dis("  hors echantillon, jamais ce qui se conclut ici.")
                dis()
                dis("  Une journee portant deux motifs est comptee dans")
                dis("  le premier de la liste --motif. L ordre de cette")
                dis("  liste change donc le tableau : le fixer une fois")
                dis("  et ne plus y toucher.")
'''

REMPLACEMENTS = [
    ("marquage hors calendrier dans la table des extremes", A1, B1),
    ("regroupement par famille d evenement", A2, B2),
]


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        return 1
    src = io.open(CIBLE, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique. Rien n a ete touche.")
        return 0

    manque = []
    for nom, a, _ in REMPLACEMENTS:
        n = src.count(a)
        if n != 1:
            manque.append((nom, n))
    if manque:
        print("KO : ancres introuvables ou ambigues, rien n a ete ecrit.")
        for nom, n in manque:
            print("  %-46s %d occurrence(s), attendu 1" % (nom, n))
        return 1

    out = src
    for nom, a, b in REMPLACEMENTS:
        out = out.replace(a, b, 1)

    try:
        compile(out, CIBLE, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (ligne %s : %s)."
              % (e.lineno, e.msg))
        print("Rien n a ete ecrit. L original est intact.")
        return 1

    sauv = CIBLE + ".avant_familles"
    if not os.path.isfile(sauv):
        shutil.copy2(CIBLE, sauv)
    io.open(CIBLE, "w", encoding="utf-8", newline="").write(out)

    print("%s : %d lignes -> %d lignes, %d remplacements."
          % (CIBLE, len(src.splitlines()), len(out.splitlines()),
             len(REMPLACEMENTS)))
    print("sauvegarde : %s" % sauv)
    print()
    print("A LIRE DANS LA NOUVELLE SORTIE :")
    print("  - les journees de mars et avril doivent afficher HORS")
    print("    CALENDRIER et non un tiret ;")
    print("  - le tableau PAR FAMILLE doit montrer cpi tout en bas et")
    print("    nonfarm tout en haut. Si ce n est pas le cas, c est que")
    print("    je l ai lu de travers dans la liste a plat.")
    print()
    print("Relancer : python ecart_carnets.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
