#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""gardien_stops.py -- un stop ne recule jamais, sur tout le compte moteur.

CE QUI A ETE MESURE
-------------------
Journaux du terminal MT5, compte 17**80 :

    25/08   26 271 modifications de stop   12 847 reculs   49 %
    26/08   29 590 modifications de stop   14 327 reculs   48 %
    27/08    3 879 modifications de stop      570 reculs   15 %

Un recul, vu de pres, ressemble a ceci (#172794092, sell NAS100) :

    15:28:16.897   31097.15 ->  29494.40
    15:28:18.975   29494.40 ->  31097.15
    15:28:21.697   31097.15 ->  29494.40

Deux valeurs, deux seulement, qui alternent : le vrai stop a 44 points
du prix, et le stop bouchon pose a l ouverture a 1602 points. La meme
forme sur US30 avec 4007 points d ecart. Ce n est pas du bruit, c est
un desaccord entre deux ecritures.

POURQUOI PERSONNE NE S Y OPPOSAIT
---------------------------------
sl_cliquet.py existe depuis le 10/08 et devait empecher exactement
cela. Recherche de la chaine SL-CLIQUET dans la totalite de logs\ le
27/08 : zero ligne. Or install() imprime toujours une ligne quand il
s arme, meme sans logger -- _dire retombe sur print(). Le cliquet n a
donc jamais ete arme, dans aucun processus. Il n y avait pas de garde
a reparer : il n y en avait pas.

POURQUOI CE FICHIER N EST PAS sl_cliquet BIS
--------------------------------------------
sl_cliquet s installe en ENVELOPPE sur mt5.order_send. Pose sur le
miroir le 27/08 a 09:00, il a fait echouer CHAQUE ouverture pendant
1h27 -- last_error (-2, 'Unnamed arguments not allowed'). Une enveloppe
sur order_send s interpose sur les ouvertures alors qu elle n a affaire
qu aux stops. C est une mauvaise place.

Ce gardien est un PROCESSUS separe, sur le modele de trail_miroir6.py
qui tourne depuis le 27/08 sans incident. Il ne s injecte dans rien, ne
modifie aucun fichier, et ne peut par construction casser aucune
ouverture : il n ecrit que des TRADE_ACTION_SLTP.

CE QU IL FAIT
-------------
Il retient, pour chaque position vivante, le meilleur stop qu il ait vu
    achat -> le plus HAUT     vente -> le plus BAS
et quand la valeur en place devient moins bonne, il remet la meilleure.
Un effacement de stop est traite comme un recul infini.

Il n a pas besoin de savoir QUI recule pour proteger. Mais il l ecrit :
chaque recul est date a la milliseconde dans logs\gardien_stops.log, et
le battement affiche les couples de valeurs qui alternent. C est avec
cette trace, et la cadence propre a chaque processus, que l ecrivain
sera nomme -- aucun des quatre candidats n ecrit aujourd hui la valeur
de ses stops dans son journal.

CE QU IL NE FAIT PAS
--------------------
Il n ouvre rien, ne ferme rien, ne touche pas au TP autrement qu en le
recopiant tel quel, et ne se rabat jamais sur un autre terminal que
celui qu on lui donne.

USAGE
-----
    python gardien_stops.py                 <- OBSERVATION, n ecrit rien
    python gardien_stops.py --once          <- un seul tour, pour voir
    python gardien_stops.py --reel          <- il restaure vraiment
"""

from __future__ import annotations

import argparse
import collections
import io
import os
import sys
import time

TERMINAL_MOTEUR = (r"C:\Program Files\TF Global Markets MetaTrader 5 "
                   r"Termina-LOCALSTACKl\terminal64.exe")

COMPTE_ATTENDU = 178780     # on refuse d agir ailleurs

JOURNAL = os.path.join("logs", "gardien_stops.log")
PERIODE = 0.5               # s entre deux regards -- le battement mesure
                            # va de 0.25 s a 3.9 s, il faut regarder plus
                            # vite que lui
BATTEMENT = 60.0            # s entre deux lignes de vie
EPS = 0.005                 # deux stops plus proches que cela sont le meme
REFUS_MAX = 3               # apres quoi on cesse d insister sur un ticket


def dire(msg):
    ligne = "%s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(ligne, flush=True)
    try:
        d = os.path.dirname(JOURNAL)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
    except Exception:
        pass                # un journal qui tombe n arrete pas la garde


def horodate():
    t = time.time()
    return time.strftime("%H:%M:%S", time.localtime(t)) + ".%03d" % (
        int((t - int(t)) * 1000))


def meilleur(sens, a, b):
    """Le meilleur des deux stops. 0.0 n est pas un stop, c est une absence."""
    if not a:
        return b
    if not b:
        return a
    return max(a, b) if sens > 0 else min(a, b)


def recule(sens, best, neuf):
    """Vrai si neuf est moins protecteur que best."""
    if not best:
        return False                     # rien a defendre encore
    if not neuf:
        return True                      # effacement : recul infini
    return (neuf < best - EPS) if sens > 0 else (neuf > best + EPS)


def tour(mt5, mem, reel, stat):
    """Un regard sur toutes les positions. Rend (vues, reculs, restaures)."""
    positions = mt5.positions_get()
    if positions is None:
        return 0, 0, 0
    vivants = set()
    reculs = restaures = 0

    for p in positions:
        tk = int(p.ticket)
        vivants.add(tk)
        sens = 1 if int(p.type) == 0 else -1
        sl = float(getattr(p, "sl", 0.0) or 0.0)
        tp = float(getattr(p, "tp", 0.0) or 0.0)
        sym = str(getattr(p, "symbol", "?"))

        m = mem.get(tk)
        if m is None:
            # Premiere vue. On s amorce sur ce que porte la position.
            # Le stop bouchon est, par construction, toujours du mauvais
            # cote : s amorcer dessus ne coute rien, le vrai stop est
            # meilleur et passera.
            mem[tk] = {"sens": sens, "best": sl, "sym": sym,
                       "magic": int(getattr(p, "magic", 0) or 0),
                       "vals": collections.Counter([round(sl, 2)]),
                       "reculs": 0, "refus": 0, "gele": False}
            continue

        m["vals"][round(sl, 2)] += 1

        if not recule(sens, m["best"], sl):
            avant = m["best"]
            m["best"] = meilleur(sens, m["best"], sl)
            if avant and abs(m["best"] - avant) > EPS:
                stat["avances"] += 1
            continue

        # --- c est un recul -------------------------------------------
        reculs += 1
        m["reculs"] += 1
        stat["reculs"] += 1
        best = m["best"]
        ecart = float("inf") if not sl else abs(best - sl)
        dire("  RECUL %s #%d %s  %.2f -> %s   (%s)"
             % (horodate(), tk, sym, best,
                "EFFACE" if not sl else "%.2f" % sl,
                "infini" if ecart == float("inf") else "%.2f pts" % ecart))

        if m["gele"]:
            continue
        if not reel:
            continue

        r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP,
                            "position": tk,
                            "sl": float(best),
                            "tp": float(tp)})
        code = getattr(r, "retcode", None) if r is not None else None
        if code == mt5.TRADE_RETCODE_DONE:
            restaures += 1
            stat["restaures"] += 1
            m["refus"] = 0
            dire("    remis a %.2f" % best)
        else:
            m["refus"] += 1
            dire("    REFUS retcode %s %s %s"
                 % (code,
                    getattr(r, "comment", "") if r is not None else "",
                    "" if r is not None else mt5.last_error()))
            if m["refus"] >= REFUS_MAX:
                m["gele"] = True
                dire("    GEL #%d : %d refus d affilee, je cesse d insister"
                     " sur ce ticket. Le stop en place reste %s."
                     % (tk, REFUS_MAX, "efface" if not sl else "%.2f" % sl))

    for tk in list(mem):
        if tk not in vivants:
            del mem[tk]
    return len(vivants), reculs, restaures


def bilan(mem, stat, mode, tours):
    dire("  battement [%s] : %d tour(s), %d position(s), %d recul(s) vu(s),"
         " %d restaure(s), %d avance(s) legitime(s)"
         % (mode, tours, len(mem), stat["reculs"], stat["restaures"],
            stat["avances"]))
    chauds = sorted((m for m in mem.values() if m["reculs"]),
                    key=lambda m: -m["reculs"])[:4]
    for m in chauds:
        v = m["vals"].most_common(3)
        dire("      %s magic %d : %d recul(s), valeurs %s"
             % (m["sym"], m["magic"], m["reculs"],
                "  ".join("%.2f x%d" % (a, b) for a, b in v)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--terminal", default=TERMINAL_MOTEUR)
    ap.add_argument("--compte", type=int, default=COMPTE_ATTENDU)
    ap.add_argument("--reel", action="store_true",
                    help="restaure vraiment le stop. Sans lui : observation.")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--periode", type=float, default=PERIODE)
    a = ap.parse_args()

    mode = "REEL" if a.reel else "OBSERVATION"
    dire("=" * 70)
    dire("gardien_stops -- un stop ne recule jamais -- mode %s" % mode)
    if not a.reel:
        dire("  OBSERVATION : rien ne sera envoye. --reel pour restaurer.")

    if not os.path.exists(a.terminal):
        dire("ABANDON : terminal introuvable -- %s" % a.terminal)
        dire("Je ne me rabats pas sur le terminal par defaut : c est")
        dire("l autre compte, et j y deplacerais des stops qui ne sont")
        dire("pas les miens.")
        return 2
    try:
        import MetaTrader5 as mt5
    except ImportError:
        dire("ABANDON : MetaTrader5 non installe.")
        return 2
    if not mt5.initialize(path=a.terminal):
        dire("ABANDON : initialize a echoue -- %s" % (mt5.last_error(),))
        return 2

    info = mt5.account_info()
    login = int(info.login) if info else 0
    s = str(login)
    dire("  compte : %s   %s" % (s[:2] + "**" + s[-2:],
                                 info.server if info else "?"))
    if login != a.compte:
        dire("ABANDON : ce terminal est connecte a %s, j attendais %d."
             % (s[:2] + "**" + s[-2:], a.compte))
        dire("Restaurer des stops sur le mauvais compte serait pire que")
        dire("de ne rien faire.")
        mt5.shutdown()
        return 2

    mem = {}
    stat = {"reculs": 0, "restaures": 0, "avances": 0}
    dernier, tours = time.time(), 0
    try:
        while True:
            tours += 1
            try:
                vues, _, _ = tour(mt5, mem, a.reel, stat)
            except Exception as e:
                dire("  tour en erreur : %s" % str(e)[:160])
                vues = 0
            if a.once:
                dire("  un seul tour demande : %d position(s) vue(s), %d"
                     " memorisee(s)." % (vues, len(mem)))
                break
            maintenant = time.time()
            if maintenant - dernier >= BATTEMENT:
                bilan(mem, stat, mode, tours)
                dernier, tours = maintenant, 0
            time.sleep(a.periode)
    except KeyboardInterrupt:
        dire("  arret demande.")
        bilan(mem, stat, mode, tours)
    finally:
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
