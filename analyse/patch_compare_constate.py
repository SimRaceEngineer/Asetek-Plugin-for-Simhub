# -*- coding: utf-8 -*-
r"""
patch_compare_constate.py -- CONSTATE se lit dans le journal

  python patch_compare_constate.py --essai
  python patch_compare_constate.py
  python patch_compare_constate.py --defaire

CE QU IL CORRIGE

    Le tableau de bord affirmait : "Les colonnes CONSTATE sont vides :
    AUCUN de ces magics n a pris un seul trade. Rien sur la machine ne
    lit ces definitions et ne place d ordre papier."

    C etait vrai le 18/08. C est faux depuis que papers_moteur.py
    tourne. Un panneau qui affirme une chose fausse est pire qu un
    panneau absent : on lui fait confiance.

    CONSTATE se lit donc dans docs\papers_live\trades.jsonl, et le jeu
    en ligne se lit dans le MOTEUR -- pas dans une liste recopiee ici
    qui divergerait au premier magic ajoute.

TROIS DISTINCTIONS QU IL TIENT

    'hors moteur' n est PAS zero. Zero veut dire que le filtre n a
    jamais accroche ; hors moteur veut dire que personne ne pose la
    question. Les confondre ferait passer une absence de mesure pour
    un resultat.

    RR '--' n est PAS zero non plus : c est l absence de perte, donc
    l absence de rapport gain/perte.

    Et le tableau des 36 ne couvre pas le moteur. La serie 240000 n a
    jamais figure dans l export ; les magics leader ne sont entrees qu
    apres. Le patch ajoute donc une SECONDE table -- ce qui a ete
    promis d un cote, ce qui tourne de l autre. Les fondre aurait cache
    laquelle repond de quoi.

CE QU IL NE FAIT PAS

    Il ne touche que papers_compare.py. Sauvegarde .bak, --defaire
    restaure. Aucun processus, aucun fichier d etat.
"""
import argparse
import io
import os
import shutil
import sys

CIBLE = "papers_compare.py"

