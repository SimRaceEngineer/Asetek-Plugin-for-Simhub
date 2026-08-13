# -*- coding: utf-8 -*-
"""
patch_orderflow_er_decale_v2.py -- l ER de la barre PRECEDENTE, a cote

  python patch_orderflow_er_decale_v2.py --essai
  python patch_orderflow_er_decale_v2.py

POURQUOI UNE v2

    La v1 a ete refusee, et elle a bien fait : 0 occurrence de l ancre.
    J avais ecrit le bloc `if bar:` a douze espaces d indentation, un
    cran trop profond. Le vrai fichier le porte a HUIT, dans
    attach(trades, of_idx, coh_idx=None), l.291. La v2 est ecrite sur
    le code lu, pas sur le code suppose.

    Deux autres choses que la v1 ignorait, et qui l auraient rendue
    fausse meme avec la bonne indentation :

      - `minute` peut valoir None (l.266 : `... if e else None`). Faire
        `minute - BAR_SEC` sans garde leverait un TypeError sur le
        premier ticket sans entry_ts lisible.
      - les deux branches posent aussi `_events` et `_contra`. On
        s insere AVANT elles, sans y toucher.

CE QU ON MESURE, ET POURQUOI

    orderflow_join apparie chaque trade a sa barre ainsi (l.266-267) :

        minute = int(e // BAR_SEC) * BAR_SEC if e else None
        bar    = of_idx.get((t.get("asset"), minute)) if e else None

    L arrondi va vers le BAS : la barre retenue est celle qui CONTIENT
    l entree, et elle se referme APRES. Un trade entre a 10:00:15 est
    apparie a la barre 10:00-10:01, dont l ER n est connu qu a 10:01.

    Consequence : les chiffres du gel V9 -- US30 CARNAGE +1,57 (59),
    MOU -14,59 (47), CORRECT +11,97 (48), PROPRE +20,43 (24) --
    DECRIVENT ce qui s est passe pendant le trade. Ils n etaient pas
    lisibles au moment de decider. Aucune regle live ne les reproduit.

    Deux regles restent implementables, et ce patch sert a chiffrer
    les deux :

      A. LA BARRE PRECEDENTE, close avant l entree. Son ER est connu a
         l instant t. Elle decrit le passe immediat, pas le mouvement
         qu on prend.
      B. ATTENDRE LA CLOTURE de la barre en cours, lire son ER, entrer.
         C est l ER de la BONNE barre, au prix d un retard de 0 a 60 s.
         Ce retard a un cout en prix d entree : c est `_close_barre`,
         a comparer au prix d entree reel.

    B est la meilleure des deux SI le cout du retard est petit. C est
    tout l objet de la mesure -- et elle ne vaut que le jour ou le flux
    cessera d etre differe de 10 min. En attendant, on prepare la
    colonne.

CE QUE LE PATCH AJOUTE -- TROIS CHAMPS, RIEN D AUTRE

      _er_prec        ER de la barre precedente, close avant l entree
      _er_band_prec   sa bande
      _close_barre    cloture de la barre contenante = cout du retard

    `_er` et `_er_band` ne sont NI modifies NI remplaces, et `_events`
    et `_contra` non plus. Tout ce qui les lit -- panneaux, gels,
    etudes -- rend exactement les memes chiffres qu avant. On ajoute
    une colonne, on n en corrige aucune : les mesures passees restent
    comparables.

    Les trois champs existent TOUJOURS, meme sans barre. Un champ a
    None se lit ; un champ absent leve une KeyError trois semaines
    plus tard, dans un panneau, un dimanche.

SUR LE NOM DU CHAMP DE CLOTURE

    La barre peut nommer sa cloture `close` ou `c` selon ce qu ecrit
    scid_orderflow. Le code injecte lit l un PUIS l autre. Il ne
    devine pas : si aucun des deux n existe, `_close_barre` vaut None
    et la mesure B est simplement indisponible -- ce qui se voit, au
    lieu de planter.

DEUX ANCRES, chacune verifiee unique. IDEMPOTENT. Sauvegarde
horodatee. ast.parse avant ecriture, puis controle SUR L ARBRE que les
trois champs atterrissent dans la meme fonction que `_er_band`, avec
of_idx, minute et BAR_SEC a portee -- ailleurs ils compileraient sans
jamais etre calcules.

C est une jointure de LECTURE : aucun ordre, rien a redemarrer. Les
panneaux qui importent le module au demarrage la reliront a leur
prochain lancement.
"""
import argparse
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "orderflow_join.py"
MARQUEUR = "_er_band_prec"

