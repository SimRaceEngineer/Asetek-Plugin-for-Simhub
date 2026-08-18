# -*- coding: utf-8 -*-
r"""
patch_bornes.py -- les egalites font deborder la queue basse, et les
                   seances mortes ne sont pas des seances

  python patch_bornes.py --essai
  python patch_bornes.py
  puis : python bougies_reperes.py --centile 99.5

DEUX DEFAUTS, TOUS DEUX LISIBLES DANS LA SORTIE DU 18/08

    MES-continu   37 754 reperes   283,86 par seance   (~22 % des minutes)
    YM-continu    79 647 reperes   711,13 par seance   (~57 % des minutes)

    Attendu au centile 99,5 sur deux queues : ~6 %.

1. LES EGALITES DEBORDENT LA QUEUE BASSE

    Ligne extreme de la sortie :

        2026-02-05 00:50   VITESSE 0.5  TAILLE 1.0  AMPLEUR 0.0
                           PRESSION 0.5  SPREAD 0.2  RENDU 0.0

    Sur une seance quasi morte, la mediane de `high - low` vaut ZERO et
    celle de `trades` vaut 1 ou 2. Le centile 0,5 tombe donc sur zero, et
    la condition `valeur <= borne` attrape TOUTE LA MASSE LIEE au lieu de
    0,5 %.

    Un centile suppose une distribution continue. Sur des entiers petits
    -- un nombre de transactions, une amplitude en tics -- les egalites
    sont la regle, pas l exception.

    LE CORRECTIF : apres avoir calcule une borne, on COMPTE ce qu elle
    designerait. Si elle depasse trois fois sa part nominale, la
    distribution est degeneree de ce cote-la ce jour-la : la borne est
    desactivee, et le nombre de desactivations est affiche.

    On ne devine pas si la distribution est continue : on mesure ce que
    le seuil attrape.

2. UNE SEANCE SANS ACTIVITE N EST PAS UNE SEANCE

    Les extremes de YM sont TOUS dates du 2026-03-13 -- sa toute
    premiere seance. Ceux de MES, du 05/02, quand `MESM26` ne cotait
    presque pas.

    Le filtre existant exige la moitie du nombre median de BARRES. Une
    seance de nuit thin le passe : elle a ses barres, elles sont vides.

    LE CORRECTIF : meme regle, appliquee aux TRANSACTIONS. Une seance est
    retenue si sa mediane de `trades` atteint la moitie de la mediane des
    medianes. Meme forme que la regle des barres -- on ne la reinvente
    pas, on l applique a la bonne grandeur.

    C est la lecon du 17/08 : "une plage de dates n est pas une
    couverture, c est une enveloppe". Un contrat n est liquide que sur
    son trimestre, et compter ses barres ne dit pas s il s y passe
    quelque chose.

CE QUE CA VA CHANGER

    Les seances ecartees et les bornes desactivees sont AFFICHEES. Si le
    nombre de reperes retombe vers 6 % des minutes, le defaut etait bien
    la. S il reste a 50 %, c est autre chose et il faudra le chercher.

    La table par heure redeviendra lisible : dans la sortie fautive, YM
    donnait 6,8 % a 03:00 UTC et 1,1 % a 14:00 -- l inverse exact du
    marche. L outil mesurait la minceur.

3. ET UN `%%` QUI S AFFICHE

    `print("  Consequence : ~12 %% des minutes")` sans formatage affiche
    litteralement `%%`. Corrige aussi.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, compile
avant de remplacer.
"""
import argparse
import io
import os
import shutil
import sys

CIBLE = "bougies_reperes.py"
MARQUE = "part_max"

A1 = '''    haut, bas = {}, {}
    for d in DIMS:
        v = [b[d] for b in jour]
        haut[d] = centile(v, c)
        bas[d] = centile(v, 100.0 - c)
        # Si les deux bornes se confondent, la dimension est constante
        # sur cette seance : on ne signale rien plutot que tout.
        if haut[d] is not None and bas[d] is not None and haut[d] <= bas[d]:
            haut[d] = bas[d] = None
    return haut, bas
'''
B1 = '''    haut, bas = {}, {}
    n = len(jour)
    # Une borne ne doit pas designer plus de TROIS FOIS sa part
    # nominale. Au centile 99,5 la part nominale est 0,5 %, donc on
    # tolere 1,5 %.
    part_max = 3.0 * (100.0 - c) / 100.0
    coupees = 0
    for d in DIMS:
        v = [b[d] for b in jour]
        hi = centile(v, c)
        lo = centile(v, 100.0 - c)
        if hi is None or lo is None or hi <= lo:
            # Dimension constante sur cette seance : on ne signale rien
            # plutot que tout.
            haut[d] = bas[d] = None
            continue
        # LES EGALITES. Un centile suppose une distribution continue.
        # Sur des entiers petits -- un nombre de transactions, une
        # amplitude en tics -- les egalites sont la regle : `<= lo`
        # attrape toute la masse liee, pas 0,5 %. On ne devine pas si
        # la distribution est continue, on COMPTE ce que le seuil
        # designe.
        nh = len([x for x in v if x >= hi])
        nl = len([x for x in v if x <= lo])
        haut[d] = hi if nh <= part_max * n else None
        bas[d] = lo if nl <= part_max * n else None
        if haut[d] is None:
            coupees += 1
        if bas[d] is None:
            coupees += 1
    return haut, bas, coupees
'''

