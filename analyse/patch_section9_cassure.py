# -*- coding: utf-8 -*-
"""
patch_section9_cassure.py -- couper la section 9 au 5 aout

  python patch_section9_cassure.py --essai
  python patch_section9_cassure.py
  python patch_section9_cassure.py --annuler

LE PROBLEME, ET IL EST DE MOI

    La section 9 agrege TOUTE la fenetre. Elle affiche donc

        en seance    ...    x60  +71.04/68

    un chiffre qui melange les cinq jours rentables du 29/07-04/08
    (+13 300 EUR en seance) avec les huit jours de pertes qui suivent.
    Aucun des deux cotes ne porte ce nombre : il n existe que dans la
    moyenne.

    Ce soir le REPL l a repris tel quel pour recommander une strategie
    "H1 en seance US". Il ne l a pas invente -- il a lu ce que le
    panneau affiche. La regle 2 du journal ("aucun chiffre agrege sur
    toute la fenetre sans preciser de quel cote du 5 aout il tombe")
    etait ECRITE dans les documents et VIOLEE par le panneau, toutes
    les cinq minutes.

    Un panneau qui enfreint la regle qu on impose au modele est un
    piege permanent. C est celui-la qu on retire.

CE QUE FAIT LE PATCH

    La section 9 passe de deux camps a QUATRE :

        seance <05/08   seance >05/08   hors <05/08   hors >05/08

    Meme decoupage horaire qu avant (15:30-19:30 sur l heure d entree
    seule, sans classifieur), meme tableau a quatre colonnes
    x10/x20/x30/x60, memes marqueurs `?` sous 54 tickets. On ajoute
    une dimension, on n en retire aucune.

    La date de cassure devient un ARGUMENT, --cassure, comme FUSION et
    PORTEE : c est un choix, il doit se voir et se changer sans
    toucher au code.

CE QUE CA VA MONTRER, ET IL FAUT S Y ATTENDRE

    Les cellules seront environ deux fois plus petites. Plusieurs
    passeront sous 54 et gagneront un `?`. Ce n est pas une perte
    d information : c est l information qui etait cachee par
    l agregation. Une cellule de 68 tickets qui se revele etre 30
    avant et 38 apres n a jamais valu 68.

MARCHE ARRIERE

    --annuler restaure la version a deux camps. Rejouable dans les
    deux sens ; le patch verifie l etat courant au lieu de le
    supposer.

TROIS ANCRES. La principale est reperee par ses BORNES (du titre de
la section 9 au titre de la section 10) et non par son contenu : le
texte interieur peut avoir bouge, la coupe reste sure. ast.parse et
controle AST. Sauvegarde horodatee, suffixee si collision.

Ce patch ne touche qu un LECTEUR. Aucun ordre, aucun collecteur.
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

# Bornes de la section 9 : du titre au titre suivant. Robuste au
# contenu, qui a deja change deux fois aujourd hui.
R_SEC9 = re.compile(
    r'^([ \t]*)bloc\("9\. SEANCE US.*?(?=^[ \t]*bloc\("10\. RAPPELS)',
    re.M | re.S)
A_CONST = "PORTEE = 120"
A_ARG = '    p.add_argument("--depuis", default=None)'
MARQUE = "CAMPS9"

SEC9 = '''%(i)sbloc("9. SEANCE US  (H9)",
%(i)s     ["Le seul edge demontrable du dossier au 14/08. Mesure sur",
%(i)s      "3 560 tickets : -5,48 EUR/tk hors seance contre +9,80 en",
%(i)s      "seance. Moyenne elaguee a 1 %% : -5,71, soit PIRE que la",
%(i)s      "brute -- ce n est donc pas une queue. Negatif 11 jours",
%(i)s      "sur 14. Le decoupage se fait sur l heure d entree seule,",
%(i)s      "sans classifieur.",
%(i)s      "",
%(i)s      "COUPE AU %%s : `<` = avant, `>` = a partir de." %% a.cassure,
%(i)s      "Agregee sur toute la fenetre, cette section melangeait les",
%(i)s      "cinq jours rentables du 29/07-04/08 avec les huit jours de",
%(i)s      "pertes qui suivent. Elle affichait +71 EUR/tk sur le x60 en",
%(i)s      "seance -- un chiffre qu aucun des deux cotes ne porte. Les",
%(i)s      "cellules sont deux fois plus petites qu avant et plusieurs",
%(i)s      "portent un `?` : c est ce que l agregation cachait, pas une",
%(i)s      "perte."])
%(i)s_et = a.cassure[8:10] + "/" + a.cassure[5:7]
%(i)sCAMPS9 = ("seance <" + _et, "seance >" + _et,
%(i)s          "hors   <" + _et, "hors   >" + _et)
%(i)sgse = collections.defaultdict(list)
%(i)sfor k in tk:
%(i)s    if k["setup"] is None:
%(i)s        continue
%(i)s    _i = (0 if "15:30" <= k["h"] < "19:30" else 2) \\
%(i)s        + (0 if k["jour"] < a.cassure else 1)
%(i)s    _nm = CAMPS9[_i]
%(i)s    gse[(_nm, k["setup"])].append(k["pnl"])
%(i)s    gse[(_nm, "TOUS")].append(k["pnl"])
%(i)stable4("PnL moyen par ticket, les quatre grands",
%(i)s       list(CAMPS9),
%(i)s       lambda nm, x: gse.get((nm, x), []))
%(i)sdis()
%(i)sfor camp in CAMPS9:
%(i)s    v = gse.get((camp, "TOUS"), [])
%(i)s    if v:
%(i)s        dis("  %%-16s tous setups confondus : n=%%-5d moy %%+8.2f%%s"
%(i)s            %% (camp, len(v), sum(v) / len(v),
%(i)s               "" if len(v) >= SEUIL else "  ?"))

'''

VIEUX = '''%(i)sbloc("9. SEANCE US  (H9)",
%(i)s     ["Le seul edge demontrable du dossier au 14/08. Mesure sur",
%(i)s      "3 560 tickets : -5,48 EUR/tk hors seance contre +9,80 en",
%(i)s      "seance. Moyenne elaguee a 1 %% : -5,71, soit PIRE que la",
%(i)s      "brute -- ce n est donc pas une queue. Negatif 11 jours",
%(i)s      "sur 14. Le decoupage se fait sur l heure d entree seule,",
%(i)s      "sans classifieur."])
%(i)sgse = collections.defaultdict(list)
%(i)sfor k in tk:
%(i)s    if k["setup"] is None:
%(i)s        continue
%(i)s    camp = "en seance" if "15:30" <= k["h"] < "19:30" else "hors seance"
%(i)s    gse[(camp, k["setup"])].append(k["pnl"])
%(i)s    gse[(camp, "TOUS")].append(k["pnl"])
%(i)stable4("PnL moyen par ticket, les quatre grands",
%(i)s       ["en seance", "hors seance"],
%(i)s       lambda nm, x: gse.get((nm, x), []))
%(i)sdis()
%(i)sfor camp in ("en seance", "hors seance"):
%(i)s    v = gse.get((camp, "TOUS"), [])
%(i)s    if v:
%(i)s        dis("  %%-16s tous setups confondus : n=%%-5d moy %%+8.2f"
%(i)s            %% (camp, len(v), sum(v) / len(v)))

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
    p.add_argument("--cassure", default="2026-08-05")
    p.add_argument("--annuler", action="store_true")
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", a.cassure):
        print("KO : --cassure doit etre AAAA-MM-JJ, recu %r." % a.cassure)
        return 1
    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = lire(a.fichier)
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    deja = MARQUE in src
    print("  etat actuel : section 9 %s"
          % ("coupee (4 camps)" if deja else "agregee (2 camps)"))
    if deja == (not a.annuler):
        print()
        print("Rien a faire -- deja dans l etat demande.")
        return 0

    m = R_SEC9.search(src)
    if not m:
        print("KO : section 9 introuvable entre son titre et celui de la")
        print("     section 10. Rien n a ete ecrit.")
        return 1
    if len(R_SEC9.findall(src)) != 1:
        print("KO : %d sections 9 trouvees, il en faut 1."
              % len(R_SEC9.findall(src)))
        print("Rien n a ete ecrit.")
        return 1
    ind = m.group(1)
    print("  section 9 reperee, indentation %d espaces, %d lignes."
          % (len(ind), m.group(0).count("\n")))

    neuf = src[:m.start()] + \
        ((VIEUX if a.annuler else SEC9) % {"i": ind}) + src[m.end():]

    # --- la constante et l argument, seulement a l aller -------------
    if not a.annuler:
        if "CASSURE = " not in neuf:
            if neuf.count(A_CONST) != 1:
                print("KO : %d occurrence(s) de '%s'."
                      % (neuf.count(A_CONST), A_CONST))
                print("Rien n a ete ecrit.")
                return 1
            neuf = neuf.replace(
                A_CONST,
                A_CONST + "\n"
                "# Le 5 aout n est pas choisi apres coup : c est la date\n"
                "# que la stack retient elle-meme en nommant\n"
                "# panel_rails_post0508. Comme FUSION et PORTEE, c est un\n"
                "# CHOIX -- il s expose et se change en ligne de commande.\n"
                'CASSURE = "%s"' % a.cassure, 1)
        if '"--cassure"' not in neuf:
            if neuf.count(A_ARG) != 1:
                print("KO : %d occurrence(s) de l argument --depuis."
                      % neuf.count(A_ARG))
                print("Rien n a ete ecrit.")
                return 1
            neuf = neuf.replace(
                A_ARG,
                A_ARG + '\n    p.add_argument("--cassure", default=CASSURE)',
                1)
    else:
        neuf = re.sub(r'\n    p\.add_argument\("--cassure"[^\n]*', "",
                      neuf, count=1)
        neuf = re.sub(r"\n# Le 5 aout n est pas choisi.*?\nCASSURE = \"[^\"]*\"",
                      "", neuf, count=1, flags=re.S)

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # Controles : on n a touche QUE la section 9.
    for t in ('bloc("10. RAPPELS', 'bloc("8.', 'def table4(', 'def main(',
              "SEUIL = 54", "QUATRE = ", "a.joindre"):
        if neuf.count(t) != src.count(t):
            print("KO : %s n apparait plus le meme nombre de fois." % t)
            print("Rien n a ete ecrit.")
            return 1
    if (MARQUE in neuf) == a.annuler:
        print("KO : l etat obtenu n est pas celui demande.")
        print("Rien n a ete ecrit.")
        return 1
    noms = [n.id for n in ast.walk(arbre)
            if isinstance(n, ast.Name) and n.id == "gse"]
    if not noms:
        print("KO : gse a disparu de la section.")
        print("Rien n a ete ecrit.")
        return 1

    print()
    if a.annuler:
        print("  section 9 -> 2 camps (en seance / hors seance)")
    else:
        e = a.cassure[8:10] + "/" + a.cassure[5:7]
        print("  section 9 -> 4 camps :")
        print("     seance <%s   seance >%s" % (e, e))
        print("     hors   <%s   hors   >%s" % (e, e))
        print("  --cassure ajoute, defaut CASSURE = %s" % a.cassure)
        print()
        print("  Attends-toi a des cellules deux fois plus petites et a")
        print("  des `?` nouveaux : c est ce que l agregation cachait.")
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
