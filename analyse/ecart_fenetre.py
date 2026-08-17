# -*- coding: utf-8 -*-
r"""
ecart_fenetre.py -- l attente et la decision, separees

  python ecart_fenetre.py
  python ecart_fenetre.py --avant 60 --apres 60
  python ecart_fenetre.py --motif CPI,Nonfarm,Fed

LE DEFAUT QU IL CORRIGE

    `ecart_carnets.py` mesure le CVD de la JOURNEE ENTIERE, soit
    environ 1380 minutes. La publication y pese une minute sur mille
    trois cent quatre-vingts.

    La preuve que ca ne va pas est deja dans nos donnees : le 12/08, la
    journee entiere est vendeuse sur le S&P (CVD -8773) alors que la
    fenetre de 14h30 est acheteuse (+815). Les deux chiffres sont
    justes et ils disent le contraire, parce qu ils ne mesurent pas la
    meme chose.

    Le marche s immobilise AVANT la statistique -- parfois plusieurs
    jours -- puis tranche DESSUS. Additionner les deux dans un seul
    nombre, c est laisser l attente annuler la decision.

    Ce fichier separe donc deux fenetres :

        ATTENTE   [T - avant, T[      le positionnement
        DECISION  [T, T + apres]      la reaction

CHAQUE EVENEMENT A SON HEURE, ET ELLE EST LUE

    Fed Interest Rate Decision  20:00 Paris
    ADP                         14:15
    CPI, Nonfarm Payrolls       14:30
    un discours de Powell       l heure qu il veut

    Mesurer tout le monde a 14h30 decrirait une autre bougie pour la
    moitie des lignes. L instant vient du calendrier, evenement par
    evenement, converti en UTC (calendrier - 3 h).

LA DISTRIBUTION DE REFERENCE EST LA MEME FENETRE HORAIRE

    Le centile d une fenetre ne se lit pas dans la distribution des
    JOURNEES : une heure de 14h30 a 15h30 n a pas le meme volume qu une
    heure de 3h du matin.

    Pour chaque evenement, la reference est donc construite sur LA MEME
    FENETRE HORAIRE de toutes les seances disponibles. Comparer 14h30
    a 14h30 elimine l effet d heure de la journee -- comme la
    stratification par jour de semaine eliminait l effet de jour.

CE QUI EST ECARTE, ET COMPTE

    Une fenetre qui enjambe un raccord d echeance : elle mesurerait la
    base entre contrats.
    Une fenetre dont la couverture en barres est inferieure a la moitie
    de la mediane des memes fenetres : elle mesurerait un trou.

CE QUE CE FICHIER NE FAIT TOUJOURS PAS

    Il ne teste rien. Trois CPI restent trois CPI. Il DECRIT, il
    SEPARE, et il montre si la fenetre dit autre chose que la journee
    -- ce qui est la seule question posee ici.

LECTEUR SEUL : lit cartes\scid\of_*.csv et le calendrier.
"""
import argparse
import csv
import io
import os
import sys
import datetime as dt

ENTREE = os.path.join("cartes", "scid")
SORTIE = os.path.join("cartes", "panel_ecart_fenetre.txt")
LARG = 100
DECALAGE_CAL_VERS_SCID = -3

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def horo(s):
    if not s:
        return None
    s = s.strip().replace("T", " ").replace("/", ".")
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
              "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"):
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
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def charge(dossier):
    out = {}
    if not os.path.isdir(dossier):
        return out, []
    for nom in sorted(os.listdir(dossier)):
        if not nom.startswith("of_") or not nom.endswith(".csv"):
            continue
        serie = []
        with io.open(os.path.join(dossier, nom), encoding="utf-8",
                     errors="replace") as f:
            for r in csv.DictReader(f, delimiter=";"):
                t = horo(r.get("ts"))
                c = flt(r.get("close"))
                if t is None or c is None:
                    continue
                serie.append((t, c, flt(r.get("delta")) or 0.0,
                              flt(r.get("volume")) or 0.0,
                              (r.get("contrat") or "").strip()))
        if len(serie) > 100:
            serie.sort(key=lambda x: x[0])
            out[nom[3:-4]] = serie
    absorbes = {}
    for sym, serie in out.items():
        for n in set(x[4] for x in serie if x[4]):
            if n != sym and n in out:
                absorbes[n] = sym
    msg = ["  of_%s.csv ecarte : deja dans of_%s.csv (colonne `contrat`)"
           % (n, s) for n, s in sorted(absorbes.items())]
    return dict((s, v) for s, v in out.items() if s not in absorbes), msg


