# -*- coding: utf-8 -*-
r"""
reaction_evenements.py -- une surprise macro deplace-t-elle le marche,
et a quel horizon ?

  python reaction_evenements.py --verifie
  python reaction_evenements.py
  python reaction_evenements.py --pays US --importance HIGH

LA QUESTION, ET POURQUOI ELLE EST OUVERTE

    Le 17/08, j ai ecarte le forecast du calendrier MT5 parce que le
    CPI du 12/08 sortait a 3,4 contre 2,7 annonces -- une enorme
    surprise -- sans que le prix bouge dans les quinze minutes.

    L utilisateur a objecte, et il a raison : mon raisonnement
    supposait qu une surprise DOIVE produire un mouvement immediat. Si
    un ecart au consensus reorganise le marche sur PLUSIEURS JOURS
    (rotation, changement de regime) sans faire de bougie dans la
    minute, alors le forecast est juste et ma refutation ne vaut rien.

    Fait a l appui de cette objection : notre detecteur de rupture
    trouve le 5 aout avec US500 passant de +22,00 a -7,51 EUR par
    signal (p = 0,002). Un changement de regime de cette taille ne
    s est pas annonce par un spike de quinze minutes non plus.

    On ne tranche donc pas par argument. On mesure aux DEUX horizons
    dans le meme tableau, et le tableau depart les deux lectures.

LA CHAINE DES FUSEAUX -- LE POINT LE PLUS FRAGILE

    Trois horloges, et le total fait TROIS heures :

        calendrier MT5    heure SERVEUR   = UTC+3
        cycles/snapshots  heure MACHINE   = UTC+2   (calendrier - 1 h)
        SierraChart .scid                 = UTC     (calendrier - 3 h)

    Une erreur d une heure ici deplacerait chaque evenement d une
    heure et ne se verrait sur AUCUN controle interne : les tableaux
    sortiraient pleins, alignes, et faux.

    D ou `--verifie`, qui ne mesure rien : il prend les publications
    americaines HIGH connues pour tomber a 14:30 heure de Paris, les
    convertit, et montre l heure obtenue cote prix. Si ce n est pas
    12:30 UTC, on s arrete.

    Verite de terrain gratuite : le BLS publie son calendrier officiel
    (bls.gov/schedule/news_release/cpi.htm) -- CPI a 08:30 ET, dates
    listees jusqu en decembre. C est un meilleur ancrage que n importe
    quelle inference.

CE QU ON MESURE

    surprise = actual - forecast, puis NORMALISEE par evenement :
    0,1 point sur le CPI et 0,1 point sur le NFP ne sont pas
    comparables. La normalisation se fait par l ecart-type des
    surprises passees DU MEME evenement -- ce qui exige au moins
    quelques occurrences, sinon l evenement est ecarte et compte.

    Reaction a SIX horizons : 15 / 30 / 60 minutes, puis 1 / 3 / 5
    jours. Les trois premiers testent ma lecture, les trois derniers
    la sienne.

    Et DEUX grandeurs par horizon : le PRIX en %, et le DELTA CUMULE
    (contrats a l achat moins a la vente). Le prix dit ou ca va, le
    delta dit qui pousse.

LE TEMOIN APPARIE

    Pour chaque evenement, les MEMES heure et minute sur les journees
    SANS publication HIGH. Sans lui on mesurerait "ce qui se passe a
    14h30" -- c est-a-dire l ouverture americaine -- et on
    l appellerait un effet macro.

LECTEUR SEUL : lit le CSV du calendrier et les CSV de cartes\scid\.
"""
import argparse
import csv
import io
import math
import os
import sys
import datetime as dt

CAL = "calendrier.csv"
SCID = os.path.join("cartes", "scid")
SORTIE = os.path.join("cartes", "panel_reaction.txt")
LARG = 100

# Le calendrier est en heure serveur (UTC+3), les .scid en UTC.
DECALAGE_CAL_VERS_SCID = -3

