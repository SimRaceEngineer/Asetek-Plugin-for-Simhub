# -*- coding: utf-8 -*-
"""
oos_v9.py -- gel puis verdict hors echantillon des regles v9

  python oos_v9.py --champs      # AVANT tout : quels champs sont lisibles
  python oos_v9.py --geler       # aujourd hui
  python oos_v9.py --verdict     # vers le 1er septembre

CE QUI CHANGE PAR RAPPORT AUX HUIT HARNAIS PRECEDENTS
    Les gels V5 a V8 lisaient churn_trades*.jsonl, ou tous les champs
    utiles etaient deja des colonnes. Le gel V9 lit l etat des RAILS fige a
    l entree, et cet etat n a pas de nom de champ connu depuis ce depot :
    le panel qui le produit (rails_trades_panel.py) vit sur le VPS et n est
    pas ici. On sait seulement, par l export du 10/08, le VOCABULAIRE des
    valeurs -- rails_pos BOTH>50 / BOTH<50 / STRADDLE, rsi_pos ABOVE /
    INSIDE / BELOW -- et qu il y a une entree par pas de temps.

    D ou le mode --champs, a lancer EN PREMIER sur le VPS. Il ouvre le
    fichier, dit quelles clefs il a reconnues, sur quelle proportion des
    enregistrements, et s arrete la. Si la couverture est mauvaise, c est
    le nom des champs qu il faut corriger ICI, dans CLEFS_* -- jamais dans
    regles_gelees_v9.py, qui est gele et dont l empreinte est verifiee.

    Cette separation est la meme qu au gel V8 : le quantile de premiere
    heure y etait calcule par le harnais, pas par les regles.

DEUX SECOURS SI LE NOM DES CHAMPS N EST PAS RECONNU
    1. Le biais et la position du RSI se REDUISENT a partir des nombres.
       Le panel les definit ainsi et pas autrement :
         biais bull = les deux rails > 50 · bear = les deux < 50 · sinon flat
         RSI ABOVE = au-dessus des deux rails · BELOW = sous les deux ·
         INSIDE = entre les deux
       Si l enregistrement porte les valeurs numeriques bull/bear/rsi, le
       harnais recalcule les etiquettes lui-meme. C est une reconstitution
       exacte de la definition du panel, pas une approximation.
    2. --champs liste les clefs les plus frequentes de l enregistrement
       pour qu on puisse completer CLEFS_* en une minute.

CE HARNAIS NE CONCLUT PAS SI LA COUVERTURE EST TROP FAIBLE
    Fail-open veut dire "on autorise", donc un champ absent ne vide pas une
    regle de selection : il la DILUE jusqu a la rendre identique a la
    reference. Une couverture basse ne produit donc pas une erreur visible,
    elle produit un tableau plat et rassurant. C est le piege propre a ce
    gel-ci, et la seule protection est de refuser de conclure.
"""
import argparse, datetime as dt, hashlib, io, json, math, os, sys
import regles_gelees_v9 as R

NOMS = ["rails_trades_archive.jsonl", "rails_trades.jsonl",
        "churn_trades_archive.jsonl", "churn_trades.jsonl"]
DOSSIERS = [os.path.join("docs", "rails_trades"), r"docs\rails_trades",
            os.path.join("docs", "churn_trades"), r"docs\churn_trades",
            r"C:\ScalpExport\docs\rails_trades",
            r"C:\ScalpExport\docs\churn_trades"]
FR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regles_gelees_v9.py")

DEBUT_REGIME = "2026-07-28"   # plancher : le panel rails ne remonte pas avant
COUV_MIN = 60.0               # % de tickets devant avoir M1 ET M5 classes
COUV_MIN_Y = 60.0             # idem pour M1, M15 et le verdict churn

TFS = ["M1", "M3", "M5", "M15"]

# ---------------------------------------------------------------------------
# Noms de champs candidats. C EST LE SEUL ENDROIT A CORRIGER si --champs
# annonce une couverture faible. Le fichier de regles reste intouchable.
# %s est remplace par le pas de temps, en minuscules puis en majuscules.
# ---------------------------------------------------------------------------
CLEFS_NICHE = ["rails", "rails_snapshot", "snap", "snapshot", "tf"]
CLEFS_POS = ["rails_pos_%s", "%s_rails_pos", "rails_%s_pos", "pos_%s",
             "railspos_%s", "biais_%s", "%s_biais"]
