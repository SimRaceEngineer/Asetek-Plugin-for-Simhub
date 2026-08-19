# -*- coding: utf-8 -*-
r"""
papers_decisions.py -- combien de DECISIONS derriere les prises, et
                       quels papers se recoupent

  python papers_decisions.py

LECTEUR SEUL. N ECRIT RIEN, NE PREND AUCUN TRADE. AUCUN GATE INSTALLE.

POURQUOI CE SCRIPT PASSE AVANT LE GATE

    Le panneau donne 230207 a n=70, borne de Wilson 63 %. Mais
    _signals (panneau:694) regroupe les bras 206 et 207 : deux
    executions d un MEME signal, a la meme seconde, sur le meme actif
    et le meme sens. Le journal papier, lui, compte les deux.

    Si 70 prises sont 35 decisions, la borne tombe vers 55 %, le RR
    exige a la borne monte de 0,59 a 0,82, et le dossier change. Une
    borne de Wilson calculee sur des tirages non independants n est pas
    prudente, elle est fausse dans le sens qui arrange.

    Je ne construis pas un gate reel sur un effectif que je sais gonfle.

CE QUE FAIT CE SCRIPT

    1. Il rejoint le journal papier aux tickets pour retrouver le MAGIC
       CHURN de chaque prise, puis applique la regle du panneau, telle
       qu elle est ecrite :

         famille = magic // 1000
         si famille dans (206, 207) : cle = (actif, sens, magic % 1000,
                                             tranche de 30 s)
         sinon                      : cle = le ticket

       et recalcule WR, RR et Wilson au niveau DECISION.

    2. Il mesure le RECOUVREMENT entre papers -- l objection de
       DeepSeek : 230207, 230201 et 220014 sont-ils trois confirmations
       ou trois lectures du meme echantillon ? Un chevauchement se
       compte, il ne se discute pas.

    3. Il compare les candidats au TEMOIN. 220014 n a aucune regle :
       son predicat est `lambda t: True`, filtre seulement par actif et
       sens (papers_moteur.SANS_PREUVE). C est donc "long US500 a
       chaque entree", c est-a-dire la derive du marche. Tout ce qu un
       filtre apporte se mesure PAR RAPPORT A LUI, pas dans l absolu.

    4. Il imprime le predicat exact du gate envisage -- sans l ecrire.

CE QU IL N EST PAS

    Il n installe rien, ne touche aucun processus, n ecrit aucun
    fichier. Le gate reste une proposition sur l ecran tant que les
    chiffres de la partie 1 ne l ont pas justifie.
"""
import argparse
import calendar
import sys

CANDIDATS = [230207, 230201, 230205, 230210, 220014, 220004]
TEMOINS = {220014: "US500 achat", 220004: "US30 vente"}


def _epoch(ts):
    try:
        return calendar.timegm((int(ts[0:4]), int(ts[5:7]), int(ts[8:10]),
                                int(ts[11:13]), int(ts[14:16]),
                                int(ts[17:19]), 0, 1, 0))
    except (ValueError, IndexError, TypeError):
        return 0


