# -*- coding: utf-8 -*-
r"""
ecart_carnets.py -- comparer deux actifs LE MEME JOUR, et non des
journees entre elles

  python ecart_carnets.py
  python ecart_carnets.py --calendrier calendrier.csv
  python ecart_carnets.py --motif CPI

POURQUOI CET ANGLE

    Tout ce qui a ete tente aujourd hui a bute sur le meme mur : pour
    dire qu une journee est particuliere, il faut des journees
    ordinaires a lui opposer, et notre calendrier ne couvre que
    juin-septembre avec deux series hebdomadaires qui tombent toujours
    le meme jour de la semaine. Il n existe pas un seul mercredi temoin.

    Ce fichier ne compare pas des journees. Il compare DEUX ACTIFS
    A L INTERIEUR DE CHAQUE JOURNEE.

        Le 12/08, le Dow etait au centile 8 de sa propre distribution
        de CVD, le S&P au centile 25 de la sienne.

    Cet ecart de 17 centiles ne demande aucun temoin apparie : les deux
    actifs ont vecu la meme journee, la meme seance, la meme humeur. Ce
    qui les separe ne peut pas etre un effet de periode, ni un effet de
    jour de semaine, ni un changement d echeance -- ces trois causes
    frappent les deux en meme temps.

    C est le seul angle de la journee qui echappe aux trois murs.

CE QUE MESURE `ecart`

    Pour chaque seance et chaque symbole : le delta cumule du jour,
    puis son CENTILE dans la distribution du MEME symbole. Le centile
    est sans echelle -- il ne suppose ni le meme volume, ni le meme
    multiplicateur, ni la meme liquidite.

        ecart = centile(YM) - centile(MES)

    Negatif : le Dow est vendu plus durement que le S&P, rapporte a ce
    que chacun fait d ordinaire. Positif : l inverse.

CE QUE CE FICHIER NE FAIT PAS, ET C EST VOLONTAIRE

    Il ne teste rien. Trois CPI dans la plage, ce n est pas un
    echantillon, et aucun arrangement statistique ne changera ca.

    Il DECRIT la distribution des ecarts sur toutes les seances, puis
    il SITUE les journees de publication dedans, et il PRE-ENREGISTRE
    ce qu il faudrait voir aux prochaines pour que l observation tienne.

    Une observation pre-enregistree sur trois points et confirmee hors
    echantillon vaut mieux qu un test bricole sur vingt-deux -- c est
    la lecon de la matinee.

LE NOTIONNEL

    Les multiplicateurs sont des SPECIFICATIONS DE CONTRAT (CME), pas
    des mesures. Ils sont declares en tete de fichier, affiches a
    l execution, et ne servent qu aux lignes en dollars. Toute la
    mesure principale est en centiles, donc indifferente a leur
    exactitude.

LECTEUR SEUL : lit cartes\scid\of_*.csv et le calendrier.
"""
import argparse
import csv
import io
import os
import sys
import datetime as dt

ENTREE = os.path.join("cartes", "scid")
SORTIE = os.path.join("cartes", "panel_ecart.txt")
LARG = 100

# Specification de contrat CME, en dollars par point d indice. CE NE
# SONT PAS DES MESURES : elles ne servent qu aux lignes en dollars, et
# elles sont affichees pour etre verifiables. La mesure principale est
# en centiles et n en depend pas.
MULTIPLICATEUR = {"MES": 5.0, "MNQ": 2.0, "MYM": 0.5,
                  "YM": 5.0, "ES": 50.0, "NQ": 20.0}

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def horo(s, sep="-"):
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


def multiplicateur(sym):
    """La racine du symbole decide. `MES-continu` -> MES."""
    r = sym.split("-")[0].upper()
    for k in sorted(MULTIPLICATEUR, key=len, reverse=True):
        if r.startswith(k):
            return k, MULTIPLICATEUR[k]
    return None, None


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


