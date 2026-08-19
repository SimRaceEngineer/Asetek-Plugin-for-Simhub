# -*- coding: utf-8 -*-
r"""
papers_conflit.py -- les quatre lignes que MON parseur n a pas su lire

  python papers_conflit.py
  python papers_conflit.py --mot CONFLIT

LECTEUR SEUL. N ECRIT RIEN, NE PREND AUCUN TRADE.

CE QUE panel_papers.txt A REVELE, ET CE QUE CA DIT DE MOI

    Les libelles de l export portaient les reponses que j ai passe
    deux scripts a deduire :

      M15 SCATTER / MIXED / ALL   la colonne ALL etait ECRITE
      M5 * NO / CLEAN             l etoile = ancre M5 (panneau:878),
                                  et l absence de WITH/AGAINST = la
                                  ligne dv "-"
      M15 NO / MIXED              pas d etoile : ancre M15, meme
                                  ligne "-"

    J ai reconstruit par balayage ce qui etait imprime sur la ligne.
    C est la meme faute que le 14/08 et le 18/08 : raisonner sur ma
    reconstruction alors que la definition etait dans un fichier que
    j avais deja.

CE QUI RESTE, ET POURQUOI CE N EST PAS UNE ENIGME DU PANNEAU

    Quatre lignes de l export portent un marqueur ecrit par MON
    parseur, papers_panel.py :

      M1 bull RSI dedans / achat    n= 171   [col. non identifiee : 15]
      M15 bull RSI au-dessus/achat  n= 186   [col. non identifiee : 12]
      M15 CONFLIT vente             n= 358   [col. non identifiee : 15]
      M15 bull+                     n= 248   [col. non identifiee : 12]

    Ce sont EXACTEMENT les quatre qui ne se reproduisent jamais. Le
    marqueur dit que le parseur n a pas su quelle colonne portait
    l effectif. Les nombres 171, 186, 358 et 248 sont donc suspects
    a la source : j ai cherche a reproduire des valeurs dont mon
    propre outil annoncait qu il n etait pas sur de les avoir lues.

    Continuer a chercher un predicat pour ces nombres serait chercher
    la bonne cle pour une serrure dont on n a pas verifie l adresse.

CE QUE FAIT CE SCRIPT

    A. Il trouve, dans le SOURCE du panneau, les fonctions qui
       produisent ces libelles -- CONFLUENCE rails x HLC pour le
       CONFLIT, et ce qui porte "bull+" et le RSI -- et les imprime
       telles quelles. Aucune paraphrase.

    B. Il retrouve dans les PANNEAUX TEXTE la ligne d origine de
       chacune des quatre, avec son en-tete de section et sa ligne
       de colonnes, pour qu on voie enfin la mise en colonne que le
       parseur n a pas su lire.

    Ensuite seulement on saura si 358 est un effectif ou une autre
    colonne. Pas avant.
"""
import argparse
import io
import os
import re
import sys

MOTS_SOURCE = ("CONFLIT", "bull+", "dedans", "au-dessus", "CONFLUENCE")
LIBELLES = ("M15 CONFLIT vente", "M1 bull RSI dedans",
            "M15 bull RSI au-dessus", "M15 bull+")
MAX_FONCTION = 90


def enclosante(lignes, k):
    ind = len(lignes[k]) - len(lignes[k].lstrip())
    for j in range(k, -1, -1):
        m = re.match(r"(\s*)def\s+(\w+)\s*\(", lignes[j])
        if m and len(m.group(1)) < ind:
            return m.group(2), j
    return "<module>", None


def corps(lignes, debut):
    """La fonction entiere, du def a la premiere ligne de meme niveau."""
    ind = len(lignes[debut]) - len(lignes[debut].lstrip())
    fin = debut + 1
    while fin < len(lignes):
        l = lignes[fin]
        if l.strip() and (len(l) - len(l.lstrip())) <= ind:
            break
        fin += 1
    return debut, fin


