#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""trail_miroir6.py -- le trailing 0.50R de la branche 6, et rien d autre.

CE QU IL FAIT
-------------
Il surveille les positions dont le magic est dans 6220000 - 6249999 --
la branche 6, reservee aux deux ACCORD M15 -- et il avance leur stop
selon une seule regle :

    des que le prix a avance de 0.50R, le stop suit a 0.50R sous le
    plus haut atteint, sans jamais reculer.

Il ne touche a AUCUNE autre position. Il ne ferme rien. Il n ouvre
rien. Il ne fait que des TRADE_ACTION_SLTP, et uniquement sur des
magics de la plage 6.

POURQUOI SEULEMENT LES ACCORD M15
---------------------------------
Le rejeu barre par barre du 27/08 a passe treize politiques de sortie
sur un mois de trades. Toutes detruisent la queue -- les 5 % de
gagnants qui portent 31 % du gain brut. Une seule ligne sort du lot :

    240004 ACCORD M15 BAISSIER   TR 0.50R   +1286 sur 59 prises rejouees
    240003 ACCORD M15 HAUSSIER   TR 0.50R      +4 sur 58 prises rejouees

C est peu de prises, et c est dit. La branche 6 existe pour porter
cette mesure en reel sur ces deux magics, pas pour generaliser un
resultat qui ne se generalise pas.

D OU VIENT LA DISTANCE
----------------------
R est la perte moyenne REALISEE du magic, mesuree par accord_m15.py et
convertie en points, actif par actif. Elle ne vient PAS du stop
d origine : celui-ci est le placeholder a 200 points sur SPX500, quand
la perte moyenne y vaut 5.5 points. Il n est jamais touche.

Les quartiles etaient serres -- 41.2 / 42.4 / 44.1 sur NAS100 pour
240004 -- donc une distance unique par couple (magic, actif) est une
bonne approximation et non un compromis.

SANS ETAT SUR DISQUE, VOLONTAIREMENT
------------------------------------
Le plus haut atteint n est PAS persiste. Au demarrage il est reamorce
au prix courant, ce qui ne peut que rendre le stop moins avance --
jamais plus. Le 27/08 au matin, un liens.json jamais purge a coute une
demi-heure de diagnostic ; un fichier d etat qui survit a un
redemarrage est une source de mensonge de plus, et ici on peut s en
passer.

Le stop ne recule jamais non plus : chaque modification est comparee
au SL DEJA POSE sur la position, et refusee si elle l aggrave. La
regle du cliquet, appliquee a la source.

SIMULATION PAR DEFAUT
---------------------
Sans --reel il n envoie rien et journalise ce qu il aurait fait. Le
mode est ecrit en toutes lettres a chaque demarrage ET dans chaque
battement : le 26/08, un pont parti en simulation sans le dire a coute
une journee de miroirs.

USAGE
-----
    python trail_miroir6.py                 <- SIMULATION
    python trail_miroir6.py --reel
    python trail_miroir6.py --once          <- un seul tour, pour voir
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

TERMINAL_MOTEUR = (r"C:\Program Files\TF Global Markets MetaTrader 5 "
                   r"Termina-LOCALSTACKl\terminal64.exe")

PLAGE6 = (6220000, 6249999)
DECALAGE6 = 6000000         # 6240004 - 6000000 = 240004

# R median en POINTS, mesure par accord_m15.py le 27/08 sur un mois.
# La distance de trailing est la MOITIE de ces valeurs.
R_POINTS = {
    (240003, "NAS100"): 51.7,
    (240003, "SPX500"): 5.5,
    (240003, "US30"): 55.0,
    (240004, "NAS100"): 42.4,
    (240004, "SPX500"): 4.3,
    (240004, "US30"): 43.1,
}
PART = 0.50                 # distance de suivi, en R
JOURNAL = os.path.join("logs", "trail_miroir6.log")
PERIODE = 1.0               # s entre deux regards
BATTEMENT = 60.0            # s entre deux lignes de vie
MARGE_MOUVEMENT = 0.10      # on ne bouge que si on gagne 10 % de R


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


def magic_paper(magic):
    """6240004 -> 240004, ou None si le magic n est pas de la branche 6."""
    m = int(magic)
    if not (PLAGE6[0] <= m <= PLAGE6[1]):
        return None
    return m - DECALAGE6


def niveau_trail(sens, entree, best, r_pts, part=PART):
    """Le niveau demande, ou None si le trailing n est pas encore arme.

    Arme quand l avance atteint part.R -- soit le moment ou le premier
    niveau vaut exactement l entree. Poser un trailing avant, c est
    poser un stop SOUS l entree : une perte inventee, pas une
    protection. C est le defaut que le rejeu du 27/08 a porte pendant
    trois versions.
    """
    avance = (best - entree) * sens
    if avance < part * r_pts:
        return None
    n = best - sens * part * r_pts
    if (n - entree) * sens < 0:     # ceinture
        n = entree
    return n


def borne_courtier(mt5, info, tick, sens, niveau):
    """Rapproche le niveau si le courtier interdit d etre si pres du prix.

    Rendre (niveau, note). Un stop refuse en boucle ne se voit pas dans
    un journal ; un stop rapproche et DIT se voit.
    """
    try:
        stops = float(getattr(info, "trade_stops_level", 0) or 0) * info.point
    except Exception:
        stops = 0.0
    if stops <= 0:
        return niveau, ""
    if sens > 0:
        limite = tick.bid - stops
        if niveau > limite:
            return limite, "rapproche de %.1f pts (stops level)" % (
                (niveau - limite) / info.point if info.point else 0.0)
    else:
        limite = tick.ask + stops
        if niveau < limite:
            return limite, "rapproche de %.1f pts (stops level)" % (
                (limite - niveau) / info.point if info.point else 0.0)
    return niveau, ""


