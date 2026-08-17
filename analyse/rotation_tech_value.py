# -*- coding: utf-8 -*-
r"""
rotation_tech_value.py -- les techs s achetent-elles plus que les
values, et depuis quand ?

  python rotation_tech_value.py
  python rotation_tech_value.py --fenetre 15

LA QUESTION, POSEE PAR L UTILISATEUR LE 17/08

    "Ces bougies delimitees a fort spike haut/bas (ce sont celles au
    moment des CPI) auraient un impact. On voit que de la, l US30 est
    travaille a la baisse en vue de trouver un support au profit des
    techs qui elles sont achetees pour du long terme. Peut-etre que tu
    peux regarder si depuis ces CPI a date les techs s achetent plus
    que les values."

    Trois choses distinctes la-dedans, et il faut les separer sinon on
    confirme ce qu on croit :

      1. reperer les chocs DANS LES DONNEES, pas a la main ;
      2. mesurer l ecart techs / values, en % et pas en points ;
      3. dire si le changement apres le choc est distinguable du
         hasard, sachant qu on a tres peu de journees apres.

CE QU ON MESURE

    L ECART. US30 vaut ~53 700 et US500 ~7 794 : un point ne veut pas
    dire la meme chose. Tout est ramene en POURCENT du prix d ouverture
    de la journee. L ecart du jour est alors

        ecart_tech = rendement(US100) - rendement(US30)
        ecart_500  = rendement(US500) - rendement(US30)

    Un ecart positif veut dire "la tech a fait mieux que la value ce
    jour-la", que le marche monte ou descende. C est bien une rotation
    qu on mesure, pas une tendance.

    LE CHOC. Une journee est marquee CHOC si les TROIS actifs font, au
    cours de la meme fenetre de %(fen)d minutes, un mouvement en %% qui
    depasse un multiple de leur mediane journaliere habituelle. Les
    trois ensemble : c est ce qui distingue une nouvelle macro (CPI)
    d un spike propre a un actif. La date n est pas saisie a la main --
    si le detecteur ne trouve rien, on n a pas de choc, et on le dit.

    LA COMPARAISON. Moyenne de l ecart AVANT le premier choc contre
    moyenne A PARTIR du choc.

CE QUI CALIBRE LE RESULTAT

    Permutation par JOURNEE : on melange les etiquettes avant/apres
    entre journees entieres, en gardant les effectifs, et on regarde a
    quelle frequence le hasard fait au moins aussi bien. C est la meme
    methode que `cassure_par_actif.py`. Elle respecte le fait qu une
    journee entiere est l unite d observation -- les cycles d une meme
    journee ne sont pas independants entre eux.

LA RESERVE QUI PESE SUR TOUT LE RESTE, ECRITE AVANT LES CHIFFRES

    Le choc est recent. S il tombe le 12 ou le 13, il reste TROIS ou
    QUATRE journees apres, contre une douzaine avant. Avec quatre
    journees :

      - la moyenne d apres est portee par quatre nombres ; un seul
        mauvais jour la retourne ;
      - le p le plus petit atteignable est 1 / C(n, k) ; il est
        imprime, et si le p obtenu vaut ce minimum, ca ne veut pas dire
        "tres significatif", ca veut dire "aucune permutation ne fait
        mieux", ce qui arrive naturellement quand k est minuscule.

    Ce script ne peut donc PAS conclure que la rotation est installee.
    Il peut dire : elle est visible, de telle taille, et voici la
    probabilite de la voir aussi grande par hasard avec si peu de
    journees. C est une hypothese datee a verifier, pas un feu vert.

    Deuxieme reserve : l historique commence fin juillet. Le range de
    debut juillet dont parle l utilisateur n est PAS dans ces donnees.
    On ne peut rien dire de lui ici.

LECTEUR SEUL : lit les CSV de cartes\cycles\, ecrit un .txt.
"""
import argparse
import csv
import io
import os
import random
import sys
import datetime as dt

