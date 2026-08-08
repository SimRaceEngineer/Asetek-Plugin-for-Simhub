# -*- coding: utf-8 -*-
"""
croisements.py -- interroge profil_jour.csv, ne recharge rien depuis MT5.

Repond a quatre questions posees dans l ordre :
  1. le type de journee change-t-il la casse et l extension ?
  2. la largeur du matin, connue a 14h30, la change-t-elle ? (causal, lui)
  3. l ouverture hors de la value area de la veille la change-t-elle ?
  4. l extension s arrete-t-elle SUR les niveaux de la veille, ou juste
     quelque part ? -- test de permutation + test de franchissement.

Aucun scipy. Aucune ecriture dans les panels.
"""
import io, os, sys, math, random

FIC = "profil_jour.csv"
MIN_N = 20              # sous ce seuil on affiche mais on marque la cellule
SEUIL_PROX = 0.10       # "arrive au contact" = a moins de 0,10 range AM du niveau
random.seed(20260808)   # permutation reproductible


# --------------------------------------------------------------- lecture
def f(v):
    """float ou None -- les prev_* manquent le premier jour de chaque actif."""
    if v is None:
        return None
    v = v.strip().replace(",", ".")
    if v == "" or v.upper() in ("NA", "NONE", "NAN"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def lire(chemin):
    if not os.path.isfile(chemin):
        print("introuvable : %s" % chemin)
        print("lance d abord profil_jour.py")
        sys.exit(1)
    lignes = [l.rstrip("\n") for l in io.open(chemin, encoding="utf-8-sig") if l.strip()]
    sep = ";" if lignes[0].count(";") >= lignes[0].count(",") else ","
    ent = [c.strip() for c in lignes[0].split(sep)]
    out = []
    for l in lignes[1:]:
        c = l.split(sep)
        if len(c) < len(ent):
            c = c + [""] * (len(ent) - len(c))
        out.append(dict(zip(ent, c)))
    print("%s : %d lignes, %d colonnes, separateur '%s'" % (chemin, len(out), len(ent), sep))
    manque = [k for k in ("jour", "asset", "am_range", "am_low", "am_high") if k not in ent]
    if manque:
        print("colonnes absentes : %s -- le fichier n est pas celui attendu" % ", ".join(manque))
        sys.exit(1)
    return out, ent


# ------------------------------------------------------------ statistique
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
    m = sum(xs) / float(len(xs))
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def p_normale(z):
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))


def t_deux(a, b):
    """Welch sur deux listes. Renvoie (ecart, p) ou (None, None)."""
    a = [x for x in a if x is not None]
    b = [x for x in b if x is not None]
    if len(a) < 3 or len(b) < 3:
        return None, None
    ma, mb = moy(a), moy(b)
    se = math.sqrt(et(a) ** 2 / len(a) + et(b) ** 2 / len(b))
    if se == 0:
        return ma - mb, None
    return ma - mb, p_normale((ma - mb) / se)


def p_prop(k1, n1, k2, n2):
    """Difference de deux proportions, approximation normale."""
    if n1 < 3 or n2 < 3:
        return None
    p1, p2 = k1 / float(n1), k2 / float(n2)
    p = (k1 + k2) / float(n1 + n2)
    se = math.sqrt(p * (1 - p) * (1.0 / n1 + 1.0 / n2))
    if se == 0:
        return None
    return p_normale((p1 - p2) / se)


