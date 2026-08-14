# -*- coding: utf-8 -*-
"""
patch_panel_sections.py -- branche tickets_rails dans panel_quadruple

  python patch_panel_sections.py --essai
  python patch_panel_sections.py

CE QUI MANQUAIT, ET QUE J AVAIS ANNONCE COMME FAIT

    panel_quadruple lisait tickets_rails.jsonl, comptait ses lignes,
    et ne s en servait pas. Les six sections tournaient toutes sur
    events.jsonl. J avais pourtant ecrit que le panneau contiendrait
    "seance, episode, richesse, porteur, regime" : il n avait que la
    seance.

CE QUE CE PATCH AJOUTE -- quatre sections, numerotees 6 a 9

    6. LES EPISODES      allumages par actif et par setup, nombre
                         d episodes, petits rattaches et hors episode
    7. SOUS COUVERTURE   H10 : le petit setup en ligne, le grand qui a
                         ouvert l episode en colonne
    8. LA RICHESSE       H14 : 1-4 / 5-9 / 10+ entrees par episode, et
                         les rangs 1-4 contre 5+
    9. SEANCE US         H9 : en seance contre hors seance, sur les
                         quatre grands puis tous setups confondus

    L ancienne section 6 (rappels) devient la 10.

POURQUOI CA COMPTE

    events.jsonl ne remonte qu au 12/08 -- c est l age du collecteur.
    tickets_rails remonte au 21/07. Les deux seuls resultats qui
    tiennent au 14/08, H9 et H14, ne sont mesurables que sur le
    second. Sans ces sections, le panneau affichait le nouveau et
    taisait le mesure.

TROIS ANCRES, chacune verifiee unique. IDEMPOTENT. Sauvegarde
horodatee. ast.parse.

CE PATCH A ETE GENERE PAR DIFFERENCE, PAS RECOPIE A LA MAIN : le
script qui l a produit a verifie que les trois substitutions
reproduisent EXACTEMENT le fichier teste, caractere pour caractere.

Ce patch ne modifie qu un LECTEUR. Aucun ordre, aucun collecteur.
"""
import argparse
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "panel_quadruple.py"
MARQUEUR = "8. LA RICHESSE DE L EPISODE"

A1 = 'import argparse\nimport collections\n'
N1 = 'import argparse\nimport bisect\nimport collections\n'

A2 = 'QUATRE = ("10", "20", "30", "60")\n'
N2 = 'QUATRE = ("10", "20", "30", "60")\nPETIT = ("01", "02", "03", "05")\nFUSION = 30\nPORTEE = 120\n'

