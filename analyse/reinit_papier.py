# -*- coding: utf-8 -*-
"""
reinit_papier.py -- repartir du journal papier a une coupure nette

  python reinit_papier.py --coupure 2026-08-13T00:00 --essai
  python reinit_papier.py --coupure 2026-08-13T00:00

POURQUOI PLUTOT QUE --depuis

    --depuis existe et marche. Mais c est un filtre qu il faut penser a
    taper : dans trois mois, quelqu un lira le rapport sans lui et
    conclura sur huit entrees ouvertes a la meme seconde le 12/08 a
    23:38:54, sur aucun signal. Un artefact qu on doit se rappeler
    d exclure finit toujours par etre inclus.

    Ici il sort du journal. Ce qui reste est propre par construction,
    et le rapport n a plus besoin d etre corrige a la lecture.

RIEN N EST DETRUIT

    Les lignes ecartees vont dans docs/papier_tf/trades.avant-<coupure>
    .jsonl, a cote. Si on veut un jour comparer, ou verifier que la
    coupure etait au bon endroit, tout est la.

LA COUPURE PORTE SUR L OUVERTURE, PAS SUR LA CLOTURE

    Un trade ouvert a 23:38 et ferme a 03:00 porte ts=03:00 et
    ouvert=23:38. C est une entree du 12, pas du 13. Trier sur la
    cloture laisserait passer exactement les lignes qu on veut sortir.

    Les VEILLE, elles, sont datees de leur propre instant : une veille
    est une preuve de presence a un moment donne, pas un evenement qui
    dure.

LES POSITIONS ENCORE OUVERTES

    Le script regarde etat.json. Une position ouverte AVANT la coupure
    finirait par ecrire sa cloture dans le journal neuf, et reintroduirait
    ce qu on vient d en sortir. Elles sont donc retirees de l etat, et
    le script dit lesquelles.

    Au 13/08 10:25 la plus ancienne date de 02:20 : il ne devrait y en
    avoir aucune. Le controle est la pour le jour ou ce ne sera plus
    vrai.

ARRETE L OBSERVATEUR AVANT DE LANCER CECI

    papier_tf --loop ajoute une ligne toutes les dix minutes et a chaque
    evenement. Reecrire le fichier pendant qu il ecrit dedans perdrait
    une ligne, au hasard. Le script le rappelle et n a aucun moyen de le
    verifier lui-meme.

LECTURE ET REECRITURE D UN SEUL FICHIER. Aucun ordre, aucun processus
touche.
"""
import argparse
import io
import json
import os
import shutil
import sys
from datetime import datetime

_ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER = os.path.join(_ICI, "docs", "papier_tf")
TRADES = os.path.join(DOSSIER, "trades.jsonl")
ETAT = os.path.join(DOSSIER, "etat.json")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--coupure", required=True,
                   help="AAAA-MM-JJTHH:MM -- tout ce qui est OUVERT avant"
                        " part a l archive")
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if len(a.coupure) < 16 or a.coupure[10] != "T":
        print("KO : coupure attendue au format AAAA-MM-JJTHH:MM.")
        print("     Recu : %r" % a.coupure)
        return 1
    if not os.path.isfile(TRADES):
        print("KO : %s introuvable." % TRADES)
        return 1

    garde, archive, illisibles = [], [], 0
    for ligne in io.open(TRADES, encoding="utf-8", errors="replace"):
        brut = ligne.strip()
        if not brut:
            continue
        if brut[0] != "{":
            illisibles += 1
            continue
        try:
            e = json.loads(brut)
        except ValueError:
            illisibles += 1
            continue
        # TRADE : on juge sur l ouverture. VEILLE : sur son propre instant.
        quand = e.get("ouvert") if e.get("quoi") == "TRADE" else e.get("ts")
        (garde if (quand or "") >= a.coupure else archive).append(brut)

    tr_g = len([l for l in garde if '"quoi": "TRADE"' in l])
    tr_a = len([l for l in archive if '"quoi": "TRADE"' in l])
    ve_g = len(garde) - tr_g
    ve_a = len(archive) - tr_a

    print("=" * 72)
    print(" REINITIALISATION DU JOURNAL PAPIER")
    print("=" * 72)
    print("coupure : %s" % a.coupure.replace("T", " "))
    print()
    print("%-28s %8s %8s" % ("", "gardees", "archivees"))
    print("-" * 72)
    print("%-28s %8d %8d" % ("jambes de trade", tr_g, tr_a))
    print("%-28s %8d %8d" % ("veilles", ve_g, ve_a))
    print("-" * 72)
    if illisibles:
        print("%d ligne(s) illisible(s), laissee(s) de cote." % illisibles)
    if not archive:
        print()
        print("Rien a archiver : aucune ligne anterieure a la coupure.")
        print("Le journal est deja propre a partir de cet instant.")
        return 0

    # Les positions ouvertes avant la coupure ecriraient leur cloture
    # dans le journal neuf et y reintroduiraient ce qu on en sort.
    vieilles = {}
    etat = {}
    if os.path.isfile(ETAT):
        try:
            etat = json.load(io.open(ETAT, encoding="utf-8"))
        except (ValueError, IOError):
            etat = {}
        vieilles = {k: v for k, v in etat.items()
                    if (v.get("ts") or "") < a.coupure}

    print()
    if vieilles:
        print("POSITIONS OUVERTES ANTERIEURES A LA COUPURE -- retirees de")
        print("l etat, sinon leur cloture reviendrait dans le journal neuf :")
        for k in sorted(vieilles):
            print("  %-10s ouverte le %s" % (k, vieilles[k].get("ts")))
    else:
        print("Aucune position ouverte n est anterieure a la coupure.")
        print("L etat n a pas besoin d etre touche.")

    print()
    print("ARRETE papier_tf --loop AVANT D ECRIRE : il ajoute une ligne")
    print("toutes les dix minutes, et reecrire le fichier pendant qu il")
    print("ecrit dedans en perdrait une, au hasard.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    horo = a.coupure.replace(":", "").replace("-", "")
    dest = os.path.join(DOSSIER, "trades.avant-%s.jsonl" % horo)
    io.open(dest, "w", encoding="utf-8").write("\n".join(archive) + "\n")

    sauve = TRADES + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(TRADES, sauve)
    tmp = TRADES + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(
        ("\n".join(garde) + "\n") if garde else "")
    if os.path.exists(TRADES):
        os.remove(TRADES)
    os.rename(tmp, TRADES)

    if vieilles:
        for k in vieilles:
            etat.pop(k, None)
        t2 = ETAT + ".tmp"
        io.open(t2, "w", encoding="utf-8").write(
            json.dumps(etat, ensure_ascii=False, indent=1))
        if os.path.exists(ETAT):
            os.remove(ETAT)
        os.rename(t2, ETAT)

    print()
    print("archive     : %s" % dest)
    print("sauvegarde  : %s" % sauve)
    print("journal     : %d ligne(s) conservee(s)" % len(garde))
    if vieilles:
        print("etat        : %d position(s) retiree(s)" % len(vieilles))
    print()
    print("Relance papier_tf --loop. L amorcage fait qu il n ouvrira rien")
    print("au demarrage : le journal repart vraiment de la coupure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