def tour(mt5, best, reel, inconnus):
    """Un regard sur les positions de la branche 6. Rend (vues, bougees)."""
    positions = mt5.positions_get()
    if positions is None:
        return 0, 0
    vues = bougees = 0
    vivants = set()

    for p in positions:
        mp = magic_paper(getattr(p, "magic", 0) or 0)
        if mp is None:
            continue
        vues += 1
        tk = int(p.ticket)
        vivants.add(tk)
        sym = p.symbol
        sens = 1 if p.type == 0 else -1
        entree = float(p.price_open)

        r_pts = R_POINTS.get((mp, sym))
        if r_pts is None:
            cle = (mp, sym)
            if cle not in inconnus:
                inconnus.add(cle)
                dire("  M%s %s : aucun R mesure pour ce couple, position"
                     " LAISSEE TELLE QUELLE." % (p.magic, sym))
                dire("     Je ne devine pas une distance de stop.")
            continue

        info = mt5.symbol_info(sym)
        tick = mt5.symbol_info_tick(sym)
        if info is None or tick is None:
            continue
        courant = tick.bid if sens > 0 else tick.ask

        # Le plus haut n est pas persiste : au demarrage il vaut le prix
        # courant, ce qui ne peut que retarder le trailing, jamais l
        # avancer a tort.
        b = best.get(tk)
        if b is None:
            b = max(entree, courant) if sens > 0 else min(entree, courant)
        elif (courant - b) * sens > 0:
            b = courant
        best[tk] = b

        niveau = niveau_trail(sens, entree, b, r_pts)
        if niveau is None:
            continue

        sl_actuel = float(getattr(p, "sl", 0.0) or 0.0)
        # Le stop ne recule jamais. Un SL absent (0.0) est traite comme
        # une absence de protection, pas comme un stop a zero.
        if sl_actuel and (niveau - sl_actuel) * sens <= 0:
            continue
        if sl_actuel and info.point:
            gain = abs(niveau - sl_actuel) / info.point
            if gain < MARGE_MOUVEMENT * r_pts:
                continue        # pas la peine de modifier pour trois points

        niveau, note = borne_courtier(mt5, info, tick, sens, niveau)
        if sl_actuel and (niveau - sl_actuel) * sens <= 0:
            continue            # apres bornage il n ameliore plus rien

        chiffre = "%.*f" % (int(getattr(info, "digits", 2) or 2), niveau)
        etiquette = ("M%s %s #%s  sl %s -> %s"
                     % (p.magic, sym, tk,
                        ("%.*f" % (int(getattr(info, "digits", 2) or 2),
                                   sl_actuel)) if sl_actuel else "aucun",
                        chiffre))
        if note:
            etiquette += "  (%s)" % note

        if not reel:
            dire("  [SIMULATION] %s" % etiquette)
            bougees += 1
            continue

        req = {"action": mt5.TRADE_ACTION_SLTP,
               "position": tk,
               "sl": float(niveau),
               "tp": float(getattr(p, "tp", 0.0) or 0.0)}
        r = mt5.order_send(req)
        code = getattr(r, "retcode", None) if r is not None else None
        if code == mt5.TRADE_RETCODE_DONE:
            dire("  %s" % etiquette)
            bougees += 1
        else:
            dire("  REFUSE %s -- retcode %s %s"
                 % (etiquette, code,
                    getattr(r, "comment", "") if r is not None else ""))

    for tk in list(best):
        if tk not in vivants:
            del best[tk]        # la position est fermee, on oublie son pic
    return vues, bougees


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--terminal", default=TERMINAL_MOTEUR)
    ap.add_argument("--reel", action="store_true",
                    help="sans lui, RIEN n est envoye")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--periode", type=float, default=PERIODE)
    a = ap.parse_args()

    mode = "REEL" if a.reel else "SIMULATION"
    dire("=" * 70)
    dire("trail_miroir6 -- trailing %.2fR sur la branche 6 -- mode %s"
         % (PART, mode))
    if not a.reel:
        dire("  SIMULATION : aucun ordre ne sera envoye. --reel pour agir.")
    dire("  plage surveillee : %d - %d" % PLAGE6)
    dire("  distances : " + ", ".join(
        "%s/%s %.1f pts" % (m, s, v * PART)
        for (m, s), v in sorted(R_POINTS.items())))

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
    s = str(info.login) if info else "?"
    dire("  compte : %s   %s" % (s[:2] + "**" + s[-2:],
                                 info.server if info else "?"))

    best, inconnus = {}, set()
    dernier, tours, total_b = 0.0, 0, 0
    try:
        while True:
            tours += 1
            try:
                vues, bougees = tour(mt5, best, a.reel, inconnus)
                total_b += bougees
            except Exception as e:
                dire("  tour en erreur : %s" % str(e)[:160])
                vues = 0
            if a.once:
                dire("  un seul tour demande : %d position(s) de la"
                     " branche 6 vue(s)." % vues)
                break
            maintenant = time.time()
            if maintenant - dernier >= BATTEMENT:
                dire("  battement [%s] : %d tour(s), %d position(s)"
                     " suivie(s), %d stop(s) avance(s) au total"
                     % (mode, tours, vues, total_b))
                dernier, tours = maintenant, 0
            time.sleep(a.periode)
    except KeyboardInterrupt:
        dire("  arret demande.")
    finally:
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
