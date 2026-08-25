#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""avant_reboot.py -- ce qu on laisse seul en appuyant sur le bouton.

POURQUOI CE FICHIER EXISTE
--------------------------
START_TRADING_STACK_V3.bat coupe tout : taskkill global sur python au
[1/5], fermeture des terminaux MT5 au [2/5]. Pendant deux a trois
minutes, les positions ouvertes ne sont plus gerees par personne.

Elles ne disparaissent pas -- elles vivent chez le courtier. Mais une
position SANS stop chez le courtier, pendant que la machine qui lui
tenait la main est eteinte, c est une perte non bornee. La question
n est donc pas "combien de positions", c est "combien sans stop".

Ce fichier ne fait que LIRE. Il n envoie aucun ordre, ne touche a
aucun processus, ne modifie aucun fichier. On peut le lancer en pleine
seance sans rien risquer.

TROIS CHOSES, DANS L ORDRE OU ELLES COMPTENT
    1. Les positions du compte principal, et pour chacune : stop pose
       ou pas. Le total sans stop est le seul chiffre qui autorise ou
       interdit le reboot.
    2. Le compte miroir, lu dans docs/cartes_live/compte.json -- c est
       l envoyeur du pont qui l ecrit toutes les dix secondes. On lit
       aussi son AGE : un instantane fige depuis une heure ne dit rien
       de l instant present, et vaut mieux etre dit que devine.
    3. Les huit processus que le .bat ne relancait pas, avant/apres.
       Le meme inventaire relance apres le reboot doit les montrer
       tous les huit -- c est le controle du patch.

USAGE
-----
    python avant_reboot.py
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time

RACINE = os.path.dirname(os.path.abspath(__file__))
COMPTE_MIROIR = os.path.join(RACINE, "docs", "cartes_live", "compte.json")

# Les huit que le .bat ne relancait pas. Motif = ce qu on cherche dans
# la ligne de commande. Il doit etre assez precis pour ne rien attraper
# d autre.
ATTENDUS = (
    ("papier_tf",      "papier_tf.py"),
    ("x60_onset",      "x60_onset.py"),
    ("rafraichir_x60", "rafraichir_x60.py"),
    ("panels_auto",    "panels_auto.py"),
    ("miroir_papers",  "miroir_papers.py"),
    ("pont lecteur",   "--lecteur"),
    ("pont envoyeur",  "--envoyeur"),
    ("gardien_stack",  "gardien_stack.py"),
)

PS_LISTE = ("Get-CimInstance Win32_Process -Filter "
            "\"Name='python.exe' OR Name='pythonw.exe'\" | "
            "ForEach-Object { [string]$_.ProcessId + ' ' "
            "+ [string]$_.CommandLine }")


def masque(n):
    """Un numero de compte ne se promene pas en clair."""
    s = str(n)
    return s if len(s) < 5 else s[:2] + "*" * (len(s) - 4) + s[-2:]


def branche(magic):
    """1 = miroir simple, 2 = soumis aux sorties, 5 = filtre CVD,
    0 = le parent lui-meme, None = hors des plages connues."""
    m = int(magic)
    if 220000 <= m <= 249999:
        return 0
    if 4220000 <= m <= 4249999:
        return 2
    if 5220000 <= m <= 5249999:
        return 5
    return None


