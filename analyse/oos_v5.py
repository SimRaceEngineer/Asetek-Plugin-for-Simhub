# -*- coding: utf-8 -*-
"""
oos_v5.py -- gel puis verdict hors echantillon des regles v5

  python oos_v5.py --geler      # aujourd hui
  python oos_v5.py --verdict    # vers le 1er septembre

DEPENDANCE PARTICULIERE A CE GEL, A NE PAS OUBLIER
    La direction de la matinee vient de profil_jour.csv, qui est un
    INSTANTANE : il ne contient que les seances presentes au moment ou
    profil_jour.py a tourne. Pour le verdict de septembre il faudra donc
    RELANCER profil_jour.py d abord, sinon les nouvelles seances n auront
    pas de matin, tomberont en fail-open, et le verdict portera sur un
    corpus vide sans le dire. Le script le verifie et refuse de conclure
    si la couverture est trop faible.
"""
import argparse, datetime as dt, hashlib, io, json, math, os, sys
import regles_gelees_v5 as R

CSV = "profil_jour.csv"
JOIN = os.path.join("docs", "churn_trades", "join_context.jsonl")
NOMS = ["churn_trades_archive.jsonl", "churn_trades.jsonl"]
DOSSIERS = [os.path.join("docs", "churn_trades"), r"docs\churn_trades",
            r"C:\ScalpExport\docs\churn_trades"]
FR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regles_gelees_v5.py")
DEBUT_REGIME = "2026-07-21"          # debut du corpus msitrident1 recupere
COUV_MIN = 50.0                      # % de tickets devant avoir un matin

ALIAS = {"US100": "NAS100", "NAS100": "NAS100", "US500": "SPX500",
         "SPX500": "SPX500", "US30": "US30", "DJ30": "US30"}
ACHAT = ("BUY", "ACHAT", "LONG", "B")
VENTE = ("SELL", "VENTE", "SHORT", "S")


def empreinte(p):
    h = hashlib.sha256()
    h.update(open(p, "rb").read())
    return h.hexdigest()


def sources(exp):
    if exp:
        return exp
    for d in DOSSIERS:
        t = [os.path.join(d, n) for n in NOMS if os.path.isfile(os.path.join(d, n))]
        if t:
            return t
    print("Aucun churn_trades*.jsonl trouve. Utilise --fichier.")
    sys.exit(1)


def lire_matin():
    if not os.path.isfile(CSV):
        print("introuvable : %s" % CSV)
        print("lance profil_jour.py AVANT oos_v5.py -- sans lui, aucun ticket")
        print("n a de direction du matin et le verdict serait vide.")
        sys.exit(1)
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
    if out:
        js = sorted({k[0] for k in out})
        print("profil_jour.csv : %d couples jour/actif, %s -> %s"
              % (len(out), js[0], js[-1]))
    return out


def lire_flux():
    out = {}
    if not os.path.isfile(JOIN):
        print("/!\\ %s absent : Y2 et Y3 seront inertes (fail-open)." % JOIN)
        return out
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
    return out


def charger(chemins, matin, flux):
    par = {}
    for ch in chemins:
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
            try:
                heure = int(ts[11:13])
            except ValueError:
                continue
            b = (o.get("asset") or "").strip().upper()
            asset = ALIAS.get(b, b)
            s = (o.get("dir") or "").strip().upper()
            sens = "UP" if s in ACHAT else ("DOWN" if s in VENTE else "")
            am = matin.get((ts[:10], asset))
            acc = ""
            if am and sens:
                acc = "AVEC" if sens == am else "CONTRE"
            par[tk] = {"ts": ts, "jour": ts[:10], "heure": heure, "asset": asset,
                       "dir": s, "pnl": float(pnl), "ticket": tk,
                       "accord_matin": acc, "contra": flux.get(tk, "")}
    return list(par.values())


def stats(lot):
    n = len(lot)
    if n == 0:
        return {"n": 0, "total": 0.0, "moy": 0.0, "et": 0.0, "sem": 0.0}
    t = sum(x["pnl"] for x in lot)
    m = t / n
    et = 0.0
    if n > 1:
        et = math.sqrt(sum((x["pnl"] - m) ** 2 for x in lot) / (n - 1))
    return {"n": n, "total": t, "moy": m, "et": et,
            "sem": et / math.sqrt(n) if n else 0.0}


def couverture(lot, champs):
    if not champs:
        return 100.0
    ok = sum(1 for s in lot if all(s.get(c) not in (None, "") for c in champs))
    return 100.0 * ok / max(1, len(lot))


