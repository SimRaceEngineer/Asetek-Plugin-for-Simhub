# -*- coding: utf-8 -*-
r"""
patch_permutation.py -- la p-value, et la raison pour laquelle elle
pourrait ne pas exister

  python patch_permutation.py

CE QU IL AJOUTE

    1. La COMPOSITION des deux groupes par jour de la semaine.
    2. Une p-value par PERMUTATION PAR JOURNEE, stratifiee par jour
       de la semaine.

POURQUOI LA STRATIFICATION N EST PAS UN RAFFINEMENT

    Les deux seules series qui survivent au filtre d occurrences sont
    hebdomadaires, et tombent toujours le meme jour :

        EIA Crude Oil Stocks Change    mercredi
        Initial Jobless Claims         jeudi

    Les temoins, eux, sont construits sur les journees SANS publication
    HIGH. Il y a une publication HIGH presque tous les mercredis et
    tous les jeudis. Donc les temoins ne sont, en pratique, ni des
    mercredis ni des jeudis.

    La table ne compare alors pas "avec surprise" a "sans surprise".
    Elle compare DES MERCREDIS ET DES JEUDIS A DES LUNDIS, MARDIS ET
    VENDREDIS. Un effet de jour de la semaine -- et il en existe, les
    fins de semaine ne se traitent pas comme les debuts -- sortirait
    exactement sous la forme observee : une difference monotone qui
    grandit avec l horizon.

    Une permutation NON stratifiee melangerait les jours de semaine et
    declarerait cet artefact significatif. Une permutation stratifiee
    ne compare que des mercredis a des mercredis. Si aucun mercredi
    temoin n existe, elle ne peut rien comparer -- et c est une
    REPONSE, pas une panne : elle dit que la mesure telle qu elle est
    construite ne peut pas etre testee.

LA JOURNEE EST L UNITE D OBSERVATION

    Deux fenetres ouvertes le meme jour a deux heures differentes ne
    sont pas deux tirages independants : elles voient le meme marche,
    la meme seance, la meme humeur. Les valeurs sont donc moyennees par
    JOURNEE avant tout calcul, et c est le label de la journee qui est
    permute.

    Consequence a lire : la difference affichee dans le bloc
    permutation n est pas exactement celle des tables du dessus. Les
    tables moyennent par FENETRE, la permutation par JOURNEE. L ecart
    entre les deux mesure a quel point quelques journees portent
    plusieurs fenetres.

CE QUE LA P-VALUE NE DIRA PAS

    Douze tests par symbole -- six horizons, deux grandeurs. Sous
    l hypothese nulle, obtenir une p sous 0,05 arrive environ une fois
    sur deux par symbole, PAR HASARD. Une p isolee a 0,04 dans ce
    tableau ne vaut rien. Ce qui vaudrait quelque chose : une colonne
    entiere qui descend, ou une p tres basse la ou une hypothese
    pre-enregistree l attendait.

    La graine du tirage est FIXE. Une p-value qui change a chaque
    execution n est pas une mesure, c est une loterie qu on relance
    jusqu a ce qu elle plaise.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import io
import os
import shutil
import sys

CIBLE = "reaction_evenements.py"
MARQUE = "def permutation("

# ---------------------------------------------------------------- 1
A1 = '''import math
import os
import sys
'''
B1 = '''import math
import os
import random
import sys
'''

# ---------------------------------------------------------------- 2
A2 = 'def prix_a(serie, cible, tolerance, rend_index=False):\n'
B2 = '''JOURS_SEMAINE = ("lundi", "mardi", "mercredi", "jeudi", "vendredi",
                 "samedi", "dimanche")


def par_jour(paires, cle):
    """La valeur moyenne par JOURNEE.

    La journee est l unite d observation. Deux fenetres ouvertes le
    meme jour a deux heures differentes ne sont pas deux tirages
    independants : elles voient le meme marche, la meme seance. Les
    compter deux fois gonflerait l effectif sans ajouter d information
    -- et c est l effectif qui fabrique les p-values."""
    g = {}
    for t, x in paires:
        v = x.get(cle)
        if v is not None:
            g.setdefault(t.date(), []).append(v)
    return dict((d, sum(v) / len(v)) for d, v in g.items())


def composition(p_ev, p_tm, cle):
    """Combien de JOURNEES dans chaque groupe, et lesquelles.

    Les series hebdomadaires tombent toujours le meme jour ; les
    temoins sont pris sur les journees sans publication, donc jamais ce
    jour-la. La comparaison devient une comparaison de jours de la
    semaine, et ca ne se voit dans aucun total."""
    ev = par_jour(p_ev, cle)
    tm = par_jour(p_tm, cle)
    out = []
    for i, n in enumerate(JOURS_SEMAINE):
        a = sum(1 for d in ev if d.weekday() == i)
        b = sum(1 for d in tm if d.weekday() == i)
        if a or b:
            out.append((n, a, b))
    return out


def permutation(p_ev, p_tm, cle, tirages, graine=20260817):
    """p-value par permutation des labels de JOURNEE, a l interieur
    d un meme jour de la semaine.

    Rend (p, difference, n_ev, n_tm, perdues) ou None si rien n est
    testable. `perdues` compte les journees dont le jour de semaine
    n existe que dans UN des deux groupes : elles ne peuvent etre
    permutees avec rien, donc elles sortent du test. Les compter et les
    afficher est le coeur de l affaire -- si elles sont presque toutes
    perdues, la mesure n est pas testable telle qu elle est
    construite."""
    ev = par_jour(p_ev, cle)
    tm = par_jour(p_tm, cle)
    if not ev or not tm:
        return None
    strates = {}
    for d, v in ev.items():
        strates.setdefault(d.weekday(), [[], []])[0].append(v)
    for d, v in tm.items():
        strates.setdefault(d.weekday(), [[], []])[1].append(v)

    perdues = sum(len(s[0]) + len(s[1]) for s in strates.values()
                  if not s[0] or not s[1])
    utiles = [s for s in strates.values() if s[0] and s[1]]
    if not utiles:
        return (None, None, 0, 0, perdues)
    n_ev = sum(len(s[0]) for s in utiles)
    n_tm = sum(len(s[1]) for s in utiles)
    if n_ev < 3 or n_tm < 3:
        return (None, None, n_ev, n_tm, perdues)

    def stat(strat):
        a = [v for s in strat for v in s[0]]
        b = [v for s in strat for v in s[1]]
        return sum(a) / len(a) - sum(b) / len(b)

    obs = stat(utiles)
    al = random.Random(graine)
    pires = 0
    pool = [(list(s[0]) + list(s[1]), len(s[0])) for s in utiles]
    for _ in range(tirages):
        melange = []
        for vals, k in pool:
            v = list(vals)
            al.shuffle(v)
            melange.append((v[:k], v[k:]))
        if abs(stat(melange)) >= abs(obs):
            pires += 1
    # (1 + pires) / (1 + tirages) : jamais p = 0. Avec 2000 tirages on
    # ne peut pas distinguer mieux que 0,0005, et pretendre le
    # contraire serait inventer de la precision.
    return ((1.0 + pires) / (1.0 + tirages), obs, n_ev, n_tm, perdues)


def prix_a(serie, cible, tolerance, rend_index=False):
'''

# ---------------------------------------------------------------- 3
A3 = '    p.add_argument("--verifie", action="store_true")\n'
B3 = '''    p.add_argument("--tirages", type=int, default=2000,
                   help="permutations par test")
    p.add_argument("--verifie", action="store_true")
'''

# ---------------------------------------------------------------- 4
A4 = '''        r_ev = [reaction(serie, e["t"], MINUTES, JOURS, a.tolerance,
                         jours_b, pourcent) for e in dans]
        r_tm = [reaction(serie, t, MINUTES, JOURS, a.tolerance,
                         jours_b, pourcent) for t in temoins]
        r_ev = [x for x in r_ev if x]
        r_tm = [x for x in r_tm if x]
'''
B4 = '''        # On garde l INSTANT a cote de chaque reaction : la
        # permutation permute des journees, elle a donc besoin de
        # savoir de quelle journee vient chaque valeur.
        p_ev = [(e["t"], reaction(serie, e["t"], MINUTES, JOURS,
                                  a.tolerance, jours_b, pourcent))
                for e in dans]
        p_tm = [(t, reaction(serie, t, MINUTES, JOURS, a.tolerance,
                             jours_b, pourcent)) for t in temoins]
        p_ev = [(t, x) for t, x in p_ev if x]
        p_tm = [(t, x) for t, x in p_tm if x]
        r_ev = [x for _, x in p_ev]
        r_tm = [x for _, x in p_tm]
'''

# ---------------------------------------------------------------- 5
A5 = '''        dis()
        dis("  Le prix dit OU ca va, le delta dit QUI pousse. Un prix")
'''
B5 = '''        dis()
        dis("  COMPOSITION DES DEUX GROUPES -- en JOURNEES")
        dis("  %-12s %12s %12s" % ("", "surprises", "temoin"))
        comp = composition(p_ev, p_tm, cles[0])
        for nom_j, na, nb in comp:
            dis("  %-12s %12d %12d" % (nom_j, na, nb))
        muets = [nom_j for nom_j, na, nb in comp if not na or not nb]
        if muets:
            dis()
            dis("  %s : ce jour de semaine n existe que dans UN des deux"
                % ", ".join(muets))
            dis("  groupes. Aucune comparaison n y est possible -- il n y")
            dis("  a rien a mettre en face. Les series hebdomadaires")
            dis("  tombent toujours le meme jour, et les temoins sont")
            dis("  pris sur les journees SANS publication : ce sont donc,")
            dis("  par construction, des jours de semaine differents.")

        dis()
        dis("  PERMUTATION PAR JOURNEE, stratifiee par jour de semaine")
        res = []
        for k in cles:
            for suff, dk in (("", k), (" delta", "d_" + k)):
                r = permutation(p_ev, p_tm, dk, a.tirages)
                if r is not None:
                    res.append((k + suff, r))
        testable = [x for x in res if x[1][0] is not None]
        if not testable:
            # Ne pas repeter douze fois la meme phrase : quand AUCUN
            # horizon n est testable, la cause est unique et tient en
            # un paragraphe. Douze lignes identiques donneraient
            # l impression de douze problemes.
            perdues = max([r[4] for _, r in res] or [0])
            dis()
            dis("  AUCUN horizon n est testable. Les %d journees des deux"
                % perdues)
            dis("  groupes tombent sur des jours de semaine qui n existent")
            dis("  que d un seul cote : il n y a litteralement rien a")
            dis("  mettre en face pour permuter.")
            dis()
            dis("  Ce n est pas une panne, c est le resultat. Les tables")
            dis("  ci-dessus comparent des journees d un jour de semaine a")
            dis("  des journees d un autre. Leur difference contient donc")
            dis("  l effet de jour de semaine ET l effet macro, sans")
            dis("  aucun moyen de les separer sur ces donnees.")
            dis()
            dis("  Deux sorties possibles, et une seule est honnete :")
            dis("  ETENDRE LE CALENDRIER vers le passe pour recuperer des")
            dis("  evenements mensuels -- CPI, NFP, Fed -- qui ne tombent")
            dis("  pas toujours le meme jour. Baisser le seuil")
            dis("  d occurrences ne ferait que normaliser des surprises")
            dis("  sur deux points.")
        else:
            dis("  %-12s %8s %8s %12s %10s"
                % ("horizon", "n_ev", "n_tm", "difference", "p"))
            for lab, (pv, obs, n1, n2, perdues) in res:
                if pv is None:
                    dis("  %-12s %8d %8d  non testable" % (lab, n1, n2))
                else:
                    dis("  %-12s %8d %8d %12.4f %10.4f"
                        % (lab, n1, n2, obs, pv))
            dis()
            dis("  Douze tests ici -- six horizons, deux grandeurs. Sous")
            dis("  l hypothese nulle, une p sous 0,05 sort environ une")
            dis("  fois sur deux PAR HASARD dans un tableau de cette")
            dis("  taille. Une p isolee a 0,04 ne vaut rien ; une colonne")
            dis("  entiere qui descend, ou une p basse la ou une")
            dis("  hypothese pre-enregistree l attendait, oui.")
            dis()
            dis("  n_ev et n_tm ne comptent que les journees REELLEMENT")
            dis("  comparables. Ils sont plus petits que les effectifs")
            dis("  des tables du dessus, et ce sont eux qui sont vrais.")
            dis()
            dis("  La difference ci-dessus est calculee par JOURNEE, les")
            dis("  tables du dessus par FENETRE. L ecart entre les deux")
            dis("  mesure a quel point quelques journees portent")
            dis("  plusieurs fenetres.")

        dis()
        dis("  Le prix dit OU ca va, le delta dit QUI pousse. Un prix")
'''

REMPLACEMENTS = [
    ("import random", A1, B1),
    ("fonctions par_jour(), composition(), permutation()", A2, B2),
    ("option --tirages", A3, B3),
    ("instants gardes a cote des reactions", A4, B4),
    ("bloc composition + permutation", A5, B5),
]


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        return 1
    src = io.open(CIBLE, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique : `%s` est present dans %s." % (MARQUE, CIBLE))
        print("Rien n a ete touche.")
        return 0

    if "def ecarte_doublons(" not in src:
        print("KO : patch_doublons.py n a pas ete applique.")
        print("     Celui-ci s ancre dessus. Lancer d abord :")
        print("       python patch_doublons.py")
        return 1

    manque = []
    for nom, a, _ in REMPLACEMENTS:
        n = src.count(a)
        if n != 1:
            manque.append((nom, n))
    if manque:
        print("KO : ancres introuvables ou ambigues, rien n a ete ecrit.")
        for nom, n in manque:
            print("  %-46s %d occurrence(s), attendu 1" % (nom, n))
        return 1

    out = src
    for nom, a, b in REMPLACEMENTS:
        out = out.replace(a, b, 1)

    try:
        compile(out, CIBLE, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (ligne %s : %s)."
              % (e.lineno, e.msg))
        print("Rien n a ete ecrit. L original est intact.")
        return 1

    sauv = CIBLE + ".avant_permutation"
    if not os.path.isfile(sauv):
        shutil.copy2(CIBLE, sauv)
    io.open(CIBLE, "w", encoding="utf-8", newline="").write(out)

    print("%s : %d lignes -> %d lignes, %d remplacements."
          % (CIBLE, len(src.splitlines()), len(out.splitlines()),
             len(REMPLACEMENTS)))
    print("sauvegarde : %s" % sauv)
    print()
    print("Deux blocs nouveaux par symbole : la composition des groupes")
    print("en journees, puis les p-values. Si la composition montre des")
    print("jours de semaine presents d un seul cote, les p correspondantes")
    print("sortiront `non testable` -- c est une reponse, pas une panne.")
    print()
    print("Relancer : python reaction_evenements.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
