#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""corrige_remplissage_pont.py -- rc=10030, le mode de remplissage.

CE QUI S EST PASSE
------------------
Le 25/08 a 14:00:01, des la premiere seconde de la fenetre du miroir,
chaque ordre du pont est reparti :

    14:00:01.350  ENTREE M240006 US30 BUY 0.76
    14:00:01.355    OUVERTURE REFUSEE rc=10030 Unsupported filling mode

Toutes, sans exception. J avais code `ORDER_FILLING_IOC` en dur dans les
requetes, sans demander au terminal ce qu il accepte. Ce courtier veut
autre chose sur ces symboles.

LE CORRECTIF
------------
Le mode se lit dans le masque `filling_mode` du symbole. On essaie dans
l ordre, et on retient celui qui a marche -- une fois trouve, il n est
plus recherche.

Un refus AUTRE que 10030 est rendu tel quel sans reessayer : sinon on
enverrait quatre fois un ordre refuse pour une raison qui n a rien a
voir avec le remplissage, ce qui serait bien pire que le defaut d
origine.

USAGE
-----
    python corrige_remplissage_pont.py                 <- simulation
    python corrige_remplissage_pont.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\pont_miroirs.py"
SUFFIXE_BAK = ".bak_remplissage"
MARQUEUR = "def envoyer(req, sym):"

ANCRE_PRIX = '''def prix(sym, achat):
    t = mt5.symbol_info_tick(sym)
    if t is None:
        return None
    return t.ask if achat else t.bid
'''

BLOC = ANCRE_PRIX + '''

# Le mode de remplissage ne s invente pas. Le 25/08 a 14:00, chaque
# ordre est reparti en rc=10030 "Unsupported filling mode" parce que
# IOC etait code en dur : ce courtier veut autre chose sur ces symboles.
# On lit donc le masque du symbole, on essaie dans l ordre, et on retient
# celui qui a marche.
_REMPLISSAGE = {}
NOM_REMPLISSAGE = {0: "FOK", 1: "IOC", 2: "RETURN"}


def modes_possibles(sym):
    try:
        masque = int(getattr(mt5.symbol_info(sym), "filling_mode", 0) or 0)
    except Exception:
        masque = 0
    ordre = []
    if masque & 1:                       # SYMBOL_FILLING_FOK
        ordre.append(getattr(mt5, "ORDER_FILLING_FOK", 0))
    if masque & 2:                       # SYMBOL_FILLING_IOC
        ordre.append(getattr(mt5, "ORDER_FILLING_IOC", 1))
    for m in (getattr(mt5, "ORDER_FILLING_FOK", 0),
              getattr(mt5, "ORDER_FILLING_IOC", 1),
              getattr(mt5, "ORDER_FILLING_RETURN", 2)):
        if m not in ordre:
            ordre.append(m)
    return ordre


def envoyer(req, sym):
    """order_send, en essayant les modes de remplissage jusqu au bon.

    Un refus autre que 10030 est un vrai refus : on le rend tel quel
    plutot que de reessayer, sinon on enverrait quatre fois un ordre
    refuse pour une raison qui n a rien a voir avec le remplissage.
    """
    connu = _REMPLISSAGE.get(sym)
    ordre = ([connu] if connu is not None else []) \\
        + [m for m in modes_possibles(sym) if m != connu]
    dernier = None
    for m in ordre:
        req["type_filling"] = m
        dernier = mt5.order_send(req)
        if dernier is None:
            continue
        if dernier.retcode == mt5.TRADE_RETCODE_DONE:
            if _REMPLISSAGE.get(sym) != m:
                _REMPLISSAGE[sym] = m
                dire("envoyeur", "  remplissage retenu pour %s : %s"
                     % (sym, NOM_REMPLISSAGE.get(m, m)))
            return dernier
        if dernier.retcode != 10030:
            return dernier
    return dernier
'''