CHANGEMENTS = [
 ('import argparse\nimport io\nimport os\nimport sys',
  'import argparse\nimport io\nimport json\nimport os\nimport sys',
  '1/5  import json'),

 ('def ligne_strategie(magic, nom, profil, cles, actif):',
  '# ======================================================================\n# CE QUI TOURNE VRAIMENT   (19/08/2026)\n# ======================================================================\n# Le tableau annoncait "AUCUN de ces magics n a pris un seul trade".\n# C etait vrai le 18/08 et c est faux depuis que papers_moteur.py\n# tourne. Un panneau qui affirme une chose fausse est pire qu un\n# panneau absent : on lui fait confiance.\n#\n# CONSTATE se lit donc dans le journal, et le jeu en ligne se lit dans\n# le moteur -- pas dans une liste recopiee ici qui divergerait au\n# premier magic ajoute.\nJOURNAL = os.path.join("docs", "papers_live", "trades.jsonl")\n\n\ndef charge_journal(chemin=JOURNAL):\n    """Rend {magic: [prises]}. Journal absent = dict vide, sans erreur."""\n    par = {}\n    if not os.path.isfile(chemin):\n        return par\n    with io.open(chemin, encoding="utf-8", errors="replace") as f:\n        for l in f:\n            l = l.strip()\n            if not l:\n                continue\n            try:\n                o = json.loads(l)\n            except ValueError:\n                continue\n            if isinstance(o, dict) and o.get("magic") is not None:\n                par.setdefault(o["magic"], []).append(o)\n    return par\n\n\ndef jeu_en_ligne():\n    """Rend {magic: nom} tel que le MOTEUR le definit, ou None.\n\n    On l importe au lieu de le recopier : une liste de magics tenue a\n    deux endroits diverge au premier ajout, et c est exactement ce qui\n    a produit les deux TIGHT_SPREAD et les deux plafonds jumeaux."""\n    try:\n        import papers_moteur as pm\n        pe, pr, manque = pm._charge_modules()\n        if manque:\n            return None\n        return dict((m, nom) for m, nom, _a, _s, _p in pm.papers(pe, pr))\n    except Exception:\n        return None\n\n\ndef mesure(prises):\n    """(n, pnl total, RR realise). RR None s il n y a aucune perte :\n    un rapport gain/perte sans perte n existe pas, il ne vaut pas zero."""\n    n = len(prises)\n    if not n:\n        return 0, 0.0, None\n    pnls = [x.get("pnl") or 0.0 for x in prises]\n    g = [v for v in pnls if v > 0]\n    pe_ = [-v for v in pnls if v < 0]\n    rr = ((sum(g) / len(g)) / (sum(pe_) / len(pe_))) if g and pe_ else None\n    return n, sum(pnls), rr\n\n\ndef ligne_strategie(magic, nom, profil, cles, actif):',
  '2/5  lecture du journal et du jeu en ligne'),

 ('    a("  Les colonnes CONSTATE sont vides : AUCUN de ces magics n a pris")\n    a("  un seul trade. Rien sur la machine ne lit ces definitions et ne")\n    a("  place d ordre papier. Tant que ce sera le cas, elles le")\n    a("  resteront -- quel que soit l affichage.")\n    a("")\n',
  '    par = charge_journal()\n    roster = jeu_en_ligne()\n    total = sum(len(v) for v in par.values())\n    if roster is None:\n        a("  MOTEUR ILLISIBLE : papers_moteur.py ou ses modules sont")\n        a("  absents. CONSTATE ne peut pas etre rempli, et l ignorer")\n        a("  aurait affiche des zeros pour une absence de mesure.")\n    elif not total:\n        a("  Les colonnes CONSTATE sont vides : le moteur tourne (%d"\n          % len(roster))\n        a("  papers en ligne) mais son journal est vide. Lance")\n        a("  papers_moteur.py.")\n    else:\n        a("  CONSTATE est LU DANS LE JOURNAL depuis le 19/08 : %d prises"\n          % total)\n        a("  sur %d papers en ligne. Ce panneau affirmait jusqu ici qu"\n          % len(roster))\n        a("  AUCUN magic n avait pris un trade -- c etait vrai le 18/08,")\n        a("  et faux depuis. Un panneau qui affirme une chose fausse est")\n        a("  pire qu un panneau absent : on lui fait confiance.")\n        a("")\n        a("  \'hors moteur\' n est PAS zero. Zero veut dire que le filtre")\n        a("  n a jamais accroche ; hors moteur veut dire que personne ne")\n        a("  pose la question. Les confondre ferait passer une absence")\n        a("  de mesure pour un resultat.")\n    a("")\n',
  '3/5  le preambule dit ce qui est, pas ce qui etait'),

 ('    for magic, jeu, act, tf, sens, cles in lignes:\n        n_max, n_tot, taux, pnl_tr = po.agrege(cles)\n        a("  %-7d %-3s %-8s %-10s %-11s | %5d %4.0f%% %4.0f%% %5.2f %7.2f "\n          "| %6s %8s %6s"\n          % (magic, jeu, act, tf[:10], sens[:11], n_max, 100 * taux,\n             100 * po.wilson_bas(taux, n_tot), po.rr_equilibre(taux),\n             pnl_tr, "--", "--", "--"))\n',
  '    for magic, jeu, act, tf, sens, cles in lignes:\n        n_max, n_tot, taux, pnl_tr = po.agrege(cles)\n        if roster is None:\n            c_n, c_pnl, c_rr = "?", "?", "?"\n        elif magic not in roster:\n            c_n, c_pnl, c_rr = "hors", "moteur", "--"\n        else:\n            n, pnl, rr = mesure(par.get(magic) or [])\n            c_n = "%d" % n\n            c_pnl = ("%+.0f" % pnl) if n else "0"\n            c_rr = ("%.2f" % rr) if rr is not None else "--"\n        a("  %-7d %-3s %-8s %-10s %-11s | %5d %4.0f%% %4.0f%% %5.2f %7.2f "\n          "| %6s %8s %6s"\n          % (magic, jeu, act, tf[:10], sens[:11], n_max, 100 * taux,\n             100 * po.wilson_bas(taux, n_tot), po.rr_equilibre(taux),\n             pnl_tr, c_n, c_pnl, c_rr))\n',
  '4/5  les trois colonnes CONSTATE se remplissent'),

 ('    a("  PnL/tr attendu depuis l export -- IN ECHANTILLON, jamais verifie.")\n    return L',
  '    a("  PnL/tr attendu depuis l export -- IN ECHANTILLON, jamais verifie.")\n    a("  TRADES/PnL/RR  CONSTATE, lu dans docs\\\\papers_live\\\\trades.jsonl.")\n\n    if roster:\n        dedans = set(m for m, _j, _a, _t, _s, _c in lignes)\n        restants = sorted(m for m in roster if m not in dedans)\n        a("")\n        a("=" * 132)\n        a("LE MOTEUR -- les %d papers en ligne, dont %d hors de ce tableau"\n          % (len(roster), len(restants)))\n        a("=" * 132)\n        a("  Le tableau ci-dessus est le registre de ce qui a ete PROMIS.")\n        a("  Le moteur, lui, fait tourner un autre ensemble : la serie")\n        a("  240000 n a jamais figure dans l export, et les magics leader")\n        a("  reparees le 19/08 ne sont entrees qu apres. Les deux listes")\n        a("  ne coincident pas, et les fondre en une seule aurait cache")\n        a("  laquelle repond de quoi.")\n        a("")\n        a("  %-7s %-30s %6s %10s %6s" % ("MAGIC", "NOM", "PRISES", "PnL",\n                                         "RR"))\n        a("  " + "-" * 64)\n        for m in sorted(roster):\n            n, pnl, rr = mesure(par.get(m) or [])\n            a("  %-7d %-30s %6d %+10.0f %6s"\n              % (m, roster[m][:30], n, pnl,\n                 ("%.2f" % rr) if rr is not None else "--"))\n        a("  " + "-" * 64)\n        a("  RR realise, pas attendu. \'--\' = aucune perte encore, donc")\n        a("  pas de rapport gain/perte : ce n est pas un zero.")\n    return L',
  '5/5  la table du moteur, a cote de celle des promesses'),

]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", action="append", default=None)
    p.add_argument("--essai", action="store_true")
    p.add_argument("--defaire", action="store_true")
    a = p.parse_args()

    che = None
    for r in (a.racine or ["."]):
        c = os.path.join(r, CIBLE)
        if os.path.isfile(c):
            che = c
            break
    if che is None:
        print("KO : %s introuvable." % CIBLE)
        return 1

    print("=" * 74)
    print("PATCH COMPARE -- CONSTATE se lit dans le journal")
    print("=" * 74)
    print("  cible : %s" % che)
    print()

    if a.defaire:
        bak = che + ".bak"
        if not os.path.isfile(bak):
            print("  Pas de sauvegarde : rien a restaurer.")
            return 1
        shutil.copyfile(bak, che)
        print("  restaure : %s <- %s" % (che, bak))
        return 0

    s = io.open(che, encoding="utf-8").read()
    absentes, deja = [], []
    for ancre, suite, desc in CHANGEMENTS:
        if suite in s:
            deja.append(desc)
        elif s.count(ancre) != 1:
            absentes.append((desc, s.count(ancre)))

    if deja:
        print("  DEJA APPLIQUE :")
        for d in deja:
            print("    %s" % d)
        print()
    if absentes:
        print("  ANCRE INTROUVABLE -- rien ne sera ecrit :")
        for d, n in absentes:
            print("    %s   (%d occurrence(s) au lieu de 1)" % (d, n))
        print()
        print("  papers_compare.py n est pas dans l etat attendu.")
        print("  Recopie papers_compare_v4.py, puis relance.")
        return 1
    if not deja:
        print("  Les %d ancres sont trouvees, une seule fois chacune."
              % len(CHANGEMENTS))
        print()

    for ancre, suite, desc in CHANGEMENTS:
        if suite in s:
            continue
        s = s.replace(ancre, suite, 1)
        print("  %s" % desc)
    print()

    if a.essai:
        print("  --essai : RIEN n a ete ecrit.")
        return 0

    bak = che + ".bak"
    if not os.path.isfile(bak):
        shutil.copyfile(che, bak)
        print("  sauvegarde : %s" % bak)
    io.open(che, "w", encoding="utf-8", newline="").write(s)
    print("  ecrit      : %s" % che)
    print()
    print("  Relance ensuite pour regenerer les cartes :")
    print("      python papers_compare.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
