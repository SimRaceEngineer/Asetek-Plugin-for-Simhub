# -*- coding: utf-8 -*-
"""
regime_jour.py -- reconnaitre une seance de TENDANCE AVANT qu elle ait lieu.

L OBSERVATION QUI MOTIVE TOUT CECI
    Du 22 au 31 juillet la stack a fait +13 279 EUR ; du 3 au 7 aout elle a
    perdu 3 108 EUR. Sur le graphique 4h, la premiere periode est une sortie
    de range en tendance, la seconde un retour en range.

    Ce n est donc pas la stack qui s est degradee, c est le mode du marche
    qui a change. Et ca explique que le stop optimal bascule : en tendance
    il faut laisser courir, en range il faudrait couper. Chercher un stop
    fixe qui convienne aux deux est sans espoir.

    Le vrai probleme est ailleurs : SAVOIR DANS QUEL MODE ON EST, avant la
    seance et pas apres.

LA DIFFICULTE, ET POURQUOI LE TYPE DE JOURNEE NE SUFFIT PAS
    profil_jour.csv classe deja les journees en RANGE / MIXTE / TREND, mais
    a partir de la CLOTURE. C est donc descriptif, jamais decidable a
    l ouverture. On l a deja verifie : sur des donnees aleatoires, croiser
    quoi que ce soit avec ce type produit des p a 0,000 par pure
    circularite.

    Tout ce que ce script utilise pour PREDIRE est calcule sur les jours
    PRECEDENTS uniquement, jamais sur le jour courant.

LES QUATRE SECTIONS
    1. le P&L de la stack suit-il vraiment le type de journee ? (descriptif,
       mais c est la verification de l hypothese de depart)
    2. les regimes s agglutinent-ils ? -- matrice de transition et
       autocorrelation de l efficience, sur 128 seances
    3. deux indicateurs glissants CAUSAUX, calcules hors jour courant :
         A  efficience quotidienne moyenne des N derniers jours
         B  efficience MULTI-JOURS : |deplacement net sur N jours| divise
            par la somme des amplitudes quotidiennes. C est la definition
            visuelle du range contre la tendance sur un graphique 4h.
    4. le test operationnel : eviter les seances que l indicateur classe en
       range aurait-il aide ?

    Les sections 2 et 3 reposent sur 128 seances de prix : solides.
    Les sections 1 et 4 reposent sur ~17 seances de P&L : indicatives.
    Cette asymetrie est rappelee dans la sortie.
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


def p_prop(k1, n1, k2, n2):
    if n1 < 5 or n2 < 5:
        return None
    p = (k1 + k2) / float(n1 + n2)
    se = math.sqrt(p * (1 - p) * (1.0 / n1 + 1.0 / n2))
    return p_norm((k1 / float(n1) - k2 / float(n2)) / se) if se else None


def binom(k, n):
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
        o, cl = f(d.get("open")), f(d.get("close"))
        rg, ef = f(d.get("range")), f(d.get("eff"))
        if not j or not a or rg is None or rg <= 0 or cl is None:
            continue
        par.setdefault(a, []).append(
            {"jour": j, "open": o, "close": cl, "range": rg,
             "eff": ef if ef is not None else (abs(cl - o) / rg if o else None),
             "type": (d.get("type") or "").strip().upper()})
    for a in par:
        par[a].sort(key=lambda x: x["jour"])
    print("prix : %d actifs, %d lignes"
          % (len(par), sum(len(v) for v in par.values())))
    return par


def lire_pnl():
    if not os.path.isfile(STOP):
        print("/!\\ %s absent : les sections 1 et 4 seront sautees." % STOP)
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
    """Ajoute a chaque seance deux indicateurs calcules SUR LES JOURS
    PRECEDENTS UNIQUEMENT. Le jour courant n y entre jamais : sans ca
    l indicateur serait circulaire et tout le reste serait faux."""
    for a, s in par.items():
        for i, d in enumerate(s):
            for N in FENETRES:
                h = s[max(0, i - N):i]
                d["indA_%d" % N] = moy([x["eff"] for x in h]) if len(h) == N else None
                if len(h) == N and h[0]["open"] is not None:
                    somme = sum(x["range"] for x in h)
                    net = abs(h[-1]["close"] - h[0]["open"])
                    d["indB_%d" % N] = net / somme if somme > 0 else None
                else:
                    d["indB_%d" % N] = None
    return par


def section1(par, pnl):
    if not pnl:
        return
    print()
    print("=" * 90)
    print("  1. le P&L de la stack suit-il le type de journee ?")
    print("=" * 90)
    print("DESCRIPTIF : le type se calcule sur la cloture, donc apres coup.")
    print("Ce n est pas une regle, c est la verification de l hypothese.")
    lots = {}
    for a, s in par.items():
        for d in s:
            v = pnl.get((d["jour"], a))
            if v is not None and d["type"]:
                lots.setdefault(d["type"], []).append(v)
    if not lots:
        print("  aucun recoupement entre les dates du prix et celles du P&L.")
        return
    print()
    print("  %-14s %6s %12s %12s" % ("type", "N", "total EUR", "moyen EUR"))
    print("  " + "-" * 50)
    for k in ("RANGE", "MIXTE", "TREND_UP", "TREND_DOWN"):
        g = lots.get(k)
        if not g:
            continue
        print("  %-14s %6d %+12.2f %+12.2f" % (k, len(g), sum(g), moy(g)))
    print("  " + "-" * 50)
    tr = lots.get("TREND_UP", []) + lots.get("TREND_DOWN", [])
    ra = lots.get("RANGE", [])
    if len(tr) >= 5 and len(ra) >= 5:
        se = math.sqrt(et(tr) ** 2 / len(tr) + et(ra) ** 2 / len(ra))
        p = p_norm((moy(tr) - moy(ra)) / se) if se else None
        print("  TENDANCE %+.2f contre RANGE %+.2f par couple jour/actif, ecart %+.2f"
              % (moy(tr), moy(ra), moy(tr) - moy(ra)))
        print("  p=%s sur %d contre %d observations"
              % ("%.3f" % p if p is not None else "-", len(tr), len(ra)))


def section2(par):
    print()
    print("=" * 90)
    print("  2. les regimes s agglutinent-ils ? -- 128 seances, resultat solide")
    print("=" * 90)
    print("Si le mode du marche persiste d un jour a l autre, alors la veille")
    print("renseigne sur aujourd hui, et c est une information CAUSALE.")
    print()
    print("  autocorrelation de l efficience (jour t contre jour t-1) :")
    for a, s in sorted(par.items()):
        x = [s[i - 1]["eff"] for i in range(1, len(s))
             if s[i]["eff"] is not None and s[i - 1]["eff"] is not None]
        y = [s[i]["eff"] for i in range(1, len(s))
             if s[i]["eff"] is not None and s[i - 1]["eff"] is not None]
        rho, p = spearman(x, y)
        if rho is None:
            continue
        print("    %-9s N=%d  rho=%+.3f  p=%s" % (a, len(x), rho,
                                                  "%.3f" % p if p is not None else "-"))
    print()
    print("  probabilite d une journee de TENDANCE selon la veille :")
    print("    %-9s %-14s %6s %12s" % ("actif", "veille", "N", "P(tendance)"))
    print("    " + "-" * 46)
    for a, s in sorted(par.items()):
        base = sum(1 for d in s if d["type"].startswith("TREND")) / float(len(s))
        cel = {}
        for i in range(1, len(s)):
            k = "TENDANCE" if s[i - 1]["type"].startswith("TREND") else s[i - 1]["type"]
            if not k:
                continue
            cel.setdefault(k, []).append(1 if s[i]["type"].startswith("TREND") else 0)
        for k in sorted(cel):
            g = cel[k]
            if len(g) < 10:
                continue
            print("    %-9s %-14s %6d %11.0f%%" % (a, k, len(g), 100.0 * sum(g) / len(g)))
        print("    %-9s %-14s %6d %11.0f%%  <- reference" % (a, "toutes", len(s), 100.0 * base))
        print("    " + "-" * 46)


def section3(par):
    print()
    print("=" * 90)
    print("  3. les indicateurs glissants CAUSAUX annoncent-ils la tendance ?")
    print("=" * 90)
    print("A = efficience quotidienne moyenne des N jours precedents")
    print("B = |deplacement net sur N jours| / somme des amplitudes")
    print("    B est la definition visuelle du range contre la tendance.")
    print("Ni l un ni l autre n utilise le jour courant.")
    for nom in ("indA", "indB"):
        print()
        print("  --- %s ---" % nom)
        print("  %-9s %3s %6s %10s %8s %14s"
              % ("actif", "N", "obs", "rho", "p", "P(tend) bas/haut"))
        print("  " + "-" * 62)
        for a, s in sorted(par.items()):
            for N in FENETRES:
                cle = "%s_%d" % (nom, N)
                g = [d for d in s if d.get(cle) is not None and d["eff"] is not None]
                if len(g) < 30:
                    continue
                rho, p = spearman([d[cle] for d in g], [d["eff"] for d in g])
                q = sorted(d[cle] for d in g)
                lo, hi = q[len(q) // 3], q[(2 * len(q)) // 3]
                b = [d for d in g if d[cle] <= lo]
                h = [d for d in g if d[cle] >= hi]
                pb = 100.0 * sum(1 for d in b if d["type"].startswith("TREND")) / max(1, len(b))
                ph = 100.0 * sum(1 for d in h if d["type"].startswith("TREND")) / max(1, len(h))
                pp = p_prop(sum(1 for d in h if d["type"].startswith("TREND")), len(h),
                            sum(1 for d in b if d["type"].startswith("TREND")), len(b))
                print("  %-9s %3d %6d %+10.3f %8s   %3.0f%% / %3.0f%%  p=%s"
                      % (a, N, len(g), rho if rho is not None else 0.0,
                         "%.3f" % p if p is not None else "-", pb, ph,
                         "%.3f" % pp if pp is not None else "-"))
    print()
    print("  rho positif = l indicateur annonce vraiment l efficience du jour.")
    print("  L ecart bas/haut est plus parlant que rho : c est lui qui dirait")
    print("  combien de tendances on capture en ne tradant que le tiers haut.")


def section4(par, pnl):
    if not pnl:
        return
    print()
    print("=" * 90)
    print("  4. eviter les seances classees RANGE aurait-il aide ?")
    print("=" * 90)
    print("INDICATIF SEULEMENT : peu de seances de P&L. Le prix donne 128")
    print("seances, l argent une quinzaine. On regarde le sens, pas le p.")
    for nom in ("indA", "indB"):
        for N in FENETRES:
            cle = "%s_%d" % (nom, N)
            obs = []
            for a, s in par.items():
                for d in s:
                    v = pnl.get((d["jour"], a))
                    if v is not None and d.get(cle) is not None:
                        obs.append((d[cle], v, d["jour"]))
            if len(obs) < 15:
                continue
            obs.sort()
            coup = len(obs) // 2
            bas = [x[1] for x in obs[:coup]]
            haut = [x[1] for x in obs[coup:]]
            pos = sum(1 for x in haut if x > 0)
            print()
            print("  %s sur %d jours -- %d observations" % (nom, N, len(obs)))
            print("    moitie BASSE (regime de range)  : total %+9.2f, moyen %+8.2f"
                  % (sum(bas), moy(bas)))
            print("    moitie HAUTE (regime de tendance): total %+9.2f, moyen %+8.2f"
                  % (sum(haut), moy(haut)))
            print("    en ne tradant que la moitie haute : %+.2f au lieu de %+.2f"
                  % (sum(haut), sum(bas) + sum(haut)))
            print("    (%d observations positives sur %d dans la moitie haute)"
                  % (pos, len(haut)))


def main():
    par = indicateurs(lire_prix())
    pnl = lire_pnl()
    section1(par, pnl)
    section2(par)
    section3(par)
    section4(par, pnl)
    print()
    print("=" * 90)
    print("  ce qui est solide et ce qui ne l est pas")
    print("=" * 90)
    print("SOLIDE : sections 2 et 3, sur 128 seances de prix. Si les regimes")
    print("persistent et qu un indicateur causal les annonce, c est un fait")
    print("de marche, independant de la stack.")
    print()
    print("INDICATIF : sections 1 et 4, sur une quinzaine de seances de P&L.")
    print("Elles disent le SENS, pas l ampleur, et surement pas un seuil.")
    print()
    print("Et le piege habituel : la section 4 coupe a la mediane, ce qui est")
    print("un choix. Ne le transforme pas en regle avant de l avoir gele et")
    print("laisse tourner quinze seances hors echantillon.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
