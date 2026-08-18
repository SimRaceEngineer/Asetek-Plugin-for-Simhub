# -*- coding: utf-8 -*-
r"""
patch_queues.py -- les DEUX queues de chaque dimension, et l horloge
                   rendue visible

  python patch_queues.py --essai
  python patch_queues.py
  puis : python bougies_reperes.py --centile 99.5

DEUX FAUTES TROUVEES PAR LA PREMIERE SORTIE REELLE

1. JE NE REGARDAIS QU UNE QUEUE SUR DEUX

    `bougies_reperes.py` ne signale une minute que si elle DEPASSE le
    centile 99. Or les phenomenes qui nous interessent sont, pour
    moitie, en BAS de la distribution :

        ABSORPTION      RENDU bas   -- beaucoup de flux, peu d amplitude
        petits ordres   TAILLE bas  -- "beaucoup de petits ordres presses"
        compression     AMPLEUR bas -- le prix ne bouge plus du tout

    La sortie du 18/08 le montre en creux : les vingt-cinq minutes les
    plus marquees de MES ont presque toutes un `RENDU` entre 0,1 et
    0,5. Ce sont des minutes ABSORBEES, et aucune n est signalee pour
    ca -- elles passent par VITESSE, AMPLEUR et PRESSION. Le phenomene
    etait dans mes chiffres et mon detecteur ne savait pas le nommer.

    C est mot pour mot la faute de `bruit_par_actif` v1, consignee le
    17/08 : "ne cherchait qu un franchissement de 1 VERS LE HAUT. Les
    trois actifs descendent : rien trouve." Troisieme fois.

2. L HORLOGE PASSAIT POUR UN EVENEMENT

    Treize des vingt-cinq minutes les plus marquees de YM tombent a
    13:30 UTC EXACTEMENT -- l ouverture du cash NYSE. Ce n est pas un
    evenement de marche, c est une horloge, et c est le piege deja
    consigne au paragraphe 2 du protocole a propos de 14:30 et de
    l initial balance.

    Une hypothese pre-enregistree sur les bougies reperes, sans ce
    controle, mesurerait "le marche ouvre a 15h30 Paris" et sortirait
    un p magnifique.

CE QUE LE PATCH FAIT

    - chaque dimension teste ses DEUX queues : centile c et centile
      100-c. Le libelle porte le sens : `VITE+` rapide, `TAIL-` petits
      ordres, `REND-` absorbe ;
    - une table REPERES PAR HEURE, par symbole, qui rend l effet
      d horloge visible AVANT qu on construise quoi que ce soit
      dessus ;
    - la co-occurrence continue de croiser les six dimensions sans
      leur signe : la question "combien de phenomenes" ne change pas.

    Deux queues doublent le nombre de reperes -- de ~6 % a ~12 % des
    minutes. Le patch le dit dans la sortie et suggere `--centile 99.5`.

IL NE CHANGE NI LES DIMENSIONS NI LEUR NORMALISATION. Les six restent
rapportees a la mediane de leur propre seance et de leur propre actif.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, compile
avant de remplacer.
"""
import argparse
import io
import os
import shutil
import sys

CIBLE = "bougies_reperes.py"
# Marqueur sur du CODE, jamais sur de la prose : le mot "queue"
# apparaitrait dans un commentaire des la premiere relecture.
MARQUE = "def bornes("

A1 = '''            lim = {}
            for d in DIMS:
                lim[d] = centile([b[d] for b in j], a.centile)
                if lim[d]:
                    seuils[d].append(lim[d])
            for b in j:
                q = [d for d in DIMS if lim[d] and b[d] >= lim[d]]
                if q:
                    b["quoi"] = q
                    b["sym"] = sym
                    reperes.append(b)
'''
B1 = '''            haut, bas = bornes(j, a.centile)
            for d in DIMS:
                if haut[d]:
                    seuils[d].append(haut[d])
            for b in j:
                q = []
                for d in DIMS:
                    if haut[d] is not None and b[d] >= haut[d]:
                        q.append(d + "+")
                    elif bas[d] is not None and b[d] <= bas[d]:
                        q.append(d + "-")
                if q:
                    b["quoi"] = q
                    b["dims"] = set(x[:-1] for x in q)
                    b["sym"] = sym
                    reperes.append(b)
'''