# ------------------------------------------------------------ preparation
def preparer(rows):
    """Recalcule tout depuis les colonnes brutes -- on ne fait confiance
    a aucune colonne derivee sans la verifier."""
    ok, ecarts = [], 0
    for r in rows:
        d = {"jour": r.get("jour", "").strip(), "asset": r.get("asset", "").strip(),
             "type": (r.get("type") or "").strip().upper()}
        for k in ("open", "high", "low", "close", "range", "eff",
                  "am_high", "am_low", "am_range", "pm_high", "pm_low",
                  "poc", "vah", "val",
                  "prev_poc", "prev_vah", "prev_val",
                  "prev_high", "prev_low", "prev_close"):
            d[k] = f(r.get(k))
        d["am_dir"] = (r.get("am_dir") or "").strip().upper()
        ova = (r.get("ouv_vs_prev_va") or "").strip()
        d["ouv_va"] = ova.upper() if f(ova) is None else None
        d["ouv_va_num"] = f(ova)

        if d["am_range"] is None or d["am_range"] <= 0:
            continue
        if d["am_low"] is None or d["am_high"] is None:
            continue

        # casse et extension recalculees ; on compare a la colonne si elle existe
        if d["pm_low"] is not None:
            d["casse_bas"] = 1 if d["pm_low"] < d["am_low"] else 0
            d["ext_bas"] = max(0.0, (d["am_low"] - d["pm_low"]) / d["am_range"])
        else:
            d["casse_bas"], d["ext_bas"] = None, None
        if d["pm_high"] is not None:
            d["casse_haut"] = 1 if d["pm_high"] > d["am_high"] else 0
            d["ext_haut"] = max(0.0, (d["pm_high"] - d["am_high"]) / d["am_range"])
        else:
            d["casse_haut"], d["ext_haut"] = None, None
        for col, val in (("ext_bas", d["ext_bas"]), ("ext_haut", d["ext_haut"])):
            v = f(r.get(col))
            if v is not None and val is not None and abs(v - val) > 0.02:
                ecarts += 1
        ok.append(d)
    if ecarts:
        print("/!\\ %d ecarts entre extension recalculee et colonne du CSV "
              "-- j utilise la recalculee." % ecarts)
    return ok


def largeur_am(rows, fenetre=20):
    """Bande de largeur du matin, mediane glissante par actif, SANS le jour
    courant : disponible a 14h30, donc utilisable en decision."""
    par = {}
    for d in rows:
        par.setdefault(d["asset"], []).append(d)
    for a in par:
        s = sorted(par[a], key=lambda x: x["jour"])
        for i, d in enumerate(s):
            hist = [x["am_range"] for x in s[max(0, i - fenetre):i]]
            if len(hist) < 10:
                d["am_larg"] = ""
                continue
            m = med(hist)
            r = d["am_range"] / m
            d["am_larg"] = "ETROIT" if r < 0.75 else ("LARGE" if r > 1.30 else "NORMAL")
            d["am_ratio"] = r


# ---------------------------------------------------------------- tableaux
def tab_casse(rows, cle, titre, ordre=None):
    print()
    print("=" * 88)
    print("  " + titre)
    print("=" * 88)
    groupes = {}
    for d in rows:
        k = d.get(cle)
        if k in (None, ""):
            continue
        groupes.setdefault(k, []).append(d)
    if not groupes:
        print("  colonne '%s' vide -- rien a croiser." % cle)
        return {}
    cles = ordre if ordre else sorted(groupes)
    print("%-14s %5s | %7s %8s %8s | %7s %8s %8s"
          % ("", "N", "P(bas)", "ext moy", "ext med", "P(haut)", "ext moy", "ext med"))
    print("-" * 88)
    for k in cles:
        g = groupes.get(k)
        if not g:
            continue
        cb = [d["casse_bas"] for d in g if d["casse_bas"] is not None]
        ch = [d["casse_haut"] for d in g if d["casse_haut"] is not None]
        eb = [d["ext_bas"] for d in g if d["casse_bas"] == 1]
        eh = [d["ext_haut"] for d in g if d["casse_haut"] == 1]
        mk = "" if len(g) >= MIN_N else "  (faible)"
        print("%-14s %5d | %6.0f%% %8.2f %8.2f | %6.0f%% %8.2f %8.2f%s"
              % (k, len(g),
                 100.0 * sum(cb) / max(1, len(cb)), moy(eb) or 0, med(eb) or 0,
                 100.0 * sum(ch) / max(1, len(ch)), moy(eh) or 0, med(eh) or 0, mk))
    print("-" * 88)
    # comparaisons deux a deux sur la casse basse et sur l extension basse
    dispo = [k for k in cles if k in groupes and len(groupes[k]) >= 3]
    if len(dispo) >= 2:
        print("comparaisons (casse basse, puis extension basse) :")
        for i in range(len(dispo)):
            for j in range(i + 1, len(dispo)):
                a, b = groupes[dispo[i]], groupes[dispo[j]]
                ka = sum(d["casse_bas"] for d in a if d["casse_bas"] is not None)
                na = len([d for d in a if d["casse_bas"] is not None])
                kb = sum(d["casse_bas"] for d in b if d["casse_bas"] is not None)
                nb = len([d for d in b if d["casse_bas"] is not None])
                pp = p_prop(ka, na, kb, nb)
                ea = [d["ext_bas"] for d in a if d["casse_bas"] == 1]
                ebb = [d["ext_bas"] for d in b if d["casse_bas"] == 1]
                ec, pe = t_deux(ea, ebb)
                print("  %-12s vs %-12s  casse %+5.1f pt p=%s | ext %s p=%s"
                      % (dispo[i], dispo[j],
                         100.0 * (ka / float(max(1, na)) - kb / float(max(1, nb))),
                         "%.3f" % pp if pp is not None else "-",
                         "%+.2f" % ec if ec is not None else "  -  ",
                         "%.3f" % pe if pe is not None else "-"))
    return groupes