def par_seance(serie):
    par = {}
    for t, c, d, v, _ in serie:
        j = t.date()
        a = par.setdefault(j, [0.0, 0.0, 0, c])
        a[0] += d
        a[1] += v
        a[2] += 1
        a[3] = c
    cpt = sorted(x[2] for x in par.values())
    med = cpt[len(cpt) // 2] if cpt else 0
    return dict((j, x) for j, x in par.items() if x[2] >= max(1, med // 2))


def centiles(valeurs):
    """Le centile de chaque valeur dans sa propre distribution."""
    tri = sorted(valeurs.values())
    n = len(tri)
    return dict((k, 100.0 * sum(1 for x in tri if x < v) / n)
                for k, v in valeurs.items())


def lis_calendrier(chemin, pays, imp):
    """Les dates de publication, en heure SERVEUR ramenee a la date
    UTC des barres (calendrier - 3 h)."""
    out = {}
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
        d = (t - dt.timedelta(hours=3)).date()
        out.setdefault(d, []).append((r.get("evenement") or "").strip())
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entree", default=ENTREE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--calendrier", default="calendrier.csv")
    p.add_argument("--pays", default="US")
    p.add_argument("--importance", default="HIGH")
    p.add_argument("--motif", default="CPI,Nonfarm,Non-Farm,Payrolls,Fed,FOMC",
                   help="fragments de nom a situer, separes par des virgules")
    p.add_argument("--extremes", type=int, default=10)
    a = p.parse_args()

    barres, msg = charge(a.entree)
    if len(barres) < 2:
        print("KO : il faut au moins deux symboles dans %s." % a.entree)
        return 1

    dis("=" * LARG)
    dis("ECART ENTRE CARNETS -- deux actifs, la meme journee")
    dis("=" * LARG)
    for m in msg:
        dis(m)
    if msg:
        dis()
    dis("  On ne compare pas des journees entre elles : on compare deux")
    dis("  actifs A L INTERIEUR de chaque journee. Ce qui les separe ne")
    dis("  peut etre ni un effet de periode, ni un effet de jour de")
    dis("  semaine, ni un changement d echeance -- ces trois causes")
    dis("  frappent les deux actifs en meme temps.")

    # --- seances et centiles, par symbole ---------------------------
    tab, cent = {}, {}
    dis()
    dis("-" * LARG)
    dis("  %-16s %8s %14s %10s %12s"
        % ("symbole", "seances", "med CVD/jour", "mult $/pt", "signe fige"))
    dis("-" * LARG)
    for sym in sorted(barres):
        s = par_seance(barres[sym])
        if len(s) < 20:
            dis("  %-16s %8d   moins de vingt seances, ecarte."
                % (sym, len(s)))
            continue
        cv = dict((j, x[0]) for j, x in s.items())
        fige = len(set(v > 0 for v in cv.values())) < 2
        rac, mult = multiplicateur(sym)
        dis("  %-16s %8d %14.0f %10s %12s"
            % (sym, len(s), mediane(list(cv.values())) or 0,
               ("%g (%s)" % (mult, rac)) if mult else "?",
               "OUI" if fige else "non"))
        if fige:
            dis("      ECARTE : son CVD ne change jamais de signe, il ne")
            dis("      mesure pas un desequilibre acheteur/vendeur.")
            continue
        tab[sym] = s
        cent[sym] = centiles(cv)
    dis("-" * LARG)
    dis("  Les multiplicateurs sont des specifications de contrat CME,")
    dis("  pas des mesures. Ils ne servent qu aux lignes en dollars ;")
    dis("  tout ce qui suit est en CENTILES et n en depend pas.")

    if len(tab) < 2:
        dis()
        dis("  Moins de deux symboles exploitables. Rien a comparer.")
        ecrire(a.sortie)
        return 1

    cal = lis_calendrier(a.calendrier, a.pays, a.importance)
    motifs = [x.strip().lower() for x in a.motif.split(",") if x.strip()]

    syms = sorted(tab)
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            sa, sb = syms[i], syms[j]
            communs = sorted(set(tab[sa]) & set(tab[sb]))
            if len(communs) < 20:
                continue
            dis()
            dis("=" * LARG)
            dis("ECART %s moins %s -- %d seances communes"
                % (sb, sa, len(communs)))
            dis("=" * LARG)
            ec = dict((d, cent[sb][d] - cent[sa][d]) for d in communs)
            vals = sorted(ec.values())
            dis("  ecart = centile(%s) - centile(%s), en points de centile."
                % (sb, sa))
            dis("  Negatif : %s est vendu plus durement que %s, rapporte"
                % (sb, sa))
            dis("  a ce que chacun fait d ordinaire.")
            dis()
            dis("  mediane %+.1f   q1 %+.1f   q3 %+.1f   min %+.1f   max %+.1f"
                % (mediane(vals), vals[len(vals) // 4],
                   vals[3 * len(vals) // 4], vals[0], vals[-1]))
            dis()
            dis("  Une mediane proche de zero dit que sur l ensemble des")
            dis("  seances aucun des deux n est systematiquement plus")
            dis("  vendu que l autre. C est la condition pour qu un ecart")
            dis("  observe un jour donne veuille dire quelque chose.")

            # --- les extremes -----------------------------------
            ordre = sorted(ec.items(), key=lambda kv: kv[1])
            dis()
            dis("  LES %d SEANCES OU %s EST LE PLUS VENDU RELATIVEMENT :"
                % (a.extremes, sb))
            dis("  %-12s %8s %10s %10s   %s"
                % ("date", "ecart", "c(" + sb[:6] + ")",
                   "c(" + sa[:6] + ")", "publications HIGH"))
            for d, v in ordre[:a.extremes]:
                evs = cal.get(d, [])
                dis("  %-12s %+8.1f %10.1f %10.1f   %s"
                    % (d, v, cent[sb][d], cent[sa][d],
                       ", ".join(e[:28] for e in evs[:2]) or "-"))

            # --- les journees nommees ---------------------------
            vises = []
            for d in communs:
                for e in cal.get(d, []):
                    if any(m in e.lower() for m in motifs):
                        vises.append((d, e))
                        break
            dis()
            if not vises:
                dis("  Aucune journee ne porte les motifs demandes (%s)"
                    % a.motif)
                dis("  dans la plage commune. Rien a situer.")
                continue
            dis("  LES JOURNEES NOMMEES -- %d trouvee(s)" % len(vises))
            dis("  %-12s %8s %10s %10s   %s"
                % ("date", "ecart", "rang", "sur", "evenement"))
            rangs = []
            for d, e in sorted(vises):
                r = sum(1 for x in vals if x < ec[d]) + 1
                rangs.append(r)
                dis("  %-12s %+8.1f %10d %10d   %s"
                    % (d, ec[d], r, len(vals), e[:34]))
            dis()
            dis("  `rang 1` = la seance ou %s est le plus vendu" % sb)
            dis("  relativement a %s. Un rang au milieu = journee" % sa)
            dis("  ordinaire pour l ecart entre les deux carnets.")

            # --- pre-enregistrement -----------------------------
            med_rang = mediane([float(r) for r in rangs])
            attendu = (len(vals) + 1) / 2.0
            dis()
            dis("  PRE-ENREGISTREMENT -- a lire avant de conclure")
            dis("  Rang median de ces journees : %.0f sur %d."
                % (med_rang, len(vals)))
            dis("  Sous l hypothese `ces journees n ont rien de")
            dis("  particulier`, on attendrait environ %.0f." % attendu)
            if len(rangs) < 5:
                dis()
                # Le `%` etait sur la ligne suivante : la premiere
                # imprimait un `%d` litteral et la seconde levait une
                # TypeError. Cette branche ne se declenche qu a moins de
                # cinq occurrences -- donc exactement sur les vraies
                # donnees, ou il y a trois CPI. Trouvee au banc.
                dis("  %d journee(s) : AUCUNE CONCLUSION POSSIBLE, et"
                    % len(rangs))
                dis("  aucun arrangement statistique n y changera rien.")
                dis("  Ce qui suit est une observation a confirmer HORS")
                dis("  ECHANTILLON, pas un resultat.")
            dis()
            dis("  A verifier aux %d prochaines occurrences, sans changer" % 3)
            dis("  ni la fenetre, ni le calcul, ni les symboles : si le")
            dis("  rang median reste du meme cote de %.0f, l observation"
                % attendu)
            dis("  tient. Sinon elle tombe. La date de verification et le")
            dis("  sens attendu doivent etre notes dans HYPOTHESES.md")
            dis("  AVANT la prochaine publication.")

    dis()
    dis("=" * LARG)
    dis("CE QUE CA NE DIT PAS")
    dis("=" * LARG)
    dis("  Aucun test : une poignee de journees ne fait pas un")
    dis("  echantillon. Ce fichier decrit et pre-enregistre, il ne")
    dis("  conclut pas.")
    dis("  Aucune causalite : un ecart de centiles ne dit pas qui vend,")
    dis("  ni pourquoi, ni si c est le meme acteur des deux cotes.")
    dis("  Aucun euro : le centile est sans echelle. Le lien au PnL")
    dis("  passe par churn_trades.jsonl.")
    dis("  Et surtout : le CVD d une seance ne dit rien de la SEQUENCE")
    dis("  a l interieur de la seance. Le 12/08, la fenetre de 14h30")
    dis("  montrait le S&P acheteur alors que sa journee est vendeuse.")
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
