# -*- coding: utf-8 -*-
"""
sarkeep_gel.py -- que valent les positions quand un mouvement est declare fini ?

  python sarkeep_gel.py
  python sarkeep_gel.py --journal logs\\price_action_20260812.log

CE QU EST UN SARKEEP, ET POURQUOI CETTE ETUDE

    Le SARKEEP prend le dernier point SAR du mouvement precedent comme
    frontiere. Tant que le prix reste sous le dernier SAR d un mouvement
    haussier passe, on est en vente -- et par construction les gains de
    ce mouvement haussier ONT DEJA ETE ENCAISSES.

    Un retournement SARKEEP n est donc pas qu un filtre de direction.
    C est l instant ou un mouvement est declare TERMINE.

    D ou la question, qui n a jamais ete mesuree : a cet instant precis,
    que valent encore les positions ouvertes qui suivaient ce mouvement ?

        Si elles portent du latent qu elles rendront ensuite, le SARKEEP
        est un signal d encaissement qu on n exploite pas.

        Si elles finissent mieux que leur latent d alors, les laisser
        courir etait le bon choix, et il ne faut rien changer.

    Aujourd hui le SARKEEP ne sert qu a REFUSER des entrees
    (adaptive_ml_trader, autolearn_trader : "SARKEEP:NOT_CONFIRMED").
    L utiliser en sortie serait un usage neuf. Cette etude ne valide donc
    rien d existant : elle teste une idee, et elle demarre a zero.

CE QU IL FAIT

    Il suit le journal de price_action et, a CHAQUE ligne [SARKEEP],
    prend un instantane de toutes les positions ouvertes.

    Il n agit pas. Il ne ferme rien, ne deplace aucun stop, n envoie
    aucun ordre. Il regarde ce que l action aurait rencontre.

    Une ligne par couple (retournement, position). Plus une ligne sans
    position quand le retournement survient a plat -- ca compte aussi :
    un signal qui se declenche quand on n a rien en portefeuille ne
    rapporte rien.

LA COLONNE QUI PORTE TOUT

    `suivait_le_mouvement` : la position allait-elle dans le sens du
    mouvement qui vient de se terminer ?

        flip BULL->BEAR  ->  les ACHATS sur cet actif suivaient
        flip BEAR->BULL  ->  les VENTES sur cet actif suivaient

    Ce sont celles-la, et elles seules, que le signal designerait comme
    a encaisser. Les autres sont enregistrees comme temoins.

CE QU IL NE FAIT PAS

    Il ne conclut pas. Le verdict demande le P&L REALISE, qui n existe
    qu a la fermeture : on joint ensuite sur le ticket avec
    tickets_rails.jsonl, et on compare le latent au moment du signal au
    resultat final. Deux nombres mesures, soustraits -- ni simulation ni
    modele.

    Il ne suppose aucun pas de temps. Il enregistre TOUS les champs
    cle=valeur de la ligne (SarKeep, SarKeep3, SarKeepPrev, confirms),
    tels quels. Si SarKeep3 designe du M3 et pas du M5, la donnee le
    dira -- ce n est pas a ce script d en decider.

LE PROTOCOLE, POSE AVANT LA COLLECTE

    Unite      : la seance, pas le retournement.
    Fenetre    : du 13/08 au 31/08.
    Verdict    : 01/09, le meme jour que le gel V9.
    Critere    : sur les seances, la somme (latent_au_signal - realise)
                 des positions qui suivaient le mouvement doit etre
                 positive, avec un test du signe a p <= 0,05.
    Comparateur: les memes positions qui NE suivaient PAS le mouvement.
                 Sans elles on mesurerait l humeur du marche, pas le
                 signal.

    Ecrit d avance pour pouvoir REFUTER. Si le critere n est pas atteint,
    on ne branche rien -- quel que soit le total en euros.

LECTURE SEULE. Un fichier par jour. Ctrl+C pour arreter.
"""
import argparse
import csv
import io
import os
import re
import sys
import time
from datetime import datetime

try:
    import MetaTrader5 as mt5
except ImportError:
    print("KO : MetaTrader5 introuvable dans cet interpreteur.")
    sys.exit(1)

DOSSIER = os.path.join("docs", "sarkeep_gel")
RE_FLIP = re.compile(
    r"\[SARKEEP\]\s+(\S+)\s+flip\s+(\w+)\s*->\s*(\w+)\s*\|?\s*(.*)$")
RE_KV = re.compile(r"(\w+)=([^\s|]+)")
COLONNES = ["ts", "actif_flip", "de", "vers", "sarkeep", "sarkeep3",
            "sarkeep_prev", "confirms", "ticket", "magic", "symbole", "sens",
            "suivait_le_mouvement", "prix_open", "prix_courant", "sl", "tp",
            "profit_latent", "pic_pts", "age_s", "n_positions"]


def journal_du_jour(dossier="logs"):
    n = "price_action_%s.log" % datetime.now().strftime("%Y%m%d")
    return os.path.join(dossier, n)


