# -*- coding: utf-8 -*-
"""
panels_auto.py -- rafraichir les panneaux tout seul, toutes les N minutes

  python panels_auto.py
  python panels_auto.py --minutes 15 --dest panels

POURQUOI

    Les panneaux du REPL ne se mettaient a jour que si quelqu un lancait
    rails_join puis export_panels a la main. Resultat le 12/08 : a 16h45
    le REPL raisonnait encore sur l export de 13h38, avec assurance, et
    rien n indiquait que ses chiffres avaient trois heures.

    Ce script fait tourner les deux, en boucle. Avec patch_repl_frais --
    qui fait relire les fichiers au REPL des qu ils changent -- le REPL
    voit des donnees d au plus N minutes, sans redemarrage.

    Les deux sont necessaires et ne se remplacent pas : celui-ci rend les
    DONNEES fraiches, l autre rend la LECTURE fraiche.

CE QU IL FAIT, DANS L ORDRE

    1. rails_join.py     joint config_*.jsonl et series_*.jsonl
                         -> tickets_rails.jsonl
    2. export_panels.py  regenere les quatre panneaux en texte

    L ordre compte : exporter avant de joindre produirait des panneaux
    sur le corpus de la veille.

CE QU IL COUTE

    rails_join relit ~430 000 lignes de series, export_panels autant pour
    l orderflow. Compter deux a trois minutes par cycle. A 15 minutes
    d intervalle, la machine travaille environ un cinquieme du temps --
    sur six coeurs dont deux utilises, ca passe. En dessous de 10
    minutes, le cycle suivant demarrerait avant la fin du precedent : le
    script REFUSE un intervalle plus court.

CE QU IL NE FAIT PAS

    Aucun ordre, aucune position, aucune modification du moteur. Il lance
    deux scripts d analyse qui ecrivent des fichiers, rien d autre.

    Il n ecrit pas non plus par-dessus un export en cours : chaque cycle
    attend la fin du precedent avant de recommencer.

A LANCER une fois, dans sa propre fenetre. Ctrl+C pour arreter.
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

MINUTES = 15
MINI = 10
DEST = "panels"


def maintenant():
    return datetime.now().strftime("%H:%M:%S")


def lancer(argv, delai):
    """(ok, resume). Ne leve jamais : la boucle doit survivre a tout."""
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable] + argv, capture_output=True,
                           text=True, timeout=delai)
    except subprocess.TimeoutExpired:
        return False, "delai de %d s depasse" % delai
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, e)
    d = time.time() - t0
    if r.returncode != 0:
        court = (r.stderr or r.stdout or "").strip().split("\n")[-1][:120]
        return False, "code %d en %.0f s : %s" % (r.returncode, d, court)
    return True, "%.0f s" % d


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--minutes", type=float, default=MINUTES)
    p.add_argument("--dest", default=DEST)
    p.add_argument("--delai", type=int, default=600,
                   help="delai maximum par script, en secondes")
    a = p.parse_args()

    if a.minutes < MINI:
        print("KO : %g minutes, c est trop court." % a.minutes)
        print("Un cycle dure deux a trois minutes ; en dessous de %d le"
              % MINI)
        print("suivant demarrerait avant la fin du precedent.")
        return 1

    for f in ("rails_join.py", "export_panels.py"):
        if not os.path.isfile(f):
            print("KO : %s introuvable -- lance depuis le dossier de la"
                  " stack." % f)
            return 1

    print("=" * 72)
    print(" SCALP-EA / RAFRAICHISSEMENT AUTOMATIQUE DES PANNEAUX")
    print("=" * 72)
    print("intervalle : %g minutes" % a.minutes)
    print("destination : %s" % a.dest)
    print()
    print("rails_join puis export_panels, dans cet ordre.")
    print("Aucun ordre n est envoye. Ctrl+C pour arreter.")
    print()

    n = 0
    try:
        while True:
            n += 1
            t0 = time.time()
            ok1, r1 = lancer(["rails_join.py"], a.delai)
            print("[%s] cycle %d  rails_join   : %s"
                  % (maintenant(), n, r1 if ok1 else "ECHEC -- " + r1))
            if ok1:
                ok2, r2 = lancer(["export_panels.py", "--dest", a.dest],
                                 a.delai)
                print("[%s] cycle %d  export      : %s"
                      % (maintenant(), n, r2 if ok2 else "ECHEC -- " + r2))
            else:
                # Exporter sur un corpus non joint donnerait des panneaux
                # de la veille en se taisant. On prefere sauter le tour.
                print("[%s] cycle %d  export SAUTE : la jointure a echoue,"
                      " un export ici afficherait le corpus de la veille."
                      % (maintenant(), n))

            reste = a.minutes * 60 - (time.time() - t0)
            if reste > 0:
                time.sleep(reste)
            else:
                print("[%s] le cycle a dure plus que l intervalle"
                      " -- on enchaine sans pause." % maintenant())
    except KeyboardInterrupt:
        print()
        print("Arret demande apres %d cycle(s)." % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
