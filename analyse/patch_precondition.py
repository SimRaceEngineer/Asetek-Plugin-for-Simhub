# -*- coding: utf-8 -*-
r"""
patch_precondition.py -- un verdict de dissociation qui ne verifiait
pas sa condition d application

  python patch_precondition.py

LE DEFAUT

    Sortie reelle du 17/08 :

        MES-continu   n=133   rho(delta, rendement) = 0.569   p = 0.0005
        YM-continu    n=112   rho(delta, rendement) = 0.015   p = 0.8726

        MES / YM      n=110   rho PRIX 0.777   rho DELTA 0.031

        LES PRIX BOUGENT ENSEMBLE, LES FLUX NON. C est une
        dissociation : la rotation entre les deux actifs est
        invisible dans les prix et lisible dans les carnets.

    Faux, ou plutot : non demontre.

    Une dissociation "les prix ensemble, les flux separes" ne veut dire
    quelque chose que si LES DEUX FLUX PORTENT DE L INFORMATION. Le
    delta de YM n en porte pas : rho = 0,015 avec p = 0,87 sur 112
    seances, il n a aucun rapport avec le mouvement de YM lui-meme.

    Or corriger n importe quoi avec du bruit donne zero. Le 0,031 entre
    les deux deltas est donc exactement ce qu on obtient sans aucune
    rotation. Il ne distingue pas les deux hypotheses.

    C est la faute recurrente de la journee : un verdict calcule sans
    controler ce qu il suppose.

LE CORRECTIF

    Le verdict de dissociation n est prononce que si les DEUX symboles
    ont un `rho(delta, rendement)` significatif -- p < 0,05 sur la
    permutation deja calculee en section 1. Aucun seuil nouveau n est
    invente : on reutilise la p-value que l outil produit deja.

    Sinon, il dit lequel des deux flux est muet, et que la comparaison
    des deltas ne peut pas trancher.

CE QUE CA N ENLEVE PAS

    Le rho de 0,569 a p = 0,0005 sur MES reste, et c est le resultat
    solide de la journee : sur le S&P, le flux d ordres et la direction
    du jour vont ensemble.

    L asymetrie entre les deux symboles reste aussi, et elle est
    informative par elle-meme : le flux SierraChart n a pas la meme
    valeur des deux cotes. Sur le 12/08, MES echange 35 979 contrats
    dans l heure contre 3 132 pour YM.

CE QUI RESTE A FAIRE, ET QUE CE PATCH NE FAIT PAS

    `rho` est mesure sur des agregats JOURNALIERS. Un delta informatif
    a l echelle de la minute peut se laver entierement sur une seance.
    La meme mesure a l echelle horaire trancherait -- et c est elle qui
    decidera si H30, construite sur une fenetre d une heure du delta de
    YM, repose sur du signal ou sur du bruit.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import io
import os
import shutil
import sys

CIBLE = "flux_contre_prix.py"
MARQUE = "informatif"

A1 = '''    dis("  %-16s %8s %12s %10s" % ("symbole", "n", "rho(d, r)", "p"))
    for sym in sorted(sc):
        js = sorted(sc[sym])
        r = [sc[sym][j][0] for j in js]
        d = [sc[sym][j][1] for j in js]
        rho, pv = p_permutation(d, r, a.tirages)
        dis("  %-16s %8d %12.3f %10.4f" % (sym, len(js), rho, pv))
'''
B1 = '''    dis("  %-16s %8s %12s %10s %12s"
        % ("symbole", "n", "rho(d, r)", "p", "flux"))
    informatif = {}
    for sym in sorted(sc):
        js = sorted(sc[sym])
        r = [sc[sym][j][0] for j in js]
        d = [sc[sym][j][1] for j in js]
        rho, pv = p_permutation(d, r, a.tirages)
        # Un flux est dit INFORMATIF s il explique le prix de son
        # PROPRE symbole. Le seuil n est pas invente ici : c est la
        # p-value de la permutation ci-dessus.
        informatif[sym] = (pv is not None and pv < 0.05)
        dis("  %-16s %8d %12.3f %10.4f %12s"
            % (sym, len(js), rho, pv,
               "informatif" if informatif[sym] else "MUET"))
'''

A2 = '''            if rp is not None and rd is not None:
                dis("  Ecart entre les deux : %.3f contre %.3f."
                    % (rp, rd))
                if rp > 0.5 and abs(rd) < 0.25:
'''
B2 = '''            if rp is not None and rd is not None:
                dis("  Ecart entre les deux : %.3f contre %.3f."
                    % (rp, rd))
                # LA CONDITION D APPLICATION DU VERDICT.
                #
                # "Les prix ensemble, les flux separes" ne veut dire
                # quelque chose que si LES DEUX FLUX portent de
                # l information. Correler n importe quoi avec du bruit
                # donne zero : un rho de deltas nul ne distingue pas
                # "rotation" de "l un des deux deltas est du bruit".
                muets = [s for s in (sa, sb) if not informatif.get(s)]
                if muets:
                    dis()
                    dis("  VERDICT SUSPENDU : le delta de %s n explique"
                        % ", ".join(muets))
                    dis("  pas le prix de son PROPRE symbole (section 1).")
                    dis("  Correler n importe quoi avec du bruit donne")
                    dis("  zero, donc un rho de deltas nul ne distingue")
                    dis("  pas une rotation d un flux muet. La")
                    dis("  comparaison ne peut pas trancher ici.")
                    dis()
                    dis("  Ce n est pas rien pour autant : un flux muet")
                    dis("  d un cote et parlant de l autre dit que la")
                    dis("  source n a pas la meme valeur sur les deux")
                    dis("  symboles -- ce qui est une reponse a la")
                    dis("  question de savoir quoi payer.")
                elif rp > 0.5 and abs(rd) < 0.25:
'''

REMPLACEMENTS = [
    ("colonne `flux` et memorisation du caractere informatif", A1, B1),
    ("condition d application du verdict de dissociation", A2, B2),
]


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        return 1
    src = io.open(CIBLE, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique. Rien n a ete touche.")
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

    sauv = CIBLE + ".avant_precondition"
    if not os.path.isfile(sauv):
        shutil.copy2(CIBLE, sauv)
    io.open(CIBLE, "w", encoding="utf-8", newline="").write(out)

    print("%s : %d lignes -> %d lignes, %d remplacements."
          % (CIBLE, len(src.splitlines()), len(out.splitlines()),
             len(REMPLACEMENTS)))
    print("sauvegarde : %s" % sauv)
    print()
    print("La section 1 gagne une colonne `flux` : informatif ou MUET.")
    print("Attendu sur tes donnees : MES informatif (p = 0,0005), YM")
    print("MUET (p = 0,87). Et le verdict de dissociation sera SUSPENDU")
    print("au lieu d annoncer une rotation que la mesure ne montre pas.")
    print()
    print("Relancer : python flux_contre_prix.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
