# -*- coding: utf-8 -*-
"""
jumeaux.py -- A/B des politiques de sortie 206 (hold) contre 207 (trail).

POURQUOI CE TEST EST DIFFERENT DE TOUS LES AUTRES
    Tout ce qu on a mesure jusqu ici est OBSERVATIONNEL : on decoupe un
    corpus apres coup et on compare des groupes qui different par autre
    chose que ce qu on croit mesurer.

    Ici, potentiellement, non. Les familles 206 et 207 semblent etre des
    JUMEAUX : meme signal d entree, deux politiques de fermeture --
    conservation jusqu au retournement contre suivi de stop. Le docstring
    de magic_section.py le dit : "dedupliquer les jumeaux 206/207
    fusionnerait les deux bras qu on veut justement separer".

    Si c est vrai, c est la SEULE randomisation controlee du dispositif,
    et elle est la par conception. Un test apparie y est bien plus
    puissant qu une comparaison de groupes : meme signal, meme instant,
    meme marche, une seule difference.

CE QUE LES TESTS DE SORTIE PRECEDENTS NE COUVRENT PAS
    On a montre qu aucun TP/SL fixe et aucun critere temporel ne battent
    les sorties existantes. Mais on testait l ajout d une couche PAR-DESSUS
    ces sorties. Le choix ENTRE DEUX POLITIQUES EXISTANTES n a jamais ete
    mesure. La question est entierement ouverte.

L HYPOTHESE A VERIFIER AVANT DE MESURER
    Section 0 : les deux bras se declenchent-ils vraiment ensemble ?
    On ne le suppose pas, on le compte. Si l appariement echoue, le test
    apparie est abandonne et on retombe sur une comparaison de groupes,
    beaucoup plus faible -- et le script le dit au lieu de faire semblant.

APPARIEMENT
    magic 206NNN <-> magic 207NNN : meme trois derniers chiffres, prefixe
    different. Deux tickets sont apparies s ils portent le meme actif et
    des horodatages d entree distants de moins de TOL_S secondes.
"""
import io, os, sys, math, json, datetime as dt

CHURN = [os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
         os.path.join("docs", "churn_trades", "churn_trades.jsonl")]
TOL_S = 120                 # tolerance d appariement, en secondes
HOLD, TRAIL = "206", "207"
MIN_PAIRES = 20


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


def t_apparie(diffs):
    """Test sur differences appariees. Bien plus puissant qu un test de
    groupes : toute la variabilite commune aux deux bras s annule."""
    d = [x for x in diffs if x is not None]
    if len(d) < 5:
        return None, None, 0
    m = moy(d)
    s = et(d)
    se = s / math.sqrt(len(d)) if s else 0.0
    return m, (p_norm(m / se) if se else None), len(d)


def t_deux(a, b):
    a = [x for x in a if x is not None]
    b = [x for x in b if x is not None]
    if len(a) < 3 or len(b) < 3:
        return None, None
    e = moy(a) - moy(b)
    se = math.sqrt(et(a) ** 2 / len(a) + et(b) ** 2 / len(b))
    return e, (p_norm(e / se) if se else None)


def binom(k, n):
    """Test de signe : le seul robuste aux journees hors norme."""
    if n == 0:
        return None
    c = [1]
    for _ in range(n):
        c = [1] + [c[j] + c[j + 1] for j in range(len(c) - 1)] + [1]
    return min(1.0, sum(c[i] for i in range(n + 1)
                        if i >= max(k, n - k) or i <= min(k, n - k)) / float(sum(c)))


def epoch(ts):
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            t = dt.datetime.strptime(str(ts)[:19], f)
            return (t - dt.datetime(1970, 1, 1)).total_seconds()
        except ValueError:
            pass
    return None


def prem(o, cles):
    for c in cles:
        v = o.get(c)
        if isinstance(v, dict):
            v = v.get("verdict")
        if v not in (None, ""):
            return str(v).strip().upper()
    return ""


def charger():
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
            mg = o.get("magic")
            if len(ts) < 16 or pnl is None or tk is None or mg is None or tk in par:
                continue
            e = epoch(ts)
            if e is None:
                continue
            par[tk] = {"ticket": tk, "magic": str(mg), "ts": ts, "ep": e,
                       "jour": ts[:10], "heure": int(ts[11:13]),
                       "asset": (o.get("asset") or "").strip().upper(),
                       "pnl": float(pnl),
                       "setup": (o.get("rails_setup") or "").strip().upper(),
                       # le verdict de churn est a churn_entry.verdict, PAS
                       # dans hlc_churn_entry qui est le consensus HLC par TF
                       "churn": prem(o, ["churn_entry", "churn"]),
                       "dir": (o.get("dir") or "").strip().upper()}
    return list(par.values())