CLEFS_RSIPOS = ["rsi_pos_%s", "%s_rsi_pos", "rsi_%s_pos", "rsipos_%s"]
CLEFS_BULL = ["bull_%s", "%s_bull", "rails_bull_%s", "%s_rails_bull"]
CLEFS_BEAR = ["bear_%s", "%s_bear", "rails_bear_%s", "%s_rails_bear"]
CLEFS_RSI = ["rsi_%s", "%s_rsi", "rsi_val_%s"]
CLEFS_SENS = ["sens", "dir", "side", "type", "direction"]
CLEFS_CHURN = ["churn", "churn_entry", "churn_verdict", "verdict_churn",
               "churn_at_entry"]
CLEFS_TS = ["entry_ts", "ts", "open_time", "time"]
CLEFS_PNL = ["pnl_eur", "pnl", "profit_eur", "profit"]
CLEFS_TICKET = ["ticket", "id", "deal", "position"]

POS_VERS_BIAIS = {"BOTH>50": R.BULL, "BOTH<50": R.BEAR, "STRADDLE": R.FLAT,
                  ">50": R.BULL, "<50": R.BEAR, "BULL": R.BULL,
                  "BEAR": R.BEAR, "FLAT": R.FLAT}
RSIPOS_VALIDES = {"ABOVE": R.DESSUS, "INSIDE": R.DEDANS, "BELOW": R.SOUS,
                  "+": R.DESSUS, "=": R.DEDANS, "-": R.SOUS}
SENS_ACHAT = {"BUY", "LONG", "ACHAT", "0", "OP_BUY"}
SENS_VENTE = {"SELL", "SHORT", "VENTE", "1", "OP_SELL"}
CHURN_VALIDES = {"CLEAN": "CLEAN", "MIXED": "MIXED", "MIXTE": "MIXED",
                 "CHURN": "CHURN", "NOISE": "CHURN"}


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
    t = [n for n in NOMS if os.path.isfile(n)]
    if t:
        return t
    print("Aucun rails_trades*.jsonl ni churn_trades*.jsonl trouve.")
    print("Utilise --fichier <chemin>.")
    sys.exit(1)


# ------------------------------------------------------------ normalisation
def _prem(o, clefs):
    """Premiere clef presente et non vide, parmi une liste de candidates."""
    for c in clefs:
        for k in (c, c.upper(), c.lower()):
            if k in o and o[k] not in (None, ""):
                return o[k]
    return None


def _niche(o, tf):
    """Sous-dictionnaire du pas de temps, si l enregistrement en a un."""
    for c in CLEFS_NICHE:
        v = o.get(c)
        if isinstance(v, dict):
            for k in (tf, tf.lower(), tf.upper()):
                if isinstance(v.get(k), dict):
                    return v[k]
    return None


