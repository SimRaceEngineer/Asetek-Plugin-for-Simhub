# -*- coding: utf-8 -*-
"""
croix_flux.py -- le sens du matin et le contre-flux sont-ils la meme chose ?

LA QUESTION
    Deux effets mesures separement, tous deux solides :
      - aller CONTRE l orderflow rapporte  (contre-flux, deja etabli)
      - aller CONTRE le matin ruine        (sens_matin.py, +23 EUR/tk)
    Ce sont deux "contre" differents. Mais un ticket peut etre avec le
    matin ET contre le flux en meme temps. Si les deux variables sont
    fortement liees, il n y a qu une seule decouverte habillee de deux
    facons, et les geler toutes les deux serait se compter deux fois.

CE QU ON FAIT
    1. table 2x2 : combien de tickets dans chaque combinaison, et ce que
       chacune rapporte. Si une case est presque vide, les deux variables
       sont redondantes.
    2. l effet du matin SUBSISTE-T-IL a flux constant ? On le remesure
       separement chez les tickets AVEC le flux et chez les CONTRE. Si
       l ecart tient dans les deux strates, les deux effets sont
       independants et s ajoutent. S il disparait dans une strate, c est
       le flux qui portait tout.
    3. et reciproquement, l effet du flux subsiste-t-il a matin constant.

    C est un controle de stratification, exactement le meme raisonnement
    que le centrage horaire : un effet qui ne survit pas a variable
    confondante fixee n existe pas separement.
"""
import io, os, sys, math, json

CSV = "profil_jour.csv"
JOIN = os.path.join("docs", "churn_trades", "join_context.jsonl")
CHURN = [os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
         os.path.join("docs", "churn_trades", "churn_trades.jsonl")]
ALIAS = {"US100": "NAS100", "NAS100": "NAS100", "US500": "SPX500",
         "SPX500": "SPX500", "US30": "US30", "DJ30": "US30"}
ACHAT = ("BUY", "ACHAT", "LONG", "B")
VENTE = ("SELL", "VENTE", "SHORT", "S")


def moy(xs):
    return sum(xs) / float(len(xs)) if xs else None


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
        j, a = (d.get("jour") or "").strip(), (d.get("asset") or "").strip()
        s = (d.get("am_dir") or "").strip().upper()
        if s.startswith("H") or s == "UP":
            s = "UP"
        elif s.startswith("B") or s == "DOWN":
            s = "DOWN"
        else:
            continue
        if j and a:
            out[(j, a)] = s
    return out


def lire_flux():
    """contra du fichier de jointure : AVEC / CONTRE par rapport a l ORDERFLOW."""
    if not os.path.isfile(JOIN):
        print("introuvable : %s" % JOIN)
        print("lance d abord jointure3.py -- c est lui qui produit ce fichier.")
        sys.exit(1)
    out = {}
    for l in io.open(JOIN, encoding="utf-8-sig"):
        l = l.strip()
        if not l:
            continue
        try:
            o = json.loads(l)
        except ValueError:
            continue
        c = (o.get("contra") or "").strip().upper()
        if c in ("AVEC", "CONTRE"):
            out[o.get("ticket")] = c
    print("flux renseigne pour %d tickets" % len(out))
    return out


def lire_tickets():
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
            if s in ACHAT:
                s = "UP"
            elif s in VENTE:
                s = "DOWN"
            else:
                continue
            b = (o.get("asset") or "").strip().upper()
            par[tk] = {"ticket": tk, "jour": ts[:10], "heure": int(ts[11:13]),
                       "asset": ALIAS.get(b, b), "sens": s, "pnl": float(pnl)}
    return list(par.values())


