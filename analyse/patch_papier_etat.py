# -*- coding: utf-8 -*-
"""
patch_papier_etat.py -- papier_tf --etat : voir ce que churn dit, cellule par cellule

  python patch_papier_etat.py --essai
  python patch_papier_etat.py

  puis :  python papier_tf.py --etat

POURQUOI

    Le 13/08 au matin : aucune entree x10, et une seule x20 depuis le
    lancement. Trois explications tiennent, et le journal ne permet pas
    de les departager :

      a) le signal ne se declenche pas sur ces unites -- resultat
      b) MetaTrader n a pas assez de barres M10/M20, parce que ces
         unites ne sont jamais ouvertes dans un graphique et que le
         terminal les construit paresseusement -- panne silencieuse
      c) _analyze leve sur ces barres -- panne silencieuse aussi

    Et c est le point noir de papier_tf : cellule() attrape TOUTE
    exception et rend None. Une cellule cassee est indiscernable d une
    cellule calme. Elle le restera pour toujours, sans une ligne de
    journal.

CE QUE --etat AFFICHE

    Les 36 cellules, avec pour chacune : le nombre de barres que
    MetaTrader rend vraiment, l ignition et sa direction, ou bien le
    type et le message de l exception -- NON rattrapee, affichee.

    Plus un resume : combien de cellules sont exploitables, et
    lesquelles ne le sont pas et pourquoi.

    C est une photo, pas un journal. Deux appels a dix minutes
    d intervalle disent si une cellule est calme ou morte.

LECTURE SEULE, comme le reste du module. Aucun ordre, aucun etat
modifie, aucun fichier ecrit.

TROIS ANCRES, verifiees uniques avant la moindre ecriture.
IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "papier_tf.py"
MARQUEUR = "def etat("

RE_RAPPORT = re.compile(r'^def rapport\(\):$', re.M)

RE_ARG = re.compile(
    r'^([ \t]*)p\.add_argument\("--rapport", action="store_true"\)$', re.M)

RE_DISPATCH = re.compile(
    r'^([ \t]*)if a\.loop:\n([ \t]*)return boucle\(a\.pas\)$', re.M)

ETAT = '''def etat():
    """Ce que churn dit de chaque cellule, MAINTENANT, sans rien filtrer.

    cellule() attrape toute exception et rend None : une cellule dont
    _analyze refuse les barres est donc indiscernable d une cellule
    calme, et le reste pour toujours. Ici on ne rattrape rien, on
    AFFICHE -- c est tout l interet de la commande."""
    if mt5 is None or _chr is None:
        print("KO : --etat a besoin de MetaTrader5 et de churn_regime.")
        return 1
    if not mt5.initialize():
        print("KO : mt5.initialize() a echoue -- %s" % (mt5.last_error(),))
        return 1

    print("=" * LARG)
    print("  ETAT DES CELLULES -- %s" % maintenant().replace("T", " "))
    print("=" * LARG)
    print("%-10s %-6s %-7s %8s %10s %-6s  %s"
          % ("cellule", "duree", "actif", "barres", "ignition", "dir",
             "remarque"))
    print("-" * LARG)

    vivantes, muettes = 0, []
    for actif, code, sym in ACTIFS:
        for mn in DUREES:
            tf = tf_mt5(mn)
            k = cle("206", code, mn)
            if tf is None:
                print("%-10s %-6s %-7s %8s %10s %-6s  %s"
                      % (k, libelle(mn), actif, "-", "-", "-",
                         "unite absente de ce MetaTrader5"))
                muettes.append((k, "unite inconnue du terminal"))
                continue
            bars = mt5.copy_rates_from_pos(sym, tf, 0, BARRES)
            nb = 0 if bars is None else len(bars)
            if nb < 40:
                # 40 = le minimum que cellule() exige. En dessous elle
                # rend None sans un mot, et la cellule ne tradera jamais.
                note = ("MetaTrader ne rend que %d barres -- il construit"
                        " les unites rares seulement quand on les ouvre"
                        " dans un graphique" % nb)
                print("%-10s %-6s %-7s %8d %10s %-6s  %s"
                      % (k, libelle(mn), actif, nb, "-", "-", note))
                muettes.append((k, "%d barres, il en faut 40" % nb))
                continue
            try:
                cel = _chr._analyze(bars)
            except Exception as e:
                note = "_analyze LEVE : %s: %s" % (type(e).__name__, e)
                print("%-10s %-6s %-7s %8d %10s %-6s  %s"
                      % (k, libelle(mn), actif, nb, "-", "-", note[:44]))
                muettes.append((k, note))
                continue
            if cel is None:
                print("%-10s %-6s %-7s %8d %10s %-6s  %s"
                      % (k, libelle(mn), actif, nb, "-", "-",
                         "_analyze rend None"))
                muettes.append((k, "_analyze rend None"))
                continue
            vivantes += 1
            print("%-10s %-6s %-7s %8d %10s %-6s  %s"
                  % (k, libelle(mn), actif, nb,
                     "OUI" if cel.get("ignition") else "non",
                     cel.get("dir") or "-", ""))
    print("-" * LARG)
    total = len(ACTIFS) * len(DUREES)
    print("  %d cellules exploitables sur %d." % (vivantes, total))
    if muettes:
        print()
        print("  CELLULES MUETTES -- elles ne tradront JAMAIS en l etat :")
        for k, r in muettes:
            print("    %-10s %s" % (k, r))
        print()
        print("  Si la cause est le nombre de barres : ouvre une fois")
        print("  l unite dans un graphique MetaTrader sur cet actif, le")
        print("  terminal construira la serie et la gardera.")
    print()
    print("  Une photo, pas un journal. Deux appels a dix minutes")
    print("  d intervalle disent si une cellule est CALME ou MORTE :")
    print("  calme, elle affiche des barres et une direction qui bouge ;")
    print("  morte, elle affiche la meme remarque.")
    print()
    print("  Le bras 207 partage exactement les memes cellules -- memes")
    print("  entrees, seule la sortie change. Il n est pas repete ici.")
    mt5.shutdown()
    return 0


'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    for nom, rx in (("def rapport()", RE_RAPPORT),
                    ("l argument --rapport", RE_ARG),
                    ("l aiguillage de main()", RE_DISPATCH)):
        n = len(rx.findall(src))
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1

    m = RE_RAPPORT.search(src)
    neuf = src[:m.start()] + ETAT + src[m.start():]

    neuf = RE_ARG.sub(
        lambda mo: (mo.group(0) + "\n" + mo.group(1)
                    + 'p.add_argument("--etat", action="store_true")'),
        neuf, count=1)

    neuf = RE_DISPATCH.sub(
        lambda mo: (mo.group(1) + "if a.etat:\n"
                    + mo.group(2) + "return etat()\n"
                    + mo.group(1) + "if a.loop:\n"
                    + mo.group(2) + "return boucle(a.pas)"),
        neuf, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("papier_tf.py --etat affichera les 36 cellules avec, pour")
    print("chacune, le nombre de barres rendues par MetaTrader, l ignition")
    print("et sa direction -- ou l exception, NON rattrapee.")
    print()
    print("C est ce que cellule() cache aujourd hui : elle attrape tout et")
    print("rend None, donc une cellule cassee ressemble a une cellule")
    print("calme, pour toujours.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. --etat est disponible tout de suite ; l observateur")
    print("qui tourne n a PAS besoin d etre redemarre.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
