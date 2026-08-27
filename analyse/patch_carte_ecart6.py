#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_carte_ecart6.py -- l ecart 6 moins 1, sur les MEMES magics.

LE PIEGE QUE CE PATCH EVITE
---------------------------
_synthese agrege par actif, TOUTES STRATEGIES CONFONDUES. La branche 1
y couvre une trentaine de magics ; la branche 6 n existe que sur les
deux accords M15. Ecrire un "6 moins 1" comme le "2 moins 1" existant
comparerait 27 trades sur deux magics a 418 sur trente : le resultat
mesurerait le NOMBRE DE STRATEGIES, pas la qualite de la sortie.

Le commentaire de _synthese dit deja la meme chose de la branche 5 :

    5 moins 1 en PnL par trade : la branche 5 refuse des entrees, son
    effectif est plus petit par construction, et comparer les montants
    mesurerait le nombre de trades au lieu de leur qualite.

CE QUE CE PATCH POSE
--------------------
Plutot que d y renoncer, il restreint la branche 1 aux MEMES MAGICS que
la 6. Sur ce perimetre-la, les deux branches partagent tout -- meme
entree, meme lot, meme instant -- et seule la sortie differe. L ecart en
PnL redevient alors exactement ce qu il pretend etre : ce que le
trailing 0.50R a rapporte ou coute par rapport a la sortie d origine.

Les magics ne sont pas ecrits en dur : ils sont LUS dans les donnees,
    magics6 = set(m for (m, b, s) in fin if b == 6)
donc la ligne suit d elle-meme le jour ou la branche 6 s etendra a
d autres signaux, sans qu on ait a y revenir.

Quand la branche 6 n a rien fait sur un actif, la ligne ne parait pas.

USAGE
-----
    python patch_carte_ecart6.py                 <- simulation
    python patch_carte_ecart6.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import time

CIBLE_DEFAUT = "cartes_live.py"
MARQUEUR = "[ECART6-2708]"

# La fin du bloc des ecarts 2-1 et 5-1, dans _synthese. On se pose juste
# apres, au meme niveau que "un = par[1]".
RE_FIN_ECARTS = re.compile(
    r"(?P<i>[ \t]*)% \(lib, av, note, k, f % v, ap,[ \t]*\r?\n"
    r"[ \t]*\"memes effectifs\" if quoi == \"pnl\"[ \t]*\r?\n"
    r"[ \t]*else \"effectifs differents par construction\"\)\)[ \t]*\r?\n")

BLOC = '''
{i}# La branche 6 n existe que sur les accords M15. La comparer a la
{i}# branche 1 toutes strategies confondues comparerait 27 trades sur
{i}# deux magics a 418 sur trente : ce serait le nombre de strategies
{i}# qu on mesurerait, pas la qualite de la sortie. On restreint donc
{i}# la 1 aux MEMES magics -- la, meme entree, meme lot, meme instant,
{i}# et l ecart ne peut plus venir que du trailing.  [ECART6-2708]
{i}magics6 = set(m for (m, b, s) in fin if b == 6)
{i}if magics6 and par.get(6):
{i}    src1 = [c for (m, b, s), c in fin.items()
{i}            if b == 1 and m in magics6
{i}            and (sym is None or s == sym)]
{i}    un6 = constate(_somme(src1), po)
{i}    if un6:
{i}        v6 = par[6]["pnl"] - un6["pnl"]
{i}        k6 = "vert" if v6 > 0 else ("rouge" if v6 < 0 else "")
{i}        corps.append(
{i}            '<tr class="syec"><td></td><td class="brq">%s</td>'
{i}            '<td colspan="5" class="note2">%s</td>'
{i}            '<td class="ec %s">%s</td>'
{i}            '<td colspan="3" class="note2">%s</td></tr>'
{i}            % ("6 &minus; 1", "en PnL", k6, "%+.2f" % v6,
{i}               "memes magics, memes entrees (n %d contre %d)"
{i}               % (par[6]["n"], un6["n"])))
'''


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
        print("DEJA POSE : %s est present dans %s." % (MARQUEUR, a.cible))
        return 0
    if "BRANCHES = (1, 2, 5, 6)" not in src:
        print("REFUS : la branche 6 n est pas dans BRANCHES.")
        print("        Appliquez d abord patch_carte_html6.py, sans quoi")
        print("        par[6] n existerait jamais et la ligne ne paraitrait")
        print("        pas.")
        return 3

    trouves = RE_FIN_ECARTS.findall(src)
    if len(trouves) != 1:
        print("REFUS : la fin du bloc des ecarts attendue 1 fois, trouvee %d."
              % len(trouves))
        return 3

    m = RE_FIN_ECARTS.search(src)
    # Les ecarts vivent dans une boucle interne ; la ligne "un = par[1]"
    # est deux niveaux plus haut. On reprend son retrait, pas celui de
    # la ligne trouvee.
    m2 = re.search(r"^(?P<i>[ \t]*)un = par\[1\]$", src, re.M)
    if m2 is None:
        print("REFUS : la ligne 'un = par[1]' est introuvable.")
        return 3
    bloc = BLOC.format(i=m2.group("i"))
    if "\r\n" in src:
        bloc = bloc.replace("\n", "\r\n")
    neuf = src[:m.end()] + bloc + src[m.end():]

    try:
        compile(neuf, a.cible, "exec")
    except SyntaxError as e:
        print("REFUS : le resultat ne compile pas -- ligne %s : %s"
              % (e.lineno, e.msg))
        return 4

    print("1 ancre posee, resultat compile.")
    print("  retrait repris de 'un = par[1]' : %d espace(s)"
          % len(m2.group("i")))
    print("  %d -> %d octets  (+%d)" % (len(src), len(neuf),
                                        len(neuf) - len(src)))
    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancez avec --appliquer.")
        return 0

    sauve = "%s.avant_ec6_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.cible, sauve)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        relu = f.read()
    ok = MARQUEUR in relu
    print("")
    print("sauvegarde   : %s" % os.path.basename(sauve))
    print("VERIFICATION : %s" % ("ok" if ok else "ECHEC"))
    if not ok:
        shutil.copy2(sauve, a.cible)
        print("Le fichier a ete REMIS dans son etat d origine.")
        return 5
    print("")
    print("boucle_cartes_live relit le module a chaque tour : la prochaine")
    print("generation portera la ligne. Rien a redemarrer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
