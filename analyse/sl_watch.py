# -*- coding: utf-8 -*-
"""
sl_watch.py -- la trajectoire de chaque stop, quel qu en soit l auteur

  python sl_watch.py
  python sl_watch.py --intervalle 3 --dossier docs\\sl_watch

POURQUOI CE MONTAGE, ET PAS UN AUTRE

    On voulait mesurer le SAR. On a decouvert que le chemin Python du
    SAR est debranche : ea_autonomy_guard.is_autonomy_on() vaut True et
    sar_anchor.dat n existe meme pas. L EA calcule son SAR dans MT5 et
    n ecrit rien cote Python. Les compteurs [TRAIL] et [ANCHOR TRAIL] a
    zero mesuraient donc du code mort.

    Instrumenter un module de plus aurait reproduit la meme erreur. On
    observe donc LE STOP LUI-MEME.

    Ce programme ne sait pas qui deplace un SL et ne cherche pas a le
    savoir. Il constate. Il capte donc TOUS les auteurs a la fois --
    SAR de l EA, trail MFE, closer Python, C14, sortie manuelle -- et il
    survivra a tout ce qu on patchera ensuite.

CE QU IL ECRIT

    Une ligne par EVENEMENT, jamais une ligne par cycle :

      DEBUT      premiere fois qu on voit ce ticket
      SL         le stop a bouge (avec avant, apres, et le sens du mouvement)
      TP         le take profit a bouge
      FIN        le ticket a disparu -- position fermee

    Colonnes : horodatage, evenement, ticket, magic, symbole, sens,
    volume, prix d entree, prix courant, sl_avant, sl_apres, la distance
    du nouveau SL a l entree EN POINTS ET EN POURCENT du prix, le profit
    latent, le pic favorable vu depuis l ouverture, et l age du ticket.

    La distance en pourcent est la grandeur qui compte : c est elle qui
    se compare a la fenetre de C14 (0,040 % sur US30/US500, 0,069 % sur
    NAS100) et aux crans du trail MFE.

    Le pic favorable est suivi ici meme, cycle apres cycle. Ca ne coute
    rien puisqu on interroge deja les positions, et ca donne ce qui
    manquait a mfe_trail_events : le MFE VRAI du ticket, pas celui vu par
    un module a un instant donne.

LECTURE SEULE, ET STRUCTURELLEMENT

    Trois appels MT5 seulement : positions_get, symbol_info,
    account_info. Aucun order_send, aucun import d un module qui en
    contient un. Ce fichier ne sait pas passer d ordre.

CE QU IL NE FAIT PAS

    Il ne conclut rien. Il n a pas de colonne "aurait du" ni "bon
    stop / mauvais stop" : ces jugements se font apres coup, en joignant
    sur le ticket avec tickets_rails.jsonl qui porte le P&L reel.

    Il ne remplace pas mfe_trail_events.csv, qui porte les REFUS -- une
    tentative refusee ne change pas le SL, donc elle est invisible ici.
    Les deux journaux sont complementaires : l un dit ce qui a ete
    tente, l autre ce qui a ete obtenu.

LE PROTOCOLE, POSE AVANT LA COLLECTE

    Unite : la seance, pas le ticket.
    Fenetre : du 13/08 au 31/08.
    Verdict : 01/09, le meme jour que le gel V9.
    Critere : test du signe a p <= 0,05 sur les seances.
    Rien ne se branche avant cette date, quel que soit le total en euros.

A LANCER une fois, il tourne jusqu a Ctrl+C. Un fichier par jour.
"""
import argparse
import csv
import io
import os
import sys
import time
from datetime import datetime

try:
    import MetaTrader5 as mt5
except ImportError:
    print("KO : MetaTrader5 introuvable dans cet interpreteur.")
    sys.exit(1)

DOSSIER = os.path.join("docs", "sl_watch")
INTERVALLE = 3.0
COLONNES = ["ts", "evenement", "ticket", "magic", "symbole", "sens", "volume",
            "prix_open", "prix_courant", "sl_avant", "sl_apres",
            "dist_sl_pts", "dist_sl_pct", "sens_mouvement",
            "profit_eur", "pic_pts", "age_s"]


def maintenant():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def points(sym, cache):
    """Taille du point, mise en cache : symbol_info coute un aller-retour."""
    if sym not in cache:
        si = mt5.symbol_info(sym)
        cache[sym] = (si.point if si and si.point else 0.01)
    return cache[sym]