A2 = '''def main():
'''
B2 = '''def bornes(jour, c):
    """Les deux bornes de chaque dimension : centile c et centile 100-c.

    Une queue unique n est pas plus simple, elle est aveugle d un cote.
    L absorption vit en BAS du RENDU et les petits ordres presses en
    BAS de la TAILLE ; ne regarder que le haut, c est chercher un
    franchissement vers le haut sur des series qui descendent."""
    haut, bas = {}, {}
    for d in DIMS:
        v = [b[d] for b in jour]
        haut[d] = centile(v, c)
        bas[d] = centile(v, 100.0 - c)
        # Si les deux bornes se confondent, la dimension est constante
        # sur cette seance : on ne signale rien plutot que tout.
        if haut[d] is not None and bas[d] is not None and haut[d] <= bas[d]:
            haut[d] = bas[d] = None
    return haut, bas


def par_heure(reperes):
    """Combien de reperes par heure UTC. Rend la liste triee."""
    h = {}
    for b in reperes:
        h[b["t"].hour] = h.get(b["t"].hour, 0) + 1
    return sorted(h.items())


def main():
'''

A3 = '''            a1 = [b for b in r if d1 in b["quoi"]]
            cells = []
            for d2 in DIMS:
                if not a1:
                    cells.append("%8s" % "-")
                elif d1 == d2:
                    cells.append("%7d%%" % 100)
                else:
                    n = len([b for b in a1 if d2 in b["quoi"]])
'''
B3 = '''            a1 = [b for b in r if d1 in b["dims"]]
            cells = []
            for d2 in DIMS:
                if not a1:
                    cells.append("%8s" % "-")
                elif d1 == d2:
                    cells.append("%7d%%" % 100)
                else:
                    n = len([b for b in a1 if d2 in b["dims"]])
'''

A4 = '''    # --- le listing -------------------------------------------------
'''
B4 = '''    # --- l horloge, avant tout le reste -----------------------------
    print("=" * 78)
    print("REPERES PAR HEURE -- l horloge avant l evenement")
    print("=" * 78)
    print("  Une heure qui concentre les reperes n est pas un evenement,")
    print("  c est une HORLOGE. 13:30 UTC est l ouverture du cash NYSE,")
    print("  12:30 celle des grandes publications americaines. Le")
    print("  paragraphe 2 du protocole porte deja ce piege sur 14:30 et")
    print("  l initial balance du moteur.")
    print()
    print("  Toute mesure batie sur ces reperes devra apparier ses")
    print("  temoins A LA MEME MINUTE DE SEANCE, ou retirer ces heures")
    print("  -- et le dire.")
    print()
    for sym in sorted(tout):
        h = par_heure(tout[sym])
        if not h:
            continue
        tot = sum(n for _, n in h)
        print("  %s   %d reperes" % (sym, tot))
        for heure, n in h:
            part = 100.0 * n / tot
            print("    %02d:00 UTC  %5d  %5.1f %%  %s"
                  % (heure, n, part, "#" * int(round(part))))
        print()

    # --- le listing -------------------------------------------------
'''

A5 = '''                     b["RENDU"], ",".join(x[:4] for x in b["quoi"])))
'''
B5 = '''                     b["RENDU"],
                     ",".join(x[:4] + x[-1] for x in b["quoi"])))
'''

A6 = '''    print("  AUCUNE p-value, aucun temoin : cet outil DECRIT. Il ne")
'''
B6 = '''    print("  DEUX QUEUES par dimension : `VITE+` rapide, `TAIL-` petits")
    print("  ordres, `REND-` absorbe. Une queue unique serait aveugle du")
    print("  cote ou vivent l absorption et les petits ordres presses.")
    print("  Consequence : ~12 %% des minutes au lieu de ~6. Pour du")
    print("  vraiment rare, --centile 99.5 ou plus.")
    print()
    print("  AUCUNE p-value, aucun temoin : cet outil DECRIT. Il ne")
'''

REMPLACEMENTS = [
    ("detection sur les deux queues", A1, B1),
    ("fonctions bornes() et par_heure()", A2, B2),
    ("co-occurrence sur les dimensions non signees", A3, B3),
    ("table des reperes par heure", A4, B4),
    ("libelles portant le sens", A5, B5),
    ("annonce des deux queues", A6, B6),
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
    print("  - chaque dimension teste ses DEUX queues, le libelle porte")
    print("    le sens : VITE+ rapide, TAIL- petits ordres, REND- absorbe")
    print("  - une table REPERES PAR HEURE, qui montre l effet d horloge")
    print("    avant qu on construise quoi que ce soit dessus")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauv = a.fichier + ".avant_queues"
    if not os.path.isfile(sauv):
        shutil.copy2(a.fichier, sauv)
    io.open(a.fichier, "w", encoding="utf-8", newline="").write(out)

    print()
    print("sauvegarde : %s" % sauv)
    print("%s : %d -> %d lignes."
          % (a.fichier, len(src.splitlines()), len(out.splitlines())))
    print()
    print("A REGARDER EN PREMIER DANS LA PROCHAINE SORTIE :")
    print("  la table par heure de YM. Si 13:00 UTC concentre une part")
    print("  importante des reperes, l ouverture du cash domine, et")
    print("  toute mesure devra en tenir compte AVANT d etre ecrite.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
