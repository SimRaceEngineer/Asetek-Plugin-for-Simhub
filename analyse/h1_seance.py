# -*- coding: utf-8 -*-
"""
h1_seance.py -- la PREMIERE HEURE americaine comme signal, et ce qu elle
                annonce du reste de la seance.

POURQUOI CETTE FENETRE ET PAS UNE AUTRE
    Tout ce qu on a mesure jusqu ici s arrete a 14h00 courtier, soit deux
    heures et demie AVANT l ouverture cash americaine. C est tot, donc
    exploitable, mais mal informe : le range du matin s est revele muet
    (ses deux bornes cassent dans la moitie des seances) et un mauvais
    etalon (les points fixes le battent).

    La premiere heure americaine se termine vers 17h30 courtier. Il reste
    alors quatre heures et demie de seance. C est la seule fenetre a la
    fois assez TARDIVE pour etre informee et assez PRECOCE pour servir.

L HEURE N EST PAS CODEE EN DUR
    Les bougies MT5 sont en heure courtier. L ouverture est localisee dans
    les donnees par le pic de volume, comme dans preopen.py -- qui avait
    trouve 16h30 sur les trois indices, soit UTC+3.

TROIS FENETRES
    PRE  : l heure avant l ouverture     (deja testee, mauvais etalon)
    H1   : la premiere heure americaine  (le signal qu on teste ici)
    RDS  : le reste de la seance         (ce qu on cherche a annoncer)

CE QU ON TESTE
    1. l amplitude de H1 annonce-t-elle celle du reste ? -- c est le
       regroupement de volatilite intraday, bien plus fort qu au jour le
       jour. Sous marche a volatilite constante, rho vaut 0 : le test est
       propre, pas besoin de temoin par permutation.
    2. la direction de H1 se prolonge-t-elle ? Ici aussi le temoin est
       50%% : les increments de deux fenetres disjointes sont independants
       sous marche aleatoire.
    3. casser le range du matin PENDANT H1, est-ce different ?
    4. H1 bat-il le matin comme predicteur ?
    5. et le P&L de la stack sur les tickets ouverts APRES H1.
"""
import io, os, sys, math, json, datetime as dt

ACTIFS = ["US30", "SPX500", "NAS100"]
JOURS = 190
DEBUT_AM = 8
FIN_AM = 14
FIN = 22
SORTIE = "h1_seance.csv"
CHURN = [os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
         os.path.join("docs", "churn_trades", "churn_trades.jsonl")]
ALIAS = {"US100": "NAS100", "NAS100": "NAS100", "US500": "SPX500",
         "SPX500": "SPX500", "US30": "US30", "DJ30": "US30"}


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


def p_prop(k1, n1, k2, n2):
    if n1 < 5 or n2 < 5:
        return None
    p = (k1 + k2) / float(n1 + n2)
    se = math.sqrt(p * (1 - p) * (1.0 / n1 + 1.0 / n2))
    return p_norm((k1 / float(n1) - k2 / float(n2)) / se) if se else None


def binom_demi(k, n):
    if n == 0:
        return None
    c = [1]
    for _ in range(n):
        c = [1] + [c[j] + c[j + 1] for j in range(len(c) - 1)] + [1]
    return min(1.0, sum(c[i] for i in range(n + 1)
                        if i >= max(k, n - k) or i <= min(k, n - k)) / float(sum(c)))


def rangs(xs):
    idx = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]:
            j += 1
        m = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[idx[k]] = m
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 8:
        return None, None
    ra, rb = rangs(a), rangs(b)
    ma, mb = moy(ra), moy(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    if da == 0 or db == 0:
        return None, None
    rho = num / (da * db)
    n = len(a)
    if abs(rho) >= 1.0:
        return rho, None
    t = rho * math.sqrt((n - 2) / (1 - rho * rho))
    return rho, p_norm(t)


# --------------------------------------------------------------- donnees
def charger():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        print("MT5 injoignable"); sys.exit(1)
    fin = dt.datetime.now()
    deb = fin - dt.timedelta(days=JOURS)
    out = {}
    for sym in ACTIFS:
        mt5.symbol_select(sym, True)
        bars, t = [], deb
        while t < fin:
            t2 = min(t + dt.timedelta(days=30), fin)
            r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, t, t2)
            if r is not None and len(r):
                bars.extend(r)
            t = t2
        if not bars:
            print("  %-8s aucune bougie" % sym); continue
        vus, prop = set(), []
        for x in bars:
            k = int(x["time"])
            if k in vus:
                continue
            vus.add(k)
            prop.append((dt.datetime.utcfromtimestamp(k), float(x["high"]),
                         float(x["low"]), float(x["open"]), float(x["close"]),
                         float(x["tick_volume"])))
        prop.sort()
        out[sym] = prop
        print("  %-8s %d bougies M5" % (sym, len(prop)))
    mt5.shutdown()
    return out