REMPLACEMENTS = (
    ('        "type_time": mt5.ORDER_TIME_GTC,\n'
     '        "type_filling": mt5.ORDER_FILLING_IOC,\n    }',
     '        "type_time": mt5.ORDER_TIME_GTC,\n    }', 2),
    ('    r = mt5.order_send(req)\n'
     '    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:\n'
     '        dire("envoyeur", "  OUVERTURE REFUSEE',
     '    r = envoyer(req, src["sym"])\n'
     '    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:\n'
     '        dire("envoyeur", "  OUVERTURE REFUSEE', 1),
    ('    r = mt5.order_send(req)\n'
     '    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:\n'
     '        dire("envoyeur", "  FERMETURE REFUSEE',
     '    r = envoyer(req, sym)\n'
     '    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:\n'
     '        dire("envoyeur", "  FERMETURE REFUSEE', 1),
)


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    args = ap.parse_args()

    print("=" * 66)
    print("corrige_remplissage_pont -- %s"
          % ("APPLIQUER" if args.appliquer else "SIMULATION"))
    print("=" * 66)

    if not os.path.isfile(args.cible):
        print("introuvable : %s" % args.cible)
        return 2

    s = lire(args.cible)
    print("cible : %s  (%d lignes)" % (args.cible, s.count("\n") + 1))

    if MARQUEUR in s:
        print("")
        print("Deja corrige : envoyer() est present.")
        return 0

    if s.count(ANCRE_PRIX) != 1:
        print("")
        print("REFUS : prix() introuvable ou en double. Fichier different.")
        return 1
    for vieux, _neuf, attendu in REMPLACEMENTS:
        n = s.count(vieux)
        if n != attendu:
            print("")
            print("REFUS : motif attendu %d fois, trouve %d." % (attendu, n))
            print("   %s..." % vieux.strip().split("\n")[0][:56])
            return 1

    print("        les quatre motifs sont la, aux bons comptes.")
    print("")
    print("a faire :")
    print("   + modes_possibles() et envoyer(), apres prix()")
    print("   - ORDER_FILLING_IOC code en dur, 2 requetes")
    print("   ~ order_send -> envoyer, a l ouverture et a la fermeture")

    if not args.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer.")
        return 0

    bak = args.cible + SUFFIXE_BAK
    if not os.path.exists(bak):
        shutil.copy2(args.cible, bak)
        print("")
        print("sauvegarde : %s" % bak)

    s = s.replace(ANCRE_PRIX, BLOC, 1)
    for vieux, neuf, _a in REMPLACEMENTS:
        s = s.replace(vieux, neuf)
    with io.open(args.cible, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print("ecrit : %s" % args.cible)

    relu = lire(args.cible)
    # `r = envoyer(req` compte les deux APPELS. Chercher `envoyer(req`
    # tout court en trouverait trois, la definition comprise -- et le
    # controle condamnerait un correctif correct.
    appels = relu.count("    r = envoyer(req")
    if MARQUEUR not in relu or '"type_filling": mt5.ORDER_FILLING_IOC' in relu \
            or appels != 2:
        print("relu   : CORRECTIF INCOMPLET (%d appel(s) au lieu de 2)"
              % appels)
        print("         restaurer %s" % bak)
        return 1
    print("relu   : envoyer() present, IOC en dur retire, 2 appels branches.")
    try:
        compile(relu, args.cible, "exec")
        print("syntaxe: le fichier compile.")
    except SyntaxError as e:
        print("syntaxe: ERREUR ligne %s -- restaurer %s" % (e.lineno, bak))
        return 1

    print("")
    print("-" * 66)
    print("Le pont doit etre RELANCE : les deux processus tournent sur la")
    print("version chargee en memoire.")
    print("Fermer les deux fenetres, puis PONT_MIROIRS.cmd reel")
    print("")
    print("Les positions deja ouvertes chez le miroir ne seront pas")
    print("copiees -- leur prix d entree appartient au passe. Seules les")
    print("suivantes le seront, et elles, exactement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
