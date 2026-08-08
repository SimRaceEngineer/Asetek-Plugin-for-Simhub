# -*- coding: utf-8 -*-
"""
seuil_seance.py -- le seuil d excursion, en prix, puis son effet sur le P&L.

L IDEE TESTEE
    Le range du matin fixe l echelle de l apres-midi. Quand le prix a
    parcouru X fois ce range au-dela de la borne du matin -- dans un sens
    ou dans l autre -- la volatilite exploitable de la seance a ete
    largement delivree. On arreterait alors d OUVRIR des ordres.

    Attention a la justification : ce n est PAS parce que le mouvement
    s essouffle. Le hazard mesure est plat, il ne s essouffle pas. C est
    parce que x*S(x) a un maximum : au-dela, la fraction de seances qui
    suivent chute plus vite que le gain unitaire ne monte.

CE QUE CE SCRIPT MESURE
    1. l heure du premier franchissement du seuil, par seance et par actif
    2. le P&L des tickets ouverts AVANT ce seuil contre ceux ouverts APRES

    Le test se fait a l unite SEANCE, pas au ticket : les tickets d une
    meme journee sont correles, un t-test sur tickets est trompeur. C est
    la correction qu on a deja etablie et qui avait retourne des resultats.

CE QU IL NE MESURE PAS
    La version "on cloture tout au seuil". Ca demande le chemin des
    positions minute par minute, pas seulement les extremes de seance.
    Ici on ne juge que le blocage des NOUVELLES entrees, qui ne touche a
    aucune position ouverte et reste reversible.
"""
import io, os, sys, math, json, datetime as dt

DEBUT_AM = 8            # heure de debut du matin (broker)
FIN_AM = 14             # le matin s arrete a 14h00, comme profil_jour.py
FIN_PM = 22
SEUILS = [0.50, 0.75, 1.00, 1.25, 1.50]
ACTIFS = ["US30", "SPX500", "NAS100"]
SORTIE = "seuil_seance.csv"
# churn_trades nomme les indices autrement que MT5. Sans cette table,
# 1346 tickets sur 2223 tombaient silencieusement du croisement et tout
# le resultat ne portait que sur l US30.
ALIAS_ACTIF = {"US100": "NAS100", "NAS100": "NAS100",
               "US500": "SPX500", "SPX500": "SPX500",
               "US30": "US30", "DJ30": "US30"}
CHURN = [os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
         os.path.join("docs", "churn_trades", "churn_trades.jsonl")]


def moy(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / float(len(xs)) if xs else None


def et(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / float(len(xs))
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def p_norm(z):
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))


