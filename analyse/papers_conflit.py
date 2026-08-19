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

LES QUATRE LIGNES QUI RESISTENT

    Quatre lignes de l export portent un marqueur ecrit par MON
    parseur, papers_panel.py, et ce sont exactement les quatre qui ne
    se reproduisent pas :

      M1 bull RSI dedans / achat    n= 171   [col. non identifiee : 15]
      M15 bull RSI au-dessus/achat  n= 186   [col. non identifiee : 12]
      M15 CONFLIT vente             n= 358   [col. non identifiee : 15]
      M15 bull+                     n= 248   [col. non identifiee : 12]

CE QUE LA PREMIERE PASSE A APPRIS, ET OU JE M ETAIS TROMPE

    1. LE MARQUEUR NE VEUT PAS DIRE CE QUE JE CROYAIS.
       Sur la ligne, l effectif est EXACTEMENT a la meme place que sur
       toutes les autres :

         M15 CONFLIT vente   n= 358  52%  PnL +2019.33  ( 5.64/tr)  [...]
         M15 SPLIT / CLEAN   n= 243  57%  PnL +5033.59  (20.71/tr)

       "col. non identifiee" ne dit pas que 358 est mal lu : il dit que
       le parseur n a pas su de quelle COLONNE DE SESSION la ligne
       venait. J avais ecrit que 171, 186, 358 et 248 etaient suspects
       a la source. C est faux, les effectifs sont bons.

    2. LE FORMAT D ORIGINE A UN CHAMP DE PLUS.

         M15 | CONFLIT | vente | 384 | 16 | 51% | +1793.46 | ...

       Ce 16 varie de 8 a 16 selon les lignes et porte un avertissement
       quand il est bas : c est un nombre de JOURS couverts. Dix champs
       la ou les autres sections en ont neuf -- d ou l echec.

    3. JE N AI CHERCHE QUE DANS UN SEUL FICHIER.
       rails_trades_panel.py ne contient aucune section CONFLUENCE. Or
       panel_rails_trades.txt ET panel_orderflow.txt la portent, avec
       les memes chiffres. Elle est produite AILLEURS, et la premiere
       passe ne pouvait pas la voir.

CE QUE FAIT CETTE VERSION

    A. Elle balaye TOUS les modules du depot, pas un seul, et imprime
       en entier les fonctions qui portent CONFLUENCE, CONFLIT ou
       "bull+". Aucune paraphrase.

    B. Elle retrouve dans les PANNEAUX TEXTE la ligne d origine de
       chacune des quatre, avec son en-tete de section.

    Ce qui manque n est plus l effectif -- il est bon -- mais la
    DEFINITION de la section qui le produit. C est elle qu on cherche,
    et elle est dans un module.
"""
import argparse
import io
import os
import re
import sys

MOTS_SOURCE = ("CONFLUENCE", "CONFLIT", "bull+", "RSI dedans", "au-dessus")
# Les mots qui designent la section elle-meme, pas une legende qui la
# mentionne : c est sur eux qu on imprime la fonction en entier.
MOTS_FORTS = ("CONFLUENCE", "CONFLIT", "bull+")
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


def fichiers_python(racines, taille_max=4 * 1024 * 1024):
    """Tous les .py, chacun une fois, sauf les miens.

    La version precedente ne lisait QUE rails_trades_panel.py. La
    section CONFLUENCE n y est pas -- elle est ailleurs, et c est
    exactement ce que la premiere passe n a pas pu voir."""
    vus = set()
    for racine in racines:
        if not os.path.isdir(racine):
            continue
        for dossier, _sd, fichiers in os.walk(racine):
            if "__pycache__" in dossier:
                continue
            for f in sorted(fichiers):
                if not f.endswith(".py") or f.startswith("papers_"):
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


def partie_source(add, racines, mots, max_index=50, max_fonctions=3):
    add("=" * 96)
    add("OU CES MOTS APPARAISSENT -- dans TOUS les modules, pas un seul")
    add("=" * 96)
    add("  La passe precedente ne lisait que rails_trades_panel.py et")
    add("  n y a rien trouve. La section CONFLUENCE existe pourtant :")
    add("  panel_rails_trades.txt ET panel_orderflow.txt la portent.")
    add("  Elle est donc produite ailleurs.")
    add("")
    add("  %-34s %6s  %-26s %s" % ("fichier", "ligne", "fonction", "extrait"))
    add("  " + "-" * 94)
    index, forts, vus = 0, {}, 0
    for chemin, lignes in fichiers_python(racines):
        for i, l in enumerate(lignes):
            touches = [m for m in mots if m in l]
            if not touches:
                continue
            nom, debut = enclosante(lignes, i)
            if index < max_index:
                add("  %-34s %6d  %-26s %s"
                    % (os.path.basename(chemin)[:34], i + 1, nom[:26],
                       l.strip()[:30]))
            index += 1
            if debut is not None and any(m in l for m in MOTS_FORTS):
                cle = (chemin, nom)
                if cle not in forts:
                    forts[cle] = (debut, lignes)
            vus += 1
    if index > max_index:
        add("  ... %d occurrence(s) de plus" % (index - max_index))
    add("")
    if not vus:
        add("  Aucun de ces mots dans aucun module. La section vient")
        add("  d un fichier que ce balayage ne couvre pas.")
        return
    add("  %d occurrence(s), %d fonction(s) portant un mot FORT"
        % (vus, len(forts)))
    add("")
    for (chemin, nom), (debut, lignes) in list(forts.items())[:max_fonctions]:
        d, f = corps(lignes, debut)
        n = f - d
        add("-" * 96)
        add("  --- %s : %s  (ligne %d, %d lignes)"
            % (os.path.basename(chemin), nom, d + 1, n))
        add("-" * 96)
        for k in range(d, min(f, d + MAX_FONCTION)):
            add("  %5d  %s" % (k + 1, lignes[k][:104]))
        if n > MAX_FONCTION:
            add("  ... %d lignes de plus (rendu HTML)" % (n - MAX_FONCTION))
        add("")
    if len(forts) > max_fonctions:
        add("  %d autre(s) fonction(s) non imprimee(s) : %s"
            % (len(forts) - max_fonctions,
               ", ".join(n for _c, n in list(forts)[max_fonctions:])))
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
    p.add_argument("--panneau", default=None,
                   help="limiter le balayage a ce dossier")
    a = p.parse_args()

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
    racines = [a.panneau] if a.panneau else [".", "analyse"]
    partie_source(add, racines, tuple(a.mot) if a.mot else MOTS_SOURCE)
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
