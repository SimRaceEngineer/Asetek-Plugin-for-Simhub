# -*- coding: utf-8 -*-
r"""
archive_zones.py -- garder le journal des zones avant qu il soit purge

  python archive_zones.py
  python archive_zones.py --source "C:\...\intraday_zones_held.log"

POURQUOI

  intraday_zones.py ecrit ses evenements dans

      %APPDATA%\MetaQuotes\Terminal\Common\Files\intraday_zones_held.log

  et le REECRIT periodiquement -- `open(HELD_LOG_FILE, "w")`, ligne
  2050. Constate le 18/08 : 71 130 octets couvrant 32 heures, du 17/08
  05:02 au 18/08 13:12. Ce n est pas une archive, c est un tampon.

  Nos bougies reperes couvrent cinq mois. Croiser les deux aujourd hui
  porterait sur un jour et demi d evenements : aucune puissance, et un
  `p` qui ne voudrait rien dire. La bonne reponse n est pas de mesurer
  quand meme, c est d accumuler.

CE QU IL FAIT

  Il lit le journal, et ajoute a `docs\zones_held.log` les lignes que
  l archive ne contient pas encore. Rien d autre.

  IL N ECRIT JAMAIS DANS LE JOURNAL DE LA STACK. Le fichier source est
  ouvert en lecture seule. Un outil d analyse qui touche a un fichier
  ecrit par le systeme vivant est un outil qu on ne peut plus lancer
  sans reflechir.

TROIS PRECAUTIONS, CHACUNE POUR UNE RAISON PRECISE

  1. LA DERNIERE LIGNE INCOMPLETE EST IGNOREE. Le journal est ouvert en
     ajout par un processus vivant : une lecture peut tomber au milieu
     d une ligne. On ne garde que les lignes terminees par un saut de
     ligne. La ligne laissee de cote sera reprise au tour suivant,
     complete -- la deduplication s en charge.

  2. DEDUPLICATION SUR LA LIGNE ENTIERE. Pas sur la date : deux
     evenements peuvent partager la seconde (le 17/08 a 05:02, trois
     lignes en vingt-deux secondes). Comparer des lignes completes ne
     perd rien et n invente rien.

  3. DETECTION DE TROU. Si la premiere ligne du journal est POSTERIEURE
     a la derniere ligne de l archive, l intervalle entre les deux a
     ete purge avant qu on le lise.

     L outil signale cet INTERVALLE ; il n affirme pas une perte -- le
     trou peut etre vide, et l outil ne sait pas ce qu il n a pas vu.
     La nuance compte : une archive qui se croit complete est mauvaise,
     mais un outil qui annonce des pertes imaginaires l est aussi.

CADENCE

  La purge se declenche a un moment que le code ne dit pas -- ni
  quotidien franc, ni horaire : le tampon actuel demarre au 17/08
  05:02 et n a pas ete purge le 18 a la meme heure. Probablement un
  plafond de taille.

  Donc : AU MOINS une fois par jour, deux valent mieux. La detection de
  trou dira si la cadence choisie suffit ; c est elle qui doit decider,
  pas moi.

CE QU IL NE FAIT PAS

  Aucune mesure, aucun croisement, aucune interpretation. Il accumule.
  Le croisement avec les bougies reperes se fera quand l archive aura
  de la profondeur, et son enonce sera gele avant.

LECTEUR SEUL sur le journal. N ecrit que dans `docs\`.
"""
import argparse
import io
import os
import sys

SOURCE = os.path.join(os.environ.get("APPDATA", ""), "MetaQuotes",
                      "Terminal", "Common", "Files",
                      "intraday_zones_held.log")
ARCHIVE = os.path.join("docs", "zones_held.log")


def lignes_completes(chemin):
    """Les lignes du fichier, SANS la derniere si elle est tronquee.

    Un processus vivant ecrit dedans en ajout ; tomber au milieu d une
    ligne est normal, pas exceptionnel."""
    if not os.path.isfile(chemin):
        return None, "absent"
    brut = io.open(chemin, "r", encoding="ascii", errors="replace").read()
    if not brut:
        return [], "vide"
    tronquee = not brut.endswith("\n")
    v = [x for x in brut.split("\n") if x.strip()]
    if tronquee and v:
        v = v[:-1]
        return v, "derniere ligne incomplete, laissee pour le tour suivant"
    return v, ""


def horodate(ligne):
    """La date d une ligne, ou None. Format constate :
    2026-08-18 13:09:50|US500|TOP|7727.33|HELD|H:2|..."""
    t = ligne.split("|", 1)[0].strip()
    return t if len(t) == 19 and t[4] == "-" and t[13] == ":" else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default=SOURCE)
    p.add_argument("--archive", default=ARCHIVE)
    a = p.parse_args()

    print("=" * 78)
    print("ARCHIVE DU JOURNAL DES ZONES")
    print("=" * 78)
    print("  source  : %s" % a.source)
    print("  archive : %s" % a.archive)
    print()

    src, note = lignes_completes(a.source)
    if src is None:
        print("KO : journal introuvable.")
        print("     Verifie le chemin -- il vient de intraday_zones.py,")
        print("     lignes 149 a 155.")
        return 1
    if note:
        print("  note : %s" % note)
    print("  journal : %d ligne(s) exploitable(s)" % len(src))
    if not src:
        print("  rien a archiver.")
        return 0

    d = os.path.dirname(a.archive)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    arc, _ = lignes_completes(a.archive)
    arc = arc or []
    print("  archive : %d ligne(s) avant ce passage" % len(arc))

    # --- trou : le journal commence-t-il APRES la fin de l archive ? --
    if arc:
        t_arc = [horodate(x) for x in arc]
        t_arc = [x for x in t_arc if x]
        t_src = [horodate(x) for x in src]
        t_src = [x for x in t_src if x]
        if t_arc and t_src and t_src[0] > t_arc[-1]:
            print()
            print("  TROU POSSIBLE : le journal demarre a %s," % t_src[0])
            print("         l archive s arrete a %s. Ce qui a pu" % t_arc[-1])
            print("         se produire dans cet intervalle a ete purge")
            print("         avant qu on le lise.")
            print("         Le trou peut etre VIDE -- l outil ne sait pas")
            print("         ce qu il n a pas vu. Il signale l intervalle,")
            print("         il n affirme pas une perte.")
            print("         S il revient souvent, passer plus souvent.")

    connu = set(arc)
    neuf = [x for x in src if x not in connu]
    if neuf:
        f = io.open(a.archive, "a", encoding="ascii", errors="replace",
                    newline="")
        for x in neuf:
            f.write(x + "\n")
        f.close()
    print()
    print("  ajoutees : %d" % len(neuf))
    print("  archive  : %d ligne(s) au total" % (len(arc) + len(neuf)))

    tous = arc + neuf
    t = [horodate(x) for x in tous]
    t = [x for x in t if x]
    if t:
        print("  periode  : %s -> %s" % (min(t), max(t)))
        print("  non horodatees : %d" % (len(tous) - len(t)))
    print()
    print("  Aucune mesure ici. On accumule ; le croisement avec les")
    print("  bougies reperes attend que l archive ait de la profondeur,")
    print("  et son enonce sera gele avant d etre calcule.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
