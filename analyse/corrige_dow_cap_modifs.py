#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""corrige_dow_cap_modifs.py -- rendre a dow_cap_gate son perimetre d origine.

LE DEFAUT
---------
dow_cap_gate.py arbitre des ENTREES : il decide si un achat ou une vente
a le droit de partir, selon la ligne de loi de Dow M3 de l actif.

Mais il s installe en remplacant mt5.order_send, et mt5.order_send sert a
tout : ouvrir une position, MODIFIER un stop (TRADE_ACTION_SLTP), FERMER
(un DEAL qui porte le ticket de la position visee), annuler un pending.

Le fichier ne lit jamais request["action"]. Verifie le 25/08/2026 : le
mot n apparait pas une seule fois dans ses 1361 lignes.

Consequence, mesuree sur trading_engine_20260824.log :

  [MFE_TRAIL] MODIFY FAILED #172586547 rc=10020
      (DOW_CAP_US_SESSION:US30_AUTONOMOUS_FLOOR_BROKEN_DN_block_BUY)
      sl_try=53477.50 cur_sl=49434.60 peak=85.8

Une modification de stop ne porte ni magic ni type. dow_cap_gate en
deduit magic=0 -- jamais dans sa liste blanche -- et type=0, qu il
traduit en direction "BUY". Il examine donc la modification comme une
entree a l achat et la refuse des que la ligne Dow interdit le BUY.

Le trailing ne peut plus remonter aucun stop. Les positions restent sur
leur stop initial, a plusieurs milliers de points, avec 86 points de
gain au pic. 30 562 refus dans la seule journee du 24/08, soit 98,8 %
de tous les blocages du gate.

LE CORRECTIF
------------
Une porte, posee en tete de _wrapped_order_send : tout ce qui n est pas
une ouverture traverse sans examen.

Ce n est pas un desserrage de regle. C est la regle que le fichier
applique deja aux fermetures de exit_tp_manager depuis le 22/05, avec ce
motif ligne ~1180 :

    "capital protection > Dow Cap conviction"

Elle n avait ete accordee qu a un module. Elle vaut pour tous.

CE QUE LE SCRIPT NE FAIT PAS
----------------------------
- Il ne touche a aucune regle d entree. Un achat refuse hier serait
  refuse a l identique apres correction.
- Il ne touche a aucune position ouverte.
- Il ne relance rien.

Le module est deja charge en memoire dans le processus du moteur : la
correction ne prend effet qu au prochain demarrage de la stack.

USAGE
-----
    python corrige_dow_cap_modifs.py                 <- simulation
    python corrige_dow_cap_modifs.py --appliquer     <- ecrit
    python corrige_dow_cap_modifs.py --racine D:\\...
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

RACINE_DEFAUT = r"C:\SVPS\Scalp-EA-main"
CIBLE = "dow_cap_gate.py"
SUFFIXE_BAK = ".bak_modifs"
MARQUEUR = "_est_une_entree"

# Ancre : la premiere ligne du corps de _wrapped_order_send. On insere
# juste avant, pour passer avant tout autre examen.
ANCRE = "    # 2026-05-27 AI Master super-gate exempt (M154+M50002)"

HELPERS = '''
def _champ(request, nom, defaut=0):
    """Lit un champ d une requete mt5, qu elle soit dict ou objet."""
    try:
        if isinstance(request, dict):
            return request.get(nom, defaut)
        return getattr(request, nom, defaut)
    except Exception:
        return defaut


def _est_une_entree(request):
    """True seulement pour l ouverture d une position ou la pose d un pending.

    2026-08-25. mt5.order_send sert aussi a modifier un stop
    (TRADE_ACTION_SLTP) et a fermer (un DEAL qui porte le ticket de la
    position visee). Ces requetes ne portent ni magic ni type : ce gate
    en deduisait magic=0 et direction "BUY", les examinait comme des
    entrees a l achat et les refusait. Le trailing ne pouvait plus
    remonter aucun stop -- 30 562 refus le 24/08, tous des modifications.

    Ce gate arbitre des entrees. Il n a pas autorite sur la gestion d une
    position deja ouverte.
    """
    action = _champ(request, "action", None)
    if action is not None and mt5 is not None:
        ouvertures = set()
        for nom in ("TRADE_ACTION_DEAL", "TRADE_ACTION_PENDING"):
            valeur = getattr(mt5, nom, None)
            if valeur is not None:
                try:
                    ouvertures.add(int(valeur))
                except Exception:
                    pass
        try:
            if ouvertures and int(action) not in ouvertures:
                return False
        except Exception:
            pass
    # Une fermeture est un DEAL qui porte le ticket de la position visee.
    try:
        if int(_champ(request, "position", 0) or 0) != 0:
            return False
    except Exception:
        pass
    return True

'''

GARDE = '''    # 2026-08-25 : ce gate arbitre des ENTREES. Modifications de stop,
    # fermetures et annulations traversent sans examen -- meme motif que
    # le bypass ETP plus bas : capital protection > Dow Cap conviction.
    if not _est_une_entree(request):
        _stats["bypass_non_entree"] = _stats.get("bypass_non_entree", 0) + 1
        return _orig_order_send(request)

'''