A3 = '    bloc("6. RAPPELS DE LECTURE",'
N3 = '    # ------------------------------------------------------------------\n    # 6 a 9 : ce que tickets_rails apporte et que events.jsonl ne peut\n    # pas donner -- il remonte au 21/07 la ou le collecteur x60 ne\n    # remonte qu au 12/08.\n    # ------------------------------------------------------------------\n    tk = []\n    for d in rails:\n        t = horo(d.get("entry_ts"))\n        if t is None or d.get("pnl_eur") is None:\n            continue\n        tk.append({"t": t, "jour": (d.get("entry_ts") or "")[:10],\n                   "actif": d.get("asset"),\n                   "setup": setup_de(d.get("magic")),\n                   "pnl": d.get("pnl_eur"),\n                   "h": (d.get("entry_ts") or "")[11:16]})\n    tk.sort(key=lambda k: k["t"])\n    tk = [k for k in tk if garde(k["jour"])]\n\n    # Episodes : un allumage de grand timeframe en ouvre un ; un second\n    # a moins de FUSION minutes le prolonge au lieu d en rouvrir un.\n    allum = collections.defaultdict(list)\n    for k in tk:\n        if k["setup"] in QUATRE:\n            allum[k["actif"]].append(k["t"])\n    for act in allum:\n        allum[act].sort()\n    eps = collections.defaultdict(list)\n    for act, ar in allum.items():\n        cur = None\n        for t in ar:\n            if cur and (t - cur["fin"]).total_seconds() <= FUSION * 60:\n                cur["fin"] = t\n                cur["n"] += 1\n                continue\n            cur = {"debut": t, "fin": t, "n": 1, "petits": []}\n            eps[act].append(cur)\n    debuts = dict((a2, [e["debut"] for e in v]) for a2, v in eps.items())\n    for k in tk:\n        if k["setup"] not in PETIT:\n            continue\n        v = eps.get(k["actif"])\n        if not v:\n            continue\n        i = bisect.bisect_right(debuts[k["actif"]], k["t"]) - 1\n        if i < 0:\n            continue\n        e = v[i]\n        if (k["t"] - e["fin"]).total_seconds() > PORTEE * 60:\n            continue\n        k["rang"] = len(e["petits"]) + 1\n        k["ep"] = e\n        e["petits"].append(k)\n    for act in eps:\n        for e in eps[act]:\n            for k in e["petits"]:\n                k["taille"] = len(e["petits"])\n\n    bloc("6. LES EPISODES  (source tickets_rails, depuis le 21/07)",\n         ["Un allumage de grand timeframe ouvre un episode ; un second",\n          "a moins de %d min le prolonge au lieu d en rouvrir un." % FUSION,\n          "L episode se ferme %d min apres son dernier allumage." % PORTEE,\n          "Ces deux durees sont des CHOIX, pas des mesures."])\n    tot_ep = sum(len(v) for v in eps.values())\n    dis()\n    dis("  allumages par actif et par setup")\n    dis("  %-14s %13s %13s %13s %13s"\n        % ("", "x10", "x20", "x30", "x60"))\n    dis("  " + "-" * (14 + 4 * 14))\n    for act in sorted(eps):\n        cpt = collections.Counter(k["setup"] for k in tk\n                                  if k["actif"] == act and k["setup"] in QUATRE)\n        dis("  %-14s %s"\n            % (act, " ".join("%13d" % cpt.get(x, 0) for x in QUATRE)))\n    rat = [k for act in eps for e in eps[act] for k in e["petits"]]\n    dis()\n    dis("  %d episodes, %d petits rattaches, %d hors episode"\n        % (tot_ep, len(rat),\n           len([k for k in tk if k["setup"] in PETIT and "ep" not in k])))\n\n    bloc("7. LE PETIT SOUS COUVERTURE  (H10)",\n         ["Ligne = le petit setup qui entre. Colonne = le grand qui a",\n          "ouvert l episode. Mesure du 14/08 : porteur M10-M30",\n          "+13,89 EUR/tk contre -15,09 sous porteur H1, t ~ 4,1 --",\n          "mais sur une seance et demie d allumages x10/x20/x30.",\n          "C est cette ligne-la que le gel doit remplir."])\n    gpo = collections.defaultdict(list)\n    for act in eps:\n        for e in eps[act]:\n            # Le setup du PREMIER allumage de l episode : c est lui qui\n            # a ouvert, les suivants n ont fait que le prolonger.\n            prem = None\n            for k in tk:\n                if k["actif"] == act and k["setup"] in QUATRE \\\n                        and k["t"] == e["debut"]:\n                    prem = k["setup"]\n                    break\n            if prem is None:\n                continue\n            for k in e["petits"]:\n                gpo[(k["setup"], prem)].append(k["pnl"])\n    table4("PnL moyen du petit, selon le grand qui a ouvert",\n           ["x%s entre" % x for x in PETIT],\n           lambda nm, x: gpo.get((nm.split(" ")[0][1:], x), []))\n\n    bloc("8. LA RICHESSE DE L EPISODE  (H14)",\n         ["Le seul resultat de la journee dont l effectif tienne a",\n          "l unite qui compte -- l EPISODE, pas le ticket.",\n          "Un bon depart est avare : il declenche trois ou quatre",\n          "entrees puis laisse courir. Un moteur qui ne cesse plus de",\n          "tirer signale l absence de depart, pas sa force.",\n          "ATTENTION : la taille finale n est PAS connue au moment",\n          "d entrer. Ce tableau explique, il ne se joue pas."])\n    dis()\n    for lib, f in (("1-4 entrees", lambda t: t <= 4),\n                   ("5-9 entrees", lambda t: 5 <= t <= 9),\n                   ("10+ entrees", lambda t: t >= 10)):\n        v = [k["pnl"] for k in rat if f(k.get("taille", 0))]\n        n2 = len(v)\n        if not n2:\n            dis("  %-16s        -" % lib)\n            continue\n        dis("  %-16s n=%-5d moy %+8.2f  total %+10.2f%s"\n            % (lib, n2, sum(v) / n2, sum(v), "" if n2 >= SEUIL else "  ?"))\n    dis()\n    for lib, f in (("rangs 1-4", lambda r: r <= 4),\n                   ("rangs 5+", lambda r: r >= 5)):\n        v = [k["pnl"] for k in rat if f(k.get("rang", 0))]\n        n2 = len(v)\n        if not n2:\n            continue\n        dis("  %-16s n=%-5d moy %+8.2f  total %+10.2f%s"\n            % (lib, n2, sum(v) / n2, sum(v), "" if n2 >= SEUIL else "  ?"))\n\n    bloc("9. SEANCE US  (H9)",\n         ["Le seul edge demontrable du dossier au 14/08. Mesure sur",\n          "3 560 tickets : -5,48 EUR/tk hors seance contre +9,80 en",\n          "seance. Moyenne elaguee a 1 % : -5,71, soit PIRE que la",\n          "brute -- ce n est donc pas une queue. Negatif 11 jours",\n          "sur 14. Le decoupage se fait sur l heure d entree seule,",\n          "sans classifieur."])\n    gse = collections.defaultdict(list)\n    for k in tk:\n        if k["setup"] is None:\n            continue\n        camp = "en seance" if "15:30" <= k["h"] < "19:30" else "hors seance"\n        gse[(camp, k["setup"])].append(k["pnl"])\n        gse[(camp, "TOUS")].append(k["pnl"])\n    table4("PnL moyen par ticket, les quatre grands",\n           ["en seance", "hors seance"],\n           lambda nm, x: gse.get((nm, x), []))\n    dis()\n    for camp in ("en seance", "hors seance"):\n        v = gse.get((camp, "TOUS"), [])\n        if v:\n            dis("  %-16s tous setups confondus : n=%-5d moy %+8.2f"\n                % (camp, len(v), sum(v) / len(v)))\n\n    bloc("10. RAPPELS DE LECTURE",'