def decisions(prises, info):
    """{cle de decision: [pnl]}. Regle de _signals, panneau:694."""
    out = {}
    for p in prises:
        t = info.get(p.get("ticket"))
        mag = (t or {}).get("magic")
        try:
            fam = int(mag or 0) // 1000
        except (TypeError, ValueError):
            fam = 0
        if fam in (206, 207):
            cle = (p.get("actif"), p.get("sens"), int(mag) % 1000,
                   _epoch(p.get("ts") or "") // 30)
        else:
            cle = ("SOLO", p.get("ticket"))
        out.setdefault(cle, []).append(p.get("pnl") or 0.0)
    return out


def mesure(valeurs, PM):
    """WR, RR et Wilson sur une liste de resultats par decision."""
    n = len(valeurs)
    if not n:
        return None
    gains = [x for x in valeurs if x > 0]
    pertes = [-x for x in valeurs if x < 0]
    p = len(gains) / float(n)
    wil = PM.wilson_bas(p, n)
    return {
        "n": n, "wr": 100.0 * p, "tot": sum(valeurs),
        "moy": sum(valeurs) / n,
        "rr": ((sum(gains) / len(gains)) / (sum(pertes) / len(pertes)))
              if gains and pertes else None,
        "wilson": 100.0 * wil,
        # le RR qu il faut atteindre pour gagner AU PIRE taux defendable
        "exige": ((1.0 - wil) / wil) if wil > 0 else float("inf")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--journal", default=None)
    p.add_argument("--rails", default=None)
    a = p.parse_args()

    try:
        import papers_moteur as PM
        import papers_population as PP
    except ImportError as e:
        print("KO : papers_moteur.py et papers_population.py requis. (%s)" % e)
        return 1

    journal, ko_j = PM.lire_jsonl(a.journal or PM.JOURNAL)
    tickets, ko_t = PP.lire(a.rails or PP.RAILS)
    info = dict((t.get("ticket"), t) for t in tickets
                if t.get("ticket") is not None)

    L = []
    add = L.append
    add("=" * 100)
    add("DES PRISES AUX DECISIONS -- et qui se recoupe avec qui")
    add("=" * 100)
    add("")
    add("  Lecteur seul. Rien n est ecrit, aucun gate n est installe.")
    add("")
    add("  journal : %d prises (%d illisibles)" % (len(journal), ko_j))
    add("  tickets : %d (%d illisibles)" % (len(tickets), ko_t))
    if not journal:
        add("")
        add("  Journal vide. Lance papers_moteur.py d abord.")
        print("\n".join(L))
        return 1

    par = {}
    for e in journal:
        par.setdefault(e.get("magic"), []).append(e)

    # --- combien de prises retrouvent leur ticket ? -------------------
    total = sum(len(v) for v in par.values())
    joints = sum(1 for e in journal if e.get("ticket") in info)
    add("  jointure : %d prises sur %d retrouvent leur ticket"
        % (joints, total))
    if joints < total:
        add("  Les prises non jointes comptent chacune pour une decision")
        add("  -- faute de magic churn, on ne peut pas les regrouper. Ca")
        add("  SURESTIME le nombre de decisions, donc ca ne flatte rien.")
    add("")

    add("=" * 100)
    add("CHAQUE PAPER, AU NIVEAU DECISION")
    add("=" * 100)
    add("  %-7s %-26s %6s %6s %5s %6s %7s %6s %7s  %s"
        % ("MAGIC", "PAPER", "prises", "decis", "x", "WR", "WILSON",
           "RR", "exige", "verdict"))
    add("  " + "-" * 98)
    stats = {}
    for magic in sorted(par, key=lambda m: -len(par[m])):
        prises = par[magic]
        d = decisions(prises, info)
        vals = [sum(v) / len(v) for v in d.values()]   # _signals : moyenne
        m = mesure(vals, PM)
        if not m:
            continue
        stats[magic] = m
        rr = m["rr"]
        if rr is None:
            verdict = "aucune perte -- indecidable"
        elif rr > m["exige"]:
            verdict = "TIENT a la borne"
        else:
            verdict = "ne tient PAS a la borne"
        add("  %-7s %-26s %6d %6d %5.2f %5.0f%% %6.0f%% %6s %7.2f  %s"
            % (magic, (prises[0].get("nom") or "")[:26], len(prises),
               m["n"], len(prises) / float(m["n"]), m["wr"], m["wilson"],
               ("%.2f" % rr) if rr else "--", m["exige"], verdict))
    add("")
    add("  x        prises par decision. 2,00 = chaque signal compte")
    add("           deux fois (les deux bras 206/207).")
    add("  exige    le RR qu il faut atteindre pour gagner AU PIRE taux")
    add("           encore defendable a 95 %. C est le seul seuil qui ne")
    add("           se sur-ajuste pas.")
    add("")

    # --- le recoupement ----------------------------------------------
    add("=" * 100)
    add("RECOUVREMENT -- trois confirmations, ou trois lectures du meme")
    add("echantillon ? (objection DeepSeek, 19/08)")
    add("=" * 100)
    presents = [m for m in CANDIDATS if m in par]
    jeux = dict((m, set(e.get("ticket") for e in par[m]
                        if e.get("ticket") is not None)) for m in presents)
    add("  %-8s %s" % ("", "  ".join("%7d" % m for m in presents)))
    for m in presents:
        cells = []
        for n in presents:
            if m == n:
                cells.append("      -")
                continue
            inter = len(jeux[m] & jeux[n])
            part = 100.0 * inter / max(1, len(jeux[m]))
            cells.append("%6.0f%%" % part)
        add("  %-8d %s   (%d tickets)"
            % (m, "  ".join(cells), len(jeux[m])))
    add("")
    add("  Lecture : la case (ligne, colonne) donne la part des tickets")
    add("  de la LIGNE qui sont aussi pris par la COLONNE. La matrice")
    add("  n est pas symetrique -- un petit paper peut etre inclus a")
    add("  100 % dans un gros sans que l inverse soit vrai.")
    add("")

    # --- contre le temoin --------------------------------------------
    add("=" * 100)
    add("CONTRE LE TEMOIN -- ce qu un filtre ajoute a la derive")
    add("=" * 100)
    add("  220014 et 220004 n ont AUCUNE regle : leur predicat est")
    add("  `lambda t: True` (papers_moteur.SANS_PREUVE), filtre seulement")
    add("  par actif et par sens. 220014 est donc 'long US500 a chaque")
    add("  entree du churn' -- la derive du marche, pas un filtre.")
    add("")
    for tem, quoi in sorted(TEMOINS.items()):
        if tem not in stats:
            continue
        base = stats[tem]["moy"]
        add("  temoin %d (%s) : %+.2f par decision, %d decisions"
            % (tem, quoi, base, stats[tem]["n"]))
        for magic in presents:
            if magic in TEMOINS or magic not in stats:
                continue
            # meme actif que le temoin, sinon la comparaison n a pas
            # d objet : un paper "tous actifs" ne se juge pas contre un
            # temoin US500.
            if (par[magic][0].get("actif") or "") != quoi.split()[0]:
                continue
            m = stats[magic]
            rap = (m["moy"] / base) if base else None
            add("    %-7d %-24s %+8.2f/decision   %s"
                % (magic, (par[magic][0].get("nom") or "")[:24], m["moy"],
                   ("x%.1f" % rap) if rap and rap > 0
                   else "signe oppose au temoin"))
        add("")

    # --- le gate envisage, imprime et NON ecrit ----------------------
    add("=" * 100)
    add("LE GATE ENVISAGE -- imprime, PAS installe")
    add("=" * 100)
    add("  230207 = US HLC SPLIT CONFLUENCE, actif US500, cle M15_SPL_CL")
    add("  (papers_moteur.SEPT). Son predicat, tel qu il tourne :")
    add("")
    add("      hlc(t, 'M15', 'consensus') == 'SPLIT'")
    add("      and ver(t) == 'clean'")
    add("      and t['asset'] == 'US500'")
    add("")
    add("  Ce script n ecrit rien. Le gate ne sera propose que si la")
    add("  ligne 230207 ci-dessus tient A LA BORNE, au niveau DECISION,")
    add("  et si son recoupement avec 230201 laisse deux mesures")
    add("  distinctes plutot qu une repetee.")
    add("")
    add("=" * 100)
    add("  Ce script n a rien ecrit, n a installe aucun gate, et n a")
    add("  pris aucun trade.")
    add("=" * 100)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
