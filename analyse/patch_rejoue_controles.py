#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_rejoue_controles.py -- trois defauts de LECTURE du rejeu.

Le moteur de rejoue_sorties.py est intact : les dix cas verifies a la
main repassent tous. Ce qui etait faux, c est la facon de PRESENTER et
de CONTROLER, et l un des trois defauts etait dans mon propre garde-fou.

1. LE CONTROLE DU MFE COMPARAIT DEUX ECHELLES DE LOT
   `mb` etait le MFE des barres converti avec l eur_pt du TICKET reel.
   `mj` etait le MFE du journal, qui porte deja le lot du PAPER. La
   mediane de 1.35 du 27/08 mesurait donc mon erreur autant que les
   donnees, et faisait echouer le controle sur une difference qui n
   existait pas. Il se fait desormais EN POINTS, ou la question a un
   sens.

2. LA TABLE COMPARAIT UN ECART PARTIEL A UNE REFERENCE COMPLETE
   Les colonnes n et PnL venaient du journal ENTIER, en face d ecarts
   calcules sur les seuls tickets rejoues. En mode essai, 300 tickets
   rejoues s affichaient en face de 1289 prises. Les deux colonnes
   portent maintenant sur ce qui a reellement ete rejoue.

3. LA POPULATION PERDUE ETAIT RAPPORTEE AU MAUVAIS DENOMINATEUR
   Elle etait divisee par ce que le journal cite et non par ce qui a
   ete examine : en mode essai elle paraissait dix fois plus petite
   qu elle n est. Et --limite le dit maintenant en toutes lettres.

Ce patch ne touche pas a rejoue() ni a aucune politique.

USAGE
-----
    python patch_rejoue_controles.py                 <- simulation
    python patch_rejoue_controles.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys
import time

CIBLE_DEFAUT = "rejoue_sorties.py"
MARQUEUR = "mb_pts"
TAILLE_AVANT = 24652
TAILLE_APRES = 25885

R = []

R.append((
'''        # controle croise du MFE : les barres et le journal disent-ils
        # la meme chose ?
        mb = mfe_des_barres(bars, sens, entree) * abs(eur_pt)
        mj = max(abs(p.get("mfe") or 0.0) for p in prises)
        if mj > 1e-6 and mb > 1e-6:
            mfe_ratio.append(mb / mj)

''',
'''        # Controle croise du MFE, EN POINTS. Le comparer en euros
        # revenait a confronter deux echelles de lot : les barres
        # donnent un prix, le journal porte deja le lot du paper.
        # C etait mon erreur du 27/08, et elle faisait echouer le
        # controle sur une difference qui n existait pas.
        mb_pts = mfe_des_barres(bars, sens, entree)

'''))

R.append((
'''            r_pts = Re / abs(ep)
            dd = {}''',
'''            r_pts = Re / abs(ep)
            mj_pts = abs(p.get("mfe") or 0.0) / abs(ep)
            if mj_pts > 1e-9 and mb_pts > 1e-9:
                mfe_ratio.append(mb_pts / mj_pts)
            vus_n[m] = vus_n.get(m, 0) + 1
            vus_pnl[m] = vus_pnl.get(m, 0.0) + p["pnl"]
            dd = {}'''))

R.append((
'''    n_ok = n_sans_deal = n_sans_barre = n_sans_eurpt = n_sans_R = 0''',
'''    n_ok = n_sans_deal = n_sans_barre = n_sans_eurpt = n_sans_R = 0
    n_vus = 0
    vus_n, vus_pnl = {}, {}     # ce qui a REELLEMENT ete rejoue'''))

R.append((
'''    for tk, prises in besoin.items():
        d = par_pos.get(tk)
        if not d:''',
'''    for tk, prises in besoin.items():
        n_vus += 1
        d = par_pos.get(tk)
        if not d:'''))

R.append((
'''    perdus = n_sans_deal + n_sans_barre + n_sans_eurpt
    part = 100.0 * perdus / max(1, len(besoin))
    dire("  population perdue      : %d / %d  (%.1f %%)"
         % (perdus, len(besoin), part))''',
'''    perdus = n_sans_deal + n_sans_barre + n_sans_eurpt
    # Le denominateur est ce qu on a EXAMINE, pas ce que le journal
    # cite : en mode essai la boucle s arrete avant la fin, et
    # rapporter la perte sur la population entiere la ferait paraitre
    # dix fois plus petite qu elle n est.
    part = 100.0 * perdus / max(1, n_vus)
    dire("  population perdue      : %d / %d examine(s)  (%.1f %%)"
         % (perdus, n_vus, part))
    if a.limite:
        dire("")
        dire("  !! MODE ESSAI : --limite %d. %d ticket(s) examines sur"
             % (a.limite, n_vus))
        dire("     %d cites par le journal. Les totaux ci-dessous ne sont"
             % len(besoin))
        dire("     PAS ceux du mois. Relancer sans --limite pour conclure.")'''))

R.append((
'''    lignes = [(m, pp) for m, pp in par_magic.items() if len(pp) >= a.min_n]
    lignes.sort(key=lambda t: -len(t[1]))''',
'''    # On affiche l effectif et le PnL des prises REJOUEES, pas ceux du
    # journal entier : comparer un ecart partiel a une reference
    # complete donnerait un rapport faux sans en avoir l air.
    lignes = [(m, vus_n[m], vus_pnl[m]) for m in vus_n
              if vus_n[m] >= a.min_n]
    lignes.sort(key=lambda t: -t[1])'''))

R.append((
'''        e = "%-7s %-22s %6s %9s" % ("MAGIC", "PAPER", "n", "PnL reel")''',
'''        e = "%-7s %-22s %6s %9s" % ("MAGIC", "PAPER", "n rej", "PnL rej")'''))

R.append((
'''        for m, pp in lignes:
            reel = sum(p["pnl"] for p in pp)
            ln = "%-7s %-22s %6d %+9.0f" % (m, (noms.get(m) or "")[:22],
                                            len(pp), reel)''',
'''        for m, nn, reel in lignes:
            ln = "%-7s %-22s %6d %+9.0f" % (m, (noms.get(m) or "")[:22],
                                            nn, reel)'''))

R.append((
'''        dire("  Ecart de PnL en EUR contre la sortie reelle. Le stop ne")
        dire("  recule jamais : c est le cliquet, par construction.")''',
'''        dire("  n rej / PnL rej : effectif et PnL des prises REJOUEES.")
        dire("  L ecart se compare a cette colonne-la, pas au mois entier.")
        dire("  Le stop ne recule jamais : c est le cliquet.")'''))


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
        print("Ce n est pas la version que ce patch sait corriger.")
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

    sauve = "%s.avant_controles_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
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
