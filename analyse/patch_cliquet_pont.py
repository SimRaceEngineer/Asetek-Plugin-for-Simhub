#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cliquet_pont.py -- le cliquet vit DANS le pont, pas autour.

POURQUOI
--------
Les journaux du terminal MT5 ont chiffre la chose : le 25/08 49 % des
modifications de stop etaient des RECULS, le 26/08 48 %, le 27/08 13 %.
Sur #172794092 (sell NAS100) le stop oscillait toutes les 1 a 3 secondes
entre 29494.40, le vrai stop, et 31097.15, le stop bouchon a +1600 pts.

Le pont ne fabrique pas ce battement : il le RECOPIE fidelement sur
18**09. Le log de l envoyeur du 27/08 a 15:32 le montre nu :

    STOPS M240006 US30 #172795339  57378.40 -> 53378.40
    STOPS M240006 US30 #172795339  53378.40 -> 53375.40
    STOPS M240006 US30 #172795339  53375.40 -> 57378.40

Trois envois, un aller-retour complet, en 1.1 seconde.

CE QUE FAIT CE PATCH
--------------------
Il pose un cliquet LOCAL, dans le corps de la fonction qui ecrit le
stop, juste avant order_send. Pas une enveloppe autour de order_send :
c est cette enveloppe-la, posee ce matin par sl_cliquet, qui a tue les
ouvertures pendant 1h27 avec (-2, 'Unnamed arguments not allowed').
Ici rien n entoure order_send, donc rien ne peut casser une ouverture.

La regle tient en une phrase : le pont retient le meilleur stop deja
ecrit sur chaque ticket et, si la source lui en demande un moins bon,
il REECRIT le meilleur au lieu de reculer.

Il substitue au lieu de refuser : ainsi un vrai changement de TP passe
toujours, et le memo _DERNIER_STOP absorbe la repetition -- le second
battement identique ne genere meme plus d appel a order_send.

Le sens est lu sur la position (pos[0].type), pas devine :
    achat  -> meilleur = plus HAUT
    vente  -> meilleur = plus BAS
Le stop bouchon est, par construction, toujours du mauvais cote : a
+1600 pts au-dessus d une vente, a -200 pts en dessous d un achat. Le
cliquet peut donc etre amorce sans risque sur le stop deja en place au
moment du demarrage.

CE QUE CE PATCH NE FAIT PAS
---------------------------
Il ne soigne pas la CAUSE. La cause est sur le compte du moteur, ou
quelque chose reecrit le bouchon par-dessus le vrai stop. Ce patch
arrete le symptome sur 18**09, et seulement la. La cause reste a nommer.

USAGE
-----
    python patch_cliquet_pont.py                 <- simulation
    python patch_cliquet_pont.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import time

CIBLE_DEFAUT = "pont_miroirs.py"

# Le marqueur est un sentinelle : une chaine qui n existe NULLE PART
# ailleurs. Trois fois cette semaine un marqueur trop banal s est
# reconnu tout seul et le patch a dit "deja pose" sans rien ecrire.
MARQUEUR = "[CLIQUET-PONT-2708]"

# --- ancre 1 : les deux memoires, au niveau module -------------------
RE_DECL = re.compile(r"^_DERNIER_STOP\s*=\s*\{\s*\}\s*$", re.M)

DECL = '''
# Le meilleur stop deja ecrit sur chaque ticket de 18**09, et le
# dernier recul dont on a parle. Le second n existe que pour ne pas
# repeter la meme ligne de log 40 fois par minute.  [CLIQUET-PONT-2708]
_MEILLEUR_STOP = {}
_CLIQUET_DIT = {}'''

# --- ancre 2 : oublier le ticket quand la position n existe plus -----
OUBLI_AV = '''    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        oublier_stop(ticket)
        return True'''

OUBLI_AP = '''    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        oublier_stop(ticket)
        _MEILLEUR_STOP.pop(ticket, None)
        _CLIQUET_DIT.pop(ticket, None)
        return True'''

# --- ancre 3 : le cliquet lui-meme, juste avant l ecriture -----------
ENVOI_AV = '''    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP,
                        "position": ticket, "sl": sl, "tp": tp})'''

