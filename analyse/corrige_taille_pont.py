#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""corrige_taille_pont.py -- dimensionner sur le compte dedie.

CE QU ON CORRIGE
----------------
Le pont recopiait le volume du miroir. Or ce volume vient de `lot_de`
applique a la balance du compte du MOTEUR -- environ 15 000 EUR -- d ou
les 0,75 observes le 25/08 alors que le compte dedie porte 25 000.

    0,76 -> balance 15 200
    0,75 -> balance 15 000
    0,71 -> balance 14 200

La regle du 1 lot pour 20 000 etait donc respectee, mais sur le mauvais
compte. Tout l interet d un compte neuf est que la taille suive sa
propre equite : 25 000 / 20 000 = 1,25, et elle bougera avec lui.

CE QUE CA IMPLIQUE
------------------
Si nous ouvrons 1,25 la ou le miroir ouvre 0,75, une fermeture partielle
ne peut plus se copier en volume. Quand le miroir passe de 0,75 a 0,23,
fermer 0,52 comme lui ferait diverger les deux positions des le premier
partiel.

On travaille donc en PROPORTION. Chaque lien retient le rapport k entre
notre taille et la sienne, et toute reduction ferme k fois la sienne.

Les liens deja ecrits sont de simple tickets, sans rapport. Ils sont
lus avec k = 1 -- ce qui est exact, puisque ces positions-la ont ete
prises au volume du miroir.

Une sortie TOTALE ne recalcule rien : elle ferme tout ce qui reste. La
position a pu etre entamee, et recalculer un volume exposerait a en
laisser un residu ouvert.

USAGE
-----
    python corrige_taille_pont.py                 <- simulation
    python corrige_taille_pont.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\pont_miroirs.py"
SUFFIXE_BAK = ".bak_taille"
MARQUEUR = "def notre_lot(sym):"

R = []

R.append(('''def prix(sym, achat):''', '''BALANCE_PAR_LOT = 20000.0
LOT_MINI = 0.10


def notre_lot(sym):
    """La regle des papers -- balance / 20000, plancher 0.10 -- mais
    appliquee a la balance du compte DEDIE, relue avant chaque prise.

    C est tout l interet d un compte neuf : la taille suit sa propre
    equite. Copier le volume du miroir revenait a dimensionner sur la
    balance du compte du moteur, qui n a rien a voir -- d ou les 0,75
    observes le 25/08 alors que 25 000 / 20 000 fait 1,25.
    """
    try:
        bal = float(mt5.account_info().balance)
    except Exception:
        bal = BALANCE_PAR_LOT
    brut = max(LOT_MINI, bal / BALANCE_PAR_LOT)
    try:
        si = mt5.symbol_info(sym)
        pas = float(si.volume_step) or 0.01
        v = max(float(si.volume_min) or LOT_MINI,
                round(round(brut / pas) * pas, 2))
        return min(v, float(si.volume_max) or 100.0)
    except Exception:
        return round(brut, 2)


def _tk(lien):
    """Le lien etait un simple ticket avant le 25/08 15h ; il porte
    maintenant aussi le rapport de taille. On lit les deux formes."""
    return int(lien["ticket"]) if isinstance(lien, dict) else int(lien)


def _k(lien):
    return float(lien.get("k", 1.0)) if isinstance(lien, dict) else 1.0


def prix(sym, achat):''', 1))

R.append(('''    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": src["sym"],
        "volume": src["volume"],''', '''    vol = notre_lot(src["sym"])
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": src["sym"],
        "volume": vol,''', 1))

R.append(('''        dire("envoyeur", "  [SIMULATION] ouvrir %s %s %.2f @ %.2f sl=%.2f"
             % (src["sym"], "BUY" if achat else "SELL", src["volume"], p,
                src["sl"]))
        return None''', '''        dire("envoyeur", "  [SIMULATION] ouvrir %s %s %.2f @ %.2f sl=%.2f"
             % (src["sym"], "BUY" if achat else "SELL", vol, p, src["sl"]))
        return None''', 1))

R.append(('''    dire("envoyeur", "  ouvert : ticket %s @ %.2f" % (r.order, r.price))
    return int(r.order)''', '''    dire("envoyeur", "  ouvert : ticket %s  %.2f lot @ %.2f  (miroir %.2f)"
         % (r.order, vol, r.price, src["volume"]))
    return int(r.order), vol''', 1))

R.append(('''def fermer(ticket, sym, sens_src, volume, reel):
    if reel:
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            return True
        volume = min(volume, float(pos[0].volume))''', '''def fermer(ticket, sym, sens_src, volume, reel):
    """volume None = tout ce qui reste. Sur une sortie totale c est plus
    sur que de recalculer : la position peut avoir ete entamee."""
    if reel:
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            return True
        reste = float(pos[0].volume)
        volume = reste if volume is None else min(volume, reste)
    elif volume is None:
        volume = 0.0''', 1))

