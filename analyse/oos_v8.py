# -*- coding: utf-8 -*-
"""
oos_v8.py -- gel puis verdict hors echantillon des regles v8

  python oos_v8.py --geler      # aujourd hui
  python oos_v8.py --verdict    # vers le 1er septembre

DEPENDANCE PARTICULIERE A CE GEL, A NE PAS OUBLIER
    L amplitude de la premiere heure vient de h1_seance.csv, qui est un
    INSTANTANE : il ne contient que les seances presentes au moment ou
    h1_seance.py a tourne. Pour le verdict de septembre il faudra donc
    RELANCER h1_seance.py d abord, sinon les nouvelles seances n auront pas
    d amplitude, tomberont en fail-open, et le verdict portera sur un corpus
    vide sans le dire. Le script le verifie et refuse de conclure si la
    couverture est trop faible.

    Ce gel-ci ne depend QUE de h1_seance.csv. Pas de profil_jour.csv, pas
    d orderflow : aucune regle de v8 ne regarde la direction, et c est
    volontaire.

CE QUE CE HARNAIS AJOUTE AUX PRECEDENTS
    Un quantile glissant plutot qu un simple au-dessus/en-dessous de la
    mediane. Il faut donc que le meme champ serve les trois seuils du gel
    (0,70 pour U1 et U4, 0,50 pour U3, 0,30 pour U6) : le calcul est fait une
    fois, les regles ne font que le comparer.

    Et un TEST DE SIGNE a cote du test de magnitude. C est la lecon directe
    de v5_periode.py : au gel V5, les deux ne disaient pas la meme chose, et
    c est le signe qui avait raison.
"""
import argparse, datetime as dt, hashlib, io, json, math, os, sys
import regles_gelees_v8 as R

CSV = "h1_seance.csv"
NOMS = ["churn_trades_archive.jsonl", "churn_trades.jsonl"]
DOSSIERS = [os.path.join("docs", "churn_trades"), r"docs\churn_trades",
            r"C:\ScalpExport\docs\churn_trades"]
FR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regles_gelees_v8.py")
DEBUT_REGIME = "2026-07-21"          # debut du corpus msitrident1 recupere
COUV_MIN = 50.0                      # % de tickets devant etre classes

ALIAS = {"US100": "NAS100", "NAS100": "NAS100", "US500": "SPX500",
         "SPX500": "SPX500", "US30": "US30", "DJ30": "US30"}


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


def lire_quantiles():
    """Quantile glissant de la premiere heure, par seance et par actif.

    q = part des FENETRE_Q seances PRECEDENTES du meme actif dont la premiere
    heure a ete STRICTEMENT moins ample que celle du jour. Le jour courant
    n y entre pas, aucun jour futur non plus.

    C est la correction principale apportee a la proposition d origine, qui
    comparait l amplitude du jour a la distribution de TOUT l echantillon.
    Cela revenait a savoir aujourd hui ce que seront les amplitudes des mois
    a venir -- le defaut exact que le gel V7 reproche a regime_jour.py.
    """
    if not os.path.isfile(CSV):
        print("introuvable : %s" % CSV)
        print("lance h1_seance.py AVANT oos_v8.py -- sans lui aucun ticket n a")
        print("de quantile de premiere heure et le verdict serait vide.")
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
            h = [x[1] for x in s[max(0, i - R.FENETRE_Q):i]]
            if len(h) < R.MIN_HIST:
                continue
            out[(j, a)] = sum(1 for x in h if x < r) / float(len(h))
    if out:
        js = sorted({k[0] for k in out})
        print("h1_seance.csv : %d couples jour/actif classes, %s -> %s"
              % (len(out), js[0], js[-1]))
        for nom, seuil, sens in (("tercile haut", R.Q_TERCILE, "haut"),
                                 ("moitie haute (V6)", R.Q_MEDIANE, "haut"),
                                 ("tercile bas", R.Q_BAS, "bas")):
            n = (sum(1 for v in out.values() if v >= seuil) if sens == "haut"
                 else sum(1 for v in out.values() if v <= seuil))
            print("  %-18s : %4d sur %d (%.0f%%)"
                  % (nom, n, len(out), 100.0 * n / len(out)))
        if sum(1 for v in out.values() if v >= R.Q_TERCILE) < 30:
            print("  /!\\ moins de 30 seances-actif dans le tercile haut. U1 et U4")
            print("      auront tres peu de puissance et leur verdict sera fragile,")
            print("      quel qu il soit.")
    return out


