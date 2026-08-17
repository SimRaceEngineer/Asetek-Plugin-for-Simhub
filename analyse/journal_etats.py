# -*- coding: utf-8 -*-
r"""
journal_etats.py -- ce bloc de 14:30:32 est-il un evenement de marche
ou une horloge du moteur ? et quels labels decrivent vraiment un regime ?

  python journal_etats.py
  python journal_etats.py --seconde "14:30:32"
  python journal_etats.py --taille 6

LES DEUX QUESTIONS, POSEES PAR L UTILISATEUR LE 17/08

    1. "Est-ce qu on ne tient pas la une bougie spike ?" -- a propos du
       12/08 a 14:30:32, ou TREIZE changements d etat tombent dans la
       MEME seconde, sur les trois actifs.

    2. "Est-ce que ce sont tous des elements differents lorsqu on a BUY
       puis TREND_DYING ?"

CE QUI REND LE BLOC DE 14:30:32 SUSPECT -- DANS LES DEUX SENS

    Partout ailleurs le journal change par un ou deux champs sur un
    seul actif. La, treize d un coup sur les trois. 14:30 heure VPS,
    c est 8h30 a New York : l heure des statistiques americaines. Ca
    colle.

    Mais dans le meme bloc, `ib_etat` passe de UNKNOWN a INSIDE sur les
    TROIS actifs simultanement. L initial balance ne devient pas
    definie parce que le marche bouge : elle devient definie parce que
    sa fenetre de calcul s ouvre. C est la signature d une HORLOGE, pas
    d un choc.

    Les deux peuvent tomber a la meme seconde. Sur une seule journee on
    ne peut pas les separer. Sur dix-huit, si.

        Un bloc qui revient a la MEME HEURE plusieurs jours de suite
        est un evenement PROGRAMME. Un bloc unique a sa journee est un
        evenement SUBI.

    C est tout le test, et il ne demande aucune donnee nouvelle.

LA SECONDE QUESTION : NON, CE NE SONT PAS LES MEMES ELEMENTS

    Le journal melangeait dans une seule colonne deux natures qui n ont
    rien a voir :

        biais                       une DECISION (BUY / SELL / HOLD)
        fr_ev, fr_canal, fr_fb,
        bb_etat, piege_side         des DIAGNOSTICS
        ib_etat                     une horloge, et une position

    "BUY" est ce que le moteur veut faire ; "TREND_DYING" est ce qu il
    croit voir. Les voir se suivre n est pas une contradiction -- ce
    sont deux phrases sur deux sujets.

    Mais il y a plus genant, et c est mesurable : dans l extrait du
    12/08, `fr_ev` fait NEUTRAL -> TREND_DYING -> NEUTRAL en quarante
    secondes, et `biais` fait HOLD -> BUY -> HOLD en trente-trois
    secondes. Un label qui change trois fois par minute ne decrit pas
    un regime, il decrit du bruit d etiquetage.

    D ou la DUREE DE SEJOUR : combien de temps chaque label tient avant
    de basculer. Un champ dont la mediane de sejour vaut vingt secondes
    ne peut pas servir de condition d entree, quelle que soit la
    qualite du reste.

CE QUE CE FICHIER NE FAIT PAS

    Il ne regarde AUCUN prix. C est volontaire : la question porte sur
    ce que le moteur enregistre, pas sur ce que le marche a fait. Les
    deux se croiseront apres, et separement.

    Il trie par horodatage avant de mesurer -- les CSV ne sont pas dans
    l ordre, ce qu on a decouvert le meme jour, et aucune duree n a de
    sens sur des lignes desordonnees.

LECTEUR SEUL : lit les CSV de cartes\cycles\, ecrit un .txt.
"""
import argparse
import csv
import io
import os
import sys
import datetime as dt

ENTREE = os.path.join("cartes", "cycles")
SORTIE = os.path.join("cartes", "panel_journal.txt")
ACTIFS = ("US30", "US500", "US100")
LARG = 100