def _nombre(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _etat_tf(o, tf):
    """(biais, rsi) du pas de temps, chacun '' si irreductible.

    Deux voies, dans cet ordre : l etiquette si elle est la, sinon les
    nombres. La seconde reconstitue la definition du panel a l identique --
    bull = les deux rails au-dessus de 50, RSI ABOVE = au-dessus des deux --
    elle n approxime rien.
    """
    src = _niche(o, tf) or o
    kl, ku = tf.lower(), tf.upper()

    def cands(mod):
        return [m % kl for m in mod] + [m % ku for m in mod]

    biais = ""
    v = _prem(src, ["rails_pos", "pos"]) if src is not o else None
    if v is None:
        v = _prem(o, cands(CLEFS_POS))
    if v is not None:
        biais = POS_VERS_BIAIS.get(str(v).strip().upper(), "")

    rsi = ""
    v = _prem(src, ["rsi_pos"]) if src is not o else None
    if v is None:
        v = _prem(o, cands(CLEFS_RSIPOS))
    if v is not None:
        rsi = RSIPOS_VALIDES.get(str(v).strip().upper(), "")

    if biais and rsi:
        return biais, rsi

    # Secours par les nombres, definition du panel appliquee telle quelle.
    if src is not o:
        nb, nu, nr = (_nombre(src.get("bull")), _nombre(src.get("bear")),
                      _nombre(src.get("rsi")))
    else:
        nb = _nombre(_prem(o, cands(CLEFS_BULL)))
        nu = _nombre(_prem(o, cands(CLEFS_BEAR)))
        nr = _nombre(_prem(o, cands(CLEFS_RSI)))
    if not biais and nb is not None and nu is not None:
        if nb > 50 and nu > 50:
            biais = R.BULL
        elif nb < 50 and nu < 50:
            biais = R.BEAR
        else:
            biais = R.FLAT
    if not rsi and nb is not None and nu is not None and nr is not None:
        haut, bas = max(nb, nu), min(nb, nu)
        rsi = R.DESSUS if nr > haut else (R.SOUS if nr < bas else R.DEDANS)
    return biais, rsi


def _sens(o):
    v = _prem(o, CLEFS_SENS)
    if v is None:
        return ""
    s = str(v).strip().upper()
    if s in SENS_ACHAT:
        return R.ACHAT
    if s in SENS_VENTE:
        return R.VENTE
    return ""


def _churn(o):
    v = _prem(o, CLEFS_CHURN)
    if v is None:
        return ""
    return CHURN_VALIDES.get(str(v).strip().upper(), "")


def charger(chemins):
    par = {}
    lus = brut = 0
    for ch in chemins:
        for l in io.open(ch, encoding="utf-8-sig"):
            l = l.strip()
            if not l or l[0] != "{":
                continue
            brut += 1
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ts = _prem(o, CLEFS_TS) or ""
            ts = str(ts)
            pnl = _nombre(_prem(o, CLEFS_PNL))
            tk = _prem(o, CLEFS_TICKET)
            if len(ts) < 16 or pnl is None or tk is None or tk in par:
                continue
            try:
                heure = int(ts[11:13])
            except ValueError:
                continue
            s = {"ts": ts, "jour": ts[:10], "hm": ts[11:16], "heure": heure,
                 "pnl": pnl, "ticket": tk, "sens": _sens(o), "churn": _churn(o)}
            for tf in TFS:
                b, r = _etat_tf(o, tf)
                s["biais_" + tf.lower()] = b
                s["rsi_" + tf.lower()] = r
            par[tk] = s
            lus += 1
    if not lus:
        print("Aucun enregistrement exploitable sur %d lignes JSON lues." % brut)
        print("Lance --champs pour voir ce que contiennent ces lignes.")
        sys.exit(1)
    return list(par.values())


# --------------------------------------------------------------- diagnostic
def champs(a):
    """Mode de reconnaissance : ce que le harnais sait lire, et sur combien."""
    ch = sources(a.fichier)
    print("fichiers : %s" % ", ".join(ch))
    lot = charger(ch)
    print("%d enregistrements avec horodatage, P&L et identifiant." % len(lot))
    print()
    print("%-14s %8s %8s" % ("champ", "renseigne", "%"))
    print("-" * 34)
    noms = ["sens", "churn"]
    for tf in TFS:
        noms += ["biais_" + tf.lower(), "rsi_" + tf.lower()]
    for n in noms:
        k = sum(1 for s in lot if s.get(n))
        print("%-14s %8d %7.0f%%" % (n, k, 100.0 * k / max(1, len(lot))))
    print("-" * 34)
    for n, lab in (("biais_m1", "biais M1"), ("rsi_m1", "RSI M1"),
                   ("biais_m5", "biais M5"), ("rsi_m5", "RSI M5"),
                   ("biais_m15", "biais M15"), ("churn", "churn"),
                   ("sens", "sens")):
        d = {}
        for s in lot:
            d[s.get(n) or "(vide)"] = d.get(s.get(n) or "(vide)", 0) + 1
        print("%-10s : %s" % (lab, "  ".join("%s=%d" % (k, d[k])
                                             for k in sorted(d))))
    cx = couverture(lot, R.CH_X)
    cy = couverture(lot, R.CH_Y)
    print()
    print("couverture famille X (sens, biais M1) : %.0f%%  -- minimum %.0f%%"
          % (cx, COUV_MIN))
    print("couverture famille Y (M1, M15, churn) : %.0f%%  -- minimum %.0f%%"
          % (cy, COUV_MIN_Y))
    if cx < COUV_MIN or cy < COUV_MIN_Y:
        print()
        print("*** NOMS DE CHAMPS A CORRIGER ***")
        print("Complete CLEFS_POS / CLEFS_RSIPOS / CLEFS_CHURN / CLEFS_SENS")
        print("en haut de CE fichier, jamais dans regles_gelees_v9.py.")
        print("Voici les clefs les plus frequentes d un enregistrement brut :")
        for c in ch:
            for l in io.open(c, encoding="utf-8-sig"):
                l = l.strip()
                if l.startswith("{"):
                    try:
                        o = json.loads(l)
                    except ValueError:
                        continue
                    print("   " + ", ".join(sorted(o.keys())))
                    return 1
    else:
        print("Couverture suffisante : --geler peut tourner.")
    return 0


# ------------------------------------------------------------------- mesures
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


def couverture(lot, champs_):
    if not champs_:
        return 100.0
    ok = sum(1 for s in lot if all(s.get(c) not in (None, "") for c in champs_))
    return 100.0 * ok / max(1, len(lot))


def _paires(lot, fn):
    d = {}
    for s in lot:
        e = d.setdefault(s["jour"], {"g": [], "r": []})
        e["g" if fn(s) else "r"].append(s["pnl"])
    return [sum(v["g"]) / len(v["g"]) - sum(v["r"]) / len(v["r"])
            for v in d.values() if len(v["g"]) >= 3 and len(v["r"]) >= 3]


def par_seance(lot, fn):
    """Magnitude a l unite seance. Les tickets d une meme journee sont
    correles : c est la correction la plus ancienne de l etude."""
    dd = _paires(lot, fn)
    if len(dd) < 5:
        return None, None, len(dd)
    m = sum(dd) / len(dd)
    sd = math.sqrt(sum((x - m) ** 2 for x in dd) / (len(dd) - 1)) if len(dd) > 1 else 0.0
    se = sd / math.sqrt(len(dd)) if sd else 0.0
    pv = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(m / se) / math.sqrt(2.0)))) if se else None
    return m, pv, len(dd)


