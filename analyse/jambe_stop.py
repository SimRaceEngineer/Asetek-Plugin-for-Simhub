# -*- coding: utf-8 -*-
"""
jambe_stop.py -- le trou central de toute l etude, enfin comble.

CE QUI MANQUAIT
    Tout ce qu on a mesure porte sur des EXTREMES DE SEANCE. On sait a
    quelle frequence un niveau est atteint. On n a jamais su combien de
    fois on se fait sortir AVANT. Sans ca, aucun resultat de prix ne
    devient une regle : un objectif touche dans 45% des seances ne vaut
    rien si le stop saute d abord dans 60% des cas.

CE QUE FAIT CE SCRIPT
    Il rejoue chaque POSITION REELLE en M1, de son ouverture a sa
    fermeture, et mesure :
      MFE  le meilleur point atteint en faveur  (Maximum Favourable Excursion)
      MAE  le pire point atteint contre         (Maximum Adverse Excursion)
    puis il simule une grille d objectifs et de stops par-dessus la
    logique de sortie existante, et compte qui touche en premier.

    C est un OVERLAY, pas un remplacement : quand ni l objectif ni le stop
    ne sont touches, on garde le resultat reel de la position. La question
    posee est donc "ajouter un TP et un SL a ce que la stack fait deja
    aurait-il aide ?", et non "que ferait une autre strategie".

TROIS LIMITES, TOUTES ASSUMEES
    1. RESOLUTION M1. Si l objectif et le stop sont tous deux a l interieur
       de la meme bougie, on ne peut pas savoir lequel a ete touche en
       premier. On suppose alors LE STOP -- hypothese pessimiste, jamais
       optimiste. Le taux d ambiguite est affiche : s il est eleve, les
       chiffres sont a lire comme une borne basse.
    2. SPREAD ET GLISSEMENT non modelises. Un stop reel se declenche un
       peu plus loin, un objectif un peu plus tard. Les resultats sont
       donc legerement optimistes de ce cote-la, ce qui compense en partie
       le point 1.
    3. AUCUN EFFET DE RETROACTION. Sortir plus tot aurait change les
       positions suivantes (marge, exposition, logique de la stack). On
       mesure un contrefactuel simple, pas une re-simulation complete.

HORAIRES : heure COURTIER (UTC+3), une heure d avance sur Paris.
"""
import io, os, sys, math, datetime as dt

DEBUT = dt.datetime(2026, 7, 20)
FIN = dt.datetime(2026, 8, 9)
SORTIE = "jambe_stop.csv"
# python jambe_stop.py 2026-08-01 2026-08-09  -> restreint la fenetre
if len(sys.argv) >= 3:
    DEBUT = dt.datetime.strptime(sys.argv[1], "%Y-%m-%d")
    FIN = dt.datetime.strptime(sys.argv[2], "%Y-%m-%d")
    SORTIE = "jambe_stop_%s_%s.csv" % (sys.argv[1], sys.argv[2])
# grille exprimee en multiples du MFE median de l actif : elle s adapte
# donc automatiquement a l echelle de chaque indice, sans rien coder en dur
GRILLE = [0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00]


def moy(xs):
    return sum(xs) / float(len(xs)) if xs else None


def med(xs):
    xs = sorted(xs)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def quart(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(q * len(xs)))]


