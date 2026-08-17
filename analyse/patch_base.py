# -*- coding: utf-8 -*-
r"""
patch_base.py -- ne pas mesurer la base entre deux echeances

  python patch_base.py

CE QU IL CORRIGE

    `contrat_continu.py` produit une serie raccordee avec une colonne
    `contrat` qui garde la provenance de chaque barre, et les prix n y
    sont VOLONTAIREMENT pas ajustes : deux echeances ne cotent pas au
    meme niveau, il y a une base entre elles.

    La colonne existait pour que l aval puisse ecarter les fenetres a
    cheval sur le raccord. `reaction_evenements.py` ne la lisait pas.

    Consequence : une fenetre de 5 seances enjambant la bascule aurait
    mesure le saut de base -- plusieurs points d indice d un coup --
    et l aurait compte comme un mouvement de marche. Sur un echantillon
    de vingt evenements, un seul suffit a deplacer la moyenne.

    Apres correction, toute fenetre dont le debut et la fin ne sont pas
    sur le MEME contrat rend None, et n entre dans aucune moyenne. Le
    nombre de fenetres ainsi ecartees est affiche : une exclusion
    silencieuse serait aussi trompeuse que l erreur qu elle corrige.

MARCHE ARRIERE

    Une copie `.bak-<horodatage>` avant modification. Ne s applique
    qu une fois.
"""
import io
import os
import sys
import datetime as dt

CIBLE = "reaction_evenements.py"
MARQUE = "_ECARTES_BASE"

# 1. lire la colonne `contrat` en meme temps que prix et delta
A1 = '''                if t and c and c > 0:
                    serie.append((t, c, d if d is not None else 0.0))'''
N1 = '''                if t and c and c > 0:
                    # 4e element : le contrat d origine, vide si la
                    # serie n est pas un raccord. Ajoute a la fin pour
                    # que serie[i][1] et serie[i][2] restent valides.
                    serie.append((t, c, d if d is not None else 0.0,
                                  (r.get("contrat") or "").strip()))'''

# 2. refuser toute fenetre a cheval sur deux echeances
A2 = '''        i1 = prix_a(serie, cible, delai, rend_index=True)
        if i1 is None or i1 <= i0:
            out[lab] = None
            out["d_" + lab] = None
            continue'''
N2 = '''        i1 = prix_a(serie, cible, delai, rend_index=True)
        if i1 is None or i1 <= i0:
            out[lab] = None
            out["d_" + lab] = None
            continue
        # Une fenetre a cheval sur DEUX echeances ne mesure pas un
        # mouvement de marche : elle mesure la base entre contrats,
        # plusieurs points d indice d un coup. Les prix du raccord ne
        # sont pas ajustes -- c est un choix -- donc c est ici qu on
        # protege la mesure.
        if len(serie[i0]) > 3 and serie[i0][3] and \\
                serie[i0][3] != serie[i1][3]:
            _ECARTES_BASE[0] += 1
            out[lab] = None
            out["d_" + lab] = None
            continue'''

# 3. le compteur, et son affichage
A3 = '''_ECHO = []'''
N3 = '''_ECHO = []

# Compte les fenetres ecartees parce qu elles enjambent un raccord de
# contrat. Une exclusion silencieuse serait aussi trompeuse que
# l erreur qu elle corrige.
_ECARTES_BASE = [0]'''

A4 = '''    dis("  Aucun p-value : il viendra par permutation par journee")'''
N4 = '''    if _ECARTES_BASE[0]:
        dis()
        dis("  %d fenetre(s) ecartee(s) parce qu elles enjambaient un"
            % _ECARTES_BASE[0])
        dis("  raccord d echeance. Les prix du raccord ne sont pas")
        dis("  ajustes : une telle fenetre aurait mesure la base entre")
        dis("  contrats et non un mouvement de marche.")
        dis()
    dis("  Aucun p-value : il viendra par permutation par journee")'''


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        return 1
    src = io.open(CIBLE, encoding="utf-8").read()
    if MARQUE in src:
        print("Deja applique. Rien n a ete modifie.")
        return 0

    for i, (a, _) in enumerate(((A1, N1), (A2, N2), (A3, N3), (A4, N4)), 1):
        if src.count(a) != 1:
            print("KO : ancre %d trouvee %d fois, une seule attendue."
                  % (i, src.count(a)))
            print("     Reprendre reaction_evenements_v2.py sur le Drive,")
            print("     puis patch_seances.py et patch_garde.py.")
            return 1

    bak = "%s.bak-%s" % (CIBLE, dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    io.open(bak, "w", encoding="utf-8").write(src)

    out = src
    for a, n in ((A1, N1), (A2, N2), (A3, N3), (A4, N4)):
        out = out.replace(a, n)
    try:
        compile(out, CIBLE, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (%s ligne %s)."
              % (e.msg, e.lineno))
        print("     Rien n a ete ecrit. La sauvegarde %s reste." % bak)
        return 1
    io.open(CIBLE, "w", encoding="utf-8").write(out)
    print("Applique.")
    print("  sauvegarde : %s" % bak)
    print("  %d lignes -> %d lignes"
          % (len(src.splitlines()), len(out.splitlines())))
    print()
    print("Marche arriere : Copy-Item %s %s -Force" % (bak, CIBLE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
