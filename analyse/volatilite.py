# -*- coding: utf-8 -*-
"""
volatilite.py -- l AMPLITUDE, la quantite que j avais oubliee.

POURQUOI CE FICHIER EXISTE
    regime_jour.py a teste la persistance de l EFFICIENCE -- la part du
    chemin qui se transforme en deplacement net. Resultat : nulle, voire
    negative. Les journees de tendance ne s enchainent pas.

    Mais l efficience n est pas la volatilite. L amplitude, elle, est la
    quantite la PLUS persistante de toute la finance : une journee large
    est presque toujours suivie d une journee large, dans tous les marches
    et a toutes les echelles. Je ne l avais pas testee. C est une omission,
    pas un detail : c est probablement le vrai canal.

    Et pour un scalpeur le lien au P&L serait direct, sans passer par la
    notion de tendance : plus d amplitude, plus d occasions.

CE QUE CA CHANGERAIT
    Si l amplitude explique le P&L mieux que l efficience, alors la regle
    inversee trouvee dans regime_jour (trader apres les periodes calmes)
    ne porte pas sur le bon indicateur, et il ne faut surtout pas la geler
    telle quelle.

CAUSALITE
    Tous les indicateurs sont calcules sur les jours PRECEDENTS. Le jour
    courant n y entre jamais.

PREUVE INEGALE, RAPPELEE PARTOUT
    Sections 1 et 2 : 128 seances de prix, solides.
    Sections 3 a 5  : une quarantaine d observations de P&L, indicatives.
"""
import io, os, sys, math

CSV = "profil_jour.csv"
STOP = "jambe_stop.csv"
FENETRES = [3, 5, 10]


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


