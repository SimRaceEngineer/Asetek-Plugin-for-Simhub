#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""corrige_marge_pont.py -- le plancher de marge, et deux defauts de journal.

TROIS CORRECTIFS, APPLIQUES ENSEMBLE
------------------------------------
Un seul arret vaut mieux que trois.

1. LE PLANCHER DE MARGE. Le miroir se protege lui-meme, ligne 71 de
   miroir_papers.py : `NIVEAU_MINI = 300.0`, verifie sur la position
   PROJETEE. Son commentaire dit pourquoi : "soixante miroirs au lot du
   parent, c est le niveau de marge qui s effondre vers 130 %, pas la
   marge libre qui manque".

   Le pont ouvre PLUS GROS que le miroir -- 1,25 contre 0,75 -- sur un
   compte PLUS PETIT. Avoir repris sa taille sans reprendre sa
   protection etait une faute. `MAX_MIROIRS = 60` et les deux branches
   comptent : a 1,25 lot le niveau tomberait vers 185 %.

   Si la marge est incalculable, on laisse passer. Refuser sur une
   mesure absente bloquerait la copie a la premiere anomalie de l API.

2. LES STOPS, IDEMPOTENTS. Le pont comparait l etat precedent de la
   source a son etat courant, sans jamais regarder notre propre
   position. Une modification qui echoue n etait donc jamais reessayee,
   et une source qui oscillerait aurait ete suivie indefiniment. On
   compare desormais a notre stop reel : rien ne part si la valeur est
   deja la bonne.

3. LE TICKET DANS LE JOURNAL. `STOPS`, `SORTIE` et `REDUCTION`
   n affichaient que le magic et le symbole. Or le miroir ouvre
   plusieurs positions sous le meme magic -- quatre `240004` sur le
   compte le 25/08 -- et deux tickets differents se lisaient alors
   comme une seule position qui oscillerait. J ai cru a une boucle sur
   cet artefact.

USAGE
-----
    python corrige_marge_pont.py                 <- simulation
    python corrige_marge_pont.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\pont_miroirs.py"
SUFFIXE_BAK = ".bak_marge"
MARQUEUR = "def niveau_projete("

R = []

R.append(('''BALANCE_PAR_LOT = 20000.0
LOT_MINI = 0.10
''', '''BALANCE_PAR_LOT = 20000.0
LOT_MINI = 0.10

# Plancher de NIVEAU de marge, verifie sur la position PROJETEE. C est
# la regle du miroir lui-meme (NIVEAU_MINI = 300.0, ligne 71 de
# miroir_papers.py), et son commentaire dit pourquoi elle existe :
# "soixante miroirs au lot du parent, c est le niveau de marge qui
# s effondre vers 130 %, pas la marge libre qui manque".
# Le pont ouvre PLUS GROS que le miroir sur un compte PLUS PETIT. Avoir
# repris sa taille sans reprendre sa protection etait une faute.
NIVEAU_MINI = 300.0     # en %, 0 pour desactiver


def niveau_projete(sym, type_ordre, vol, p):
    """Niveau de marge apres cet ordre, en %. None si incalculable --
    et dans ce cas on laisse passer : refuser sur une mesure absente
    reviendrait a bloquer la copie a la premiere anomalie de l API."""
    try:
        m = mt5.order_calc_margin(type_ordre, sym, vol, p)
        ai = mt5.account_info()
        if m is None or ai is None:
            return None
        total = float(ai.margin) + float(m)
        if total <= 0:
            return float("inf")
        return 100.0 * float(ai.equity) / total
    except Exception:
        return None
''', 1))

R.append(('''    vol = notre_lot(src["sym"])
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": src["sym"],
        "volume": vol,
        "type": mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL,''',
          '''    vol = notre_lot(src["sym"])
    type_ordre = mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL
    if NIVEAU_MINI > 0:
        niv = niveau_projete(src["sym"], type_ordre, vol, p)
        if niv is not None and niv < NIVEAU_MINI:
            dire("envoyeur", "  REFUS MARGE %s %.2f : niveau projete %.0f %%"
                 " < %.0f %%" % (src["sym"], vol, niv, NIVEAU_MINI))
            return None
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": src["sym"],
        "volume": vol,
        "type": type_ordre,''', 1))

R.append(('''def regler_stops(ticket, sl, tp, reel):
    if not reel:
        dire("envoyeur", "  [SIMULATION] sl=%.2f tp=%.2f sur %s" % (sl, tp, ticket))
        return True
    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP,
                        "position": int(ticket), "sl": sl, "tp": tp})
    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
        dire("envoyeur", "  SL/TP REFUSE rc=%s" % getattr(r, "retcode", "?"))
        return False
    return True''',
          '''def regler_stops(ticket, sl, tp, reel, etiquette=""):
    """N envoie QUE si notre stop differe deja de la cible.

    Comparer l etat precedent de la source a son etat courant ne suffit
    pas : si une modification echoue on ne la reessaie jamais, et si la
    source oscillait on la suivrait indefiniment. Le seul test qui tienne
    est celui de notre propre position.
    """
    if not reel:
        dire("envoyeur", "  [SIMULATION] %s #%s sl=%.2f tp=%.2f"
             % (etiquette, ticket, sl, tp))
        return True
    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        return True
    if abs(float(pos[0].sl) - sl) <= EPS and abs(float(pos[0].tp) - tp) <= EPS:
        return True                      # deja a la bonne valeur
    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP,
                        "position": int(ticket), "sl": sl, "tp": tp})
    if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
        dire("envoyeur", "  SL/TP REFUSE #%s rc=%s"
             % (ticket, getattr(r, "retcode", "?")))
        return False
    dire("envoyeur", "  STOPS %s #%s  %.2f -> %.2f"
         % (etiquette, ticket, float(pos[0].sl), sl))
    return True''', 1))