A2 = '''            haut, bas = bornes(j, a.centile)
'''
B2 = '''            haut, bas, _co = bornes(j, a.centile)
            coupees += _co
'''

A3 = '''        cpt = sorted(len(v) for v in jours.values())
        seuil_j = max(30, (cpt[len(cpt) // 2] if cpt else 0) // 2)
        reperes, nseances, seuils = [], 0, dict((d, []) for d in DIMS)
        for jour in sorted(jours):
            j = jours[jour]
            if len(j) < seuil_j:
                continue
            nseances += 1
'''
B3 = '''        cpt = sorted(len(v) for v in jours.values())
        seuil_j = max(30, (cpt[len(cpt) // 2] if cpt else 0) // 2)
        # UNE SEANCE SANS ACTIVITE N EST PAS UNE SEANCE. Le filtre par
        # nombre de barres laisse passer les seances thin : elles ont
        # leurs barres, elles sont vides. Meme regle -- la moitie de la
        # mediane -- appliquee aux TRANSACTIONS.
        mtr = [med([b["n"] for b in v]) or 0.0 for v in jours.values()]
        seuil_tr = (med(mtr) or 0.0) / 2.0
        reperes, nseances, seuils = [], 0, dict((d, []) for d in DIMS)
        coupees, mortes = 0, []
        for jour in sorted(jours):
            j = jours[jour]
            if len(j) < seuil_j:
                continue
            if (med([b["n"] for b in j]) or 0.0) < seuil_tr:
                mortes.append(jour)
                continue
            nseances += 1
'''

A4 = '''        print("  %-16s seuils medians : %s" % ("", "  ".join(
            "%s %.1f" % (d, med(seuils[d]) or 0.0) for d in DIMS)))
'''
B4 = '''        print("  %-16s seuils medians : %s" % ("", "  ".join(
            "%s %.1f" % (d, med(seuils[d]) or 0.0) for d in DIMS)))
        print("  %-16s %d seance(s) ecartee(s) faute d activite reelle "
              "(mediane de trades < %.1f)" % ("", len(mortes), seuil_tr))
        if mortes:
            print("  %-16s de %s a %s" % ("", min(mortes), max(mortes)))
        print("  %-16s %d borne(s) desactivee(s) : la queue debordait "
              "sa part nominale" % ("", coupees))
'''

A5 = '''    print("  Consequence : ~12 %% des minutes au lieu de ~6. Pour du")
'''
B5 = '''    print("  Consequence : ~12 % des minutes au lieu de ~6. Pour du")
'''

REMPLACEMENTS = [
    ("bornes() : les egalites comptees", A1, B1),
    ("appel de bornes() a trois valeurs", A2, B2),
    ("filtre des seances sans activite", A3, B3),
    ("affichage des ecarts et des bornes coupees", A4, B4),
    ("le %% litteral", A5, B5),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable." % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique. Rien n a ete touche.")
        return 0
    if "def bornes(" not in src:
        print("KO : patch_queues.py n a pas ete applique.")
        print("     Lancer d abord : python patch_queues.py")
        return 1

    manque = []
    for nom, av, _ in REMPLACEMENTS:
        n = src.count(av)
        if n != 1:
            manque.append((nom, n))
    if manque:
        print("KO : ancres introuvables ou ambigues, rien n a ete ecrit.")
        for nom, n in manque:
            print("  %-44s %d occurrence(s), attendu 1" % (nom, n))
        return 1
    print("  les %d ancres sont uniques." % len(REMPLACEMENTS))

    out = src
    for nom, av, ap in REMPLACEMENTS:
        out = out.replace(av, ap, 1)

    try:
        compile(out, a.fichier, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (ligne %s : %s)."
              % (e.lineno, e.msg))
        print("Rien n a ete ecrit. L original est intact.")
        return 1

    print()
    print("Apres patch :")
    print("  - une borne qui designe plus de 3 fois sa part nominale est")
    print("    desactivee : les egalites ne debordent plus la queue basse")
    print("  - les seances sans activite reelle sont ecartees, meme regle")
    print("    que pour les barres mais appliquee aux transactions")
    print("  - les deux comptes sont AFFICHES")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauv = a.fichier + ".avant_bornes"
    if not os.path.isfile(sauv):
        shutil.copy2(a.fichier, sauv)
    io.open(a.fichier, "w", encoding="utf-8", newline="").write(out)

    print()
    print("sauvegarde : %s" % sauv)
    print("%s : %d -> %d lignes."
          % (a.fichier, len(src.splitlines()), len(out.splitlines())))
    print()
    print("A VERIFIER SUR LA PROCHAINE SORTIE :")
    print("  1. le nombre de reperes doit retomber vers ~6 % des minutes,")
    print("     soit ~75 par seance et non 284 ou 711 ;")
    print("  2. la table par heure de YM doit remonter sur 13:00-19:00")
    print("     UTC. Dans la sortie fautive elle donnait 6,8 % a 03:00 et")
    print("     1,1 % a 14:00 -- l inverse exact du marche.")
    print()
    print("Si ces deux nombres ne bougent pas, le defaut est ailleurs et")
    print("il ne faut pas chercher a l habiller.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
