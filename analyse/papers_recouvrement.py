#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
papers_recouvrement.py -- combien de filtres differents, vraiment ?

LECTEUR SEUL. N ECRIT RIEN.

  python papers_recouvrement.py
  python papers_recouvrement.py --seuil 0.7 --plafond 60

LA QUESTION

    Vingt-trois papers tournent. Mais si cinq d entre eux prennent les
    memes trades, il n y a pas cinq filtres : il y en a un, decrit de
    cinq facons. On croirait alors avoir cinq confirmations
    independantes alors qu on regarde la meme chose cinq fois.

    Le miroir en ligne aggrave le probleme : son plafond de miroirs
    simultanes serait consomme par des doublons.

CE QU IL MESURE

    Il rejoue les predicats du MOTEUR -- papers_moteur.papers() et
    accepte(), pas une reecriture -- sur les tickets deja journalises,
    dans la fenetre de session du moteur. Puis :

    1. combien de prises chacun a,
    2. le RECOUVREMENT deux a deux, dans les deux sens,
    3. les GROUPES de papers qui se ressemblent au-dela du seuil,
    4. les papers qui sont un SOUS-ENSEMBLE strict d un autre,
    5. combien de papers prennent le MEME ticket, et donc si le
       plafond du miroir va mordre,
    6. l APPORT PROPRE de chacun : les trades que lui seul prend.

DEUX MESURES, PAS UNE

    Jaccard  = communs / (union). Symetrique. Dit "ce sont les memes".
    Inclusion = communs / (prises de A). Asymetrique. Dit "A est
    contenu dans B" -- ce que Jaccard rate quand A est petit et B
    grand.

    Un paper rare entierement contenu dans un autre n apporte rien,
    meme si son Jaccard est faible.
