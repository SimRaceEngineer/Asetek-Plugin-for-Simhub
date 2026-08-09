# -*- coding: utf-8 -*-
"""
v5_periode.py -- l effet du sens du matin existe-t-il dans LES DEUX periodes ?

CE QU ON A DECOUVERT ET QUI OBLIGE A REFAIRE LA MESURE
    Le corpus du gel V5 melange deux populations :
      juillet  21, 29, 30, 31/07 -- closer ACTIF, machine msitrident1,
                                    AUCUN contexte orderflow
      aout     03 au 07/08       -- closer inactif, VPS reinstalle,
                                    orderflow present
    Ce n est pas un defaut de couverture, c est une frontiere de date.

    Pire : deux seances portent tout le P&L. 29/07 fait +5933 et 04/08
    fait +4857, contre -5760 cumules pour les sept autres.

    Le p=0,008 a l unite seance venait donc d un test sur les MAGNITUDES,
    ecrase par ces deux journees. Le test de signe seul donne 7/9, soit
    p environ 0,18 : NON significatif.

CE QUE CE SCRIPT FAIT
    1. le detail seance par seance, en clair, pour qu on VOIE les neuf
    2. la mesure separee sur chaque periode
    3. la mesure en retirant les deux journees dominantes
    4. le test de signe, robuste, a cote du test de magnitude
    5. le controle horaire dans chaque cas

    Aucune de ces vues ne sauvera l effet a elle seule -- quatre et cinq
    seances, c est trop peu. Le but n est pas de conclure mais de savoir
    OU l effet vit, avant que le hors-echantillon ne tranche en septembre.
"""
import io, os, sys, math, json

CSV = "profil_jour.csv"
CHURN = [os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
         os.path.join("docs", "churn_trades", "churn_trades.jsonl")]
ALIAS = {"US100": "NAS100", "NAS100": "NAS100", "US500": "SPX500",
         "SPX500": "SPX500", "US30": "US30", "DJ30": "US30"}
ACHAT = ("BUY", "ACHAT", "LONG", "B")
VENTE = ("SELL", "VENTE", "SHORT", "S")
COUPURE = "2026-08-01"        # frontiere entre les deux regimes


def moy(xs):
    return sum(xs) / float(len(xs)) if xs else None


def med(xs):
    xs = sorted(xs)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def et(xs):
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


def binom(k, n):
    """Test de signe bilateral exact. Le seul test robuste aux journees
    hors norme : il ne regarde que le SENS de l ecart, jamais son montant."""
    if n == 0:
        return None
    c = [1]
    for i in range(n):
        c = [1] + [c[j] + c[j + 1] for j in range(len(c) - 1)] + [1]
    tot = float(sum(c))
    q = sum(c[i] for i in range(n + 1) if i >= max(k, n - k) or i <= min(k, n - k))
    return min(1.0, q / tot)


def lire_matin():
    if not os.path.isfile(CSV):
        print("introuvable : %s" % CSV); sys.exit(1)
    lg = [l.rstrip("\n") for l in io.open(CSV, encoding="utf-8-sig") if l.strip()]
    sep = ";" if lg[0].count(";") >= lg[0].count(",") else ","
    ent = [c.strip() for c in lg[0].split(sep)]
    out = {}
    for l in lg[1:]:
        c = l.split(sep)
        if len(c) < len(ent):
            c += [""] * (len(ent) - len(c))
        d = dict(zip(ent, c))
        s = (d.get("am_dir") or "").strip().upper()
        s = "UP" if (s.startswith("H") or s == "UP") else ("DOWN" if (s.startswith("B") or s == "DOWN") else "")
        j, a = (d.get("jour") or "").strip(), (d.get("asset") or "").strip()
        if j and a and s:
            out[(j, a)] = s
    return out


def charger(matin):
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
            s = (o.get("dir") or "").strip().upper()
            sens = "UP" if s in ACHAT else ("DOWN" if s in VENTE else "")
            b = (o.get("asset") or "").strip().upper()
            asset = ALIAS.get(b, b)
            am = matin.get((ts[:10], asset))
            if not am or not sens:
                continue
            par[tk] = {"jour": ts[:10], "heure": int(ts[11:13]), "asset": asset,
                       "accord": "AVEC" if sens == am else "CONTRE",
                       "pnl": float(pnl)}
    return list(par.values())


def ecarts_par_seance(lot):
    d = {}
    for t in lot:
        e = d.setdefault(t["jour"], {"AVEC": [], "CONTRE": []})
        e[t["accord"]].append(t["pnl"])
    out = []
    for j in sorted(d):
        a, c = d[j]["AVEC"], d[j]["CONTRE"]
        if len(a) >= 3 and len(c) >= 3:
            out.append((j, len(a), moy(a), len(c), moy(c), moy(a) - moy(c),
                        sum(a) + sum(c)))
    return out


