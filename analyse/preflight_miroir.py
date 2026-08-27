#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""preflight_miroir.py -- GO / NO-GO avant 14:00, et la raison nommee.

POURQUOI
--------
27/08 : le miroir a pris son premier ordre a 14:53 pour une seance qui
commence a 14:00. Une heure et vingt-sept minutes, sur cinq heures de
paper par jour. La cause tenait en une ligne -- sl_cliquet installe en
enveloppe sur mt5.order_send dans miroir_papers -- et elle a mis quatre
heures a se voir parce que le message d erreur jetait mt5.last_error() :

    res.comment if res else "sans reponse"

Le vrai motif etait (-2, 'Unnamed arguments not allowed'), et il n a
paru qu une fois le message corrige.

Ce controle aurait dit NON en dix secondes, a 13:45, avec le temps de
corriger avant l ouverture.

CE QU IL VERIFIE
----------------
  A  aucune enveloppe sl_cliquet dans le miroir ni dans le pont
     -- c est LE defaut du 27/08, et il est statique donc visible avant
  B  miroir_papers : MIROIR6, magic_trail, ACCORDS_M15
  C  pont_miroirs : les quatre plages de magics
  D  daily_watchdog : les gardes du 27/08 posees
  E  sl_cliquet : version 2.1, les miroirs hors gestion du moteur
  F  cartes_live : la branche 6 lisible
  G  les cinq services ecrivent-ils, et depuis combien de temps
  H  le terminal MOTEUR accepte-t-il un ordre -- order_check, qui
     valide une requete SANS trader
  I  le terminal DEDIE, de meme

CE QU IL NE FAIT PAS
--------------------
Il n envoie aucun ordre. order_check valide une requete aupres du
courtier et rend un retcode ; rien n est place. Il ne demarre ni
n arrete aucun processus -- c est le travail de Lancer-Miroirs.ps1, a
lancer AVANT lui.

USAGE
-----
    python preflight_miroir.py
    python preflight_miroir.py --volume 0.10

Code de sortie 0 si tout est GO, 1 s il reste un NO-GO.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time

RACINE = r"C:\SVPS\Scalp-EA-main"
TERMINAL_MOTEUR = (r"C:\Program Files\TF Global Markets MetaTrader 5 "
                   r"Termina-LOCALSTACKl\terminal64.exe")
TERMINAL_DEDIE = (r"C:\Program Files\TF Global Markets MetaTrader 5 "
                  r"Terminal\terminal64.exe")
COMPTE_MOTEUR = 178780
COMPTE_DEDIE = 182109
SYMBOLES = ("US30", "NAS100", "SPX500")
SILENCE_MAX = 180        # s : au-dela, un journal fige est un service muet

# (nom affiche, journal principal, journal propre)
# os.path.join, pas de contre-oblique dans la chaine : ecrire
# "logs\\x.txt" en dur fait un NOM DE FICHIER avec une contre-oblique
# partout ailleurs que sur Windows, et mes propres essais concluent alors
# "aucun journal" sur des fichiers qui existent.
def _j(*p):
    return os.path.join(*p)


SERVICES = (
    ("miroir",        _j("logs", "miroir_sortie.txt"),    None),
    ("pont-lecteur",  _j("logs", "pont_lect_sortie.txt"), None),
    ("pont-envoyeur", _j("logs", "pont_env_sortie.txt"),  None),
    ("trail6",        _j("logs", "trail6_sortie.txt"),
                      _j("logs", "trail_miroir6.log")),
    ("gardien",       _j("logs", "gardien_sortie.txt"),
                      _j("logs", "gardien_stops.log")),
)

RESULTATS = []


def dit(nom, ok, detail=""):
    RESULTATS.append((nom, ok, detail))
    print("  %-4s %-34s %s" % ("GO" if ok else "NON", nom, detail))
    return ok


