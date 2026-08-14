# -*- coding: utf-8 -*-
"""
patch_section7_cassure.py -- couper la section 7 (H10) au 5 aout

  python patch_section7_cassure.py --essai
  python patch_section7_cassure.py
  python patch_section7_cassure.py --annuler

LE MEME DEFAUT QUE LA SECTION 9, UNE SECTION PLUS LOIN

    Le chapeau de la section 7 annonce :

        "porteur M10-M30 +13,89 EUR/tk contre -15,09 sous porteur H1"

    Sa propre table, colonne x60, affiche :

        -2,72   +3,09   -1,05   -5,04

    Aucune de ces valeurs n approche -15,09. Ce n est pas une
    incoherence de calcul : ce sont DEUX FENETRES. Le chapeau cite une
    mesure post-05/08 ; la table agrege tout depuis le 21/07.

    Le REPL a lu cette section sans voir le probleme -- justement
    parce que le chapeau lui fournissait un chiffre plausible. Un
    tableau dont le titre parle d une autre periode que ses cellules
    est pire qu un tableau absent : il se lit sans effort et il ment.

    Et c est la section qui porte H10, la seule question ouverte que
    le gel doit trancher. La laisser ainsi, c est garantir qu on
    relira le mauvais nombre pendant quinze jours.

CE QUE FAIT LE PATCH

    Un tableau devient DEUX, avant et depuis la cassure. Memes lignes
    (x01/x02/x03/x05 qui entrent), memes colonnes (x10/x20/x30/x60 qui
    ont ouvert l episode), memes marqueurs.

    LE DECOUPAGE SE FAIT SUR LA DATE DE DEBUT DE L EPISODE, pas sur
    celle de chaque petit ticket. C est un CHOIX, et il est dit dans
    le chapeau : un episode reste entier du cote ou il a commence.
    Decouper sur le ticket couperait un episode en deux quand il
    enjambe minuit, et la question posee ici porte sur le PORTEUR,
    donc sur l episode.

IL FAUT patch_section9_cassure.py D ABORD

    Ce patch utilise `a.cassure`, l argument que le precedent
    installe. Sans lui le panneau planterait a la generation
    suivante, c est-a-dire dans moins de cinq minutes et sans
    personne devant l ecran. Le patch verifie et REFUSE.

CE QU IL FAUT ATTENDRE

    La colonne x60 va se scinder. Si le cote "depuis" ressemble au
    -15,09 du chapeau, la mesure et la table se rejoignent enfin. Si
    le cote "depuis" reste proche de zero, alors c est le -15,09 qui
    demande une explication -- il vient d un autre instrument
    (martingale_inv_v2) et rien ne garantit qu il compte les memes
    tickets.

    Les colonnes x10/x20/x30 seront presque vides du cote "avant" :
    ces setups n existent que depuis le 13/08 13:10. Une colonne vide
    la est un fait, pas un manque.

UNE ANCRE, reperee par les BORNES de la section (titre 7 -> titre 8).
ast.parse et controle AST. Sauvegarde horodatee, suffixee si
collision. Ne touche qu un LECTEUR.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "panel_quadruple.py"
MARQUE = "CAMPS7"

R_SEC7 = re.compile(
    r'^([ \t]*)bloc\("7\. LE PETIT SOUS COUVERTURE.*?(?=^[ \t]*bloc\("8\.)',
    re.M | re.S)

SEC7 = '''%(i)sbloc("7. LE PETIT SOUS COUVERTURE  (H10)",
%(i)s     ["Ligne = le petit setup qui entre. Colonne = le grand qui a",
%(i)s      "ouvert l episode.",
%(i)s      "",
%(i)s      "COUPE AU %%s, sur la date de DEBUT DE L EPISODE" %% a.cassure,
%(i)s      "et non sur celle de chaque petit ticket : la question porte",
%(i)s      "sur le porteur, donc sur l episode, qui reste entier du cote",
%(i)s      "ou il a commence. C est un choix.",
%(i)s      "",
%(i)s      "Avant ce patch, le chapeau annoncait +13,89 EUR/tk sous",
%(i)s      "porteur M10-M30 contre -15,09 sous H1 (mesure post-05/08)",
%(i)s      "au-dessus d une table qui agregeait TOUT depuis le 21/07 et",
%(i)s      "montrait -2,72 / +3,09 / -1,05 / -5,04 sous H1. Deux",
%(i)s      "fenetres, un seul tableau. Les deux parlent enfin de la",
%(i)s      "meme periode.",
%(i)s      "",
%(i)s      "Les colonnes x10/x20/x30 seront quasi vides du cote AVANT :",
%(i)s      "ces setups n existent que depuis le 13/08 13:10. Une case",
%(i)s      "vide y est un fait, pas un manque.",
%(i)s      "",
%(i)s      "C est cette ligne-la que le gel doit remplir."])
%(i)sgpo = collections.defaultdict(list)
%(i)sfor act in eps:
%(i)s    for e in eps[act]:
%(i)s        # Le setup du PREMIER allumage de l episode : c est lui qui
%(i)s        # a ouvert, les suivants n ont fait que le prolonger.
%(i)s        prem = None
%(i)s        for k in tk:
%(i)s            if k["actif"] == act and k["setup"] in QUATRE \\
%(i)s                    and k["t"] == e["debut"]:
%(i)s                prem = k["setup"]
%(i)s                break
%(i)s        if prem is None:
%(i)s            continue
%(i)s        _c7 = "<" if e["debut"].strftime("%%Y-%%m-%%d") < a.cassure \\
%(i)s            else ">"
%(i)s        for k in e["petits"]:
%(i)s            gpo[(_c7, k["setup"], prem)].append(k["pnl"])
%(i)sCAMPS7 = (("<", "AVANT le " + a.cassure),
%(i)s          (">", "DEPUIS le " + a.cassure))
%(i)sfor _c7, _lib7 in CAMPS7:
%(i)s    table4("PnL moyen du petit selon le grand qui a ouvert -- %%s"
%(i)s           %% _lib7,
%(i)s           ["x%%s entre" %% x for x in PETIT],
%(i)s           lambda nm, x, _c=_c7:
%(i)s           gpo.get((_c, nm.split(" ")[0][1:], x), []))

'''

VIEUX = '''%(i)sbloc("7. LE PETIT SOUS COUVERTURE  (H10)",
%(i)s     ["Ligne = le petit setup qui entre. Colonne = le grand qui a",
%(i)s      "ouvert l episode. Mesure du 14/08 : porteur M10-M30",
%(i)s      "+13,89 EUR/tk contre -15,09 sous porteur H1, t ~ 4,1 --",
%(i)s      "mais sur une seance et demie d allumages x10/x20/x30.",
%(i)s      "C est cette ligne-la que le gel doit remplir."])
%(i)sgpo = collections.defaultdict(list)
%(i)sfor act in eps:
%(i)s    for e in eps[act]:
%(i)s        # Le setup du PREMIER allumage de l episode : c est lui qui
%(i)s        # a ouvert, les suivants n ont fait que le prolonger.
%(i)s        prem = None
%(i)s        for k in tk:
%(i)s            if k["actif"] == act and k["setup"] in QUATRE \\
%(i)s                    and k["t"] == e["debut"]:
%(i)s                prem = k["setup"]
%(i)s                break
%(i)s        if prem is None:
%(i)s            continue
%(i)s        for k in e["petits"]:
%(i)s            gpo[(k["setup"], prem)].append(k["pnl"])
%(i)stable4("PnL moyen du petit, selon le grand qui a ouvert",
%(i)s       ["x%%s entre" %% x for x in PETIT],
%(i)s       lambda nm, x: gpo.get((nm.split(" ")[0][1:], x), []))

'''


def lire(c):
    return io.open(c, encoding="utf-8", errors="replace").read()


def sauver(c, t):
    base = "%s.bak-%s" % (c, datetime.now().strftime("%Y%m%d-%H%M%S"))
    s, k = base, 1
    while os.path.exists(s):
        s = "%s-%d" % (base, k)
        k += 1
    shutil.copy2(c, s)
    io.open(c, "w", encoding="utf-8").write(t)
    print("Sauvegarde : %s" % s)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--annuler", action="store_true")
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = lire(a.fichier)
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    # Le garde-fou qui compte : sans a.cassure, le panneau planterait
    # a la generation suivante, dans moins de cinq minutes et sans
    # personne devant l ecran.
    if not a.annuler and '"--cassure"' not in src:
        print("KO : l argument --cassure n existe pas dans ce fichier.")
        print("     Applique patch_section9_cassure.py D ABORD : ce")
        print("     patch s appuie sur a.cassure, et sans lui le")
        print("     panneau planterait a la prochaine regeneration.")
        print("Rien n a ete ecrit.")
        return 1

    deja = MARQUE in src
    print("  etat actuel : section 7 %s"
          % ("coupee (2 tableaux)" if deja else "agregee (1 tableau)"))
    if deja == (not a.annuler):
        print()
        print("Rien a faire -- deja dans l etat demande.")
        return 0

    if len(R_SEC7.findall(src)) != 1:
        print("KO : %d section(s) 7 reperee(s) entre son titre et celui"
              " de la section 8, il en faut 1." % len(R_SEC7.findall(src)))
        print("Rien n a ete ecrit.")
        return 1
    m = R_SEC7.search(src)
    ind = m.group(1)
    print("  section 7 reperee, indentation %d espaces, %d lignes."
          % (len(ind), m.group(0).count("\n")))

    neuf = src[:m.start()] + \
        ((VIEUX if a.annuler else SEC7) % {"i": ind}) + src[m.end():]

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # On n a touche a RIEN d autre.
    for t in ('bloc("6.', 'bloc("8.', 'bloc("9. SEANCE US',
              'bloc("10. RAPPELS', "def table4(", "def main(",
              "SEUIL = 54", "a.joindre", "CASSURE = ", '"--cassure"'):
        if neuf.count(t) != src.count(t):
            print("KO : %s apparait %d fois, %d avant."
                  % (t, neuf.count(t), src.count(t)))
            print("Rien n a ete ecrit.")
            return 1
    if (MARQUE in neuf) == a.annuler:
        print("KO : l etat obtenu n est pas celui demande.")
        print("Rien n a ete ecrit.")
        return 1
    # table4 est appele DANS UNE BOUCLE sur CAMPS7 : le nombre
    # d appels textuels ne change pas, c est le nombre d executions
    # qui double. Une premiere version de ce controle attendait +1 et
    # bloquait le patch -- le garde-fou avait tort, pas le patch.
    if neuf.count("table4(") != src.count("table4("):
        print("KO : table4 apparait %d fois, %d avant."
              % (neuf.count("table4("), src.count("table4(")))
        print("Rien n a ete ecrit.")
        return 1
    # Ce qui compte vraiment : la boucle existe et porte sur CAMPS7.
    if not a.annuler:
        boucle = [n for n in ast.walk(arbre)
                  if isinstance(n, ast.For)
                  and isinstance(n.iter, ast.Name)
                  and n.iter.id == "CAMPS7"]
        if len(boucle) != 1:
            print("KO : %d boucle(s) sur CAMPS7, il en faut 1."
                  % len(boucle))
            print("Rien n a ete ecrit.")
            return 1

    print()
    if a.annuler:
        print("  section 7 -> 1 tableau agrege (etat d origine).")
    else:
        print("  section 7 -> 2 tableaux : AVANT / DEPUIS la cassure.")
        print("  Decoupage sur la date de DEBUT DE L EPISODE.")
        print()
        print("  Attendu : les colonnes x10/x20/x30 quasi vides du cote")
        print("  AVANT -- ces setups datent du 13/08 13:10. Une case")
        print("  vide y est un fait, pas un manque.")
    print("Marche arriere : %s"
          % ("python %s" % os.path.basename(__file__) if a.annuler
             else "python %s --annuler" % os.path.basename(__file__)))
    print()
    print("PREND EFFET A LA PROCHAINE REGENERATION DU PANNEAU (5 min),")
    print("ou tout de suite : python panel_quadruple.py")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauver(a.fichier, neuf)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
