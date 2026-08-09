# -*- coding: utf-8 -*-
"""
oos_v7.py -- gel puis verdict hors echantillon des regles v7

  python oos_v7.py --geler      # aujourd hui
  python oos_v7.py --verdict    # vers le 1er septembre

DEPENDANCE PARTICULIERE A CE GEL, A NE PAS OUBLIER
    L amplitude de la premiere heure vient de h1_seance.csv, qui est un
    INSTANTANE : il ne contient que les seances presentes au moment ou
    h1_seance.py a tourne. Pour le verdict de septembre il faudra donc
    RELANCER h1_seance.py d abord, sinon les nouvelles seances n auront
    pas d amplitude, tomberont en fail-open, et le verdict portera sur un
    corpus vide sans le dire. Le script le verifie et refuse de conclure
    si la couverture est trop faible.

    Le regime d amplitude vient de profil_jour.csv, meme remarque.
    RELANCER h1_seance.py ET profil_jour.py AVANT le verdict.
"""
import argparse, datetime as dt, hashlib, io, json, math, os, sys
import regles_gelees_v7 as R

CSV = "h1_seance.csv"
JOIN = os.path.join("docs", "churn_trades", "join_context.jsonl")
NOMS = ["churn_trades_archive.jsonl", "churn_trades.jsonl"]
DOSSIERS = [os.path.join("docs", "churn_trades"), r"docs\churn_trades",
            r"C:\ScalpExport\docs\churn_trades"]
FR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regles_gelees_v7.py")
DEBUT_REGIME = "2026-07-21"          # debut du corpus msitrident1 recupere
COUV_MIN = 50.0                      # % de tickets devant etre classes

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


FENETRE_MED = 20          # seances servant a la mediane glissante
MIN_HIST = 10             # en dessous, on ne classe pas : fail-open
MATIN = "profil_jour.csv"


def _lire_csv(chemin):
    lg = [l.rstrip("\n") for l in io.open(chemin, encoding="utf-8-sig") if l.strip()]
    sep = ";" if lg[0].count(";") >= lg[0].count(",") else ","
    ent = [c.strip() for c in lg[0].split(sep)]
    out = []
    for l in lg[1:]:
        c = l.split(sep)
        if len(c) < len(ent):
            c += [""] * (len(ent) - len(c))
        out.append(dict(zip(ent, c)))
    return out


def _med(xs):
    xs = sorted(xs)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def lire_h1():
    """Classe chaque seance en grande ou petite premiere heure, contre la
    MEDIANE GLISSANTE des %d seances precedentes du meme actif, JOUR COURANT
    EXCLU. Un seuil calcule sur tout l echantillon serait du recul deguise :
    on saurait aujourd hui ce que seront les amplitudes des mois a venir.""" % FENETRE_MED
    if not os.path.isfile(CSV):
        print("introuvable : %s" % CSV)
        print("lance h1_seance.py AVANT oos_v7.py -- sans lui aucun ticket n a")
        print("d amplitude de premiere heure et le verdict serait vide.")
        sys.exit(1)
    par = {}
    for d in _lire_csv(CSV):
        j, a = (d.get("jour") or "").strip(), (d.get("asset") or "").strip()
        try:
            r = float((d.get("h1_range") or "").replace(",", "."))
        except ValueError:
            continue
        if j and a and r > 0:
            par.setdefault(a, []).append((j, r))
    out = {}
    for a in par:
        s = sorted(par[a])
        for i, (j, r) in enumerate(s):
            h = [x[1] for x in s[max(0, i - FENETRE_MED):i]]
            if len(h) < MIN_HIST:
                continue
            out[(j, a)] = "GRANDE" if r > _med(h) else "PETITE"
    if out:
        js = sorted({k[0] for k in out})
        print("h1_seance.csv : %d couples jour/actif classes, %s -> %s"
              % (len(out), js[0], js[-1]))
        n_oui = sum(1 for v in out.values() if v == "GRANDE")
        print("  grandes premieres heures : %d sur %d (%.0f%%)"
              % (n_oui, len(out), 100.0 * n_oui / len(out)))
    return out


def lire_regime():
    """CALME / AGITE par seance et par actif, indicateur ENTIEREMENT CAUSAL.

    ind = amplitude moyenne des %d seances PRECEDENTES, divisee par la
    mediane des amplitudes de TOUTES les seances anterieures du meme actif
    (fenetre qui s elargit). CALME si le rapport est sous 1, AGITE sinon.

    Deux precautions qui manquaient a regime_jour.py :
      - le jour courant n entre ni dans la moyenne ni dans la mediane ;
      - le seuil vaut 1,0 par construction, ce n est pas un parametre
        ajuste. Couper a la mediane de l echantillon complet, comme on
        l avait fait, revenait a connaitre l avenir.
    """ % FENETRE_MED
    if not os.path.isfile(MATIN):
        print("/!\\ %s absent : W1, W2, W4 et W5 tomberont en fail-open." % MATIN)
        return {}
    par = {}
    for d in _lire_csv(MATIN):
        j, a = (d.get("jour") or "").strip(), (d.get("asset") or "").strip()
        try:
            r = float((d.get("range") or "").replace(",", "."))
        except ValueError:
            continue
        if j and a and r > 0:
            par.setdefault(a, []).append((j, r))
    out = {}
    for a in par:
        srt = sorted(par[a])
        for i, (j, r) in enumerate(srt):
            recent = [x[1] for x in srt[max(0, i - FENETRE_MED):i]]
            hist = [x[1] for x in srt[:i]]
            if len(recent) < FENETRE_MED or len(hist) < MIN_HIST * 2:
                continue
            base = _med(hist)
            if not base:
                continue
            out[(j, a)] = "CALME" if (sum(recent) / len(recent)) < base else "AGITE"
    if out:
        js = sorted({k[0] for k in out})
        n_c = sum(1 for v in out.values() if v == "CALME")
        print("profil_jour.csv : %d couples classes en regime, %s -> %s"
              % (len(out), js[0], js[-1]))
        part = 100.0 * n_c / len(out)
        print("  regimes CALME : %d sur %d (%.0f%%)" % (n_c, len(out), part))
        if part < 25 or part > 75:
            print("  /!\\ partage tres desequilibre. Le seuil a 1,0 est fixe par")
            print("      construction et non ajuste, ce qui est voulu -- mais avec")
            print("      un cote aussi minoritaire, W1 et W2 auront peu de puissance")
            print("      et leur verdict de septembre sera fragile.")
    return out


