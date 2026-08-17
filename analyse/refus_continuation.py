# -*- coding: utf-8 -*-
r"""
refus_continuation.py -- quand une tentative de continuation echoue,
le carnet le disait-il AVANT, ou seulement PENDANT ?

  python refus_continuation.py
  python refus_continuation.py --fenetre 60 --horizon 60 --tampon 3
  python refus_continuation.py --sens bas

LA DEMANDE, ET CE QU ELLE DEVIENT UNE FOIS MESURABLE

    "Le 05/08, le 12/08 et le 17/08, un debut de trend haussier a ete
    refuse et le prix est rentre dans le range. Il faut trouver les
    declencheurs."

    Trois journees ne sont pas une serie -- trois tirages du meme cote
    arrivent une fois sur huit. Mais les ecarter serait aussi faux que
    d en conclure quelque chose.

    LA BONNE QUESTION N EST PAS "que s est-il passe ces trois jours-la".
    C est : COMBIEN DE FOIS cet evenement s est-il produit dans les huit
    mois de carnets, et les trois journees remarquees en sont-elles des
    exemples ordinaires ?

    Trois journees remarquees a l oeil sont trois journees VECUES. Si
    l outil en trouve quarante, les trois n avaient rien de special et
    la regularite est ailleurs. S il n en trouve que cinq, elles sont
    l essentiel de la population et il n y a rien a mesurer.

    Dans les deux cas on sait quelque chose. C est le seul moyen de
    sortir du "3 sur 3".

CE QUI EST MESURE, ET AVEC QUELLE UNITE

    Une TENTATIVE de continuation, a la minute t :

        cloture(t) > plus_haut([t-W, t[) + k * u

    `u` est l UNITE DE BRUIT DE LA JOURNEE ET DE L ACTIF : la mediane
    des variations absolues d une minute a l autre, ce jour-la, sur cet
    actif. Elle est MESUREE, pas choisie.

    C est le tampon qui manquait a H27, et son absence y est ecrite
    noir sur blanc : sans lui, franchir un bord d un centieme de point
    compte autant que le franchir de dix, ce qui avantage
    mecaniquement les actifs calmes. Ici k * u remplace le seuil
    invente. Le tampon est affiche par actif et par journee.

    La suite, sur [t, t+H], donne TROIS issues et non deux :

        REFUS         cloture(t+H) < niveau - k*u   (reintegration nette)
        CONTINUATION  cloture(t+H) > niveau + k*u
        INDECIS       entre les deux

    L INDECIS est une categorie a part exprès. Le 17/08 on a consigne
    qu une branche par defaut n est pas un fourre-tout : verser les
    indecis dans les refus gonflerait le groupe qui nous interesse avec
    des cas qui ne sont pas des refus.

CE QUE LE CARNET DIT, ET QUAND

    Pour chaque evenement, trois mesures separees dans le TEMPS :

        APPROCHE   delta sur [t-W, t[    -- avant que ca se decide
        DECISION   delta sur [t, t+H]    -- pendant
        VOLUME     sur [t, t+H], rapporte au volume minute median du jour

    C est la separation qui repond a la question posee. Si le delta
    d APPROCHE distingue deja les refus des continuations, le carnet
    prevenait : il y a un declencheur. Si seul le delta de DECISION
    les distingue, le carnet DECRIT le refus au moment ou il a lieu --
    instructif, mais sans avance.

    La meme distinction que patch_decalage.py, appliquee ici a un
    evenement au lieu d une correlation d ensemble.

LE SECOND ACTIF, SIMULTANEMENT

    Pour chaque evenement sur un actif, les memes mesures sont prises
    sur l AUTRE au meme instant. "Les trois reviennent et shortent
    fort" est une observation sur la simultaneite ; c est la colonne
    `autre` qui la teste, dans la limite de deux actifs.

LA LIMITE, ECRITE D ABORD

    IL N Y A PAS DE NASDAQ DANS LES CARNETS. `MNQM26`, `MNQU26`,
    `NQM26` font 1 Ko -- verifie le 17/08, pas suppose. Le refus du
    plus haut du Nasdaq est donc INVISIBLE a cet outil. Il mesure le
    S&P et le Dow qui l accompagnent, jamais l actif qui a refuse.

    Toute lecture qui presenterait un resultat MES/YM comme la
    confirmation d un comportement du Nasdaq serait fausse.

CE QUE CET OUTIL NE DIT PAS

    Aucun euro. Ce sont des points et des contrats. Le passage a
    l euro exige des tickets, des frais et un spread, et il passe par
    churn_trades.jsonl.

    Aucune causalite. Un carnet qui provoque le refus et un refus qui
    attire le carnet produisent la meme difference.

    Et un evenement defini avec W, H et k est un evenement parmi
    d autres. Les trois valeurs sont affichees ; les balayer jusqu a ce
    que le resultat parle serait un balayage, et un balayage trouve
    toujours un maximum.

LECTEUR SEUL. N ouvre aucun fichier en ecriture.
"""
import argparse
import bisect
import csv
import io
import os
import random
import sys
from datetime import datetime, timedelta

