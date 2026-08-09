# -*- coding: utf-8 -*-
"""
latent_heure.py -- a partir de quelle heure le latent dit-il quelque chose ?

LA QUESTION
    "La premiere heure americaine fait la journee" est un adage de marche.
    On vient de le mesurer sur le PRIX : l amplitude de cette heure annonce
    celle du reste de la seance (rho 0,26 a 0,51) et le P&L des tickets
    ouverts apres (+32,60 contre +1,55 par ticket).

    Reste a le verifier sur le LATENT : a quelle heure le flottant cesse
    d etre du bruit et commence a annoncer la fin de journee ?

CE QU ON MESURE, DANS L ORDRE D UTILITE
    1. profil horaire : quand l exposition se construit
    2. a quelle heure tombent les extremes du flottant
    3. LA QUESTION : correlation entre le flottant a l heure H et
         a) le resultat de TOUTE la journee
         b) le resultat du RESTE de la journee  <- la seule actionnable
       L heure ou (b) devient nette est la reponse.
    4. couper tout a l heure H aurait-il aide ? -- la vieille question du
       seuil de latent, enfin chiffree

AVERTISSEMENT DE TAILLE
    Le latent n existe que sur une poignee de seances : le 04 et le 05
    aout mesures, le 06 et le 07 reconstruits depuis MT5 par
    latent_reconstruire.py. Quatre ou cinq journees la ou le prix en a
    128. Tout ce fichier est une ESQUISSE. Aucune correlation sur cinq
    jours ne prouve quoi que ce soit ; on cherche une FORME, pas un p.

FUSEAU
    Les horodatages du latent viennent de latent_log.py. Le script
    verifie s ils sont sur la meme horloge que churn_trades, qui est en
    heure COURTIER (UTC+3, une heure d avance sur Paris). Sans ce
    controle, une reponse a l heure pres serait fausse d une heure.
"""
import io, os, sys, math, json, glob, datetime as dt

DIR = os.path.join("docs", "latent")
CHURN = [os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
         os.path.join("docs", "churn_trades", "churn_trades.jsonl")]
HEURES = list(range(8, 23))


def moy(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / float(len(xs)) if xs else None


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def p_norm(z):
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))


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
    if len(a) < 5:
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
    if abs(rho) >= 1.0 or n < 5:
        return rho, None
    t = rho * math.sqrt((n - 2) / (1 - rho * rho))
    return rho, p_norm(t)


def parse_ts(v):
    if isinstance(v, (int, float)):
        return dt.datetime.utcfromtimestamp(float(v))
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(str(v)[:19], f)
        except ValueError:
            pass
    return None


def lire():
    fics = sorted(glob.glob(os.path.join(DIR, "latent_*.jsonl")))
    if not fics:
        print("aucun fichier dans %s" % DIR)
        sys.exit(1)
    jours = {}
    for f in fics:
        for l in io.open(f, encoding="utf-8-sig"):
            l = l.strip()
            if not l:
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            t = parse_ts(o.get("ts"))
            if t is None or "floating" not in o:
                continue
            j = t.strftime("%Y-%m-%d")
            jours.setdefault(j, []).append(
                {"t": t, "flot": float(o.get("floating") or 0.0),
                 "eq": float(o.get("equity") or 0.0),
                 "bal": float(o.get("balance") or 0.0),
                 "n": int(o.get("n_pos") or 0),
                 "src": o.get("src") or "mesure"})
    for j in jours:
        jours[j].sort(key=lambda x: x["t"])
    print("%d fichiers, %d journees : %s"
          % (len(fics), len(jours), ", ".join(sorted(jours))))
    rec = sum(1 for j in jours for x in jours[j] if x["src"] == "reconstruit")
    tot = sum(len(v) for v in jours.values())
    if rec:
        print("dont %d echantillons reconstruits sur %d (%.0f%%)"
              % (rec, tot, 100.0 * rec / tot))
    if len(jours) < 8:
        print()
        print("/!\\ %d journees seulement. Ce qui suit est une ESQUISSE :" % len(jours))
        print("    on cherche une FORME dans les courbes, pas une significativite.")
    return jours


def calibrer(jours):
    """Le latent et churn_trades sont-ils sur la meme horloge ?"""
    hl = [x["t"].hour for j in jours for x in jours[j] if x["n"] > 0]
    hc = []
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
            ts = o.get("entry_ts") or ""
            if len(ts) >= 13:
                try:
                    hc.append(int(ts[11:13]))
                except ValueError:
                    pass
    print()
    print("controle de fuseau :")
    if hl:
        print("  latent, echantillons avec positions : %02dh -> %02dh, mediane %02dh"
              % (min(hl), max(hl), med(hl)))
    if hc:
        print("  churn_trades, entrees               : %02dh -> %02dh, mediane %02dh"
              % (min(hc), max(hc), med(hc)))
    if hl and hc and abs(med(hl) - med(hc)) > 1.5:
        print("  /!\\ MEDIANES ECARTEES DE PLUS D UNE HEURE : les deux sources")
        print("      ne sont probablement pas sur la meme horloge. Toute")
        print("      reponse a l heure pres serait fausse.")
    elif hl and hc:
        print("  horloges compatibles. Heure COURTIER, UTC+3 : retranche 1h")
        print("  pour ton heure de Paris. Ouverture cash US a 16h30 courtier.")


def valeur_a(serie, h):
    """Dernier echantillon a ou avant h:59. None si la journee commence apres."""
    cand = [x for x in serie if x["t"].hour <= h]
    return cand[-1] if cand else None