MINUTES = (15, 30, 60)
JOURS = (1, 3, 5)

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def horo(s, sep_date="."):
    if not s:
        return None
    s = s.strip().replace("T", " ").replace("/", sep_date)
    for f in ("%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
              "%Y.%m.%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(s[:19], f)
        except ValueError:
            continue
    return None


def flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def mediane(v):
    if not v:
        return None
    v = sorted(v)
    return v[len(v) // 2]


def moyenne(v):
    return sum(v) / len(v) if v else None


def ecart_type(v):
    n = len(v)
    if n < 2:
        return None
    m = sum(v) / n
    return math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))


def lis_calendrier(chemin):
    """Le calendrier, remis a l heure des .scid (UTC)."""
    out = []
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        lignes = [l for l in f if not l.startswith("#")]
    for r in csv.DictReader(lignes, delimiter=";"):
        t = horo(r.get("ts"))
        if not t:
            continue
        out.append({
            "t": t + dt.timedelta(hours=DECALAGE_CAL_VERS_SCID),
            "t_cal": t,
            "pays": (r.get("pays") or "").strip(),
            "ev": (r.get("evenement") or "").strip(),
            "imp": (r.get("importance") or "").strip(),
            "actual": flt(r.get("actual")),
            "forecast": flt(r.get("forecast")),
            "previous": flt(r.get("previous")),
        })
    out.sort(key=lambda x: x["t"])
    return out


def lis_barres(dossier):
    """Les barres orderflow, triees.

    Rend {symbole: [(t, close, delta), ...]}. Le `delta` (ask - bid) est
    lu en meme temps que le prix : c est le VRAI flux d ordres, contrats
    echanges a l achat moins a la vente, et non le volume de ticks que
    MT5 infere. On le porte des le depart pour ne pas relire 57 Mo une
    seconde fois."""
    out = {}
    if not os.path.isdir(dossier):
        return out
    for nom in sorted(os.listdir(dossier)):
        if not nom.startswith("of_") or not nom.endswith(".csv"):
            continue
        serie = []
        with io.open(os.path.join(dossier, nom), encoding="utf-8",
                     errors="replace") as f:
            for r in csv.DictReader(f, delimiter=";"):
                t = horo(r.get("ts"))
                c = flt(r.get("close"))
                d = flt(r.get("delta"))
                if t and c and c > 0:
                    serie.append((t, c, d if d is not None else 0.0))
        if len(serie) > 100:
            serie.sort(key=lambda x: x[0])
            out[nom[3:-4]] = serie
    return out


def prix_a(serie, cible, tolerance, rend_index=False):
    """Le prix a l instant le plus proche de `cible`, si l ecart tient
    dans `tolerance` secondes. Rend None sinon -- une barre prise a
    deux heures de la cible ne mesure pas la cible."""
    lo, hi = 0, len(serie) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if serie[mid][0] < cible:
            lo = mid + 1
        else:
            hi = mid
    best = None
    for i in (lo - 1, lo, lo + 1):
        if 0 <= i < len(serie):
            d = abs((serie[i][0] - cible).total_seconds())
            if best is None or d < best[0]:
                best = (d, serie[i][1], i)
    if best is None or best[0] > tolerance:
        return None
    return best[1] if not rend_index else best[2]