def lire(nom):
    p = os.path.join(RACINE, nom)
    try:
        with io.open(p, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return None


def age(chemin):
    if not chemin:
        return None
    p = os.path.join(RACINE, chemin)
    if not os.path.exists(p):
        return None
    return int(time.time() - os.path.getmtime(p))


# --------------------------------------------------------- les fichiers

def controle_fichiers():
    print("")
    print("--- ce que les fichiers disent ---")

    # A : l enveloppe qui a coute 1h27
    for f in ("miroir_papers.py", "pont_miroirs.py"):
        s = lire(f)
        if s is None:
            dit("A  %s lisible" % f, False, "introuvable")
            continue
        pose = "_sl_cli.install(" in s
        dit("A  %s sans enveloppe" % f, not pose,
            "sl_cliquet.install() present -- c est le defaut du 27/08"
            if pose else "")

    # B : la branche 6 armee dans le miroir
    s = lire("miroir_papers.py")
    if s is not None:
        dit("B  MIROIR6 arme", "MIROIR6 = True" in s,
            "MIROIR6 = False ou absent" if "MIROIR6 = True" not in s else "")
        dit("B  magic_trail", "magic_trail" in s, "")
        dit("B  ACCORDS_M15", "ACCORDS_M15" in s, "")

    # C : les quatre plages du pont
    s = lire("pont_miroirs.py")
    if s is not None:
        manque = [p for p in ("220000", "4220000", "5220000", "6220000")
                  if p not in s]
        dit("C  pont : 4 plages de magics", not manque,
            "manque " + ", ".join(manque) if manque else "")
        dit("C  pont : releve des orphelines", "[ORPHELINS-2708]" in s, "")

    # D : les gardes du watchdog
    s = lire("daily_watchdog.py")
    if s is not None:
        dit("D  BE du bon cote du prix", "[BE-COTE-PRIX-2708]" in s, "")
        dit("D  R7 laisse les miroirs", "[R7-MIROIRS-2708]" in s, "")

    # E : le cliquet
    s = lire("sl_cliquet.py")
    if s is not None:
        dit("E  sl_cliquet 2.1", 'VERSION = "2.1"' in s, "")
        dit("E  plages miroir connues", "PLAGES_MIROIR" in s, "")

    # F : le panneau
    s = lire("cartes_live.py")
    if s is not None:
        dit("F  panneau : branche 6", "6220000" in s, "")


# --------------------------------------------------------- les services

def controle_services():
    print("")
    print("--- ce que les services produisent ---")
    for nom, j1, j2 in SERVICES:
        a1, a2 = age(j1), age(j2)
        cand = [x for x in (a1, a2) if x is not None]
        if not cand:
            dit("G  %s" % nom, False, "aucun journal -- jamais demarre ?")
            continue
        a = min(cand)
        dit("G  %s" % nom, a <= SILENCE_MAX,
            "journal fige depuis %d s" % a if a > SILENCE_MAX
            else "ecrit il y a %d s" % a)


# --------------------------------------------------------- les terminaux

def controle_terminal(mt5, etiquette, chemin, compte, volume):
    print("")
    print("--- %s ---" % etiquette)
    if not os.path.exists(chemin):
        dit("H  %s : terminal" % etiquette, False, "introuvable : %s" % chemin)
        return
    if not mt5.initialize(path=chemin):
        dit("H  %s : connexion" % etiquette, False, "%s" % (mt5.last_error(),))
        return
    try:
        ai, ti = mt5.account_info(), mt5.terminal_info()
        if ai is None:
            dit("H  %s : compte" % etiquette, False, "illisible")
            return
        s = str(ai.login)
        bon = int(ai.login) == compte
        dit("H  %s : compte" % etiquette, bon,
            "%s -- attendu %s" % (s[:2] + "**" + s[-2:],
                                  str(compte)[:2] + "**" + str(compte)[-2:])
            if not bon else "%s  %s" % (s[:2] + "**" + s[-2:], ai.server))
        if not bon:
            return
        dit("H  %s : AutoTrading" % etiquette,
            bool(getattr(ti, "trade_allowed", False)),
            "eteint -- chaque ordre partirait en rc=10027"
            if ti and not ti.trade_allowed else "")

        for sym in SYMBOLES:
            info = mt5.symbol_info(sym)
            tick = mt5.symbol_info_tick(sym)
            if info is None or tick is None:
                dit("I  %s : %s" % (etiquette, sym), False, "symbole illisible")
                continue
            vol = max(float(volume), float(getattr(info, "volume_min", 0.01)))
            req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym,
                   "volume": vol, "type": mt5.ORDER_TYPE_SELL,
                   "price": tick.bid, "deviation": 20, "magic": 220001,
                   "comment": "PREFLIGHT", "type_time": mt5.ORDER_TIME_GTC,
                   "type_filling": 0}
            r = mt5.order_check(req)
            if r is None:
                dit("I  %s : %s accepterait un ordre" % (etiquette, sym),
                    False, "order_check rend None -- %s" % (mt5.last_error(),))
                continue
            dit("I  %s : %s accepterait un ordre" % (etiquette, sym),
                r.retcode == 0, "" if r.retcode == 0
                else "retcode %s %s" % (r.retcode, r.comment))
    finally:
        mt5.shutdown()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--volume", type=float, default=0.10,
                    help="volume de la sonde order_check. Aucun ordre n est"
                         " envoye.")
    ap.add_argument("--sans-mt5", action="store_true",
                    help="ne teste que les fichiers et les journaux")
    a = ap.parse_args()

    print("=" * 70)
    print("  PREFLIGHT MIROIR   %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)
    print("  Aucun ordre ne sera envoye : order_check valide une requete")
    print("  aupres du courtier et rend un retcode, sans rien placer.")

    if not os.path.isdir(RACINE):
        print("ABANDON : %s introuvable." % RACINE)
        return 2
    os.chdir(RACINE)

    controle_fichiers()
    controle_services()

    if not a.sans_mt5:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            dit("H  MetaTrader5", False, "module non installe")
            mt5 = None
        if mt5 is not None:
            controle_terminal(mt5, "moteur 17**80", TERMINAL_MOTEUR,
                              COMPTE_MOTEUR, a.volume)
            controle_terminal(mt5, "dedie 18**09", TERMINAL_DEDIE,
                              COMPTE_DEDIE, a.volume)

    rates = [(n, d) for n, ok, d in RESULTATS if not ok]
    print("")
    print("=" * 70)
    if not rates:
        print("  GO -- %d controles, aucun refus." % len(RESULTATS))
        print("  Le miroir peut ouvrir a 14:00.")
        return 0
    print("  NO-GO -- %d controle(s) sur %d en echec :"
          % (len(rates), len(RESULTATS)))
    for n, d in rates:
        print("      %s%s" % (n, ("  : " + d) if d else ""))
    print("")
    print("  Corriger AVANT 14:00. Une heure perdue en seance ne se")
    print("  rattrape pas : le paper ne tourne que cinq heures par jour.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
