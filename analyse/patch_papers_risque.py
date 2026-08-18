# -*- coding: utf-8 -*-
r"""
patch_papers_risque.py -- corriger ce que le panneau affirme sur le risque

  python patch_papers_risque.py --essai
  python patch_papers_risque.py

CE QUI ETAIT FAUX

    Le panneau ecrivait : "des lots proportionnels a la balance, avec un
    stop en POINTS, donnent un risque par trade qui est un POURCENTAGE
    CONSTANT du compte".

    C est vrai A DISTANCE DE STOP EGALE. C est FAUX entre deux
    strategies dont les stops different en points -- et les stops se
    posent sur la structure, donc ils different. Celle qui vise large
    risque mecaniquement plus par prise.

    Autrement dit la regle du 1 pour 20 k neutralise la TAILLE DU
    COMPTE, pas l ECART DE STOPS. Le panneau laissait croire qu elle
    reglait les deux.

CE QUI EST AJOUTE

    Le paragraphe dit maintenant ce qui est neutralise et ce qui ne
    l est pas, et donne la formule du vrai risque constant :

        lot = (balance x risque%) / (points_SL x valeur_point)

    Elle demande la valeur du point, absente de l export. La regle
    retenue ne change pas ; ce qu elle laisse passer est ecrit.

ET LA BALANCE FICTIVE EST EPINGLEE

    Le compte reel ne vaut pas 20 000. Un moteur papier qui lirait le
    solde reel dimensionnerait autrement, sans que rien ne le signale,
    et les deux jeux seraient compares a des tailles qui n ont jamais
    ete celles de leur enonce.

Sauvegarde horodatee, refuse de s appliquer deux fois, compile avant de
remplacer.
"""
import argparse
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "papers_compare.py"
MARQUE = "ELLE NE NEUTRALISE PAS l ecart de stops"

ANC1 = '    a("  balance de depart (fictive) : %.0f" % BALANCE0)'

NEW1 = '    a("  balance de depart (FICTIVE)  : %.0f" % BALANCE0)\n    a("")\n    a("  CETTE BALANCE EST UNE VARIABLE A PART, ET DOIT LE RESTER.")\n    a("  Le compte reel ne vaut pas %.0f. Un moteur papier qui lirait le" % BALANCE0)\n    a("  solde reel dimensionnerait a balance_reelle / %.0f -- soit un" % LOT_PAR)\n    a("  lot different du 1,00 attendu, sans que rien ne le signale, et")\n    a("  les deux jeux seraient compares a des tailles qui n ont jamais")\n    a("  ete celles de leur enonce.")\n    a("")'

ANC2 = '    a("  POURQUOI CA NE BIAISE PAS LA COMPARAISON")\n    a("  Des lots proportionnels a la balance, avec un stop en POINTS,")\n    a("  donnent un risque par trade qui est un POURCENTAGE CONSTANT du")\n    a("  compte. A lot fixe, la strategie la plus frequente accumulerait")\n    a("  mecaniquement plus de risque absolu et paraitrait meilleure ou")\n    a("  pire pour une raison qui n a rien a voir avec sa qualite.")'

NEW2 = '    a("  CE QUE CETTE REGLE NEUTRALISE, ET CE QU ELLE NE NEUTRALISE PAS")\n    a("")\n    a("  ELLE NEUTRALISE la taille du compte. Le risque par trade vaut")\n    a("  points_SL x valeur_point x balance / %.0f : rapporte a la" % LOT_PAR)\n    a("  balance, il ne depend plus d elle. Une strategie ne paraitra")\n    a("  donc ni meilleure ni pire selon qu elle a grossi ou fondu.")\n    a("")\n    a("  ELLE NE NEUTRALISE PAS l ecart de stops entre strategies.")\n    a("  J avais ecrit que le risque etait un pourcentage constant du")\n    a("  compte -- c est vrai A DISTANCE DE STOP EGALE, et faux entre")\n    a("  deux strategies dont les stops different en points. Les stops")\n    a("  se posent sur la structure : celle qui vise large risque")\n    a("  mecaniquement plus par prise que celle qui vise serre.")\n    a("")\n    a("  Le vrai risque constant demanderait de dimensionner DEPUIS le")\n    a("  stop :")\n    a("")\n    a("      lot = (balance x risque%) / (points_SL x valeur_point)")\n    a("")\n    a("  C est plus juste et plus contraignant -- il faut la valeur du")\n    a("  point, que l export ne donne pas. La regle retenue reste le")\n    a("  1 pour %.0f ; ce paragraphe dit ce qu elle laisse passer plutot" % LOT_PAR)\n    a("  que de le taire.")'


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable." % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes." % (a.fichier, src.count("\n") + 1))

    if MARQUE in src:
        print("Deja applique -- rien a faire.")
        return 0

    out = src
    for i, (anc, neuf) in enumerate(((ANC1, NEW1), (ANC2, NEW2)), 1):
        n = out.count(anc)
        print("  ancre %d : %d occurrence(s), attendu 1" % (i, n))
        if n != 1:
            print()
            print("KO : ancre absente ou ambigue. RIEN n a ete ecrit.")
            return 1
        out = out.replace(anc, neuf, 1)

    try:
        compile(out, a.fichier, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (ligne %s : %s)."
              % (e.lineno, e.msg))
        return 1
    print("  le resultat compile.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauv = "%s.bak-%s" % (a.fichier,
                          datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauv)
    io.open(a.fichier, "w", encoding="utf-8", newline="").write(out)
    print()
    print("Sauvegarde : %s" % sauv)
    print("%d -> %d lignes." % (len(src.splitlines()), len(out.splitlines())))
    print()
    print("Relance ensuite :")
    print("    python papers_compare.py --sortie panels")
    return 0


if __name__ == "__main__":
    sys.exit(main())
