# -*- coding: utf-8 -*-
r"""
patch_temoin.py -- un temoin doit etre une journee VERIFIEE sans
publication, pas une journee dont on ne sait rien

  python patch_temoin.py

CE QU IL CORRIGE

    Une journee devient temoin quand elle n apparait pas dans la liste
    des dates d evenements. C est juste tant que le calendrier couvre
    la periode. Il ne la couvre pas :

        barres        du 2025-12-28 au 2026-08-17
        calendrier    de juin a octobre

    De janvier a mai, le fichier de calendrier est VIDE. Toutes ces
    journees sont donc declarees "sans publication" -- alors qu il y a
    eu des CPI, des NFP et des Fed pendant ces cinq mois. L absence n y
    est pas mesuree, elle est seulement inconnue.

    Sur le tirage du 17/08 : 126 journees temoins, dont de l ordre de
    110 avant juin. Le groupe temoin est a ~85 % constitue de journees
    hors calendrier. La comparaison n est alors pas "avec surprise
    contre sans surprise", c est JUIN-AOUT CONTRE JANVIER-MAI.

POURQUOI C EST PIRE ENCORE SUR LE DELTA

    Le raccord bascule de MESM26 a MESU26 le 16 juin. Les evenements
    sont donc presque tous sur MESU26, les temoins presque tous sur
    MESM26. Deux echeances n ont pas le meme volume : le delta cumule
    n a pas la meme magnitude sur l une et sur l autre.

    L ecart mesure -- -1330 contrats a 15 minutes, p = 0,0015 -- est
    exactement ce que produirait cette difference de liquidite, sans
    qu aucune macro n intervienne. Trois faits vont dans ce sens :

        YMU26-CBOT   un seul contrat sur toute sa plage   rien sur 12 tests
        TICK-NYSE    pas de contrat du tout               rien sur 12 tests
        MES-continu  le seul qui bascule                  le seul qui sort

    Ce n est pas une preuve. C est une coherence, et elle se teste.

CE QUE FAIT LE CORRECTIF

    Un temoin ne peut etre pris QUE dans la plage effectivement
    couverte par le calendrier. Hors de cette plage, on ne sait pas, et
    on ne compte pas. Les journees ecartees sont comptees et affichees.

    Consequence attendue : l effectif temoin va CHUTER, et certains
    horizons passeront a "trop peu de points". C est le resultat
    correct. Un effectif honnete de 20 vaut mieux qu un effectif de 126
    dont 110 ne mesurent rien.

    La plage est LUE dans le fichier de calendrier, pas ecrite en dur :
    si le calendrier est etendu vers le passe -- ce qui est la vraie
    solution -- la plage s elargit toute seule et les temoins
    reviennent.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import io
import os
import shutil
import sys

CIBLE = "reaction_evenements.py"
MARQUE = "cal_deb, cal_fin"

# ---------------------------------------------------------------- 1
A1 = '''        temoins = []
        heures = set((e["t"].hour, e["t"].minute) for e in dans)
        j = deb.date()
        while j <= fin.date():
            if j not in jours_ev:
                for hh, mm in heures:
                    temoins.append(dt.datetime(j.year, j.month, j.day,
                                               hh, mm))
            j += dt.timedelta(days=1)
'''
B1 = '''        # UN TEMOIN EST UNE JOURNEE VERIFIEE SANS PUBLICATION.
        #
        # Une journee absente de `jours_ev` n est "sans publication"
        # que si le calendrier couvre cette journee-la. Les barres
        # commencent en decembre, le calendrier en juin : de janvier a
        # mai, le fichier est vide, et toutes ces journees etaient
        # declarees temoins alors qu il y a eu des CPI, des NFP et des
        # Fed pendant ces cinq mois.
        #
        # Le groupe temoin devenait alors une PERIODE et non une
        # condition -- janvier-mai contre juin-aout -- avec en prime un
        # changement d echeance au milieu, donc un niveau de volume
        # different et un delta cumule qui ne se compare pas.
        #
        # La plage est LUE dans le calendrier. Etendre le calendrier
        # vers le passe elargit la plage sans toucher a ce code.
        cal_deb, cal_fin = min(e["t"].date() for e in cal), \\
            max(e["t"].date() for e in cal)
        temoins = []
        hors = 0
        heures = set((e["t"].hour, e["t"].minute) for e in dans)
        j = deb.date()
        while j <= fin.date():
            if j not in jours_ev:
                if cal_deb <= j <= cal_fin:
                    for hh, mm in heures:
                        temoins.append(dt.datetime(j.year, j.month,
                                                   j.day, hh, mm))
                else:
                    hors += 1
            j += dt.timedelta(days=1)
        dis("  Calendrier couvert : du %s au %s." % (cal_deb, cal_fin))
        if hors:
            dis("  %d journee(s) sans publication ECARTEES du temoin :"
                % hors)
            dis("  elles tombent HORS de cette plage. Sur ces journees,")
            dis("  l absence de publication n est pas mesuree, elle est")
            dis("  seulement inconnue -- et les compter revenait a")
            dis("  comparer deux PERIODES, pas deux conditions.")
'''

REMPLACEMENTS = [
    ("construction du temoin bornee au calendrier", A1, B1),
]


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        return 1
    src = io.open(CIBLE, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique : `%s` est present dans %s." % (MARQUE, CIBLE))
        print("Rien n a ete touche.")
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

    sauv = CIBLE + ".avant_temoin"
    if not os.path.isfile(sauv):
        shutil.copy2(CIBLE, sauv)
    io.open(CIBLE, "w", encoding="utf-8", newline="").write(out)

    print("%s : %d lignes -> %d lignes, %d remplacement."
          % (CIBLE, len(src.splitlines()), len(out.splitlines()),
             len(REMPLACEMENTS)))
    print("sauvegarde : %s" % sauv)
    print()
    print("A LIRE DANS LA SORTIE, DANS CET ORDRE :")
    print()
    print("  1. le nombre de journees ECARTEES du temoin. S il est de")
    print("     l ordre de 110 sur 126, le tableau precedent comparait")
    print("     bien deux periodes et non deux conditions.")
    print()
    print("  2. le -1330 contrats a 15 min, p = 0,0015 sur MES-continu.")
    print("     S il disparait, c etait la base entre MESM26 et MESU26.")
    print("     S il survit avec un effectif honnete, il devient la")
    print("     premiere chose interessante de la matinee.")
    print()
    print("  3. les horizons qui passent a `trop peu de points`. C est")
    print("     attendu, et c est le resultat correct.")
    print()
    print("Relancer : python reaction_evenements.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