# --------------------------------------------------------------- MT5
def charger():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        print("MT5 injoignable"); sys.exit(1)
    acc = mt5.account_info()
    print("compte %s" % (acc.login if acc else "?"))

    deals = mt5.history_deals_get(DEBUT, FIN) or []
    pos = {}
    for d in deals:
        p = pos.setdefault(d.position_id, {"sym": None, "vol": 0, "type": None,
                                           "open": None, "close": None,
                                           "px": None, "pnl": 0.0})
        p["pnl"] += d.profit + d.commission + d.swap
        if d.entry == mt5.DEAL_ENTRY_IN:
            if p["open"] is None or d.time < p["open"]:
                p.update(open=d.time, sym=d.symbol, vol=d.volume,
                         type=d.type, px=d.price)
        else:
            if p["close"] is None or d.time > p["close"]:
                p["close"] = d.time
    pos = dict((k, v) for k, v in pos.items()
               if v["open"] and v["close"] and v["sym"] and v["px"])
    print("positions fermees : %d" % len(pos))
    if not pos:
        mt5.shutdown(); return None, None

    # euros par point, avec controle de linearite : MT5 gere le contrat et
    # la devise, mais on ne lui fait pas confiance sans verifier que le
    # profit est bien proportionnel au deplacement.
    coef, rejets = {}, 0
    for k, p in pos.items():
        s = mt5.ORDER_TYPE_BUY if p["type"] == mt5.DEAL_TYPE_BUY else mt5.ORDER_TYPE_SELL
        a = mt5.order_calc_profit(s, p["sym"], p["vol"], p["px"], p["px"] + 1.0)
        b = mt5.order_calc_profit(s, p["sym"], p["vol"], p["px"], p["px"] + 2.0)
        if a is None or b is None or abs(b - 2 * a) > max(0.01, abs(a) * 0.02):
            rejets += 1
        else:
            coef[k] = abs(a)
    print("coefficients euros/point : %d, rejets de linearite : %d" % (len(coef), rejets))

    syms = sorted(set(p["sym"] for p in pos.values()))
    m1 = {}
    for s in syms:
        mt5.symbol_select(s, True)
        bars, t = [], DEBUT
        while t < FIN:
            t2 = min(t + dt.timedelta(days=7), FIN)
            r = mt5.copy_rates_range(s, mt5.TIMEFRAME_M1, t, t2)
            if r is not None and len(r):
                bars.extend(r)
            t = t2
        if not bars:
            print("  %-8s AUCUNE bougie M1 -- positions ignorees" % s); continue
        vus, prop = set(), []
        for x in bars:
            k = int(x["time"])
            if k in vus:
                continue
            vus.add(k)
            prop.append((k, float(x["high"]), float(x["low"])))
        prop.sort()
        m1[s] = prop
        print("  %-8s %d bougies M1" % (s, len(prop)))
    mt5.shutdown()

    for k in list(pos):
        if k not in coef or pos[k]["sym"] not in m1:
            del pos[k]
        else:
            pos[k]["coef"] = coef[k]
            pos[k]["achat"] = (pos[k]["type"] == 0)   # DEAL_TYPE_BUY == 0
    print("positions exploitables : %d" % len(pos))
    return pos, m1


def fenetre(bars, t0, t1):
    """bougies dont l heure est dans [t0, t1]. Recherche dichotomique."""
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid][0] < t0:
            lo = mid + 1
        else:
            hi = mid
    out = []
    i = lo
    while i < len(bars) and bars[i][0] <= t1:
        out.append(bars[i])
        i += 1
    return out


def excursions(pos, m1):
    """MFE et MAE en points puis en euros, position par position."""
    out, sans = [], 0
    for k, p in pos.items():
        b = fenetre(m1[p["sym"]], p["open"], p["close"])
        if len(b) < 2:
            sans += 1
            continue
        px = p["px"]
        if p["achat"]:
            mfe = max(h for _t, h, _l in b) - px
            mae = px - min(l for _t, _h, l in b)
        else:
            mfe = px - min(l for _t, _h, l in b)
            mae = max(h for _t, h, _l in b) - px
        out.append({"id": k, "sym": p["sym"], "achat": p["achat"], "px": px,
                    "open": p["open"], "close": p["close"], "coef": p["coef"],
                    "pnl": p["pnl"], "bars": b,
                    "mfe": max(0.0, mfe), "mae": max(0.0, mae),
                    "duree": (p["close"] - p["open"]) / 60.0})
    if sans:
        print("/!\\ %d positions sans bougie M1 exploitable -- ignorees." % sans)
    return out