# ------------------------------------------------- test des appuis (niveaux)
NIVEAUX_BAS = [("prev_val", "VAL veille"), ("prev_poc", "POC veille"),
               ("prev_low", "bas veille"), ("prev_close", "cloture veille")]
NIVEAUX_HAUT = [("prev_vah", "VAH veille"), ("prev_poc", "POC veille"),
                ("prev_high", "haut veille"), ("prev_close", "cloture veille")]


def test_arret(rows):
    """L extension se termine-t-elle PRES d un niveau de la veille ?
    Controle par permutation : on rejoue le meme calcul avec les niveaux
    d une autre journee du meme actif. Si le vrai niveau n est pas plus
    proche que le faux, il n y a pas d appui, seulement de la coincidence."""
    print()
    print("=" * 88)
    print("  4a. l extension s arrete-t-elle SUR un niveau de la veille ?")
    print("=" * 88)
    print("distance |bas du PM - niveau| en unites de range du matin.")
    print("temoin = le meme niveau pris sur une autre seance du meme actif.")
    print()
    print("%-16s %5s %9s %9s %9s %9s %8s"
          % ("niveau", "N", "med reel", "med temoin", "moy reel", "moy tem.", "p"))
    print("-" * 88)
    par_actif = {}
    for d in rows:
        par_actif.setdefault(d["asset"], []).append(d)

    for col, lib in NIVEAUX_BAS:
        reels, temoins = [], []
        for a, g in par_actif.items():
            dispo = [d for d in g if d.get(col) is not None]
            for d in g:
                if d.get("casse_bas") != 1 or d.get("pm_low") is None:
                    continue
                if d.get(col) is None or not dispo:
                    continue
                reels.append(abs(d["pm_low"] - d[col]) / d["am_range"])
                autre = random.choice([x for x in dispo if x["jour"] != d["jour"]] or dispo)
                temoins.append(abs(d["pm_low"] - autre[col]) / d["am_range"])
        if len(reels) < 5:
            print("%-16s %5d   (trop peu)" % (lib, len(reels)))
            continue
        ec, p = t_deux(reels, temoins)
        print("%-16s %5d %9.2f %9.2f %9.2f %9.2f %8s"
              % (lib, len(reels), med(reels), med(temoins),
                 moy(reels), moy(temoins), "%.3f" % p if p is not None else "-"))
    print("-" * 88)
    print("med reel nettement < med temoin = le niveau attire vraiment le bas du PM.")
    print("les deux medianes proches = le niveau n explique rien.")