ENTREE = os.path.join("cartes", "cycles")
SORTIE = os.path.join("cartes", "panel_rotation.txt")
TECH = "US100"
LARGE = "US500"
VALUE = "US30"
LARG = 100

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def charge(dossier):
    jours = {}
    if not os.path.isdir(dossier):
        return jours
    for nom in sorted(os.listdir(dossier)):
        if not nom.startswith("cycles_") or not nom.endswith(".csv"):
            continue
        with io.open(os.path.join(dossier, nom), encoding="utf-8",
                     errors="replace") as f:
            L = [r for r in csv.DictReader(f, delimiter=";")]
        if L:
            jours[nom[7:-4]] = L
    return jours


def pas_median(jours):
    p = []
    for L in jours.values():
        for k in range(1, min(len(L), 300)):
            try:
                t0 = dt.datetime.strptime(L[k - 1]["ts"][:19],
                                          "%Y-%m-%d %H:%M:%S")
                t1 = dt.datetime.strptime(L[k]["ts"][:19],
                                          "%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError, TypeError):
                continue
            d = (t1 - t0).total_seconds()
            if 0 < d < 600:
                p.append(d)
    p.sort()
    return p[len(p) // 2] if p else 10.0


def mediane(v):
    if not v:
        return None
    v = sorted(v)
    return v[len(v) // 2]


def moyenne(v):
    return sum(v) / len(v) if v else None


def serie(L, actif):
    return [flt(r.get("%s_bid" % actif)) for r in L]


def rendement_jour(px):
    """Rendement de la journee en POURCENT, ouverture a cloture.

    En points, US30 ecraserait tout : il vaut sept fois le US500. En
    pourcent les trois deviennent comparables, ce qui est la condition
    pour parler de rotation."""
    deb = fin = None
    for v in px:
        if v is not None and v > 0:
            if deb is None:
                deb = v
            fin = v
    if deb is None or fin is None or deb <= 0:
        return None
    return (fin - deb) / deb * 100.0


def amplitude_max(px, k):
    """Le plus grand mouvement en %% sur une fenetre glissante de k
    cycles dans la journee. C est la mesure de spike."""
    best = 0.0
    n = len(px)
    for i in range(0, n - k):
        a, b = px[i], px[i + k]
        if a is None or b is None or a <= 0:
            continue
        m = abs(b - a) / a * 100.0
        if m > best:
            best = m
    return best


def permutation(vals, k_apres, obs, tirages, graine):
    """Melange les etiquettes avant/apres ENTRE JOURNEES.

    L unite d observation est la journee : les cycles d une meme
    journee ne sont pas independants, donc on ne melange jamais a
    l interieur d une journee. On compte la frequence a laquelle le
    hasard produit un ecart au moins aussi grand EN VALEUR ABSOLUE --
    bilateral, parce qu on n avait pas pre-enregistre le signe."""
    r = random.Random(graine)
    n = len(vals)
    if k_apres < 1 or k_apres >= n:
        return None, None
    au_moins = 0
    for _ in range(tirages):
        idx = list(range(n))
        r.shuffle(idx)
        ap = [vals[i] for i in idx[:k_apres]]
        av = [vals[i] for i in idx[k_apres:]]
        d = moyenne(ap) - moyenne(av)
        if abs(d) >= abs(obs):
            au_moins += 1
    return (au_moins + 1.0) / (tirages + 1.0), au_moins


def combinaisons(n, k):
    if k < 0 or k > n:
        return 0
    r = 1
    for i in range(k):
        r = r * (n - i) // (i + 1)
    return r


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--entree", default=ENTREE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--fenetre", type=float, default=15.0,
                   help="fenetre du spike, en minutes")
    p.add_argument("--multiple", type=float, default=2.5,
                   help="un choc = amplitude > ce multiple de la mediane")
    p.add_argument("--tirages", type=int, default=20000)
    p.add_argument("--graine", type=int, default=17)
    a = p.parse_args()

    jours = charge(a.entree)
    if not jours:
        print("KO : aucun CSV dans %s." % a.entree)
        print("     Lance d abord : python extraire_cycles.py")
        return 1
    cyc = pas_median(jours)
    k = max(1, int(round(a.fenetre * 60.0 / cyc)))
    noms = sorted(jours)

    dis("=" * LARG)
    dis("ROTATION TECH / VALUE -- LES TECHS S ACHETENT-ELLES PLUS ?")
    dis("=" * LARG)
    dis("  %d journees (%s a %s), pas median %.0f s."
        % (len(noms), noms[0], noms[-1], cyc))
    dis("  genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dis()
    dis("  Tout est en POURCENT du prix d ouverture de la journee : en")
    dis("  points l US30 ecraserait tout, il vaut sept fois le US500.")
    dis()
    dis("  ecart tech  = rendement(%s) - rendement(%s)" % (TECH, VALUE))
    dis("  ecart 500   = rendement(%s) - rendement(%s)" % (LARGE, VALUE))
    dis()
    dis("  Positif = la tech a fait mieux que la value ce jour-la, que")
    dis("  le marche monte ou descende. C est une rotation, pas une")
    dis("  tendance.")
    dis()
    dis("  L historique commence le %s : le range de debut juillet n est"
        % noms[0])
    dis("  PAS dans ces donnees et rien ici ne le concerne.")
    dis("=" * LARG)

    # --- par journee : rendements, ecarts, amplitude de spike ---
    table = []
    for j in noms:
        L = jours[j]
        px = dict((x, serie(L, x)) for x in (VALUE, LARGE, TECH))
        r = dict((x, rendement_jour(px[x])) for x in px)
        if any(r[x] is None for x in r):
            continue
        amp = dict((x, amplitude_max(px[x], k)) for x in px)
        table.append({"jour": j, "r": r, "amp": amp,
                      "tech": r[TECH] - r[VALUE],
                      "cinq": r[LARGE] - r[VALUE]})
    if len(table) < 4:
        dis("  Moins de quatre journees exploitables : rien a comparer.")
        return 1

    # --- detection des chocs, dans les donnees ---
    med = {}
    for x in (VALUE, LARGE, TECH):
        med[x] = mediane([t["amp"][x] for t in table]) or 0.0
    for t in table:
        t["choc"] = all(t["amp"][x] >= a.multiple * med[x]
                        for x in (VALUE, LARGE, TECH)) \
            if all(med[x] > 0 for x in med) else False

    dis()
    dis("-" * LARG)
    dis("PAR JOURNEE")
    dis("-" * LARG)
    dis("  %-12s %8s %8s %8s %10s %10s %9s %s"
        % ("jour", VALUE, LARGE, TECH, "ecart tech", "ecart 500",
           "spike max", ""))
    dis("  %-12s %8s %8s %8s %10s %10s %9s %s"
        % ("", "%", "%", "%", "pts de %", "pts de %",
           "%% / %dmin" % int(a.fenetre), "choc"))
    for t in table:
        dis("  %-12s %8.2f %8.2f %8.2f %10.2f %10.2f %9.2f %s"
            % (t["jour"], t["r"][VALUE], t["r"][LARGE], t["r"][TECH],
               t["tech"], t["cinq"],
               max(t["amp"][x] for x in t["amp"]),
               "CHOC" if t["choc"] else ""))
    dis()
    dis("  Un choc = les TROIS actifs depassent %.1f fois leur amplitude"
        % a.multiple)
    dis("  mediane sur %d min dans la MEME journee. Les trois ensemble :"
        % int(a.fenetre))
    dis("  c est ce qui distingue une macro d un spike propre a un actif.")
    dis("  Mediane de reference : %s %.2f %%, %s %.2f %%, %s %.2f %%."
        % (VALUE, med[VALUE], LARGE, med[LARGE], TECH, med[TECH]))

    chocs = [t["jour"] for t in table if t["choc"]]
    dis()
    if not chocs:
        dis("  => AUCUN choc detecte a ce seuil. La question posee")
        dis("     supposait un evenement ; les donnees n en montrent pas")
        dis("     a %.1f x la mediane. Baisser --multiple montrerait des"
            % a.multiple)
        dis("     journees, mais choisir le seuil qui fait apparaitre")
        dis("     l evenement qu on cherche n est plus une detection.")
        dis("     Rien n est compare.")
        ecrire(a.sortie)
        return 0

    dis("  => %d journee(s) de choc : %s" % (len(chocs), ", ".join(chocs)))
    coupe = chocs[0]
    idx = [t["jour"] for t in table].index(coupe)
    dis("     La coupure est posee au PREMIER : %s. Elle vient du" % coupe)
    dis("     detecteur, pas d une date saisie a la main -- il n y a")
    dis("     donc pas de recherche de la meilleure coupure ici, et le p")
    dis("     qui suit n a pas a etre corrige pour ca.")

    # --- avant / apres ---
    for nom, cle in (("ECART TECH (%s - %s)" % (TECH, VALUE), "tech"),
                     ("ECART 500  (%s - %s)" % (LARGE, VALUE), "cinq")):
        av = [t[cle] for t in table[:idx]]
        ap = [t[cle] for t in table[idx:]]
        dis()
        dis("-" * LARG)
        dis(nom)
        dis("-" * LARG)
        if len(av) < 2 or len(ap) < 2:
            dis("  Moins de deux journees d un cote : non comparable.")
            continue
        m_av, m_ap = moyenne(av), moyenne(ap)
        obs = m_ap - m_av
        pos_av = sum(1 for x in av if x > 0)
        pos_ap = sum(1 for x in ap if x > 0)
        dis("  avant %-9s %2d journees, moyenne %+6.2f pts de %%, %d/%d > 0"
            % ("(< %s)" % coupe, len(av), m_av, pos_av, len(av)))
        dis("  a partir de %-3s %2d journees, moyenne %+6.2f pts de %%,"
            " %d/%d > 0"
            % (coupe, len(ap), m_ap, pos_ap, len(ap)))
        dis("  ecart                        %+6.2f pts de %% par journee"
            % obs)
        vals = [t[cle] for t in table]
        pv, _ = permutation(vals, len(ap), obs, a.tirages, a.graine)
        nb = combinaisons(len(vals), len(ap))
        pmin = 1.0 / nb if nb else 1.0
        dis()
        dis("  permutation par journee, %d tirages : p = %.3f"
            % (a.tirages, pv))
        dis("  p le plus petit atteignable avec %d journees dont %d"
            % (len(vals), len(ap)))
        dis("  apres : %.4f (il n existe que %d decoupages possibles)."
            % (pmin, nb))
        if pv is not None and pv <= 2 * pmin:
            dis("  ATTENTION : p est au plancher ou juste au-dessus. Ca ne")
            dis("  veut pas dire tres significatif, ca veut dire qu il n y")
            dis("  a presque pas de decoupages possibles. Avec %d journees"
                % len(ap))
            dis("  apres, ce resultat ne peut pas etre autre chose qu une")
            dis("  hypothese a re-mesurer dans deux semaines.")

    dis()
    dis("=" * LARG)
    dis("CE QUE CA NE DIT PAS")
    dis("=" * LARG)
    dis("  1. Aucun euro. Ces ecarts sont des rendements d indices, pas")
    dis("     le PnL de la stack. Un ecart tech/value favorable ne dit")
    dis("     pas qu un biais long tech aurait gagne : il faudrait le")
    dis("     mesurer sur churn_trades.jsonl.")
    dis("  2. Ouverture a cloture. Une journee qui monte puis rend tout")
    dis("     compte comme plate, alors qu elle est tres differente pour")
    dis("     du scalping. C est volontaire ici -- la question portait")
    dis("     sur une rotation de fond -- mais ca ne se transpose pas")
    dis("     tel quel a une regle intraday.")
    dis("  3. Le lien avec le CPI est une INTERPRETATION. Le detecteur")
    dis("     voit un choc simultane sur les trois actifs ; il ne sait")
    dis("     pas ce qui l a cause. Le flux de news est le seul endroit")
    dis("     ou verifier que la date correspond vraiment a une")
    dis("     publication -- tant que ce n est pas fait, la cause reste")
    dis("     une supposition.")
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