def charger(chemins, quant):
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
            q = quant.get((ts[:10], asset))
            par[tk] = {"ts": ts, "jour": ts[:10], "hm": ts[11:16], "heure": heure,
                       "asset": asset, "dir": (o.get("dir") or "").strip().upper(),
                       "pnl": float(pnl), "ticket": tk,
                       "h1_q": "" if q is None else q}
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


def _paires(lot, fn):
    d = {}
    for s in lot:
        e = d.setdefault(s["jour"], {"g": [], "r": []})
        e["g" if fn(s) else "r"].append(s["pnl"])
    return [sum(v["g"]) / len(v["g"]) - sum(v["r"]) / len(v["r"])
            for v in d.values() if len(v["g"]) >= 3 and len(v["r"]) >= 3]


def par_seance(lot, fn):
    """Ecart a l unite seance : une observation par journee. Correction
    etablie de longue date -- les tickets d une meme journee sont correles."""
    dd = _paires(lot, fn)
    if len(dd) < 5:
        return None, None, len(dd)
    m = sum(dd) / len(dd)
    sd = math.sqrt(sum((x - m) ** 2 for x in dd) / (len(dd) - 1)) if len(dd) > 1 else 0.0
    se = sd / math.sqrt(len(dd)) if sd else 0.0
    pv = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(m / se) / math.sqrt(2.0)))) if se else None
    return m, pv, len(dd)


def signe_seance(lot, fn):
    """Test de SIGNE, a cote du test de magnitude.

    Ajoute a ce gel-ci parce que v5_periode.py a montre ce que coute son
    absence : au gel V5, le p=0,008 a l unite seance venait d un test sur les
    magnitudes ecrase par deux journees, et le test de signe seul donnait 7
    sur 9, soit p environ 0,18 -- non significatif. On ne veut plus lire un
    ecart sans savoir combien de seances vont dans son sens.
    """
    dd = _paires(lot, fn)
    n = len(dd)
    if n < 5:
        return None, None, n
    k = sum(1 for x in dd if x > 0)
    c = [1]
    for _ in range(n):
        c = [1] + [c[j] + c[j + 1] for j in range(len(c) - 1)] + [1]
    tot = float(sum(c))
    ext = sum(c[i] for i in range(n + 1) if abs(i - n / 2.0) >= abs(k - n / 2.0))
    return k, min(1.0, ext / tot), n