def section1(jours):
    print()
    print("=" * 84)
    print("  1. profil horaire : quand l exposition se construit")
    print("=" * 84)
    print("  %-6s %8s %12s %12s %12s"
          % ("heure", "n_pos", "flottant med", "|flot| med", "|flot| max"))
    print("  " + "-" * 56)
    for h in HEURES:
        xs = [x for j in jours for x in jours[j] if x["t"].hour == h]
        if len(xs) < 5:
            continue
        print("  %02dh    %8.1f %12.0f %12.0f %12.0f"
              % (h, med([x["n"] for x in xs]), med([x["flot"] for x in xs]),
                 med([abs(x["flot"]) for x in xs]),
                 max(abs(x["flot"]) for x in xs)))
    print("  " + "-" * 56)
    print("  |flot| = exposition en valeur absolue, dans les deux sens.")


def section2(jours):
    print()
    print("=" * 84)
    print("  2. a quelle heure tombent les extremes du flottant ?")
    print("=" * 84)
    print("  %-12s %14s %8s %14s %8s"
          % ("jour", "pire flottant", "heure", "meilleur", "heure"))
    print("  " + "-" * 62)
    hb, hh = [], []
    for j in sorted(jours):
        s = jours[j]
        if len(s) < 20:
            continue
        bas = min(s, key=lambda x: x["flot"])
        haut = max(s, key=lambda x: x["flot"])
        hb.append(bas["t"].hour)
        hh.append(haut["t"].hour)
        print("  %-12s %14.0f %8s %14.0f %8s"
              % (j, bas["flot"], bas["t"].strftime("%H:%M"),
                 haut["flot"], haut["t"].strftime("%H:%M")))
    print("  " + "-" * 62)
    if hb:
        print("  heure mediane du PIRE flottant : %02dh   du MEILLEUR : %02dh"
              % (med(hb), med(hh)))


def section3(jours):
    print()
    print("=" * 84)
    print("  3. LA QUESTION : a quelle heure le flottant devient-il informatif ?")
    print("=" * 84)
    print("(a) contre le resultat de TOUTE la journee -- descriptif")
    print("(b) contre le resultat du RESTE de la journee -- LA colonne utile :")
    print("    a l heure H, mon flottant annonce-t-il ce qui reste a venir ?")
    print()
    print("  %-6s %6s %10s %8s %10s %8s"
          % ("heure", "N", "rho (a)", "p", "rho (b)", "p"))
    print("  " + "-" * 54)
    for h in HEURES:
        fl, tot, reste = [], [], []
        for j in sorted(jours):
            s = jours[j]
            if len(s) < 20:
                continue
            v = valeur_a(s, h)
            if v is None or v["t"].hour < h:
                continue
            fl.append(v["flot"])
            tot.append(s[-1]["eq"] - s[0]["eq"])
            reste.append(s[-1]["eq"] - v["eq"])
        if len(fl) < 4:
            continue
        ra, pa = spearman(fl, tot)
        rb, pb = spearman(fl, reste)
        print("  %02dh    %6d %+10.3f %8s %+10.3f %8s"
              % (h, len(fl), ra or 0, "%.3f" % pa if pa is not None else "-",
                 rb or 0, "%.3f" % pb if pb is not None else "-"))
    print("  " + "-" * 54)
    print("  Colonne (b) proche de 0 = le flottant a cette heure ne dit rien")
    print("  de la suite. Nettement NEGATIVE = un gros flottant positif est")
    print("  suivi d une degradation, donc il faudrait encaisser.")
    print("  Sur %d journees, ne lis que la FORME de la colonne." % len(jours))


def section4(jours):
    print()
    print("=" * 84)
    print("  4. couper tout a l heure H aurait-il aide ?")
    print("=" * 84)
    print("La vieille question du seuil de latent, enfin chiffree : on compare")
    print("l equity a l heure H a celle de la fin de journee.")
    print()
    print("  %-6s %6s %14s %14s %12s"
          % ("heure", "N", "en coupant", "en laissant", "ecart"))
    print("  " + "-" * 58)
    for h in HEURES:
        a, b = [], []
        for j in sorted(jours):
            s = jours[j]
            if len(s) < 20:
                continue
            v = valeur_a(s, h)
            if v is None or v["t"].hour < h:
                continue
            a.append(v["eq"] - s[0]["eq"])
            b.append(s[-1]["eq"] - s[0]["eq"])
        if len(a) < 4:
            continue
        print("  %02dh    %6d %14.0f %14.0f %12.0f"
              % (h, len(a), sum(a), sum(b), sum(a) - sum(b)))
    print("  " + "-" * 58)
    print("  Ecart positif = couper a cette heure aurait rapporte plus que")
    print("  laisser courir. Attention : sur %d journees, une seule mauvaise"
          % len(jours))
    print("  fin de seance suffit a creer un ecart qui n existe pas.")


def main():
    jours = lire()
    if not jours:
        return 1
    calibrer(jours)
    section1(jours)
    section2(jours)
    section3(jours)
    section4(jours)
    print()
    print("=" * 84)
    print("  ce qu il faut en attendre")
    print("=" * 84)
    print("Avec %d journees, aucun p n a de sens. Ce qui compte est de voir" % len(jours))
    print("SI la colonne (b) de la section 3 change de nature autour de 16h30")
    print("courtier -- l ouverture cash americaine. Si le flottant ne dit rien")
    print("avant et quelque chose apres, l adage tient aussi sur ton compte.")
    print()
    print("Et il faudra relancer ce script dans quelques semaines : le latent")
    print("s accumule maintenant que run_latent_loop.bat est en place, alors")
    print("qu il etait mort avant le 07/08.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