# ------------------------------------------------------- 1. les seuils
def construire_seuils(jour_min, jour_max):
    import MetaTrader5 as mt5
    if not mt5.initialize():
        print("MT5 injoignable"); sys.exit(1)
    d0 = dt.datetime.strptime(jour_min, "%Y-%m-%d") - dt.timedelta(days=3)
    d1 = dt.datetime.strptime(jour_max, "%Y-%m-%d") + dt.timedelta(days=2)
    par_jour = {}
    for sym in ACTIFS:
        mt5.symbol_select(sym, True)
        r = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, d0, d1)
        if r is None or len(r) == 0:
            print("  %-8s aucune bougie" % sym); continue
        print("  %-8s %d bougies M5" % (sym, len(r)))
        for x in r:
            t = dt.datetime.utcfromtimestamp(int(x["time"]))
            j = t.strftime("%Y-%m-%d")
            if not (DEBUT_AM <= t.hour < FIN_PM):
                continue
            par_jour.setdefault((j, sym), []).append(
                (t, float(x["high"]), float(x["low"])))
    mt5.shutdown()

    lignes, seances = [], {}
    for (j, sym), bars in sorted(par_jour.items()):
        bars.sort()
        am = [b for b in bars if b[0].hour < FIN_AM]
        pm = [b for b in bars if b[0].hour >= FIN_AM]
        if len(am) < 12 or len(pm) < 12:
            continue
        amh = max(b[1] for b in am)
        aml = min(b[2] for b in am)
        amr = amh - aml
        if amr <= 0:
            continue
        rec = {"jour": j, "asset": sym, "am_range": amr,
               "am_high": amh, "am_low": aml}
        for X in SEUILS:
            hb, bb = amh + X * amr, aml - X * amr
            quand, cote = "", ""
            for t, h, l in pm:
                if h > hb or l < bb:
                    quand = t.strftime("%H:%M")
                    cote = "HAUT" if h > hb else "BAS"
                    break
            rec["t_%.2f" % X] = quand
            rec["c_%.2f" % X] = cote
        seances[(j, sym)] = rec
        lignes.append(rec)

    cols = ["jour", "asset", "am_range", "am_high", "am_low"]
    for X in SEUILS:
        cols += ["t_%.2f" % X, "c_%.2f" % X]
    with io.open(SORTIE, "w", encoding="utf-8") as fo:
        fo.write(";".join(cols) + "\n")
        for r in lignes:
            fo.write(";".join(str(r.get(c, "")) for c in cols) + "\n")
    print("ecrit %s : %d lignes" % (SORTIE, len(lignes)))

    print()
    print("=== a quelle heure le seuil tombe-t-il ? ===")
    print("%-8s %6s %8s %9s %9s %9s"
          % ("seuil", "atteint", "part", "heure med", "1er quart", "dern. q."))
    print("-" * 60)
    for X in SEUILS:
        hs = sorted(r["t_%.2f" % X] for r in lignes if r["t_%.2f" % X])
        n = len(hs)
        if not n:
            print("%-8.2f %6d" % (X, 0)); continue
        print("%-8.2f %6d %7.0f%% %9s %9s %9s"
              % (X, n, 100.0 * n / len(lignes), hs[n // 2],
                 hs[n // 4], hs[(3 * n) // 4]))
    print("-" * 60)
    print("Une heure mediane tardive = le seuil ne bloque presque rien.")
    print("Une heure mediane tot = il coupe une vraie part de la seance.")
    return seances


# ------------------------------------------- 2. le P&L avant / apres
def charger_tickets():
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
            brut = (o.get("asset") or "").strip().upper()
            par[tk] = {"jour": ts[:10], "hm": ts[11:16],
                       "brut": brut, "asset": ALIAS_ACTIF.get(brut, brut),
                       "heure": int(ts[11:13]), "pnl": float(pnl)}
    return list(par.values())


def controle_heure(tickets, seances, cle):
    """LE CONTROLE QUI DECIDE.

    Le seuil tombe vers 16h30-17h de mediane, or on sait deja que la fin
    de session US est le bon creneau. "Apres le seuil" pourrait donc n etre
    qu un synonyme de "tard", et n apporter strictement rien.

    On compare donc avant et apres A HEURE EGALE : dans chaque tranche
    horaire, certaines seances ont deja franchi le seuil et d autres non.
    Si l ecart survit a ce decoupage, le seuil dit quelque chose que
    l heure ne dit pas. S il s evapore, c est l heure qui parlait."""
    # On retire l effet horaire par centrage : chaque ticket est ramene a
    # l ecart entre son P&L et la moyenne de SA tranche horaire. Toute
    # difference qui subsiste ensuite ne peut plus venir de l heure.
    # Le decoupage en tranches comparees deux a deux serait plus direct,
    # mais il n a aucune puissance ici : le seuil tombe presque toujours
    # a la meme heure, donc chaque tranche est entierement avant ou
    # entierement apres. Le centrage, lui, garde tous les tickets.
    lots = {}
    for t in tickets:
        lots.setdefault(t["heure"], []).append(t["pnl"])
    ref = dict((h, moy(v)) for h, v in lots.items())

    av, ap, mixtes = [], [], 0
    par_h = {}
    for t in tickets:
        r = seances.get((t["jour"], t["asset"]))
        if r is None:
            continue
        q = r.get(cle) or ""
        cote = "apres" if (q and t["hm"] >= q) else "avant"
        (ap if cote == "apres" else av).append(t["pnl"] - ref.get(t["heure"], 0.0))
        par_h.setdefault(t["heure"], {"avant": 0, "apres": 0})[cote] += 1
    mixtes = sum(1 for d in par_h.values() if d["avant"] >= 5 and d["apres"] >= 5)
    if len(av) < 20 or len(ap) < 20:
        print("    a heure egale : trop peu de tickets apres centrage.")
        return
    e = moy(av) - moy(ap)
    se = math.sqrt(et(av) ** 2 / len(av) + et(ap) ** 2 / len(ap))
    p = p_norm(e / se) if se else None
    print("    a heure egale (P&L centre par tranche horaire) :")
    print("      ecart %+.2f EUR/tk, p=%s, %d tranches reellement mixtes"
          % (e, "%.3f" % p if p is not None else "-", mixtes))
    if mixtes < 2:
        print("      /!\\ moins de 2 tranches mixtes : le centrage ne separe")
        print("          presque rien du seuil et de l heure. Non concluant.")
    elif abs(e) < 2.0:
        print("      -> l ecart s evapore : c est l heure qui parlait, pas le seuil.")
    else:
        print("      -> l ecart SURVIT : le seuil dit quelque chose de plus que l heure.")


def comparer(seances, tickets):
    print()
    print("=" * 78)
    print("  P&L des tickets ouverts AVANT le seuil contre APRES")
    print("=" * 78)
    jt = sorted({t["jour"] for t in tickets})
    js = sorted({j for j, _ in seances})
    com = sorted(set(jt) & set(js))
    print("seances avec tickets %d, avec prix %d, communes %d"
          % (len(jt), len(js), len(com)))
    if not com:
        print("aucune seance commune -- verifie les dates ou le fuseau.")
        return
    aa, brut = {}, {}
    for t in tickets:
        if t["jour"] not in com:
            continue
        aa[t["asset"]] = aa.get(t["asset"], 0) + 1
        brut[t["brut"]] = brut.get(t["brut"], 0) + 1
    print("actifs churn_trades : %s" % ", ".join("%s=%d" % kv for kv in sorted(brut.items())))
    print("apres alias MT5    : %s" % ", ".join("%s=%d" % kv for kv in sorted(aa.items())))
    inconnus = [a for a in aa if a not in ACTIFS]
    if inconnus:
        perdus = sum(aa[a] for a in inconnus)
        print("/!\\ %d tickets sans prix charge (%s) -- ils seront ignores."
              % (perdus, ", ".join(inconnus)))
        print("    Complete ALIAS_ACTIF en tete du fichier avant de conclure.")

    # controle de fuseau : si l horodatage des tickets et celui des bougies
    # MT5 ne sont pas sur la meme horloge, la comparaison avant/apres est
    # fausse sans rien casser visiblement. On le verifie explicitement.
    ht = sorted(t["hm"] for t in tickets if t["jour"] in com)
    if ht:
        n = len(ht)
        print("heures des tickets : %s -> %s (mediane %s)" % (ht[0], ht[-1], ht[n // 2]))
        print("heures des bougies : %02d:00 -> %02d:00, matin jusqu a %02d:00"
              % (DEBUT_AM, FIN_PM, FIN_AM))
        deb = "%02d:00" % DEBUT_AM
        fin = "%02d:00" % FIN_PM
        hors = sum(1 for h in ht if h < deb or h >= fin)
        if hors:
            print("/!\\ %d tickets sur %d hors de la plage des bougies (%.0f%%)."
                  % (hors, n, 100.0 * hors / n))
            print("    Decalage d horloge probable entre churn_trades et MT5 :")
            print("    le resultat ci-dessous serait fausse. A verifier avant de lire.")
        else:
            print("horloges coherentes : tous les tickets tombent dans la plage.")

    for X in SEUILS:
        cle = "t_%.2f" % X
        av, ap, par_seance = [], [], {}
        for t in tickets:
            r = seances.get((t["jour"], t["asset"]))
            if r is None:
                continue
            q = r.get(cle) or ""
            if not q:
                cote = "avant"          # seuil jamais atteint : tout est avant
            else:
                cote = "apres" if t["hm"] >= q else "avant"
            (av if cote == "avant" else ap).append(t["pnl"])
            d = par_seance.setdefault(t["jour"], {"avant": [], "apres": []})
            d[cote].append(t["pnl"])
        if len(ap) < 20:
            print()
            print("seuil %.2f : seulement %d tickets apres seuil -- trop peu." % (X, len(ap)))
            continue
        ma, mp = moy(av), moy(ap)
        # test a l unite seance : une observation par journee
        paires = [(moy(d["avant"]), moy(d["apres"])) for d in par_seance.values()
                  if len(d["avant"]) >= 3 and len(d["apres"]) >= 3]
        print()
        print("seuil %.2f x range du matin" % X)
        print("  avant : %5d tickets  %+8.2f EUR/tk  total %+10.2f" % (len(av), ma, sum(av)))
        print("  apres : %5d tickets  %+8.2f EUR/tk  total %+10.2f" % (len(ap), mp, sum(ap)))
        # le sens compte : bloquer l apres n aide QUE si l apres est moins bon
        print("  ecart : %+.2f EUR/tk -- l APRES est %s" %
              (ma - mp, "MOINS bon (bloquer aiderait)" if ma > mp
               else "MEILLEUR (bloquer couterait)"))
        controle_heure(tickets, seances, cle)
        if len(paires) >= 5:
            d = [a - b for a, b in paires]
            m, s = moy(d), et(d)
            se = s / math.sqrt(len(d)) if d else 0.0
            p = p_norm(m / se) if se else None
            pos = sum(1 for x in d if x > 0)
            print("  a l unite seance : %d seances, ecart moyen %+.2f, %d/%d positives, p=%s"
                  % (len(paires), m, pos, len(paires),
                     "%.3f" % p if p is not None else "-"))
        else:
            print("  a l unite seance : %d seances exploitables -- pas de test." % len(paires))
    print()
    print("-" * 78)
    print("Lire l ecart A L UNITE SEANCE, pas au ticket : les tickets d une")
    print("meme journee sont correles et gonflent artificiellement le t.")
    print("Un ecart positif = les tickets ouverts apres le seuil rapportent")
    print("moins : bloquer les nouvelles entrees aurait aide.")


def main():
    tickets = charger_tickets()
    if not tickets:
        print("aucun ticket lu dans docs/churn_trades -- lance depuis le dossier de la stack.")
        return 1
    js = sorted({t["jour"] for t in tickets})
    print("%d tickets, %d seances, %s -> %s" % (len(tickets), len(js), js[0], js[-1]))
    print()
    print("=== chargement des prix M5 ===")
    seances = construire_seuils(js[0], js[-1])
    if not seances:
        print("aucune seance de prix construite.")
        return 1
    comparer(seances, tickets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