DOSSIER = os.path.join("cartes", "scid")
GRAINE = 20260817

# Les journees citees par l utilisateur. Elles sont MARQUEES dans la
# liste des evenements, pas traitees a part : si elles sont ordinaires,
# elles doivent se perdre au milieu des autres.
CITEES = ("2026-08-05", "2026-08-12", "2026-08-17")

FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
           "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S")


def dis(*a):
    print(*a)


def horo(s):
    if not s:
        return None
    s = s.strip()
    for f in FORMATS:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def med(v):
    if not v:
        return None
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def charge(dossier):
    """Les of_*.csv, dedoublonnes par la colonne `contrat`.

    Un fichier qui porte une colonne `contrat` est un raccord et
    declare lui-meme les echeances qu il absorbe. On lit ce que les
    donnees declarent, jamais un motif de nom de fichier."""
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


def par_jour(serie):
    """Les barres regroupees par date, seances seulement.

    Une seance est une date portant au moins la moitie du nombre
    median de barres -- les futures CME rouvrent le dimanche soir et
    creent des seances fantomes de quelques barres."""
    j = {}
    for b in serie:
        j.setdefault(b[0].date(), []).append(b)
    cpt = sorted(len(v) for v in j.values())
    m = cpt[len(cpt) // 2] if cpt else 0
    seuil = max(30, m // 2)
    return dict((d, v) for d, v in j.items() if len(v) >= seuil), m, seuil


def index_minute(barres):
    """{minute -> barre}, pour retrouver l autre actif au meme instant."""
    return dict((b[0].replace(second=0, microsecond=0), b) for b in barres)


def fenetre(barres, ts, t0, t1):
    """Les barres dont l horodatage est dans [t0, t1[.

    Definie en TEMPS et non en nombre de barres. Une fenetre comptee
    en lignes s etire silencieusement sur les heures creuses : c est
    la faute du 17/08 au matin, ou une `fenetre de 15 minutes`
    couvrait deux heures.

    `ts` est la liste triee des horodatages. On la coupe par recherche
    dichotomique : un balayage lineaire par barre couterait 1250 x 1250
    operations par seance et par symbole, soit des dizaines de minutes
    sur les huit mois."""
    return barres[bisect.bisect_left(ts, t0):bisect.bisect_left(ts, t1)]


def evenements(barres, W, H, k, sens):
    """Les tentatives de continuation, avec leur issue.

    Rend une liste de dicts. Le niveau franchi, le tampon utilise et
    les trois mesures de carnet y sont, pour que rien du verdict ne
    soit calcule par un chemin que la sortie ne montre pas."""
    if len(barres) < 3:
        return [], None
    # Unite de bruit de la journee : mediane des variations absolues
    # d une minute a l autre. Mesuree, pas choisie.
    u = med([abs(barres[i][1] - barres[i - 1][1])
             for i in range(1, len(barres))])
    if not u or u <= 0:
        return [], None
    vmed = med([b[3] for b in barres]) or 0.0
    tampon = k * u

    ts = [b[0] for b in barres]
    out = []
    dernier = None
    for i, b in enumerate(barres):
        t, c = b[0], b[1]
        av = fenetre(barres, ts, t - _min(W), t)
        if len(av) < W // 3:          # fenetre trop creuse pour un bord
            continue
        if sens == "haut":
            niveau = max(x[1] for x in av)
            perce = c > niveau + tampon
        else:
            niveau = min(x[1] for x in av)
            perce = c < niveau - tampon
        if not perce:
            continue
        # Periode refractaire : une tentative par fenetre. Sans elle,
        # une seule poussee compte quarante fois.
        if dernier is not None and (t - dernier).total_seconds() < W * 60:
            continue
        ap = fenetre(barres, ts, t, t + _min(H) + _min(1))
        if len(ap) < H // 3:
            continue
        fin = ap[-1][1]
        if sens == "haut":
            if fin < niveau - tampon:
                issue = "REFUS"
            elif fin > niveau + tampon:
                issue = "CONTINUATION"
            else:
                issue = "INDECIS"
        else:
            if fin > niveau + tampon:
                issue = "REFUS"
            elif fin < niveau - tampon:
                issue = "CONTINUATION"
            else:
                issue = "INDECIS"
        dernier = t
        out.append({
            "t": t, "jour": t.date(), "issue": issue,
            "niveau": niveau, "tampon": tampon, "u": u,
            "approche": sum(x[2] for x in av),
            "decision": sum(x[2] for x in ap),
            "vol": (sum(x[3] for x in ap) / (vmed * max(1, len(ap)))
                    if vmed else 0.0),
            "amplitude": (fin - niveau) / u,
        })
    return out, u


def _min(n):
    return timedelta(minutes=n)


def p_stratifie(evs, champ, tirages, graine=GRAINE):
    """p par permutation des ISSUES A L INTERIEUR DE CHAQUE JOURNEE.

    Deux evenements d une meme seance voient le meme marche, la meme
    humeur, la meme nouvelle du matin. Permuter les issues toutes
    journees confondues ferait naitre la difference de l effet de
    journee et de rien d autre.

    Seules les journees portant A LA FOIS un refus et une continuation
    contribuent -- une journee dont tous les evenements ont la meme
    issue ne peut rien permuter. Leur nombre est rendu : si moins de
    dix contribuent, il n y a pas de test, et on le dit au lieu
    d imprimer un nombre.

    Les INDECIS sont exclus du test. Ils ne sont ni l un ni l autre,
    et les verser dans un groupe pour gonfler l effectif serait la
    faute de la branche fourre-tout.

    Travaille sur des listes de nombres et permute des ETIQUETTES, pas
    des dictionnaires : une version qui recopiait les evenements a
    chaque tirage mettait plus de deux minutes au banc."""
    jours = {}
    for e in evs:
        if e["issue"] in ("REFUS", "CONTINUATION"):
            jours.setdefault(e["jour"], []).append((e["issue"], e[champ]))
    utiles = [v for v in jours.values()
              if len(set(i for i, _ in v)) > 1]
    if len(utiles) < 10:
        return None, None, len(utiles)

    vals, labs, bornes = [], [], []
    for v in utiles:
        a = len(vals)
        for i, x in v:
            labs.append(i)
            vals.append(x)
        bornes.append((a, len(vals)))

    def ecart(et):
        a = [vals[i] for i in range(len(vals)) if et[i] == "REFUS"]
        b = [vals[i] for i in range(len(vals)) if et[i] != "REFUS"]
        if not a or not b:
            return None
        return med(a) - med(b)

    obs = ecart(labs)
    if obs is None:
        return None, None, len(utiles)
    al = random.Random(graine)
    cour = list(labs)
    pires = 0
    for _ in range(tirages):
        for a, b in bornes:
            bloc = cour[a:b]
            al.shuffle(bloc)
            cour[a:b] = bloc
        c = ecart(cour)
        if c is not None and abs(c) >= abs(obs):
            pires += 1
    return obs, (1.0 + pires) / (1.0 + tirages), len(utiles)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dossier", default=DOSSIER)
    p.add_argument("--fenetre", type=int, default=60,
                   help="W minutes : le range qu on tente de franchir")
    p.add_argument("--horizon", type=int, default=60,
                   help="H minutes : le delai au bout duquel on juge")
    p.add_argument("--tampon", type=float, default=3.0,
                   help="k : le franchissement doit valoir k fois le "
                        "bruit minute median du jour")
    p.add_argument("--sens", choices=("haut", "bas"), default="haut")
    p.add_argument("--tirages", type=int, default=2000)
    a = p.parse_args()

    dis("=" * 78)
    dis("REFUS DE CONTINUATION -- le carnet prevenait-il, ou decrivait-il ?")
    dis("=" * 78)
    dis("  fenetre W = %d min   horizon H = %d min   tampon k = %.1f"
        % (a.fenetre, a.horizon, a.tampon))
    dis("  sens : %s" % ("franchissement du HAUT" if a.sens == "haut"
                         else "franchissement du BAS"))
    dis()
    dis("  IL N Y A PAS DE NASDAQ DANS LES CARNETS -- MNQM26, MNQU26 et")
    dis("  NQM26 font 1 Ko, verifie le 17/08. Un refus du plus haut du")
    dis("  Nasdaq est INVISIBLE ici. Cet outil mesure le S&P et le Dow")
    dis("  qui l accompagnent, jamais l actif qui a refuse.")
    dis()

    barres, msg = charge(a.dossier)
    for m in msg:
        dis(m)
    if len(barres) < 1:
        dis("KO : aucun of_*.csv dans %s." % a.dossier)
        return 1

    # --- couverture, avant toute mesure -----------------------------
    dis("-" * 78)
    dis("  %-16s %8s %8s %12s %12s" % ("symbole", "barres", "seances",
                                       "debut", "fin"))
    dis("-" * 78)
    jours = {}
    for sym in sorted(barres):
        j, m, seuil = par_jour(barres[sym])
        jours[sym] = j
        ds = sorted(j)
        dis("  %-16s %8d %8d %12s %12s"
            % (sym, len(barres[sym]), len(j),
               ds[0] if ds else "-", ds[-1] if ds else "-"))
    dis("-" * 78)
    dis("  Une seance est une date portant au moins la moitie du nombre")
    dis("  median de barres. Les reouvertures CME du dimanche soir en")
    dis("  creent de fantomes, de quelques barres, qui feraient des")
    dis("  journees sans en etre.")
    dis()

    # --- les evenements ---------------------------------------------
    tout = {}
    for sym in sorted(jours):
        evs = []
        us = []
        for d in sorted(jours[sym]):
            e, u = evenements(sorted(jours[sym][d]), a.fenetre,
                              a.horizon, a.tampon, a.sens)
            evs.extend(e)
            if u:
                us.append(u)
        tout[sym] = evs
        n = dict((k, 0) for k in ("REFUS", "CONTINUATION", "INDECIS"))
        for e in evs:
            n[e["issue"]] += 1
        dis("  %-16s %4d tentatives   REFUS %d   CONTINUATION %d   "
            "INDECIS %d" % (sym, len(evs), n["REFUS"], n["CONTINUATION"],
                            n["INDECIS"]))
        if us:
            dis("  %-16s bruit minute median du jour : %.3f point "
                "(tampon = %.2f)" % ("", med(us), a.tampon * med(us)))
    dis()

    # --- les trois journees citees, au milieu des autres ------------
    dis("=" * 78)
    dis("LES JOURNEES CITEES, PARMI LES AUTRES")
    dis("=" * 78)
    dis("  Trois journees remarquees a l oeil sont trois journees")
    dis("  VECUES. Si elles se perdent au milieu de quarante, elles n")
    dis("  avaient rien de special et la regularite est ailleurs.")
    dis()
    for sym in sorted(tout):
        vus = [e for e in tout[sym] if str(e["jour"]) in CITEES]
        if not vus:
            dis("  %-16s aucune tentative ces jours-la." % sym)
            continue
        dis("  %s" % sym)
        dis("    %-19s %-13s %9s %9s %8s %7s"
            % ("instant", "issue", "approche", "decision", "vol/med",
               "ampl/u"))
        for e in sorted(vus, key=lambda x: x["t"]):
            dis("    %-19s %-13s %9.0f %9.0f %8.2f %7.1f"
                % (e["t"].strftime("%Y-%m-%d %H:%M"), e["issue"],
                   e["approche"], e["decision"], e["vol"],
                   e["amplitude"]))
    dis()

    # --- la question : avant, ou pendant ? --------------------------
    dis("=" * 78)
    dis("LE CARNET PREVENAIT-IL, OU DECRIVAIT-IL ?")
    dis("=" * 78)
    dis("  Ecart = mediane(REFUS) - mediane(CONTINUATION).")
    dis("  p par permutation des ISSUES A L INTERIEUR DE CHAQUE JOURNEE :")
    dis("  deux tentatives d une meme seance voient le meme marche, et")
    dis("  permuter toutes journees confondues ferait naitre la")
    dis("  difference de l effet de journee.")
    dis()
    verdict = {}
    for sym in sorted(tout):
        evs = tout[sym]
        r = len([e for e in evs if e["issue"] == "REFUS"])
        c = len([e for e in evs if e["issue"] == "CONTINUATION"])
        dis("  %s   REFUS %d   CONTINUATION %d" % (sym, r, c))
        if r < 15 or c < 15:
            dis("    Moins de 15 d un cote : rien n est teste. Ce n est")
            dis("    pas un resultat nul, c est une absence de mesure.")
            dis()
            verdict[sym] = None
            continue
        dis("    %-12s %12s %10s %10s" % ("mesure", "ecart", "p", "jours"))
        res = {}
        for champ, nom in (("approche", "APPROCHE"),
                           ("decision", "DECISION"),
                           ("vol", "VOLUME")):
            e, pv, nj = p_stratifie(evs, champ, a.tirages)
            res[champ] = (e, pv)
            if e is None:
                dis("    %-12s %12s %10s %10d   (moins de 10 journees "
                    "melangees)" % (nom, "-", "-", nj))
            else:
                dis("    %-12s %12.1f %10.4f %10d" % (nom, e, pv, nj))
        verdict[sym] = res
        dis()

    # --- ce que ca veut dire ----------------------------------------
    dis("=" * 78)
    dis("LECTURE")
    dis("=" * 78)
    for sym in sorted(verdict):
        r = verdict[sym]
        if r is None:
            dis("  %-16s pas assez d evenements des deux cotes." % sym)
            continue
        ea, pa = r["approche"]
        ed, pd = r["decision"]
        parle_avant = ea is not None and pa is not None and pa < 0.05
        parle_pendant = ed is not None and pd is not None and pd < 0.05
        if parle_avant and parle_pendant:
            dis("  %-16s le carnet DIFFERE DEJA PENDANT L APPROCHE." % sym)
            dis("  %-16s Il y a un declencheur mesurable avant que le" % "")
            dis("  %-16s refus ait lieu. C est le seul cas qui donne une" % "")
            dis("  %-16s avance, et il demande une verification hors" % "")
            dis("  %-16s echantillon avant d en faire quoi que ce soit." % "")
        elif parle_pendant:
            dis("  %-16s le carnet ne distingue les deux issues que" % sym)
            dis("  %-16s PENDANT. Il DECRIT le refus au moment ou il a" % "")
            dis("  %-16s lieu -- exact, instructif, et sans avance. Un" % "")
            dis("  %-16s flux live serait un compte rendu, pas un signal." % "")
        elif parle_avant:
            dis("  %-16s le carnet differe AVANT et plus apres." % sym)
            dis("  %-16s Resultat inhabituel : a verifier avant d y" % "")
            dis("  %-16s croire, il ressemble plus a un artefact qu a un" % "")
            dis("  %-16s signal." % "")
        else:
            dis("  %-16s AUCUNE des trois mesures ne separe les refus" % sym)
            dis("  %-16s des continuations. Sur cette definition d" % "")
            dis("  %-16s evenement, le carnet ne distingue pas les deux." % "")
    dis()
    dis("  W, H et k valent %d, %d et %.1f. Les rebalayer jusqu a ce que"
        % (a.fenetre, a.horizon, a.tampon))
    dis("  le resultat parle serait un balayage, et un balayage trouve")
    dis("  toujours un maximum : le maximum d une recherche sous H0 vaut")
    dis("  deja 1,5 a 3 ecarts types.")
    dis()
    dis("  Aucun euro ici : des points et des contrats. Le passage a")
    dis("  l euro exige des tickets, des frais et un spread, et il passe")
    dis("  par churn_trades.jsonl.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