def par_seance(lot, fn):
    """Ecart a l unite seance : une observation par journee. Correction
    etablie de longue date -- les tickets d une meme journee sont correles."""
    d = {}
    for s in lot:
        e = d.setdefault(s["jour"], {"g": [], "r": []})
        e["g" if fn(s) else "r"].append(s["pnl"])
    p = [(sum(v["g"]) / len(v["g"]), sum(v["r"]) / len(v["r"]))
         for v in d.values() if len(v["g"]) >= 3 and len(v["r"]) >= 3]
    if len(p) < 5:
        return None, None, len(p)
    dd = [a - b for a, b in p]
    m = sum(dd) / len(dd)
    sd = math.sqrt(sum((x - m) ** 2 for x in dd) / (len(dd) - 1)) if len(dd) > 1 else 0.0
    se = sd / math.sqrt(len(dd)) if sd else 0.0
    pv = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(m / se) / math.sqrt(2.0)))) if se else None
    return m, pv, len(p)


def heure_egale(lot, fn):
    """Centrage du P&L sur la tranche horaire. Verifie sur donnees
    fabriquees : un effet purement horaire sort p=0,002 a l unite seance
    et disparait ici. La correction par seance ne suffit PAS."""
    ref = {}
    for s in lot:
        ref.setdefault(s["heure"], []).append(s["pnl"])
    ref = dict((h, sum(v) / len(v)) for h, v in ref.items())
    g = [s["pnl"] - ref[s["heure"]] for s in lot if fn(s)]
    r = [s["pnl"] - ref[s["heure"]] for s in lot if not fn(s)]
    if len(g) < 20 or len(r) < 20:
        return None, None

    def mo(x):
        return sum(x) / float(len(x))

    def sd(x):
        m = mo(x)
        return math.sqrt(sum((y - m) ** 2 for y in x) / (len(x) - 1))
    e = mo(g) - mo(r)
    se = math.sqrt(sd(g) ** 2 / len(g) + sd(r) ** 2 / len(r))
    pv = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(e / se) / math.sqrt(2.0)))) if se else None
    return e, pv


def tableau(lot, titre):
    print()
    print("=" * 96)
    print("  " + titre)
    print("=" * 96)
    ref = stats(lot)
    print("%-4s %-28s %6s %10s %9s %9s %6s %9s %9s"
          % ("", "regle", "N", "PnL", "EUR/tk", "ecart", "couv.", "p seance", "p heure"))
    print("-" * 96)
    res = {}
    for code, lib, fn, champs in R.REGLES:
        g = [s for s in lot if fn(s)]
        st = stats(g)
        cv = couverture(lot, champs)
        ms, ps, ns = par_seance(lot, fn)
        eh, ph = heure_egale(lot, fn)
        res[code] = {"libelle": lib, "n": st["n"], "total": st["total"],
                     "moy": st["moy"], "et": st["et"], "couverture": cv,
                     "ecart_seance": ms, "p_seance": ps, "n_seances": ns,
                     "ecart_heure": eh, "p_heure": ph}
        print("%-4s %-28s %6d %10.2f %9.2f %+9.2f %5.0f%% %9s %9s"
              % (code, lib, st["n"], st["total"], st["moy"], st["moy"] - ref["moy"], cv,
                 "%.3f" % ps if ps is not None else "-",
                 "%.3f" % ph if ph is not None else "-"))
    print("-" * 96)
    print("p seance = ecart a l unite journee. p heure = apres centrage horaire.")
    print("Une regle n est credible que si LES DEUX sont petits.")
    inertes = [c for c in res if c != "Y0" and res[c]["n"] == ref["n"]]
    if inertes:
        print("INERTES (n excluent rien) : %s" % ", ".join(sorted(inertes)))
    return res, ref


def verif_couverture(lot):
    cv = couverture(lot, ["accord_matin"])
    print("couverture 'direction du matin' : %.0f%% des tickets" % cv)
    if cv < COUV_MIN:
        print()
        print("*** COUVERTURE INSUFFISANTE ***")
        print("Moins de %.0f%% des tickets ont une direction de matinee." % COUV_MIN)
        print("Cause quasi certaine : profil_jour.csv ne couvre pas la periode.")
        print("RELANCE profil_jour.py, puis relance ce script.")
        return False
    return True