def trouver(racine, nom):
    """Cherche nom sous racine. Renvoie la liste des chemins trouves."""
    trouves = []
    for dossier, sous, fichiers in os.walk(racine):
        sous[:] = [d for d in sous
                   if not d.startswith(".") and d.lower() not in ("docs", "logs")]
        if nom in fichiers:
            trouves.append(os.path.join(dossier, nom))
    return trouves


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def corriger(source):
    """Renvoie (nouveau_source, message). nouveau_source None si refus."""
    if MARQUEUR in source:
        return None, "deja corrige (%s present)" % MARQUEUR
    if ANCRE not in source:
        return None, "ancre introuvable -- le fichier a change, je m arrete"
    if source.count(ANCRE) != 1:
        return None, "ancre presente %d fois, ambigu" % source.count(ANCRE)

    tete = "def _wrapped_order_send(request):"
    if source.count(tete) != 1:
        return None, "_wrapped_order_send introuvable ou en double"

    # Les helpers vont juste avant la definition du wrapper.
    source = source.replace(tete, HELPERS.lstrip("\n") + "\n" + tete, 1)
    # La garde va en tete du corps du wrapper.
    source = source.replace(ANCRE, GARDE + ANCRE, 1)
    return source, "ok"


def voisins_suspects(dossier):
    """Autres fichiers qui remplacent mt5.order_send sans lire 'action'."""
    suspects = []
    for nom in sorted(os.listdir(dossier)):
        if not nom.endswith(".py") or nom == CIBLE:
            continue
        chemin = os.path.join(dossier, nom)
        try:
            texte = lire(chemin)
        except Exception:
            continue
        if "mt5.order_send =" not in texte:
            continue
        lit_action = ('"action"' in texte) or ("'action'" in texte)
        suspects.append((nom, lit_action))
    return suspects


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=RACINE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true",
                    help="ecrit reellement (defaut : simulation)")
    args = ap.parse_args()

    print("=" * 68)
    print("corrige_dow_cap_modifs -- %s" % ("APPLIQUER" if args.appliquer
                                            else "SIMULATION"))
    print("=" * 68)

    if not os.path.isdir(args.racine):
        print("racine introuvable : %s" % args.racine)
        return 2

    trouves = trouver(args.racine, CIBLE)
    if not trouves:
        print("%s introuvable sous %s" % (CIBLE, args.racine))
        return 2
    if len(trouves) > 1:
        print("ATTENTION : %d copies de %s" % (len(trouves), CIBLE))
        for c in trouves:
            print("   %s" % c)
        print("Je ne corrige que celle qui est a la racine de la stack.")
        racine_directe = os.path.join(args.racine, CIBLE)
        if racine_directe not in trouves:
            print("...et elle n y est pas. Je m arrete.")
            return 2
        trouves = [racine_directe]

    chemin = trouves[0]
    print("cible : %s" % chemin)

    source = lire(chemin)
    print("       %d lignes, %d octets" % (source.count("\n") + 1, len(source)))
    print("       lit request[\"action\"] : %s"
          % ("oui" if '"action"' in source else "NON  <-- c est le defaut"))

    nouveau, message = corriger(source)
    if nouveau is None:
        print("")
        print("REFUS : %s" % message)
        return 1

    print("")
    print("Insertions preparees :")
    print("   - %d lignes de helpers avant _wrapped_order_send"
          % (HELPERS.strip().count("\n") + 1))
    print("   - %d lignes de garde en tete du wrapper"
          % (GARDE.strip().count("\n") + 1))
    print("   nouveau total : %d lignes" % (nouveau.count("\n") + 1))

    if not args.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer pour ecrire.")
    else:
        bak = chemin + SUFFIXE_BAK
        if not os.path.exists(bak):
            shutil.copy2(chemin, bak)
            print("")
            print("sauvegarde : %s" % bak)
        else:
            print("")
            print("sauvegarde deja presente : %s (conservee)" % bak)
        with io.open(chemin, "w", encoding="utf-8", newline="") as f:
            f.write(nouveau)
        print("ecrit : %s" % chemin)
        # Relecture, pour ne pas se contenter d avoir cru ecrire.
        relu = lire(chemin)
        if MARQUEUR in relu and "bypass_non_entree" in relu:
            print("relu   : correctif present.")
        else:
            print("relu   : CORRECTIF ABSENT -- restaurer %s" % bak)
            return 1
        try:
            compile(relu, chemin, "exec")
            print("syntaxe: le fichier compile.")
        except SyntaxError as e:
            print("syntaxe: ERREUR ligne %s -- restaurer %s" % (e.lineno, bak))
            return 1

    print("")
    print("-" * 68)
    print("Les autres gates qui remplacent mt5.order_send :")
    voisins = voisins_suspects(os.path.dirname(chemin))
    if not voisins:
        print("   aucun.")
    for nom, lit_action in voisins:
        print("   %-38s lit 'action' : %s"
              % (nom, "oui" if lit_action else "NON  <-- meme defaut"))

    print("-" * 68)
    print("Le module est deja charge en memoire dans le processus du")
    print("moteur. La correction ne prend effet qu au prochain demarrage")
    print("de la stack. Aucune position ouverte n a ete touchee.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
