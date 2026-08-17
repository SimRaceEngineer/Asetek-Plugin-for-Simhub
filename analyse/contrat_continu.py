# -*- coding: utf-8 -*-
r"""
contrat_continu.py -- rabouter les echeances en une seule serie

  python contrat_continu.py --racine MES
  python contrat_continu.py --racine YM --sortie cartes\scid
  python contrat_continu.py --racine MES --montre

POURQUOI

    Un `.scid` couvre UNE echeance. `MESU26` est le contrat de
    septembre : il existe depuis janvier mais ne cote vraiment qu a
    partir de juin, quand il devient le contrat de reference. Avant, il
    y a quelques transactions eparses -- assez pour remplir un fichier
    et faire croire a six mois d historique.

    Mesure du 17/08 : YMU26 affiche 154 dates et 72 625 barres, mais
    une MEDIANE de 131 barres par jour pour une moyenne de 471. Un
    future qui cote 23 h devrait en avoir ~1 380. La fenetre reellement
    exploitable faisait deux mois et demi sur six affiches.

    Pour couvrir un an, il faut plusieurs echeances et les rabouter.
    C est la pratique standard sur les futures, et c est ce que fait ce
    fichier.

COMMENT ON CHOISIT L ECHEANCE, CHAQUE JOUR

    Par le VOLUME, pas par une date de roulement ecrite a la main.

    Chaque journee, on retient le contrat qui a echange le plus de
    volume ce jour-la. C est la definition operationnelle du "contrat
    de reference" : celui ou le marche est. Elle se lit dans les
    donnees, elle ne se declare pas, et elle reste juste meme si le
    roulement a lieu un jour different de ce qu on croyait.

    `--montre` affiche le calendrier de roulement obtenu, sans rien
    ecrire. A regarder avant de raboutter : un roulement qui change
    trois fois en une semaine signale un probleme de donnees, pas un
    marche indecis.

CE QUI N EST PAS FAIT, ET POURQUOI

    AUCUN AJUSTEMENT DE PRIX. Deux echeances ne cotent pas au meme
    niveau -- l ecart peut faire des dizaines de points. Un raboutage
    brut cree donc un SAUT au roulement.

    On ne le corrige pas, et c est un choix :

      - pour mesurer une reaction en % sur quelques minutes ou
        quelques seances, le saut n intervient que si la fenetre
        enjambe le roulement. Ces fenetres-la sont RETIREES (colonne
        `roulement`), ce qui est exact ;
      - un ajustement retrospectif (retrancher l ecart a tout le
        passe) rendrait les prix anciens faux dans l absolu, et
        n importe quelle mesure de niveau -- un POC, un support --
        deviendrait fausse sans prevenir.

    Retirer quelques fenetres coute moins cher que falsifier tout
    l historique.

LECTEUR SEUL : lit les CSV de cartes\scid\, en ecrit un nouveau.
"""
import argparse
import csv
import io
import os
import sys
import datetime as dt