def bloc(lot, titre):
    if not lot:
        print("\n%s : aucun ticket." % titre)
        return
    a = [t["pnl"] for t in lot if t["accord"] == "AVEC"]
    c = [t["pnl"] for t in lot if t["accord"] == "CONTRE"]
    if len(a) < 20 or len(c) < 20:
        print("\n%s : trop peu de tickets (avec=%d contre=%d)." % (titre, len(a), len(c)))
        return
    e, p = t_deux(a, c)
    ec = ecarts_par_seance(lot)
    pos = sum(1 for x in ec if x[5] > 0)
    ps = binom(pos, len(ec)) if ec else None
    # magnitude a l unite seance
    dd = [x[5] for x in ec]
    pm = None
    if len(dd) >= 3:
        se = et(dd) / math.sqrt(len(dd)) if et(dd) else 0.0
        pm = p_norm(moy(dd) / se) if se else None

    print()
    print("-" * 88)
    print("  %s" % titre)
    print("-" * 88)
    print("  AVEC   %5d tk  %+8.2f EUR/tk   |   CONTRE %5d tk  %+8.2f   |  ecart %+7.2f (p=%s)"
          % (len(a), moy(a), len(c), moy(c), e, "%.3f" % p if p is not None else "-"))
    if ec:
        print("  a l unite seance : %d seances, ecart moyen %+.2f, MEDIAN %+.2f"
              % (len(ec), moy(dd), med(dd)))
        print("    magnitude p=%s   |   SIGNE %d/%d p=%s  <-- le robuste"
              % ("%.3f" % pm if pm is not None else "-", pos, len(ec),
                 "%.3f" % ps if ps is not None else "-"))
    # controle horaire
    ref = {}
    for t in lot:
        ref.setdefault(t["heure"], []).append(t["pnl"])
    ref = dict((h, moy(v)) for h, v in ref.items())
    ca = [t["pnl"] - ref[t["heure"]] for t in lot if t["accord"] == "AVEC"]
    cc = [t["pnl"] - ref[t["heure"]] for t in lot if t["accord"] == "CONTRE"]
    eh, ph = t_deux(ca, cc)
    print("  a heure egale    : ecart %+.2f, p=%s"
          % (eh if eh is not None else 0.0, "%.3f" % ph if ph is not None else "-"))


def main():
    lot = charger(lire_matin())
    if len(lot) < 100:
        print("trop peu de tickets apparies (%d)." % len(lot)); return 1
    js = sorted({t["jour"] for t in lot})
    print("%d tickets, %d seances, %s -> %s" % (len(lot), len(js), js[0], js[-1]))

    print()
    print("=" * 88)
    print("  1. le detail seance par seance -- regarde-le avant tout le reste")
    print("=" * 88)
    print("%-12s %6s %10s %6s %10s %10s %12s"
          % ("jour", "N avec", "EUR/tk", "N ctr", "EUR/tk", "ecart", "PnL seance"))
    print("-" * 88)
    ec = ecarts_par_seance(lot)
    for j, na, ma, nc, mc, e, tot in ec:
        print("%-12s %6d %+10.2f %6d %+10.2f %+10.2f %12.2f"
              % (j, na, ma, nc, mc, e, tot))
    print("-" * 88)
    dom = sorted(ec, key=lambda x: -x[6])[:2]
    print("les 2 seances les plus rentables : %s"
          % ", ".join("%s (%+.0f)" % (x[0], x[6]) for x in dom))
    tot = sum(x[6] for x in ec)
    print("elles pesent %+.0f sur un total de %+.0f -- les autres font %+.0f"
          % (sum(x[6] for x in dom), tot, tot - sum(x[6] for x in dom)))

    print()
    print("=" * 88)
    print("  2. par periode, puis sans les deux journees dominantes")
    print("=" * 88)
    print("juillet = closer ACTIF, msitrident1, pas d orderflow")
    print("aout    = closer inactif, VPS reinstalle, orderflow present")
    bloc(lot, "TOUT LE CORPUS (rappel du gel)")
    bloc([t for t in lot if t["jour"] < COUPURE], "JUILLET seul")
    bloc([t for t in lot if t["jour"] >= COUPURE], "AOUT seul")
    exclus = set(x[0] for x in dom)
    bloc([t for t in lot if t["jour"] not in exclus],
         "SANS les 2 journees dominantes (%s)" % ", ".join(sorted(exclus)))

    print()
    print("=" * 88)
    print("  comment lire")
    print("=" * 88)
    print("Le test de SIGNE est le seul robuste ici : il ne regarde que le sens")
    print("de l ecart, jamais son montant, donc deux journees hors norme ne")
    print("peuvent pas le porter. Sur 4 ou 5 seances il n atteindra jamais la")
    print("significativite -- ce n est pas une faiblesse du test, c est la")
    print("taille du corpus.")
    print()
    print("Ce qu on cherche n est donc pas un p, c est une CONSTANCE : le meme")
    print("signe dans les deux periodes, et l ecart qui survit au retrait des")
    print("deux grosses journees. Si l effet ne vit que dans une periode ou que")
    print("dans deux seances, le gel V5 partira avec une hypothese deja fragile,")
    print("et il faudra le dire dans la lecture de septembre.")
    print()
    print("Le gel V5 n est PAS modifie par ce script. On documente sa fragilite,")
    print("on ne retouche pas les regles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