R.append(('''                if n is None:
                    if lien:
                        dire("envoyeur", "SORTIE M%s %s %.2f"
                             % (a["magic"], a["sym"], a["volume"]))
                        if fermer(lien, a["sym"], a["sens"], a["volume"], args.reel):
                            liens.pop(tk, None)
                            ecrire_atomique(LIENS, liens)
                    continue
                if n["volume"] < a["volume"] - EPS and lien:
                    delta = round(a["volume"] - n["volume"], 2)
                    dire("envoyeur", "REDUCTION M%s %s %.2f"
                         % (a["magic"], a["sym"], delta))
                    fermer(lien, a["sym"], a["sens"], delta, args.reel)
                if lien and (abs(n["sl"] - a["sl"]) > EPS
                             or abs(n["tp"] - a["tp"]) > EPS):
                    dire("envoyeur", "STOPS M%s %s sl %.2f -> %.2f"
                         % (a["magic"], a["sym"], a["sl"], n["sl"]))
                    regler_stops(lien, n["sl"], n["tp"], args.reel)''',
          '''                if n is None:
                    if lien:
                        dire("envoyeur", "SORTIE M%s %s (miroir %.2f)"
                             % (a["magic"], a["sym"], a["volume"]))
                        # None = tout ce qui reste. La position a pu etre
                        # entamee par un partiel ; recalculer un volume
                        # exposerait a en laisser un residu ouvert.
                        if fermer(_tk(lien), a["sym"], a["sens"], None,
                                  args.reel):
                            liens.pop(tk, None)
                            ecrire_atomique(LIENS, liens)
                    continue
                if n["volume"] < a["volume"] - EPS and lien:
                    delta = round(a["volume"] - n["volume"], 2)
                    # On ferme la meme PROPORTION, pas le meme volume :
                    # nos tailles different de k, et fermer 0,52 quand le
                    # miroir en ferme 0,52 ferait diverger les deux
                    # positions des le premier partiel.
                    notre = round(delta * _k(lien), 2)
                    dire("envoyeur", "REDUCTION M%s %s %.2f  (miroir %.2f)"
                         % (a["magic"], a["sym"], notre, delta))
                    fermer(_tk(lien), a["sym"], a["sens"], notre, args.reel)
                if lien and (abs(n["sl"] - a["sl"]) > EPS
                             or abs(n["tp"] - a["tp"]) > EPS):
                    dire("envoyeur", "STOPS M%s %s sl %.2f -> %.2f"
                         % (a["magic"], a["sym"], a["sl"], n["sl"]))
                    regler_stops(_tk(lien), n["sl"], n["tp"], args.reel)''', 1))

R.append(('''                t = ouvrir(n, args.reel)
                if t:
                    liens[tk] = t
                    ecrire_atomique(LIENS, liens)''',
          '''                res = ouvrir(n, args.reel)
                if res:
                    ticket_nous, vol_nous = res
                    src = float(n["volume"]) or 1.0
                    liens[tk] = {"ticket": ticket_nous,
                                 "k": round(vol_nous / src, 6)}
                    ecrire_atomique(LIENS, liens)''', 1))


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    args = ap.parse_args()

    print("=" * 66)
    print("corrige_taille_pont -- %s"
          % ("APPLIQUER" if args.appliquer else "SIMULATION"))
    print("=" * 66)

    if not os.path.isfile(args.cible):
        print("introuvable : %s" % args.cible)
        return 2
    s = lire(args.cible)
    print("cible : %s  (%d lignes)" % (args.cible, s.count("\n") + 1))

    if MARQUEUR in s:
        print("")
        print("Deja corrige : notre_lot() est present.")
        return 0

    for i, (vieux, _neuf, attendu) in enumerate(R, 1):
        n = s.count(vieux)
        if n != attendu:
            print("")
            print("REFUS : motif %d attendu %d fois, trouve %d."
                  % (i, attendu, n))
            print("   %s..." % vieux.strip().split("\n")[0][:56])
            print("Le fichier n est pas celui que j attends. Je m arrete.")
            return 1
    print("        les %d motifs sont la, aux bons comptes." % len(R))
    print("")
    print("a faire :")
    print("   + notre_lot(), _tk(), _k()")
    print("   ~ ouverture au lot du compte dedie, et rend (ticket, volume)")
    print("   ~ reduction proportionnelle : k fois celle du miroir")
    print("   ~ sortie totale : tout ce qui reste, sans recalcul")
    print("   ~ liens : {ticket, k} au lieu d un simple ticket")

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
    manques = [m for m in (MARQUEUR, "def _tk(lien):", "notre_lot(src[",
                           'round(vol_nous / src, 6)', "delta * _k(lien)")
               if m not in relu]
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
    print("Le pont doit etre relance. Les positions deja ouvertes gardent")
    print("leur lien : le nouvel envoyeur relit liens.json au demarrage et")
    print("les fermera quand le miroir les fermera. Elles avaient ete")
    print("prises au volume du miroir, donc leur rapport vaut 1 -- ce que")
    print("l ancienne forme du lien rend exactement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