def geler(a):
    matin, flux = lire_matin(), lire_flux()
    lot = [s for s in charger(sources(a.fichier), matin, flux)
           if s["jour"] >= DEBUT_REGIME]
    if not lot:
        print("Aucun signal depuis %s." % DEBUT_REGIME)
        return 1
    if not verif_couverture(lot):
        return 1
    jours = sorted({s["jour"] for s in lot})
    date_gel = a.date or dt.date.today().isoformat()
    ins = [s for s in lot if s["jour"] <= date_gel]

    print("regles_gelees_v5.py v%s" % R.VERSION)
    print("SHA-256  : %s" % empreinte(FR))
    print("date gel : %s" % date_gel)
    print("in-sample: %d tickets, %d seances, %s -> %s"
          % (len(ins), len({s["jour"] for s in ins}), jours[0], jours[-1]))

    res, ref = tableau(ins, "IN-SAMPLE (ne prouve rien : la regle en est issue)")

    enr = {"version": R.VERSION, "sha256": empreinte(FR), "date_gel": date_gel,
           "debut_regime": DEBUT_REGIME, "n_insample": len(ins),
           "seances_insample": len({s["jour"] for s in ins}),
           "et_pnl": ref["et"], "regles": res, "origine": R.ORIGINE}
    out = a.sortie or ("gel_v5_%s.json" % date_gel)
    io.open(out, "w", encoding="utf-8").write(json.dumps(enr, indent=2, ensure_ascii=False))
    print()
    print("Gel ecrit : %s" % out)
    print("NE PLUS TOUCHER A regles_gelees_v5.py.")
    print()
    print("RAPPEL POUR SEPTEMBRE : relancer profil_jour.py AVANT le verdict,")
    print("sinon les nouvelles seances n auront pas de direction de matinee.")
    return 0


def verdict(a):
    g = a.gel or (sorted(f for f in os.listdir(".")
                         if f.startswith("gel_v5_") and f.endswith(".json")) or [None])[-1]
    if not g:
        print("Aucun gel_v5_*.json. Lance d abord --geler.")
        return 1
    gel = json.load(io.open(g, encoding="utf-8-sig"))
    print("gel du %s (%s)" % (gel["date_gel"], g))

    if empreinte(FR) != gel["sha256"]:
        print()
        print("*** regles_gelees_v5.py A CHANGE DEPUIS LE GEL ***")
        print("attendu %s" % gel["sha256"])
        print("actuel  %s" % empreinte(FR))
        print("Verdict INVALIDE : les regles ont ete ajustees apres coup.")
        if not a.force:
            return 1

    matin, flux = lire_matin(), lire_flux()
    lot = [s for s in charger(sources(a.fichier), matin, flux)
           if s["jour"] > gel["date_gel"]]
    if not lot:
        print("Aucune donnee posterieure au gel.")
        return 1
    print("hors echantillon : %d tickets, %d seances"
          % (len(lot), len({s["jour"] for s in lot})))
    if not verif_couverture(lot):
        return 1

    res, ref = tableau(lot, "HORS ECHANTILLON -- le seul tableau qui compte")

    print()
    print("%-4s %-26s %9s %9s %9s %9s %s"
          % ("", "regle", "in-samp", "oos", "p seance", "p heure", "signe"))
    print("-" * 96)
    ref_in = gel["regles"]["Y0"]["moy"]
    for code, lib, fn, champs in R.REGLES:
        if code == "Y0":
            continue
        e_in = gel["regles"].get(code, {}).get("moy", 0.0) - ref_in
        e_oo = res[code]["moy"] - ref["moy"]
        sgn = "inerte" if e_in == 0 else ("TENU" if (e_in > 0) == (e_oo > 0) else "INVERSE")
        print("%-4s %-26s %+9.2f %+9.2f %9s %9s %s"
              % (code, lib, e_in, e_oo,
                 "%.3f" % res[code]["p_seance"] if res[code]["p_seance"] is not None else "-",
                 "%.3f" % res[code]["p_heure"] if res[code]["p_heure"] is not None else "-",
                 sgn))
    print("-" * 96)
    print()
    print("'TENU' = le signe se reproduit, PAS que l effet est prouve.")
    print("Y6 est le CONTROLE NEGATIF. Son p sera TOUJOURS identique a celui")
    print("de Y1 : c est son complement, la partition testee est la meme. Ce")
    print("qu il faut regarder est son ECART, qui doit etre le miroir de Y1.")
    print("Si Y1 sort positif et Y6 positif aussi, le harnais mesure autre")
    print("chose que ce qu on croit et tout le tableau est a jeter.")
    if len({s["jour"] for s in lot}) < 15:
        print("/!\\ moins de 15 seances : resultat fragile quel qu il soit.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geler", action="store_true")
    ap.add_argument("--verdict", action="store_true")
    ap.add_argument("--fichier", nargs="+", default=None)
    ap.add_argument("--gel", default=None)
    ap.add_argument("--sortie", default=None)
    ap.add_argument("--date", default=None)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.geler:
        return geler(a)
    if a.verdict:
        return verdict(a)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
