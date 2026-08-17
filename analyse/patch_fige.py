# -*- coding: utf-8 -*-
r"""
patch_fige.py -- mon test d exclusion etait plus strict que celui qui
avait produit le constat, donc il ratait sa cible

  python patch_fige.py

LE DEFAUT

    `signe_fige()` sommait le delta sur TOUTES les dates du fichier et
    exigeait que le signe soit unanime :

        return len(set(v > 0 for v in par.values())) < 2

    TICK-NYSE a 134 dates pour 130 seances : les quatre autres sont des
    reouvertures du dimanche soir et des journees tronquees. Il suffit
    qu UNE d elles ait une somme nulle -- et `v > 0` est faux pour
    zero -- pour que l ensemble contienne deux valeurs et que le
    symbole passe le filtre.

    Resultat : TICK-NYSE est reste dans la sortie du 17/08, avec ses
    deux tableaux qui ne mesurent rien.

    La cause n est pas l etourderie. `cvd_journalier.py` avait etabli
    le constat autrement : il FILTRE d abord les vraies seances -- une
    date portant au moins la moitie du nombre median de barres -- puis
    conclut par un ecart au tirage a pile ou face, z = +11,4 pour TICK
    contre -0,4 pour MES et +1,9 pour YM.

    J ai reecrit un test voisin au lieu de reprendre celui-la. Un test
    voisin repond a une question voisine.

LE CORRECTIF

    Reprendre exactement la construction de `cvd_journalier.py` :

        seances  = dates portant au moins la moitie du nombre median
                   de barres (seuil MESURE, pas invente)
        z        = (positives - n/2) / (racine(n)/2)
        ecarte   si |z| >= 8

    Le seuil de 8 n est pas invente ici non plus : c est celui que
    `cvd_journalier.py` affiche depuis ce matin -- "au-dela de +/-3 ce
    n est plus du hasard ; au-dela de +/-8 ce n est plus un marche,
    c est une constante du fichier". MES est a -0,4, YM a +1,9, TICK a
    +11,4 : la separation est franche, elle n est pas ajustee pour
    l occasion.

    Et le z de chaque symbole est AFFICHE, pour qu on juge l exclusion
    au lieu de la subir.

LA REGLE

    Quand un constat a ete etabli par un outil, le reutiliser tel quel
    ailleurs -- pas en reecrire une version de memoire. Deux tests qui
    se ressemblent ne repondent pas a la meme question, et celui qu on
    reecrit est toujours celui qui rate.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import io
import os
import shutil
import sys

CIBLE = "ecart_fenetre.py"
MARQUE = "SEUIL_Z"

A1 = '''def signe_fige(serie):
    """Le CVD par seance de ce symbole change-t-il de signe ?

    TICK-NYSE sort 130 seances positives sur 130 : son `delta` est un
    compteur monotone, pas un desequilibre acheteur/vendeur. Un indice
    n a pas de carnet. `ecart_carnets.py` l ecarte deja ; ce fichier,
    ecrit apres, ne le faisait pas -- et deux de ses trois tableaux ne
    mesuraient donc rien."""
    par = {}
    for x in serie:
        j = x[0].date()
        par[j] = par.get(j, 0.0) + x[2]
    if len(par) < 20:
        return False
    return len(set(v > 0 for v in par.values())) < 2
'''
B1 = '''# Au-dela de cet ecart au tirage a pile ou face, le signe du CVD
# quotidien n est plus un fait de marche mais une constante du
# fichier. Ce n est pas un seuil invente ici : c est celui que
# cvd_journalier.py affiche depuis le 17/08, et la separation qu il
# produit est franche -- MES -0,4, YM +1,9, TICK +11,4.
SEUIL_Z = 8.0


def signe_fige(serie):
    """Le CVD par seance de ce symbole change-t-il de signe ?

    PREMIERE VERSION, FAUSSE : elle sommait le delta sur TOUTES les
    dates et exigeait une unanimite parfaite. TICK-NYSE a 134 dates
    pour 130 seances -- reouvertures du dimanche soir, journees
    tronquees -- et il suffit qu une seule ait une somme nulle pour
    que le filtre le laisse passer. Il est effectivement passe.

    Cette version reprend la construction de `cvd_journalier.py`, qui
    avait etabli le constat : filtrer les vraies seances, puis mesurer
    l ecart a un tirage a pile ou face. Reecrire un test voisin de
    memoire, c est repondre a une question voisine.

    Rend (fige, z, n) pour que l exclusion soit AFFICHEE et jugeable."""
    par = {}
    for x in serie:
        j = x[0].date()
        a = par.setdefault(j, [0.0, 0])
        a[0] += x[2]
        a[1] += 1
    if len(par) < 20:
        return False, 0.0, len(par)
    cpt = sorted(x[1] for x in par.values())
    med = cpt[len(cpt) // 2]
    seuil = max(1, med // 2)
    cv = [x[0] for x in par.values() if x[1] >= seuil]
    n = len(cv)
    if n < 20:
        return False, 0.0, n
    pos = sum(1 for v in cv if v > 0)
    z = (pos - n / 2.0) / ((n ** 0.5) / 2.0)
    return abs(z) >= SEUIL_Z, z, n
'''

A2 = '''    # UN SYMBOLE SANS CARNET N EST PAS COMPARABLE.
    figes = [s for s, v in barres.items() if signe_fige(v)]
    for s in figes:
        del barres[s]
'''
B2 = '''    # UN SYMBOLE SANS CARNET N EST PAS COMPARABLE.
    juges = dict((s, signe_fige(v)) for s, v in barres.items())
    figes = [s for s, (f, z, n) in juges.items() if f]
    for s in figes:
        del barres[s]
'''

A3 = '''    if figes:
        dis("  ECARTE(S) -- signe de CVD fige sur toutes les seances :")
        for s in figes:
            dis("    %s : son delta ne change jamais de signe. C est un"
                % s)
            dis("    compteur, pas un desequilibre acheteur/vendeur. Un")
            dis("    indice n a pas de carnet.")
        dis()
'''
B3 = '''    dis("  SIGNE DU CVD QUOTIDIEN -- ecart a un tirage a pile ou face")
    dis("  %-16s %8s %10s %10s" % ("symbole", "seances", "z", "retenu"))
    for s in sorted(juges):
        f, z, n = juges[s]
        dis("  %-16s %8d %10.1f %10s"
            % (s, n, z, "NON" if f else "oui"))
    dis()
    dis("  Au-dela de |z| = %.0f, le signe du CVD n est plus un fait de"
        % SEUIL_Z)
    dis("  marche mais une constante du fichier : un indice n a pas de")
    dis("  carnet acheteur/vendeur, son `delta` est un compteur.")
    if figes:
        dis("  ECARTE(S) : %s." % ", ".join(sorted(figes)))
    dis()
'''

REMPLACEMENTS = [
    ("test du signe fige, repris de cvd_journalier", A1, B1),
    ("appel qui conserve le z", A2, B2),
    ("affichage du z de chaque symbole", A3, B3),
]


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        return 1
    src = io.open(CIBLE, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique. Rien n a ete touche.")
        return 0

    if "def signe_fige(" not in src:
        print("KO : patch_fenetre.py n a pas ete applique.")
        print("     Lancer d abord : python patch_fenetre.py")
        return 1

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

    sauv = CIBLE + ".avant_fige"
    if not os.path.isfile(sauv):
        shutil.copy2(CIBLE, sauv)
    io.open(CIBLE, "w", encoding="utf-8", newline="").write(out)

    print("%s : %d lignes -> %d lignes, %d remplacements."
          % (CIBLE, len(src.splitlines()), len(out.splitlines()),
             len(REMPLACEMENTS)))
    print("sauvegarde : %s" % sauv)
    print()
    print("La sortie affichera desormais le z de CHAQUE symbole. Attendu")
    print("d apres cvd_journalier du 17/08 : MES -0,4, YM +1,9, TICK")
    print("+11,4 -- et TICK seul ecarte. Si les trois z different de ces")
    print("valeurs, c est que les deux outils ne comptent pas les memes")
    print("seances, et il faudra le regarder avant de lire quoi que ce")
    print("soit d autre.")
    print()
    print("Relancer : python ecart_fenetre.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
