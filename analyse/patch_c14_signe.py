#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_c14_signe.py -- un gain verrouille n est pas un pinch

  python patch_c14_signe.py               simulation, n ecrit rien
  python patch_c14_signe.py --appliquer

LE DEFAUT
    buddha_clause_gate.py, dans _c14_check_sl_mod :

        prox = C14_BE_PROXIMITY.get(asset, 0.0)
        dist_to_entry = abs(float(new_sl) - entry)
        if dist_to_entry > prox:
            return True, "trail_far_from_entry", snap

    La distance est prise en VALEUR ABSOLUE. Un stop pose quinze points
    AU-DESSUS de l entree -- un gain mis a l abri -- et un stop pose
    quinze points en dessous -- une perte -- tombent donc sous le meme
    veto. Avec C14_BE_PROXIMITY a 20 points sur US30 et US100, cela
    interdit de proteger quoi que ce soit tant que la position n a pas
    parcouru vingt points, et interdit le breakeven purement et
    simplement.

CE QUE LA MESURE DIT
    bilan_c14.py, le 26/08, sur la seance entiere : 18 466 refus, 472
    positions rejouees barre M1 par barre M1, le verrou se declenche sur
    100 % d entre elles.

        argent SAUVE  : +5877.76 EUR sur 287 positions
        argent COUTE  : -2687.34 EUR sur 184 positions
        NET           : +3190.42 EUR, soit +6.76 par position

    Positif sur les trois actifs, sur les trois avis de Buddha, dans les
    deux sens. Pas une decoupe ou le veto aide. Les deux echantillons de
    blocks.jsonl depouilles donnaient par ailleurs 100 % de refus portant
    sur un stop qui verrouillait un gain.

CE QUE FAIT CE PATCH
    Il rend la distance SIGNEE. Un stop qui met la position a l abri --
    au-dela de l entree dans le sens du trade -- passe sans discussion.
    Un stop qui se rapproche de l entree PAR LE BAS reste soumis au veto
    d origine, bande et clause Buddha comprises : l intention de
    l auteur, empecher un breakeven premature en pleine tendance, est
    conservee la ou elle a un sens.

    Une seule insertion, entre le calcul de prox et celui de
    dist_to_entry. Aucune autre ligne n est touchee.

CE QU IL NE FAIT PAS
    Il ne rebranche pas sl_arbitre, qui est hors de la chaine. Or le
    +3190 a ete calcule en appliquant aux niveaux refuses une suite
    MONOTONE -- un stop qui ne recule jamais. Ce patch seul ouvre
    l avance sans fermer le recul : la ligne "if not tighten: return
    True" laisse toujours passer un stop qui s elargit. Les deux vont
    ensemble.

    Et il ne prend effet qu au redemarrage du moteur : un processus
    Python ne relit pas son fichier apres son demarrage.

IDEMPOTENT.
"""
import argparse
import io
import os
import shutil
import sys
import time

CIBLE = "buddha_clause_gate.py"
ANCRE = 'prox = C14_BE_PROXIMITY.get(asset, 0.0)'
SUITE = 'dist_to_entry = abs(float(new_sl) - entry)'
MARQUE = "verrouille_un_gain"

BLOC = [
    '# 27/08 : la distance etait prise en VALEUR ABSOLUE, donc un stop',
    '# pose 15 points AU-DESSUS de l entree -- un gain verrouille -- et',
    '# un stop pose 15 points en dessous -- une perte -- tombaient sous',
    '# le meme veto. Mesure du 26/08 par bilan_c14 : 472 positions',
    '# rejouees barre par barre, 18 466 refus, 100 % portant sur un',
    '# verrouillage de gain, +3190 EUR nets en faveur du passage,',
    '# positif sur les trois actifs et les trois avis de Buddha.',
    '# On rend donc la distance SIGNEE. Le veto d origine reste entier',
    '# du cote PERTE, ou son intention -- pas de breakeven premature en',
    '# pleine tendance -- garde un sens.',
    'marge_gain = ((float(new_sl) - entry) if pos_dir == "BUY"',
    '              else (entry - float(new_sl)))',
    'if marge_gain >= 0.0:',
    '    snap["marge_gain"] = round(marge_gain, 3)',
    '    snap["decision"] = "verrouille_un_gain"',
    '    return True, "verrouille_un_gain", snap',
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fichier", default=CIBLE)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.fichier):
        print("ABANDON : %s introuvable dans %s" % (a.fichier, os.getcwd()))
        return 2

    with io.open(a.fichier, encoding="latin-1", newline="") as f:
        texte = f.read()
    lignes = texte.split("\n")
    print("%s : %d lignes, %d octets"
          % (a.fichier, len(lignes), len(texte.encode("latin-1"))))

    if MARQUE in texte:
        print("DEJA PATCHE : la marque %s est presente. Rien a faire." % MARQUE)
        return 0

    vus = [i for i, l in enumerate(lignes) if l.rstrip("\r").strip() == ANCRE]
    if len(vus) != 1:
        print("ABANDON : %d ligne(s) '%s' au lieu d une seule." % (len(vus), ANCRE))
        for i in vus:
            print("  ligne %d" % (i + 1))
        return 2
    i = vus[0]

    # La ligne SUIVANTE doit bien etre le calcul en valeur absolue : si le
    # fichier deploye differe de celui que j ai lu, on ne devine pas.
    j = i + 1
    while j < len(lignes) and not lignes[j].strip():
        j += 1
    if j >= len(lignes) or lignes[j].rstrip("\r").strip() != SUITE:
        print("ABANDON : la ligne qui suit l ancre n est pas celle attendue.")
        print("  attendu : %s" % SUITE)
        print("  trouve  : %s" % (lignes[j].strip() if j < len(lignes) else "fin"))
        return 2

    ligne = lignes[i]
    fin = "\r" if ligne.endswith("\r") else ""
    corps = ligne[:-1] if fin else ligne
    creux = corps[:len(corps) - len(corps.lstrip())]
    bloc = [creux + x + fin for x in BLOC]

    print("")
    print("ligne %d, insertion de %d ligne(s) apres :" % (i + 1, len(bloc)))
    print("    %s" % corps.strip())
    for b in bloc:
        print("  + %s" % b.rstrip())
    print("")
    print("la ligne suivante, inchangee :")
    print("    %s" % lignes[j].strip())
    print("")

    if not a.appliquer:
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer pour ecrire.")
        return 0

    lignes[i + 1:i + 1] = bloc
    neuf = "\n".join(lignes)
    sauve = "%s.avant_c14_signe_%s" % (a.fichier, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    with io.open(a.fichier, "w", encoding="latin-1", newline="") as f:
        f.write(neuf)
    with io.open(a.fichier, encoding="latin-1", newline="") as f:
        relu = f.read()
    ok = relu == neuf and MARQUE in relu
    print("sauvegarde   : %s" % sauve)
    print("ecart taille : %+d octets"
          % (len(relu.encode("latin-1")) - len(texte.encode("latin-1"))))
    print("VERIFICATION : %s" % ("ok" if ok else "ECHEC -- restaurer la sauvegarde"))
    print("")
    print("Sans effet tant que le moteur n a pas redemarre.")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
