#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ferme_orphelines.py -- solder les dix positions sans lien du 25/08.

D OU ELLES VIENNENT
-------------------
Le 25/08, `PONT_MIROIRS.cmd` a ete lance deux fois sans fermer les
fenetres precedentes : deux paires lecteur/envoyeur ont tourne en
parallele de 15:02 a 15:38. Les deux envoyeurs ouvraient chacun leur
copie d une meme position source et ecrivaient le MEME `liens.json` --
le dernier ecrivain effacant le lien de l autre.

Il reste donc dix positions que plus aucun processus ne suivra. Elles
portent leur stop d ouverture, donc elles ne sont pas nues ; mais quand
elles se solderont au hasard, elles seront comptees dans le CONSTATE de
leur magic et fausseront exactement ce que ce compte sert a mesurer.

LA LISTE EST EN DUR, ET C EST VOULU
-----------------------------------
Un script qui fermerait "tout ce qui n est pas dans liens.json" serait
dangereux : l envoyeur ouvre en permanence, et une position prise a la
seconde ou l on lit le fichier n y figure pas encore. Elle serait
fermee comme orpheline alors qu elle vient de naitre.

Dix numeros, releves a 16:08, verifies un par un sur leur magic ET leur
symbole avant d etre touches. Rien d autre ne peut etre ferme par ce
script, quelles que soient les circonstances.

CE QU IL REFUSE DE FAIRE
------------------------
- travailler sur un compte qui n est pas 182109 ;
- travailler sur autre chose qu une demo ;
- fermer un ticket dont le magic ou le symbole ne correspond pas ;
- fermer quoi que ce soit sans --reel.

USAGE
-----
    python ferme_orphelines.py                 <- simulation
    python ferme_orphelines.py --reel
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

TERMINAL_DEDIE = r"C:\Program Files\TF Global Markets MetaTrader 5 Terminal\terminal64.exe"
TERMINAL_MOTEUR = r"C:\Program Files\TF Global Markets MetaTrader 5 Termina-LOCALSTACKl\terminal64.exe"
COMPTE = 182109

# (ticket, magic attendu, symbole attendu) -- releve du 25/08 16:08.
ORPHELINES = [
    (172647819,  240004, "SPX500"),
    (172647829,  240007, "SPX500"),
    (172647835,  240004, "SPX500"),
    (172648611,  240007, "US30"),
    (172648620,  220004, "US30"),
    (172648629,  240004, "US30"),
    (172649125,  240006, "NAS100"),
    (172649134,  220004, "US30"),
    (172649138, 4220004, "US30"),
    (172649142,  240002, "US30"),
]


def modes(sym):
    """Le mode de remplissage ne s invente pas -- rc=10030 le 25/08 a
    14:00 sur chaque ordre du pont, IOC etant code en dur."""
    try:
        masque = int(getattr(mt5.symbol_info(sym), "filling_mode", 0) or 0)
    except Exception:
        masque = 0
    ordre = []
    if masque & 1:
        ordre.append(getattr(mt5, "ORDER_FILLING_FOK", 0))
    if masque & 2:
        ordre.append(getattr(mt5, "ORDER_FILLING_IOC", 1))
    for m in (getattr(mt5, "ORDER_FILLING_FOK", 0),
              getattr(mt5, "ORDER_FILLING_IOC", 1),
              getattr(mt5, "ORDER_FILLING_RETURN", 2)):
        if m not in ordre:
            ordre.append(m)
    return ordre


def envoyer(req, sym):
    dernier = None
    for m in modes(sym):
        req["type_filling"] = m
        dernier = mt5.order_send(req)
        if dernier is None:
            continue
        if dernier.retcode == mt5.TRADE_RETCODE_DONE:
            return dernier
        if dernier.retcode != 10030:      # 10030 = remplissage refuse
            return dernier
    return dernier


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--terminal", default=TERMINAL_DEDIE)
    ap.add_argument("--reel", action="store_true")
    args = ap.parse_args()

    print("=" * 66)
    print("ferme_orphelines -- %s"
          % ("REEL" if args.reel else "SIMULATION"))
    print("=" * 66)

    if mt5 is None:
        print("MetaTrader5 introuvable dans cet interpreteur.")
        return 2
    if os.path.abspath(args.terminal) == os.path.abspath(TERMINAL_MOTEUR):
        print("REFUS : c est le terminal du moteur.")
        return 2
    if not mt5.initialize(path=args.terminal):
        print("initialize a echoue : %s" % (mt5.last_error(),))
        return 1
    try:
        ai = mt5.account_info()
        if ai is None:
            print("compte illisible.")
            return 1
        if int(ai.login) != COMPTE:
            print("MAUVAIS COMPTE : attendu %d, trouve %s"
                  % (COMPTE, ai.login))
            return 1
        if ai.trade_mode != getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0):
            print("Ce compte n est pas une demo. Refus.")
            return 1
        print("compte %s  solde %.2f  equite %.2f"
              % (str(ai.login)[:2] + "**" + str(ai.login)[-2:],
                 ai.balance, ai.equity))
        print("")

        ferme = absent = refuse = ecart = 0
        for tk, magic, sym in ORPHELINES:
            pos = mt5.positions_get(ticket=tk)
            if not pos:
                print("  #%d  deja fermee" % tk)
                absent += 1
                continue
            p = pos[0]
            if int(p.magic) != magic or p.symbol != sym:
                print("  #%d  ECART : magic %s / %s au lieu de %d / %s"
                      " -- NON TOUCHEE" % (tk, p.magic, p.symbol, magic, sym))
                ecart += 1
                continue
            achat = int(p.type) == getattr(mt5, "ORDER_TYPE_SELL", 1)
            t = mt5.symbol_info_tick(sym)
            if t is None:
                print("  #%d  pas de cotation -- NON TOUCHEE" % tk)
                refuse += 1
                continue
            if not args.reel:
                print("  #%d  M%d %-6s %.2f  -> fermerait a %.2f"
                      % (tk, magic, sym, p.volume,
                         t.ask if achat else t.bid))
                continue
            r = envoyer({"action": mt5.TRADE_ACTION_DEAL, "symbol": sym,
                         "volume": float(p.volume),
                         "type": (mt5.ORDER_TYPE_BUY if achat
                                  else mt5.ORDER_TYPE_SELL),
                         "position": int(tk),
                         "price": t.ask if achat else t.bid,
                         "deviation": 30, "magic": 0,
                         "comment": "orpheline 25-08",
                         "type_time": mt5.ORDER_TIME_GTC}, sym)
            if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
                print("  #%d  REFUSEE rc=%s %s"
                      % (tk, getattr(r, "retcode", "?"),
                         getattr(r, "comment", "")))
                refuse += 1
            else:
                print("  #%d  M%d %-6s %.2f  fermee a %.2f"
                      % (tk, magic, sym, p.volume, r.price))
                ferme += 1

        print("")
        print("-" * 66)
        if not args.reel:
            print("SIMULATION -- rien n a ete ferme.")
            print("Relancer avec --reel.")
        else:
            print("%d fermee(s), %d deja fermee(s), %d refusee(s), %d ecart(s)"
                  % (ferme, absent, refuse, ecart))
            print("")
            print("Regenerer le panneau ensuite : les affaires ainsi soldees")
            print("entrent dans le CONSTATE de leur magic. Elles y ont leur")
            print("place -- elles ont bien ete prises et bien ete fermees.")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())