def section0(lot):
    """Verifier le jumelage AVANT de mesurer quoi que ce soit."""
    print()
    print("=" * 88)
    print("  0. sont-ce vraiment des jumeaux ? -- on compte, on ne suppose pas")
    print("=" * 88)
    fam = {}
    for t in lot:
        m = t["magic"]
        if len(m) >= 6 and m[:3] in (HOLD, TRAIL):
            fam.setdefault(m[3:], {HOLD: [], TRAIL: []})[m[:3]].append(t)
    if not fam:
        print("  aucun magic en 206xxx / 207xxx trouve.")
        print("  magics presents : %s"
              % ", ".join(sorted({t["magic"] for t in lot})[:20]))
        return {}, []
    print("  %-8s %8s %8s %10s %12s %12s"
          % ("suffixe", "206 hold", "207 trail", "apparies", "% du 206", "% du 207"))
    print("  " + "-" * 64)
    paires_tot = []
    for suf in sorted(fam):
        a = sorted(fam[suf][HOLD], key=lambda x: x["ep"])
        b = sorted(fam[suf][TRAIL], key=lambda x: x["ep"])
        if not a or not b:
            print("  %-8s %8d %8d %10s   (un seul bras)" % (suf, len(a), len(b), "-"))
            continue
        # appariement glouton par proximite temporelle, meme actif
        pris = set()
        paires = []
        for x in a:
            best, bd = None, None
            for j, y in enumerate(b):
                if j in pris or y["asset"] != x["asset"]:
                    continue
                d = abs(y["ep"] - x["ep"])
                if d <= TOL_S and (bd is None or d < bd):
                    best, bd = j, d
            if best is not None:
                pris.add(best)
                paires.append((x, b[best]))
        print("  %-8s %8d %8d %10d %11.0f%% %11.0f%%"
              % (suf, len(a), len(b), len(paires),
                 100.0 * len(paires) / len(a), 100.0 * len(paires) / len(b)))
        paires_tot.extend(paires)
    print("  " + "-" * 64)
    tot_h = sum(len(fam[s][HOLD]) for s in fam)
    tot_t = sum(len(fam[s][TRAIL]) for s in fam)
    print("  total : %d hold, %d trail, %d paires (tolerance %d s)"
          % (tot_h, tot_t, len(paires_tot), TOL_S))
    taux = 100.0 * len(paires_tot) / max(1, min(tot_h, tot_t))
    print("  taux d appariement : %.0f%% du bras le plus petit" % taux)
    print()
    if taux >= 70:
        print("  -> JUMELAGE CONFIRME. Le test apparie de la section 1 est")
        print("     legitime, et c est la seule experience controlee du")
        print("     dispositif : meme signal, meme instant, une seule difference.")
    elif taux >= 30:
        print("  -> JUMELAGE PARTIEL. Les deux bras ne se declenchent pas")
        print("     toujours ensemble. Le test apparie ne porte que sur la")
        print("     partie appariee, qui n est peut-etre pas representative.")
        print("     Lire la section 2 avec au moins autant d attention.")
    else:
        print("  -> PAS DE JUMELAGE. Les deux familles ne tirent pas sur les")
        print("     memes signaux : ce n est PAS un A/B controle, seulement")
        print("     deux strategies differentes qu on compare apres coup.")
        print("     Tout ce qui suit redevient observationnel.")
    return fam, paires_tot


def section1(paires):
    print()
    print("=" * 88)
    print("  1. test APPARIE -- hold moins trail, paire par paire")
    print("=" * 88)
    if len(paires) < MIN_PAIRES:
        print("  %d paires seulement -- pas de test." % len(paires))
        return
    print("Chaque difference annule tout ce que les deux bras ont en commun :")
    print("le signal, l instant, l actif, le marche. Il ne reste que la")
    print("politique de sortie.")
    d = [x["pnl"] - y["pnl"] for x, y in paires]
    m, p, n = t_apparie(d)
    pos = sum(1 for v in d if v > 0)
    ps = binom(pos, len(d))
    print()
    print("  %d paires" % len(paires))
    print("  hold  %+8.2f EUR/tk    trail %+8.2f EUR/tk"
          % (moy([x["pnl"] for x, _ in paires]), moy([y["pnl"] for _, y in paires])))
    print("  difference moyenne %+.2f EUR par paire, mediane %+.2f"
          % (m, med(d)))
    print("  p apparie %s   |   signe %d/%d, p=%s  <- le robuste"
          % ("%.3f" % p if p is not None else "-", pos, len(d),
             "%.3f" % ps if ps is not None else "-"))
    print()
    print("  Positif = HOLD gagne. Negatif = TRAIL gagne.")

    # unite seance, indispensable ici aussi
    par_j = {}
    for x, y in paires:
        par_j.setdefault(x["jour"], []).append(x["pnl"] - y["pnl"])
    js = [(j, moy(v)) for j, v in par_j.items() if len(v) >= 3]
    if len(js) >= 5:
        dd = [v for _, v in js]
        mm, pp, _ = t_apparie(dd)
        k = sum(1 for v in dd if v > 0)
        print()
        print("  a l unite seance : %d seances, ecart moyen %+.2f, %d/%d en faveur"
              % (len(js), mm, k, len(js)))
        print("                     p magnitude %s, p signe %s"
              % ("%.3f" % pp if pp is not None else "-",
                 "%.3f" % binom(k, len(js)) if binom(k, len(js)) is not None else "-"))
    else:
        print()
        print("  a l unite seance : %d seances exploitables -- pas de test." % len(js))


