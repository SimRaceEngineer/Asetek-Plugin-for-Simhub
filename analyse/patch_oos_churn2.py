#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_oos_churn2.py -- churn_entry est un dict, pas une chaine

CE QUE LE PREMIER PATCH N A PAS SUFFI A REGLER
    patch_oos_churn.py a ajoute churn_entry a CLEFS_CHURN, et --champs
    annonce toujours churn a 0 pour cent. C etait previsible et je l avais
    dit : le champ existe, _prem le trouve, mais sa valeur est

        {'VERDICT': 'CHURN', 'CONF': ...}

    et _churn fait str(v).strip().upper() dessus. La chaine obtenue,
    "{'VERDICT': 'CHURN', ...}", n est dans aucune clef de CHURN_VALIDES,
    donc le verdict revient vide. Corriger la liste de NOMS ne pouvait pas
    suffire : c est la LECTURE de la valeur qu il faut corriger.

DEUX MODIFICATIONS, DANS oos_v9.py UNIQUEMENT
    1. _churn descend dans le dictionnaire et en sort VERDICT. Une chaine
       continue de fonctionner, au cas ou le format changerait.
    2. CHURN_VALIDES apprend OK, qui apparait dans les donnees et que le
       vocabulaire d origine -- CLEAN / MIXED / CHURN -- ne prevoyait pas.

POURQUOI OK RESTE "OK" ET NE DEVIENT PAS "CLEAN"
    Ce serait l hypothese la plus naturelle, et c est exactement pour ca
    qu il ne faut pas la poser ici. Rien ne dit qu OK et CLEAN designent le
    meme etat, et le fichier de regles est gele : on ne change pas le sens
    de ses cellules par une supposition faite trois semaines apres.

    Le risque de garder OK a part est nul. Les trois regles de la famille Y
    -- Y1, Y2, Y4 -- ne testent qu une seule valeur, MIXED. Un ticket OK ne
    les declenchera pas, ce qui est le comportement correct si OK n est pas
    MIXED. Et comme OK devient une valeur RECONNUE, il compte dans la
    couverture, ce qui est le but.

CE QUE CA NE REGLE TOUJOURS PAS
    La famille X -- X1, X3, X4, X6, dont la tete X1 -- repose sur le biais
    des rails M1/M3/M5. Les clefs d un enregistrement sont :

        asset, churn_entry, close_reason, close_ts, dir,
        entry_captured_live, entry_price, entry_ts, mae_eur, mae_pts,
        magic, mfe_eur, mfe_pts, pid, pnl_eur, ticket, volume

    Aucun champ rails. Aucun RSI. Ce n est pas un probleme de nom, la
    donnee n existe pas. Tant que le module qui ecrit ce journal ne les
    ajoute pas, --verdict refusera de conclure le 01/09, et il aura raison.

IDEMPOTENT.
"""
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "oos_v9.py"
# Le marqueur doit etre UNIQUE au bloc pose. Premier jet : "isinstance(v,
# dict)" -- deja present dans _niche, donc le patch se croyait applique et
# ne faisait rien. Meme piege qu avec "_sl_arb.install" ce matin. Ici la
# chaine ci-dessous n existe nulle part ailleurs dans le fichier.
MARQUEUR = '("VERDICT", "verdict", "Verdict")'

ANCRE_FN = '    return CHURN_VALIDES.get(str(v).strip().upper(), "")'
NEUF_FN = '''    # 11/08 : churn_entry vaut {'VERDICT': 'CHURN', 'CONF': ...}, pas une
    # chaine. str(dict) ne correspond a aucune clef de CHURN_VALIDES, d ou
    # une couverture a 0 pour cent malgre un champ present sur 100 pour
    # cent des tickets. On descend d un cran, et on tolere la chaine au cas
    # ou le format changerait.
    if isinstance(v, dict):
        for _k in ("VERDICT", "verdict", "Verdict"):
            if v.get(_k):
                v = v[_k]
                break
    return CHURN_VALIDES.get(str(v).strip().upper(), "")'''

ANCRE_VOC = '                 "CHURN": "CHURN", "NOISE": "CHURN"}'
NEUF_VOC = ('                 "CHURN": "CHURN", "NOISE": "CHURN",\n'
            '                 # OK apparait dans les donnees et n etait pas prevu.\n'
            '                 # Garde distinct de CLEAN : rien ne dit que c est le\n'
            '                 # meme etat, et le fichier de regles est gele.\n'
            '                 "OK": "OK"}')


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable -- lance depuis le dossier de la stack." % CIBLE)
        return 1

    src, enc = lire(CIBLE)
    print("%s : %d lignes, encodage %s" % (CIBLE, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Deja corrige -- rien a faire.")
        return 0

    for lab, a in (("la fonction _churn", ANCRE_FN),
                   ("le vocabulaire CHURN_VALIDES", ANCRE_VOC)):
        if src.count(a) != 1:
            print("KO : %d occurrence(s) de l ancre pour %s, il en faut 1 :"
                  % (src.count(a), lab))
            print("    " + a.strip())
            return 1

    neuf = src.replace(ANCRE_FN, NEUF_FN, 1).replace(ANCRE_VOC, NEUF_VOC, 1)
    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    sauve = "%s.bak-%s" % (CIBLE, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(CIBLE, sauve)
    io.open(CIBLE, "w", encoding=enc).write(neuf)
    print("Sauvegarde : %s" % sauve)
    print("_churn descend dans le dict ; OK est un verdict reconnu.")
    print()
    print("Verifie :   python oos_v9.py --champs")
    print()
    print("ATTENDU")
    print("  churn                    doit passer de 0% a pres de 100%")
    print("  couverture famille Y     doit franchir les 60% requis")
    print("  couverture famille X     restera a 0%, et c est normal :")
    print("                           aucun champ rails n est ecrit sur disque.")
    print()
    print("La ligne churn doit maintenant lister CLEAN, MIXED, CHURN et OK")
    print("avec leurs effectifs. Si OK domine largement, il faudra decider")
    print("ce qu il designe AVANT le 01/09 -- mais en le documentant, pas en")
    print("modifiant regles_gelees_v9.py, dont l empreinte est posee.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
