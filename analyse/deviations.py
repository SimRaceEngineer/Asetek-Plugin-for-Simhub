# -*- coding: utf-8 -*-
"""
deviations.py -- les grandes deviations traitees comme une POPULATION.

CE QUI CHANGE PAR RAPPORT A TOUT CE QU ON A FAIT
    Jusqu ici 2,5x n etait qu un point sur une courbe de survie. Ici les
    seances qui atteignent 2x, 2,5x ou 3x deviennent un groupe a part
    entiere, qu on decrit et qu on compare au reste.

LES QUATRE QUESTIONS
    1. QUI sont ces seances ? Sont-elles reconnaissables A 14h30, avant
       que la deviation ait lieu ? Si oui c est exploitable, si non c est
       une constatation de fin de journee.

    2. LE REBOND DE FIN DE COURBE EST-IL REEL ? La probabilite de retour
       dans le range du matin decroit proprement de 47%% a 13%%... puis
       remonte a 18%% et 17%% a 2,50x et 3,00x, avec le retour median qui
       saute de 0,97 a 1,49. C est la SEULE non-monotonie de toute
       l etude, sur N=38 et N=30. Profil d un retournement de
       capitulation -- ou du bruit. On tranche formellement ici.

    3. LA MEMOIRE REVIENT-ELLE LOIN ? Le hazard est plat partout, donc
       sachant qu on a atteint 2x, la suite devrait ressembler exactement
       au depart. On le verifie directement plutot que par bandes.

    4. LES DEUX BORNES ONT-ELLES CEDE ? Une deviation de 2,5x vers le bas
       dans une seance qui a aussi casse son plus haut n est pas le meme
       animal qu une tendance propre. Personne n a jamais separe les deux.

Aucune ecriture, aucun MT5. Lit profil_jour.csv.
"""
import io, os, sys, math

FIC = "profil_jour.csv"
SEUILS = [2.0, 2.5, 3.0]
FENETRE = 20
MIN_N = 15


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
    if se == 0:
        return None
    return p_norm((k1 / float(n1) - k2 / float(n2)) / se)


def t_deux(a, b):
    a = [x for x in a if x is not None]
    b = [x for x in b if x is not None]
    if len(a) < 3 or len(b) < 3:
        return None, None
    e = moy(a) - moy(b)
    se = math.sqrt(et(a) ** 2 / len(a) + et(b) ** 2 / len(b))
    return e, (p_norm(e / se) if se else None)


def lire():
    if not os.path.isfile(FIC):
        print("introuvable : %s -- lance profil_jour.py" % FIC)
        sys.exit(1)
    lg = [l.rstrip("\n") for l in io.open(FIC, encoding="utf-8-sig") if l.strip()]
    sep = ";" if lg[0].count(";") >= lg[0].count(",") else ","
    ent = [c.strip() for c in lg[0].split(sep)]
    rows = []
    for l in lg[1:]:
        c = l.split(sep)
        if len(c) < len(ent):
            c += [""] * (len(ent) - len(c))
        d0 = dict(zip(ent, c))
        d = {"jour": (d0.get("jour") or "").strip(),
             "asset": (d0.get("asset") or "").strip(),
             "type": (d0.get("type") or "").strip().upper(),
             "am_dir": (d0.get("am_dir") or "").strip().upper(),
             "ouv_va": (d0.get("ouv_vs_prev_va") or "").strip().upper()}
        for k in ("open", "close", "am_high", "am_low", "am_range",
                  "pm_high", "pm_low"):
            d[k] = f(d0.get(k))
        if not d["am_range"] or d["am_range"] <= 0:
            continue
        if d["am_low"] is None or d["am_high"] is None:
            continue
        d["casse_bas"] = 1 if (d["pm_low"] is not None and d["pm_low"] < d["am_low"]) else 0
        d["casse_haut"] = 1 if (d["pm_high"] is not None and d["pm_high"] > d["am_high"]) else 0
        d["ext_bas"] = (max(0.0, (d["am_low"] - d["pm_low"]) / d["am_range"])
                        if d["pm_low"] is not None else None)
        d["ext_haut"] = (max(0.0, (d["pm_high"] - d["am_high"]) / d["am_range"])
                         if d["pm_high"] is not None else None)
        rows.append(d)
    # bande de largeur du matin, mediane glissante SANS le jour courant :
    # disponible a 14h30, donc utilisable en decision
    par = {}
    for d in rows:
        par.setdefault(d["asset"], []).append(d)
    for a in par:
        s = sorted(par[a], key=lambda x: x["jour"])
        for i, d in enumerate(s):
            h = [x["am_range"] for x in s[max(0, i - FENETRE):i]]
            d["larg"] = ""
            if len(h) >= 10:
                q = d["am_range"] / med(h)
                d["larg"] = "ETROIT" if q < 0.75 else ("LARGE" if q > 1.30 else "NORMAL")
    print("%d lignes, %d actifs, %s -> %s"
          % (len(rows), len({d["asset"] for d in rows}),
             min(d["jour"] for d in rows), max(d["jour"] for d in rows)))
    return rows