def simuler(t, tp_pts, sl_pts):
    """Rejoue la position bougie par bougie avec un objectif et un stop.
    Renvoie ('TP'|'SL'|'REEL', pnl_euros, ambigu)."""
    px, ach, co = t["px"], t["achat"], t["coef"]
    if ach:
        niv_tp, niv_sl = px + tp_pts, px - sl_pts
    else:
        niv_tp, niv_sl = px - tp_pts, px + sl_pts
    for _ts, h, l in t["bars"]:
        touche_tp = (h >= niv_tp) if ach else (l <= niv_tp)
        touche_sl = (l <= niv_sl) if ach else (h >= niv_sl)
        if touche_tp and touche_sl:
            # ambiguite intra-bougie : on suppose le STOP, jamais l inverse
            return "SL", -sl_pts * co, True
        if touche_sl:
            return "SL", -sl_pts * co, False
        if touche_tp:
            return "TP", tp_pts * co, False
    return "REEL", t["pnl"], False


def main():
    pos, m1 = charger()
    if not pos:
        return 1
    trades = excursions(pos, m1)
    if len(trades) < 50:
        print("trop peu de positions exploitables (%d)." % len(trades)); return 1

    with io.open(SORTIE, "w", encoding="utf-8") as fo:
        # la colonne 'jour' permet de redecouper la periode dans mae_mfe.py
        # sans jamais recharger le M1 : indispensable pour isoler le regime
        # sans closer sans refaire tout le rejeu.
        fo.write("id;jour;sym;sens;mfe_pts;mae_pts;mfe_eur;mae_eur;pnl_eur;duree_min\n")
        for t in trades:
            fo.write("%s;%s;%s;%s;%.1f;%.1f;%.2f;%.2f;%.2f;%.0f\n"
                     % (t["id"],
                        dt.datetime.utcfromtimestamp(t["open"]).strftime("%Y-%m-%d"),
                        t["sym"], "ACHAT" if t["achat"] else "VENTE",
                        t["mfe"], t["mae"], t["mfe"] * t["coef"],
                        t["mae"] * t["coef"], t["pnl"], t["duree"]))
    print("ecrit %s : %d positions" % (SORTIE, len(trades)))

    print()
    print("=" * 90)
    print("  1. de combien faut-il souffrir, et combien rend-on ?")
    print("=" * 90)
    print("%-9s %6s %10s %10s %10s %10s %9s"
          % ("actif", "N", "MFE med", "MAE med", "MFE q75", "MAE q75", "duree med"))
    print("-" * 90)
    for s in sorted({t["sym"] for t in trades}):
        g = [t for t in trades if t["sym"] == s]
        print("%-9s %6d %10.1f %10.1f %10.1f %10.1f %8.0f mn"
              % (s, len(g), med([t["mfe"] for t in g]), med([t["mae"] for t in g]),
                 quart([t["mfe"] for t in g], 0.75), quart([t["mae"] for t in g], 0.75),
                 med([t["duree"] for t in g])))
    print("-" * 90)
    print("en points. MFE = meilleur moment de la position, MAE = pire moment.")

    print()
    print("=" * 90)
    print("  2. le diagnostic classique MAE / MFE")
    print("=" * 90)
    gagn = [t for t in trades if t["pnl"] > 0]
    perd = [t for t in trades if t["pnl"] <= 0]
    print("  %d gagnantes, %d perdantes" % (len(gagn), len(perd)))
    if gagn and perd:
        print("  MAE mediane des GAGNANTES : %.1f pts (%.2f EUR)"
              % (med([t["mae"] for t in gagn]),
                 med([t["mae"] * t["coef"] for t in gagn])))
        print("     -> la chaleur qu il faut accepter pour laisser gagner.")
        print("        Un stop plus serre que ca coupe des trades gagnants.")
        print("  MAE mediane des PERDANTES : %.1f pts (%.2f EUR)"
              % (med([t["mae"] for t in perd]),
                 med([t["mae"] * t["coef"] for t in perd])))
        print("  MFE mediane des PERDANTES : %.1f pts (%.2f EUR)"
              % (med([t["mfe"] for t in perd]),
                 med([t["mfe"] * t["coef"] for t in perd])))
        print("     -> le profit qui a ete VU puis rendu sur les trades perdants.")
        m = med([t["mae"] for t in gagn])
        n = sum(1 for t in perd if t["mae"] <= m)
        print("  %d perdantes sur %d (%.0f%%) n ont jamais depasse la MAE mediane"
              % (n, len(perd), 100.0 * n / len(perd)))
        print("  des gagnantes : ce sont celles qu un stop ne peut PAS distinguer.")

    print()
    print("=" * 90)
    print("  3. LA QUESTION : un objectif et un stop auraient-ils aide ?")
    print("=" * 90)
    reel = sum(t["pnl"] for t in trades)
    print("  resultat REEL de la stack sur ces %d positions : %+.2f EUR"
          % (len(trades), reel))
    print()
    for s in sorted({t["sym"] for t in trades}):
        g = [t for t in trades if t["sym"] == s]
        if len(g) < 30:
            continue
        base = med([t["mfe"] for t in g]) or 1.0
        print("  %s -- %d positions, MFE median %.1f pts, reel %+.2f EUR"
              % (s, len(g), base, sum(t["pnl"] for t in g)))
        print("    %8s %8s %10s %8s %8s %12s"
              % ("TP pts", "SL pts", "TP first", "SL first", "ni l un", "resultat"))
        meilleur = None
        for ftp in GRILLE:
            for fsl in GRILLE:
                tp, sl = ftp * base, fsl * base
                tot = ntp = nsl = nre = namb = 0.0
                for t in g:
                    q, v, amb = simuler(t, tp, sl)
                    tot += v
                    namb += 1 if amb else 0
                    if q == "TP":
                        ntp += 1
                    elif q == "SL":
                        nsl += 1
                    else:
                        nre += 1
                if meilleur is None or tot > meilleur[0]:
                    meilleur = (tot, tp, sl, ntp, nsl, nre, namb)
                if ftp in (0.5, 1.0, 2.0) and fsl in (0.5, 1.0, 2.0):
                    print("    %8.0f %8.0f %9.0f%% %7.0f%% %7.0f%% %+12.2f"
                          % (tp, sl, 100.0 * ntp / len(g), 100.0 * nsl / len(g),
                             100.0 * nre / len(g), tot))
        tot, tp, sl, ntp, nsl, nre, namb = meilleur
        print("    MEILLEURE combinaison de la grille : TP %.0f / SL %.0f -> %+.2f EUR"
              % (tp, sl, tot))
        print("      (%.0f%% TP, %.0f%% SL, %.0f%% sortie reelle, %.0f%% d ambiguite"
              % (100.0 * ntp / len(g), 100.0 * nsl / len(g),
                 100.0 * nre / len(g), 100.0 * namb / len(g)))
        print("       intra-bougie tranchee en faveur du stop)")
        print("      gain contre le reel : %+.2f EUR" % (tot - sum(t["pnl"] for t in g)))
        print()

    print("=" * 90)
    print("  comment lire, et le piege a eviter")
    print("=" * 90)
    print("La MEILLEURE combinaison est choisie SUR LES MEMES DONNEES qu elle")
    print("optimise : avec 49 couples testes par actif, en trouver un qui bat")
    print("le reel est presque garanti, meme dans du bruit. Ce chiffre n est PAS")
    print("une esperance de gain, c est une borne haute optimiste.")
    print()
    print("Ce qui vaut vraiment, c est la section 2 : la MAE mediane des")
    print("gagnantes dit ou le stop ne peut pas descendre sans couper ce qui")
    print("marche, et la MFE des perdantes dit combien de profit vu a ete rendu.")
    print("Ces deux nombres-la ne dependent d aucun choix de parametre.")
    print()
    print("Et le taux d ambiguite intra-bougie borne la confiance : au-dela de")
    print("15 ou 20%%, il faudrait du tick pour trancher, pas du M1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