def signe_seance(lot, fn):
    """Test de SIGNE. Au gel V5, la magnitude donnait p=0,008 et le signe
    7 journees sur 9, soit p environ 0,18 : c est le signe qui avait raison.

    Ce gel-ci en a plus besoin encore que les autres. Le corpus rails ne
    compte que NEUF journees : une seule seance aberrante suffit a fabriquer
    n importe quelle magnitude. Avec neuf paires, le test de signe ne peut
    pas descendre sous p = 0,004 meme si les neuf vont dans le meme sens --
    autant le savoir avant de lire la colonne.
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
    """Centrage du P&L sur la tranche horaire.

    Verifie sur donnees fabriquees : un effet purement horaire sort p=0,002
    a l unite seance et disparait ici. La correction par seance ne suffit
    PAS.

    Ici le confondant horaire est reel et documente : le panel mesure
    -5,49 EUR par ticket sur le creneau 09h-11h, soit 32 %% du corpus. Une
    configuration qui se produit surtout le matin heriterait de cet ecart
    sans rien y avoir contribue.
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
    for code, lib, fn, ch in R.REGLES:
        st = stats([s for s in lot if fn(s)])
        cv = couverture(lot, ch)
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
    print("vont dans le sens de l ecart. p heure = apres centrage horaire. Une")
    print("regle n est credible que si LES TROIS sont petits.")
    inertes = [c for c in res if c != "X0" and res[c]["n"] == ref["n"]]
    if inertes:
        print("INERTES (n excluent rien -- champs absents ?) : %s"
              % ", ".join(sorted(inertes)))
    return res, ref


def verif_couverture(lot):
    cx, cy = couverture(lot, R.CH_X), couverture(lot, R.CH_Y)
    print("couverture X (sens, biais M1) : %.0f%%   Y (M1, M15, churn) : %.0f%%"
          % (cx, cy))
    if cx < COUV_MIN or cy < COUV_MIN_Y:
        print()
        print("*** COUVERTURE INSUFFISANTE -- ON NE CONCLUT PAS ***")
        print("Les champs rails ne sont pas lus sur assez de tickets. En")
        print("fail-open, cela ne vide pas les regles : cela les rend")
        print("identiques a la reference, et le tableau serait plat sans")
        print("que rien ne le signale.")
        print("Lance --champs et corrige les CLEFS_* de ce fichier.")
        return False
    return True


