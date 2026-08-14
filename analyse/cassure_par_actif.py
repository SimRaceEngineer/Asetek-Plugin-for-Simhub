# -*- coding: utf-8 -*-
r"""
cassure_par_actif.py -- ou se casse chaque actif, et si ca se casse

  python cassure_par_actif.py
  python cassure_par_actif.py --actif US100
  python cassure_par_actif.py --tirages 1000

CE QU IL REPOND

    Toute l analyse du dossier repose sur UNE date de cassure, le
    5 aout, choisie a l oeil et appliquee aux trois actifs. Si un actif
    change de regime a une autre date, sa periode "depuis" melange deux
    regimes et la reference commune ne decrit plus personne.

    Ce script cherche, pour CHAQUE actif separement, la date qui
    separe le mieux les signaux en deux moitiés de moyennes
    differentes -- et surtout, il dit si cette date veut dire quelque
    chose.

LE PIEGE, ET LA SEULE FACON HONNETE D EN SORTIR

    Prendre le maximum de trente dates candidates et annoncer "la
    cassure est au 13" est exactement l erreur qu on corrige partout
    ailleurs : c est un maximum d enumeration. Sur des donnees SANS
    aucune rupture, ce maximum vaut deja 2,5 ou 3 -- il faut bien que
    l une des trente dates soit la meilleure.

    Bonferroni ne convient pas ici : les tests sont massivement
    correles (deux dates voisines partagent presque tout leur
    echantillon), et la correction serait absurdement severe.

    On procede donc par PERMUTATION. On rebat les resultats au hasard
    en gardant les dates, on refait la recherche complete du maximum,
    et on recommence --tirages fois. La proportion de tirages dont le
    maximum egale ou depasse celui observe EST la p-valeur, et elle
    tient compte du fait qu on a cherche.

    PERMUTATION PAR SEANCE, ET NON PAR SIGNAL. Les signaux d une meme
    journee ne sont pas independants -- meme regime, meme volatilite,
    souvent les memes mouvements. Rebattre signal par signal detruirait
    cette structure, retrecirait la distribution de reference et
    rendrait n importe quoi "significatif". On permute donc des
    JOURNEES entieres, en bloc.

CE QU IL AFFICHE

    Pour chaque actif : le profil du t par date candidate (une courbe
    en ASCII), la meilleure date, sa p-valeur de permutation, et le t
    de la date IMPOSEE (5 aout) pour comparaison.

    Une vraie rupture donne un pic net et une p-valeur basse. Du bruit
    donne un profil en dents de scie et une p-valeur elevee. Le profil
    est affiche justement pour qu on puisse voir lequel des deux on a,
    au lieu de faire confiance a un seul nombre.

    On ne conclut pas a la place du lecteur : le script imprime "pas
    de rupture detectable" quand p depasse 0,05, et il ne propose
    aucune date de remplacement dans ce cas.

REPRODUCTIBLE : le tirage est initialise a --graine (12345 par
defaut). Deux executions donnent le meme resultat, sinon un chiffre
qui bouge d une fois sur l autre finirait par etre choisi.

Lecteur SEUL : lit un .jsonl, ecrit un .txt. Aucun ordre, aucun
collecteur, aucun etat modifie.
"""
import argparse
import io
import math
import os
import random
import sys
import datetime as dt

import profils_croises as pc

SORTIE = os.path.join("cartes", "panel_cassure.txt")
IMPOSE = "2026-08-05"
MIN_N = 150
TIRAGES = 400
GRAINE = 12345
LARG = 100

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def par_jour(sig):
    """Les signaux groupes par journee, dans l ordre. C est l unite de
    permutation : une journee entiere se deplace d un bloc."""
    jours = {}
    for s in sig:
        if not s["jour"]:
            continue
        jours.setdefault(s["jour"], []).append(s["pnl"])
    return [(j, jours[j]) for j in sorted(jours)]


def balaye(blocs, min_n):
    """Pour chaque coupure possible ENTRE deux journees, l ecart de
    moyenne entre avant et apres, et son t.

    Le t est celui d une difference de deux moyennes :
        t = (m_apres - m_avant) / (sigma * racine(1/n1 + 1/n2))
    avec sigma estime sur l ensemble -- meme convention que le reste du
    dossier, ou sigma est une constante assumee et non re-estimee a
    chaque cellule.

    Rend la liste (date, n_avant, n_apres, m_avant, m_apres, t) pour
    toutes les coupures ou les deux cotes ont au moins min_n signaux.
    """
    n_tot = sum(len(v) for _, v in blocs)
    if n_tot < 2 * min_n:
        return []
    tous = [x for _, v in blocs for x in v]
    moy = sum(tous) / n_tot
    var = sum((x - moy) ** 2 for x in tous) / max(1, n_tot - 1)
    sig = math.sqrt(var) or 1.0

    out = []
    n1 = 0
    s1 = 0.0
    total = sum(tous)
    for i in range(len(blocs) - 1):
        n1 += len(blocs[i][1])
        s1 += sum(blocs[i][1])
        n2 = n_tot - n1
        if n1 < min_n or n2 < min_n:
            continue
        m1 = s1 / n1
        m2 = (total - s1) / n2
        t = (m2 - m1) / (sig * math.sqrt(1.0 / n1 + 1.0 / n2))
        out.append((blocs[i + 1][0], n1, n2, m1, m2, t))
    return out


