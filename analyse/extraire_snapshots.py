# -*- coding: utf-8 -*-
r"""
extraire_snapshots.py -- 1,9 Go de snapshots ramenes a quelques Mo,
en gardant le VOLUME et les POC

  python extraire_snapshots.py --colonnes
  python extraire_snapshots.py
  python extraire_snapshots.py --jours 2026-08-12

CE QUE J AVAIS RATE

    J ai ecrit, le 17/08 : "sans volume, on ne peut construire qu un
    profil en TEMPS, pas un VPOC". C etait faux. Le volume est dans
    snapshots.csv depuis le debut, et pas qu un peu :

        volume_profile.poc / vah / val / bid_position
        market_laws.<actif>.M1 / M3 / M5 / M15.va_poc
        vp_daily.poc / pov_vol / total_vol / price_vs_poc
        vp_rolling.poc / pov_pct_of_poc
        futures_heatmap.poc / max_vol / total_vol
        cvd_strength.M1 / M3 / M5 / score
        tick_micro.absorption / reversal_prob / burst_* / velocity_*
        volcan_m3.v1 / v2 / day_max  (body, volume, direction, heure)
        pulse.delta_5min / delta_30min

    Je cherchais dans cycles.jsonl ce qui etait dans snapshots.csv. Le
    POC ancre est donc calculable, et il est meme DEJA CALCULE par la
    stack -- on n a pas a le reconstruire, on a a le lire.

POURQUOI UNE TRANSCRIPTION

    Chaque snapshots.csv pese 130 a 150 Mo pour environ 475 lignes :
    ce sont des lignes de plusieurs centaines de milliers de
    caracteres, avec des milliers de colonnes. On ne relit pas ca a
    chaque essai.

    On passe UNE fois, on garde les colonnes qui portent du volume, du
    POC, du CVD et de la microstructure, et on ecrit un CSV par
    journee. Le resultat se relit en une seconde.

    Le fichier est lu LIGNE PAR LIGNE et decoupe par index de colonne,
    calcules une seule fois depuis l en-tete. Rien n est charge en
    memoire.

CE QU ON GARDE

    Le choix se fait par MOTIF de nom, pas par liste ecrite a la main :
    une colonne qui contient poc, vah, val, vol, cvd, delta, tick,
    burst, absorption, velocity, reversal ou volcan est prise. Plus
    l horodatage, la phase de session, les trois prix, les positions et
    le PnL du jour.

    `--colonnes` montre ce qui serait pris, avec le compte, et n ecrit
    rien. A lancer AVANT la passe : on ne transcrit pas 1,9 Go contre
    une selection qu on n a pas regardee.

CADENCE

    L audit du 17/08 donne un pas de ~190 s pour cette source, soit
    trois minutes, sur 21 journees. Ce n est pas un flux fin : c est
    une base pour le POC, les positions et le PnL, pas pour une
    fenetre de quinze secondes. La colonne `ts` est conservee telle
    quelle et audit_cadence.py sait relire le resultat.

LECTEUR SEUL. N ouvre aucun fichier de la stack en ecriture.
"""
import argparse
import csv
import io
import os
import sys
import time

RACINE = os.path.join("docs", "buddha")
SORTIE = os.path.join("cartes", "snapshots")

# Toujours garder, quel que soit le motif.
TOUJOURS = ("ts", "session_phase", "bid.US30", "bid.US500", "bid.US100",
            "positions.n", "positions.n_buy", "positions.n_sell",
            "positions.open_pnl", "positions.day_pnl",
            "buddha.alignment", "buddha.leader", "buddha.weakest")

# Les motifs de selection. Un nom de colonne qui contient l un d eux
# est retenu. On choisit par MOTIF et pas par liste ecrite a la main :
# la liste des colonnes fait plusieurs milliers d entrees et changera
# encore ; un motif survit a un renommage partiel, une liste non.
MOTIFS = ("poc", "vah", "val", "vol", "cvd", "delta", "tick",
          "burst", "absorption", "velocity", "reversal", "volcan",
          "swing")

# ... sauf ceux-la. `description` et `reasons` sont des phrases de
# plusieurs centaines de caracteres : les garder ferait exploser la
# sortie sans rien apporter de mesurable.
EXCLUS = ("description", "reasons", "burst_history", "last_update")


def retenue(nom):
    n = nom.strip().lower()
    if nom.strip() in TOUJOURS:
        return True
    if any(x in n for x in EXCLUS):
        return False
    return any(m in n for m in MOTIFS)


def entete(chemin):
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        t = f.readline()
    return [c.strip() for c in t.rstrip("\r\n").split(",")]


def journees(racine):
    if not os.path.isdir(racine):
        return []
    out = []
    for j in sorted(os.listdir(racine)):
        c = os.path.join(racine, j, "snapshots.csv")
        if os.path.isfile(c):
            out.append((j, c))
    return out


