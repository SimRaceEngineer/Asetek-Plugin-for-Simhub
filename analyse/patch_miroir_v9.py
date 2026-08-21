# -*- coding: utf-8 -*-
"""
patch_miroir_v9.py -- passe miroir_papers.py de la v8 a la v9.

  python patch_miroir_v9.py --essai
  python patch_miroir_v9.py

CE QUE LA v9 AJOUTE : LE MIROIR 2

  Chaque paper envoie desormais DEUX ordres au lieu d un :

    magic M      -- exempte des autres modules depuis le 21/08, il ne
                    sort que quand son parent sort.
    magic 4M     -- 240004 devient 4240004. Hors de la plage
                    220000-249999, donc AUCUNE exemption : M154_FOLLOW,
                    IGN_COVER et PREOPEN_75 le traitent comme avant.

  Les deux recoivent la meme recopie de SL et le meme suivi de volume
  partiel. C est la condition pour que l ecart mesure entre les deux
  soit attribuable au REGIME DE SORTIE et a rien d autre : un stop qui
  aurait diverge en route se melangerait a ce qu on veut mesurer.

  La marge est verifiee pour DEUX ordres avant d envoyer le premier.
  Sans ca, le plafond pourrait couper entre les deux et laisser une
  paire boiteuse -- un parent avec un miroir 1 et pas de miroir 2 ne
  compte dans aucune comparaison. Une paire incomplete est journalisee
  comme telle.

  MAX_MIROIRS compte les deux branches : a nombre de miroirs egal, deux
  fois moins de parents seront couverts. C est le bon arbitrage pour
  une comparaison appariee.

POURQUOI UN PATCH ET PAS LE FICHIER ENTIER

  La v8 deposee sur le Drive fait 41560 octets et c est exactement
  celle qui tourne. La base est donc connue a l octet pres, ce qui n a
  pas ete le cas ce matin : le v6 du VPS avait 3492 octets de moins que
  le mien et personne ne l avait vu. Les ancres verifient cette base.

  Le script relit le resultat avec ast.parse, garde une copie
  miroir_papers.v8.py, et n ecrit rien si une seule ancre manque.

APRES

  Il faut RELANCER le miroir pour que la v9 prenne effet.
"""
import argparse
import ast
import io
import os
import shutil
import sys

CIBLE = "miroir_papers.py"
MARQUE = "MIROIR2"

