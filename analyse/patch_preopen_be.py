#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_preopen_be.py -- BE ou mieux, jamais moins, dans preopen_protect.py

CE QU ON A ETABLI LE 11/08
    Les trois reculs de stop du 10/08 a 15:27 viennent de preopen_protect.py.
    Verification au centime : ticket #171937213, entree a 53966,25, et le BE
    de 15:27 a pose le stop a 53966,25 exactement.

        #171930748  TRAIL 29744,45 -> BE 29805,45   61,0 points rendus
        #171937209  TRAIL 53944,70 -> BE 53967,25   22,6
        #171937213  TRAIL 53944,20 -> BE 53966,25   22,1

CE N EST PAS UN BUG, ET IL FAUT LE DIRE
    Le module l annonce en tete : "A 15:27 Paris (juste avant l open cash US
    15:30), UNE fois par jour : BE sur TOUTES les positions en gain
    (autonomes INCLUS, user OK explicite malgre sl_mover_exemptions /
    structural_sl : l open peut tout renverser)".

    C est une decision de conception, prise en connaissance de cause. Ce
    patch ne la renverse pas.

CE QU IL CORRIGE
    L implementation trahit l intention. Sur une position deja suivie en
    profit, ramener le stop au prix d entree ne protege pas davantage : ca
    REND du verrou deja acquis. Un stop au-dela de l entree protege PLUS que
    le BE, pas moins.

    La garde posee ici sert donc l intention a la lettre -- se premunir d un
    retournement a l open -- sans rendre ce qui etait acquis :

        si le stop courant est deja au niveau de l entree ou au-dela,
        on n y touche pas.

    Ce qui n a PAS de stop, ou un stop moins bon que l entree, est ramene au
    BE comme avant. La regle de 15:27 continue de s appliquer a tout le
    reste, y compris aux "autonomes".

    _move_be renvoie True dans ce cas : la position EST protegee au niveau
    BE ou mieux, donc le compteur "BE=%d" de _fire() reste honnete.

CE QU IL NE TOUCHE PAS
    La fermeture de 75 pour cent des gros gagnants, l autre moitie du
    module. Elle n a rien a voir avec les reculs de stop.

IDEMPOTENT.
"""
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "preopen_protect.py"
MARQUEUR = "_be_deja_mieux"

# Ancre par expression, avec capture de l indentation : le 11/08 un patch a
# echoue parce que j avais suppose 8 espaces la ou le fichier en avait 16.
# On ne devine plus, on capture.
RE_ANCRE = re.compile(
    r'^([ \t]*)req = \{"action": mt5\.TRADE_ACTION_SLTP, "symbol": p\.symbol, '
    r'"position": p\.ticket,[ \t]*\n'
    r'([ \t]*)"sl": float\(p\.price_open\), "tp": float\(p\.tp\), '
    r'"magic": int\(p\.magic\)\}[ \t]*$',
    re.M)

GARDE = '''# 11/08 : BE ou MIEUX, jamais moins. Sur une position deja suivie en
# profit, ramener le stop a l entree rend le verrou au lieu de le
# renforcer -- 61,0 / 22,6 / 22,1 points abandonnes le 10/08 a 15:27 sur
# trois tickets qui etaient deja mieux proteges que le BE.
# L intention du module est servie a la lettre : un stop au-dela de
# l entree protege PLUS contre le retournement de l open, pas moins.
_be_deja_mieux = False
try:
    _entree = float(p.price_open)
    if p.sl:
        _be_deja_mieux = (p.sl >= _entree
                          if p.type == mt5.POSITION_TYPE_BUY
                          else p.sl <= _entree)
except Exception:
    _be_deja_mieux = False          # au moindre doute, on applique le BE
if _be_deja_mieux:
    return True                     # deja au BE ou mieux : rien a faire'''


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable -- lance depuis le dossier de la stack." % CIBLE)
        return 1

    src, enc = lire(CIBLE)
    print("%s : %d lignes, encodage %s" % (CIBLE, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Garde deja posee -- rien a faire.")
        return 0

    trouve = RE_ANCRE.findall(src)
    if len(trouve) != 1:
        print("KO : %d occurrence(s) de l ancre, il en faut 1." % len(trouve))
        print("Attendu, dans _move_be, a n importe quelle indentation :")
        print('    req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": p.symbol, '
              '"position": p.ticket,')
        print('           "sl": float(p.price_open), "tp": float(p.tp), '
              '"magic": int(p.magic)}')
        return 1

    ind = trouve[0][0]
    print("ancre trouvee : indentation %d espaces" % len(ind))
    bloc = "\n".join(ind + l if l else "" for l in GARDE.split("\n"))

    def _sub(m):
        return bloc + "\n" + m.group(0)

    neuf = RE_ANCRE.sub(_sub, src, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    sauve = "%s.bak-%s" % (CIBLE, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(CIBLE, sauve)
    io.open(CIBLE, "w", encoding=enc).write(neuf)
    print("Sauvegarde : %s" % sauve)
    print()
    print("A 15:27, une position deja protegee au-dela de son entree ne sera")
    print("plus ramenee au BE. Tout le reste est inchange, y compris la")
    print("fermeture des 75 pour cent et le BE sur les positions moins bien")
    print("protegees.")
    print()
    print("preopen_protect tourne dans trading_engine.py : il faut relancer")
    print("le moteur pour que la garde prenne effet, ou attendre son prochain")
    print("demarrage. Verifier demain vers 15:30 :")
    print("    Get-ChildItem -Recurse -Filter *.log | Select-String 'preopen_protect'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
