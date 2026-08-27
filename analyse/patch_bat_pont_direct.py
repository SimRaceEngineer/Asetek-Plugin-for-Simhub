#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_bat_pont_direct.py -- le pont et le panneau survivent au redemarrage

  python patch_bat_pont_direct.py               simulation
  python patch_bat_pont_direct.py --appliquer

DEUX MANQUES, TOUS DEUX CONSTATES
    1. Le pont n est pas relance. La ligne

           start "Pont Miroirs" /MIN cmd /c call "%PROJ%PONT_MIROIRS.cmd" reel

       ne lance rien. Constate trois fois le 27/08 : le bloc s execute
       bien -- miroir_papers en sort a 09:09:06 -- et le pont reste
       absent. Il etait mort depuis 07:50, compte.json fige a 07:49:58,
       et le compte miroir muet toute la matinee sans que rien ne le
       dise. La branche de secours juste en dessous, elle, marche : on
       l a lancee a la main a 09:36 et les deux roles ont demarre.

       On supprime donc l intermediaire et on lance les deux roles
       directement. Le delai entre eux passe de 3 a 15 secondes :
       l envoyeur consomme l instantane du lecteur, qui doit avoir eu
       le temps de s attacher a son terminal.

    2. La boucle du panneau n y figure pas. cartes_live.py n est dans
       aucune boucle, et le .bat commence par tuer les instances
       precedentes : chaque redemarrage regele donc le panneau, qui
       continue d afficher une page ancienne avec l air d etre vivante.
       Le 27/08 il est reste fige a 07:49 pendant deux heures.

CE QU IL NE FAIT PAS
    Il ne touche a aucune autre ligne. Ce fichier contient un mot de
    passe applicatif : lecture et ecriture en latin-1, fin de ligne
    d origine conservee, et seule la tranche visee est remplacee.

IDEMPOTENT.
"""
import argparse
import io
import os
import shutil
import sys
import time

CIBLE = "START_TRADING_STACK_V3.bat"
MARQUE = "on ne passe plus par PONT_MIROIRS.cmd"
DEBUT = 'if exist "%PROJ%PONT_MIROIRS.cmd" ('

NEUF = [
    'rem 27/08 : on ne passe plus par PONT_MIROIRS.cmd. La ligne',
    'rem   start "Pont Miroirs" /MIN cmd /c call "...PONT_MIROIRS.cmd" reel',
    'rem ne lancait rien -- constate trois fois : le bloc s execute bien,',
    'rem miroir_papers en sort, et le pont reste absent. Il etait mort',
    'rem depuis 07:50, compte.json fige, le compte miroir muet toute la',
    'rem matinee. On lance donc les deux roles directement, forme dont on',
    'rem a la preuve qu elle marche. 15 s entre les deux et non 3 :',
    'rem l envoyeur consomme l instantane du lecteur.',
    'if exist "%PROJ%pont_miroirs.py" (',
    '    echo   + pont_miroirs --lecteur',
    '    start "Pont Lecteur" /MIN cmd /c %PY% "%PROJ%pont_miroirs.py" --lecteur',
    '    timeout /t 15 /nobreak >nul 2>&1',
    '    echo   + pont_miroirs --envoyeur --compte %CPT_MIROIR% --reel',
    '    start "Pont Envoyeur" /MIN cmd /c %PY% "%PROJ%pont_miroirs.py" --envoyeur --compte %CPT_MIROIR% --reel',
    ') else ( echo   ! pont_miroirs.py ABSENT )',
    '',
    'rem 27/08 : la boucle du panneau. cartes_live.py n est dans aucune',
    'rem boucle et le .bat tue les instances precedentes : sans cette',
    'rem ligne, chaque redemarrage regele la page, qui continue d afficher',
    'rem un rendu ancien avec l air d etre vivante.',
    'if exist "%PROJ%boucle_cartes_live.py" (',
    '    echo   + boucle_cartes_live   ^(le panneau cesse de vieillir^)',
    '    start "Boucle Cartes" /MIN cmd /c %PY% "%PROJ%boucle_cartes_live.py" --cadence 60',
    ') else ( echo   ! boucle_cartes_live.py ABSENT )',
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
        print("DEJA PATCHE. Rien a faire.")
        return 0

    vus = [i for i, l in enumerate(lignes) if l.rstrip("\r").strip() == DEBUT]
    if len(vus) != 1:
        print("ABANDON : %d ligne(s) '%s' au lieu d une." % (len(vus), DEBUT))
        return 2
    i = vus[0]

    # La tranche fait douze lignes. On verifie sa forme avant d y toucher :
    # un fichier deploye qui differerait ne doit pas etre devine.
    fin = i + 11
    if fin >= len(lignes):
        print("ABANDON : le fichier s arrete avant la fin du bloc.")
        return 2
    controles = [(i + 2, 'PONT_MIROIRS.cmd" reel'),
                 (i + 4, '%PROJ%pont_miroirs.py"'),
                 (i + 9, "--envoyeur")]
    for n, attendu in controles:
        if attendu not in lignes[n]:
            print("ABANDON : la ligne %d ne contient pas %r." % (n + 1, attendu))
            print("  trouve : %s" % lignes[n].strip())
            return 2
    if lignes[fin].rstrip("\r").strip() != ")":
        print("ABANDON : la ligne %d devrait fermer le bloc, elle contient : %s"
              % (fin + 1, lignes[fin].strip()))
        return 2

    ligne0 = lignes[i]
    fin_l = "\r" if ligne0.endswith("\r") else ""
    corps = ligne0[:-1] if fin_l else ligne0
    creux = corps[:len(corps) - len(corps.lstrip())]
    bloc = [(creux + x if x else "") + fin_l for x in NEUF]

    print("")
    print("remplacement des lignes %d a %d (%d lignes) par %d :"
          % (i + 1, fin + 1, fin - i + 1, len(bloc)))
    print("")
    print("  AVANT")
    for n in range(i, fin + 1):
        print("    %s" % lignes[n].rstrip())
    print("")
    print("  APRES")
    for b in bloc:
        print("    %s" % b.rstrip())
    print("")

    if not a.appliquer:
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer pour ecrire.")
        return 0

    lignes[i:fin + 1] = bloc
    neuf = "\n".join(lignes)
    sauve = "%s.avant_pont_direct_%s" % (a.fichier, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    with io.open(a.fichier, "w", encoding="latin-1", newline="") as f:
        f.write(neuf)
    with io.open(a.fichier, encoding="latin-1", newline="") as f:
        relu = f.read()
    # 27/08 : la marque de controle doit etre absente du patch LUI-MEME.
    # Premier jet : je cherchais "PONT_MIROIRS.cmd\" reel", que mon propre
    # commentaire cite -- et le patch criait a l echec sur un fichier
    # parfaitement correct. Une fausse alerte est pire qu un echec net :
    # elle pousse a restaurer une sauvegarde inutilement. On vise donc
    # la forme REELLE de l appel, avec sa variable, que le commentaire
    # n emploie pas.
    ok = (relu == neuf and MARQUE in relu
          and "%PROJ%PONT_MIROIRS.cmd" not in relu)
    print("sauvegarde   : %s" % sauve)
    print("ecart taille : %+d octets"
          % (len(relu.encode("latin-1")) - len(texte.encode("latin-1"))))
    print("VERIFICATION : %s" % ("ok" if ok else "ECHEC -- restaurer la sauvegarde"))
    print("")
    print("Sans effet avant le prochain demarrage de la stack.")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
