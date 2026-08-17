# -*- coding: utf-8 -*-
r"""
bougie_deux_actifs.py -- une bougie, deux carnets, minute par minute

  python bougie_deux_actifs.py --date 2026-08-12 --heure 14:30
  python bougie_deux_actifs.py --date 2026-08-12 --heure 14:30 --avant 60 --apres 60
  python bougie_deux_actifs.py --date 2026-08-12 --heure 12:30 --fuseau utc

LA QUESTION, POSEE DEPUIS LE DEBUT

    "La bougie a d ailleurs fini ROUGE pour US30 et VERTE pour
    US500/US100, c est peut-etre une coincidence."

    Jusqu a aujourd hui on ne pouvait pas trancher : le Dow n existait
    qu en YMU26, 131 barres par jour, deux heures d activite par
    seance. Avec YMM26 (244 Mo) le Dow est mesurable au meme grain que
    le S&P. La divergence devient une mesure.

CE QUE CET OUTIL NE DEMANDE PAS

    Pas de calendrier. Pas de consensus. Pas de temoin apparie. Pas de
    p-value. Une bougie n est pas un echantillon : c est un evenement
    qu on decrit. Tout ce qu il faut, ce sont deux series de delta REEL
    a la meme seconde -- et on les a.

    Il n y a donc aucune hypothese a pre-enregistrer ici, et aucun
    seuil a inventer. Ce fichier DECRIT.

L ETALON EST LA JOURNEE ELLE-MEME

    "Le delta etait de -1800 a 14h30" ne veut rien dire seul. -1800 sur
    une seance ou la mediane par minute est de 200, c est neuf fois
    l ordinaire. Sur une seance a 3000, ce n est rien.

    Chaque minute est donc rapportee a la MEDIANE ABSOLUE DE LA MEME
    JOURNEE, et son rang y est donne en centile. L etalon est mesure
    sur la seance, pas apporte de l exterieur.

    C est aussi ce qui rend MES et YM comparables : leurs volumes n ont
    rien a voir en contrats, mais "trois fois l ordinaire du jour" se
    compare a "trois fois l ordinaire du jour".

LE FUSEAU, ENCORE

    Les .scid sont en UTC. Toi tu lis un chart en heure de Paris.
    L ecart est de 2 h en ete, 1 h en hiver -- il est CALCULE depuis la
    date (heure d ete europeenne : du dernier dimanche de mars au
    dernier dimanche d octobre) et AFFICHE. Une erreur d une heure ici
    decrirait une autre bougie, avec le meme aplomb.

CE QUE LE PROFIL DE VOLUME EST, ET N EST PAS

    Le profil affiche en fin de sortie est construit sur les CLOTURES
    de barres d une minute, ponderees par leur volume. Ce n est PAS un
    VPOC au tick : un vrai profil repartit le volume de chaque
    transaction sur son propre prix, pas sur la cloture de la minute
    qui la contient.

    Il en est une approximation utilisable pour situer une bougie -- au
    dessus ou en dessous du prix le plus echange de la seance -- et
    rien de plus. Le dire ici evite de le prendre pour ce qu il n est
    pas dans trois semaines.

LECTEUR SEUL : lit cartes\scid\of_*.csv, n ecrit qu un panel texte.
"""
import argparse
import csv
import io
import os
import sys
import datetime as dt

ENTREE = os.path.join("cartes", "scid")
SORTIE = os.path.join("cartes", "panel_bougie.txt")
LARG = 100

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def horo(s):
    if not s:
        return None
    s = s.strip().replace("T", " ")
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
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


def dernier_dimanche(annee, mois):
    """Le dernier dimanche d un mois -- regle civile europeenne."""
    j = dt.date(annee, mois, 31) if mois == 3 else dt.date(annee, mois, 31)
    while j.weekday() != 6:
        j -= dt.timedelta(days=1)
    return j


def decalage_paris(d):
    """Paris - UTC, en heures, pour une DATE donnee.

    Heure d ete europeenne : du dernier dimanche de mars au dernier
    dimanche d octobre. C est une regle civile publiee, pas une
    constante inventee -- mais elle est calculee et affichee, parce
    qu une erreur d une heure decrirait une autre bougie."""
    deb = dernier_dimanche(d.year, 3)
    fin = dernier_dimanche(d.year, 10)
    return 2 if deb <= d < fin else 1