# Chaque champ avec sa NATURE. C est la reponse a la deuxieme question
# de l utilisateur, ecrite dans le code et pas seulement dans une
# phrase : une decision et un diagnostic ne se lisent pas pareil.
CHAMPS = (
    ("biais", "DECISION"),
    ("fr_ev", "diagnostic"),
    ("fr_canal", "diagnostic"),
    ("fr_fb", "diagnostic"),
    ("bb_etat", "diagnostic"),
    ("piege_side", "diagnostic"),
    ("ib_etat", "horloge/position"),
)
RACINE = (("alignment", "diagnostic"), ("leader", "diagnostic"),
          ("weakest", "diagnostic"))

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def horo(s):
    if not s:
        return None
    s = s.strip().replace("T", " ")
    try:
        return dt.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def quantile(v, q):
    if not v:
        return None
    v = sorted(v)
    return v[int(q * (len(v) - 1))]


def charge(dossier):
    """Les journees, TRIEES par horodatage.

    Le tri n est pas une precaution de style : les CSV contiennent des
    lignes qui reculent dans le temps, et une duree de sejour calculee
    sur des lignes desordonnees serait negative ou absurde."""
    jours = {}
    if not os.path.isdir(dossier):
        return jours
    for nom in sorted(os.listdir(dossier)):
        if not nom.startswith("cycles_") or not nom.endswith(".csv"):
            continue
        with io.open(os.path.join(dossier, nom), encoding="utf-8",
                     errors="replace") as f:
            L = []
            for r in csv.DictReader(f, delimiter=";"):
                t = horo(r.get("ts"))
                if t:
                    r["_t"] = t
                    L.append(r)
        if L:
            L.sort(key=lambda r: r["_t"])
            jours[nom[7:-4]] = L
    return jours


def changements(L):
    """Tous les changements d etiquette, avec leur horodatage.

    Rend une liste de (t, actif, champ, avant, apres, nature)."""
    out = []
    for i in range(1, len(L)):
        a, b = L[i - 1], L[i]
        for c, nat in RACINE:
            va, vb = (a.get(c) or ""), (b.get(c) or "")
            if va != vb:
                out.append((b["_t"], "(global)", c, va, vb, nat))
        for x in ACTIFS:
            for c, nat in CHAMPS:
                cle = "%s_%s" % (x, c)
                va, vb = (a.get(cle) or ""), (b.get(cle) or "")
                if va != vb:
                    out.append((b["_t"], x, c, va, vb, nat))
    return out


def blocs(chg, taille):
    """Les secondes ou beaucoup de champs basculent d un coup.

    On regroupe a la SECONDE et on ne garde que les groupes d au moins
    `taille` changements touchant au moins deux actifs. Un seul actif
    qui bascule cinq champs, c est un actif qui bouge ; trois actifs
    qui basculent ensemble, c est autre chose."""
    par_sec = {}
    for t, actif, c, va, vb, nat in chg:
        par_sec.setdefault(t, []).append((actif, c, va, vb, nat))
    out = []
    for t in sorted(par_sec):
        g = par_sec[t]
        actifs = set(a for a, _, _, _, _ in g if a != "(global)")
        if len(g) >= taille and len(actifs) >= 2:
            out.append((t, g))
    return out