def heure_egale(lot, fn):
    """Centrage du P&L sur la tranche horaire. Verifie sur donnees
    fabriquees : un effet purement horaire sort p=0,002 a l unite seance
    et disparait ici. La correction par seance ne suffit PAS.

    Sur ce gel-ci le centrage est PARTICULIEREMENT important : toutes les
    regles sauf U0 contiennent un filtre horaire, donc l heure est le
    confondant evident. U2 et U5 sont la pour la meme raison.
    """
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
    print("=" * 108)
    print("  " + titre)
    print("=" * 108)
    ref = stats(lot)
    print("%-4s %-32s %6s %10s %9s %9s %6s %9s %9s %9s"
          % ("", "regle", "N", "PnL", "EUR/tk", "ecart", "couv.",
             "p seance", "p signe", "p heure"))
    print("-" * 108)
    res = {}
    for code, lib, fn, champs in R.REGLES:
        st = stats([s for s in lot if fn(s)])
        cv = couverture(lot, champs)
        ms, ps, ns = par_seance(lot, fn)
        k, psg, _ = signe_seance(lot, fn)
        eh, ph = heure_egale(lot, fn)
        res[code] = {"libelle": lib, "n": st["n"], "total": st["total"],
                     "moy": st["moy"], "et": st["et"], "couverture": cv,
                     "ecart_seance": ms, "p_seance": ps, "n_seances": ns,
                     "seances_positives": k, "p_signe": psg,
                     "ecart_heure": eh, "p_heure": ph}
        print("%-4s %-32s %6d %10.2f %9.2f %+9.2f %5.0f%% %9s %9s %9s"
              % (code, lib, st["n"], st["total"], st["moy"], st["moy"] - ref["moy"], cv,
                 "%.3f" % ps if ps is not None else "-",
                 "%.3f" % psg if psg is not None else "-",
                 "%.3f" % ph if ph is not None else "-"))
    print("-" * 108)
    print("p seance = magnitude a l unite journee. p signe = combien de journees")
    print("vont dans le sens de l ecart, sans regarder son ampleur. p heure =")
    print("apres centrage horaire. Une regle n est credible que si LES TROIS")
    print("sont petits -- au gel V5, magnitude et signe ne disaient pas la meme")
    print("chose, et c est le signe qui avait raison.")
    inertes = [c for c in res if c != "U0" and res[c]["n"] == ref["n"]]
    if inertes:
        print("INERTES (n excluent rien) : %s" % ", ".join(sorted(inertes)))
    return res, ref


def verif_couverture(lot):
    cv = couverture(lot, ["h1_q"])
    print("couverture 'quantile premiere heure' : %.0f%% des tickets" % cv)
    if cv < COUV_MIN:
        print()
        print("*** COUVERTURE INSUFFISANTE ***")
        print("Moins de %.0f%% des tickets ont un quantile de premiere heure." % COUV_MIN)
        print("Cause quasi certaine : h1_seance.csv ne couvre pas la periode.")
        print("RELANCE h1_seance.py, puis ce script.")
        return False
    return True


def geler(a):
    quant = lire_quantiles()
    lot = [s for s in charger(sources(a.fichier), quant) if s["jour"] >= DEBUT_REGIME]
    if not lot:
        print("Aucun signal depuis %s." % DEBUT_REGIME)
        return 1
    if not verif_couverture(lot):
        return 1
    jours = sorted({s["jour"] for s in lot})
    date_gel = a.date or dt.date.today().isoformat()
    ins = [s for s in lot if s["jour"] <= date_gel]

    print("regles_gelees_v8.py v%s" % R.VERSION)
    print("SHA-256  : %s" % empreinte(FR))
    print("date gel : %s" % date_gel)
    print("in-sample: %d tickets, %d seances, %s -> %s"
          % (len(ins), len({s["jour"] for s in ins}), jours[0], jours[-1]))

    res, ref = tableau(ins, "IN-SAMPLE (ne prouve rien, et ici moins encore)")
    print()
    print("Ce tableau in-sample compte MOINS que pour les gels precedents : le")
    print("seuil de U1 n a pas ete choisi sur ces donnees, il vient d une")
    print("proposition exterieure. Ce qu on lit ici n est donc meme pas un")
    print("resultat surajuste, c est une simple description avant l epreuve.")

    enr = {"version": R.VERSION, "sha256": empreinte(FR), "date_gel": date_gel,
           "debut_regime": DEBUT_REGIME, "n_insample": len(ins),
           "seances_insample": len({s["jour"] for s in ins}),
           "et_pnl": ref["et"], "regles": res, "origine": R.ORIGINE,
           "seuils": {"tercile": R.Q_TERCILE, "mediane": R.Q_MEDIANE,
                      "bas": R.Q_BAS, "fenetre": R.FENETRE_Q,
                      "fin_h1": R.FIN_H1, "fin_fenetre": R.FIN_FENETRE}}
    out = a.sortie or ("gel_v8_%s.json" % date_gel)
    io.open(out, "w", encoding="utf-8").write(json.dumps(enr, indent=2, ensure_ascii=False))
    print()
    print("Gel ecrit : %s" % out)
    print("NE PLUS TOUCHER A regles_gelees_v8.py.")
    print()
    print("RAPPEL POUR SEPTEMBRE : relancer h1_seance.py AVANT, sinon les")
    print("nouvelles seances tomberont toutes en fail-open.")
    return 0


