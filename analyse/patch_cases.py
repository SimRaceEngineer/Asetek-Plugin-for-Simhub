# -*- coding: utf-8 -*-
r"""
patch_cases.py -- un verdict qui contredit sa propre table

  python patch_cases.py

LE DEFAUT

    Sortie reelle du 17/08, paire MES-continu x TICK-NYSE :

                            TICK-NYSE +    TICK-NYSE -
        MES-continu +                60              0
        MES-continu -                59              0

        Les quatre cases sont peuplees : le signe du CVD
        varie d une seance a l autre sur les deux symboles.

    Deux cases sont a ZERO, et la phrase juste en dessous affirme que
    les quatre sont peuplees. `TICK-NYSE` sort 130 seances positives
    sur 130 : son signe ne varie jamais.

    La cause : je testais la case DOMINANTE (`> 85 %`). Avec 60 et 59
    reparties sur une seule colonne, aucune case ne domine -- donc le
    code tombait dans la branche "tout va bien" sans jamais regarder
    combien de cases etaient reellement remplies.

    C est la meme faute que `bruit_par_actif` ce matin : un verdict
    calcule a cote de la table qu il pretend resumer.

LE CORRECTIF

    Compter les cases non vides, et le dire. Trois cas au lieu de deux :

        une case domine            -> deux fichiers qui derivent
        moins de quatre cases      -> un symbole a signe fige,
                                      la comparaison n a pas de sens
        quatre cases peuplees      -> le signe varie des deux cotes

    Et nommer le symbole figé, plutot que de laisser le lecteur
    recompter la table.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import io
import os
import shutil
import sys

CIBLE = "cvd_journalier.py"
MARQUE = "peuplees ="

A1 = '''            else:
                dis()
                dis("  Les quatre cases sont peuplees : le signe du CVD")
                dis("  varie d une seance a l autre sur les deux symboles.")
                dis("  Un desaccord observe un jour donne est alors un")
                dis("  fait de cette journee-la, pas une constante.")
'''
B1 = '''            else:
                # Compter les cases REELLEMENT remplies. Tester la case
                # dominante ne suffit pas : 60 et 59 repartis sur une
                # seule colonne ne font dominer personne, et deux cases
                # restent pourtant vides.
                peuplees = sum(1 for v in c.values() if v)
                figes = []
                for s in (sa, sb):
                    sg = set(x[0] > 0 for d, x in tables[s].items()
                             if d in communs)
                    if len(sg) < 2:
                        figes.append(s)
                dis()
                if peuplees < 4:
                    dis("  Seulement %d case(s) sur 4 sont peuplees."
                        % peuplees)
                    if figes:
                        dis("  %s ne change JAMAIS de signe sur ces"
                            % ", ".join(figes))
                        dis("  seances : son CVD ne mesure pas un")
                        dis("  desequilibre acheteur/vendeur, et comparer")
                        dis("  son signe a celui d un autre symbole n a")
                        dis("  pas de sens. Un indice n a pas de carnet.")
                    else:
                        dis("  Une combinaison de signes ne se produit")
                        dis("  jamais. Ce n est pas un tableau de")
                        dis("  contingence lisible.")
                else:
                    dis("  Les quatre cases sont peuplees : le signe du CVD")
                    dis("  varie d une seance a l autre sur les deux")
                    dis("  symboles. Un desaccord observe un jour donne est")
                    dis("  alors un fait de cette journee-la, pas une")
                    dis("  constante du fichier.")
'''

REMPLACEMENTS = [
    ("verdict de contingence fonde sur les cases remplies", A1, B1),
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

    sauv = CIBLE + ".avant_cases"
    if not os.path.isfile(sauv):
        shutil.copy2(CIBLE, sauv)
    io.open(CIBLE, "w", encoding="utf-8", newline="").write(out)

    print("%s : %d lignes -> %d lignes, %d remplacement."
          % (CIBLE, len(src.splitlines()), len(out.splitlines()),
             len(REMPLACEMENTS)))
    print("sauvegarde : %s" % sauv)
    print()
    print("Les paires impliquant TICK-NYSE diront desormais qu elles ne")
    print("sont pas lisibles. La paire MES x YM, elle, ne change pas :")
    print("ses quatre cases sont bien peuplees (32 / 21 / 34 / 23).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