def maximum(courbe):
    if not courbe:
        return None
    return max(courbe, key=lambda c: abs(c[5]))


def permutation(blocs, min_n, tirages, alea):
    """La distribution du maximum de |t| SOUS L HYPOTHESE QU IL N Y A
    AUCUNE RUPTURE.

    On garde les journees et leurs effectifs, on rebat l ordre des
    journees, et on refait la recherche complete du maximum. Chaque
    tirage rend donc le meilleur t qu on aurait trouve en cherchant
    dans du bruit ayant la meme structure."""
    tailles = [(j, v) for j, v in blocs]
    maxs = []
    for _ in range(tirages):
        alea.shuffle(tailles)
        c = maximum(balaye(tailles, min_n))
        maxs.append(abs(c[5]) if c else 0.0)
    return sorted(maxs)


def courbe_ascii(courbe, larg=64):
    """Le profil du t, date par date. Un pic net contre des dents de
    scie : c est cette forme qui distingue une rupture d un artefact,
    et aucun nombre unique ne la remplace."""
    if not courbe:
        return []
    hi = max(abs(c[5]) for c in courbe) or 1.0
    lignes = []
    for d, n1, n2, m1, m2, t in courbe:
        k = int(round(abs(t) / hi * larg))
        barre = ("+" if t > 0 else "-") * max(1, k)
        lignes.append("  %s  n %5d/%-5d  %+7.2f -> %+7.2f  t %+6.2f  %s"
                      % (d, n1, n2, m1, m2, t, barre))
    return lignes