# Indentation reelle : `if bar:` a 8, son corps a 12. Lu sur le
# fichier (l.291-295), pas suppose -- c est ce qui a coule la v1.
ANCRE = '''        if bar:
            evs = bar.get("events") or []
            d["_of"] = bar
            d["_er"] = bar.get("er")
            d["_er_band"] = er_band(bar.get("er"))
'''

NEUF = '''        if bar:
            evs = bar.get("events") or []
            d["_of"] = bar
            d["_er"] = bar.get("er")
            d["_er_band"] = er_band(bar.get("er"))
            # LA BARRE PRECEDENTE, close AVANT l entree.
            # `bar` ci-dessus est la barre qui CONTIENT l entree :
            # int(e // BAR_SEC) arrondit vers le bas, donc elle se
            # referme apres et son ER n est pas connu au moment de
            # decider. Celui-ci l est. Les deux coexistent : _er_band
            # pour relire l historique tel qu il a ete mesure,
            # _er_band_prec pour ce qui aurait pu etre decide.
            # `minute` peut valoir None (cf. plus haut) : sans cette
            # garde, un ticket sans entry_ts lisible leverait un
            # TypeError au premier passage.
            _bp = (of_idx.get((t.get("asset"), minute - BAR_SEC))
                   if minute else None)
            d["_er_prec"] = _bp.get("er") if _bp else None
            d["_er_band_prec"] = er_band(_bp.get("er") if _bp else None)
            # La cloture de la barre contenante : le prix qu on
            # paierait en attendant sa fermeture pour lire son ER.
            # L ecart avec l entree reelle est le COUT DU RETARD, et
            # il decide a lui seul si cette regle-la vaut la peine.
            # `close` ou `c` selon ce qu ecrit scid_orderflow ; si ni
            # l un ni l autre, None -- la mesure manque, elle ne plante
            # pas.
            d["_close_barre"] = (bar.get("close") if bar.get("close")
                                 is not None else bar.get("c"))
'''

# Les trois champs doivent exister meme sans barre. On s insere apres
# `_er_band` et AVANT `_events` / `_contra`, auxquels on ne touche pas.
ANCRE2 = '''        else:
            d["_of"] = None
            d["_er"] = None
            d["_er_band"] = "?"
'''
NEUF2 = '''        else:
            d["_of"] = None
            d["_er"] = None
            d["_er_band"] = "?"
            d["_er_prec"] = None
            d["_er_band_prec"] = "?"
            d["_close_barre"] = None
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

    for nom, anc in (("le bloc `if bar:`", ANCRE),
                     ("le bloc `else:` correspondant", ANCRE2)):
        c = src.count(anc)
        if c != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (c, nom))
            print("     L indentation attendue est 8 espaces pour le bloc")
            print("     et 12 pour son corps, comme dans attach().")
            print("Rien n a ete ecrit.")
            return 1
    print("Deux ancres, chacune unique.")

    neuf = src.replace(ANCRE, NEUF, 1).replace(ANCRE2, NEUF2, 1)

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # Poses dans une autre fonction, les trois champs compileraient
    # sans jamais etre calcules. On verifie qu ils sont dans la MEME
    # fonction que _er_band, et que of_idx, minute et BAR_SEC y sont.
    ok = False
    for f in ast.walk(arbre):
        if not isinstance(f, ast.FunctionDef):
            continue
        d = ast.dump(f)
        if "_er_band" in d and "_er_band_prec" in d:
            ok = ("of_idx" in d and "minute" in d and "BAR_SEC" in d)
            if ok:
                print("Arbre verifie : les trois champs sont dans %s(),"
                      " avec of_idx, minute et BAR_SEC." % f.name)
            break
    if not ok:
        print("KO : les nouveaux champs ne sont pas dans la fonction qui")
        print("     calcule _er_band, ou of_idx/minute/BAR_SEC n y sont")
        print("     pas. Ils compileraient sans etre calcules.")
        print("Rien n a ete ecrit.")
        return 1

    # Les champs intouchables doivent rester exactement aussi nombreux
    # qu avant. Si l un d eux bougeait, un panneau changerait de
    # chiffres sans qu on l ait demande.
    for champ in ('d["_er"]', 'd["_er_band"]', 'd["_events"]',
                  'd["_contra"]', 'd["_of"]'):
        if src.count(champ) != neuf.count(champ):
            print("KO : %s n apparait plus le meme nombre de fois." % champ)
            print("Rien n a ete ecrit.")
            return 1
    print("Champs existants intacts : _of, _er, _er_band, _events, _contra.")

    print()
    print("Trois champs ajoutes, aucun modifie :")
    print("  _er_prec        ER de la barre PRECEDENTE, close avant l entree")
    print("  _er_band_prec   sa bande")
    print("  _close_barre    cloture de la barre contenante = cout du retard")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Jointure de lecture : aucun ordre, rien a redemarrer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
