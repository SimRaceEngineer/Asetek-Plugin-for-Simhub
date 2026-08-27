#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_be_watchdog.py -- le break-even cesse de viser le mauvais cote du prix.

CE QUI A ETE MESURE
-------------------
Journal du terminal MT5, compte 17**80, 27/08 jusqu a 16:11 :

    2 019 modifications de stop acceptees
    2 173 REFUSEES par le courtier, motif [Invalid stops]

Plus de refus que d acceptations. L ecart entre le stop demande et le
PRIX D ENTREE de la position est une constante par actif :

    US30    buy    1 394 refus    entree + 8.00   (1 347 fois sur 1 394)
    NAS100  buy      107 refus    entree + 5.00   (107 fois sur 107)
    SPX500  buy      125 refus    entree + 0.80   (122 fois sur 125)

Et BE_BUFFER_PTS = {"US30": 800, "US500": 80, "US100": 500} multiplie par
info.point vaut 8.00 / 0.80 / 5.00. Trois actifs, trois correspondances
exactes : c est _move_to_be, sans autre candidat possible.

LE DEFAUT, EN UNE PHRASE
------------------------
Les deux branches de _move_to_be comparent le niveau vise au STOP actuel
de la position, jamais au PRIX courant :

    if p.type == 0:                          # BUY
        new_sl = p.price_open + buffer
        if p.sl >= new_sl:                   <- ou est le stop
            return p.ticket, True
    else:
        new_sl = p.price_open + buffer       # SELL, volontaire
        if p.sl > 0 and p.sl <= new_sl:      <- ou est le stop
            return p.ticket, True

Une position en perte franchit donc les deux tests et part quand meme.
Un achat dont le prix est retombe sous l entree ne peut pas porter un
stop au-dessus du prix courant : le courtier refuse, la fonction
recommence deux secondes plus tard, indefiniment.

    15:40:03  order #172796440 buy 0.58 US30 at 53558.60 done
    15:47:32  failed modify #172796440 sl: 49562.60 -> 53566.60
                                                    [Invalid stops]

Cela ne coute rien en P&L -- un refus ne change rien -- mais cela martele
le courtier et noie les journaux.

CE QUE CE PATCH POSE
--------------------
1. La garde manquante, juste avant l envoi : le niveau vise doit etre du
   BON COTE DU PRIX COURANT. Sinon on rend (ticket, True), la meme
   convention de no-op silencieux que les deux exemptions deja presentes
   dans la fonction -- succes annonce, aucun ordre, aucun reessai.

2. L exemption des positions MIROIR, a cote des deux qui existent deja.
   Elles portent le stop de leur paper parent ; un BE a entree+tampon le
   remplace par un stop serre, et la position miroir se ferme alors sur
   une sortie que le paper n a jamais demandee -- le resultat de la
   branche est faux. C est la meme lecon que le 24/04 pour les M93xxx et
   que le 25/06 pour les rails 164000-173999, sur une troisieme famille.
   Les deux commentaires en tete de la fonction la disent deja :

     "watchdog was silently BE-ing them -- SL resserre a entry
      = SL hit instantane"
     "le BE a entry+buffer convertit le filet en stop instantane
      sur un wick alors que le sens est encore bon"

CE QUE CE PATCH NE TOUCHE PAS
-----------------------------
_check_auto_breakeven (R7), dont la documentation dit "SL only moves UP"
-- ce qui n est vrai que pour un achat. A regarder ensuite, pas ici.

Les ancres sont des EXPRESSIONS REGULIERES tolerantes aux espaces, et
chacune doit correspondre exactement une fois. Trois fois cette semaine
un patch a rate parce qu une ancre recopiee d un ecran ne collait pas au
caractere pres.

USAGE
-----
    python patch_be_watchdog.py                 <- simulation
    python patch_be_watchdog.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import time

CIBLE_DEFAUT = "daily_watchdog.py"
MARQUEUR = "[BE-COTE-PRIX-2708]"

# La requete SLTP de _move_to_be n est PAS unique dans le fichier :
# _check_auto_breakeven (R7) construit la meme. Un patch qui se contente
# de la chercher tombe sur deux resultats et ne sait pas lequel prendre
# -- c est ce qui est arrive le 27/08 a 16:52, et le patch a eu raison de
# refuser plutot que de deviner. On delimite donc d abord la fonction, et
# on ne pose les ancres 2 et 3 qu a l interieur.
RE_FONCTION = re.compile(
    r"^def _move_to_be\(.*?(?=^def |^class |\Z)", re.M | re.S)
RE_DEF = re.compile(r"^def (\w+)", re.M)

# --- ancre 1 : la declaration des plages, a cote des tampons ----------
RE_TAMPONS = re.compile(r"^BE_BUFFER_PTS\s*=\s*\{.*$", re.M)

DECL = '''

# Les positions MIROIR des papers. Leur stop appartient a leur paper
# parent : le watchdog n a rien a y faire.  [BE-COTE-PRIX-2708]
#   220000 - 249999    miroir 1, le magic du paper lui-meme
#  4220000 - 4249999   miroir 2      5220000 - 5249999   miroir 5
#  6220000 - 6249999   miroir 6
PLAGES_MIROIR = ((220000, 249999), (4220000, 4249999),
                 (5220000, 5249999), (6220000, 6249999))'''

# --- ancre 2 : l exemption miroir, sous celle des AUTONOMOUS ----------
RE_AUTON = re.compile(
    r"(?P<i>[ \t]*)if p\.magic in AUTONOMOUS_MAGICS and not force_autonomous:"
    r"[ \t]*\r?\n[ \t]*return p\.ticket, True[^\r\n]*\r?\n")