PAIRES = [
    ('# vers 130 %, pas la marge libre qui manque. Ce plancher-ci mord.\nNIVEAU_MINI = 300.0     # en %, 0 pour desactiver\n\nMAX_MIROIRS = 60\nPOLL_SEC = 0.5\n\n# Surveillance. Le 21/08 la boucle a tourne six heures sans ecrire une\n',
     '# vers 130 %, pas la marge libre qui manque. Ce plancher-ci mord.\nNIVEAU_MINI = 300.0     # en %, 0 pour desactiver\n\n# --- MIROIR 2 : la meme entree, l ancien regime de sortie ------------------\n# Le miroir 1 (magics 220xxx/230xxx/240xxx) est exempte de M154_FOLLOW,\n# IGN_COVER et PREOPEN_75 : il sort quand son parent sort, point.\n# Le miroir 2 porte le meme magic prefixe d un 4 -- 240004 -> 4240004 --\n# donc hors de la plage 220000-249999 de papers_exempt, donc soumis aux\n# autres modules comme avant. Meme entree, meme lot, meme instant : le\n# seul ecart entre les deux est ce qui decide de la SORTIE.\n#\n# UNE SEULE difference separe les branches : qui decide de la SORTIE.\n# Tout le reste est tenu identique -- meme lot, meme SL a l entree,\n# meme recopie du SL apres l entree, meme suivi du volume sur solde\n# partiel. C est la condition pour que l ecart mesure entre les deux\n# soit attribuable au regime de sortie et a rien d autre.\nMIROIR2 = True\n\nMAX_MIROIRS = 60        # compte les DEUX branches\nPOLL_SEC = 0.5\n\n# Surveillance. Le 21/08 la boucle a tourne six heures sans ecrire une\n'),
    ('               miroirs, vieux))\n\n\ndef calcule_lot(info, pos):\n    """Le volume du miroir, normalise au pas du symbole."""\n    if LOT == "parent":\n',
     '               miroirs, vieux))\n\n\ndef magic_double(magic):\n    """240004 -> 4240004. Hors de toute plage exemptee."""\n    return int("4%d" % int(magic))\n\n\ndef est_miroir2(magic):\n    """Le 4 de tete pousse le magic au-dela du million."""\n    try:\n        return int(magic) >= 1000000\n    except (TypeError, ValueError):\n        return False\n\n\ndef calcule_lot(info, pos):\n    """Le volume du miroir, normalise au pas du symbole."""\n    if LOT == "parent":\n'),
    ('    return v\n\n\ndef marge_tient(mt5, symbole, achat, lot, prix):\n    """(bool, message). Non calculable => on laisse passer, et on le dit."""\n    try:\n        besoin = mt5.order_calc_margin(\n            mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL,\n',
     '    return v\n\n\ndef marge_tient(mt5, symbole, achat, lot, prix, combien=1):\n    """(bool, message). Non calculable => on laisse passer, et on le dit.\n\n    combien : nombre d ordres que l on s apprete a envoyer d un bloc.\n    Avec le miroir 2, les deux partent ensemble ou pas du tout : les\n    verifier un par un laisserait passer le premier et refuser le\n    second, ce qui casserait la paire et donc la comparaison.\n    """\n    try:\n        besoin = mt5.order_calc_margin(\n            mt5.ORDER_TYPE_BUY if achat else mt5.ORDER_TYPE_SELL,\n'),
    ('        return True, "marge non calculable (%s)" % e\n    if not besoin:\n        return True, "marge non calculable"\n    ai = mt5.account_info()\n    libre = float(getattr(ai, "margin_free", 0) or 0)\n    if not libre:\n',
     '        return True, "marge non calculable (%s)" % e\n    if not besoin:\n        return True, "marge non calculable"\n    besoin = besoin * max(1, int(combien))\n    ai = mt5.account_info()\n    libre = float(getattr(ai, "margin_free", 0) or 0)\n    if not libre:\n'),
    ('        self.sl_refus = {}\n\n    # -- envoi -----------------------------------------------------------\n    def envoie(self, pos, rec, magic, nom, t_signal):\n        mt5 = self.mt5\n        info = mt5.symbol_info(pos.symbol)\n        tick = mt5.symbol_info_tick(pos.symbol)\n',
     '        self.sl_refus = {}\n\n    # -- envoi -----------------------------------------------------------\n    def envoie(self, pos, rec, magic, nom, t_signal, combien=1):\n        mt5 = self.mt5\n        info = mt5.symbol_info(pos.symbol)\n        tick = mt5.symbol_info_tick(pos.symbol)\n'),
    ('        spread = (tick.ask - tick.bid) / info.point if info.point else 0.0\n        lot = calcule_lot(info, pos)\n\n        ok_marge, note = marge_tient(mt5, pos.symbol, achat, lot, prix)\n        if not ok_marge:\n            csv_ligne({\n                "evenement": "MARGE", "ticket_parent": pos.ticket,\n',
     '        spread = (tick.ask - tick.bid) / info.point if info.point else 0.0\n        lot = calcule_lot(info, pos)\n\n        ok_marge, note = marge_tient(mt5, pos.symbol, achat, lot, prix,\n                                     combien)\n        if not ok_marge:\n            csv_ligne({\n                "evenement": "MARGE", "ticket_parent": pos.ticket,\n'),
    ('        miroir est SEUL a les gerer : s il ne suit pas, sa sortie n a\n        plus rien a voir avec celle de son parent et la comparaison\n        qu on cherche a faire perd son sens.\n\n        La regle compare les deux etats REELS plutot que de suivre les\n        changements. C est ce qui la rend auto-reparatrice : apres un\n',
     '        miroir est SEUL a les gerer : s il ne suit pas, sa sortie n a\n        plus rien a voir avec celle de son parent et la comparaison\n        qu on cherche a faire perd son sens.\n\n        Les DEUX branches en beneficient, miroir 2 compris : lui aussi\n        doit rester une copie fidele de son parent partout ailleurs,\n        sans quoi l ecart mesure entre les branches melangerait le\n        regime de sortie avec un stop qui a diverge en cours de route.\n\n        La regle compare les deux etats REELS plutot que de suivre les\n        changements. C est ce qui la rend auto-reparatrice : apres un\n'),
    ('                        "volume_miroir": (calcule_lot(info, pos)\n                                          if info else None)})\n                    continue\n                tm, e = self.envoie(pos, rec, magic, nom, t_signal)\n                if tm:\n                    self.liens.setdefault(tk, []).append((magic, tm))\n                    dit("    M%s envoye, ticket %s" % (magic, tm))\n                else:\n                    dit("    M%s REFUSE : %s" % (magic, e))\n            ecrit_liens(self.liens)\n\n\n',
     '                        "volume_miroir": (calcule_lot(info, pos)\n                                          if info else None)})\n                    continue\n                combien = 2 if MIROIR2 else 1\n                tm, e = self.envoie(pos, rec, magic, nom, t_signal, combien)\n                if not tm:\n                    dit("    M%s REFUSE : %s" % (magic, e))\n                    continue\n                self.liens.setdefault(tk, []).append((magic, tm))\n                dit("    M%s envoye, ticket %s" % (magic, tm))\n                if not MIROIR2:\n                    continue\n                # La marge a deja ete verifiee pour DEUX ordres avant le\n                # premier : le second ne peut donc pas se voir refuser\n                # pour cette raison, et la paire reste entiere.\n                m2 = magic_double(magic)\n                tm2, e2 = self.envoie(pos, rec, m2, nom, t_signal, 1)\n                if tm2:\n                    self.liens.setdefault(tk, []).append((m2, tm2))\n                    dit("    M%s envoye, ticket %s  (ancien regime)"\n                        % (m2, tm2))\n                else:\n                    dit("    M%s REFUSE : %s  -- paire incomplete,"\n                        " ce parent ne comptera pas" % (m2, e2))\n            ecrit_liens(self.liens)\n\n\n'),
    ('        print("           sous-estime : ce n est pas la taille reelle.")\n    else:\n        print("  volume : %s" % (LOT,))\n    print("  refus au-dela de %.0f %% de la marge libre, avant chaque ordre."\n          % (MARGE_MAXI * 100))\n    if NIVEAU_MINI:\n',
     '        print("           sous-estime : ce n est pas la taille reelle.")\n    else:\n        print("  volume : %s" % (LOT,))\n    if MIROIR2:\n        print()\n        print("  MIROIR 2 ACTIF : chaque paper envoie DEUX ordres.")\n        print("    magic tel quel  -> exempte, sort avec son parent")\n        print("    magic prefixe 4 -> soumis aux autres modules, comme avant")\n        print("    les deux partent ensemble ou pas du tout.")\n        print()\n    print("  refus au-dela de %.0f %% de la marge libre, avant chaque ordre."\n          % (MARGE_MAXI * 100))\n    if NIVEAU_MINI:\n'),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        print("Repertoire courant : %s" % os.getcwd())
        return 1
    s = io.open(CIBLE, encoding="utf-8").read()
    if MARQUE in s:
        print("Deja en v9 -- le miroir 2 est present.")
        return 0
    manque = [i for i, (av, _ap) in enumerate(PAIRES, 1) if s.count(av) != 1]
    if manque:
        print("KO : %d ancre(s) introuvable(s) ou ambigue(s) : %s"
              % (len(manque), ", ".join(str(i) for i in manque)))
        print("Le fichier n est pas la v8 attendue (41560 octets).")
        print("Il fait %d octets. RIEN n a ete ecrit." % len(s.encode("utf-8")))
        print("Reprends miroir_papers_v8.py sur le Drive avant de patcher.")
        return 1
    neuf = s
    for av, ap in PAIRES:
        neuf = neuf.replace(av, ap, 1)
    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (%s). RIEN n a ete ecrit." % e)
        return 1
    if a.essai:
        print("PRET : %d -> %d octets, %d hunk(s), le resultat compile."
              % (len(s.encode("utf-8")), len(neuf.encode("utf-8")),
                 len(PAIRES)))
        print("Rien n est ecrit. Relance sans --essai.")
        return 0
    shutil.copy2(CIBLE, "miroir_papers.v8.py")
    io.open(CIBLE, "w", encoding="utf-8", newline="\n").write(neuf)
    print("v9 ecrite : %d octets, %d hunk(s) appliques."
          % (len(neuf.encode("utf-8")), len(PAIRES)))
    print("Copie de secours : miroir_papers.v8.py")
    print("")
    print("Il reste a RELANCER le miroir pour que la v9 prenne effet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