def reaction(serie, t0, horizons_min, horizons_j, tol):
    """Deux reactions par horizon : le PRIX en %, et le DELTA cumule.

    Le prix dit ou ca va. Le delta dit qui pousse. Les deux peuvent
    diverger -- un prix qui monte sur un delta negatif, c est une
    hausse que les vendeurs subissent -- et c est justement ce genre de
    desaccord qu on cherche a voir. On les mesure donc cote a cote et
    jamais l un a la place de l autre."""
    i0 = prix_a(serie, t0, tol, rend_index=True)
    if i0 is None:
        return None
    base = serie[i0][1]
    out = {}
    for lab, delai, t in ([("%dmin" % m, tol, dt.timedelta(minutes=m))
                           for m in horizons_min]
                          + [("%dj" % j, tol * 20, dt.timedelta(days=j))
                             for j in horizons_j]):
        i1 = prix_a(serie, t0 + t, delai, rend_index=True)
        if i1 is None or i1 <= i0:
            out[lab] = None
            out["d_" + lab] = None
            continue
        out[lab] = (serie[i1][1] - base) / base * 100.0
        # delta CUMULE sur la fenetre : la somme des ask-bid de chaque
        # barre traversee. Une difference de CVD donnerait la meme
        # chose, mais la somme reste juste meme si le CVD a ete remis
        # a zero par un changement de journee.
        out["d_" + lab] = sum(serie[k][2] for k in range(i0 + 1, i1 + 1))
    return out