def index_jour(serie):
    """Les barres regroupees par date, pour ne pas rebalayer la serie
    a chaque fenetre."""
    par = {}
    for x in serie:
        par.setdefault(x[0].date(), []).append(x)
    return par


def fenetre(barres_jour, t0, t1):
    """Somme des deltas, somme des volumes, nombre de barres, et les
    contrats rencontres, sur [t0, t1[."""
    d = v = 0.0
    n = 0
    contrats = set()
    for x in barres_jour:
        if t0 <= x[0] < t1:
            d += x[2]
            v += x[3]
            n += 1
            if x[4]:
                contrats.add(x[4])
    return d, v, n, contrats


def distribution(par_jour, hh, mm, avant, apres):
    """Pour chaque seance, le delta cumule sur la MEME fenetre horaire.

    C est la reference : une heure de 14h30 ne se compare qu a des
    heures de 14h30. Rend deux dictionnaires date -> delta, l un pour
    l attente, l autre pour la decision, plus les comptes de barres
    pour juger la couverture."""
    att, dec, nb_a, nb_d = {}, {}, {}, {}
    for j, bar in par_jour.items():
        anc = dt.datetime(j.year, j.month, j.day, hh, mm)
        da, va, na, ca = fenetre(bar, anc - dt.timedelta(minutes=avant),
                                 anc)
        dd, vd, nd, cd = fenetre(bar, anc,
                                 anc + dt.timedelta(minutes=apres))
        # Une fenetre a cheval sur deux echeances mesure la base.
        if len(ca) > 1 or len(cd) > 1 or (ca and cd and ca != cd):
            continue
        att[j], dec[j] = da, dd
        nb_a[j], nb_d[j] = na, nd
    return att, dec, nb_a, nb_d


