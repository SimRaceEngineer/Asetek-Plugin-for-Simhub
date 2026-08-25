#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sonde_compte_papers.py -- controle avant vol du compte dedie aux papers live.

POURQUOI
--------
Le projet : que les decisions de papier_tf partent en reel sur un compte
dedie, entrees et sorties au meme instant, avec la seule condition PM
(14:00-19:00) et aucun gate. Le compte dedie sert a garantir qu aucun
module du moteur ne touche ces positions.

Avant d ecrire l executeur, il faut etre sur de sept choses. Cette sonde
les verifie toutes et **n envoie aucun ordre**.

  1. On s attache bien au terminal voulu, pas a celui du moteur.
  2. C est le bon compte.
  3. C est un compte de DEMO.
  4. AutoTrading est active cote terminal -- c est le bouton
     "Trading Algo". Eteint, il produit rc=10027 sur chaque ordre,
     pendant que tout le reste a l air de fonctionner. C est ce qui a
     coute la nuit du 24 au 25/08.
  5. Le trading par expert est autorise cote compte.
  6. Les trois symboles existent, sont visibles et negociables, et on
     connait leur lot minimum et leur pas.
  7. Aucun autre module de la stack ne pointe vers ce terminal -- sinon
     l isolement promis n existe pas.

Le numero de compte est masque a l affichage : la sortie de ce script
est collee dans une conversation.

USAGE
-----
    python sonde_compte_papers.py
    python sonde_compte_papers.py --compte 182109
    python sonde_compte_papers.py --terminal "C:\\...\\terminal64.exe"