def main():
    matin, flux, tickets = lire_matin(), lire_flux(), lire_tickets()
    lot = []
    for t in tickets:
        s = matin.get((t["jour"], t["asset"]))
        f = flux.get(t["ticket"])
        if s is None or f is None:
            continue
        t["matin"] = "AVEC" if t["sens"] == s else "CONTRE"
        t["flux"] = f
        lot.append(t)
    print("%d tickets ont A LA FOIS le matin et le flux renseignes" % len(lot))
    if len(lot) < 100:
        print("trop peu pour conclure. Le flux ne couvre qu une partie du corpus.")
        return 1
    print("%d seances, %s -> %s"
          % (len({t["jour"] for t in lot}),
             min(t["jour"] for t in lot), max(t["jour"] for t in lot)))

    cel = {}
    for t in lot:
        cel.setdefault((t["matin"], t["flux"]), []).append(t["pnl"])

    print()
    print("=" * 78)
    print("  1. table 2x2 -- matin en ligne, flux en colonne")
    print("=" * 78)
    print("%-16s %22s %22s" % ("", "flux AVEC", "flux CONTRE"))
    print("-" * 78)
    for m in ("AVEC", "CONTRE"):
        bouts = []
        for f in ("AVEC", "CONTRE"):
            g = cel.get((m, f), [])
            bouts.append("%22s" % ("-" if not g else "%d tk  %+8.2f" % (len(g), moy(g))))
        print("%-16s %s" % ("matin " + m, " ".join(bouts)))
    print("-" * 78)
    petites = [k for k in [("AVEC", "AVEC"), ("AVEC", "CONTRE"),
                           ("CONTRE", "AVEC"), ("CONTRE", "CONTRE")]
               if len(cel.get(k, [])) < 40]
    if petites:
        print("/!\\ cases peu remplies : %s"
              % ", ".join("matin %s / flux %s" % k for k in petites))
        print("    les deux variables sont liees : la stratification perdra")
        print("    de la puissance, lis les p avec prudence.")
    else:
        print("Les quatre cases sont remplies : les deux variables ne sont pas")
        print("redondantes, la stratification ci-dessous est interpretable.")

    print()
    print("=" * 78)
    print("  2. l effet du MATIN subsiste-t-il A FLUX CONSTANT ?")
    print("=" * 78)
    for f in ("AVEC", "CONTRE"):
        a = cel.get(("AVEC", f), [])
        c = cel.get(("CONTRE", f), [])
        e, p = t_deux(a, c)
        print("  chez les tickets flux %-7s : ecart %s  p=%s   (n=%d / %d)"
              % (f, "%+7.2f" % e if e is not None else "   -   ",
                 "%.3f" % p if p is not None else "-", len(a), len(c)))

    print()
    print("=" * 78)
    print("  3. l effet du FLUX subsiste-t-il A MATIN CONSTANT ?")
    print("=" * 78)
    for m in ("AVEC", "CONTRE"):
        a = cel.get((m, "CONTRE"), [])      # contre-flux = le cote suppose rentable
        c = cel.get((m, "AVEC"), [])
        e, p = t_deux(a, c)
        print("  chez les tickets matin %-7s : ecart %s  p=%s   (n=%d / %d)"
              % (m, "%+7.2f" % e if e is not None else "   -   ",
                 "%.3f" % p if p is not None else "-", len(a), len(c)))

    print()
    print("=" * 78)
    print("  lecture")
    print("=" * 78)
    print("Section 2 : si l ecart du matin tient dans LES DEUX strates de flux,")
    print("les deux effets sont independants et s ajoutent -- deux decouvertes.")
    print("S il ne tient que dans une strate, c est le flux qui portait tout.")
    print()
    print("Section 3 : meme raisonnement en sens inverse. Ecart positif =")
    print("aller contre le flux rapporte, ce qu on avait mesure separement.")
    print()
    print("Attention : ces quatre cases viennent des memes 9 seances que")
    print("l effet lui-meme. Rien n est prouve ici, on ne fait que verifier")
    print("qu on ne compte pas deux fois la meme chose avant de geler.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
