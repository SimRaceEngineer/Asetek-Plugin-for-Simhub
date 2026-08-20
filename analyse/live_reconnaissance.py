# -*- coding: utf-8 -*-
"""
live_reconnaissance.py -- ce qu il faut savoir AVANT d envoyer
                          un seul ordre reel pour les 19 magics.

CE SCRIPT N ENVOIE AUCUN ORDRE. Il ne modifie rien, ne ferme rien,
ne place rien. Il lit le terminal deja ouvert et repond a quatre
questions dont depend toute la suite :

  1. Le compte est-il HEDGING ou NETTING ?
     En netting, 19 magics sur le meme symbole FUSIONNENT en une
     seule position nette. Le PnL par magic devient alors
     immesurable, et toute la comparaison live/paper s effondre.
     C est la question qui decide si le projet est faisable tel quel.

  2. Quel est le lot minimum, et la marge tient-elle ?
     19 magics x volume_min, sur trois symboles, en simultane.

  3. Quel est le spread reel, maintenant, sur chaque symbole ?
     C est la moitie de ce qu on cherche a mesurer.

  4. Quels magics tournent deja ? (pour ne rien recouvrir)

Usage :
    python live_reconnaissance.py
    python live_reconnaissance.py --spread 60     (echantillonne 60 s)
"""

import sys
import time

SEP = "=" * 92

MAGICS = [240007, 220014, 230207, 240004, 230201, 240005, 240002,
          230205, 240001, 220004, 230210, 240008, 240003, 240006,
          230106, 230307, 230102, 230202, 230107]

# les deux temoins sans regle : ils prennent TOUT leur actif+sens
TEMOINS = {220004, 220014}

CHERCHE = ("US30", "SPX500", "NAS100", "US500", "USTEC")


def masque_compte(n):
    s = str(n)
    if len(s) <= 4:
        return "*" * len(s)
    return s[:2] + "*" * (len(s) - 4) + s[-2:]