"""

from __future__ import annotations

import argparse
import io
import os
import sys

TERMINAL_DEFAUT = r"C:\Program Files\TF Global Markets MetaTrader 5 Terminal\terminal64.exe"
TERMINAL_MOTEUR = r"C:\Program Files\TF Global Markets MetaTrader 5 Termina-LOCALSTACKl\terminal64.exe"
RACINE_STACK = r"C:\SVPS\Scalp-EA-main"
SYMBOLES = ("US30", "SPX500", "NAS100")

# Motif cherche dans la stack : un chemin vers CE terminal-ci.
MOTIF_CHEMIN = "MetaTrader 5 Terminal\\"

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


def masque(valeur):
    """182109 -> 18**09. La sortie de ce script est collee ailleurs."""
    t = str(valeur)
    if len(t) <= 4:
        return "*" * len(t)
    return t[:2] + "*" * (len(t) - 4) + t[-2:]


def oui_non(v):
    return "oui" if v else "NON"


def nom_mode_marge(v):
    noms = {
        getattr(mt5, "ACCOUNT_MARGIN_MODE_RETAIL_NETTING", -1): "netting",
        getattr(mt5, "ACCOUNT_MARGIN_MODE_EXCHANGE", -2): "exchange",
        getattr(mt5, "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING", -3): "hedging",
    }
    return noms.get(v, "inconnu (%s)" % v)


def nom_mode_trade(v):
    noms = {
        getattr(mt5, "SYMBOL_TRADE_MODE_DISABLED", -1): "DESACTIVE",
        getattr(mt5, "SYMBOL_TRADE_MODE_LONGONLY", -2): "achat seul",
        getattr(mt5, "SYMBOL_TRADE_MODE_SHORTONLY", -3): "vente seule",
        getattr(mt5, "SYMBOL_TRADE_MODE_CLOSEONLY", -4): "cloture seule",
        getattr(mt5, "SYMBOL_TRADE_MODE_FULL", -5): "complet",
    }
    return noms.get(v, "inconnu (%s)" % v)


def qui_pointe_vers(racine, motif):
    """Fichiers de la stack qui contiennent le chemin de ce terminal."""
    trouves = []
    if not os.path.isdir(racine):
        return None
    for dossier, sous, fichiers in os.walk(racine):
        sous[:] = [d for d in sous
                   if not d.startswith(".") and d.lower() not in ("docs", "logs")]
        for nom in fichiers:
            if not nom.lower().endswith((".py", ".bat", ".cmd")):
                continue
            chemin = os.path.join(dossier, nom)
            if os.path.abspath(chemin) == os.path.abspath(__file__):
                continue
            try:
                with io.open(chemin, encoding="utf-8", errors="replace") as f:
                    texte = f.read()
            except Exception:
                continue
            for i, ligne in enumerate(texte.splitlines(), 1):
                if motif in ligne:
                    trouves.append((os.path.relpath(chemin, racine), i,
                                    ligne.strip()[:90]))
    return trouves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--terminal", default=TERMINAL_DEFAUT)
    ap.add_argument("--compte", type=int, default=None,
                    help="numero attendu ; refus si le terminal en porte un autre")
    ap.add_argument("--racine", default=RACINE_STACK)
    args = ap.parse_args()

    print("=" * 70)
    print("sonde_compte_papers -- aucun ordre ne sera envoye")
    print("=" * 70)

    # Cette protection passe avant tout le reste : elle ne doit dependre
    # de rien, pas meme de la presence du paquet MetaTrader5.
    if os.path.abspath(args.terminal) == os.path.abspath(TERMINAL_MOTEUR):
        print("REFUS : ce chemin est celui du terminal du moteur.")
        print("La sonde ne s attache pas au compte de la stack live.")
        return 2

    if mt5 is None:
        print("MetaTrader5 introuvable dans cet interpreteur.")
        return 2

    if not os.path.isfile(args.terminal):
        print("terminal introuvable : %s" % args.terminal)
        return 2

    print("terminal vise : %s" % args.terminal)
    if not mt5.initialize(path=args.terminal):
        print("initialize a echoue : %s" % (mt5.last_error(),))
        print("Le terminal doit etre lance ET connecte avant la sonde.")
        return 1

    code_retour = 0
    try:
        ti = mt5.terminal_info()
        ai = mt5.account_info()
        if ti is None or ai is None:
            print("terminal_info ou account_info vide : %s" % (mt5.last_error(),))
            return 1

        # -- 1. sommes-nous sur le bon terminal
        print("")
        print("-" * 70)
        print("1. Terminal")
        print("-" * 70)
        print("   chemin      : %s" % ti.path)
        print("   donnees     : %s" % ti.data_path)
        print("   connecte    : %s" % oui_non(ti.connected))
        if os.path.normcase(os.path.dirname(args.terminal)) != \
           os.path.normcase(ti.path.rstrip("\\")):
            print("   NOTE : le terminal joint n est pas a l endroit demande.")

        # -- 2 et 3. compte
        print("")
        print("-" * 70)
        print("2. Compte")
        print("-" * 70)
        print("   numero      : %s" % masque(ai.login))
        print("   serveur     : %s" % ai.server)
        print("   societe     : %s" % ai.company)
        print("   solde       : %.2f %s" % (ai.balance, ai.currency))
        print("   levier      : 1:%s" % ai.leverage)
        print("   mode marge  : %s" % nom_mode_marge(ai.margin_mode))
        demo = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
        est_demo = (ai.trade_mode == demo)
        print("   demo        : %s" % oui_non(est_demo))
        if not est_demo:
            print("   ARRET LOGIQUE : ce compte n est pas une demo.")
            code_retour = 1

        if args.compte is not None and int(ai.login) != int(args.compte):
            print("   MAUVAIS COMPTE : attendu %s, trouve %s"
                  % (masque(args.compte), masque(ai.login)))
            code_retour = 1

        # -- 4 et 5. autorisations
        print("")
        print("-" * 70)
        print("3. Autorisations de trading")
        print("-" * 70)
        print("   AutoTrading (bouton Trading Algo) : %s" % oui_non(ti.trade_allowed))
        print("   trading par expert, cote compte   : %s" % oui_non(ai.trade_expert))
        print("   trading autorise, cote compte     : %s" % oui_non(ai.trade_allowed))
        if not ti.trade_allowed:
            print("")
            print("   >>> AutoTrading est ETEINT. Chaque ordre serait refuse en")
            print("   >>> rc=10027, pendant que tout le reste aurait l air de")
            print("   >>> marcher. Cliquer sur 'Trading Algo' dans ce terminal.")
            code_retour = 1

        # -- 6. symboles
        print("")
        print("-" * 70)
        print("4. Symboles")
        print("-" * 70)
        print("   %-9s %-8s %-14s %8s %8s %8s %7s"
              % ("symbole", "visible", "mode", "lot min", "pas", "lot max", "spread"))
        for s in SYMBOLES:
            info = mt5.symbol_info(s)
            if info is None:
                print("   %-9s INTROUVABLE" % s)
                code_retour = 1
                continue
            if not info.visible:
                mt5.symbol_select(s, True)
                info = mt5.symbol_info(s)
            print("   %-9s %-8s %-14s %8.2f %8.2f %8.2f %7s"
                  % (s, oui_non(info.visible), nom_mode_trade(info.trade_mode),
                     info.volume_min, info.volume_step, info.volume_max,
                     info.spread))
            plein = getattr(mt5, "SYMBOL_TRADE_MODE_FULL", None)
            if plein is not None and info.trade_mode != plein:
                code_retour = 1

        # -- positions deja presentes
        pos = mt5.positions_get() or []
        print("")
        print("   positions ouvertes sur ce compte : %d" % len(pos))
        for p in pos:
            print("      #%s %s %s vol %.2f magic %s"
                  % (p.ticket, p.symbol,
                     "BUY" if p.type == 0 else "SELL", p.volume, p.magic))

    finally:
        mt5.shutdown()

    # -- 7. interference : qui d autre pointe vers ce terminal
    print("")
    print("-" * 70)
    print("5. Qui d autre, dans la stack, pointe vers ce terminal")
    print("-" * 70)
    trouves = qui_pointe_vers(args.racine, MOTIF_CHEMIN)
    if trouves is None:
        print("   racine introuvable : %s" % args.racine)
    elif not trouves:
        print("   PERSONNE. L isolement est reel.")
    else:
        print("   %d occurrence(s) -- a examiner une par une :" % len(trouves))
        for fichier, ligne, texte in trouves:
            print("   %-34s l.%-5d %s" % (fichier, ligne, texte))
        code_retour = 1

    print("")
    print("=" * 70)
    if code_retour == 0:
        print("VERDICT : compte pret. Aucun ordre n a ete envoye.")
    else:
        print("VERDICT : au moins un point bloquant ci-dessus.")
    print("=" * 70)
    return code_retour


if __name__ == "__main__":
    sys.exit(main())
