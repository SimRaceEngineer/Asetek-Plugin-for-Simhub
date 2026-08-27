#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_rejoue_diag.py -- nommer la moitie manquante, et separer deux totaux.

DEUX DEFAUTS, REVELES PAR LA CORRECTION PRECEDENTE
--------------------------------------------------
1. LA MOITIE DE LA POPULATION EST ABSENTE, ET ON NE SAIT PAS POURQUOI
   Une fois le denominateur remis d aplomb, l essai du 27/08 a montre
   292 tickets sans deal sur 593 examines -- 49 %. Le rejeu tourne sur
   la moitie du monde et le panneau se contentait de le compter.

   Deux causes possibles, deux signatures differentes :

     - la fenetre d historique est trop courte : les absents se
       massent alors a UN BOUT de la periode ;
     - le `ticket` du journal n est pas le `position_id` de MT5 : les
       absents couvrent alors la MEME plage que les trouves.

   On ne choisit pas entre les deux, on les separe. Le panneau
   distingue desormais le ticket ABSENT de l historique du ticket
   present mais aux deals INCOMPLETS, croise les deux ensembles, et
   donne la plage de dates de chaque population.

2. DEUX TOTAUX DE PORTEES DIFFERENTES SUR LA MEME PAGE
   La table par magic n affiche que les magics ayant au moins --min-n
   prises rejouees ; le tableau de la queue porte sur TOUTES les
   prises. Leurs totaux ne parlent donc pas de la meme population --
   et sur la meme page, deux totaux se comparent tout seuls, et a
   tort. C est ainsi que TR 0.50R affichait +541 a un endroit et
   -9553 a l autre. Les deux sont justes ; ils ne repondaient pas a la
   meme question. Chaque table donne maintenant ses deux lignes,
   TOTAL affiches et TOUS MAGICS.

Ce patch ne touche pas a rejoue() ni a aucune politique. Les dix cas
du coeur repassent inchanges.

USAGE
-----
    python patch_rejoue_diag.py                 <- simulation
    python patch_rejoue_diag.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys
import time

CIBLE_DEFAUT = "rejoue_sorties.py"
MARQUEUR = "ts_absents"
TAILLE_AVANT = 25885
TAILLE_APRES = 28005

R = []

R.append((
'''    n_ok = n_sans_deal = n_sans_barre = n_sans_eurpt = n_sans_R = 0
    n_vus = 0''',
'''    n_ok = n_sans_deal = n_sans_barre = n_sans_eurpt = n_sans_R = 0
    n_absent = n_incomplet = 0
    ts_absents, ts_trouves = [], []
    n_vus = 0'''))

R.append((
'''        d = par_pos.get(tk)
        if not d:
            n_sans_deal += 1
            continue
        r = resume_position(mt5, d)
        if not r:
            n_sans_deal += 1
            continue''',
'''        d = par_pos.get(tk)
        if not d:
            # Le ticket n existe pas du tout dans l historique lu.
            n_absent += 1
            n_sans_deal += 1
            ts_absents.append(str(prises[0].get("ts") or ""))
            continue
        r = resume_position(mt5, d)
        if not r:
            # Il existe, mais sans entree ou sans sortie : position
            # encore ouverte, ou deals hors de la fenetre lue.
            n_incomplet += 1
            n_sans_deal += 1
            continue
        ts_trouves.append(str(prises[0].get("ts") or ""))'''))

R.append((
'''    dire("  sans deal retrouve     : %d" % n_sans_deal)''',
'''    dire("  sans deal retrouve     : %d" % n_sans_deal)
    dire("     absent de l historique : %d" % n_absent)
    dire("     deals incomplets       : %d" % n_incomplet)
    # D ou vient le manque ? Deux causes possibles, deux signatures
    # differentes -- on les separe au lieu de choisir.
    croise = len(set(besoin) & set(par_pos))
    dire("     tickets du journal presents dans l historique : %d / %d"
         % (croise, len(besoin)))
    if ts_absents:
        ts_absents.sort()
        dire("     absents, du %s au %s"
             % (ts_absents[0][:16] or "?", ts_absents[-1][:16] or "?"))
    if ts_trouves:
        ts_trouves.sort()
        dire("     trouves, du %s au %s"
             % (ts_trouves[0][:16] or "?", ts_trouves[-1][:16] or "?"))
    dire("     Si les absents couvrent la MEME plage que les trouves, ce")
    dire("     n est pas une fenetre trop courte : c est que le ticket du")
    dire("     journal n est pas le position_id de MT5. Si au contraire")
    dire("     ils se massent a un bout, il faut elargir --jours.")'''))

R.append((
'''        dire(barre("-"))
        ln = "%-7s %-22s %6s %9s" % ("", "TOTAL", "", "")
        for nom in choix:
            ln += " %+9.0f" % tot[nom]
        dire(ln)
        dire(barre("-"))''',
'''        dire(barre("-"))
        ln = "%-7s %-22s %6d %+9.0f" % ("", "TOTAL affiches",
                                        sum(t[1] for t in lignes),
                                        sum(t[2] for t in lignes))
        for nom in choix:
            ln += " %+9.0f" % tot[nom]
        dire(ln)
        # Le tableau de la queue porte sur TOUTES les prises rejouees,
        # celui-ci sur les seuls magics affiches. Deux totaux de portees
        # differentes sur la meme page se comparent tout seuls, et a
        # tort : on affiche donc les deux.
        ln = "%-7s %-22s %6d %+9.0f" % ("", "TOUS MAGICS",
                                        sum(vus_n.values()),
                                        sum(vus_pnl.values()))
        for nom in choix:
            ln += " %+9.0f" % sum(res[m][nom] for m in vus_n)
        dire(ln)
        dire(barre("-"))'''))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.cible):
        print("ABANDON : %s introuvable." % a.cible)
        return 2

    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        src = f.read()

    if MARQUEUR in src:
        print("DEJA POSE : le marqueur %s est present." % MARQUEUR)
        return 0
    if len(src) != TAILLE_AVANT:
        print("REFUS : %s fait %d octets, %d attendus."
              % (a.cible, len(src), TAILLE_AVANT))
        print("Pose d abord patch_rejoue_controles.py, ou verifie la copie.")
        return 3

    neuf = src
    for i, (old, new) in enumerate(R, 1):
        n = neuf.count(old)
        if n != 1:
            print("REFUS : ancre %d attendue 1 fois, trouvee %d." % (i, n))
            return 4
        neuf = neuf.replace(old, new, 1)

    try:
        compile(neuf, a.cible, "exec")
    except SyntaxError as e:
        print("REFUS : le resultat ne compile pas -- ligne %s : %s"
              % (e.lineno, e.msg))
        return 5
    if len(neuf) != TAILLE_APRES:
        print("REFUS : le resultat fait %d octets, %d attendus."
              % (len(neuf), TAILLE_APRES))
        return 6

    print("%d ancre(s) posee(s), resultat compile, taille exacte." % len(R))
    print("  %d -> %d octets" % (len(src), len(neuf)))
    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancez avec --appliquer.")
        return 0

    sauve = "%s.avant_diag_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.cible, sauve)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        relu = f.read()
    ok = (MARQUEUR in relu) and (len(relu) == TAILLE_APRES)
    print("")
    print("sauvegarde  : %s" % os.path.basename(sauve))
    print("VERIFICATION : %s" % ("ok" if ok else "ECHEC"))
    if not ok:
        shutil.copy2(sauve, a.cible)
        print("Le fichier a ete REMIS dans son etat d origine.")
        return 7
    return 0


if __name__ == "__main__":
    sys.exit(main())