def un_actif(nom, sig, a, alea):
    dis()
    dis("=" * LARG)
    dis("ACTIF %s" % nom)
    dis("=" * LARG)
    blocs = par_jour(sig)
    n_tot = sum(len(v) for _, v in blocs)
    dis("  %d signaux sur %d seances." % (n_tot, len(blocs)))
    if len(blocs) < 4:
        dis("  Moins de 4 seances : rien a couper.")
        return None

    courbe = balaye(blocs, a.min_n)
    if not courbe:
        dis("  Aucune coupure ne laisse %d signaux de chaque cote."
            % a.min_n)
        dis("  Rien n est mesurable ici -- ce n est pas une absence de")
        dis("  rupture, c est une absence de donnees.")
        return None

    dis("  %d dates candidates (les deux cotes ont >= %d signaux)."
        % (len(courbe), a.min_n))
    dis()
    dis("  date         n avant/apres   moyennes            t")
    for l in courbe_ascii(courbe):
        dis(l)

    best = maximum(courbe)
    dis()
    dis("  MEILLEURE DATE : %s   t = %+.2f" % (best[0], best[5]))
    dis("    avant : %5d signaux, %+7.2f EUR/signal"
        % (best[1], best[3]))
    dis("    apres : %5d signaux, %+7.2f EUR/signal"
        % (best[2], best[4]))
    dis("    ecart : %+.2f EUR/signal" % (best[4] - best[3]))

    # la date imposee, pour comparaison
    impose = [c for c in courbe if c[0] == a.impose]
    dis()
    if impose:
        c = impose[0]
        dis("  DATE IMPOSEE %s : t = %+.2f (%d / %d signaux)"
            % (a.impose, c[5], c[1], c[2]))
        if abs(c[5]) < abs(best[5]) - 0.001:
            dis("    -> une autre date separe mieux cet actif.")
        else:
            dis("    -> c est aussi la meilleure pour cet actif.")
    else:
        dis("  DATE IMPOSEE %s : hors des candidates (un cote a moins"
            " de %d signaux)." % (a.impose, a.min_n))

    # permutation
    dis()
    dis("  Permutation : %d tirages, journees rebattues en bloc."
        % a.tirages)
    nul = permutation([(j, list(v)) for j, v in blocs], a.min_n,
                      a.tirages, alea)
    obs = abs(best[5])
    au_dessus = sum(1 for x in nul if x >= obs - 1e-12)
    p = (au_dessus + 1.0) / (a.tirages + 1.0)
    q = nul[int(0.95 * len(nul))] if nul else 0.0
    dis("    max |t| observe          : %.2f" % obs)
    dis("    max |t| median sous H0   : %.2f" % nul[len(nul) // 2])
    dis("    seuil 95%% sous H0        : %.2f" % q)
    dis("    p-valeur                 : %.3f" % p)
    dis()
    if p <= 0.05:
        dis("  => RUPTURE DETECTABLE au %s (p = %.3f)." % (best[0], p))
        dis("     Le maximum observe depasse ce qu on obtient en")
        dis("     cherchant dans du bruit de meme structure.")
    else:
        dis("  => PAS DE RUPTURE DETECTABLE (p = %.3f)." % p)
        dis("     Le maximum observe est du meme ordre que celui qu on")
        dis("     trouve en cherchant dans du bruit. AUCUNE date de")
        dis("     remplacement n est proposee : il n y en a pas.")
    return (nom, best, p)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--trades", default=pc.TRADES)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--impose", default=IMPOSE)
    p.add_argument("--min-n", type=int, default=MIN_N, dest="min_n")
    p.add_argument("--tirages", type=int, default=TIRAGES)
    p.add_argument("--graine", type=int, default=GRAINE)
    p.add_argument("--actif", default=None)
    p.add_argument("--limite", type=int, default=200000)
    a = p.parse_args()

    brut = pc.charger(a.trades, a.limite)
    if not brut:
        print("KO : %s introuvable ou vide." % a.trades)
        print("     Lance depuis le dossier de la stack.")
        return 1
    sig = pc.signaux(brut, ["M5"])
    if not sig:
        print("KO : aucun signal exploitable (entry_captured_live ?).")
        return 1

    alea = random.Random(a.graine)
    actifs = [a.actif] if a.actif else \
        sorted(set(s["actif"] for s in sig)) + ["TOUS"]

    dis("=" * LARG)
    dis("OU SE CASSE CHAQUE ACTIF -- et si ca se casse")
    dis("=" * LARG)
    dis("  %d enregistrements -> %d signaux (jumeaux 206/207 fusionnes)."
        % (len(brut), len(sig)))
    dis("  genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dis("  graine %d -- deux executions donnent le meme resultat."
        % a.graine)
    dis()
    dis("  On cherche, pour chaque actif, la date qui separe le mieux")
    dis("  ses signaux en deux moitiés de moyennes differentes.")
    dis()
    dis("  Prendre le maximum de N dates et l annoncer serait la meme")
    dis("  erreur que partout ailleurs : sur des donnees SANS rupture,")
    dis("  ce maximum vaut deja 2,5 ou 3. On le calibre donc par")
    dis("  PERMUTATION -- on rebat les JOURNEES en bloc, on refait la")
    dis("  recherche complete, %d fois, et on regarde ou tombe le" % a.tirages)
    dis("  maximum observe dans cette distribution.")
    dis()
    dis("  Journees en bloc et non signaux : deux signaux du meme jour")
    dis("  ne sont pas independants. Les rebattre un par un")
    dis("  retrecirait la reference et rendrait tout significatif.")
    dis("=" * LARG)

    res = []
    for nom in actifs:
        lot = [s for s in sig if nom == "TOUS" or s["actif"] == nom]
        r = un_actif(nom, lot, a, alea)
        if r:
            res.append(r)

    dis()
    dis("=" * LARG)
    dis("CE QUE CA CHANGE")
    dis("=" * LARG)
    detectes = [r for r in res if r[2] <= 0.05]
    if not detectes:
        dis("  Aucun actif ne montre de rupture detectable.")
        dis()
        dis("  La date du %s reste une CONVENTION, pas une mesure."
            % a.impose)
        dis("  Ce n est pas un echec : c est la reponse. Une convention")
        dis("  assumee vaut mieux qu une date choisie a l oeil et")
        dis("  presentee comme un fait.")
    else:
        dis("  %d actif(s) montrent une rupture detectable :"
            % len(detectes))
        for nom, best, pv in detectes:
            dis("    %-6s %s   ecart %+7.2f   p = %.3f"
                % (nom, best[0], best[4] - best[3], pv))
        dates = set(b[0] for _, b, _ in detectes)
        dis()
        if len(dates) > 1 or any(b[0] != a.impose for _, b, _ in detectes):
            dis("  AU MOINS UN ACTIF SE CASSE AILLEURS QUE LE %s."
                % a.impose)
            dis("  Les references par periode du dossier -- et donc les")
            dis("  ecarts de H22 a H26 -- sont calculees sur un decoupage")
            dis("  commun qui ne vaut pas pour cet actif.")
            dis()
            dis("  A FAIRE AVANT les echeances, jamais apres : relire ces")
            dis("  hypotheses avec le decoupage par actif. Les relire")
            dis("  apres avoir vu leur verdict serait choisir le")
            dis("  decoupage qui donne le resultat souhaite.")
    dis()
    dis("  Rappel : une date de rupture est une date de CHANGEMENT DE")
    dis("  MOYENNE des resultats. Elle ne dit pas ce qui a change dans")
    dis("  le marche, et elle n autorise aucun changement de parametre")
    dis("  pendant le gel.")

    d = os.path.dirname(a.sortie)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.sortie, "w", encoding="utf-8").write("\n".join(_ECHO) + "\n")
    print()
    print("ecrit : %s (%d octets)" % (a.sortie, os.path.getsize(a.sortie)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