def filtre_couverture(vals, nb):
    """Ne garde que les seances dont la fenetre porte au moins la
    moitie du nombre median de barres. Le seuil est MESURE sur les
    fenetres elles-memes, pas invente."""
    if not nb:
        return {}, 0
    med = mediane(list(nb.values())) or 0
    seuil = max(1, int(med // 2))
    return (dict((j, v) for j, v in vals.items() if nb.get(j, 0) >= seuil),
            seuil)


def centile(tri, v):
    if not tri:
        return None
    return 100.0 * sum(1 for x in tri if x < v) / len(tri)


def lis_calendrier(chemin, pays, imp, motifs):
    out = []
    if not chemin or not os.path.isfile(chemin):
        return out
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        lignes = [l for l in f if not l.startswith("#")]
    for r in csv.DictReader(lignes, delimiter=";"):
        t = horo(r.get("ts"))
        if not t:
            continue
        if pays and (r.get("pays") or "").strip() != pays:
            continue
        if imp and (r.get("importance") or "").strip() != imp:
            continue
        ev = (r.get("evenement") or "").strip()
        fam = None
        for m in motifs:
            if m in ev.lower():
                fam = m
                break
        if not fam:
            continue
        out.append({"t": t + dt.timedelta(hours=DECALAGE_CAL_VERS_SCID),
                    "t_cal": t, "ev": ev, "fam": fam})
    out.sort(key=lambda x: x["t"])
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entree", default=ENTREE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--calendrier", default="calendrier.csv")
    p.add_argument("--pays", default="US")
    p.add_argument("--importance", default="HIGH")
    p.add_argument("--motif",
                   default="cpi,nonfarm,payrolls,fomc,fed,powell,adp,ism")
    p.add_argument("--avant", type=int, default=60,
                   help="minutes d attente avant la publication")
    p.add_argument("--apres", type=int, default=60,
                   help="minutes de decision apres la publication")
    p.add_argument("--symboles", default=None)
    a = p.parse_args()

    barres, msg = charge(a.entree)
    if a.symboles:
        voulus = set(x.strip() for x in a.symboles.split(","))
        barres = dict((s, v) for s, v in barres.items() if s in voulus)
    if len(barres) < 2:
        print("KO : il faut au moins deux symboles dans %s." % a.entree)
        return 1

    motifs = [x.strip().lower() for x in a.motif.split(",") if x.strip()]
    evs = lis_calendrier(a.calendrier, a.pays, a.importance, motifs)
    if not evs:
        print("KO : aucun evenement %s / %s portant les motifs %s."
              % (a.pays, a.importance, a.motif))
        return 1

    dis("=" * LARG)
    dis("ATTENTE ET DECISION -- separees")
    dis("=" * LARG)
    for m in msg:
        dis(m)
    if msg:
        dis()
    dis("  `ecart_carnets.py` mesurait la JOURNEE : la publication y")
    dis("  pesait une minute sur mille trois cent quatre-vingts. Le")
    dis("  12/08, la journee du S&P est vendeuse (-8773) alors que la")
    dis("  fenetre de 14h30 est acheteuse (+815) -- les deux chiffres")
    dis("  sont justes et disent le contraire.")
    dis()
    dis("  ATTENTE  = [T - %d min, T[   le positionnement" % a.avant)
    dis("  DECISION = [T, T + %d min]   la reaction" % a.apres)
    dis()
    dis("  L instant T vient du calendrier, EVENEMENT PAR EVENEMENT.")
    dis("  Une decision de la Fed ne tombe pas a la meme heure qu un")
    dis("  CPI, et les mesurer toutes a 14h30 decrirait autre chose.")

    # index par jour, une fois
    idx = dict((s, index_jour(v)) for s, v in barres.items())
    syms = sorted(barres)

    # heures distinctes -> distributions de reference, calculees une
    # seule fois par (symbole, heure)
    heures = sorted(set((e["t"].hour, e["t"].minute) for e in evs))
    dis()
    dis("  %d evenement(s) retenu(s), a %d heure(s) distincte(s) :"
        % (len(evs), len(heures)))
    for hh, mm in heures:
        qui = sorted(set(e["fam"] for e in evs
                         if (e["t"].hour, e["t"].minute) == (hh, mm)))
        dis("    %02d:%02d UTC = %02d:%02d Paris(ete)   %s"
            % (hh, mm, (hh + 2) % 24, mm, ", ".join(qui)))

    ref = {}
    for sym in syms:
        for hh, mm in heures:
            att, dec, na, nd = distribution(idx[sym], hh, mm,
                                            a.avant, a.apres)
            att, sa_ = filtre_couverture(att, na)
            dec, sd_ = filtre_couverture(dec, nd)
            ref[(sym, hh, mm)] = (att, dec, sa_, sd_)

    dis()
    dis("-" * LARG)
    dis("COUVERTURE DES REFERENCES")
    dis("-" * LARG)
    dis("  %-16s %8s %10s %10s %10s"
        % ("symbole", "heure", "n attente", "n decision", "seuil barres"))
    for sym in syms:
        for hh, mm in heures:
            att, dec, s1, s2 = ref[(sym, hh, mm)]
            dis("  %-16s %8s %10d %10d %10s"
                % (sym, "%02d:%02d" % (hh, mm), len(att), len(dec),
                   "%d / %d" % (s1, s2)))
    dis()
    dis("  Chaque fenetre d evenement est comparee aux MEMES fenetres")
    dis("  horaires de toutes les autres seances. Comparer 14h30 a")
    dis("  14h30 elimine l effet d heure de la journee.")

    # --- la mesure, paire par paire --------------------------------
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            sa, sb = syms[i], syms[j]
            dis()
            dis("=" * LARG)
            dis("ECART %s moins %s -- en centiles, par phase" % (sb, sa))
            dis("=" * LARG)
            dis("  Negatif : %s est vendu plus durement que %s," % (sb, sa))
            dis("  rapporte a ce que chacun fait d ordinaire A CETTE")
            dis("  HEURE-LA.")
            dis()
            dis("  %-12s %-10s %9s %9s   %s"
                % ("date", "heure", "attente", "decision", "evenement"))
            lignes = []
            for e in evs:
                hh, mm = e["t"].hour, e["t"].minute
                d = e["t"].date()
                va = vb = None
                ok = True
                cs = {}
                for s in (sa, sb):
                    att, dec, _, _ = ref[(s, hh, mm)]
                    if d not in att or d not in dec:
                        ok = False
                        break
                    cs[s] = (centile(sorted(att.values()), att[d]),
                             centile(sorted(dec.values()), dec[d]))
                if not ok:
                    continue
                ea = cs[sb][0] - cs[sa][0]
                ed = cs[sb][1] - cs[sa][1]
                lignes.append((d, e, ea, ed))
                dis("  %-12s %-10s %+9.1f %+9.1f   %s"
                    % (d, "%02d:%02d UTC" % (hh, mm), ea, ed,
                       e["ev"][:34]))
            if not lignes:
                dis("  Aucune fenetre exploitable sur cette paire.")
                continue

            # --- par famille, et par phase --------------------
            fam = {}
            for d, e, ea, ed in lignes:
                fam.setdefault(e["fam"], []).append((ea, ed))
            dis()
            dis("  PAR FAMILLE -- l attente et la decision separement")
            dis("  %-12s %5s %12s %12s %10s %10s"
                % ("famille", "n", "med attente", "med decision",
                   "att meme", "dec meme"))
            for f in sorted(fam, key=lambda k: -len(fam[k])):
                g = fam[f]
                ma = mediane([x[0] for x in g])
                md = mediane([x[1] for x in g])
                ca = sum(1 for x in g if x[0] < 0)
                cd = sum(1 for x in g if x[1] < 0)
                dis("  %-12s %5d %+12.1f %+12.1f %10s %10s"
                    % (f[:12], len(g), ma, md,
                       "%d/%d bas" % (ca, len(g)),
                       "%d/%d bas" % (cd, len(g))))
            dis()
            dis("  `bas` = %s vendu plus durement que %s." % (sb, sa))
            dis("  Une famille dont la colonne DECISION est unanime et")
            dis("  la colonne ATTENTE ne l est pas, c est la statistique")
            dis("  qui tranche -- pas le positionnement de la veille.")
            dis("  L inverse dirait que tout etait joue avant.")

    dis()
    dis("=" * LARG)
    dis("CE QUE CA NE DIT PAS")
    dis("=" * LARG)
    dis("  Aucun test. Trois CPI restent trois CPI, et separer en deux")
    dis("  fenetres double le nombre de chiffres sans ajouter une seule")
    dis("  observation. Ce qui se lit ici se PRE-ENREGISTRE et se")
    dis("  verifie hors echantillon.")
    dis("  Le choix de %d et %d minutes est un CHOIX. Le refaire avec"
        % (a.avant, a.apres))
    dis("  d autres valeurs jusqu a ce que ca parle serait un balayage,")
    dis("  et un balayage trouve toujours un maximum. Fixer une fois,")
    dis("  noter dans HYPOTHESES.md, ne plus y toucher.")
    dis("  Aucun euro : le centile est sans echelle.")
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
