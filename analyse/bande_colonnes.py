#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bande_colonnes.py -- TOUTES les colonnes, dedans contre dehors.

LECTEUR SEUL. N ECRIT RIEN.

  python bande_colonnes.py --bas 53596 --haut 53705
  python bande_colonnes.py --bas 53596 --haut 53705 --mini 30
  python bande_colonnes.py --inventaire        (liste les colonnes)

POURQUOI

    Un ticket porte plus de cent cinquante champs : churn_entry (6),
    hlc_churn_entry x 4 unites (15 chacune), rails_entry x 3 actifs
    x 4 unites (8 chacune), epoch_entry x 4 (11), ll_entry (6), plus
    les champs a plat. Les regles de la stack n en utilisent qu une
    poignee -- consensus, leader, laggard, self_mom, transition,
    rails_pos, rsi_pos.

    Conclure qu une zone n a rien de particulier en n ayant lu que
    ces sept-la, c est conclure sur ce qu on avait deja sous la main.

CE QUE FAIT CE SCRIPT

    Il parcourt CHAQUE champ terminal, compare sa distribution chez
    les trades entres DANS la bande et chez tous les autres, et
    classe les ecarts par ampleur.

    Champs textuels : ecart de proportion, valeur par valeur.
    Champs numeriques : ecart des medianes, rapporte a l ecart
    interquartile du dehors -- une mesure robuste, insensible aux
    valeurs extremes.

CE QU IL FAUT SAVOIR AVANT DE LIRE LA SORTIE

    Avec cent cinquante colonnes testees, certaines differeront PAR
    HASARD. C est mecanique. Le classement est donc donne par
    AMPLEUR et avec les effectifs, jamais comme une liste de
    decouvertes. Une colonne en tete de liste est une PISTE, pas un
    resultat -- il faudra la verifier sur une autre bande, ou sur
    une autre periode, avant d en faire quoi que ce soit.

    Et un ecart peut n etre qu un reflet du niveau de prix lui-meme :
    a 53600 le marche n etait pas dans le meme regime qu a 52000.
    Comparer une bande a TOUT le reste melange les epoques.
