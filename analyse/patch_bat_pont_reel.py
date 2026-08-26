#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_bat_pont_reel.py -- le pont doit partir en REEL, pas en simulation

  python patch_bat_pont_reel.py               simulation, n ecrit rien
  python patch_bat_pont_reel.py --appliquer   ecrit, apres sauvegarde

LE DEFAUT, ET IL EST DE MOI
    Le bloc RELANCE_COMPLETE que j ai ajoute au .bat le 25/08 lance :

        start "Pont Miroirs" /MIN cmd /c "%PROJ%PONT_MIROIRS.cmd"

    Or PONT_MIROIRS.cmd le dit dans son en-tete, lignes 16-17 :

        PONT_MIROIRS.cmd          simulation -- aucun ordre
        PONT_MIROIRS.cmd reel     les ordres partent

    Sans argument, le pont tourne donc en SIMULATION. Il lit les
    positions miroir, annonce ce qu il ferait, et n envoie rien. Le
    26/08 a 15:10 il a ainsi "ouvert" quatre positions sur le compte
    dedie qui n ont jamais existe :

        [envoyeur]   [SIMULATION] ouvrir SPX500 SELL 1.28 @ 7671.35

    La branche de secours que j avais ecrite juste en dessous passe
    bien --reel, mais elle ne sert que si PONT_MIROIRS.cmd est absent.
    C est le chemin principal qui s execute, et c est lui qui etait
    faux.

CE QUE FAIT CE PATCH
    Il ajoute l argument reel a cette seule ligne, et passe par "call"
    -- forme robuste quand le chemin contient des espaces, ce qui est
    le cas de %PROJ%.

CE QU IL NE FAIT PAS
    Il ne reecrit aucune autre ligne. Ce fichier contient un mot de
    passe applicatif Gmail : le patch le lit en latin-1, ne touche qu a
    la ligne visee, et reecrit le reste octet pour octet. La fin de
    ligne d origine, CRLF ou LF, est conservee.

IDEMPOTENT : si la ligne porte deja reel, il ne fait rien.
"""
import argparse
import io
import os
import shutil
import sys
import time

CIBLE = "START_TRADING_STACK_V3.bat"
JETON = "PONT_MIROIRS.cmd"
LANCE = "cmd /c"


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

    vises = [i for i, l in enumerate(lignes)
             if JETON in l and LANCE in l and "rem " not in l.lower()]
    if not vises:
        print("ABANDON : aucune ligne qui LANCE %s." % JETON)
        print("  (les lignes echo ou rem ne comptent pas)")
        return 2
    if len(vises) > 1:
        print("ABANDON : %d lignes de lancement au lieu d une." % len(vises))
        for i in vises:
            print("  ligne %d : %s" % (i + 1, lignes[i].strip()))
        return 2

    i = vises[0]
    ligne = lignes[i]
    fin = "\r" if ligne.endswith("\r") else ""
    corps = ligne[:-1] if fin else ligne

    if " reel" in corps:
        print("DEJA FAIT : la ligne %d porte deja l argument reel." % (i + 1))
        print("  %s" % corps.strip())
        return 0

    creux = corps[:len(corps) - len(corps.lstrip())]
    # On reconstruit la ligne au lieu de bricoler l ancienne : "call" doit
    # se placer AVANT le chemin, et l argument APRES, guillemets compris.
    neuf_corps = (creux + 'start "Pont Miroirs" /MIN cmd /c call '
                          '"%PROJ%PONT_MIROIRS.cmd" reel')

    print("")
    print("ligne %d" % (i + 1))
    print("  avant : %s" % corps.strip())
    print("  apres : %s" % neuf_corps.strip())
    print("")

    if not a.appliquer:
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer pour ecrire.")
        return 0

    lignes[i] = neuf_corps + fin
    neuf = "\n".join(lignes)

    sauve = "%s.avant_pont_reel_%s" % (a.fichier, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    with io.open(a.fichier, "w", encoding="latin-1", newline="") as f:
        f.write(neuf)

    with io.open(a.fichier, encoding="latin-1", newline="") as f:
        relu = f.read()
    ecart = len(relu.encode("latin-1")) - len(texte.encode("latin-1"))
    attendu = len(neuf_corps) - len(corps)
    ok = (relu == neuf and ecart == attendu
          and 'PONT_MIROIRS.cmd" reel' in relu)
    print("sauvegarde   : %s" % sauve)
    print("ecart taille : %+d octets (attendu %+d)" % (ecart, attendu))
    print("VERIFICATION : %s"
          % ("ok" if ok else "ECHEC -- restaurer la sauvegarde"))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