"""

import argparse
import io
import json
import os
import sys

SEP = "=" * 104
SOURCE = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")


def lire_jsonl(chemin):
    out, ko = [], 0
    for c in (chemin, chemin + ".gz"):
        if not os.path.isfile(c):
            continue
        if c.endswith(".gz"):
            import gzip
            f = io.TextIOWrapper(gzip.open(c, "rb"), encoding="utf-8",
                                 errors="replace")
        else:
            f = io.open(c, encoding="utf-8", errors="replace")
        with f:
            for l in f:
                l = l.strip()
                if not l:
                    continue
                try:
                    o = json.loads(l)
                except ValueError:
                    ko += 1
                    continue
                if isinstance(o, dict):
                    out.append(o)
    return out, ko


def charge_moteur():
    """Importe le moteur, et DIT lequel.

    On prepend le dossier COURANT, pas celui du script : le moteur qui
    fait foi est celui qui est a cote des donnees, celui que la stack
    execute. Forcer le dossier du script a fait importer un autre
    papers_moteur.py pendant les essais, sans que rien ne le signale.
    """
    sys.path.insert(0, os.getcwd())
    try:
        import papers_moteur as pm
    except Exception as e:
        return None, "papers_moteur illisible : %s: %s" % (type(e).__name__, e)
    print("  moteur charge : %s" % getattr(pm, "__file__", "?"))
    mods = pm._charge_modules()
    if not isinstance(mods, (tuple, list)):
        mods = (mods,)
    pe = pr = None
    for m in mods:
        if pe is None and hasattr(m, "CLES"):
            pe = m
        if pr is None and hasattr(m, "REGLES"):
            pr = m
    if pe is None or pr is None:
        return None, "modules CLES / REGLES introuvables dans %r" % (mods,)
    return (pm, pm.papers(pe, pr)), None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default=SOURCE)
    p.add_argument("--seuil", type=float, default=0.80,
                   help="a partir de quelle inclusion deux papers sont "
                        "consideres comme le meme filtre")
    p.add_argument("--plafond", type=int, default=60,
                   help="plafond de miroirs simultanes, pour dire s il mord")
    p.add_argument("--tete", type=int, default=25)
    a = p.parse_args()

    print(SEP)
    print("RECOUVREMENT DES PAPERS -- combien de filtres differents ?")
    print(SEP)
    print()
    print("  Lecture seule. Rien n est ecrit, rien n est envoye.")
    print()

    if not (os.path.isfile(a.source) or os.path.isfile(a.source + ".gz")):
        print("  FICHIER INTROUVABLE : %s" % a.source)
        print("  Le chemin est RELATIF au dossier courant :")
        print("    %s" % os.getcwd())
        return

    charge, err = charge_moteur()
    if err:
        print("  %s" % err)
        return
    pm, jeu = charge
    fenetre = getattr(pm, "FENETRE", None)
    tickets, ko = lire_jsonl(a.source)
    if not tickets:
        print("  aucun ticket lisible.")
        return

    dedans = [t for t in tickets if pm.dans_fenetre(t)] if fenetre else tickets
    print("  %d paper(s), %d ticket(s) lus%s"
          % (len(jeu), len(tickets), ", %d illisibles" % ko if ko else ""))
    print("  fenetre %s : %d ticket(s) retenus"
          % (str(fenetre) if fenetre else "aucune", len(dedans)))
    print()

    prises = {}
    par_ticket = {}
    for t in dedans:
        ident = t.get("ticket")
        if ident is None:
            ident = "%s|%s|%s" % (t.get("entry_ts"), t.get("asset"),
                                  t.get("dir"))
        pris = []
        for e in jeu:
            try:
                if pm.accepte(e, t):
                    pris.append(e[0])
            except Exception:
                pass
        for m in pris:
            prises.setdefault(m, set()).add(ident)
        if pris:
            par_ticket[ident] = pris

    magics = sorted(prises, key=lambda m: -len(prises[m]))
    noms = dict((e[0], e[1]) for e in jeu)
    tous = set(e[0] for e in jeu)

    print(SEP)
    print("CE QUE CHACUN PREND")
    print(SEP)
    print()
    print("   magic    n     part    regle")
    print("   " + "-" * 76)
    for m in magics:
        n = len(prises[m])
        print("   %-8s %4d  %5.1f %%  %s"
              % (m, n, 100.0 * n / max(1, len(dedans)), noms.get(m, "")[:44]))
    muets = sorted(tous - set(magics))
    if muets:
        print()
        print("   n a rien pris : %s" % ", ".join(str(x) for x in muets))
    print()

    # ---------------------------------------------------------------- 2
    couples = []
    for i, A in enumerate(magics):
        for B in magics[i + 1:]:
            sa, sb = prises[A], prises[B]
            inter = len(sa & sb)
            if not inter:
                continue
            union = len(sa | sb)
            couples.append((inter / float(union), inter / float(len(sa)),
                            inter / float(len(sb)), A, B, inter,
                            len(sa), len(sb)))
    couples.sort(reverse=True)

    print(SEP)
    print("LES %d PLUS FORTS RECOUVREMENTS" % min(a.tete, len(couples)))
    print(SEP)
    print()
    print("   A        B         communs   Jaccard   A dans B   B dans A")
    print("   " + "-" * 74)
    for j, ia, ib, A, B, inter, na, nb in couples[:a.tete]:
        marque = ""
        if ia >= 0.999:
            marque = "   <-- %s est INCLUS dans %s" % (A, B)
        elif ib >= 0.999:
            marque = "   <-- %s est INCLUS dans %s" % (B, A)
        elif max(ia, ib) >= a.seuil:
            marque = "   <-- meme filtre"
        print("   %-8s %-8s %7d   %6.2f    %6.2f     %6.2f%s"
              % (A, B, inter, j, ia, ib, marque))
    print()

    # ---------------------------------------------------------------- 3
    print(SEP)
    print("GROUPES -- papers qui se ressemblent au-dela de %.0f %%"
          % (100 * a.seuil))
    print(SEP)
    print()
    voisins = dict((m, set()) for m in magics)
    for j, ia, ib, A, B, inter, na, nb in couples:
        if max(ia, ib) >= a.seuil:
            voisins[A].add(B)
            voisins[B].add(A)
    vus, groupes = set(), []
    for m in magics:
        if m in vus:
            continue
        pile, groupe = [m], []
        while pile:
            x = pile.pop()
            if x in vus:
                continue
            vus.add(x)
            groupe.append(x)
            pile.extend(voisins[x] - vus)
        groupes.append(sorted(groupe))
    seuls = [g[0] for g in groupes if len(g) == 1]
    vrais = [g for g in groupes if len(g) > 1]
    if not vrais:
        print("  aucun groupe : les %d papers sont distincts a ce seuil."
              % len(magics))
    for g in vrais:
        n_union = len(set().union(*[prises[m] for m in g]))
        print("  GROUPE de %d : %s" % (len(g), ", ".join(str(x) for x in g)))
        for m in g:
            print("      %-8s n=%4d  %s" % (m, len(prises[m]),
                                            noms.get(m, "")[:50]))
        print("      union %d trades -- soit %d filtre(s) reel(s) au lieu de %d"
              % (n_union, 1, len(g)))
        print()
    print("  %d paper(s) isole(s), %d groupe(s) de doublons."
          % (len(seuls), len(vrais)))
    print("  Filtres REELLEMENT distincts : %d sur %d."
          % (len(seuls) + len(vrais), len(magics)))
    print()

    # ---------------------------------------------------------------- 5
    print(SEP)
    print("COMBIEN DE PAPERS SUR LE MEME TICKET")
    print(SEP)
    print()
    combien = {}
    for ident, pris in par_ticket.items():
        combien[len(pris)] = combien.get(len(pris), 0) + 1
    for k in sorted(combien):
        barre = "#" * int(40.0 * combien[k] / max(combien.values()))
        print("   %2d paper(s)  %5d ticket(s)  %s" % (k, combien[k], barre))
    print()
    pire = max(combien) if combien else 0
    print("  Au pire, %d papers prennent le meme trade." % pire)
    print("  Le miroir enverrait donc %d ordres pour UNE entree du moteur."
          % pire)
    if pire:
        parents = a.plafond // pire
        print("  Avec un plafond de %d miroirs, il ne tiendrait que %d"
              % (a.plafond, parents))
        print("  parent(s) simultane(s) -- au-dela il refuse.")
        if parents < 5:
            print("  C est PEU : le moteur a eu 19 parents ouverts en meme")
            print("  temps hier. Le plafond mordra, et souvent.")
    print()

    # ---------------------------------------------------------------- 6
    print(SEP)
    print("APPORT PROPRE -- ce que chacun est SEUL a prendre")
    print(SEP)
    print()
    print("   magic    n     seul    part propre   regle")
    print("   " + "-" * 76)
    apports = []
    for m in magics:
        seul = sum(1 for ident in prises[m] if len(par_ticket[ident]) == 1)
        apports.append((seul / float(len(prises[m])), seul, m))
    for part, seul, m in sorted(apports, reverse=True):
        print("   %-8s %4d  %5d   %8.1f %%     %s"
              % (m, len(prises[m]), seul, 100 * part, noms.get(m, "")[:38]))
    print()
    zero = [m for part, seul, m in apports if seul == 0]
    if zero:
        print("  %d paper(s) ne prennent AUCUN trade que les autres ne"
              % len(zero))
        print("  prennent pas : %s" % ", ".join(str(x) for x in zero))
        print("  Ils n ajoutent aucune information. En ligne, ils")
        print("  consomment du plafond et de la marge pour rien.")
    print()
    print(SEP)
    print("  Rien n a ete ecrit, rien n a ete envoye.")
    print(SEP)


if __name__ == "__main__":
    main()
