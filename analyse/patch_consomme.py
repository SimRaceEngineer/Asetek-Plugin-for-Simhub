# -*- coding: utf-8 -*-
r"""
patch_consomme.py -- un niveau traverse cesse d etre trace

  python patch_consomme.py
  puis : python pine_reperes.py --symbole MES-continu --depuis 2026-08-11

LE DEFAUT, VU SUR L ECRAN

    150 reperes x 2 rayons prolonges jusqu au bord droit = 300 lignes
    horizontales qui traversent tout le graphique. Illisible.

    La cause n est pas cosmetique. **Un niveau que le prix a traverse
    n est plus un niveau : il est CONSOMME.** Continuer a le tracer,
    c est afficher des centaines de lignes deja invalidees.

CE QUE FAIT LE CORRECTIF

    Chaque rayon est garde dans un tableau avec son prix. A chaque
    barre, avant d en ouvrir de nouveaux, on ferme ceux que la bougie
    traverse :

        line.set_x2(ln, bar_index)      le rayon s arrete ici
        line.set_extend(ln, extend.none)

    L ecran ne montre plus que les niveaux ENCORE VALIDES.

CE QUE CA APPORTE, ET CE N EST PAS DE LA MISE EN FORME

    **La longueur du rayon devient la duree de survie du niveau.**

    Un niveau qui tient trois jours saute aux yeux ; un niveau traverse
    dans la minute disparait presque aussitot. C est exactement la
    grandeur qu il faudra mesurer contre un temoin -- un niveau
    ordinaire tire a la meme minute de seance et a la meme distance du
    prix.

    Le trace qui rend le graphique lisible est donc aussi celui qui
    produit le chiffre. On regarde d abord, on mesure ensuite.

CE QUE J AI EVITE, APRES LA FAUTE DE CE MATIN

    Pine n evalue pas ses `and` en court-circuit -- c est ce qui a
    produit le RE10045. Ce correctif n en pose aucun sur un acces
    tableau :

      - `touche = low <= lv` puis `if touche / touche := high >= lv` ;
      - boucles bornees, jamais un `while` sur condition composee ;
      - parcours DESCENDANT pour retirer sans decaler ce qui reste ;
      - plafond propre de 180 lignes actives, parce que Pine supprime
        lui-meme la plus ancienne au-dela de `max_lines_count` et
        laisserait une reference morte dans le tableau.

    JE N AI PAS DE PINE ICI et je ne peux pas l executer. Les
    suppositions sur le langage sont donc reduites au minimum, mais
    elles ne sont pas nulles. Si TradingView refuse, envoyez-moi le
    message : c est plus rapide que de deviner.

EXIGE patch_pine.py, applique avant. Sauvegarde, refuse de s appliquer
deux fois, compile avant de remplacer.
"""
import argparse
import io
import os
import shutil
import sys

CIBLE = "pine_reperes.py"
MARQUE = "CONSOMME"

A1 = '''var int[]    T = array.new_int()
var int[]    N = array.new_int()
var string[] D = array.new_string()
'''
B1 = '''var int[]    T = array.new_int()
var int[]    N = array.new_int()
var string[] D = array.new_string()

// Niveaux ENCORE VALIDES. Un rayon qui continue apres que le prix l a
// traverse n est plus un niveau : il est CONSOMME. Les garder tous
// saturait l ecran de centaines de lignes deja invalidees.
var line[]   L = array.new_line()
var float[]  V = array.new_float()
'''

A2 = '''if barstate.isconfirmed
    for i = 0 to 199
        if k >= array.size(T)
            break
'''
B2 = '''// FERMETURE DES NIVEAUX TRAVERSES, avant d en ouvrir de nouveaux.
// On parcourt a l envers pour pouvoir retirer sans decaler ce qui
// reste. Pas de `and` sur un acces tableau -- Pine n a pas de
// court-circuit.
if barstate.isconfirmed
    if array.size(L) > 0
        for i = array.size(L) - 1 to 0
            lv = array.get(V, i)
            touche = low <= lv
            if touche
                touche := high >= lv
            if touche
                ln = array.get(L, i)
                line.set_x2(ln, bar_index)
                line.set_extend(ln, extend.none)
                array.remove(L, i)
                array.remove(V, i)

    // Plafond de securite : Pine supprime lui-meme la ligne la plus
    // ancienne au-dela de max_lines_count, ce qui laisserait une
    // reference morte dans L. On borne donc nous-memes.
    if array.size(L) > 180
        for i = 0 to 19
            if array.size(L) == 0
                break
            line.delete(array.shift(L))
            array.shift(V)

if barstate.isconfirmed
    for i = 0 to 199
        if k >= array.size(T)
            break
'''

A3 = '''                if montrer_haut
                    line.new(bar_index, high, bar_index + 1, high,
                       color=coul_h, width=1, extend=extend.right)
                if montrer_bas
                    line.new(bar_index, low, bar_index + 1, low,
                       color=coul_b, width=1, extend=extend.right)
'''
B3 = '''                if montrer_haut
                    lh = line.new(bar_index, high, bar_index + 1, high,
                       color=coul_h, width=1, extend=extend.right)
                    array.push(L, lh)
                    array.push(V, high)
                if montrer_bas
                    lb = line.new(bar_index, low, bar_index + 1, low,
                       color=coul_b, width=1, extend=extend.right)
                    array.push(L, lb)
                    array.push(V, low)
'''

REMPLACEMENTS = [
    ("tableaux des niveaux actifs", A1, B1),
    ("fermeture des niveaux traverses", A2, B2),
    ("memorisation des rayons crees", A3, B3),
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

    if MARQUE in src:
        print("Deja applique. Rien n a ete touche.")
        return 0
    if "court-circuit" not in src:
        print("KO : patch_pine.py n a pas ete applique.")
        print("     Lancer d abord : python patch_pine.py")
        return 1

    manque = []
    for nom, av, _ in REMPLACEMENTS:
        n = src.count(av)
        if n != 1:
            manque.append((nom, n))
    if manque:
        print("KO : ancres introuvables ou ambigues, rien n a ete ecrit.")
        for nom, n in manque:
            print("  %-36s %d occurrence(s), attendu 1" % (nom, n))
        return 1
    print("  les %d ancres sont uniques." % len(REMPLACEMENTS))

    out = src
    for nom, av, ap in REMPLACEMENTS:
        out = out.replace(av, ap, 1)
    try:
        compile(out, a.fichier, "exec")
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s : %s)." % (e.lineno, e.msg))
        return 1

    if a.essai:
        print("--essai : rien n a ete ecrit.")
        return 0

    sauv = a.fichier + ".avant_consomme"
    if not os.path.isfile(sauv):
        shutil.copy2(a.fichier, sauv)
    io.open(a.fichier, "w", encoding="utf-8", newline="").write(out)
    print("sauvegarde : %s" % sauv)
    print("%s corrige." % a.fichier)
    print()
    print("Regenerer, puis TOUT REMPLACER dans le Pine Editor.")
    print()
    print("A REGARDER : la LONGUEUR des rayons. C est la duree de survie")
    print("du niveau, et c est la grandeur qu on mesurera ensuite contre")
    print("un temoin. Un ecran qui ne montre plus que quelques lignes est")
    print("le signe que le correctif marche, pas qu il a mange les")
    print("donnees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