def _rappel_causalite():
    print()
    print("RAPPEL DE CAUSALITE, A RELIRE AVANT DE CROIRE CE TABLEAU")
    print("  Tout ce que lit ce gel doit etre FIGE A L ENTREE du trade :")
    print("  biais des rails, position du RSI, verdict churn. L export du")
    print("  panel l affirme ('variables figees a l entree', 'churn a")
    print("  l entree'). Si une seule de ces valeurs etait recalculee apres")
    print("  la sortie, tout le gel serait du recul deguise et les deux")
    print("  familles tomberaient ensemble.")


def geler(a):
    lot = [s for s in charger(sources(a.fichier))
           if s["jour"] >= (a.debut or DEBUT_REGIME)]
    if not lot:
        print("Aucun signal depuis %s." % (a.debut or DEBUT_REGIME))
        return 1
    if not verif_couverture(lot):
        return 1
    date_gel = a.date or dt.date.today().isoformat()
    ins = [s for s in lot if s["jour"] <= date_gel]
    if not ins:
        print("Aucun ticket au %s ou avant." % date_gel)
        return 1
    # Bornes de l IN-SAMPLE, pas du fichier : au gel V8 cette ligne affichait
    # les bornes du corpus entier, ce qui laissait croire que le gel portait
    # sur des seances posterieures a sa propre date.
    ji = sorted({s["jour"] for s in ins})
    nj = len(ji)

    print("regles_gelees_v9.py v%s" % R.VERSION)
    print("SHA-256  : %s" % empreinte(FR))
    print("date gel : %s" % date_gel)
    print("in-sample: %d tickets, %d seances, %s -> %s"
          % (len(ins), nj, ji[0], ji[-1]))
    if nj < 12:
        print()
        print("/!\\ %d seances seulement. Le test de signe ne peut pas" % nj)
        print("    descendre sous p = %.3f meme si toutes vont dans le meme"
              % (2.0 / (2.0 ** nj)))
        print("    sens. Aucune tete de serie ne pourra donc passer 0,025 par")
        print("    le signe seul : il faudra les trois colonnes, et surtout")
        print("    plus de seances au verdict.")

    res, ref = tableau(ins, "IN-SAMPLE -- ne prouve rien")
    print()
    print("Ce tableau ne fait que redire, ticket par ticket, ce que le panel")
    print("disait deja cellule par cellule. Les deux regles ont ete choisies")
    print("SUR ces chiffres : elles y sont bonnes par construction. Le seul")
    print("interet de ce tableau est de verifier qu on a bien reconstruit les")
    print("memes populations -- comparer aux effectifs de R.INSAMPLE.")
    _rappel_causalite()

    enr = {"version": R.VERSION, "sha256": empreinte(FR), "date_gel": date_gel,
           "debut_regime": a.debut or DEBUT_REGIME, "n_insample": len(ins),
           "seances_insample": nj, "et_pnl": ref["et"], "regles": res,
           "origine": R.ORIGINE, "tetes": R.TETES,
           "insample_panel": R.INSAMPLE}
    out = a.sortie or ("gel_v9_%s.json" % date_gel)
    io.open(out, "w", encoding="utf-8").write(
        json.dumps(enr, indent=2, ensure_ascii=False))
    print()
    print("Gel ecrit : %s" % out)
    print("NE PLUS TOUCHER A regles_gelees_v9.py.")
    return 0


