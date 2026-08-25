#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""corrige_affaires_jour.py -- la fenetre des affaires closes, en heure
                               SERVEUR et non en heure machine.

CE QUI S EST PASSE
------------------
Le 25/08 a 15:52, `cartes_live` affichait "aucune affaire close" sur
les vingt-huit lignes du panneau. C etait faux : le solde du compte
dedie etait passe de 25068 a 23989 dans l apres-midi, soit 1079 euros
REALISES. Des positions avaient donc bien cloture.

LA CAUSE
--------
`affaires_du_jour()` bornait sa recherche par

    debut = datetime.now().replace(hour=0, ...)
    deals = mt5.history_deals_get(debut, datetime.now())

`datetime.now()` est l heure de la MACHINE. MT5 horodate ses affaires
en heure du SERVEUR du courtier, qui est en avance. La borne haute
etait donc systematiquement en retard sur les affaires les plus
recentes -- c est-a-dire sur toute la seance, puisque la fenetre des
papers commence a 14:00 et que le decalage est du meme ordre.

Une fenetre calculee dans un fuseau et appliquee a des donnees d un
autre fuseau ne rate pas quelques lignes : elle en rate un bloc entier,
en silence, et ce silence ressemble a un resultat.

LE CORRECTIF
------------
On ne SUPPOSE plus l heure du serveur, on la LIT. `symbol_info_tick`
rend un horodatage serveur ; minuit serveur s en deduit exactement, et
les affaires portent la meme convention. La comparaison se fait alors
entre deux grandeurs du meme fuseau.

La requete elle-meme est volontairement LARGE -- un jour de part et
d autre -- et c est le filtre sur l horodatage qui tranche. Une borne
serree sur une convention incertaine est precisement ce qui a produit
le defaut.

Si aucun tick n est lisible, on le DIT dans l instantane (`fuseau:
"machine"`) au lieu de retomber silencieusement sur l heure locale.

USAGE
-----
    python corrige_affaires_jour.py                 <- simulation
    python corrige_affaires_jour.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\pont_miroirs.py"
SUFFIXE_BAK = ".bak_affaires"
MARQUEUR = "def minuit_serveur():"

VIEUX = '''def affaires_du_jour():
    """Les affaires closes depuis minuit, regroupees par POSITION.

    Une position close produit plusieurs deals -- l entree, la sortie,
    parfois des partiels. Le resultat d une AFFAIRE est leur somme,
    commissions et swaps compris. Compter les deals compterait deux
    fois chaque trade et donnerait un taux de reussite faux.
    """
    debut = datetime.now().replace(hour=0, minute=0, second=0,
                                   microsecond=0)
    try:
        deals = mt5.history_deals_get(debut, datetime.now())
    except Exception:
        deals = None
    if not deals:
        return []
    par_pos = {}
    for d in deals:
        pid = int(getattr(d, "position_id", 0) or 0)
        if pid == 0:
            continue'''

NEUF = '''def minuit_serveur():
    """(minuit_serveur, maintenant_serveur, fuseau) en horodatage MT5.

    L heure du COURTIER n est pas celle de la machine. Le 25/08 la
    fenetre etait calculee avec `datetime.now()` et excluait en silence
    toute la seance : le panneau affichait "aucune affaire close" alors
    que 1079 euros avaient ete realises dans l apres-midi.

    `symbol_info_tick` rend un horodatage serveur, et les affaires
    portent la meme convention : la comparaison se fait donc entre deux
    grandeurs du meme fuseau, sans rien supposer.
    """
    for s in ("US30", "US500", "US100", "EURUSD"):
        try:
            tk = mt5.symbol_info_tick(s)
        except Exception:
            tk = None
        t = int(getattr(tk, "time", 0) or 0) if tk is not None else 0
        if t > 0:
            return t - (t % 86400), t, "serveur"
    t = int(time.time())
    return t - (t % 86400), t, "machine"


def affaires_du_jour():
    """Les affaires closes depuis minuit SERVEUR, regroupees par POSITION.

    Une position close produit plusieurs deals -- l entree, la sortie,
    parfois des partiels. Le resultat d une AFFAIRE est leur somme,
    commissions et swaps compris. Compter les deals compterait deux
    fois chaque trade et donnerait un taux de reussite faux.

    La requete est LARGE -- un jour de part et d autre -- et c est le
    filtre sur l horodatage qui tranche. Une borne serree posee sur une
    convention de fuseau incertaine est exactement ce qui a produit le
    defaut du 25/08.
    """
    minuit, maintenant, _fuseau = minuit_serveur()
    try:
        deals = mt5.history_deals_get(
            datetime.utcfromtimestamp(minuit - 86400),
            datetime.utcfromtimestamp(maintenant + 86400))
    except Exception:
        deals = None
    if not deals:
        return []
    par_pos = {}
    for d in deals:
        pid = int(getattr(d, "position_id", 0) or 0)
        if pid == 0:
            continue
        if int(getattr(d, "time", 0) or 0) < minuit:
            continue'''