def positions():
    try:
        import MetaTrader5 as mt5
    except Exception as e:
        print("  MetaTrader5 illisible : %s" % e)
        return None
    if not mt5.initialize():
        print("  initialize a echoue : %s" % (mt5.last_error(),))
        return None
    info = mt5.account_info()
    pos = mt5.positions_get()
    pos = list(pos) if pos else []
    if info is None:
        print("  compte illisible")
    else:
        print("  compte %s   solde %.2f   equite %.2f   flottant %+.2f"
              % (masque(info.login), info.balance, info.equity,
                 info.equity - info.balance))
    print("")
    if not pos:
        print("  AUCUNE POSITION OUVERTE. Le reboot ne laisse rien seul.")
        mt5.shutdown()
        return 0

    sans_stop = []
    print("  %-12s %-8s %-5s %-10s %-11s %s"
          % ("ticket", "symbole", "sens", "magic", "stop", "flottant"))
    print("  " + "-" * 62)
    for p in sorted(pos, key=lambda x: x.symbol):
        sens = "BUY" if p.type == 0 else "SELL"
        br = branche(p.magic)
        etq = {0: "", 2: " m2", 5: " m5"}.get(br, " ?")
        stop = ("%.2f" % p.sl) if p.sl else "AUCUN"
        if not p.sl:
            sans_stop.append(p)
        print("  %-12d %-8s %-5s %-10s %-11s %+9.2f"
              % (p.ticket, p.symbol, sens, str(p.magic) + etq, stop,
                 p.profit))
    print("")
    total = sum(x.profit for x in pos)
    print("  %d position(s), flottant total %+.2f" % (len(pos), total))
    mt5.shutdown()

    print("")
    if sans_stop:
        print("  *** %d POSITION(S) SANS STOP ***" % len(sans_stop))
        for p in sans_stop:
            print("      #%d %s %s" % (p.ticket, p.symbol,
                                       "BUY" if p.type == 0 else "SELL"))
        print("")
        print("  Ne pas rebooter comme ca. Pendant la relance, plus")
        print("  aucun processus ne les surveille et rien chez le")
        print("  courtier ne les borne. Poser un stop d abord, ou")
        print("  fermer, ou attendre qu elles se ferment seules.")
    else:
        print("  Toutes les positions portent un stop. Le courtier les")
        print("  borne meme machine eteinte : le reboot est tenable.")
    return len(sans_stop)


def miroir():
    if not os.path.isfile(COMPTE_MIROIR):
        print("  %s absent." % COMPTE_MIROIR)
        print("  L envoyeur du pont ne tourne pas, ou n a jamais ecrit.")
        return
    age = time.time() - os.path.getmtime(COMPTE_MIROIR)
    try:
        with io.open(COMPTE_MIROIR, encoding="utf-8", errors="replace") as f:
            d = json.load(f)
    except Exception as e:
        print("  illisible : %s" % e)
        return
    if age > 120:
        print("  INSTANTANE FIGE depuis %d s. Ce qui suit decrit le passe,"
              % int(age))
        print("  pas l instant present.")
    else:
        print("  instantane de %d s." % int(age))
    for cle in ("compte", "login"):
        if cle in d:
            print("  compte %s" % masque(d[cle]))
            break
    for cle in ("solde", "balance", "equite", "equity", "positions",
                "flottant"):
        if cle in d:
            print("  %-10s %s" % (cle, d[cle]))


def processus():
    try:
        s = subprocess.run(["powershell", "-NoProfile", "-Command", PS_LISTE],
                           capture_output=True, text=True, timeout=60).stdout
    except Exception as e:
        print("  inventaire impossible : %s" % e)
        return
    lignes = [l.strip() for l in s.splitlines() if l.strip()]
    print("  %d processus python en cours." % len(lignes))
    print("")
    manque = 0
    for nom, motif in ATTENDUS:
        v = [l.split(" ", 1)[0] for l in lignes if motif in l]
        if v:
            print("  %-16s en cours (%s)" % (nom, ", ".join(v)))
        else:
            print("  %-16s ARRETE" % nom)
            manque += 1
    print("")
    if manque:
        print("  %d des huit manquent. C est exactement ce que le bloc" % manque)
        print("  RELANCE_COMPLETE doit corriger : relance cet inventaire")
        print("  apres le reboot, les huit doivent y etre.")
    else:
        print("  Les huit tournent deja.")


def titre(t):
    print("")
    print("=" * 68)
    print(t)
    print("=" * 68)


def main():
    print("=" * 68)
    print("avant_reboot -- lecture seule, aucun ordre, aucun processus touche")
    print("=" * 68)

    titre("1. POSITIONS DU COMPTE PRINCIPAL")
    sans = positions()

    titre("2. COMPTE MIROIR (docs/cartes_live/compte.json)")
    miroir()

    titre("3. LES HUIT QUE LE .BAT NE RELANCAIT PAS")
    processus()

    print("")
    print("=" * 68)
    if sans:
        print("VERDICT : %d position(s) sans stop -- NE PAS REBOOTER." % sans)
    elif sans == 0:
        print("VERDICT : rien sans stop, le reboot est tenable.")
    else:
        print("VERDICT : positions non lues, je ne me prononce pas.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