def partie_source(add, chemin, mots):
    add("=" * 96)
    add("LE SOURCE DES SECTIONS QUI PRODUISENT CES LIBELLES")
    add("=" * 96)
    if not chemin or not os.path.isfile(chemin):
        add("  Panneau introuvable.")
        return
    lignes = io.open(chemin, encoding="utf-8",
                     errors="replace").read().split("\n")
    add("  %s : %d lignes" % (chemin, len(lignes)))
    add("")
    vues = {}
    for i, l in enumerate(lignes):
        if not any(m in l for m in mots):
            continue
        nom, debut = enclosante(lignes, i)
        if debut is None or nom in vues:
            continue
        vues[nom] = debut
    if not vues:
        add("  Aucun de ces mots dans le panneau. Les libelles viennent")
        add("  donc d un AUTRE producteur -- un panneau different.")
        return
    add("  Fonctions concernees : %s" % ", ".join(sorted(vues)))
    add("")
    for nom in sorted(vues, key=lambda n: vues[n]):
        d, f = corps(lignes, vues[nom])
        n = f - d
        add("-" * 96)
        add("  --- %s  (ligne %d, %d lignes)" % (nom, d + 1, n))
        add("-" * 96)
        for k in range(d, min(f, d + MAX_FONCTION)):
            add("  %5d  %s" % (k + 1, lignes[k][:104]))
        if n > MAX_FONCTION:
            add("  ... %d lignes de plus (rendu HTML)" % (n - MAX_FONCTION))
        add("")


def fichiers_texte(racines, taille_max=6 * 1024 * 1024):
    vus = set()
    for racine in racines:
        if not os.path.isdir(racine):
            continue
        for dossier, _sd, fichiers in os.walk(racine):
            for f in sorted(fichiers):
                if not f.lower().endswith(".txt"):
                    continue
                chemin = os.path.join(dossier, f)
                cle = os.path.normcase(os.path.abspath(chemin))
                if cle in vus:
                    continue
                vus.add(cle)
                try:
                    if os.path.getsize(chemin) > taille_max:
                        continue
                    yield chemin, io.open(
                        chemin, encoding="utf-8",
                        errors="replace").read().split("\n")
                except Exception:
                    continue


def entete(lignes, i):
    """La derniere ligne AU-DESSUS qui n est pas une ligne de donnees.

    Une ligne de donnees porte des barres verticales ou un n= ; un
    en-tete de section n en porte pas. On remonte au plus 40 lignes."""
    for j in range(i - 1, max(-1, i - 41), -1):
        l = lignes[j].strip()
        if not l or set(l) <= set("-=_ "):
            continue
        if "|" in l or "n=" in l:
            continue
        return j, lignes[j]
    return None, None


def partie_texte(add, racines):
    add("=" * 96)
    add("LES QUATRE LIGNES DANS LES PANNEAUX TEXTE, AVEC LEUR EN-TETE")
    add("=" * 96)
    add("  On veut voir la MISE EN COLONNE que le parseur n a pas su")
    add("  lire, et le titre de la section qui la produit.")
    add("")
    vus = 0
    for chemin, lignes in fichiers_texte(racines):
        for i, l in enumerate(lignes):
            if not any(lib in l for lib in LIBELLES):
                continue
            j, tete = entete(lignes, i)
            add("  %s:%d" % (chemin, i + 1))
            if tete is not None:
                add("      section (ligne %d) : %s" % (j + 1, tete.strip()[:80]))
            for k in range(max(0, i - 2), min(len(lignes), i + 3)):
                add("      %s%s" % ("> " if k == i else "  ",
                                    lignes[k][:100]))
            add("")
            vus += 1
            if vus >= 20:
                add("  ... (arrete a 20)")
                return
    if not vus:
        add("  Aucun panneau texte ne porte ces libelles.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mot", action="append", default=None)
    p.add_argument("--panneau", default=None)
    a = p.parse_args()

    chemin = a.panneau
    if not chemin:
        try:
            import papers_repare as PR
            chemin = PR.trouve_panneau([".", "..", os.path.join("..", "..")])
        except Exception:
            for c in ("rails_trades_panel.py",
                      os.path.join("analyse", "rails_trades_panel.py")):
                if os.path.isfile(c):
                    chemin = c
                    break

    L = []
    add = L.append
    add("=" * 96)
    add("LES QUATRE LIGNES QUE MON PARSEUR N A PAS SU LIRE")
    add("=" * 96)
    add("")
    add("  Lecteur seul. Rien n est ecrit, aucun trade n est pris.")
    add("")
    add("  Les libelles de l export portaient deja ce que j ai deduit")
    add("  par balayage : '/ ALL' etait ecrit, et l etoile marquait")
    add("  l ancre M5. Ce qui suit ne deduit rien : ca lit.")
    add("")
    partie_source(add, chemin, tuple(a.mot) if a.mot else MOTS_SOURCE)
    partie_texte(add, ["panels", os.path.join("analyse", "cartes"),
                       "docs", "."])
    add("")
    add("=" * 96)
    add("  Ce script n a rien ecrit et n a pris aucun trade.")
    add("=" * 96)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