def test_franchissement(rows):
    """Le vrai test d appui : sachant que le prix est ARRIVE AU CONTACT du
    niveau (a moins de SEUIL_PROX range AM au-dessus), le franchit-il ?
    S il y a un appui, la probabilite de franchir doit tomber. Si elle reste
    au niveau du hazard de fond deja mesure (plat), il n y a pas d appui."""
    print()
    print("=" * 88)
    print("  4b. arrive au contact du niveau, le prix le franchit-il ?")
    print("=" * 88)
    print("contact = bas du PM descend a moins de %.2f range AM au-dessus du niveau"
          % SEUIL_PROX)
    print("(on ne retient que les niveaux situes SOUS le bas du matin :")
    print(" au-dessus, la question ne se pose pas.)")
    print()
    print("%-16s %7s %9s %11s %10s"
          % ("niveau", "contacts", "franchis", "P(franchir)", "temoin"))
    print("-" * 88)
    par_actif = {}
    for d in rows:
        par_actif.setdefault(d["asset"], []).append(d)

    for col, lib in NIVEAUX_BAS:
        contacts, franchis = 0, 0
        t_contacts, t_franchis = 0, 0
        for a, g in par_actif.items():
            dispo = [d for d in g if d.get(col) is not None]
            for d in g:
                if d.get("pm_low") is None or d.get(col) is None:
                    continue
                for niv, compteurs in ((d[col], 0),
                                       (random.choice([x for x in dispo
                                                       if x["jour"] != d["jour"]] or dispo)[col], 1)):
                    if niv is None or niv >= d["am_low"]:
                        continue           # niveau au-dessus du bas du matin
                    marge = (d["pm_low"] - niv) / d["am_range"]
                    if marge > SEUIL_PROX:
                        continue           # jamais arrive au contact
                    if compteurs == 0:
                        contacts += 1
                        if d["pm_low"] < niv:
                            franchis += 1
                    else:
                        t_contacts += 1
                        if d["pm_low"] < niv:
                            t_franchis += 1
        if contacts < 5:
            print("%-16s %7d   (trop peu de contacts)" % (lib, contacts))
            continue
        pv = 100.0 * franchis / contacts
        pt = 100.0 * t_franchis / max(1, t_contacts)
        pp = p_prop(franchis, contacts, t_franchis, max(1, t_contacts))
        print("%-16s %7d %9d %10.0f%% %9.0f%%   p=%s"
              % (lib, contacts, franchis, pv, pt,
                 "%.3f" % pp if pp is not None else "-"))
    print("-" * 88)
    print("P(franchir) bien en dessous du temoin = appui reel.")
    print("P(franchir) egale au temoin = le niveau ne retient rien.")


# ------------------------------------------------------- objectifs de gain
PAS_TP = [0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00, 2.50, 3.00]


def echelle_tp(rows, sens="bas"):
    """Le hazard est plat, donc la loi est sans memoire : attendre l epuisement
    n a pas de sens, il n y en a pas. Ce qui fixe le TP, c est l arithmetique.

    S(x)   = P(l extreme du PM atteint x) = taux de remplissage d un TP a x
             pose a la cassure.
    x*S(x) = ce qu on encaisse si on n est paye QUE lorsque le TP est touche.
             Borne basse.
    E[min] = ce qu on encaisserait en sortant a l extreme quand le TP n est
             pas touche. Borne haute, inatteignable en pratique.
    Le vrai resultat est entre les deux. L optimum est la ou x*S(x) culmine."""
    cl_c = "casse_" + sens
    cl_e = "ext_" + sens
    print()
    print("=" * 88)
    print("  7. echelle d objectif -- debordement vers le %s" % ("bas" if sens == "bas" else "haut"))
    print("=" * 88)
    print("x en unites de range du matin. TP dynamique, recalcule chaque jour a 14h30.")
    par = {"TOUS": rows}
    for d in rows:
        par.setdefault(d["asset"], []).append(d)
    for a in ["TOUS"] + sorted(k for k in par if k != "TOUS"):
        g = [d for d in par[a] if d.get(cl_c) == 1 and d.get(cl_e) is not None]
        n_tot = len([d for d in par[a] if d.get(cl_c) is not None])
        if len(g) < 10:
            continue
        rm = med([d["am_range"] for d in g])
        print()
        print("%-10s %d cassures / %d seances (%.0f%%)   range AM median %.1f pts"
              % (a, len(g), n_tot, 100.0 * len(g) / max(1, n_tot), rm or 0))
        print("  %6s %8s %9s %9s %9s %9s"
              % ("x", "S(x)", "x*S(x)", "E[min]", "TP en pts", "N restant"))
        best = None
        for x in PAS_TP:
            atteint = [d for d in g if d[cl_e] >= x]
            s = len(atteint) / float(len(g))
            emin = moy([min(d[cl_e], x) for d in g])
            if best is None or x * s > best[1]:
                best = (x, x * s)
            print("  %6.2f %7.0f%% %9.3f %9.3f %9.1f %9d"
                  % (x, 100.0 * s, x * s, emin, x * (rm or 0), len(atteint)))
        print("  -> optimum de x*S(x) a x = %.2f  (soit %.0f pts au range median)"
              % (best[0], best[0] * (rm or 0)))
    print("-" * 88)
    print("Attention : S(x) est le taux de remplissage du TP, pas le resultat")
    print("du trade. La jambe stop n est pas dans ce fichier -- il n y a pas")
    print("de chemin intra-seance dans profil_jour.csv, seulement les extremes.")
    print("Ce tableau dimensionne l objectif, il ne chiffre pas l esperance.")