def verdict(a):
    g = a.gel or (sorted(f for f in os.listdir(".")
                         if f.startswith("gel_v8_") and f.endswith(".json")) or [None])[-1]
    if not g:
        print("Aucun gel_v8_*.json. Lance d abord --geler.")
        return 1
    gel = json.load(io.open(g, encoding="utf-8-sig"))
    print("gel du %s (%s)" % (gel["date_gel"], g))

    if empreinte(FR) != gel["sha256"]:
        print()
        print("*** regles_gelees_v8.py A CHANGE DEPUIS LE GEL ***")
        print("attendu %s" % gel["sha256"])
        print("actuel  %s" % empreinte(FR))
        print("Verdict INVALIDE : les regles ont ete ajustees apres coup.")
        if not a.force:
            return 1

    quant = lire_quantiles()
    lot = [s for s in charger(sources(a.fichier), quant) if s["jour"] > gel["date_gel"]]
    if not lot:
        print("Aucune donnee posterieure au gel.")
        return 1
    print("hors echantillon : %d tickets, %d seances"
          % (len(lot), len({s["jour"] for s in lot})))
    if not verif_couverture(lot):
        return 1

    res, ref = tableau(lot, "HORS ECHANTILLON -- le seul tableau qui compte")

    print()
    print("%-4s %-32s %9s %9s %9s %9s %9s %s"
          % ("", "regle", "in-samp", "oos", "p seance", "p signe", "p heure", "signe"))
    print("-" * 108)
    ref_in = gel["regles"]["U0"]["moy"]
    for code, lib, fn, champs in R.REGLES:
        if code == "U0":
            continue
        e_in = gel["regles"].get(code, {}).get("moy", 0.0) - ref_in
        e_oo = res[code]["moy"] - ref["moy"]
        sgn = "inerte" if e_in == 0 else ("TENU" if (e_in > 0) == (e_oo > 0) else "INVERSE")
        print("%-4s %-32s %+9.2f %+9.2f %9s %9s %9s %s"
              % (code, lib, e_in, e_oo,
                 "%.3f" % res[code]["p_seance"] if res[code]["p_seance"] is not None else "-",
                 "%.3f" % res[code]["p_signe"] if res[code]["p_signe"] is not None else "-",
                 "%.3f" % res[code]["p_heure"] if res[code]["p_heure"] is not None else "-",
                 sgn))
    print("-" * 108)
    print()
    print("'TENU' = le signe se reproduit, PAS que l effet est prouve.")
    print()
    print("LA LECTURE DE CE GEL TIENT EN TROIS COMPARAISONS, DANS CET ORDRE :")
    print()
    print("  U1 contre U2 -- la taille de la premiere heure apporte-t-elle quoi")
    print("      que ce soit PAR-DESSUS l heure tardive ? Si non, tout le reste")
    print("      est sans objet : c est l heure qui portait l effet, comme pour")
    print("      l hypothese du seuil d excursion.")
    print()
    print("  U1 contre U3 -- serrer au tercile bat-il la mediane du gel V6 ? Si")
    print("      U1 ne bat pas U3, la proposition ne fait que reduire le volume")
    print("      et n apporte rien qu on ne savait deja depuis le 09/08.")
    print()
    print("  U4 contre U5 -- la borne de 21h00 gagne-t-elle par le tercile ou")
    print("      par la simple exclusion de la fin de seance ?")
    print()
    print("U6 est le controle negatif. Il n est PAS le complement de U1 -- le")
    print("tiers du milieu n est dans ni l un ni l autre -- donc son p se lit")
    print("normalement, contrairement aux miroirs W1/W2 du gel V7.")
    print("Si U6 ne s effondre pas alors que U1 tient, le harnais mesure autre")
    print("chose que ce qu on croit et tout le tableau est a jeter.")
    if len({s["jour"] for s in lot}) < 15:
        print()
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
