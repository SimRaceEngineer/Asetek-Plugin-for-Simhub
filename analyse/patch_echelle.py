# -*- coding: utf-8 -*-
r"""
patch_echelle.py -- la meme mesure a l echelle horaire, pour savoir si
le silence de YM est reel ou un effet d agregation

  python patch_echelle.py
  puis : python flux_contre_prix.py --bloc 60

LA QUESTION

    Mesure du 17/08, sur des agregats JOURNALIERS :

        MES-continu   n=133   rho(delta, rendement) = 0.569   p = 0.0005
        YM-continu    n=112   rho(delta, rendement) = 0.015   p = 0.8726

    Le delta de YM ne dit rien du prix de YM. Mais une seance fait
    1250 barres : un signal d une minute peut se laver entierement sur
    une somme aussi longue. Le silence peut donc etre reel, ou n etre
    qu un effet d agregation.

    La difference n est pas academique. H30 est construite sur une
    fenetre de SOIXANTE MINUTES du delta de YM. Si YM est muet a
    l heure aussi, H30 repose sur du bruit et tombe sans attendre le
    4 septembre. Si YM parle a l heure, l asymetrie journaliere est un
    artefact d agregation et H30 tient jusqu a sa date.

    Cette mesure doit donc etre faite AVANT le 04/09, faute de quoi on
    verifiera une hypothese sans savoir si son support existe.

CE QUE FAIT LE CORRECTIF

    `--bloc N` remplace la seance par des blocs de N minutes, decoupes
    sur l horloge (0-59, 60-119, ...) et non sur les barres presentes :
    un bloc se definit en TEMPS, comme toutes les fenetres depuis ce
    matin. `--bloc 0` garde le comportement actuel, la seance.

    Un bloc est retenu s il porte au moins la moitie du nombre median
    de barres des blocs -- seuil mesure, pas invente -- et s il ne
    contient qu un seul contrat.

LA PERMUTATION RESTE PAR JOURNEE

    Onze blocs d une meme seance ne sont pas onze observations
    independantes : ils voient le meme marche, la meme humeur, la meme
    nouvelle du matin. Permuter les blocs entre eux ferait croire a un
    effectif de 1400 quand il y en a 130.

    La p-value est donc obtenue en permutant les JOURNEES : la suite
    des deltas d une journee est appariee a la suite des rendements
    d une autre. La journee reste l unite d observation, comme depuis
    ce matin.

    C est ce qui empeche cette mesure de fabriquer de la significativite
    a partir de la seule finesse du decoupage.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import io
import os
import shutil
import sys

CIBLE = "flux_contre_prix.py"
MARQUE = "--bloc"

A1 = '''def seances(serie):
'''
B1 = '''def blocs(serie, minutes):
    """La seance decoupee en blocs de `minutes`, sur l horloge.

    Le decoupage est fait en TEMPS -- 0-59, 60-119 -- et non sur les
    barres presentes : un bloc defini en nombre de barres s etirerait
    silencieusement sur les heures creuses, exactement la faute du
    17/08 au matin ou une "fenetre de 15 minutes" couvrait deux heures.

    Rend {(date, index_de_bloc): (rendement %, delta, volume)}, et le
    dictionnaire des blocs par journee pour la permutation."""
    par = {}
    for t, c, d, v, k in serie:
        cle = (t.date(), (t.hour * 60 + t.minute) // minutes)
        a = par.setdefault(cle, [c, c, 0.0, 0.0, 0, set()])
        a[1] = c
        a[2] += d
        a[3] += v
        a[4] += 1
        if k:
            a[5].add(k)
    cpt = sorted(x[4] for x in par.values())
    med = cpt[len(cpt) // 2] if cpt else 0
    seuil = max(1, med // 2)
    out = {}
    for cle, a in par.items():
        if a[4] < seuil or len(a[5]) > 1 or a[0] <= 0:
            continue
        out[cle] = ((a[1] - a[0]) / a[0] * 100.0, a[2], a[3])
    return out, med, seuil


def p_permutation_jour(cles, va, vb, tirages, graine=20260817):
    """p bilaterale en permutant les JOURNEES, pas les blocs.

    Onze blocs d une meme seance ne sont pas onze observations
    independantes. Permuter les blocs entre eux ferait croire a un
    effectif de 1400 la ou il y en a 130 : la significativite
    naitrait du decoupage et de rien d autre.

    On permute donc l appariement JOURNEE contre JOURNEE, en gardant
    l ordre des blocs a l interieur de chaque journee."""
    obs = spearman(va, vb)
    if obs is None:
        return None, None
    jours = {}
    for i, (j, b) in enumerate(cles):
        jours.setdefault(j, []).append(i)
    js = sorted(jours)
    if len(js) < 10:
        return obs, None
    al = random.Random(graine)
    pires = 0
    ordre = list(js)
    for _ in range(tirages):
        al.shuffle(ordre)
        mb = [0.0] * len(vb)
        for src, dst in zip(js, ordre):
            a, b = jours[src], jours[dst]
            for k in range(min(len(a), len(b))):
                mb[a[k]] = vb[b[k]]
        c = spearman(va, mb)
        if c is not None and abs(c) >= abs(obs):
            pires += 1
    return obs, (1.0 + pires) / (1.0 + tirages)


def seances(serie):
'''

A2 = '''    p.add_argument("--tirages", type=int, default=2000)
'''
B2 = '''    p.add_argument("--tirages", type=int, default=2000)
    p.add_argument("--bloc", type=int, default=0,
                   help="taille des blocs en minutes ; 0 = la seance")
'''

A3 = '''    for sym in sorted(barres):
        s, med, seuil = seances(barres[sym])
        if len(s) < 30:
'''
B3 = '''    for sym in sorted(barres):
        if a.bloc > 0:
            s, med, seuil = blocs(barres[sym], a.bloc)
        else:
            s, med, seuil = seances(barres[sym])
        if len(s) < 30:
'''

A4 = '''        rho, pv = p_permutation(d, r, a.tirages)
        # Un flux est dit INFORMATIF s il explique le prix de son
'''
B4 = '''        if a.bloc > 0:
            rho, pv = p_permutation_jour(js, d, r, a.tirages)
        else:
            rho, pv = p_permutation(d, r, a.tirages)
        if pv is None:
            pv = 1.0
        # Un flux est dit INFORMATIF s il explique le prix de son
'''

A5 = '''            rp, pp = p_permutation(ra, rb, a.tirages)
            rd, pd = p_permutation(da, db, a.tirages)
'''
B5 = '''            if a.bloc > 0:
                rp, pp = p_permutation_jour(com, ra, rb, a.tirages)
                rd, pd = p_permutation_jour(com, da, db, a.tirages)
            else:
                rp, pp = p_permutation(ra, rb, a.tirages)
                rd, pd = p_permutation(da, db, a.tirages)
            pp = 1.0 if pp is None else pp
            pd = 1.0 if pd is None else pd
'''

A6 = '''    dis("  Correlations de RANG (Spearman) : une seule seance extreme")
'''
B6 = '''    if a.bloc > 0:
        dis()
        dis("  ECHELLE : blocs de %d minutes, decoupes sur l horloge."
            % a.bloc)
        dis("  La p-value est obtenue en permutant les JOURNEES et non")
        dis("  les blocs : onze blocs d une meme seance ne sont pas onze")
        dis("  observations independantes, et permuter les blocs ferait")
        dis("  naitre la significativite du seul decoupage.")
        dis()
    dis("  Correlations de RANG (Spearman) : une seule seance extreme")
'''

REMPLACEMENTS = [
    ("fonctions blocs() et p_permutation_jour()", A1, B1),
    ("option --bloc", A2, B2),
    ("decoupage en blocs ou en seances", A3, B3),
    ("permutation par journee en section 1", A4, B4),
    ("permutation par journee en section 2", A5, B5),
    ("annonce de l echelle", A6, B6),
]


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        return 1
    src = io.open(CIBLE, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique. Rien n a ete touche.")
        return 0

    if "informatif" not in src:
        print("KO : patch_precondition.py n a pas ete applique.")
        print("     Lancer d abord : python patch_precondition.py")
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

    sauv = CIBLE + ".avant_echelle"
    if not os.path.isfile(sauv):
        shutil.copy2(CIBLE, sauv)
    io.open(CIBLE, "w", encoding="utf-8", newline="").write(out)

    print("%s : %d lignes -> %d lignes, %d remplacements."
          % (CIBLE, len(src.splitlines()), len(out.splitlines()),
             len(REMPLACEMENTS)))
    print("sauvegarde : %s" % sauv)
    print()
    print("A LANCER DANS CET ORDRE, ET A COMPARER :")
    print()
    print("  python flux_contre_prix.py              (la seance)")
    print("  python flux_contre_prix.py --bloc 60    (l heure)")
    print()
    print("CE QUE CHAQUE RESULTAT VOUDRAIT DIRE POUR H30 :")
    print()
    print("  YM muet a l heure aussi   -> H30 repose sur du bruit et")
    print("                               tombe sans attendre le 04/09.")
    print("  YM informatif a l heure   -> le silence journalier est un")
    print("                               effet d agregation, H30 tient")
    print("                               jusqu a sa date.")
    print()
    print("Noter le resultat dans HYPOTHESES.md dans les deux cas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