def fade_extension(rows, sens="bas"):
    """La question que le hazard plat NE tranche PAS : le prix revient-il ?
    Le hazard dit jusqu ou va l extreme. Il ne dit rien du retour. On mesure
    donc, sachant que la cassure a atteint x, si la CLOTURE est revenue
    dans le range du matin. C est la jambe reverse, et elle est licite."""
    cl_c = "casse_" + sens
    cl_e = "ext_" + sens
    borne = "am_low" if sens == "bas" else "am_high"
    print()
    print("=" * 88)
    print("  8. fade de l extension -- la cloture revient-elle dans le range AM ?")
    print("=" * 88)
    print("sachant que la cassure vers le %s a atteint x : P(cloture revenue"
          % ("bas" if sens == "bas" else "haut"))
    print("a l interieur du range du matin), et de combien elle est revenue.")
    print()
    print("  %8s %7s %14s %12s %12s"
          % ("x atteint", "N", "P(retour dedans)", "retour med", "retour moy"))
    print("-" * 88)
    g = [d for d in rows if d.get(cl_c) == 1 and d.get(cl_e) is not None
         and d.get("close") is not None and d.get(borne) is not None]
    if len(g) < 10:
        print("  trop peu de cassures exploitables (%d)" % len(g))
        return
    for x in PAS_TP:
        lot = [d for d in g if d[cl_e] >= x]
        if len(lot) < 5:
            print("  %8.2f %7d   (trop peu)" % (x, len(lot)))
            continue
        if sens == "bas":
            dedans = [d for d in lot if d["close"] > d[borne]]
            ret = [(d["close"] - d["pm_low"]) / d["am_range"] for d in lot]
        else:
            dedans = [d for d in lot if d["close"] < d[borne]]
            ret = [(d["pm_high"] - d["close"]) / d["am_range"] for d in lot]
        mk = "" if len(lot) >= MIN_N else "  (faible)"
        print("  %8.2f %7d %13.0f%% %12.2f %12.2f%s"
              % (x, len(lot), 100.0 * len(dedans) / len(lot),
                 med(ret) or 0, moy(ret) or 0, mk))
    print("-" * 88)
    print("P(retour) qui MONTE avec x = plus ca deborde, plus ca se paie au")
    print("retour : le fade a un fondement. P(retour) plate = le debordement")
    print("ne se rembourse pas, et seule la jambe continuation tient.")
    print("'retour' = distance de l extreme a la cloture, en range AM : c est")
    print("le gisement maximum d un fade tenu jusqu a la cloture.")