def une_journee(src, dest, idx, noms, entetes):
    """Une passe en streaming. On ne parse pas le CSV : on decoupe la
    ligne et on prend les index voulus.

    On passe par le module csv et NON par un split sur la virgule.
    Un banc l a montre : une seule valeur contenant une virgule --
    `description` et `reasons` en contiennent -- decale toutes les
    colonnes suivantes de cette ligne, silencieusement. Sur 1,9 Go lus
    une seule fois, une passe juste et lente vaut mieux qu une passe
    rapide et decalee.

    Les lignes dont le nombre de champs ne correspond pas a l en-tete
    sont comptees et affichees : meme avec csv, un fichier tronque en
    cours d ecriture produit des lignes courtes, et un decalage
    silencieux serait pire qu une erreur."""
    lus = bancales = 0
    n_cols = len(entetes)
    t0 = time.time()
    with io.open(src, encoding="utf-8", errors="replace") as f:
        r = csv.reader(f)
        next(r, None)
        with io.open(dest, "w", encoding="utf-8", newline="") as g:
            w = csv.writer(g, delimiter=";")
            w.writerow(noms)
            for p in r:
                if len(p) != n_cols:
                    bancales += 1
                w.writerow([p[i] if i < len(p) else "" for i in idx])
                lus += 1
    return lus, bancales, time.time() - t0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", default=RACINE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--jours", default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--champ-max", type=int, default=10000000,
                   help="taille maximale d un champ csv")
    p.add_argument("--colonnes", action="store_true",
                   help="montre la selection et n ecrit rien")
    a = p.parse_args()

    # Les lignes font plusieurs centaines de milliers de
    # caracteres : la limite par defaut du module csv les
    # ferait echouer.
    csv.field_size_limit(a.champ_max)

    js = journees(a.racine)
    if not js:
        print("KO : aucun snapshots.csv sous %s." % a.racine)
        return 1
    if a.jours:
        voulus = set(x.strip() for x in a.jours.split(","))
        js = [(j, c) for j, c in js if j in voulus]
    if not js:
        print("KO : aucune des journees demandees n a de snapshots.csv.")
        return 1

    # L en-tete est lu sur la journee la PLUS RECENTE : c est celle qui
    # porte le plus de colonnes si la stack en a ajoute.
    cols = entete(js[-1][1])
    idx = [i for i, c in enumerate(cols) if retenue(c)]
    noms = [cols[i] for i in idx]

    if a.colonnes:
        print("En-tete lu sur %s : %d colonnes." % (js[-1][0], len(cols)))
        print("%d retenues par les motifs %s"
              % (len(noms), ", ".join(MOTIFS)))
        print("moins les exclusions %s." % ", ".join(EXCLUS))
        print()
        manquants = [c for c in TOUJOURS if c not in cols]
        if manquants:
            print("ATTENTION : ces colonnes reputees toujours presentes")
            print("sont ABSENTES de l en-tete : %s" % ", ".join(manquants))
            print("Le nom se lit dans les donnees, pas dans mon souvenir.")
            print()
        for c in noms:
            print("  %s" % c)
        print()
        print("%d colonnes retenues sur %d. Rien n a ete ecrit."
              % (len(noms), len(cols)))
        print("Relancer sans --colonnes pour transcrire.")
        return 0

    if len(noms) < 10:
        print("KO : seulement %d colonnes retenues. Les motifs ne"
              % len(noms))
        print("     correspondent pas a cet en-tete -- verifier avec")
        print("     --colonnes avant de lancer une passe de 1,9 Go.")
        return 1

    if not os.path.isdir(a.sortie):
        os.makedirs(a.sortie)
    poids = sum(os.path.getsize(c) for _, c in js)
    print("%d journee(s), %.1f Go a lire, %d colonnes gardees sur %d."
          % (len(js), poids / 1e9, len(noms), len(cols)))
    print()

    t0 = time.time()
    total = banc = 0
    for j, src in js:
        dest = os.path.join(a.sortie, "snap_%s.csv" % j)
        if os.path.isfile(dest) and not a.force:
            print("  %s : deja extrait, saute." % j)
            continue
        lus, b, sec = une_journee(src, dest, idx, noms, cols)
        total += lus
        banc += b
        print("  %s : %d lignes, %.0f s, %.1f Mo -> %d Ko"
              % (j, lus, sec, os.path.getsize(src) / 1e6,
                 os.path.getsize(dest) / 1000))
    print()
    print("%d lignes, %.0f s au total. Sortie : %s"
          % (total, time.time() - t0, a.sortie))
    if banc:
        print()
        print("%d ligne(s) n avaient pas le bon nombre de champs." % banc)
        print("Une valeur contenant une virgule decale le decoupage pour")
        print("cette ligne-la. Elles sont comptees et non corrigees : un")
        print("decalage silencieux serait pire qu une erreur affichee.")
    print()
    print("Rien n a ete analyse. C est une transcription.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
