#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""orphelins.py -- ce que les redemarrages du pont n ont pas copie.

A LIRE A COTE DU PANNEAU
------------------------
Le panneau papers-live compte les affaires closes sur 18**09. Il ne peut
pas compter celles qui n y sont jamais arrivees. Quand le pont redemarre
en seance, les positions deja ouvertes a cet instant ne sont pas copiees
-- c est voulu, leur prix d entree appartient au passe -- et elles
disparaissent alors de la mesure sans laisser de ligne.

Le 27/08, la branche 6 a ouvert deux positions sur 6240004 a 15:24:15 et
15:24:16. Le pont est ne a 15:25:45. Le panneau a donc affiche zero
affaire pour 6240004, ce qui se lit "cette branche n a pas trade" alors
que la verite est "ces trades existent et personne ne les a copies".

Ce releve rend les deux cas distinguables.

    python orphelins.py               <- aujourd hui
    python orphelins.py --tout        <- toutes les sessions gardees
    python orphelins.py --jour 2026-08-27
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import os
import sys
import time

RACINE = r"C:\SVPS\Scalp-EA-main"
RELEVE = os.path.join(RACINE, "docs", "pont_miroirs", "orphelins.json")


def base_et_branche(magic):
    """La meme lecture que le panneau. On l importe s il est la."""
    try:
        import cartes_live
        return cartes_live.base_et_branche(magic)
    except Exception:
        pass
    m = int(magic)
    for prefixe, branche in ((4, 2), (5, 5), (6, 6)):
        bas = prefixe * 1000000 + 220000
        if bas <= m <= bas + 29999:
            return m - prefixe * 1000000, branche
    return m, 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--releve", default=RELEVE)
    ap.add_argument("--jour", default=time.strftime("%Y-%m-%d"))
    ap.add_argument("--tout", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.releve):
        print("Aucun releve : %s" % a.releve)
        print("")
        print("C est le cas normal tant que le pont n a pas redemarre depuis")
        print("que patch_pont_orphelins.py a ete pose. Le fichier nait au")
        print("premier demarrage de l envoyeur.")
        return 0
    try:
        with io.open(a.releve, encoding="utf-8") as f:
            sessions = (json.load(f).get("sessions") or [])
    except Exception as e:
        print("Releve illisible : %s" % str(e)[:120])
        return 2

    retenues = sessions if a.tout else [
        s for s in sessions if str(s.get("quand", "")).startswith(a.jour)]
    print("=" * 70)
    print("  ORPHELINES DU PONT   %s"
          % ("toutes sessions gardees" if a.tout else a.jour))
    print("=" * 70)
    if not retenues:
        print("  Aucun demarrage du pont %s."
              % ("enregistre" if a.tout else "ce jour-la"))
        print("  Un pont qui ne redemarre pas ne perce aucun trou : c est")
        print("  la bonne nouvelle que ce releve peut donner.")
        return 0

    total = collections.Counter()
    for s in retenues:
        print("")
        print("  demarrage %s -- %d position(s) non copiee(s)"
              % (s.get("quand", "?"), s.get("n", 0)))
        par = collections.Counter()
        for tk, d in (s.get("positions") or {}).items():
            b, br = base_et_branche(d.get("magic", 0) or 0)
            par[(b, br)] += 1
            total[(b, br)] += 1
        for (b, br), k in sorted(par.items()):
            print("      %-8d branche %d : %d" % (b, br, k))

    if len(retenues) > 1:
        print("")
        print("  --- total sur %d demarrage(s) ---" % len(retenues))
        for (b, br), k in sorted(total.items()):
            print("      %-8d branche %d : %d" % (b, br, k))

    print("")
    print("  Ces positions ont vecu sur le compte du moteur. Leur resultat")
    print("  n est nulle part dans le panneau : il n est ni gagnant ni")
    print("  perdant, il est absent. Un n de branche doit se lire en")
    print("  gardant ce compte en tete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