"""

import argparse
import gzip
import io
import json
import os
import sys

SEP = "=" * 100
DEFAUT = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")

# les champs que les regles utilisent deja -- pour les distinguer
DEJA_VUS = ("consensus", "leader", "laggard", "self_mom", "transition",
            "rails_pos", "rsi_pos", "verdict", "rails_setup")


def ouvre(c):
    if c.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(c, "rb"), encoding="utf-8",
                               errors="replace")
    return io.open(c, encoding="utf-8", errors="replace")


def lit(base, actif):
    out = []
    for c in (base, base + ".gz"):
        if not os.path.isfile(c):
            continue
        with ouvre(c) as f:
            for l in f:
                l = l.strip()
                if not l:
                    continue
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                if isinstance(o, dict) and (not actif or o.get("asset") == actif):
                    out.append(o)
    return out


def aplatis(rec, actif):
    """Tous les champs terminaux, en chemins pointes.

    Dans rails_entry, l actif du ticket devient SELF : c est ce que
    fait _moi() dans papers_regles, et sans ca chaque actif produirait
    ses propres colonnes, incomparables entre elles.
    """
    plat = {}

    def marche(prefixe, v):
        if isinstance(v, dict):
            for k, w in v.items():
                nk = k
                if prefixe == "rails_entry":
                    nk = "SELF" if k == actif else k
                marche("%s.%s" % (prefixe, nk) if prefixe else nk, w)
        elif isinstance(v, list):
            marche(prefixe + ".n", len(v))
        else:
            plat[prefixe] = v

    for k, v in rec.items():
        marche(k, v)
    return plat


def mediane(v):
    if not v:
        return None
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def quartiles(v):
    if len(v) < 4:
        return None, None
    v = sorted(v)
    return v[len(v) // 4], v[(3 * len(v)) // 4]


def nombre(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=DEFAUT)
    p.add_argument("--actif", default="US30")
    p.add_argument("--bas", type=float)
    p.add_argument("--haut", type=float)
    p.add_argument("--mini", type=int, default=20,
                   help="effectif minimum dans la bande pour qu un champ "
                        "soit juge")
    p.add_argument("--tete", type=int, default=25)
    p.add_argument("--inventaire", action="store_true")
    a = p.parse_args()

    print(SEP)
    print("TOUTES LES COLONNES -- DEDANS CONTRE DEHORS")
    print(SEP)
    print()
    print("  Lecture seule. Rien n est ecrit, rien n est envoye.")
    print()

    tickets = lit(a.fichier, a.actif)
    if not tickets:
        print("  aucun ticket %s dans %s" % (a.actif, a.fichier))
        return
    print("  %d ticket(s) %s" % (len(tickets), a.actif))

    plats = [aplatis(t, a.actif) for t in tickets]
    colonnes = {}
    for pl in plats:
        for k in pl:
            colonnes[k] = colonnes.get(k, 0) + 1
    print("  %d colonne(s) terminales distinctes" % len(colonnes))
    print()

    if a.inventaire or a.bas is None:
        print(SEP)
        print("INVENTAIRE")
        print(SEP)
        print()
        familles = {}
        for k in colonnes:
            familles.setdefault(k.split(".")[0], []).append(k)
        for fam in sorted(familles):
            noms = sorted(familles[fam])
            print("  %-20s %3d colonne(s)" % (fam, len(noms)))
            feuilles = sorted(set(n.split(".")[-1] for n in noms))
            utilisees = [f for f in feuilles if f in DEJA_VUS]
            jamais = [f for f in feuilles if f not in DEJA_VUS]
            if utilisees:
                print("      utilisees par les regles : %s"
                      % ", ".join(utilisees))
            if jamais:
                print("      JAMAIS LUES : %s" % ", ".join(jamais))
            print()
        if a.bas is None:
            print("  Donne --bas et --haut pour comparer une bande.")
            print()
            print(SEP)
            return

    bas, haut = min(a.bas, a.haut), max(a.bas, a.haut)
    dedans, dehors = [], []
    for t, pl in zip(tickets, plats):
        try:
            pr = float(t.get("entry_price"))
        except (TypeError, ValueError):
            continue
        (dedans if bas <= pr <= haut else dehors).append(pl)
    print(SEP)
    print("BANDE %.1f - %.1f" % (bas, haut))
    print(SEP)
    print()
    print("  dedans : %d ticket(s)   dehors : %d" % (len(dedans), len(dehors)))
    print()
    if len(dedans) < a.mini:
        print("  Moins de %d trades dans la bande : aucune comparaison"
              % a.mini)
        print("  ne serait credible. Elargis la bande ou baisse --mini,")
        print("  en sachant ce que tu perds.")
        return

    ecarts = []
    for col in sorted(colonnes):
        vd = [pl[col] for pl in dedans if col in pl and pl[col] is not None]
        vh = [pl[col] for pl in dehors if col in pl and pl[col] is not None]
        if len(vd) < a.mini or len(vh) < a.mini:
            continue
        if all(nombre(x) for x in vd) and all(nombre(x) for x in vh):
            md, mh = mediane(vd), mediane(vh)
            q1, q3 = quartiles(vh)
            if q1 is None or q3 is None or q3 == q1:
                continue
            taille = abs(md - mh) / float(q3 - q1)
            ecarts.append((taille, col, "nombre",
                           "median %.3g dedans contre %.3g dehors "
                           "(ecart = %.2f interquartile)" % (md, mh, taille),
                           len(vd)))
        else:
            valeurs = set(str(x) for x in vd) | set(str(x) for x in vh)
            if len(valeurs) > 30:
                continue
            pire = (0.0, None, 0.0, 0.0)
            for val in valeurs:
                pd = sum(1 for x in vd if str(x) == val) / float(len(vd))
                ph = sum(1 for x in vh if str(x) == val) / float(len(vh))
                if abs(pd - ph) > pire[0]:
                    pire = (abs(pd - ph), val, pd, ph)
            if pire[1] is None:
                continue
            ecarts.append((pire[0], col, "texte",
                           "%s : %.0f %% dedans contre %.0f %% dehors"
                           % (pire[1], 100 * pire[2], 100 * pire[3]),
                           len(vd)))

    if not ecarts:
        print("  aucune colonne ne reunit assez d observations des deux")
        print("  cotes pour etre comparee.")
        return

    ecarts.sort(reverse=True)
    print(SEP)
    print("LES %d PLUS GROS ECARTS" % min(a.tete, len(ecarts)))
    print(SEP)
    print()
    for taille, col, genre, texte, n in ecarts[:a.tete]:
        feuille = col.split(".")[-1]
        neuf = "" if feuille in DEJA_VUS else "  [jamais lue]"
        print("  %-46s n=%4d%s" % (col, n, neuf))
        print("      %s" % texte)
    print()

    print(SEP)
    print("COMMENT LIRE CE CLASSEMENT")
    print(SEP)
    print()
    print("  %d colonnes ont ete comparees. Avec autant de tests,"
          % len(ecarts))
    print("  certaines differeront par HASARD -- c est mecanique, pas")
    print("  discutable. Ce classement donne des PISTES, pas des")
    print("  resultats.")
    print()
    print("  Une piste ne devient un fait qu apres avoir tenu sur une")
    print("  AUTRE bande, ou une AUTRE periode, choisie avant de")
    print("  regarder. Sinon on decrit le bruit de cet echantillon.")
    print()
    print("  Et un ecart peut n etre que le reflet du niveau de prix :")
    print("  a %.0f le marche n etait pas dans le meme regime qu a" % bas)
    print("  d autres moments. Comparer une bande a TOUT le reste")
    print("  melange les epoques -- c est la limite de cette mesure.")
    print()
    print(SEP)
    print("  Rien n a ete ecrit, rien n a ete envoye.")
    print(SEP)


if __name__ == "__main__":
    main()