def f(v):
    if v is None:
        return None
    v = v.strip().replace(",", ".")
    if v == "" or v.upper() in ("NA", "NONE", "NAN"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def lire_prix():
    if not os.path.isfile(CSV):
        print("introuvable : %s" % CSV); sys.exit(1)
    lg = [l.rstrip("\n") for l in io.open(CSV, encoding="utf-8-sig") if l.strip()]
    sep = ";" if lg[0].count(";") >= lg[0].count(",") else ","
    ent = [c.strip() for c in lg[0].split(sep)]
    par = {}
    for l in lg[1:]:
        c = l.split(sep)
        if len(c) < len(ent):
            c += [""] * (len(ent) - len(c))
        d = dict(zip(ent, c))
        j, a = (d.get("jour") or "").strip(), (d.get("asset") or "").strip()
        rg, ar, ef = f(d.get("range")), f(d.get("am_range")), f(d.get("eff"))
        if not j or not a or rg is None or rg <= 0:
            continue
        par.setdefault(a, []).append({"jour": j, "range": rg, "am_range": ar,
                                      "eff": ef,
                                      "type": (d.get("type") or "").strip().upper()})
    for a in par:
        par[a].sort(key=lambda x: x["jour"])
    print("prix : %d actifs, %d lignes" % (len(par), sum(len(v) for v in par.values())))
    return par


def lire_pnl():
    if not os.path.isfile(STOP):
        print("/!\\ %s absent : sections 3 a 5 sautees." % STOP)
        return {}
    lg = [l.rstrip("\n") for l in io.open(STOP, encoding="utf-8-sig") if l.strip()]
    ent = [c.strip() for c in lg[0].split(";")]
    if "jour" not in ent:
        print("/!\\ %s sans colonne 'jour' : relance jambe_stop.py." % STOP)
        return {}
    out = {}
    for l in lg[1:]:
        c = l.split(";")
        if len(c) < len(ent):
            continue
        d = dict(zip(ent, c))
        try:
            k = (d["jour"].strip(), d["sym"].strip())
            out[k] = out.get(k, 0.0) + float(d["pnl_eur"])
        except (KeyError, ValueError):
            continue
    print("P&L : %d couples jour/actif" % len(out))
    return out


def indicateurs(par):
    """volN = amplitude moyenne des N jours precedents, rapportee a la
    mediane longue de l actif pour etre comparable entre indices.
    effN = efficience moyenne des N jours precedents (rappel de
    regime_jour.py, pour la stratification de la section 5).
    Le jour courant n entre dans aucun des deux."""
    for a, s in par.items():
        ref = med([x["range"] for x in s]) or 1.0
        for i, d in enumerate(s):
            d["ref"] = ref
            for N in FENETRES:
                h = s[max(0, i - N):i]
                if len(h) == N:
                    d["vol_%d" % N] = moy([x["range"] for x in h]) / ref
                    d["eff_%d" % N] = moy([x["eff"] for x in h])
                else:
                    d["vol_%d" % N] = None
                    d["eff_%d" % N] = None
    return par


def section1(par):
    print()
    print("=" * 88)
    print("  1. l amplitude persiste-t-elle ? -- 128 seances, resultat solide")
    print("=" * 88)
    print("C est LE test que j avais omis. Attendu : fortement positif.")
    print("Si ca l est, l amplitude est previsible la ou l efficience ne l est pas.")
    print()
    print("  %-9s %-12s %5s %9s %9s" % ("actif", "serie", "N", "rho", "p"))
    print("  " + "-" * 50)
    for a, s in sorted(par.items()):
        for cle, lib in (("range", "amplitude"), ("am_range", "range du matin"),
                         ("eff", "efficience")):
            x = [s[i - 1][cle] for i in range(1, len(s))
                 if s[i].get(cle) is not None and s[i - 1].get(cle) is not None]
            y = [s[i][cle] for i in range(1, len(s))
                 if s[i].get(cle) is not None and s[i - 1].get(cle) is not None]
            rho, p = spearman(x, y)
            if rho is None:
                continue
            print("  %-9s %-12s %5d %+9.3f %9s"
                  % (a, lib, len(x), rho, "%.3f" % p if p is not None else "-"))
        print("  " + "-" * 50)
    print("  L efficience est rappelee pour comparaison : c est la serie qui")
    print("  ne persistait pas. Si l amplitude persiste et pas elle, on tient")
    print("  la difference qui explique tout.")


def section2(par):
    print()
    print("=" * 88)
    print("  2. l indicateur d amplitude annonce-t-il l amplitude du jour ?")
    print("=" * 88)
    print("  %-9s %3s %6s %9s %9s %16s"
          % ("actif", "N", "obs", "rho", "p", "ampl. bas/haut"))
    print("  " + "-" * 60)
    for a, s in sorted(par.items()):
        for N in FENETRES:
            cle = "vol_%d" % N
            g = [d for d in s if d.get(cle) is not None]
            if len(g) < 30:
                continue
            rho, p = spearman([d[cle] for d in g], [d["range"] for d in g])
            q = sorted(d[cle] for d in g)
            lo, hi = q[len(q) // 3], q[(2 * len(q)) // 3]
            b = med([d["range"] for d in g if d[cle] <= lo])
            h = med([d["range"] for d in g if d[cle] >= hi])
            print("  %-9s %3d %6d %+9.3f %9s   %6.1f / %6.1f"
                  % (a, N, len(g), rho if rho is not None else 0.0,
                     "%.3f" % p if p is not None else "-", b or 0, h or 0))
        print("  " + "-" * 60)


def obs_pnl(par, pnl, cle):
    out = []
    for a, s in par.items():
        for d in s:
            v = pnl.get((d["jour"], a))
            if v is not None and d.get(cle) is not None:
                out.append((d[cle], v, d["jour"], a, d))
    return out


def section3(par, pnl):
    if not pnl:
        return
    print()
    print("=" * 88)
    print("  3. l amplitude recente annonce-t-elle le P&L ?")
    print("=" * 88)
    print("INDICATIF : une quarantaine d observations. On lit le sens.")
    for N in FENETRES:
        o = obs_pnl(par, pnl, "vol_%d" % N)
        if len(o) < 15:
            continue
        o.sort()
        c = len(o) // 2
        bas = [x[1] for x in o[:c]]
        haut = [x[1] for x in o[c:]]
        e, p = t_deux(haut, bas)
        print()
        print("  amplitude sur %d jours -- %d observations" % (N, len(o)))
        print("    CALME  : total %+9.2f, moyen %+8.2f, %d positives sur %d"
              % (sum(bas), moy(bas), sum(1 for x in bas if x > 0), len(bas)))
        print("    AGITE  : total %+9.2f, moyen %+8.2f, %d positives sur %d"
              % (sum(haut), moy(haut), sum(1 for x in haut if x > 0), len(haut)))
        print("    ecart %+.2f par observation, p=%s"
              % (e if e is not None else 0.0, "%.3f" % p if p is not None else "-"))


def section4(par, pnl):
    if not pnl:
        return
    print()
    print("=" * 88)
    print("  4. amplitude et efficience sont-ils deux canaux distincts ?")
    print("=" * 88)
    print("Table 2x2 puis stratification. Si l effet de l efficience survit")
    print("A AMPLITUDE CONSTANTE, ce sont deux informations differentes.")
    print("S il disparait, c est l amplitude qui portait tout et la regle")
    print("inversee de regime_jour ne doit PAS etre gelee telle quelle.")
    for N in FENETRES:
        cv, ce = "vol_%d" % N, "eff_%d" % N
        o = [x for x in obs_pnl(par, pnl, cv) if x[4].get(ce) is not None]
        if len(o) < 20:
            continue
        mv = med([x[0] for x in o])
        me = med([x[4][ce] for x in o])
        cel = {}
        for val, v, j, a, d in o:
            k = ("AGITE" if val > mv else "CALME",
                 "TENDU" if d[ce] > me else "HACHE")
            cel.setdefault(k, []).append(v)
        print()
        print("  fenetre %d jours, %d observations" % (N, len(o)))
        print("  %-10s %20s %20s" % ("", "efficience HACHE", "efficience TENDU"))
        for va in ("CALME", "AGITE"):
            bouts = []
            for ee in ("HACHE", "TENDU"):
                g = cel.get((va, ee), [])
                bouts.append("%20s" % ("-" if not g else "%d obs %+8.2f" % (len(g), moy(g))))
            print("  %-10s %s" % (va, " ".join(bouts)))
        for va in ("CALME", "AGITE"):
            a1, a2 = cel.get((va, "HACHE"), []), cel.get((va, "TENDU"), [])
            if len(a1) >= 4 and len(a2) >= 4:
                e, p = t_deux(a1, a2)
                print("    a amplitude %-6s : HACHE moins TENDU = %+8.2f  p=%s"
                      % (va, e, "%.3f" % p if p is not None else "-"))


def section5(par, pnl):
    if not pnl:
        return
    print()
    print("=" * 88)
    print("  5. lequel des deux separe le mieux le P&L ?")
    print("=" * 88)
    print("  %-16s %6s %12s %12s %10s"
          % ("indicateur", "obs", "moitie basse", "moitie haute", "ecart"))
    print("  " + "-" * 62)
    for nom, lib in (("vol", "amplitude"), ("eff", "efficience")):
        for N in FENETRES:
            o = obs_pnl(par, pnl, "%s_%d" % (nom, N))
            if len(o) < 15:
                continue
            o.sort()
            c = len(o) // 2
            bas, haut = [x[1] for x in o[:c]], [x[1] for x in o[c:]]
            print("  %-16s %6d %+12.2f %+12.2f %+10.2f"
                  % ("%s %d j" % (lib, N), len(o), sum(bas), sum(haut),
                     sum(haut) - sum(bas)))
    print("  " + "-" * 62)
    print("  Le plus grand ecart en valeur absolue gagne -- mais souviens-toi")
    print("  qu on compare six variantes sur une quarantaine d observations.")
    print("  Prendre la meilleure des six, c est deja surajuster.")


def main():
    par = indicateurs(lire_prix())
    pnl = lire_pnl()
    section1(par)
    section2(par)
    section3(par, pnl)
    section4(par, pnl)
    section5(par, pnl)
    print()
    print("=" * 88)
    print("  ce qu il faut en tirer")
    print("=" * 88)
    print("Section 1 : si l amplitude persiste fortement alors que l efficience")
    print("ne persiste pas, on tient enfin une quantite previsible.")
    print()
    print("Section 4 : c est elle qui dit s il faut geler la regle inversee de")
    print("regime_jour, ou si l amplitude la remplace. Ne gele rien avant.")
    print()
    print("Et le rappel qui vaut pour tout ce bloc : le prix donne 128 seances,")
    print("l argent une quarantaine d observations. Tout ce qui touche au P&L")
    print("ici est une direction de recherche, pas un resultat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