def ouvrir(dossier):
    """Un fichier par jour, en ajout. L en-tete n est ecrit qu une fois."""
    os.makedirs(dossier, exist_ok=True)
    ch = os.path.join(dossier, "sl_events_%s.csv"
                      % datetime.now().strftime("%Y%m%d"))
    neuf = not os.path.exists(ch) or os.path.getsize(ch) == 0
    f = io.open(ch, "a", encoding="utf-8", newline="")
    w = csv.DictWriter(f, fieldnames=COLONNES)
    if neuf:
        w.writeheader()
        f.flush()
    return ch, f, w


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dossier", default=DOSSIER)
    p.add_argument("--intervalle", type=float, default=INTERVALLE)
    p.add_argument("--minutes", type=float, default=0.0,
                   help="s arrete apres N minutes (0 = sans fin)")
    a = p.parse_args()

    if not mt5.initialize():
        print("KO : mt5.initialize() a echoue -- %s" % (mt5.last_error(),))
        print("Le terminal MT5 doit tourner. Ce programme ne le lance pas.")
        return 1

    ac = mt5.account_info()
    ch, f, w = ouvrir(a.dossier)
    print("=" * 74)
    print(" SCALP-EA / SURVEILLANCE DES STOPS -- LECTURE SEULE")
    print("=" * 74)
    print("compte     : %s" % (ac.login if ac else "?"))
    print("journal    : %s" % ch)
    print("intervalle : %.1f s" % a.intervalle)
    print()
    print("Une ligne par evenement : DEBUT, SL, TP, FIN.")
    print("Aucun ordre n est envoye. Ctrl+C pour arreter.")
    print()

    vus = {}            # ticket -> dict d etat
    pts = {}
    n_cycles = 0
    n_ev = 0
    t_fin = time.time() + a.minutes * 60 if a.minutes else None

    def ecrire(ev, e, sl_av=None, sl_ap=None, mouvement=""):
        nonlocal n_ev
        pt = points(e["symbole"], pts)
        d_pts = d_pct = ""
        cible = sl_ap if sl_ap is not None else e["sl"]
        if cible and e["prix_open"]:
            d_pts = round(abs(cible - e["prix_open"]) / pt, 1)
            d_pct = round(100.0 * abs(cible - e["prix_open"]) / e["prix_open"], 4)
        w.writerow({
            "ts": maintenant(), "evenement": ev, "ticket": e["ticket"],
            "magic": e["magic"], "symbole": e["symbole"], "sens": e["sens"],
            "volume": e["volume"], "prix_open": e["prix_open"],
            "prix_courant": e["prix_courant"],
            "sl_avant": "" if sl_av is None else sl_av,
            "sl_apres": "" if sl_ap is None else sl_ap,
            "dist_sl_pts": d_pts, "dist_sl_pct": d_pct,
            "sens_mouvement": mouvement,
            "profit_eur": e["profit"], "pic_pts": e["pic_pts"],
            "age_s": int(time.time() - e["t0"]),
        })
        f.flush()          # une coupure de courant ne doit rien couter
        n_ev += 1

    try:
        while True:
            if t_fin and time.time() > t_fin:
                break
            pos = mt5.positions_get()
            if pos is None:
                time.sleep(a.intervalle)
                continue

            presents = set()
            for p_ in pos:
                presents.add(p_.ticket)
                pt = points(p_.symbol, pts)
                sens = "ACHAT" if p_.type == 0 else "VENTE"
                # pic favorable, suivi ici meme : c est le MFE vrai.
                if sens == "ACHAT":
                    pic = (p_.price_current - p_.price_open) / pt
                else:
                    pic = (p_.price_open - p_.price_current) / pt

                e = vus.get(p_.ticket)
                if e is None:
                    e = {"ticket": p_.ticket, "magic": p_.magic,
                         "symbole": p_.symbol, "sens": sens,
                         "volume": p_.volume, "prix_open": p_.price_open,
                         "prix_courant": p_.price_current, "sl": p_.sl,
                         "tp": p_.tp, "profit": round(p_.profit, 2),
                         "pic_pts": round(max(0.0, pic), 1),
                         "t0": time.time()}
                    vus[p_.ticket] = e
                    ecrire("DEBUT", e, sl_ap=p_.sl)
                    continue

                e["prix_courant"] = p_.price_current
                e["profit"] = round(p_.profit, 2)
                e["pic_pts"] = round(max(e["pic_pts"], pic), 1)

                if p_.sl != e["sl"]:
                    if e["sl"] in (0, None) or p_.sl in (0, None):
                        mvt = "pose" if e["sl"] in (0, None) else "retire"
                    elif sens == "ACHAT":
                        mvt = "resserre" if p_.sl > e["sl"] else "relache"
                    else:
                        mvt = "resserre" if p_.sl < e["sl"] else "relache"
                    ecrire("SL", e, sl_av=e["sl"], sl_ap=p_.sl, mouvement=mvt)
                    e["sl"] = p_.sl

                if p_.tp != e["tp"]:
                    ecrire("TP", e, sl_av=e["tp"], sl_ap=p_.tp,
                           mouvement="tp")
                    e["tp"] = p_.tp

            for tk in [t for t in vus if t not in presents]:
                ecrire("FIN", vus[tk], sl_ap=vus[tk]["sl"])
                del vus[tk]

            n_cycles += 1
            if n_cycles % 200 == 0:
                try:
                    print("[%s] %d cycles, %d evenements, %d position(s)"
                          % (maintenant(), n_cycles, n_ev, len(vus)))
                except Exception:
                    pass    # sortie fermee : ne jamais casser la boucle
            time.sleep(a.intervalle)

    except KeyboardInterrupt:
        print()
        print("Arret demande.")
    finally:
        # Les positions encore ouvertes n ont pas de FIN : on le dit,
        # pour qu on ne les prenne pas pour des tickets perdus.
        try:
            print()
            print("%d cycles, %d evenements ecrits." % (n_cycles, n_ev))
            if vus:
                print("%d position(s) encore ouverte(s) sans ligne FIN : %s"
                      % (len(vus), ", ".join(str(t) for t in list(vus)[:10])))
            print("journal : %s" % ch)
        except Exception:
            pass
        f.close()
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