def charger(chemins, h1, regime):
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
            par[tk] = {"ts": ts, "jour": ts[:10], "hm": ts[11:16], "heure": heure,
                       "asset": asset, "dir": s, "pnl": float(pnl), "ticket": tk,
                       "h1_taille": h1.get((ts[:10], asset), ""),
                       "regime_ampl": regime.get((ts[:10], asset), "")}
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
    inertes = [c for c in res if c != "W0" and res[c]["n"] == ref["n"]]
    if inertes:
        print("INERTES (n excluent rien) : %s" % ", ".join(sorted(inertes)))
    return res, ref


def verif_couverture(lot):
    cv = couverture(lot, ["h1_taille"])
    print("couverture 'amplitude premiere heure' : %.0f%% des tickets" % cv)
    if cv < COUV_MIN:
        print()
        print("*** COUVERTURE INSUFFISANTE ***")
        print("Moins de %.0f%% des tickets ont une amplitude de premiere heure." % COUV_MIN)
        print("Cause quasi certaine : h1_seance.csv ne couvre pas la periode.")
        print("RELANCE h1_seance.py (et profil_jour.py pour W4), puis ce script.")
        return False
    return True


def geler(a):
    h1, regime = lire_h1(), lire_regime()
    lot = [s for s in charger(sources(a.fichier), h1, regime)
           if s["jour"] >= DEBUT_REGIME]
    if not lot:
        print("Aucun signal depuis %s." % DEBUT_REGIME)
        return 1
    if not verif_couverture(lot):
        return 1
    jours = sorted({s["jour"] for s in lot})
    date_gel = a.date or dt.date.today().isoformat()
    ins = [s for s in lot if s["jour"] <= date_gel]

    print("regles_gelees_v7.py v%s" % R.VERSION)
    print("SHA-256  : %s" % empreinte(FR))
    print("date gel : %s" % date_gel)
    print("in-sample: %d tickets, %d seances, %s -> %s"
          % (len(ins), len({s["jour"] for s in ins}), jours[0], jours[-1]))

    res, ref = tableau(ins, "IN-SAMPLE (ne prouve rien : la regle en est issue)")

    enr = {"version": R.VERSION, "sha256": empreinte(FR), "date_gel": date_gel,
           "debut_regime": DEBUT_REGIME, "n_insample": len(ins),
           "seances_insample": len({s["jour"] for s in ins}),
           "et_pnl": ref["et"], "regles": res, "origine": R.ORIGINE}
    out = a.sortie or ("gel_v7_%s.json" % date_gel)
    io.open(out, "w", encoding="utf-8").write(json.dumps(enr, indent=2, ensure_ascii=False))
    print()
    print("Gel ecrit : %s" % out)
    print("NE PLUS TOUCHER A regles_gelees_v7.py.")
    print()
    print("RAPPEL POUR SEPTEMBRE : relancer h1_seance.py ET profil_jour.py AVANT,")
    print("sinon les nouvelles seances tomberont toutes en fail-open.")
    return 0


def verdict(a):
    g = a.gel or (sorted(f for f in os.listdir(".")
                         if f.startswith("gel_v7_") and f.endswith(".json")) or [None])[-1]
    if not g:
        print("Aucun gel_v7_*.json. Lance d abord --geler.")
        return 1
    gel = json.load(io.open(g, encoding="utf-8-sig"))
    print("gel du %s (%s)" % (gel["date_gel"], g))

    if empreinte(FR) != gel["sha256"]:
        print()
        print("*** regles_gelees_v7.py A CHANGE DEPUIS LE GEL ***")
        print("attendu %s" % gel["sha256"])
        print("actuel  %s" % empreinte(FR))
        print("Verdict INVALIDE : les regles ont ete ajustees apres coup.")
        if not a.force:
            return 1

    h1, regime = lire_h1(), lire_regime()
    lot = [s for s in charger(sources(a.fichier), h1, regime)
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
    ref_in = gel["regles"]["W0"]["moy"]
    for code, lib, fn, champs in R.REGLES:
        if code == "W0":
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
    print("W1 et W2 sont COMPLEMENTAIRES : leur p sera TOUJOURS identique,")
    print("la partition testee etant la meme. C est leur ECART qui les")
    print("distingue, jamais leur p. Celui des deux dont l ecart est positif")
    print("hors echantillon a raison, et l autre a tort -- c est tout l objet")
    print("de ce gel, qui fige une CONTRADICTION et non une hypothese.")
    print("Si les deux sortent positifs, le harnais mesure autre")
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