def sejours(jours):
    """Combien de temps chaque champ garde sa valeur avant de changer.

    On mesure PAR JOURNEE, jamais a cheval : la nuit n est pas un
    sejour de quinze heures, c est une absence d observation."""
    out = {}
    perdus = 0
    for j in sorted(jours):
        L = jours[j]
        # Le flux est troue : l audit de cadence du 17/08 donne 48 % de
        # part utile mediane, avec des trous allant jusqu a plusieurs
        # heures. Un sejour mesure a cheval sur un trou n est pas un
        # sejour long, c est une absence d observation. On calcule donc
        # le seuil de trou SUR LA JOURNEE (cinq fois son propre pas
        # median) et on jette tout sejour qui en enjambe un.
        ec = []
        for i in range(1, len(L)):
            d = (L[i]["_t"] - L[i - 1]["_t"]).total_seconds()
            if d > 0:
                ec.append(d)
        p50 = quantile(ec, 0.5) or 10.0
        seuil = 5.0 * p50
        cles = [("(global)", c, nat) for c, nat in RACINE]
        cles += [(x, c, nat) for x in ACTIFS for c, nat in CHAMPS]
        for actif, c, nat in cles:
            cle = c if actif == "(global)" else "%s_%s" % (actif, c)
            debut = None
            val = None
            troue = False
            prec = None
            for r in L:
                if prec is not None and \
                        (r["_t"] - prec).total_seconds() > seuil:
                    troue = True
                prec = r["_t"]
                v = r.get(cle) or ""
                if val is None:
                    val, debut, troue = v, r["_t"], False
                    continue
                if v != val:
                    d = (r["_t"] - debut).total_seconds()
                    if troue:
                        perdus += 1
                    elif 0 < d < 6 * 3600:
                        out.setdefault((c, nat), []).append(d)
                    val, debut, troue = v, r["_t"], False
    return out, perdus


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entree", default=ENTREE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--taille", type=int, default=6,
                   help="taille minimale d un bloc synchrone")
    p.add_argument("--seconde", default="14:30:32",
                   help="l heure a examiner en detail")
    p.add_argument("--tolerance", type=int, default=120,
                   help="secondes d ecart pour dire `meme heure`")
    a = p.parse_args()

    jours = charge(a.entree)
    if not jours:
        print("KO : aucun CSV dans %s." % a.entree)
        print("     Lance d abord : python extraire_cycles.py")
        return 1
    noms = sorted(jours)

    dis("=" * LARG)
    dis("JOURNAL DES ETATS -- HORLOGE DU MOTEUR OU EVENEMENT DE MARCHE ?")
    dis("=" * LARG)
    dis("  %d journees (%s a %s)." % (len(noms), noms[0], noms[-1]))
    dis("  genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dis()
    dis("  Aucun prix n est lu ici. La question porte sur ce que le")
    dis("  moteur enregistre, pas sur ce que le marche a fait.")
    dis()
    dis("  Les lignes sont TRIEES par horodatage avant toute mesure :")
    dis("  les CSV en contiennent qui reculent dans le temps.")
    dis("=" * LARG)

    # ---------------- 1. les blocs synchrones ----------------
    dis()
    dis("=" * LARG)
    dis("1. LES BLOCS SYNCHRONES -- au moins %d changements dans la meme"
        % a.taille)
    dis("   seconde, sur au moins deux actifs")
    dis("=" * LARG)
    tous = {}
    for j in noms:
        b = blocs(changements(jours[j]), a.taille)
        tous[j] = b
    total = sum(len(v) for v in tous.values())
    dis("  %d bloc(s) sur %d journees." % (total, len(noms)))
    if not total:
        dis("  Aucun. Le bloc de 14:30:32 serait alors unique -- mais")
        dis("  verifier --taille avant de le croire.")
    dis()
    dis("  %-12s %10s %7s %s" % ("jour", "heure", "taille", "champs"))
    par_heure = {}
    for j in noms:
        for t, g in tous[j]:
            champs = {}
            for _, c, _, _, _ in g:
                champs[c] = champs.get(c, 0) + 1
            dis("  %-12s %10s %7d %s"
                % (j, t.strftime("%H:%M:%S"), len(g),
                   ", ".join("%s x%d" % (k, v)
                             for k, v in sorted(champs.items(),
                                                key=lambda x: -x[1]))[:58]))
            sec = t.hour * 3600 + t.minute * 60 + t.second
            par_heure.setdefault(j, []).append((sec, t, len(g)))

    # ---------------- 2. l heure demandee ----------------
    dis()
    dis("=" * LARG)
    dis("2. L HEURE %s REVIENT-ELLE LES AUTRES JOURS ?" % a.seconde)
    dis("=" * LARG)
    dis("  C est le test qui separe une horloge d un evenement. Un bloc")
    dis("  qui revient a la meme heure plusieurs jours de suite est")
    dis("  PROGRAMME ; un bloc unique a sa journee est SUBI.")
    dis()
    try:
        hh, mm, ss = [int(x) for x in a.seconde.split(":")]
        cible = hh * 3600 + mm * 60 + ss
    except ValueError:
        dis("  --seconde illisible (attendu HH:MM:SS).")
        cible = None
    if cible is not None:
        trouve = []
        for j in noms:
            for sec, t, n in par_heure.get(j, []):
                if abs(sec - cible) <= a.tolerance:
                    trouve.append((j, t, n))
        dis("  %-12s %10s %7s" % ("jour", "heure", "taille"))
        for j, t, n in trouve:
            dis("  %-12s %10s %7d" % (j, t.strftime("%H:%M:%S"), n))
        dis()
        if len(trouve) >= 3:
            dis("  => %d journees sur %d ont un bloc a +/- %d s de %s."
                % (len(trouve), len(noms), a.tolerance, a.seconde))
            dis("     C est une HORLOGE DU MOTEUR. Le bloc du 12/08 n a")
            dis("     donc rien de propre a cette journee-la, et il ne")
            dis("     peut pas servir a dater un CPI. Ce qui reste a")
            dis("     regarder pour le 12/08, c est ce que les PRIX ont")
            dis("     fait a cette seconde -- pas les etiquettes.")
        elif len(trouve) == 0:
            dis("  => Aucun bloc a cette heure, aucun jour. Soit")
            dis("     --taille est trop haut, soit le bloc examine etait")
            dis("     plus petit que le seuil.")
        else:
            dis("  => Seulement %d journee(s). Ce n est pas assez pour")
            dis("     parler d horloge, ni assez peu pour parler d un")
            dis("     evenement unique. A regarder ligne par ligne :")
            dis("     si `ib_etat` est dans le bloc, c est une fenetre")
            dis("     de calcul qui s ouvre, pas un choc.")

    # ---------------- 3. duree de sejour ----------------
    dis()
    dis("=" * LARG)
    dis("3. DUREE DE SEJOUR -- quels labels decrivent un regime, et")
    dis("   lesquels sont du bruit d etiquetage")
    dis("=" * LARG)
    dis("  Combien de temps un champ garde sa valeur avant de changer.")
    dis("  Mesure PAR JOURNEE, jamais a cheval sur la nuit.")
    dis()
    dis("  %-14s %-18s %8s %9s %9s %9s"
        % ("champ", "nature", "n", "p25 s", "median s", "p75 s"))
    sj, perdus = sejours(jours)
    for (c, nat) in sorted(sj, key=lambda k: -(quantile(sj[k], 0.5) or 0)):
        v = sj[(c, nat)]
        dis("  %-14s %-18s %8d %9.0f %9.0f %9.0f"
            % (c, nat, len(v), quantile(v, 0.25) or 0,
               quantile(v, 0.5) or 0, quantile(v, 0.75) or 0))
    dis()
    dis("  %d sejour(s) ecarte(s) parce qu ils enjambaient un trou du"
        % perdus)
    dis("  flux. Un sejour a cheval sur un trou n est pas un sejour")
    dis("  long, c est une absence d observation.")
    dis()
    court = [c for (c, nat) in sj if (quantile(sj[(c, nat)], 0.5) or 0) < 60]
    if court:
        dis("  Champs dont la valeur mediane tient MOINS D UNE MINUTE :")
        dis("    %s" % ", ".join(sorted(court)))
        dis()
        dis("  Un label qui bascule plusieurs fois par minute ne decrit")
        dis("  pas un regime. Il ne peut pas servir de condition")
        dis("  d entree : le temps de le lire, il a change. Ca ne veut")
        dis("  pas dire qu il est faux -- il peut etre une mesure fine")
        dis("  et juste -- mais il demande d etre lisse avant d etre")
        dis("  utilise, et personne n a decide comment.")
    else:
        dis("  Aucun champ ne bascule en moins d une minute en mediane.")

    dis()
    dis("=" * LARG)
    dis("CE QUE CA NE DIT PAS")
    dis("=" * LARG)
    dis("  Rien sur les prix, rien sur les euros. Un bloc synchrone")
    dis("  peut tres bien coincider avec un vrai choc ET avec une")
    dis("  horloge : les deux tombent a 14:30 si la fenetre d initial")
    dis("  balance s ouvre a l heure des statistiques. Le seul moyen de")
    dis("  les separer reste le prix a cette seconde-la, sur les")
    dis("  journees ou l horloge sonne SANS statistique.")

    d = os.path.dirname(a.sortie)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.sortie, "w", encoding="utf-8").write("\n".join(_ECHO) + "\n")
    print()
    print("ecrit : %s (%d octets)" % (a.sortie, os.path.getsize(a.sortie)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
