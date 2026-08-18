# -*- coding: utf-8 -*-
r"""
patch_pine.py -- Pine n evalue pas ses `and` en court-circuit

  python patch_pine.py
  puis : python pine_reperes.py --symbole MES-continu --depuis 2026-08-11

L ERREUR, SUR LE GRAPHIQUE DE L UTILISATEUR

    Erreur d execution RE10045
    Error on bar 5504: In 'array.get()' function.
    Index 150 is out of bounds, array size is 150.

LA CAUSE

    Le modele Pine contenait :

        while k < array.size(T) and array.get(T, k) < time_close

    En Python, `a and b` n evalue `b` que si `a` est vrai : la garde
    protege l acces. **Pine evalue les deux operandes**, toujours.
    `array.get(T, k)` est donc appele meme quand `k < array.size(T)`
    est faux, et le script meurt des que le pointeur atteint la fin de
    la table.

    J ai ecrit du Python en syntaxe Pine.

CE QUE CA DONNAIT

    L indicateur se charge, apparait dans la liste, et ne trace RIEN.
    Le seul signe est un petit `!` a cote de son nom. Un echec muet du
    point de vue de celui qui regarde le graphique.

LE CORRECTIF

    La borne se teste dans un `if` separe, et la boucle sort par
    `break` :

        for i = 0 to 199
            if k >= array.size(T)
                break
            ts = array.get(T, k)
            if ts >= time_close
                break
            if ts >= time
                ... tracer ...
            k += 1

    Aucune autre supposition sur Pine : pas de court-circuit, pas de
    `while` sur une condition composee.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, compile
avant de remplacer.
"""
import argparse
import io
import os
import shutil
import sys

CIBLE = "pine_reperes.py"
MARQUE = "court-circuit"

A = '''// Pointeur qui avance : la table est triee, on ne la reparcourt pas a
// chaque barre. Un balayage complet sur vingt mille barres ferait
// expirer le script.
var int k = 0

if barstate.isconfirmed and k < array.size(T)
    while k < array.size(T) and array.get(T, k) < time
        k += 1
    while k < array.size(T) and array.get(T, k) < time_close
        nd = array.get(N, k)
        if nd >= mini_dims
            c = array.get(D, k)
            if montrer_trait
                line.new(bar_index, low, bar_index, high,
                   color=color.new(color.gray, 40), width=1,
                   extend=extend.both, style=line.style_dotted)
            if montrer_haut
                line.new(bar_index, high, bar_index + 1, high,
                   color=coul_h, width=1, extend=extend.right)
            if montrer_bas
                line.new(bar_index, low, bar_index + 1, low,
                   color=coul_b, width=1, extend=extend.right)
            if montrer_texte
                label.new(bar_index, high, str.tostring(nd),
                   color=color.new(color.black, 100),
                   textcolor=coul_h, style=label.style_label_down,
                   size=size.tiny, tooltip=c)
        k += 1
'''

B = '''// Pointeur qui avance : la table est triee, on ne la reparcourt pas a
// chaque barre.
//
// ATTENTION : Pine n evalue PAS ses `and` en court-circuit. Ecrire
// `k < array.size(T) and array.get(T, k) < time` appelle array.get
// MEME quand k est hors bornes -- d ou l erreur RE10045 "Index 150 is
// out of bounds, array size is 150". La borne se teste donc dans un
// `if` separe, et la boucle sort par `break`.
var int k = 0

if barstate.isconfirmed
    for i = 0 to 199
        if k >= array.size(T)
            break
        ts = array.get(T, k)
        if ts >= time_close
            break
        if ts >= time
            nd = array.get(N, k)
            if nd >= mini_dims
                c = array.get(D, k)
                if montrer_trait
                    line.new(bar_index, low, bar_index, high,
                       color=color.new(color.gray, 40), width=1,
                       extend=extend.both, style=line.style_dotted)
                if montrer_haut
                    line.new(bar_index, high, bar_index + 1, high,
                       color=coul_h, width=1, extend=extend.right)
                if montrer_bas
                    line.new(bar_index, low, bar_index + 1, low,
                       color=coul_b, width=1, extend=extend.right)
                if montrer_texte
                    label.new(bar_index, high, str.tostring(nd),
                       color=color.new(color.black, 100),
                       textcolor=coul_h, style=label.style_label_down,
                       size=size.tiny, tooltip=c)
        k += 1
'''


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
    n = src.count(A)
    if n != 1:
        print("KO : %d occurrence(s) du bloc Pine, attendu 1." % n)
        print("Rien n a ete ecrit.")
        return 1
    print("  ancre unique.")

    out = src.replace(A, B, 1)
    try:
        compile(out, a.fichier, "exec")
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s : %s)." % (e.lineno, e.msg))
        return 1

    if a.essai:
        print("--essai : rien n a ete ecrit.")
        return 0

    sauv = a.fichier + ".avant_pine"
    if not os.path.isfile(sauv):
        shutil.copy2(a.fichier, sauv)
    io.open(a.fichier, "w", encoding="utf-8", newline="").write(out)
    print("sauvegarde : %s" % sauv)
    print("%s corrige." % a.fichier)
    print()
    print("Regenerer, puis recoller le fichier ENTIER dans le Pine")
    print("Editor -- l ancien porte encore le defaut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
