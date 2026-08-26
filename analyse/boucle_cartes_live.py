#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""boucle_cartes_live.py -- cartes_live cesse de vieillir

  python boucle_cartes_live.py                    boucle, 60 s
  python boucle_cartes_live.py --cadence 120
  python boucle_cartes_live.py --tours 1          un seul passage, pour essayer

POURQUOI
    cartes_live.py n a jamais ete dans une boucle : c est un outil qu on
    lance a la main. Le 26/08 a 18:05, ses deux sorties portaient encore
    l horodatage 25/08 22:30:26 -- le dernier lancement manuel, vingt
    heures plus tot. La page servie par /carte?f=cartes_live.html etait
    donc figee, y compris sa mention "instantane depose il y a 3 s", qui
    decrivait l etat du monde a 22:30:26 la veille.

    Une page qui affiche une fraicheur figee est pire qu une page
    absente : elle a l air vivante. C est la troisieme fois de la
    journee que ce piege coute une heure.

CE QU ELLE FAIT
    Elle relance cartes_live.py toutes les N secondes, et journalise a
    chaque tour le code de retour, la duree, et surtout la DATE DU
    FICHIER produit. Ce dernier point est le seul qui prouve que la
    sortie bouge : un code de retour a zero sur un script qui n ecrit
    rien vaut zero.

    En cas d echec elle continue -- une erreur passagere de MT5 ou un
    fichier verrouille ne doit pas arreter la boucle -- mais elle
    recopie la derniere ligne d erreur dans le journal, ce qui evite
    d avoir a deviner plus tard.

    Elle n envoie aucun ordre et ne touche a aucune position.
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import time

SORTIE_TEMOIN = os.path.join("cartes", "cartes_live.html")


def horo(chemin):
    try:
        return time.strftime("%m-%d %H:%M:%S",
                             time.localtime(os.path.getmtime(chemin)))
    except Exception:
        return "absent"


def dire(journal, msg):
    ligne = "%s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(ligne, flush=True)
    try:
        d = os.path.dirname(journal)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(journal, "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
    except Exception:
        pass                    # un journal qui tombe n arrete pas la boucle


def derniere_ligne(txt):
    for l in reversed((txt or "").splitlines()):
        if l.strip():
            return l.strip()[:160]
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--script", default="cartes_live.py")
    ap.add_argument("--cadence", type=int, default=60)
    ap.add_argument("--tours", type=int, default=0, help="0 = sans fin")
    ap.add_argument("--temoin", default=SORTIE_TEMOIN)
    ap.add_argument("--journal",
                    default=os.path.join("logs", "boucle_cartes_live.log"))
    ap.add_argument("--sup", default="",
                    help="arguments supplementaires passes au script")
    a = ap.parse_args()

    if not os.path.exists(a.script):
        print("ABANDON : %s introuvable dans %s" % (a.script, os.getcwd()))
        return 2

    supp = [x for x in a.sup.split() if x]
    dire(a.journal, "boucle demarree : %s %s, cadence %d s"
         % (a.script, " ".join(supp), a.cadence))
    dire(a.journal, "  temoin : %s (date actuelle %s)"
         % (a.temoin, horo(a.temoin)))

    tour = 0
    while True:
        tour += 1
        deb = time.time()
        avant = horo(a.temoin)
        try:
            p = subprocess.run([sys.executable, a.script] + supp,
                               capture_output=True, timeout=300)
            code = p.returncode
            err = derniere_ligne((p.stderr or b"").decode("utf-8", "replace"))
        except subprocess.TimeoutExpired:
            code, err = -1, "delai de 300 s depasse"
        except Exception as e:
            code, err = -2, str(e)[:160]
        duree = time.time() - deb
        apres = horo(a.temoin)

        etat = "ok" if code == 0 else ("ECHEC code %s" % code)
        bouge = "ecrit" if apres != avant else "INCHANGE"
        dire(a.journal, "tour %d : %s en %.1f s -- %s %s"
             % (tour, etat, duree, a.temoin, bouge))
        if code != 0 and err:
            dire(a.journal, "    %s" % err)
        elif apres == avant:
            # Un code zero sur une sortie qui ne bouge pas est le pire cas :
            # tout a l air normal et rien n est produit.
            dire(a.journal, "    code 0 mais le fichier n a pas change -- %s"
                 % (err or "sortie muette"))

        if a.tours and tour >= a.tours:
            dire(a.journal, "fin apres %d tour(s)" % tour)
            return 0
        reste = a.cadence - (time.time() - deb)
        if reste > 0:
            time.sleep(reste)


if __name__ == "__main__":
    sys.exit(main())