def verdict(a):
    g = a.gel or (sorted(f for f in os.listdir(".")
                         if f.startswith("gel_v9_") and f.endswith(".json"))
                  or [None])[-1]
    if not g:
        print("Aucun gel_v9_*.json. Lance d abord --geler.")
        return 1
    gel = json.load(io.open(g, encoding="utf-8-sig"))
    print("gel du %s (%s)" % (gel["date_gel"], g))

    if empreinte(FR) != gel["sha256"]:
        print()
        print("*** regles_gelees_v9.py A CHANGE DEPUIS LE GEL ***")
        print("attendu %s" % gel["sha256"])
        print("actuel  %s" % empreinte(FR))
        print("Verdict INVALIDE : les regles ont ete ajustees apres coup.")
        if not a.force:
            return 1

    lot = [s for s in charger(sources(a.fichier)) if s["jour"] > gel["date_gel"]]
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
    ref_in = gel["regles"]["X0"]["moy"]
    for code, lib, fn, ch in R.REGLES:
        if code == "X0":
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
    print("LA LECTURE DE CE GEL, DANS CET ORDRE. NE PAS LIRE AUTREMENT.")
    print()
    print("  FAMILLE X -- la transition de rail")
    print()
    print("  1. X4 contre X5. C est LE test, parce que ce sont les deux")
    print("     seuls ensembles DISJOINTS du gel. Le panel montrait un")
    print("     gradient M1 -> M5 sur quatre lignes qui se recouvrent ; ici")
    print("     elles ne se recouvrent pas. Si X5 n est pas nettement")
    print("     au-dessus de X4, il n y avait pas de gradient, seulement")
    print("     quatre facons de recompter les memes tickets, et toute la")
    print("     famille X s arrete a cette ligne.")
    print()
    print("  2. X1 contre X3. Ce que vaut la confirmation M5, et rien")
    print("     d autre. Si X3 fait aussi bien, on garde X3 : interdire la")
    print("     configuration en entier est plus simple et ne suppose rien")
    print("     sur le role du pas de temps.")
    print()
    print("  3. X3 contre X2. Si le temoin large fait aussi bien, la lecture")
    print("     du RSI n apportait rien : il suffisait de ne pas vendre")
    print("     contre des rails haussiers. Meme piege qu au gel V8, ou")
    print("     l heure tardive expliquait seule ce qu on attribuait a la")
    print("     premiere heure.")
    print()
    print("  4. X6, la replication symetrique. Elle n a pas servi a choisir")
    print("     la regle. Si X1 tient et pas X6, le mecanisme suppose -- le")
    print("     M1 declenche sur un bruit d une minute -- est faux, et il")
    print("     reste une particularite du cote vente, a expliquer avant")
    print("     d en faire quoi que ce soit.")
    print()
    print("  5. X7 seulement si X1 ET X6 tiennent. Lecon du gel V4 : deux")
    print("     filtres empiles y faisaient moins bien que le meilleur des")
    print("     deux seul. X7 doit battre X1 et X6, sinon on n empile pas.")
    print()
    print("  FAMILLE Y -- la capitulation")
    print()
    print("  6. Y1 contre Y2 ET contre Y3. Y1 est la conjonction de deux")
    print("     conditions ; battre un seul des deux temoins ne suffit pas.")
    print("     Si Y2 suffit, ce gel disait 'trader quand le marche est")
    print("     moyennement bruite', ce qui ne parle plus des rails.")
    print()
    print("  7. Y4, le miroir. In-sample il tient sur 30 signaux et QUATRE")
    print("     jours : il se decrit, il ne conclut pas. Trois issues, et")
    print("     elles etaient ecrites avant :")
    print("       Y1 tient, Y4 negatif  -> l asymetrie est un fait a")
    print("                                 expliquer, pas encore une regle")
    print("       Y1 et Y4 positifs     -> c etait le desaccord des deux")
    print("                                 bouts, et Y3 aurait du le dire")
    print("       les deux s effondrent -> la cellule etait un pari sur la")
    print("                                 hausse des indices de ces 9 jours")
    print()
    print("  SEUIL. Deux tetes de serie declarees avant : X1 et Y1, donc")
    print("  0,05 / 2 = 0,025 sur chacune, sur LES TROIS colonnes. Les")
    print("  temoins et les controles negatifs ne se lisent pas en p mais en")
    print("  SENS : un temoin qui bat sa regle la tue, quel que soit son p.")
    _rappel_causalite()
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--champs", action="store_true",
                   help="diagnostic des noms de champs, a lancer en premier")
    p.add_argument("--geler", action="store_true")
    p.add_argument("--verdict", action="store_true")
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--date")
    p.add_argument("--debut")
    p.add_argument("--sortie")
    p.add_argument("--gel")
    p.add_argument("--force", action="store_true")
    a = p.parse_args()
    if a.champs:
        return champs(a)
    if a.geler:
        return geler(a)
    if a.verdict:
        return verdict(a)
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