def charge(dossier):
    """Toutes les series, raccords compris, puis les absorbees sont
    retirees.

    Meme regle que dans reaction_evenements.py : un fichier qui porte
    une colonne `contrat` est un raccord, et les echeances qu il nomme
    sont deja dedans. On lit ce que les donnees declarent."""
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
                serie.append({
                    "t": t, "c": c,
                    "h": flt(r.get("high")), "b": flt(r.get("low")),
                    "o": flt(r.get("open")),
                    "vol": flt(r.get("volume")) or 0.0,
                    "d": flt(r.get("delta")) or 0.0,
                    "tr": flt(r.get("trades")) or 0.0,
                    "contrat": (r.get("contrat") or "").strip(),
                })
        if len(serie) > 100:
            serie.sort(key=lambda x: x["t"])
            out[nom[3:-4]] = serie
    absorbes = {}
    for sym, serie in out.items():
        noms = set(x["contrat"] for x in serie if x["contrat"])
        for n in noms:
            if n != sym and n in out:
                absorbes[n] = sym
    msg = ["  of_%s.csv ecarte : deja dans of_%s.csv (colonne `contrat`)"
           % (n, s) for n, s in sorted(absorbes.items())]
    return dict((s, v) for s, v in out.items() if s not in absorbes), msg


def seance(serie, jour):
    return [x for x in serie if x["t"].date() == jour]


def centile(valeurs, x):
    """La part des valeurs strictement inferieures a x, en %."""
    if not valeurs:
        return None
    return 100.0 * sum(1 for v in valeurs if v < x) / len(valeurs)


def profil(jour_barres, tic):
    """Profil de volume sur les CLOTURES, regroupees par tic.

    Ce n est pas un VPOC au tick -- voir l en-tete. C est une
    approximation qui situe, elle ne mesure pas."""
    seaux = {}
    for x in jour_barres:
        k = round(x["c"] / tic) * tic
        seaux[k] = seaux.get(k, 0.0) + x["vol"]
    if not seaux:
        return None, seaux
    poc = max(seaux.items(), key=lambda kv: kv[1])[0]
    return poc, seaux