VIEUX_TS = '''        paquet = {"ts": time.time(),
                  "compte": {"login": int(ai.login), "serveur": ai.server,'''
NEUF_TS = '''        _minuit, _maintenant, _fuseau = minuit_serveur()
        paquet = {"ts": time.time(),
                  "minuit_serveur": _minuit, "fuseau": _fuseau,
                  "compte": {"login": int(ai.login), "serveur": ai.server,'''


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    args = ap.parse_args()

    print("=" * 66)
    print("corrige_affaires_jour -- %s"
          % ("APPLIQUER" if args.appliquer else "SIMULATION"))
    print("=" * 66)

    if not os.path.isfile(args.cible):
        print("introuvable : %s" % args.cible)
        return 2
    s = lire(args.cible)
    print("cible : %s  (%d lignes)" % (args.cible, s.count("\n") + 1))

    if MARQUEUR in s:
        print("")
        print("Deja corrige : minuit_serveur() est present.")
        return 0
    if "def affaires_du_jour(" not in s:
        print("")
        print("REFUS : corrige_pont_amortisseur n a pas ete applique avant.")
        return 1

    for i, (vieux, att) in enumerate(((VIEUX, 1), (VIEUX_TS, 1)), 1):
        c = s.count(vieux)
        if c != att:
            print("")
            print("REFUS : motif %d attendu %d fois, trouve %d." % (i, att, c))
            print("   %s..." % vieux.strip().split("\n")[0][:56])
            return 1
    print("        les 2 motifs sont la, aux bons comptes.")
    print("")
    print("a faire :")
    print("   + minuit_serveur() : l heure du courtier, LUE dans un tick")
    print("   ~ requete large, filtre sur l horodatage serveur")
    print("   + 'fuseau' dans l instantane : serveur, ou machine si le")
    print("     tick est illisible -- dit, jamais silencieux")

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

    s = s.replace(VIEUX, NEUF, 1).replace(VIEUX_TS, NEUF_TS, 1)
    with io.open(args.cible, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print("ecrit : %s" % args.cible)

    relu = lire(args.cible)
    manques = [x for x in (MARQUEUR, "minuit, maintenant, _fuseau",
                           "utcfromtimestamp(minuit - 86400)",
                           '"fuseau": _fuseau')
               if x not in relu]
    if manques:
        print("relu   : INCOMPLET, manque %s -- restaurer %s"
              % (", ".join(manques), bak))
        return 1
    print("relu   : les quatre marques attendues sont presentes.")
    try:
        compile(relu, args.cible, "exec")
        print("syntaxe: le fichier compile.")
    except SyntaxError as e:
        print("syntaxe: ERREUR ligne %s -- restaurer %s" % (e.lineno, bak))
        return 1

    print("")
    print("-" * 66)
    print("Relancer le pont, puis regenerer le panneau. Les colonnes")
    print("CONSTATE doivent alors porter des chiffres : le solde du")
    print("compte a bouge, donc des affaires ont bien cloture.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