def localiser(prop):
    vol, n = {}, {}
    for t, h, l, o, c, v in prop:
        k = t.hour * 60 + (t.minute // 5) * 5
        vol[k] = vol.get(k, 0.0) + v
        n[k] = n.get(k, 0) + 1
    prof = dict((k, vol[k] / n[k]) for k in vol if n[k] >= 20)
    cand = [(v, k) for k, v in prof.items() if 12 * 60 <= k <= 18 * 60]
    return (max(cand)[1] if cand else None)


def bloc(bars):
    if not bars:
        return None
    bars = sorted(bars)
    h = max(x[1] for x in bars)
    l = min(x[2] for x in bars)
    o, c = bars[0][3], bars[-1][4]
    r = h - l
    return {"h": h, "l": l, "o": o, "c": c, "range": r,
            "dir": "UP" if c > o else "DOWN",
            "eff": (abs(c - o) / r) if r > 0 else 0.0}


def construire(prop, ouv):
    par = {}
    for t, h, l, o, c, v in prop:
        j = t.strftime("%Y-%m-%d")
        k = t.hour * 60 + t.minute
        d = par.setdefault(j, {"am": [], "pre": [], "h1": [], "rds": []})
        if DEBUT_AM * 60 <= k < FIN_AM * 60:
            d["am"].append((t, h, l, o, c, v))
        if ouv - 60 <= k < ouv:
            d["pre"].append((t, h, l, o, c, v))
        elif ouv <= k < ouv + 60:
            d["h1"].append((t, h, l, o, c, v))
        elif ouv + 60 <= k < FIN * 60:
            d["rds"].append((t, h, l, o, c, v))
    out = []
    for j in sorted(par):
        p = par[j]
        if len(p["am"]) < 20 or len(p["h1"]) < 8 or len(p["rds"]) < 20:
            continue
        am, h1, rds = bloc(p["am"]), bloc(p["h1"]), bloc(p["rds"])
        if not am or not h1 or not rds or am["range"] <= 0 or h1["range"] <= 0:
            continue
        d = {"jour": j, "am_range": am["range"], "am_dir": am["dir"],
             "h1_range": h1["range"], "h1_dir": h1["dir"], "h1_eff": h1["eff"],
             "rds_range": rds["range"], "rds_dir": rds["dir"], "rds_eff": rds["eff"],
             # H1 a-t-elle casse le range du matin, et de quel cote ?
             "h1_casse_haut": 1 if h1["h"] > am["h"] else 0,
             "h1_casse_bas": 1 if h1["l"] < am["l"] else 0,
             # le reste depasse-t-il les bornes de H1 ?
             "rds_au_dessus": 1 if rds["h"] > h1["h"] else 0,
             "rds_en_dessous": 1 if rds["l"] < h1["l"] else 0,
             "ext_haut": max(0.0, (rds["h"] - h1["h"]) / h1["range"]),
             "ext_bas": max(0.0, (h1["l"] - rds["l"]) / h1["range"]),
             "continue": 1 if rds["dir"] == h1["dir"] else 0}
        out.append(d)
    return out


# ------------------------------------------------------------- sections
def section1(tables):
    print()
    print("=" * 88)
    print("  1. l amplitude de la premiere heure annonce-t-elle le reste ?")
    print("=" * 88)
    print("Regroupement de volatilite intraday. Sous marche a volatilite")
    print("constante, rho vaut 0 : deux fenetres disjointes sont independantes.")
    print("Le test est donc propre, aucun temoin par permutation necessaire.")
    print()
    print("  %-9s %6s %10s %9s %10s %9s"
          % ("actif", "N", "rho H1", "p", "rho matin", "p"))
    print("  " + "-" * 60)
    for a in sorted(tables):
        t = tables[a]
        if len(t) < 30:
            continue
        r1, p1 = spearman([d["h1_range"] for d in t], [d["rds_range"] for d in t])
        r2, p2 = spearman([d["am_range"] for d in t], [d["rds_range"] for d in t])
        print("  %-9s %6d %+10.3f %9s %+10.3f %9s"
              % (a, len(t), r1 or 0, "%.3f" % p1 if p1 is not None else "-",
                 r2 or 0, "%.3f" % p2 if p2 is not None else "-"))
    print("  " + "-" * 60)
    print("  Colonne H1 nettement au-dessus de la colonne matin = la premiere")
    print("  heure americaine est un meilleur capteur d amplitude, et elle")
    print("  arrive assez tot pour servir.")


def section2(tables):
    print()
    print("=" * 88)
    print("  2. la direction de la premiere heure se prolonge-t-elle ?")
    print("=" * 88)
    print("Temoin = 50%%. Sous marche aleatoire, les directions de deux")
    print("fenetres disjointes sont independantes : ici le 50/50 est LE bon")
    print("temoin, contrairement au test d ordre des cassures.")
    print()
    print("  %-9s %6s %14s %9s %14s" % ("actif", "N", "continuation", "p", "eff. RDS"))
    print("  " + "-" * 58)
    for a in sorted(tables):
        t = tables[a]
        if len(t) < 30:
            continue
        k = sum(d["continue"] for d in t)
        p = binom_demi(k, len(t))
        print("  %-9s %6d %13.0f%% %9s %14.2f"
              % (a, len(t), 100.0 * k / len(t),
                 "%.3f" % p if p is not None else "-", med([d["rds_eff"] for d in t])))
    print("  " + "-" * 58)
    print("  Au-dessus de 50%% = continuation, en dessous = retournement.")
    print("  Rappel : la direction du MATIN donnait 88%% contre 56%% sur le")
    print("  cote qui cede. Si H1 fait mieux, elle la remplace ; sinon non.")


def section3(tables):
    print()
    print("=" * 88)
    print("  3. casser le range du matin PENDANT la premiere heure US")
    print("=" * 88)
    print("  %-9s %-16s %6s %12s %12s"
          % ("actif", "H1 a casse", "N", "continuation", "ext. mediane"))
    print("  " + "-" * 60)
    for a in sorted(tables):
        t = tables[a]
        cel = {}
        for d in t:
            if d["h1_casse_haut"] and not d["h1_casse_bas"]:
                k = "le haut"
            elif d["h1_casse_bas"] and not d["h1_casse_haut"]:
                k = "le bas"
            elif d["h1_casse_haut"] and d["h1_casse_bas"]:
                k = "les deux"
            else:
                k = "rien"
            cel.setdefault(k, []).append(d)
        for k in ("rien", "le haut", "le bas", "les deux"):
            g = cel.get(k, [])
            if len(g) < 10:
                continue
            ext = med([d["ext_haut"] if d["h1_dir"] == "UP" else d["ext_bas"] for d in g])
            print("  %-9s %-16s %6d %11.0f%% %12.2f"
                  % (a, k, len(g), 100.0 * moy([d["continue"] for d in g]), ext))
        print("  " + "-" * 60)


def section5(tables, ouv):
    """P&L des tickets ouverts APRES la premiere heure americaine."""
    par = {}
    for ch in CHURN:
        if not os.path.isfile(ch):
            continue
        for l in io.open(ch, encoding="utf-8-sig"):
            l = l.strip()
            if not l:
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ts, pnl, tk = o.get("entry_ts") or "", o.get("pnl_eur"), o.get("ticket")
            if len(ts) < 16 or pnl is None or tk is None or tk in par:
                continue
            b = (o.get("asset") or "").strip().upper()
            par[tk] = {"jour": ts[:10], "hm": ts[11:16],
                       "asset": ALIAS.get(b, b), "pnl": float(pnl)}
    if not par:
        print()
        print("  (pas de churn_trades lisible : section 5 sautee)")
        return
    seuil = "%02d:%02d" % ((ouv + 60) // 60, (ouv + 60) % 60)
    print()
    print("=" * 88)
    print("  5. P&L de la stack sur les tickets ouverts APRES %s" % seuil)
    print("=" * 88)
    print("INDICATIF : peu de seances de P&L. On lit le sens, pas le p.")
    idx = {}
    for a in tables:
        for d in tables[a]:
            idx[(d["jour"], a)] = d
    lots = {}
    for t in par.values():
        if t["hm"] < seuil:
            continue
        d = idx.get((t["jour"], t["asset"]))
        if d is None:
            continue
        # grande premiere heure ou petite, par rapport a la mediane de l actif
        lots.setdefault(t["asset"], []).append((d["h1_range"], t["pnl"], d))
    for a in sorted(lots):
        g = lots[a]
        if len(g) < 40:
            continue
        m = med([x[0] for x in g])
        pet = [x[1] for x in g if x[0] <= m]
        gro = [x[1] for x in g if x[0] > m]
        e, p = t_deux(gro, pet)
        print()
        print("  %-9s %d tickets apres %s" % (a, len(g), seuil))
        print("    premiere heure PETITE : %4d tk, total %+9.2f, moyen %+7.2f"
              % (len(pet), sum(pet), moy(pet) or 0))
        print("    premiere heure GRANDE : %4d tk, total %+9.2f, moyen %+7.2f"
              % (len(gro), sum(gro), moy(gro) or 0))
        print("    ecart %+.2f par ticket, p=%s"
              % (e if e is not None else 0.0, "%.3f" % p if p is not None else "-"))


def main():
    print("=== chargement M5 ===")
    data = charger()
    if not data:
        return 1
    tables, ouvs = {}, []
    for sym in sorted(data):
        ouv = localiser(data[sym])
        if ouv is None:
            continue
        ouvs.append(ouv)
        tables[sym] = construire(data[sym], ouv)
        print("  %-8s ouverture %02d:%02d, H1 = %02d:%02d-%02d:%02d, %d seances"
              % (sym, ouv // 60, ouv % 60, ouv // 60, ouv % 60,
                 (ouv + 60) // 60, (ouv + 60) % 60, len(tables[sym])))
    if not tables:
        print("aucune table construite."); return 1
    ouv = int(med(ouvs))
    print()
    print("fenetre H1 retenue : %02d:%02d -> %02d:%02d heure courtier"
          % (ouv // 60, ouv % 60, (ouv + 60) // 60, (ouv + 60) % 60))
    print("soit %02dh%02d -> %02dh%02d chez toi (courtier a UTC+3, une heure d avance)"
          % ((ouv - 60) // 60, ouv % 60, ouv // 60, (ouv + 60) % 60))

    cols = ["jour", "asset", "am_range", "am_dir", "h1_range", "h1_dir", "h1_eff",
            "rds_range", "rds_dir", "rds_eff", "h1_casse_haut", "h1_casse_bas",
            "rds_au_dessus", "rds_en_dessous", "ext_haut", "ext_bas", "continue"]
    with io.open(SORTIE, "w", encoding="utf-8") as fo:
        fo.write(";".join(cols) + "\n")
        for a in sorted(tables):
            for d in tables[a]:
                d["asset"] = a
                fo.write(";".join(str(d.get(c, "")) for c in cols) + "\n")
    print("ecrit %s : %d lignes" % (SORTIE, sum(len(v) for v in tables.values())))

    section1(tables)
    section2(tables)
    section3(tables)
    section5(tables, ouv)
    print()
    print("=" * 88)
    print("  lecture")
    print("=" * 88)
    print("La section 1 est la plus prometteuse : le regroupement de volatilite")
    print("intraday est bien plus fort qu au jour le jour, et c est exactement")
    print("ce qui manquait apres l echec de volatilite.py au pas quotidien.")
    print()
    print("Si rho H1 est franchement positif sur les trois actifs, tu as un")
    print("capteur d amplitude disponible a %02dh%02d courtier avec quatre heures"
          % ((ouv + 60) // 60, (ouv + 60) % 60))
    print("et demie de seance devant lui. C est la premiere chose de toute")
    print("l etude qui soit a la fois previsible et precoce.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