# ------------------------------------------ 1. qui sont ces seances ?
def qui(rows, sens):
    cle = "ext_" + sens
    print()
    print("=" * 92)
    print("  1. les grandes deviations sont-elles reconnaissables A 14h30 ? (%s)" % sens)
    print("=" * 92)
    print("On compare les seances qui ATTEINDRONT le seuil aux autres, sur des")
    print("caracteristiques toutes connues avant l ouverture US. Un ecart net")
    print("serait exploitable ; rien du tout signifie qu on ne peut que constater.")
    base = [d for d in rows if d[cle] is not None]
    for seuil in SEUILS:
        gros = [d for d in base if d[cle] >= seuil]
        autres = [d for d in base if d[cle] < seuil]
        if len(gros) < MIN_N:
            print("\n  seuil %.1fx : %d seances seulement -- trop peu." % (seuil, len(gros)))
            continue
        print()
        print("  seuil %.1fx : %d seances sur %d (%.0f%%)"
              % (seuil, len(gros), len(base), 100.0 * len(gros) / len(base)))
        for champ, lib in (("larg", "largeur du matin"), ("am_dir", "direction du matin"),
                           ("ouv_va", "ouverture vs VA veille"), ("asset", "actif")):
            vals = sorted({d[champ] for d in base if d[champ]})
            if len(vals) < 2:
                continue
            bouts = []
            for v in vals:
                ng = sum(1 for d in gros if d[champ] == v)
                nb = sum(1 for d in base if d[champ] == v)
                if nb < 10:
                    continue
                p = p_prop(ng, nb,
                           sum(1 for d in base if d[champ] != v and d[cle] >= seuil),
                           sum(1 for d in base if d[champ] != v))
                bouts.append("%s %.0f%%%s" % (v[:9], 100.0 * ng / nb,
                                              "*" if (p is not None and p < 0.05) else ""))
            if bouts:
                print("    %-24s %s" % (lib, "   ".join(bouts)))
    print()
    print("  Chaque pourcentage = part des seances de ce groupe qui atteignent")
    print("  le seuil. * = p<0,05 contre le reste, MAIS on teste beaucoup de")
    print("  cellules ici : une etoile isolee ne vaut rien.")


# --------------------------------------- 2. le rebond de fin de courbe
def rebond(rows, sens):
    cle = "ext_" + sens
    borne = "am_low" if sens == "bas" else "am_high"
    print()
    print("=" * 92)
    print("  2. le rebond de fin de courbe est-il reel ? (%s)" % sens)
    print("=" * 92)
    g = [d for d in rows if d["casse_" + sens] == 1 and d[cle] is not None
         and d["close"] is not None and d[borne] is not None]
    if len(g) < 40:
        print("  trop peu de cassures (%d)." % len(g))
        return

    def dedans(d):
        return (d["close"] > d[borne]) if sens == "bas" else (d["close"] < d[borne])

    bandes = [(0.0, 1.0, "0 a 1x"), (1.0, 2.5, "1 a 2,5x"), (2.5, 99.0, "2,5x et plus")]
    print("  %-14s %6s %14s %12s" % ("bande", "N", "P(retour dedans)", "retour med"))
    print("  " + "-" * 60)
    lots = {}
    for lo, hi, lib in bandes:
        lot = [d for d in g if lo <= d[cle] < hi]
        lots[lib] = lot
        if not lot:
            continue
        k = sum(1 for d in lot if dedans(d))
        ret = [((d["close"] - d["pm_low"]) if sens == "bas"
                else (d["pm_high"] - d["close"])) / d["am_range"] for d in lot]
        print("  %-14s %6d %13.0f%% %12.2f" % (lib, len(lot), 100.0 * k / len(lot), med(ret)))
    print("  " + "-" * 60)
    a, b = lots["1 a 2,5x"], lots["2,5x et plus"]
    if len(a) >= 10 and len(b) >= 10:
        ka = sum(1 for d in a if dedans(d))
        kb = sum(1 for d in b if dedans(d))
        p = p_prop(kb, len(b), ka, len(a))
        ecart = 100.0 * (kb / float(len(b)) - ka / float(len(a)))
        print("  bande extreme contre bande mediane : %+.1f points, p=%s"
              % (ecart, "%.3f" % p if p is not None else "-"))
        if p is not None and p < 0.05 and ecart > 0:
            print("  -> le rebond RESISTE au test. Rare et interessant.")
        else:
            print("  -> le rebond ne resiste pas : la remontee vue dans la courbe")
            print("     de survie etait du bruit d echantillon sur N=%d." % len(b))
    print("  Note : le meme test est fait dans les deux sens. Un rebond reel")
    print("  d un seul cote serait suspect ; des deux, deja plus credible.")


