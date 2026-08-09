# -*- coding: utf-8 -*-
"""
ignition.py -- un critere de sortie en TEMPS, pas en prix.

POURQUOI CETTE FAMILLE N A JAMAIS ETE TESTEE, ET POURQUOI ELLE DEVRAIT
    jambe_stop.py a montre qu un stop en PRIX echoue a tous les niveaux :
    la courbe est negative sur toute la grille en periode de tendance, et
    la meilleure des 49 combinaisons TP/SL, choisie avec le recul, perd
    contre le reel sur les trois indices.

    La raison est connue : les gagnantes encaissent une vraie chaleur --
    MAE mediane de 11 a 13 points -- puis s en remettent. Tout stop assez
    serre pour attraper les perdantes tue ces gagnantes-la.

    Mais trois mesures independantes disent que l avantage est dans
    L ALLUMAGE :
      - la MFE mediane des perdantes vaut UN SIXIEME de celle des
        gagnantes : une perdante ne montre presque jamais de profit
      - en aout, le stop tres serre ne gagnait que parce qu il isolait
        les 17%% de positions qui n avaient jamais recule
      - les rails montrent qu il vaut mieux entrer au DEBUT d un
        mouvement qu a la fin

    Un critere en TEMPS ne coupe pas les gagnantes qui souffrent avant de
    partir : il ne coupe que celles qui NE FONT RIEN. C est exactement le
    profil des perdantes. C est donc la seule famille qui reste plausible
    apres l echec des stops en prix.

CE QU ON MESURE, EXACTEMENT ET SANS SIMULATION
    Pour chaque position reelle, on relit le M1 depuis son ouverture et on
    note ou elle en etait a 1, 2, 3, 5, 10 et 15 minutes. Puis on calcule
    le resultat EXACT de la regle : "a N minutes, si la position n est pas
    en profit, on sort au prix de ce moment ; sinon on garde le resultat
    reel". Aucune approximation, aucun tirage.

RESERVES ANNONCEES D AVANCE
    - une position deja fermee avant N minutes garde son resultat reel
    - le glissement n est pas modelise : sortir 3488 positions plus tot a
      un cout d execution que ce calcul ignore
    - et le resultat sera donne PAR REGIME, parce qu on a vu que tout
      bascule entre juillet et aout
"""
import io, os, sys, math, datetime as dt

DEBUT = dt.datetime(2026, 7, 20)
FIN = dt.datetime(2026, 8, 9)
MINUTES = [1, 2, 3, 5, 10, 15]
SORTIE = "ignition.csv"
COUPURE = "2026-08-01"


def moy(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / float(len(xs)) if xs else None


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def et(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    m = moy(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def p_norm(z):
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))


def t_deux(a, b):
    if len(a) < 3 or len(b) < 3:
        return None, None
    e = moy(a) - moy(b)
    se = math.sqrt(et(a) ** 2 / len(a) + et(b) ** 2 / len(b))
    return e, (p_norm(e / se) if se else None)


def charger():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        print("MT5 injoignable"); sys.exit(1)
    acc = mt5.account_info()
    print("compte %s" % acc.login)
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

    # euros par point, avec le meme controle de linearite que partout
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

    prix = {}
    for sym in sorted(set(p["sym"] for p in pos.values())):
        mt5.symbol_select(sym, True)
        r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1, DEBUT, FIN)
        if r is None or len(r) == 0:
            print("  %-8s aucune bougie M1" % sym); continue
        prix[sym] = dict((int(x["time"]), (float(x["close"]), float(x["high"]),
                                           float(x["low"]))) for x in r)
        print("  %-8s %d bougies M1" % (sym, len(prix[sym])))
    mt5.shutdown()
    return pos, coef, prix