# ---------------------------------------------------------------- croises
def croise_deux(rows, c1, c2, titre):
    print()
    print("=" * 88)
    print("  " + titre)
    print("=" * 88)
    cells = {}
    for d in rows:
        k1, k2 = d.get(c1), d.get(c2)
        if k1 in (None, "") or k2 in (None, ""):
            continue
        cells.setdefault((k1, k2), []).append(d)
    if not cells:
        print("  croisement vide.")
        return
    k1s = sorted({k for k, _ in cells})
    k2s = sorted({k for _, k in cells})
    print("%-14s %s" % ("", " ".join("%18s" % k for k in k2s)))
    for a in k1s:
        bouts = []
        for b in k2s:
            g = cells.get((a, b), [])
            if not g:
                bouts.append("%18s" % "-")
                continue
            cb = [d["casse_bas"] for d in g if d["casse_bas"] is not None]
            eb = [d["ext_bas"] for d in g if d["casse_bas"] == 1]
            mk = "*" if len(g) < MIN_N else " "
            bouts.append("%17s%s" % ("%d %.0f%% %.2f"
                                     % (len(g), 100.0 * sum(cb) / max(1, len(cb)),
                                        moy(eb) or 0), mk))
        print("%-14s %s" % (a, " ".join(bouts)))
    print("-" * 88)
    print("cellule = N, P(casse basse), extension basse moyenne. * = moins de %d." % MIN_N)


# ------------------------------------------------------------------- main
def main():
    chemin = sys.argv[1] if len(sys.argv) > 1 else FIC
    brut, ent = lire(chemin)
    rows = preparer(brut)
    if not rows:
        print("aucune ligne exploitable.")
        return 1
    jours = sorted({d["jour"] for d in rows})
    actifs = sorted({d["asset"] for d in rows})
    print("exploitable : %d lignes, %d seances, %s -> %s, actifs %s"
          % (len(rows), len(jours), jours[0], jours[-1], ", ".join(actifs)))
    largeur_am(rows)

    ref_cb = [d["casse_bas"] for d in rows if d["casse_bas"] is not None]
    ref_ch = [d["casse_haut"] for d in rows if d["casse_haut"] is not None]
    print("reference tous actifs : P(casse basse) %.0f%%  P(casse haute) %.0f%%"
          % (100.0 * sum(ref_cb) / max(1, len(ref_cb)),
             100.0 * sum(ref_ch) / max(1, len(ref_ch))))

    tab_casse(rows, "asset", "0. rappel par actif")

    tab_casse(rows, "type",
              "1. par type de journee -- DESCRIPTIF, PAS PREDICTIF\n"
              "     ('type' se calcule sur la cloture, donc apres la casse : "
              "on ne peut pas s en servir a 14h30)",
              ordre=["RANGE", "MIXTE", "TREND_UP", "TREND_DOWN"])

    tab_casse(rows, "am_larg",
              "2. par largeur du matin -- CAUSAL (mediane des 20 seances "
              "precedentes, connue a 14h30)",
              ordre=["ETROIT", "NORMAL", "LARGE"])

    tab_casse(rows, "am_dir", "3. par direction du matin")

    if any(d.get("ouv_va") for d in rows):
        tab_casse(rows, "ouv_va", "4. par ouverture vs value area de la veille")
    else:
        print("\n(colonne ouv_vs_prev_va numerique ou vide : pas de bandes a croiser)")

    test_arret(rows)
    test_franchissement(rows)

    echelle_tp(rows, "bas")
    echelle_tp(rows, "haut")
    fade_extension(rows, "bas")
    fade_extension(rows, "haut")

    croise_deux(rows, "am_larg", "am_dir",
                "5. croise : largeur du matin x direction du matin")
    if any(d.get("ouv_va") for d in rows):
        croise_deux(rows, "am_larg", "ouv_va",
                    "6. croise : largeur du matin x ouverture vs VA veille")

    print()
    print("=" * 88)
    print("  lecture")
    print("=" * 88)
    print("- section 1 est descriptive : elle ne se decide pas a 14h30.")
    print("- section 2 est la seule utilisable en decision sur la largeur.")
    print("- 4a et 4b tranchent les appuis. Le temoin est la reference,")
    print("  pas zero : une distance mediane de 0,3 range AM n a de sens")
    print("  que comparee aux 0,3 du niveau bidon.")
    print("- 7 dimensionne l objectif de continuation, 8 dit si le fade")
    print("  a un fondement. Les deux sont en range du matin, jamais en")
    print("  points fixes : l echelle se recalcule a 14h30.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