R.append(('''                if n is None:
                    if lien:
                        dire("envoyeur", "SORTIE M%s %s (miroir %.2f)"
                             % (a["magic"], a["sym"], a["volume"]))''',
          '''                if n is None:
                    if lien:
                        dire("envoyeur", "SORTIE M%s %s #%s (miroir %.2f)"
                             % (a["magic"], a["sym"], _tk(lien), a["volume"]))''', 1))

R.append(('''                    dire("envoyeur", "REDUCTION M%s %s %.2f  (miroir %.2f)"
                         % (a["magic"], a["sym"], notre, delta))''',
          '''                    dire("envoyeur", "REDUCTION M%s %s #%s %.2f (miroir %.2f)"
                         % (a["magic"], a["sym"], _tk(lien), notre, delta))''', 1))

R.append(('''                if lien and (abs(n["sl"] - a["sl"]) > EPS
                             or abs(n["tp"] - a["tp"]) > EPS):
                    dire("envoyeur", "STOPS M%s %s sl %.2f -> %.2f"
                         % (a["magic"], a["sym"], a["sl"], n["sl"]))
                    regler_stops(_tk(lien), n["sl"], n["tp"], args.reel)''',
          '''                if lien and (abs(n["sl"] - a["sl"]) > EPS
                             or abs(n["tp"] - a["tp"]) > EPS):
                    # regler_stops journalise lui-meme, et seulement s il
                    # a reellement envoye quelque chose.
                    regler_stops(_tk(lien), n["sl"], n["tp"], args.reel,
                                 "M%s %s" % (a["magic"], a["sym"]))''', 1))


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    args = ap.parse_args()

    print("=" * 66)
    print("corrige_marge_pont -- %s"
          % ("APPLIQUER" if args.appliquer else "SIMULATION"))
    print("=" * 66)

    if not os.path.isfile(args.cible):
        print("introuvable : %s" % args.cible)
        return 2
    s = lire(args.cible)
    print("cible : %s  (%d lignes)" % (args.cible, s.count("\n") + 1))

    if MARQUEUR in s:
        print("")
        print("Deja corrige : niveau_projete() est present.")
        return 0
    if "def notre_lot(sym):" not in s:
        print("")
        print("REFUS : corrige_taille_pont n a pas ete applique avant.")
        print("Celui-ci s appuie dessus. Faire l autre d abord.")
        return 1

    for i, (vieux, _n, att) in enumerate(R, 1):
        c = s.count(vieux)
        if c != att:
            print("")
            print("REFUS : motif %d attendu %d fois, trouve %d." % (i, att, c))
            print("   %s..." % vieux.strip().split("\n")[0][:56])
            return 1
    print("        les %d motifs sont la, aux bons comptes." % len(R))
    print("")
    print("a faire :")
    print("   + NIVEAU_MINI = 300 %% et niveau_projete(), la regle du miroir")
    print("   ~ ouverture refusee si le niveau projete passe sous 300 %%")
    print("   ~ stops : rien n est envoye si notre valeur est deja la bonne")
    print("   ~ ticket affiche dans STOPS, SORTIE et REDUCTION")

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

    for vieux, neuf, _a in R:
        s = s.replace(vieux, neuf, 1)
    with io.open(args.cible, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print("ecrit : %s" % args.cible)

    relu = lire(args.cible)
    manques = [x for x in (MARQUEUR, "REFUS MARGE", "deja a la bonne valeur",
                           'SORTIE M%s %s #%s', "REDUCTION M%s %s #%s")
               if x not in relu]
    if manques:
        print("relu   : INCOMPLET, manque %s -- restaurer %s"
              % (", ".join(manques), bak))
        return 1
    print("relu   : les cinq marques attendues sont presentes.")
    try:
        compile(relu, args.cible, "exec")
        print("syntaxe: le fichier compile.")
    except SyntaxError as e:
        print("syntaxe: ERREUR ligne %s -- restaurer %s" % (e.lineno, bak))
        return 1

    print("")
    print("-" * 66)
    print("Relancer le pont. Les positions ouvertes gardent leur lien et")
    print("seront fermees quand le miroir les fermera.")
    print("")
    print("Le journal deviendra beaucoup plus calme : les 140 modifications")
    print("par minute etaient pour l essentiel des envois inutiles, et")
    print("celles qui restent porteront leur numero de ticket.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