def pas_cotation(barres):
    """Le tic, LU dans les donnees : le plus petit ecart non nul entre
    deux clotures consecutives qui represente au moins 2 % des ecarts.

    Meme methode que dans bruit_par_actif.py. Ecrire 0,25 pour MES et
    1 pour YM marcherait aujourd hui et casserait au premier symbole
    qu on ajoute."""
    ecarts = {}
    for i in range(1, len(barres)):
        e = round(abs(barres[i]["c"] - barres[i - 1]["c"]), 6)
        if e > 0:
            ecarts[e] = ecarts.get(e, 0) + 1
    if not ecarts:
        return None
    total = sum(ecarts.values())
    for e in sorted(ecarts):
        if ecarts[e] >= 0.02 * total:
            return e
    return min(ecarts)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entree", default=ENTREE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--date", required=True, help="AAAA-MM-JJ")
    p.add_argument("--heure", default="14:30", help="HH:MM")
    p.add_argument("--fuseau", default="paris", choices=("paris", "utc"))
    p.add_argument("--avant", type=int, default=30, help="minutes avant")
    p.add_argument("--apres", type=int, default=30, help="minutes apres")
    p.add_argument("--symboles", default=None,
                   help="liste separee par des virgules ; defaut : tous")
    a = p.parse_args()

    try:
        jour = dt.datetime.strptime(a.date, "%Y-%m-%d").date()
        hh, mm = [int(x) for x in a.heure.split(":")[:2]]
    except (ValueError, IndexError):
        print("KO : --date AAAA-MM-JJ et --heure HH:MM.")
        return 1

    barres, msg = charge(a.entree)
    if not barres:
        print("KO : aucune serie dans %s." % a.entree)
        print("     Lancer d abord : python lire_scid.py --dossier ...")
        return 1
    if a.symboles:
        voulus = set(x.strip() for x in a.symboles.split(","))
        barres = dict((s, v) for s, v in barres.items() if s in voulus)
        if not barres:
            print("KO : aucun des symboles demandes n existe.")
            print("     Presents : %s" % ", ".join(sorted(barres)))
            return 1

    dec = decalage_paris(jour)
    t_paris = dt.datetime(jour.year, jour.month, jour.day, hh, mm)
    if a.fuseau == "paris":
        ancre = t_paris - dt.timedelta(hours=dec)
    else:
        ancre = t_paris
        t_paris = ancre + dt.timedelta(hours=dec)

    dis("=" * LARG)
    dis("UNE BOUGIE, DEUX CARNETS -- %s" % a.date)
    dis("=" * LARG)
    for m in msg:
        dis(m)
    if msg:
        dis()
    dis("  Ancre : %s heure de Paris  =  %s UTC"
        % (t_paris.strftime("%H:%M"), ancre.strftime("%H:%M")))
    dis("  Decalage Paris-UTC ce jour-la : %d h (heure d %s)."
        % (dec, "ete" if dec == 2 else "hiver"))
    dis("  Les .scid sont en UTC. Une erreur d une heure ici decrirait")
    dis("  une autre bougie, avec le meme aplomb.")
    dis()
    dis("  Fenetre : -%d min / +%d min autour de l ancre."
        % (a.avant, a.apres))
    dis("  Elle est definie en TEMPS, jamais en nombre de barres.")

    t0 = ancre - dt.timedelta(minutes=a.avant)
    t1 = ancre + dt.timedelta(minutes=a.apres)

    # --- couverture : on regarde AVANT de decrire -------------------
    dis()
    dis("-" * LARG)
    dis("COUVERTURE -- ce qui existe reellement dans la fenetre")
    dis("-" * LARG)
    dis("  %-18s %8s %8s %10s %10s %12s"
        % ("symbole", "seance", "fenetre", "manquant", "contrat", "tic"))
    utiles = {}
    for sym in sorted(barres):
        jb = seance(barres[sym], jour)
        fen = [x for x in jb if t0 <= x["t"] <= t1]
        attendu = a.avant + a.apres + 1
        contrats = sorted(set(x["contrat"] for x in fen if x["contrat"]))
        tic = pas_cotation(jb) if len(jb) > 2 else None
        dis("  %-18s %8d %8d %10d %10s %12s"
            % (sym, len(jb), len(fen), max(0, attendu - len(fen)),
               "/".join(contrats) if contrats else "-",
               ("%g" % tic) if tic else "?"))
        if len(fen) >= 2 and tic:
            if len(contrats) > 1:
                dis("      ECARTE : la fenetre enjambe un raccord")
                dis("      d echeance. Elle mesurerait la base entre")
                dis("      contrats, pas un mouvement de marche.")
                continue
            # Le pourcentage suppose une ECHELLE. $TICK-NYSE traverse
            # zero : (p1-p0)/p0 y mesure la petitesse de la base, pas
            # le mouvement. Meme regle que dans reaction_evenements.py,
            # et decidee sur la serie, pas sur un nom de symbole.
            ech = min(x["c"] for x in jb) > 0
            if not ech:
                dis("      Serie traversant zero : mesuree en POINTS,")
                dis("      jamais en pourcent.")
            utiles[sym] = (jb, fen, tic, ech)
    if not utiles:
        dis()
        dis("  Aucune serie exploitable sur cette fenetre. Rien n est")
        dis("  decrit : une bougie qu on n a pas ne se raconte pas.")
        ecrire(a.sortie)
        return 1

    # --- l etalon de la journee -------------------------------------
    dis()
    dis("-" * LARG)
    dis("L ETALON -- la journee elle-meme")
    dis("-" * LARG)
    dis("  %-18s %12s %12s %12s"
        % ("symbole", "med |delta|", "med volume", "med |dprix|"))
    etal = {}
    for sym, (jb, fen, tic, ech) in sorted(utiles.items()):
        ad = [abs(x["d"]) for x in jb]
        av = [x["vol"] for x in jb]
        dp = [abs(jb[i]["c"] - jb[i - 1]["c"]) for i in range(1, len(jb))]
        etal[sym] = (mediane(ad) or 0.0, mediane(av) or 0.0,
                     mediane(dp) or 0.0, ad, av)
        dis("  %-18s %12.0f %12.0f %12g"
            % (sym, etal[sym][0], etal[sym][1], etal[sym][2]))
    dis()
    dis("  Tout ce qui suit est rapporte a ces medianes. `x3` veut dire")
    dis("  trois fois l ordinaire DE CETTE SEANCE -- ce qui rend MES et")
    dis("  YM comparables alors que leurs volumes n ont rien a voir.")

    # --- minute par minute ------------------------------------------
    for sym, (jb, fen, tic, ech) in sorted(utiles.items()):
        md, mv, mdp, ad, av = etal[sym]
        dis()
        dis("-" * LARG)
        dis("%s -- minute par minute (heure de Paris)" % sym)
        dis("-" * LARG)
        base = fen[0]["c"]
        cum = 0.0
        dis("  %-7s %10s %9s %9s %10s %8s %9s %7s"
            % ("heure", "cloture", "dprix", "tics", "delta", "x med",
               "cvd", "vol xm"))
        for x in fen:
            cum += x["d"]
            hp = (x["t"] + dt.timedelta(hours=dec)).strftime("%H:%M")
            dp = x["c"] - base
            rap = (abs(x["d"]) / md) if md else 0.0
            rv = (x["vol"] / mv) if mv else 0.0
            marque = ""
            if md and abs(x["d"]) >= 3 * md:
                marque = " <<"
            dis("  %-7s %10.2f %+9.2f %+9.0f %+10.0f %8.1f %+9.0f %7.1f%s"
                % (hp, x["c"], dp, dp / tic, x["d"], rap, cum, rv,
                   marque))
        dis()
        c0, c1 = fen[0]["c"], fen[-1]["c"]
        if ech:
            dis("  Bilan fenetre : %+.2f point(s), %+.0f tic(s), %+.3f %%"
                % (c1 - c0, (c1 - c0) / tic, (c1 - c0) / c0 * 100.0))
        else:
            dis("  Bilan fenetre : %+.2f point(s), soit %+.0f tic(s)."
                % (c1 - c0, (c1 - c0) / tic))
            dis("  Pas de pourcentage : la serie traverse zero.")
        dis("  Delta cumule  : %+.0f contrat(s)" % cum)
        dis("  Volume        : %.0f contrat(s), soit %.1f fois la mediane"
            % (sum(x["vol"] for x in fen),
               sum(x["vol"] for x in fen) / (mv * len(fen)) if mv else 0))
        pic = max(fen, key=lambda x: abs(x["d"]))
        # Une serie sans delta -- un indice comme $TICK n a pas de
        # carnet -- ne doit pas produire une phrase sur "la minute ou
        # le carnet a bascule". Zero partout n est pas un maximum.
        if not md or not pic["d"]:
            dis("  Delta absent de cette serie : ce symbole n a pas de")
            dis("  carnet a l achat et a la vente. Seul son prix parle.")
        else:
            dis("  Minute au plus fort delta : %s, %+.0f contrat(s), soit"
                % ((pic["t"] + dt.timedelta(hours=dec)).strftime("%H:%M"),
                   pic["d"]))
            dis("  %.1f fois la mediane du jour, centile %.1f de la"
                % (abs(pic["d"]) / md, centile(ad, abs(pic["d"])) or 0))
            dis("  seance -- c est la que le carnet a pousse le plus.")

    # --- la divergence ----------------------------------------------
    syms = sorted(utiles)
    if len(syms) >= 2:
        dis()
        dis("=" * LARG)
        dis("DIVERGENCE -- le desaccord entre deux carnets")
        dis("=" * LARG)
        for i in range(len(syms)):
            for j in range(i + 1, len(syms)):
                sa, sb = syms[i], syms[j]
                fa = dict((x["t"], x) for x in utiles[sa][1])
                fb = dict((x["t"], x) for x in utiles[sb][1])
                communs = sorted(set(fa) & set(fb))
                if len(communs) < 2:
                    dis("  %s / %s : moins de deux minutes communes."
                        % (sa, sb))
                    continue
                dis()
                dis("  %s  contre  %s" % (sa, sb))
                dis("  %d minute(s) communes sur %d et %d."
                    % (len(communs), len(fa), len(fb)))
                oppo = [t for t in communs
                        if fa[t]["d"] * fb[t]["d"] < 0]
                ca = sum(fa[t]["d"] for t in communs)
                cb = sum(fb[t]["d"] for t in communs)
                dis()
                dis("  Delta cumule : %s %+.0f   /   %s %+.0f"
                    % (sa, ca, sb, cb))
                if not ca or not cb:
                    dis("  L un des deux est a zero : pas de carnet sur")
                    dis("  ce symbole, donc aucun desaccord a lire.")
                elif ca * cb < 0:
                    dis("  LES DEUX CARNETS SONT DE SIGNE OPPOSE sur la")
                    dis("  fenetre. Ce n est pas une difference")
                    dis("  d intensite, c est un desaccord de sens.")
                else:
                    dis("  Meme signe sur la fenetre : les deux carnets")
                    dis("  poussent du meme cote, a des intensites")
                    dis("  differentes.")
                dis()
                dis("  %d minute(s) sur %d ont des deltas de signe"
                    % (len(oppo), len(communs)))
                dis("  oppose, soit %.0f %%."
                    % (100.0 * len(oppo) / len(communs)))
                if oppo:
                    dis()
                    dis("  %-7s %12s %12s" % ("heure", sa[:12], sb[:12]))
                    for t in oppo:
                        dis("  %-7s %+12.0f %+12.0f"
                            % ((t + dt.timedelta(hours=dec)).strftime(
                                "%H:%M"), fa[t]["d"], fb[t]["d"]))
                # variation relative, seule comparable entre indices
                dis()
                # Comparer deux indices en POINTS n a pas de sens : MES
                # cote vers 6400 et YM vers 45000. Le pourcentage est la
                # seule comparaison possible -- mais il exige que les
                # deux series aient une echelle. Si l une traverse zero,
                # on ne compare pas, on le dit.
                bruta = fa[communs[-1]]["c"] - fa[communs[0]]["c"]
                brutb = fb[communs[-1]]["c"] - fb[communs[0]]["c"]
                if utiles[sa][3] and utiles[sb][3]:
                    da = bruta / fa[communs[0]]["c"] * 100.0
                    db = brutb / fb[communs[0]]["c"] * 100.0
                    dis("  Prix sur les minutes communes :")
                    dis("    %-18s %+8.3f %%   (%+.2f point(s))"
                        % (sa, da, bruta))
                    dis("    %-18s %+8.3f %%   (%+.2f point(s))"
                        % (sb, db, brutb))
                    if da * db < 0:
                        dis("  LES PRIX AUSSI DIVERGENT DE SIGNE. C est")
                        dis("  la bougie rouge d un cote, verte de")
                        dis("  l autre -- mesuree, plus supposee.")
                    dis("  Le pourcentage est la seule comparaison")
                    dis("  possible : %s cote vers %.0f, %s vers %.0f."
                        % (sa, fa[communs[0]]["c"], sb,
                           fb[communs[0]]["c"]))
                else:
                    dis("  Prix : %s %+.2f pt / %s %+.2f pt."
                        % (sa, bruta, sb, brutb))
                    dis("  Aucune comparaison de prix : l une des deux")
                    dis("  series traverse zero, donc n a pas d echelle.")
                    dis("  Les deltas ci-dessus, eux, restent")
                    dis("  comparables -- ce sont des contrats.")

    # --- ou se situe la bougie dans la seance -----------------------
    dis()
    dis("=" * LARG)
    dis("SITUATION DANS LA SEANCE -- profil de volume sur les clotures")
    dis("=" * LARG)
    dis("  Ce profil regroupe les CLOTURES d une minute, ponderees par")
    dis("  leur volume. Ce n est PAS un VPOC au tick : un vrai profil")
    dis("  repartit le volume de chaque transaction sur SON prix, pas")
    dis("  sur la cloture de la minute qui la contient. Il situe, il ne")
    dis("  mesure pas.")
    dis()
    dis("  %-18s %12s %12s %12s %10s"
        % ("symbole", "POC seance", "prix ancre", "ecart", "en tics"))
    for sym, (jb, fen, tic, ech) in sorted(utiles.items()):
        poc, _ = profil(jb, tic)
        if poc is None:
            continue
        pa = None
        for x in fen:
            if x["t"] >= ancre:
                pa = x["c"]
                break
        if pa is None:
            pa = fen[-1]["c"]
        dis("  %-18s %12.2f %12.2f %+12.2f %+10.0f"
            % (sym, poc, pa, pa - poc, (pa - poc) / tic))
    dis()
    dis("  Un prix d ancre au-dessus du POC dit que la bougie part")
    dis("  d une zone MOINS echangee que le coeur de la seance. En")
    dis("  dessous, l inverse. Ca ne predit rien -- ca situe.")

    dis()
    dis("=" * LARG)
    dis("CE QUE CA NE DIT PAS")
    dis("=" * LARG)
    dis("  Aucune p-value, et c est voulu : une bougie n est pas un")
    dis("  echantillon. Pour savoir si CE motif se repete, il faut le")
    dis("  chercher sur les autres journees -- c est une autre mesure,")
    dis("  avec un temoin, et elle n est pas ici.")
    dis("  Aucun euro : ce sont des contrats et des points d indice.")
    dis("  Le lien au PnL passe par churn_trades.jsonl.")
    dis("  Aucune cause : un delta negatif dit que les vendeurs ont")
    dis("  traverse le spread, pas pourquoi.")
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