def main():
    args = sys.argv[1:]
    secondes = 0
    if "--spread" in args:
        i = args.index("--spread")
        if i + 1 < len(args):
            try:
                secondes = int(args[i + 1])
            except ValueError:
                pass

    print(SEP)
    print("RECONNAISSANCE AVANT MISE EN LIGNE -- AUCUN ORDRE N EST ENVOYE")
    print(SEP)
    print()

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("  MetaTrader5 n est pas installe dans ce python.")
        print("  Lance ce script avec le meme python que la stack.")
        return

    if not mt5.initialize():
        print("  connexion impossible : %s" % (mt5.last_error(),))
        print("  (aucun terminal n a ete lance par ce script)")
        return

    try:
        ti = mt5.terminal_info()
        ai = mt5.account_info()

        print(SEP)
        print("TERMINAL ATTACHE")
        print(SEP)
        if ti:
            print("  chemin        : %s" % ti.path)
            print("  societe       : %s" % ti.company)
            print("  trade permis  : %s" % ti.trade_allowed)
            print("  algo permis   : %s" % ti.trade_expert)
        print()
        print("  VERIFIE CE CHEMIN. Si ce n est pas le terminal live,")
        print("  arrete tout de suite : il y a cinq terminaux sur ce VPS.")
        print()

        if ai is None:
            print("  aucun compte connecte.")
            return

        print(SEP)
        print("COMPTE")
        print(SEP)
        print("  numero        : %s" % masque_compte(ai.login))
        print("  serveur       : %s" % ai.server)
        print("  devise        : %s" % ai.currency)
        print("  levier        : 1:%d" % ai.leverage)
        print("  solde         : %.2f" % ai.balance)
        print("  equity        : %.2f" % ai.equity)
        print("  marge libre   : %.2f" % ai.margin_free)
        reel = {0: "DEMO", 1: "CONCOURS", 2: "REEL"}.get(ai.trade_mode, "?")
        print("  type          : %s" % reel)
        print("  ordres max    : %s" % (ai.limit_orders or "illimite"))
        print()

        print(SEP)
        print("*** LA QUESTION QUI DECIDE DE TOUT ***")
        print(SEP)
        modes = {0: "RETAIL_NETTING", 1: "EXCHANGE", 2: "RETAIL_HEDGING"}
        m = ai.margin_mode
        print("  margin_mode : %d  = %s" % (m, modes.get(m, "inconnu")))
        print()
        if m == 2:
            print("  HEDGING. Chaque magic aura sa propre position, son")
            print("  propre ticket, son propre PnL. La comparaison")
            print("  live/paper est mesurable magic par magic.")
            print("  -> on peut y aller.")
        elif m == 0:
            print("  NETTING. Toutes les positions d un meme symbole")
            print("  FUSIONNENT en une seule. Les 19 magics ne seront")
            print("  plus distinguables : un seul prix moyen, un seul")
            print("  PnL, et le magic du dernier ordre l emporte.")
            print()
            print("  Dans ce cas la comparaison telle que tu la veux est")
            print("  IMPOSSIBLE sur ce compte. Trois issues :")
            print("    a) un second compte hedging chez le meme broker,")
            print("    b) un magic a la fois, en serie sur 19 series,")
            print("    c) on reste en paper et on mesure le spread")
            print("       autrement (voir plus bas).")
            print("  -> ne rien envoyer avant d avoir tranche.")
        else:
            print("  Mode inhabituel. On s arrete plutot que de supposer.")
        print()

        # --- symboles ----------------------------------------------------
        tous = mt5.symbols_get()
        vises = []
        for s in tous or []:
            for c in CHERCHE:
                if s.name.upper().startswith(c):
                    vises.append(s)
                    break

        print(SEP)
        print("SYMBOLES")
        print(SEP)
        if not vises:
            print("  aucun symbole trouve parmi %s" % (CHERCHE,))
        besoin_total = 0.0
        for s in vises:
            if not s.visible:
                mt5.symbol_select(s.name, True)
                s = mt5.symbol_info(s.name)
            print()
            print("  %s" % s.name)
            print("    lot min / pas / max : %s / %s / %s"
                  % (s.volume_min, s.volume_step, s.volume_max))
            print("    point / digits      : %s / %d" % (s.point, s.digits))
            print("    spread courant      : %d points" % s.spread)
            print("    stops / freeze      : %d / %d"
                  % (s.trade_stops_level, s.trade_freeze_level))
            tm = {0: "desactive", 1: "long seul", 2: "short seul",
                  3: "cloture seule", 4: "complet"}.get(s.trade_mode, "?")
            print("    trade_mode          : %s" % tm)
            remplis = []
            if s.filling_mode & 1:
                remplis.append("FOK")
            if s.filling_mode & 2:
                remplis.append("IOC")
            remplis.append("RETURN (si autorise)")
            print("    remplissage         : %s" % ", ".join(remplis))
            tick = mt5.symbol_info_tick(s.name)
            if tick:
                ecart = (tick.ask - tick.bid) / s.point if s.point else 0
                print("    bid / ask           : %.2f / %.2f  (%.0f points)"
                      % (tick.bid, tick.ask, ecart))
            try:
                mg = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, s.name,
                                           s.volume_min,
                                           tick.ask if tick else 0)
                if mg:
                    print("    marge pour %s lot   : %.2f %s"
                          % (s.volume_min, mg, ai.currency))
                    besoin_total += mg * len(MAGICS)
            except Exception as e:
                print("    marge : non calculable (%s)" % e)
        print()

        print(SEP)
        print("EST-CE QUE LA MARGE TIENT ?")
        print(SEP)
        print("  19 magics x lot minimum, tous ouverts en meme temps,")
        print("  sur chacun des symboles trouves :")
        print("    besoin   : %.2f %s" % (besoin_total, ai.currency))
        print("    dispo    : %.2f %s" % (ai.margin_free, ai.currency))
        if besoin_total and ai.margin_free:
            print("    ratio    : %.1f %% de la marge libre"
                  % (100.0 * besoin_total / ai.margin_free))
        print()
        print("  C est le pire cas -- les 19 ne declenchent jamais")
        print("  ensemble. Mais deux d entre eux, %s, n ont AUCUNE"
              % ", ".join(str(t) for t in sorted(TEMOINS)))
        print("  regle : ils prennent toutes les entrees de leur")
        print("  actif et de leur sens. Ce sont eux qui feront le")
        print("  volume, et ce sont eux le point de comparaison.")
        print()

        # --- positions deja ouvertes -------------------------------------
        print(SEP)
        print("CE QUI TOURNE DEJA")
        print(SEP)
        pos = mt5.positions_get() or []
        if not pos:
            print("  aucune position ouverte.")
        else:
            par_magic = {}
            for p in pos:
                par_magic.setdefault(p.magic, []).append(p)
            for mg in sorted(par_magic):
                lst = par_magic[mg]
                vol = sum(p.volume for p in lst)
                pnl = sum(p.profit for p in lst)
                drapeau = "  <-- dans la liste" if mg in MAGICS else ""
                print("  magic %-8s %2d position(s)  vol %.2f  pnl %8.2f%s"
                      % (mg, len(lst), vol, pnl, drapeau))
        print()
        deja = set(p.magic for p in pos) & set(MAGICS)
        if deja:
            print("  ATTENTION : %s tourne(nt) deja en reel."
                  % ", ".join(str(x) for x in sorted(deja)))
            print("  Ne pas les remettre en ligne une seconde fois.")
            print()

        # --- echantillonnage du spread -----------------------------------
        if secondes > 0 and vises:
            print(SEP)
            print("SPREAD SUR %d SECONDES" % secondes)
            print(SEP)
            releves = dict((s.name, []) for s in vises)
            fin = time.time() + secondes
            while time.time() < fin:
                for s in vises:
                    t = mt5.symbol_info_tick(s.name)
                    if t and s.point:
                        releves[s.name].append((t.ask - t.bid) / s.point)
                time.sleep(0.5)
            print()
            for nom in sorted(releves):
                v = releves[nom]
                if not v:
                    continue
                v2 = sorted(v)
                print("  %-14s n=%4d  min %5.0f  median %5.0f  "
                      "p90 %5.0f  max %5.0f points"
                      % (nom, len(v), v2[0], v2[len(v2) // 2],
                         v2[int(len(v2) * 0.9)], v2[-1]))
            print()
            print("  Le spread median est le cout fixe de chaque prise.")
            print("  Le p90 est celui que tu paieras sur les entrees")
            print("  qui suivent une nouvelle -- donc sur les meilleures.")
            print()

    finally:
        mt5.shutdown()

    print(SEP)
    print("  Aucun ordre n a ete envoye. Rien n a ete modifie.")
    print(SEP)


if __name__ == "__main__":
    main()
