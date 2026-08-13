# -*- coding: utf-8 -*-
"""
reinit_x60.py -- sortir du journal les entrees inventees par un redemarrage

  python reinit_x60.py --essai
  python reinit_x60.py --fenetre "2026-08-13 13:15" "2026-08-13 13:25" --essai
  python reinit_x60.py --fenetre "2026-08-13 13:15" "2026-08-13 13:25"

CE QU IL SORT, ET POURQUOI

    Avant patch_x60_amorcage, l observateur partait avec `connus` vide :
    chaque position x60 DEJA ouverte etait donc enregistree comme une
    nouvelle entree, horodatee a l instant du demarrage. Une entree qui
    n a jamais eu lieu, et qui apporte avec elle un plateau complet de
    tierces qui n accompagnaient rien.

    Le 13/08 vers 13:20, apres le redemarrage du moteur, l observateur
    a ete relance et a produit ces fausses entrees.

COMMENT IL LES RECONNAIT

    Par defaut, sans --fenetre, il les DETECTE : plusieurs X60_ENTREE
    dans la meme seconde, ou a moins de %d s les unes des autres, apres
    un silence d au moins %d minutes. C est la signature d un
    demarrage, pas celle du marche -- les cellules H1 basculent a des
    instants differents.

    Il AFFICHE ce qu il a trouve et ne touche a rien sans --fenetre
    explicite ou sans confirmation. Une detection automatique qui
    supprime toute seule est exactement ce qu on ne veut pas ici.

RIEN N EST DETRUIT

    Les lignes ecartees vont dans docs/x60_onset/events.avant-<horo>
    .jsonl, a cote. Meme regle que pour le papier ce matin : on archive,
    on ne supprime pas. Si la coupure etait au mauvais endroit, tout est
    encore la.

CE QU IL NE TOUCHE PAS

    Uniquement les X60_ENTREE de la fenetre. Les VEILLE, les CLOTURE,
    les SUIVI et les X60_SORTIE restent. Une sortie sans entree est
    proprement geree par le rapport, qui l ecarte en le disant -- alors
    qu une entree sans realite fausse tous les comptes.

ARRETE L OBSERVATEUR AVANT D ECRIRE

    x60_onset --loop ajoute des lignes en continu. Reecrire le fichier
    pendant qu il ecrit dedans en perdrait une, au hasard.

LECTURE ET REECRITURE D UN SEUL FICHIER. Aucun ordre, aucun processus
touche.
"""
import argparse
import io
import json
import os
import shutil
import sys
from datetime import datetime, timedelta

_ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER = os.path.join(_ICI, "docs", "x60_onset")
EVENTS = os.path.join(DOSSIER, "events.jsonl")

RAFALE_S = 90        # entrees separees de moins de ca = meme demarrage
SILENCE_MIN = 20     # silence avant la rafale qui la rend suspecte
LARG = 78

__doc__ = __doc__ % (RAFALE_S, SILENCE_MIN)