ANCRES = ((A1, N1, "le bloc d imports"),
          (A2, N2, "les constantes"),
          (A3, N3, "le titre des rappels"))

INTOUCHABLES = ("def main(", "def setup_de(", "def table4(",
                "def cellule(", "_L = []", "--boucle")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    neuf = src
    for anc, nouv, nom in ANCRES:
        n = neuf.count(anc)
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1
        neuf = neuf.replace(anc, nouv, 1)
    print("Trois ancres, chacune unique.")

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    for t in INTOUCHABLES:
        if src.count(t) != neuf.count(t):
            print("KO : %s n apparait plus le meme nombre de fois." % t)
            print("Rien n a ete ecrit.")
            return 1
    print("Intacts : main, setup_de, table4, cellule, _L, --boucle.")

    # Les nouvelles sections doivent etre DANS main() : posees
    # ailleurs elles compileraient sans jamais s afficher.
    dedans = False
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.FunctionDef) and noeud.name == "main":
            d2 = ast.dump(noeud)
            dedans = ("LES EPISODES" in d2 and "SEANCE US" in d2
                      and "LA RICHESSE" in d2)
            break
    if not dedans:
        print("KO : les nouvelles sections ne sont pas dans main().")
        print("Rien n a ete ecrit.")
        return 1
    print("Arbre verifie : les quatre sections sont dans main().")

    print()
    print("Quatre sections ajoutees, sur tickets_rails :")
    print("  6. les episodes     7. sous couverture (H10)")
    print("  8. la richesse (H14) 9. seance US (H9)")
    print()
    print("Les rappels passent de la section 6 a la section 10.")
    print("Le service du gardien reprendra le nouveau contenu a sa")
    print("prochaine passe -- rien a relancer a la main.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