def construire(pos, coef, prix):
    out, sans = [], 0
    for k, p in pos.items():
        if k not in coef or p["sym"] not in prix:
            continue
        px = prix[p["sym"]]
        t0 = (p["open"] // 60) * 60
        if t0 not in px:
            sans += 1
            continue
        signe = 1.0 if p["type"] == 0 else -1.0     # DEAL_TYPE_BUY == 0
        duree = (p["close"] - p["open"]) / 60.0
        d = {"id": k, "sym": p["sym"], "jour": dt.datetime.utcfromtimestamp(
                p["open"]).strftime("%Y-%m-%d"),
             "pnl": p["pnl"], "duree": duree, "coef": coef[k]}
        for N in MINUTES:
            t = t0 + N * 60
            if duree < N or t not in px:
                d["m%d" % N] = None          # deja fermee, ou pas de bougie
            else:
                d["m%d" % N] = signe * (px[t][0] - p["px"]) * coef[k]
        out.append(d)
    if sans:
        print("/!\\ %d positions sans bougie M1 a l ouverture -- ignorees." % sans)
    return out


def section1(rows):
    print()
    print("=" * 88)
    print("  1. profil d allumage : ou en est-on apres N minutes ?")
    print("=" * 88)
    print("En euros de P&L latent. Si les perdantes sont deja identifiables")
    print("tot, un critere en temps a un fondement.")
    print()
    print("  %-6s %8s %12s %12s %12s %12s"
          % ("N min", "obs", "gagnantes", "perdantes", "ecart", "% perd. <0"))
    print("  " + "-" * 68)
    for N in MINUTES:
        cle = "m%d" % N
        g = [r[cle] for r in rows if r[cle] is not None and r["pnl"] > 0]
        p = [r[cle] for r in rows if r[cle] is not None and r["pnl"] <= 0]
        if len(g) < 20 or len(p) < 20:
            continue
        neg = 100.0 * sum(1 for x in p if x < 0) / len(p)
        print("  %-6d %8d %+12.2f %+12.2f %+12.2f %11.0f%%"
              % (N, len(g) + len(p), med(g), med(p), med(g) - med(p), neg))
    print("  " + "-" * 68)
    print("  Colonnes = P&L latent MEDIAN a cet instant.")
    print("  Un ecart qui s ouvre vite = l allumage se voit tot.")


def section2(rows, titre, lot=None):
    """LE CALCUL EXACT. A N minutes, si la position n est pas en profit,
    on sort au prix de cet instant. Sinon elle garde son resultat reel.
    Une position deja fermee avant N minutes garde son resultat reel."""
    lot = rows if lot is None else lot
    if len(lot) < 50:
        print("\n  %s : %d positions seulement, non lu." % (titre, len(lot)))
        return
    reel = sum(r["pnl"] for r in lot)
    print()
    print("=" * 88)
    print("  2. resultat EXACT de la regle -- %s" % titre)
    print("=" * 88)
    print("  reel de la stack : %+.2f EUR sur %d positions" % (reel, len(lot)))
    print()
    print("  %-6s %10s %12s %12s %12s"
          % ("N min", "% coupees", "resultat", "vs reel", "encore ouv."))
    print("  " + "-" * 60)
    for N in MINUTES:
        cle = "m%d" % N
        tot, coup, ouv = 0.0, 0, 0
        for r in lot:
            v = r[cle]
            if v is None:
                tot += r["pnl"]              # deja fermee : resultat reel
                continue
            ouv += 1
            if v < 0:
                tot += v                     # on sort a cet instant, exact
                coup += 1
            else:
                tot += r["pnl"]
        print("  %-6d %9.0f%% %+12.2f %+12.2f %12d"
              % (N, 100.0 * coup / max(1, ouv), tot, tot - reel, ouv))
    print("  " + "-" * 60)
    print("  'encore ouv.' = positions encore vivantes a N minutes ; les")
    print("  autres etaient deja fermees et gardent leur resultat reel.")


def section3(rows):
    print()
    print("=" * 88)
    print("  3. par regime -- parce que tout bascule entre juillet et aout")
    print("=" * 88)
    print("Le stop en PRIX rapportait en aout et detruisait en juillet.")
    print("Si le critere en TEMPS aide dans LES DEUX, c est la difference")
    print("essentielle entre les deux familles, et elle serait decisive.")
    section2(rows, "JUILLET (tendance)", [r for r in rows if r["jour"] < COUPURE])
    section2(rows, "AOUT (range)", [r for r in rows if r["jour"] >= COUPURE])


def section4(rows):
    print()
    print("=" * 88)
    print("  4. variante : exiger un allumage MINIMUM, pas seulement positif")
    print("=" * 88)
    print("A N minutes, on exige au moins K euros de latent, sinon on sort.")
    print("K=0 est la regle de la section 2. Monter K coupe plus large.")
    reel = sum(r["pnl"] for r in rows)
    print()
    print("  %-6s %10s %12s %12s %12s %12s"
          % ("N min", "K=0", "K=5", "K=10", "K=20", "K=40"))
    print("  " + "-" * 70)
    for N in MINUTES:
        cle = "m%d" % N
        bouts = []
        for K in (0.0, 5.0, 10.0, 20.0, 40.0):
            tot = 0.0
            for r in rows:
                v = r[cle]
                if v is None:
                    tot += r["pnl"]
                elif v < K:
                    tot += v
                else:
                    tot += r["pnl"]
            bouts.append("%+12.2f" % (tot - reel))
        print("  %-6d %s" % (N, " ".join(bouts)))
    print("  " + "-" * 70)
    print("  Valeurs = ecart au reel. Positif = la regle aurait aide.")
    print("  Attention : cinq valeurs de K fois six valeurs de N font trente")
    print("  cellules choisies sur les memes donnees. La section 3 par regime")
    print("  vaut plus que le maximum de cette grille.")


def main():
    pos, coef, prix = charger()
    if not pos or not prix:
        return 1
    rows = construire(pos, coef, prix)
    if len(rows) < 100:
        print("trop peu de positions exploitables (%d)." % len(rows)); return 1
    js = sorted({r["jour"] for r in rows})
    print("exploitables : %d positions, %d seances, %s -> %s"
          % (len(rows), len(js), js[0], js[-1]))
    with io.open(SORTIE, "w", encoding="utf-8") as fo:
        cols = ["id", "jour", "sym", "pnl", "duree"] + ["m%d" % N for N in MINUTES]
        fo.write(";".join(cols) + "\n")
        for r in rows:
            fo.write(";".join(
                ("" if r.get(c) is None else
                 ("%.2f" % r[c] if isinstance(r.get(c), float) else str(r.get(c))))
                for c in cols) + "\n")
    print("ecrit %s" % SORTIE)

    section1(rows)
    section2(rows, "TOUT LE CORPUS")
    section3(rows)
    section4(rows)
    print()
    print("=" * 88)
    print("  comment lire")
    print("=" * 88)
    print("La section 3 est la seule qui compte vraiment. Un stop en prix")
    print("aidait en aout et detruisait en juillet : c est ce qui le rend")
    print("inutilisable, puisqu on ne sait pas dans quel regime on est.")
    print()
    print("Si le critere en temps aide dans LES DEUX regimes, il echappe a ce")
    print("piege et devient la premiere regle de sortie exploitable de toute")
    print("l etude. S il ne marche qu en aout, c est un stop deguise et il")
    print("faut l abandonner comme les autres.")
    print()
    print("Et le glissement reste hors du calcul : sortir des milliers de")
    print("positions plus tot coute quelque chose que ces chiffres ignorent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