def _horo(s):
    try:
        return datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        try:
            return datetime.strptime(str(s)[:16], "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fenetre", nargs=2, metavar=("DEBUT", "FIN"),
                   help='"AAAA-MM-JJ HH:MM" "AAAA-MM-JJ HH:MM"')
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(EVENTS):
        print("KO : %s introuvable." % EVENTS)
        return 1

    lignes, evs, ill = [], [], 0
    for ligne in io.open(EVENTS, encoding="utf-8", errors="replace"):
        b = ligne.strip()
        if not b:
            continue
        if b[0] != "{":
            ill += 1
            lignes.append((b, None))
            continue
        try:
            e = json.loads(b)
        except ValueError:
            ill += 1
            lignes.append((b, None))
            continue
        lignes.append((b, e))
        evs.append(e)

    entrees = [(i, e) for i, (_b, e) in enumerate(lignes)
               if e and e.get("quoi") == "X60_ENTREE"]

    print("=" * LARG)
    print(" REINITIALISATION DU JOURNAL x60")
    print("=" * LARG)
    print("%d ligne(s), dont %d X60_ENTREE." % (len(lignes), len(entrees)))
    if ill:
        print("%d ligne(s) illisible(s), conservee(s) telles quelles." % ill)
    print()

    if a.fenetre:
        d, f = _horo(a.fenetre[0]), _horo(a.fenetre[1])
        if d is None or f is None:
            print("KO : fenetre attendue au format \"AAAA-MM-JJ HH:MM\".")
            return 1
        vises = [i for i, e in entrees
                 if (_horo(e.get("ts")) or datetime.min) >= d
                 and (_horo(e.get("ts")) or datetime.max) <= f]
        print("Fenetre demandee : %s -> %s" % (d, f))
    else:
        # DETECTION. Une rafale d entrees rapprochees apres un silence
        # est la signature d un demarrage : les cellules H1 basculent a
        # des instants differents, elles ne s allument pas ensemble.
        vises = []
        groupes = []
        courant = []
        prec = None
        for i, e in entrees:
            t = _horo(e.get("ts"))
            if t is None:
                continue
            if prec is not None and (t - prec).total_seconds() <= RAFALE_S:
                courant.append((i, e, t))
            else:
                if len(courant) > 1:
                    groupes.append(courant)
                courant = [(i, e, t)]
            prec = t
        if len(courant) > 1:
            groupes.append(courant)

        print("DETECTION : %d groupe(s) d entrees a moins de %d s."
              % (len(groupes), RAFALE_S))
        print()
        for g in groupes:
            t0 = g[0][2]
            av = [_horo(e.get("ts")) for _i, (_b, e) in enumerate(lignes)
                  if e and _horo(e.get("ts")) and _horo(e.get("ts")) < t0]
            silence = (t0 - max(av)).total_seconds() / 60.0 if av else 999.0
            # LE BON DISCRIMINANT EST LE NOMBRE, PAS LE SILENCE.
            # Corrige le 13/08 sur le cas reel : la rafale de 13:19:21
            # portait cinq entrees et n avait que 10 minutes de silence
            # devant elle -- le seuil de silence l a donc classee
            # "plausible", a tort.
            # Une PAIRE 206/207 de la meme cellule a quelques secondes
            # d ecart est normale : les deux bras entrent sur le meme
            # signal. Au-dela de deux, ou des que plusieurs ACTIFS
            # s allument dans la meme seconde, c est un demarrage : les
            # cellules H1 de trois indices ne basculent pas ensemble.
            actifs = set(e.get("actif") for _i, e, _t in g)
            secondes = set(t.strftime("%H:%M:%S") for _i, _e, t in g)
            suspect = (len(g) > 2
                       or (len(actifs) > 1 and len(secondes) == 1))
            raison = ("%d entrees" % len(g) if len(g) > 2
                      else "%d actifs dans la meme seconde" % len(actifs))
            print("  %s  %d entree(s)  %d actif(s)  silence avant :"
                  " %.0f min  -> %s"
                  % (t0.strftime("%Y-%m-%d %H:%M:%S"), len(g), len(actifs),
                     silence, ("SUSPECT (%s)" % raison) if suspect
                     else "plausible"))
            for _i, e, t in g:
                print("      %s  M%s  %s"
                      % (t.strftime("%H:%M:%S"), e.get("magic"),
                         e.get("actif")))
            if suspect:
                vises.extend([_i for _i, _e, _t in g])
        print()
        if not groupes:
            print("Aucun groupe : rien ne ressemble a un redemarrage.")
        print("La detection ne suffit pas a decider. Relance avec")
        print("--fenetre \"debut\" \"fin\" pour ecrire, en reprenant les")
        print("horodatages ci-dessus. Rien n a ete ecrit.")
        return 0

    if not vises:
        print("Aucune X60_ENTREE dans cette fenetre. Rien a faire.")
        return 0

    print()
    print("%d X60_ENTREE seront archivees :" % len(vises))
    for i in vises:
        e = lignes[i][1]
        print("  %s  M%s  %s  (%d tierces)"
              % (e.get("ts"), e.get("magic"), e.get("actif"),
                 len(e.get("plateau") or [])))
    print()
    print("Les VEILLE, CLOTURE, SUIVI et X60_SORTIE de la meme fenetre")
    print("sont CONSERVEES. Une sortie sans entree est ecartee proprement")
    print("par le rapport, qui le dit ; une entree sans realite, non.")
    print()
    print("ARRETE x60_onset --loop AVANT D ECRIRE : il ajoute des lignes")
    print("en continu, et reecrire le fichier pendant ce temps en")
    print("perdrait une, au hasard.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    vus = set(vises)
    garde = [b for i, (b, _e) in enumerate(lignes) if i not in vus]
    arch = [b for i, (b, _e) in enumerate(lignes) if i in vus]

    horo = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(DOSSIER, "events.avant-%s.jsonl" % horo)
    io.open(dest, "w", encoding="utf-8").write("\n".join(arch) + "\n")

    sauve = EVENTS + ".bak-" + horo
    shutil.copy2(EVENTS, sauve)
    tmp = EVENTS + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(
        ("\n".join(garde) + "\n") if garde else "")
    if os.path.exists(EVENTS):
        os.remove(EVENTS)
    os.rename(tmp, EVENTS)

    print()
    print("archive    : %s" % dest)
    print("sauvegarde : %s" % sauve)
    print("journal    : %d ligne(s) conservee(s)" % len(garde))
    print()
    print("Relance x60_onset --loop. L amorcage fait qu il n inventera")
    print("plus d entree au demarrage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