EXEMPTION = '''{i}# 2026-08-27 : les positions MIROIR des papers.  [BE-COTE-PRIX-2708]
{i}# Elles portent le stop de leur paper parent. Le BE a entree+tampon le
{i}# remplace par un stop serre, et la position miroir se ferme sur une
{i}# sortie que le paper n a jamais demandee : le resultat de la branche
{i}# devient faux. Meme lecon que le 24/04 (M93xxx) et le 25/06 (rails
{i}# 164000-173999), sur une troisieme famille.
{i}try:
{i}    if any(a <= int(p.magic) <= b for a, b in PLAGES_MIROIR):
{i}        return p.ticket, True   # no-op : le stop appartient au paper
{i}except Exception:
{i}    pass
'''

# --- ancre 3 : la garde, juste avant la requete -----------------------
RE_REQ = re.compile(
    r"(?P<i>[ \t]*)req = \{[ \t]*\r?\n"
    r"[ \t]*\"action\": mt5\.TRADE_ACTION_SLTP,[ \t]*\r?\n"
    r"[ \t]*\"symbol\": p\.symbol,[ \t]*\r?\n"
    r"[ \t]*\"position\": p\.ticket,[ \t]*\r?\n"
    r"[ \t]*\"sl\": round\(new_sl, info\.digits\),")

GARDE = '''{i}# 2026-08-27 : le niveau vise doit etre du BON COTE DU PRIX COURANT.
{i}# Les deux tests ci-dessus regardent ou est le STOP, jamais ou est le
{i}# PRIX : une position en perte les franchit et part quand meme. Un
{i}# achat dont le prix est retombe sous l entree ne peut pas porter un
{i}# stop au-dessus du prix -- le courtier repond [Invalid stops] et la
{i}# fonction recommence deux secondes plus tard. 2 173 refus le 27/08,
{i}# dont 1 394 sur les seuls achats US30.  [BE-COTE-PRIX-2708]
{i}_prix = float(getattr(p, "price_current", 0.0) or 0.0)
{i}if _prix:
{i}    _marge = info.point
{i}    _trop_tot = (_prix <= new_sl + _marge) if p.type == 0 \\
{i}        else (_prix >= new_sl - _marge)
{i}    if _trop_tot:
{i}        return p.ticket, True   # pas encore en gain : no-op, pas de reessai
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

    crlf = "\r\n" in src
    def n(s):
        return s.replace("\n", "\r\n") if crlf else s

    neuf = src

    m = RE_TAMPONS.search(neuf)
    if m is None:
        print("REFUS : ancre 1 introuvable -- pas de ligne 'BE_BUFFER_PTS = {'")
        return 3
    neuf = neuf[:m.end()] + n(DECL) + neuf[m.end():]

    # -- ou commence et ou finit _move_to_be
    f = RE_FONCTION.search(neuf)
    if f is None:
        print("REFUS : la fonction _move_to_be est introuvable au niveau"
              " module.")
        return 3
    d0, d1 = f.start(), f.end()
    print("  _move_to_be : %d octets, du caractere %d au %d."
          % (d1 - d0, d0, d1))

    # Pour information : toutes les requetes SLTP du fichier, et leur
    # fonction. Voir ou vit l autre est plus utile que de l ignorer.
    for r in RE_REQ.finditer(neuf):
        noms = RE_DEF.findall(neuf[:r.start()])
        dedans = "  <- celle-ci" if d0 <= r.start() < d1 else ""
        print("    requete SLTP dans %s()%s"
              % (noms[-1] if noms else "?", dedans))

    # -- ancre 2, dans la fonction seulement
    bloc = neuf[d0:d1]
    if len(RE_AUTON.findall(bloc)) != 1:
        print("REFUS : ancre 2 (exemption AUTONOMOUS_MAGICS) attendue 1 fois"
              " dans _move_to_be, trouvee %d." % len(RE_AUTON.findall(bloc)))
        return 3
    # -- ancre 3, dans la fonction seulement
    if len(RE_REQ.findall(bloc)) != 1:
        print("REFUS : ancre 3 (la requete SLTP) attendue 1 fois dans"
              " _move_to_be, trouvee %d." % len(RE_REQ.findall(bloc)))
        return 3

    # On ecrit de la fin vers le debut : les positions restent valides.
    m = RE_REQ.search(neuf, d0, d1)
    neuf = neuf[:m.start()] + n(GARDE.format(i=m.group("i"))) + neuf[m.start():]
    m = RE_AUTON.search(neuf, d0, d1)
    neuf = neuf[:m.end()] + n(EXEMPTION.format(i=m.group("i"))) + neuf[m.end():]

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

    sauve = "%s.avant_be_%s" % (a.cible, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(a.cible, sauve)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(neuf)
    with io.open(a.cible, "r", encoding="utf-8", newline="") as f:
        relu = f.read()
    nb = relu.count(MARQUEUR)
    ok = nb == 3
    print("")
    print("sauvegarde   : %s" % os.path.basename(sauve))
    print("VERIFICATION : %s (%d marqueurs, 3 attendus)"
          % ("ok" if ok else "ECHEC", nb))
    if not ok:
        shutil.copy2(sauve, a.cible)
        print("Le fichier a ete REMIS dans son etat d origine.")
        return 5
    print("")
    print("daily_watchdog est importe par le moteur AU DEMARRAGE : cette")
    print("correction ne prendra effet qu au prochain lancement de")
    print("trading_engine.py. Rien ne change dans la seance en cours.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
