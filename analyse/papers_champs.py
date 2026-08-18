# -*- coding: utf-8 -*-
r"""
papers_champs.py -- la carte des champs, repliee, sur un seul ecran

  python papers_champs.py

LECTEUR SEUL. N ECRIT RIEN.

POURQUOI UN TROISIEME LECTEUR

    papers_vocab2.py imprime la verite mais sur 200 lignes, parce qu il
    repete `rails_entry.US30.M1.rails_pos`, `rails_entry.US30.M3...`,
    `rails_entry.US500.M1...` -- trois actifs fois quatre unites, douze
    lignes pour UN champ. Chercher le T/S la-dedans demande de faire
    defiler, et une instruction qui demande de faire defiler est une
    mauvaise instruction.

    Celui-ci REPLIE : tout segment de chemin qui est un nom d actif
    devient <ACTIF>, tout segment qui est une unite de temps devient
    <TF>. Les douze lignes redeviennent une. Le resultat tient sur un
    ecran et se colle en entier.

CE QU IL CHERCHE EN PLUS

    Les deux dernieres inconnues pour encoder les 36 cles de l export :

      le T / S    de "M5 T / CLEAN" -- tendance contre scalp
      les pentes  de "M15 bull+", "M1 flat=", "M15 flat-"

    Il ne les devine pas : il imprime TOUS les champs a faible
    cardinalite avec leurs valeurs, et le T/S comme les pentes seront
    visibles ou ils sont. Un champ dont les valeurs sont exactement
    {T, S} ou {bull+, flat=, bear-} se reconnait sans commentaire.

VALEUR EXACTE, PAS SOUS-CHAINE

    La chasse de papers_vocab2 cherchait des SOUS-CHAINES : "WIDE"
    ressortait dans "WIDENING", ce qui a produit une fausse piste. Ici
    on ne cherche rien -- on liste les valeurs telles qu elles sont.
"""
import argparse
import io
import json
import os
import sys

CIBLE = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")

ACTIFS = ("US30", "US500", "US100", "USTEC", "GER40", "XAUUSD")
UNITES = ("M1", "M2", "M3", "M5", "M10", "M15", "M20", "M30",
          "H1", "H4", "D1", "W1")


def replie(seg):
    """Rend le segment generique, ou le segment tel quel."""
    if seg in ACTIFS:
        return "<ACTIF>"
    if seg in UNITES:
        return "<TF>"
    return seg


def feuilles(obj, prefixe, profond, sortie):
    if profond <= 0:
        return
    if isinstance(obj, dict):
        for k in obj:
            s = replie(str(k))
            che = (prefixe + "." + s) if prefixe else s
            feuilles(obj[k], che, profond - 1, sortie)
    elif isinstance(obj, list):
        for e in obj[:20]:
            feuilles(e, prefixe + "[]", profond - 1, sortie)
    else:
        sortie.append((prefixe, obj))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--profond", type=int, default=7)
    p.add_argument("--max", type=int, default=14,
                   help="au-dela de N valeurs, on ne les liste pas")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable." % a.fichier)
        return 1

    champs, n, ko = {}, 0, 0
    with io.open(a.fichier, encoding="utf-8", errors="replace") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                o = json.loads(ligne)
            except ValueError:
                ko += 1
                continue
            if not isinstance(o, dict):
                continue
            n += 1
            plat = []
            feuilles(o, "", a.profond, plat)
            for che, val in plat:
                d = champs.setdefault(che, {"txt": {}, "num": 0,
                                            "mini": None, "maxi": None})
                if val is None:
                    continue
                if isinstance(val, bool):
                    d["txt"][str(val)] = d["txt"].get(str(val), 0) + 1
                elif isinstance(val, (int, float)):
                    d["num"] += 1
                    v = float(val)
                    d["mini"] = v if d["mini"] is None else min(d["mini"], v)
                    d["maxi"] = v if d["maxi"] is None else max(d["maxi"], v)
                else:
                    s = str(val)
                    d["txt"][s] = d["txt"].get(s, 0) + 1

    L = []
    add = L.append
    add("=" * 76)
    add("CARTE DES CHAMPS -- repliee par <ACTIF> et <TF>")
    add("=" * 76)
    add("  %s : %d tickets%s"
        % (a.fichier, n, ", %d illisibles" % ko if ko else ""))
    add("  Valeurs exactes, pas de recherche par sous-chaine.")
    add("")

    textuels = [(k, d) for k, d in champs.items() if d["txt"]]
    nombres = [(k, d) for k, d in champs.items() if d["num"] and not d["txt"]]

    add("-" * 76)
    add("CHAMPS A VALEURS (ce sont eux qui portent les etats)")
    add("-" * 76)
    for k, d in sorted(textuels):
        vals = sorted(d["txt"].items(), key=lambda x: -x[1])
        if len(vals) <= a.max:
            bout = "  ".join("%s(%d)" % (x, y) for x, y in vals)
        else:
            bout = "%d valeurs -- non liste (horodatage ou identifiant)" % len(vals)
        add("  %-40s %s" % (k[:40], bout))
    add("")
    add("-" * 76)
    add("CHAMPS NUMERIQUES")
    add("-" * 76)
    for k, d in sorted(nombres):
        add("  %-40s min %.4g   max %.4g" % (k[:40], d["mini"], d["maxi"]))
    add("")
    add("  Ce qui est cherche ici : un champ dont les valeurs sont")
    add("  exactement {T, S} -- c est le T/S de \"M5 T / CLEAN\" -- et un")
    add("  champ de pentes du genre {bull+, bull=, flat+, flat=, flat-,")
    add("  bear=, bear-}. S ils ne sont nulle part, les dix cles qui en")
    add("  dependent ne sont pas encodables, et il faudra le dire.")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