def section2(paires):
    print()
    print("=" * 88)
    print("  2. la bonne politique depend-elle du contexte ?")
    print("=" * 88)
    print("C est la vraie question : s il existe un aiguillage, il ne coute")
    print("rien a implementer puisque les deux bras tournent deja.")
    if len(paires) < MIN_PAIRES:
        print("  trop peu de paires.")
        return
    for cle, lib, ordre in (("churn", "verdict de churn", ("CLEAN", "MIXED", "CHURN")),
                            ("setup", "setup rails", None),
                            ("sess", "session", ("EUR", "US")),
                            ("asset", "actif", None)):
        cel = {}
        for x, y in paires:
            if cle == "sess":
                k = "US" if x["heure"] >= 14 else "EUR"
            else:
                k = x.get(cle) or ""
            if not k:
                continue
            cel.setdefault(k, []).append(x["pnl"] - y["pnl"])
        if not cel:
            continue
        print()
        print("  --- %s ---" % lib)
        print("  %-14s %7s %12s %12s %9s %9s"
              % ("", "paires", "hold-trail", "mediane", "p", "signe"))
        cles = [k for k in (ordre or sorted(cel)) if k in cel]
        for k in cles:
            d = cel[k]
            if len(d) < 10:
                continue
            m, p, _ = t_apparie(d)
            pos = sum(1 for v in d if v > 0)
            print("  %-14s %7d %+12.2f %+12.2f %9s %9s"
                  % (k, len(d), m, med(d),
                     "%.3f" % p if p is not None else "-",
                     "%d/%d" % (pos, len(d))))
    print()
    print("  Un signe qui CHANGE d une ligne a l autre, avec des p petits des")
    print("  deux cotes, serait l aiguillage recherche. Des signes identiques")
    print("  partout signifient qu une politique domine simplement l autre.")


def section3(lot, fam):
    """Comparaison de groupes, pour les tickets non apparies."""
    print()
    print("=" * 88)
    print("  3. comparaison de GROUPES -- plus faible, donnee pour memoire")
    print("=" * 88)
    print("Sans appariement, les deux bras peuvent differer par autre chose")
    print("que leur politique de sortie. A ne lire que si la section 0 a")
    print("montre un jumelage partiel ou absent.")
    h = [t["pnl"] for t in lot if t["magic"][:3] == HOLD]
    tr = [t["pnl"] for t in lot if t["magic"][:3] == TRAIL]
    if len(h) < 20 or len(tr) < 20:
        print("  trop peu de tickets.")
        return
    e, p = t_deux(h, tr)
    print()
    print("  hold  %5d tickets  %+8.2f EUR/tk  total %+10.2f" % (len(h), moy(h), sum(h)))
    print("  trail %5d tickets  %+8.2f EUR/tk  total %+10.2f" % (len(tr), moy(tr), sum(tr)))
    print("  ecart %+.2f, p=%s" % (e, "%.3f" % p if p is not None else "-"))


def main():
    lot = charger()
    if len(lot) < 100:
        print("trop peu de tickets lus (%d)." % len(lot))
        return 1
    js = sorted({t["jour"] for t in lot})
    print("%d tickets, %d seances, %s -> %s" % (len(lot), len(js), js[0], js[-1]))
    fam, paires = section0(lot)
    if not fam:
        return 1
    section1(paires)
    section2(paires)
    section3(lot, fam)
    print()
    print("=" * 88)
    print("  ce qu il faut retenir")
    print("=" * 88)
    print("Si la section 0 confirme le jumelage, la section 1 est le resultat")
    print("le plus propre de toute la campagne : une randomisation reelle,")
    print("pas un decoupage a posteriori. Un p y vaut ce qu il pretend valoir.")
    print()
    print("Si la section 2 montre un aiguillage -- hold meilleur en CLEAN,")
    print("trail meilleur en CHURN par exemple -- il est implementable sans")
    print("toucher a la logique de sortie, puisque les deux bras existent.")
    print()
    print("Reserve : cela reste in-sample. Un aiguillage trouve ici devra")
    print("etre gele avant d etre applique, comme les sept autres.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