# ------------------------------------- 3. la memoire revient-elle loin ?
def memoire(rows, sens):
    cle = "ext_" + sens
    print()
    print("=" * 92)
    print("  3. sachant qu on a atteint 2x, la suite ressemble-t-elle au depart ? (%s)" % sens)
    print("=" * 92)
    g = [d[cle] for d in rows if d["casse_" + sens] == 1 and d[cle] is not None]
    if len(g) < 40:
        print("  trop peu de cassures."); return
    print("  Si la loi est sans memoire, la distribution du chemin RESTANT")
    print("  apres 2x doit etre la meme que la distribution depuis 0.")
    print()
    print("  %-10s %14s %16s" % ("chemin", "depuis 0", "restant apres 2x"))
    print("  " + "-" * 46)
    base = g
    reste = [x - 2.0 for x in g if x >= 2.0]
    if len(reste) < 10:
        print("  moins de 10 seances au-dela de 2x -- pas de comparaison.")
        return
    for pas in (0.25, 0.50, 0.75, 1.00):
        a = 100.0 * sum(1 for x in base if x >= pas) / len(base)
        b = 100.0 * sum(1 for x in reste if x >= pas) / len(reste)
        print("  %-10.2f %13.0f%% %15.0f%%" % (pas, a, b))
    print("  " + "-" * 46)
    print("  N depuis 0 = %d, N apres 2x = %d" % (len(base), len(reste)))
    print("  Colonnes proches = memoire absente meme tres loin, ce qui")
    print("  prolongerait les huit blocs de hazard deja plats.")


# ------------------------------------------- 4. les deux bornes ont-elles cede ?
def deux_bornes(rows, sens):
    cle = "ext_" + sens
    autre = "casse_haut" if sens == "bas" else "casse_bas"
    print()
    print("=" * 92)
    print("  4. deviation propre ou aller-retour ? (%s)" % sens)
    print("=" * 92)
    print("Une deviation de 2,5x dans une seance qui a AUSSI casse l autre borne")
    print("n est pas une tendance, c est un balayage. Personne ne les a separees.")
    g = [d for d in rows if d["casse_" + sens] == 1 and d[cle] is not None]
    if len(g) < 40:
        print("  trop peu de cassures."); return
    print()
    print("  %-14s %6s %16s %14s %14s"
          % ("bande", "N", "autre borne aussi", "eff. propre", "eff. balayage"))
    print("  " + "-" * 72)
    for lo, hi, lib in [(0.0, 1.0, "0 a 1x"), (1.0, 2.0, "1 a 2x"),
                        (2.0, 2.5, "2 a 2,5x"), (2.5, 99.0, "2,5x et plus")]:
        lot = [d for d in g if lo <= d[cle] < hi]
        if len(lot) < 8:
            continue
        k = sum(1 for d in lot if d[autre] == 1)
        pr = [d[cle] for d in lot if d[autre] == 0]
        ba = [d[cle] for d in lot if d[autre] == 1]
        print("  %-14s %6d %15.0f%% %14s %14s"
              % (lib, len(lot), 100.0 * k / len(lot),
                 "%.2f" % med(pr) if pr else "-",
                 "%.2f" % med(ba) if ba else "-"))
    print("  " + "-" * 72)
    print("  Si la part d aller-retours CHUTE dans les grandes bandes, alors")
    print("  les grandes deviations sont majoritairement des tendances propres,")
    print("  et c est une distinction utilisable. Si elle reste stable, la")
    print("  taille de la deviation ne dit rien de la nature de la seance.")


def main():
    rows = lire()
    for sens in ("bas", "haut"):
        qui(rows, sens)
    for sens in ("bas", "haut"):
        rebond(rows, sens)
    for sens in ("bas", "haut"):
        memoire(rows, sens)
    for sens in ("bas", "haut"):
        deux_bornes(rows, sens)
    print()
    print("=" * 92)
    print("  ce qu il faut en retenir")
    print("=" * 92)
    print("La section 1 decide de l utilite pratique : si les grandes deviations")
    print("ne sont pas reconnaissables avant, tout le reste est de la description.")
    print("La section 2 tranche le seul resultat non-monotone de toute l etude.")
    print("La section 4 est celle qui pourrait apporter du neuf : separer la")
    print("tendance propre du balayage n a jamais ete fait.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
