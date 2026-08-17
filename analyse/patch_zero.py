# -*- coding: utf-8 -*-
r"""
patch_zero.py -- une serie qui traverse zero n a pas de rendement en
pourcent, et perdait la moitie de ses journees en silence

  python patch_zero.py

LE DEFAUT, TROUVE PAR UN FIL TENDU CE MATIN

    Les deux outils ne comptaient pas les memes seances pour le meme
    symbole :

        ecart_fenetre.py      TICK-NYSE   138 seances   z = 11.7
        flux_contre_prix.py   TICK-NYSE    67 seances   z =  8.2

    MES et YM, eux, sont identiques au chiffre pres des deux cotes --
    133 / -0,4 et 112 / +1,9. Le probleme ne touche que TICK.

    La cause : `seances()` calcule un rendement en pourcent,
    (derniere - premiere) / premiere, et ecarte toute journee dont la
    premiere cloture est <= 0 :

        if a[4] < seuil or len(a[5]) > 1 or a[0] <= 0:
            continue

    Le TICK oscille autour de zero. Environ une seance sur deux
    commence en negatif, et disparait SANS UN MOT.

    C est la troisieme fois de la journee que le pourcentage applique a
    un oscillateur produit une faute. Les deux premieres se voyaient --
    des rendements a -94 % et +63 %. Celle-ci ne se voit pas : elle
    ampute l effectif au lieu de fabriquer un chiffre absurde, ce qui
    est pire.

CE QUE CA NE CHANGE PAS

    Aucun resultat. TICK est ecarte par le test de signe dans les deux
    outils, quel que soit son decompte de seances. Les conclusions sur
    MES et YM sont intactes.

LE CORRECTIF

    Une serie dont le prix traverse zero est ecartee EXPLICITEMENT, en
    tete de traitement, avec la raison affichee -- avant qu un filtre
    de journee ne le fasse a moitie et en silence.

    Le test est le meme que dans `bougie_deux_actifs.py` et
    `reaction_evenements.py` : `min(cloture) > 0`. Le pourcentage
    suppose une echelle ; un compteur signe n en a pas.

LA REGLE, CONFIRMEE UNE TROISIEME FOIS

    Un filtre ecrit pour une condition -- ici "prix valide" -- devient
    un filtre destructeur sur une serie d une autre nature. Ce qui
    sauve, ce n est pas d y penser : c est d afficher ce qu on ecarte
    et de comparer les effectifs entre outils.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import io
import os
import shutil
import sys

CIBLE = "flux_contre_prix.py"
MARQUE = "traversent"

A1 = '''    sc, exclus = {}, []
'''
B1 = '''    # UNE SERIE QUI TRAVERSE ZERO N A PAS DE RENDEMENT EN POURCENT.
    #
    # `seances()` ecarte les journees dont la premiere cloture est
    # <= 0, parce qu il divise par elle. Sur un oscillateur comme
    # TICK-NYSE, c est une seance sur deux qui disparait -- sans un
    # mot, et en biaisant ce qui reste vers les journees commencant en
    # positif. Le decompte tombait a 67 seances contre 138 dans
    # ecart_fenetre.py, pour le meme fichier.
    #
    # On l ecarte donc EXPLICITEMENT et en entier, avant qu un filtre
    # de journee ne le fasse a moitie. Meme test que partout ailleurs :
    # le pourcentage suppose une echelle, un compteur signe n en a pas.
    traversent = [s for s, v in barres.items()
                  if min(x[1] for x in v) <= 0]
    for s in traversent:
        del barres[s]
    if traversent:
        dis()
        dis("  ECARTE(S) -- la serie traverse zero : %s"
            % ", ".join(sorted(traversent)))
        dis("  Un rendement en pourcent divise par la premiere cloture")
        dis("  du jour. Sur une serie qui passe en negatif, une seance")
        dis("  sur deux serait supprimee en silence, et ce qui resterait")
        dis("  serait biaise vers les journees commencant en positif.")
    if len(barres) < 2:
        print("KO : moins de deux symboles a echelle de prix.")
        return 1

    sc, exclus = {}, []
'''

REMPLACEMENTS = [
    ("exclusion explicite des series traversant zero", A1, B1),
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

    sauv = CIBLE + ".avant_zero"
    if not os.path.isfile(sauv):
        shutil.copy2(CIBLE, sauv)
    io.open(CIBLE, "w", encoding="utf-8", newline="").write(out)

    print("%s : %d lignes -> %d lignes, %d remplacement."
          % (CIBLE, len(src.splitlines()), len(out.splitlines()),
             len(REMPLACEMENTS)))
    print("sauvegarde : %s" % sauv)
    print()
    print("TICK-NYSE sera desormais ecarte AU DEBUT, avec la raison,")
    print("au lieu de perdre la moitie de ses journees en silence.")
    print("MES et YM ne bougent pas : 133 et 112 seances, rho 0,569 et")
    print("0,015. Si ces quatre nombres changent, c est que le patch a")
    print("touche autre chose que prevu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