SORTIE = os.path.join("cartes", "scid")
LARG = 100

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def horo(s):
    if not s:
        return None
    try:
        return dt.datetime.strptime(s.strip()[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def lis(chemin):
    """Les lignes d un of_*.csv, avec leur date et leur volume."""
    out = []
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f, delimiter=";")
        champs = r.fieldnames or []
        for d in r:
            t = horo(d.get("ts"))
            if not t:
                continue
            out.append((t, d))
    out.sort(key=lambda x: x[0])
    return out, champs


def volume_par_jour(lignes):
    par = {}
    for t, d in lignes:
        v = flt(d.get("volume")) or 0.0
        j = t.date()
        par[j] = par.get(j, 0.0) + v
    return par


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", required=True,
                   help="prefixe du symbole, par ex. MES ou YM")
    p.add_argument("--entree", default=SORTIE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--persistance", type=int, default=3,
                   help="journees consecutives avant de changer de "
                        "contrat de reference")
    p.add_argument("--montre", action="store_true",
                   help="affiche le calendrier de roulement, n ecrit rien")
    a = p.parse_args()

    if not os.path.isdir(a.entree):
        print("KO : %s introuvable." % a.entree)
        return 1
    fichiers = [n for n in sorted(os.listdir(a.entree))
                if n.startswith("of_" + a.racine) and n.endswith(".csv")
                and "continu" not in n]
    if not fichiers:
        print("KO : aucun of_%s*.csv dans %s." % (a.racine, a.entree))
        print("     Lancer d abord lire_scid.py sur les .scid voulus.")
        return 1

    dis("=" * LARG)
    dis("CONTRAT CONTINU %s -- raboutage par le volume" % a.racine)
    dis("=" * LARG)
    dis("  %d echeance(s) trouvee(s)." % len(fichiers))
    dis()

    series = {}
    champs = None
    for n in fichiers:
        nom = n[3:-4]
        lignes, ch = lis(os.path.join(a.entree, n))
        if not lignes:
            dis("  %-24s vide, ignore." % nom)
            continue
        champs = champs or ch
        series[nom] = lignes
        vpj = volume_par_jour(lignes)
        dis("  %-24s %7d barres, %s -> %s, volume total %.0f"
            % (nom, len(lignes), lignes[0][0].strftime("%Y-%m-%d"),
               lignes[-1][0].strftime("%Y-%m-%d"),
               sum(vpj.values())))

    if len(series) < 2:
        dis()
        dis("  Une seule echeance exploitable : il n y a rien a rabouter.")
        dis("  Telecharger les echeances anterieures dans SierraChart")
        dis("  (symbole + Chart > Reload and Recalculate, sur un")
        dis("  graphique INTRADAY -- le Daily ne remplit pas le .scid).")
        return 1

    # --- qui domine chaque journee ---
    persistance = a.persistance
    vols = dict((k, volume_par_jour(v)) for k, v in series.items())
    jours = sorted(set(j for v in vols.values() for j in v))
    # LE CHOIX DU JOUR NE SUFFIT PAS : IL FAUT DE L HYSTERESIS.
    #
    # "Le contrat qui a le plus de volume aujourd hui" bascule au
    # hasard quand les deux echeances sont illiquides. Sur le banc :
    # HUIT bascules pour DEUX echeances, dont six en mars alors
    # qu aucun des deux contrats n avait encore de volume.
    #
    # On ne change donc de reference que si le challenger domine
    # `persistance` journees CONSECUTIVES. Un roulement est un
    # evenement rare et durable ; s il hesite, c est qu on le lit dans
    # du bruit.
    chef = {}
    courant = None
    pretendant = None
    suite = 0
    for j in jours:
        best = None
        for k in series:
            v = vols[k].get(j, 0.0)
            if v > 0 and (best is None or v > best[1]):
                best = (k, v)
        if best is None:
            if courant:
                chef[j] = courant
            continue
        gagnant = best[0]
        if courant is None:
            courant = gagnant
        elif gagnant != courant:
            if gagnant == pretendant:
                suite += 1
            else:
                pretendant, suite = gagnant, 1
            if suite >= persistance:
                courant = gagnant
                pretendant, suite = None, 0
        else:
            pretendant, suite = None, 0
        chef[j] = courant

    # --- le calendrier de roulement ---
    dis()
    dis("-" * LARG)
    dis("QUI DOMINE, ET QUAND")
    dis("-" * LARG)
    bascules = []
    prec = None
    for j in jours:
        c = chef.get(j)
        if c and c != prec:
            bascules.append((j, prec, c))
            prec = c
    dis("  %-14s %-26s %-26s" % ("date", "avant", "apres"))
    for j, av, ap in bascules:
        dis("  %-14s %-26s %-26s"
            % (j.strftime("%Y-%m-%d"), av or "(debut)", ap))
    dis()
    dis("  %d bascule(s), avec une persistance de %d journees."
        % (len(bascules), persistance))
    dis("  Le contrat de reference est celui qui echange le plus de")
    dis("  volume, mais il ne change que s il domine %d journees"
        % persistance)
    dis("  CONSECUTIVES : un roulement est rare et durable. Sans cette")
    dis("  condition, deux echeances illiquides se relaient au hasard")
    dis("  -- huit bascules pour deux contrats sur le banc.")
    if len(bascules) > len(series):
        dis()
        dis("  ATTENTION : %d bascules pour %d echeances. Un roulement"
            % (len(bascules), len(series)))
        dis("  qui hesite signale un probleme de donnees -- typiquement")
        dis("  une echeance mal telechargee -- pas un marche indecis.")

    if a.montre:
        dis()
        dis("  --montre : rien n a ete ecrit.")
        return 0

    # --- ecriture ---
    dest = os.path.join(a.sortie, "of_%s-continu.csv" % a.racine)
    n_ecrites = n_roul = 0
    with io.open(dest, "w", encoding="utf-8", newline="") as g:
        w = csv.DictWriter(g, fieldnames=list(champs) + ["contrat",
                                                         "roulement"],
                           delimiter=";", extrasaction="ignore")
        w.writeheader()
        jours_bascule = set(j for j, _, _ in bascules)
        for k in sorted(series):
            for t, d in series[k]:
                if chef.get(t.date()) != k:
                    continue
                e = dict(d)
                e["contrat"] = k
                # Une barre du jour de bascule porte un saut de prix
                # qui n est pas un mouvement de marche. On la marque au
                # lieu de la corriger : une fenetre qui l enjambe doit
                # etre retiree, pas rattrapee.
                e["roulement"] = 1 if t.date() in jours_bascule else 0
                n_roul += e["roulement"]
                w.writerow(e)
                n_ecrites += 1

    # le fichier a ete ecrit contrat par contrat : il faut le trier
    with io.open(dest, encoding="utf-8") as f:
        r = list(csv.DictReader(f, delimiter=";"))
    r.sort(key=lambda d: d.get("ts") or "")
    with io.open(dest, "w", encoding="utf-8", newline="") as g:
        w = csv.DictWriter(g, fieldnames=list(champs) + ["contrat",
                                                         "roulement"],
                           delimiter=";", extrasaction="ignore")
        w.writeheader()
        for d in r:
            w.writerow(d)

    dis()
    dis("=" * LARG)
    dis("ECRIT : %s" % dest)
    dis("=" * LARG)
    dis("  %d barres, dont %d marquees `roulement`." % (n_ecrites, n_roul))
    dis("  Deux colonnes ajoutees : `contrat` (l echeance d origine) et")
    dis("  `roulement` (1 le jour d une bascule).")
    dis()
    dis("  AUCUN AJUSTEMENT DE PRIX n a ete fait. Deux echeances ne")
    dis("  cotent pas au meme niveau, donc la serie contient un SAUT a")
    dis("  chaque bascule. Il est marque, pas corrige : ajuster")
    dis("  retrospectivement rendrait tous les prix anciens faux dans")
    dis("  l absolu, et n importe quelle mesure de niveau -- un POC, un")
    dis("  support -- deviendrait fausse sans prevenir.")
    dis()
    dis("  Toute mesure dont la fenetre enjambe un jour de roulement")
    dis("  doit etre RETIREE. Retirer quelques fenetres coute moins")
    dis("  cher que falsifier tout l historique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
