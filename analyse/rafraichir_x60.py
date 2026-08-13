# -*- coding: utf-8 -*-
"""
rafraichir_x60.py -- le panneau X60 toutes les 30 secondes

  python rafraichir_x60.py
  python rafraichir_x60.py --pas 30

POURQUOI UNE BOUCLE A PART

    panels_auto regenere le panneau x60 dans son cycle, mais ce cycle
    dure deux a trois minutes : rails_join relit ~430 000 lignes et
    export_panels autant. Impossible d y accrocher un rafraichissement
    a 30 secondes sans faire tourner tout le reste avec.

    Le panneau x60, lui, ne fait que relire deux .jsonl et mettre en
    page. C est instantane. Il merite sa propre boucle, et c est le
    seul cas de la stack ou un processus de plus se justifie : on veut
    voir les entrees x60 et le papier EN DIRECT, pas au quart d heure.

CE QU IL FAIT

    Appelle `python x60_onset.py --rapport` toutes les --pas secondes.
    Rien d autre. Il n ouvre aucun socket, n envoie aucun ordre, et ne
    touche qu un fichier : panels/panel_x60_onset.txt.

    Il ECRIT dans son journal quand un cycle echoue ou devient lent.
    Une boucle muette qui tourne dans le vide pendant une heure est ce
    qu on essaie precisement d eviter -- c est ce qui est arrive au
    panneau x60 le 13/08, fige a 09:58 sans que rien ne le signale.

POURQUOI CE N EST PAS DANGEREUX D AVOIR DEUX ECRIVAINS

    panels_auto continue d appeler le meme rapport toutes les 15
    minutes. Les deux ecrivent donc le meme fichier. C est sans danger
    A CONDITION que l ecriture soit atomique -- fichier temporaire puis
    renommage -- sinon un lecteur peut tomber sur un fichier a moitie
    ecrit. patch_x60_atomique s en charge ; ce script verifie qu il est
    applique et REFUSE de demarrer sinon, plutot que de creer une
    course dont le symptome serait un panneau tronque au hasard.

A LANCER en fenetre cachee. Ctrl+C pour arreter.
"""
import argparse
import io
import os
import subprocess
import sys
import time
from datetime import datetime

_ICI = os.path.dirname(os.path.abspath(__file__))
PAS = 30
LENT = 5.0          # secondes au-dela desquelles on le signale


def maintenant():
    return datetime.now().strftime("%H:%M:%S")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pas", type=int, default=PAS)
    p.add_argument("--sans-controle", action="store_true",
                   help="demarrer meme si l ecriture n est pas atomique")
    a = p.parse_args()

    cible = os.path.join(_ICI, "x60_onset.py")
    if not os.path.isfile(cible):
        print("KO : x60_onset.py introuvable a cote de ce script.")
        return 1

    # Deux ecrivains sur le meme fichier ne sont sans danger que si
    # l ecriture est atomique. Sans ca, panels_auto et cette boucle
    # peuvent se croiser et laisser un panneau a moitie ecrit.
    src = io.open(cible, encoding="utf-8", errors="replace").read()
    if ".tmp" not in src and not a.sans_controle:
        print("KO : x60_onset.py n ecrit pas son panneau de facon atomique.")
        print("     panels_auto ecrit le meme fichier toutes les 15 min ;")
        print("     sans ecriture atomique les deux peuvent se croiser et")
        print("     laisser un panneau tronque, au hasard.")
        print("     Applique patch_x60_atomique.py d abord.")
        print("     (--sans-controle force le demarrage, a tes risques.)")
        return 1

    print("=" * 72)
    print(" RAFRAICHISSEMENT DU PANNEAU X60")
    print("=" * 72)
    print("intervalle : %d secondes" % a.pas)
    print("appelle    : x60_onset.py --rapport")
    print("ecrit      : panels/panel_x60_onset.txt")
    print("Aucun ordre. Ctrl+C pour arreter.")
    print()

    n = lents = echecs = 0
    try:
        while True:
            n += 1
            t0 = time.time()
            try:
                r = subprocess.run([sys.executable, cible, "--rapport"],
                                   capture_output=True, text=True,
                                   timeout=max(60, a.pas * 2), cwd=_ICI)
                code = r.returncode
                fin = (r.stderr or r.stdout or "").strip().split("\n")[-1]
            except subprocess.TimeoutExpired:
                code, fin = -1, "delai depasse"
            except Exception as e:
                code, fin = -2, "%s: %s" % (type(e).__name__, e)
            d = time.time() - t0

            if code != 0:
                echecs += 1
                print("[%s] cycle %d ECHEC (code %s) : %s"
                      % (maintenant(), n, code, fin[:120]), flush=True)
            elif d > LENT:
                lents += 1
                print("[%s] cycle %d lent : %.1f s -- le panneau grossit,"
                      " l intervalle de %d s deviendra trop court"
                      % (maintenant(), n, d, a.pas), flush=True)
            elif n % 120 == 1:
                # Une ligne par heure : assez pour prouver qu il vit,
                # pas assez pour noyer le journal.
                print("[%s] cycle %d : %.2f s  (%d echec(s), %d lent(s)"
                      " depuis le demarrage)"
                      % (maintenant(), n, d, echecs, lents), flush=True)

            reste = a.pas - (time.time() - t0)
            if reste > 0:
                time.sleep(reste)
    except KeyboardInterrupt:
        print()
        print("Arret apres %d cycle(s), %d echec(s), %d lent(s)."
              % (n, echecs, lents))
    return 0


if __name__ == "__main__":
    sys.exit(main())