def ouvrir_sortie(dossier):
    os.makedirs(dossier, exist_ok=True)
    ch = os.path.join(dossier, "sarkeep_gel_%s.csv"
                      % datetime.now().strftime("%Y%m%d"))
    neuf = not os.path.exists(ch) or os.path.getsize(ch) == 0
    f = io.open(ch, "a", encoding="utf-8", newline="")
    w = csv.DictWriter(f, fieldnames=COLONNES)
    if neuf:
        w.writeheader()
        f.flush()
    return ch, f, w


def meme_actif(symbole, actif):
    """US100 / NAS100 / US100.cash : on compare sans se formaliser."""
    a, b = symbole.upper(), actif.upper()
    return a.startswith(b) or b.startswith(a)


def suivait(sens, de):
    """La position allait-elle dans le sens du mouvement qui se termine ?"""
    if de.upper() == "BULL":
        return sens == "ACHAT"
    if de.upper() == "BEAR":
        return sens == "VENTE"
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--journal", default=None)
    p.add_argument("--dossier", default=DOSSIER)
    p.add_argument("--intervalle", type=float, default=1.0)
    a = p.parse_args()

    jr = a.journal or journal_du_jour()
    if not os.path.isfile(jr):
        print("KO : journal introuvable : %s" % jr)
        print("Le moteur price_action doit tourner et ecrire dans logs\\.")
        return 1

    if not mt5.initialize():
        print("KO : mt5.initialize() a echoue -- %s" % (mt5.last_error(),))
        return 1

    ch, f, w = ouvrir_sortie(a.dossier)
    print("=" * 76)
    print(" SCALP-EA / SARKEEP VIRTUEL -- LECTURE SEULE")
    print("=" * 76)
    print("journal suivi : %s" % jr)
    print("sortie        : %s" % ch)
    print()
    print("A chaque retournement SARKEEP, instantane des positions ouvertes.")
    print("Aucun ordre n est envoye. Ctrl+C pour arreter.")
    print()

    n_flips = n_lignes = 0
    src = io.open(jr, encoding="utf-8", errors="replace")
    src.seek(0, os.SEEK_END)        # on part de la fin : le passe est deja
    debut = {}                      # ticket -> premiere vue (pour l age)

    def instantane(actif, de, vers, kv):
        nonlocal n_flips, n_lignes
        n_flips += 1
        pos = mt5.positions_get() or []
        base = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "actif_flip": actif, "de": de, "vers": vers,
            "sarkeep": kv.get("SarKeep", ""),
            "sarkeep3": kv.get("SarKeep3", ""),
            "sarkeep_prev": kv.get("SarKeepPrev", ""),
            "confirms": kv.get("confirms", ""),
            "n_positions": len(pos),
        }
        if not pos:
            # Un signal qui se declenche a plat ne rapporte rien. On
            # l ecrit quand meme : sinon on surestimerait sa valeur en ne
            # gardant que les fois ou il y avait quelque chose a prendre.
            r = dict(base)
            for c in COLONNES:
                r.setdefault(c, "")
            w.writerow(r)
            n_lignes += 1
            f.flush()
            return

        for q in pos:
            sens = "ACHAT" if q.type == 0 else "VENTE"
            si = mt5.symbol_info(q.symbol)
            pt = si.point if si and si.point else 0.01
            pic = ((q.price_current - q.price_open) if sens == "ACHAT"
                   else (q.price_open - q.price_current)) / pt
            t0 = debut.setdefault(q.ticket, time.time())
            m = meme_actif(q.symbol, actif)
            sv = suivait(sens, de) if m else None
            r = dict(base)
            r.update({
                "ticket": q.ticket, "magic": q.magic, "symbole": q.symbol,
                "sens": sens,
                "suivait_le_mouvement": ("" if sv is None
                                         else ("oui" if sv else "non")),
                "prix_open": q.price_open, "prix_courant": q.price_current,
                "sl": q.sl, "tp": q.tp,
                "profit_latent": round(q.profit, 2),
                "pic_pts": round(max(0.0, pic), 1),
                "age_s": int(time.time() - t0),
            })
            w.writerow(r)
            n_lignes += 1
        f.flush()

    try:
        while True:
            ligne = src.readline()
            if not ligne:
                time.sleep(a.intervalle)
                continue
            m = RE_FLIP.search(ligne)
            if not m:
                continue
            actif, de, vers, reste = m.groups()
            kv = dict(RE_KV.findall(reste or ""))
            instantane(actif, de, vers, kv)
            if n_flips % 10 == 0:
                try:
                    print("[%s] %d retournements, %d lignes ecrites"
                          % (datetime.now().strftime("%H:%M:%S"),
                             n_flips, n_lignes))
                except Exception:
                    pass
    except KeyboardInterrupt:
        print()
        print("Arret demande.")
    finally:
        try:
            print("%d retournements, %d lignes." % (n_flips, n_lignes))
            print("sortie : %s" % ch)
            print()
            print("Le verdict demande le P&L REALISE : joindre sur le ticket")
            print("avec docs\\rails_trades\\tickets_rails.jsonl apres la")
            print("cloture, et comparer profit_latent au resultat final.")
        except Exception:
            pass
        src.close()
        f.close()
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