ENVOI_AP = '''    # --- cliquet local : un stop ne recule jamais  [CLIQUET-PONT-2708]
    if abs(sl) > EPS:
        _sens = 1 if int(pos[0].type) == 0 else -1
        _best = _MEILLEUR_STOP.get(ticket)
        if _best is None and abs(avant) > EPS:
            _best = avant          # amorce sur ce que porte deja la position
        if _best is not None and (sl - _best) * _sens < -EPS:
            if _CLIQUET_DIT.get(ticket) != round(sl, 2):
                _CLIQUET_DIT[ticket] = round(sl, 2)
                dire("envoyeur",
                     "  CLIQUET %s #%s : recul %.2f -> %.2f refuse, garde %.2f"
                     % (etiquette, ticket, _best, sl, _best))
            sl = _best             # on reecrit le meilleur, on ne recule pas
        if _best is None or (sl - _best) * _sens > 0:
            _best = sl
        _MEILLEUR_STOP[ticket] = _best
        if abs(avant - sl) <= EPS and abs(float(pos[0].tp) - tp) <= EPS:
            _DERNIER_STOP[ticket] = (sl, tp)
            return True            # rien a changer : pas d envoi du tout
    # --- fin du cliquet local -------------------------------------------

    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP,
                        "position": ticket, "sl": sl, "tp": tp})'''


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.cible):
        print("ABANDON : %s introuvable." % a.cible)
        return 2
    with io.open(a.cible, "r", encoding="latin-1", newline="") as f:
        src = f.read()

    if MARQUEUR in src:
        print("DEJA POSE : %s est present dans %s." % (MARQUEUR, a.cible))
        return 0

    crlf = "\r\n" in src
    def n(s):
        return s.replace("\n", "\r\n") if crlf else s

    neuf = src

    # ancre 1 -- la declaration
    m = RE_DECL.search(neuf)
    if m is None:
        print("REFUS : ancre 1 introuvable -- pas de ligne '_DERNIER_STOP = {}'")
        print("        au niveau module. Envoyez-moi les 30 premieres lignes")
        print("        qui declarent les memoires du pont.")
        return 3
    fin = m.end()
    neuf = neuf[:fin] + n(DECL) + neuf[fin:]

    # ancres 2 et 3 -- le corps
    for i, (old, new) in enumerate(((OUBLI_AV, OUBLI_AP),
                                    (ENVOI_AV, ENVOI_AP)), 2):
        old, new = n(old), n(new)
        c = neuf.count(old)
        if c != 1:
            print("REFUS : ancre %d attendue 1 fois, trouvee %d." % (i, c))
            return 3
        neuf = neuf.replace(old, new, 1)

    try:
        compile(neuf, a.cible, "exec")
    except SyntaxError as e:
        print("REFUS : le resultat ne compile pas -- ligne %s : %s"
              % (e.lineno, e.msg))
        return 4

    print("3 ancres posees, resultat compile.")
    print("  %d -> %d octets  (+%d)" % (len(src), len(neuf),
                                        len(neuf) - len(src)))
    print("  fins de ligne : %s" % ("CRLF" if crlf else "LF"))
    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancez avec --appliquer.")
        return 0

    sauve = "%s.avant_cliquet_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.cible, sauve)
    with io.open(a.cible, "w", encoding="latin-1", newline="") as f:
        f.write(neuf)
    with io.open(a.cible, "r", encoding="latin-1", newline="") as f:
        relu = f.read()
    ok = relu.count(MARQUEUR) == 2
    print("")
    print("sauvegarde   : %s" % os.path.basename(sauve))
    print("VERIFICATION : %s (%d marqueurs, 2 attendus)"
          % ("ok" if ok else "ECHEC", relu.count(MARQUEUR)))
    if not ok:
        shutil.copy2(sauve, a.cible)
        print("Le fichier a ete REMIS dans son etat d origine.")
        return 5
    print("")
    print("Seul l ENVOYEUR porte cette fonction. Le lecteur n ecrit aucun")
    print("stop : inutile de le redemarrer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