def verifie(cal, barres):
    """Ne mesure rien : montre la conversion sur des reperes connus."""
    dis("=" * LARG)
    dis("VERIFICATION DES FUSEAUX -- aucune mesure")
    dis("=" * LARG)
    dis("  calendrier MT5   heure serveur  = UTC+3")
    dis("  cycles/snapshots heure machine  = UTC+2  (calendrier - 1 h)")
    dis("  SierraChart      UTC                     (calendrier - 3 h)")
    dis()
    dis("  Les publications americaines majeures tombent a 14:30 heure")
    dis("  de Paris, soit 12:30 UTC. Si la colonne `UTC` ci-dessous ne")
    dis("  dit pas 12:30, la chaine est fausse et rien ne doit etre")
    dis("  mesure.")
    dis()
    cibles = ("CPI", "Non-Farm", "Nonfarm", "NFP", "PPI", "Retail Sales")
    vus = {}
    for e in cal:
        if e["pays"] != "US" or e["imp"] != "HIGH":
            continue
        if not any(c.lower() in e["ev"].lower() for c in cibles):
            continue
        cle = e["t_cal"].strftime("%H:%M")
        vus.setdefault(cle, []).append(e)
    dis("  %-12s %-12s %-12s %8s   %s"
        % ("calendrier", "Paris(-1h)", "UTC(-3h)", "n", "exemple"))
    for cle in sorted(vus, key=lambda k: -len(vus[k]))[:8]:
        g = vus[cle]
        t = g[0]["t_cal"]
        dis("  %-12s %-12s %-12s %8d   %s"
            % (cle,
               (t - dt.timedelta(hours=1)).strftime("%H:%M"),
               (t - dt.timedelta(hours=3)).strftime("%H:%M"),
               len(g), g[0]["ev"][:34]))
    dis()
    if barres:
        for nom, serie in sorted(barres.items())[:3]:
            dis("  %-24s %d barres, du %s au %s"
                % (nom, len(serie),
                   serie[0][0].strftime("%Y-%m-%d"),
                   serie[-1][0].strftime("%Y-%m-%d")))
    else:
        dis("  Aucune barre dans cartes\\scid\\ : lancer lire_scid.py")
        dis("  d abord. La verification des fuseaux ci-dessus reste")
        dis("  valable, elle ne depend que du calendrier.")
    dis()
    dis("  Recouvrement : c est lui qui limite tout. Le calendrier va")
    dis("  de juin a octobre, les barres commencent en fevrier -- seule")
    dis("  l intersection porte des evenements mesurables.")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--calendrier", default=CAL)
    p.add_argument("--scid", default=SCID)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--pays", default="US")
    p.add_argument("--importance", default="HIGH")
    p.add_argument("--mini-occurrences", type=int, default=4,
                   help="occurrences minimales pour normaliser")
    p.add_argument("--tolerance", type=int, default=180,
                   help="secondes d ecart tolere pour un prix")
    p.add_argument("--verifie", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.calendrier):
        print("KO : %s introuvable." % a.calendrier)
        return 1
    cal = lis_calendrier(a.calendrier)
    if not cal:
        print("KO : calendrier vide ou illisible.")
        return 1
    barres = lis_barres(a.scid)

    if a.verifie:
        verifie(cal, barres)
        ecrire(a.sortie)
        return 0

    if not barres:
        print("KO : aucune barre dans %s." % a.scid)
        print("     Lancer d abord : python lire_scid.py --dossier ...")
        return 1

    dis("=" * LARG)
    dis("REACTION AUX SURPRISES MACRO -- deux horizons, un temoin")
    dis("=" * LARG)
    dis("  %d evenements au calendrier." % len(cal))
    dis("  genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dis()
    dis("  Horizons courts (%s min) : l hypothese `une surprise se voit"
        % ", ".join(str(x) for x in MINUTES))
    dis("  tout de suite`. Horizons longs (%s jours) : l hypothese `une"
        % ", ".join(str(x) for x in JOURS))
    dis("  surprise reorganise le marche sans spiker`. Le tableau")
    dis("  depart les deux -- on ne choisit pas d avance.")
    dis("=" * LARG)

    # --- selection et normalisation ---
    sel = [e for e in cal
           if (not a.pays or e["pays"] == a.pays)
           and (not a.importance or e["imp"] == a.importance)]
    dis()
    dis("  %d evenements %s / %s." % (len(sel), a.pays, a.importance))
    avec = [e for e in sel
            if e["actual"] is not None and e["forecast"] is not None]
    dis("  %d ont actual ET forecast (%d n en ont pas)."
        % (len(avec), len(sel) - len(avec)))
    if not avec:
        dis("  Rien a mesurer.")
        ecrire(a.sortie)
        return 0

    par_ev = {}
    for e in avec:
        par_ev.setdefault(e["ev"], []).append(e)
    normalises = []
    ecartes = 0
    for nom, g in par_ev.items():
        bruts = [x["actual"] - x["forecast"] for x in g]
        s = ecart_type(bruts)
        if len(g) < a.mini_occurrences or not s or s <= 0:
            ecartes += len(g)
            continue
        m = moyenne(bruts)
        for x, b in zip(g, bruts):
            x["surprise"] = (b - m) / s
            normalises.append(x)
    dis("  %d normalises, %d ecartes (moins de %d occurrences du meme"
        % (len(normalises), ecartes, a.mini_occurrences))
    dis("  evenement, ou surprises toutes identiques).")
    dis()
    dis("  La normalisation se fait par evenement : 0,1 point sur le")
    dis("  CPI et 0,1 point sur le NFP ne sont pas comparables.")

    if not normalises:
        dis()
        dis("  Aucun evenement normalisable. Baisser --mini-occurrences")
        dis("  ferait apparaitre des z-scores calcules sur deux points,")
        dis("  ce qui n est pas une normalisation.")
        ecrire(a.sortie)
        return 0

    # --- jours avec publication, pour le temoin ---
    jours_ev = set(e["t"].date() for e in sel)

    for sym, serie in sorted(barres.items()):
        dis()
        dis("-" * LARG)
        dis("SYMBOLE %s -- %d barres, du %s au %s"
            % (sym, len(serie), serie[0][0].strftime("%Y-%m-%d"),
               serie[-1][0].strftime("%Y-%m-%d")))
        dis("-" * LARG)
        deb, fin = serie[0][0], serie[-1][0]
        dans = [e for e in normalises if deb <= e["t"] <= fin]
        dis("  %d evenement(s) dans la plage des barres." % len(dans))
        if len(dans) < 5:
            dis("  Moins de cinq : on liste et on ne calcule pas.")
            for e in dans:
                dis("    %s  %-40s surprise %+.2f"
                    % (e["t"].strftime("%Y-%m-%d %H:%M"), e["ev"][:40],
                       e["surprise"]))
            continue

        # temoin : memes heure/minute, journees SANS publication
        temoins = []
        heures = set((e["t"].hour, e["t"].minute) for e in dans)
        j = deb.date()
        while j <= fin.date():
            if j not in jours_ev:
                for hh, mm in heures:
                    temoins.append(dt.datetime(j.year, j.month, j.day,
                                               hh, mm))
            j += dt.timedelta(days=1)
        dis("  %d instant(s) temoin : memes heures, journees SANS"
            % len(temoins))
        dis("  publication. Sans eux on mesurerait l ouverture")
        dis("  americaine et on l appellerait un effet macro.")

        dis()
        dis("  PRIX -- en % depuis l instant de publication")
        dis("  %-8s %8s %10s %10s %10s"
            % ("horizon", "n", "surprises", "temoin", "difference"))
        cles = ["%dmin" % m for m in MINUTES] + ["%dj" % j for j in JOURS]
        r_ev = [reaction(serie, e["t"], MINUTES, JOURS, a.tolerance)
                for e in dans]
        r_tm = [reaction(serie, t, MINUTES, JOURS, a.tolerance)
                for t in temoins]
        r_ev = [x for x in r_ev if x]
        r_tm = [x for x in r_tm if x]
        for k in cles:
            a1 = [x[k] for x in r_ev if x.get(k) is not None]
            a2 = [x[k] for x in r_tm if x.get(k) is not None]
            if len(a1) < 5 or len(a2) < 5:
                dis("  %-8s %8s   trop peu de points" % (k, len(a1)))
                continue
            m1, m2 = moyenne(a1), moyenne(a2)
            dis("  %-8s %8d %9.3f%% %9.3f%% %9.3f%%"
                % (k, len(a1), m1, m2, m1 - m2))
        dis()
        dis("  DELTA CUMULE -- contrats a l achat moins a la vente")
        dis("  %-8s %8s %10s %10s %10s"
            % ("horizon", "n", "surprises", "temoin", "difference"))
        for k in cles:
            dk = "d_" + k
            a1 = [x[dk] for x in r_ev if x.get(dk) is not None]
            a2 = [x[dk] for x in r_tm if x.get(dk) is not None]
            if len(a1) < 5 or len(a2) < 5:
                dis("  %-8s %8s   trop peu de points" % (k, len(a1)))
                continue
            m1, m2 = moyenne(a1), moyenne(a2)
            dis("  %-8s %8d %10.0f %10.0f %10.0f"
                % (k, len(a1), m1, m2, m1 - m2))
        dis()
        dis("  Le prix dit OU ca va, le delta dit QUI pousse. Un prix")
        dis("  qui monte sur un delta negatif est une hausse que les")
        dis("  vendeurs subissent -- et ce desaccord-la ne se voit pas")
        dis("  du tout dans une table de prix.")
        dis()
        dis("  Dans les deux tables, la colonne qui repond est la")
        dis("  DERNIERE. Les deux premieres contiennent la tendance de")
        dis("  la periode ; leur difference, non.")

    dis()
    dis("=" * LARG)
    dis("CE QUE CA NE DIT PAS")
    dis("=" * LARG)
    dis("  Aucun p-value : il viendra par permutation par journee")
    dis("  quand l effectif le permettra, pas avant.")
    dis("  Aucun euro : ce sont des rendements d indice. Le lien au")
    dis("  PnL passe par churn_trades.jsonl et reste a faire.")
    dis("  Aucune direction : on mesure une AMPLITUDE de reaction, pas")
    dis("  un sens. Le signe de la surprise n est pas encore croise.")
    dis("  L ER n est pas ici : elle vient du pipeline orderflow")
    dis("  existant (scalp_orderflow_*.txt), pas des .scid. La croiser")
    dis("  demande de joindre ces deux sources, ce qui est une etape a")
    dis("  part -- et le pipeline le fait deja de son cote.")
    ecrire(a.sortie)
    return 0


def ecrire(chemin):
    d = os.path.dirname(chemin)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(chemin, "w", encoding="utf-8").write("\n".join(_ECHO) + "\n")
    print()
    print("ecrit : %s (%d octets)" % (chemin, os.path.getsize(chemin)))


if __name__ == "__main__":
    sys.exit(main())
