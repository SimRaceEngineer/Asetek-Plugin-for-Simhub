# -*- coding: utf-8 -*-
r"""
pine_reperes.py -- un indicateur Pine qui trace les bougies reperes sur
                   TradingView

  python pine_reperes.py --symbole MES-continu
  python pine_reperes.py --symbole YM-continu --depuis 2026-07-01
  python pine_reperes.py --symbole MES-continu --dims VITESSE+ --max 150

CE QU IL PRODUIT

    Un fichier `.pine` a coller dans l editeur Pine de TradingView
    (Pine Editor -> tout remplacer -> Add to chart). Il trace, sur
    CHAQUE bougie repere :

      - un trait VERTICAL sur la bougie, pour la reperer ;
      - deux rayons HORIZONTAUX prolonges a droite, partant de son
        plus haut et de son plus bas -- les niveaux qu elle laisse ;
      - une etiquette avec les dimensions franchies et leurs valeurs.

POURQUOI IL NE TRACE AUCUN PRIX DE CHEZ NOUS

    Le 14/08, `MES-continu` cotait 7826 quand le US500 d IC Markets
    etait a 7757 : soixante-dix points d ecart. Ce sont deux
    instruments differents -- un future CME et un CFD.

    Le script n exporte donc QUE DES INSTANTS. Les niveaux sont lus par
    TradingView sur SA propre serie, a la bougie qui contient l instant.
    C est ce qui les rend justes sur n importe quel courtier, et c est
    aussi ce qui fait que le meme fichier marche sur un graphique 1
    minute comme sur un 15 minutes : la bougie qui CONTIENT l instant
    est celle qui est marquee.

    Corollaire a ne pas oublier : un fichier genere pour `MES-continu`
    n a de sens que sur un graphique de S&P 500. Colle sur un Dow, il
    marquera les bonnes heures du mauvais actif. Le symbole vise est
    ecrit dans le titre de l indicateur.

LES HEURES SONT EN UTC, DECLAREES

    `timestamp("UTC", ...)` -- pas d ambiguite possible, quel que soit
    le fuseau du graphique. Les `.scid` sont en UTC ; on ne convertit
    rien, on declare.

LES BORNES DE TRADINGVIEW, ET CE QU ON JETTE

    Pine plafonne a 500 lignes et 500 etiquettes par indicateur. Chaque
    repere coute 3 lignes et 1 etiquette : le plafond REEL est donc de
    166 reperes. `--max` vaut 150 par defaut.

    CE QUI EST JETE EST DIT. Le script affiche combien de reperes il a
    trouves, combien il en garde, et sur quel critere -- jamais une
    troncature muette. Une limite d affichage n est pas un resultat.

    Pour en voir davantage : restreindre avec `--depuis`, ou filtrer
    sur une dimension avec `--dims`.

IL NE REDEFINIT RIEN

    Il IMPORTE `bougies_reperes` et appelle ses fonctions. La
    definition d une bougie repere reste a UN SEUL ENDROIT : si elle
    change la, elle change ici. Deux definitions jumelles finissent
    toujours par diverger en silence -- c est la faute du 14/08 sur
    COUNCIL_MAX_TOKENS, qui a coute une soiree.

CE QU IL NE DIT PAS

    Rien sur ce qui va se passer. Un rayon sur un plus haut de bougie
    repere est un NIVEAU, pas une prevision. Savoir si le prix y
    revient plus souvent que sur un niveau ordinaire demande un temoin
    apparie -- une mesure separee, qui n est pas ici.

LECTEUR SEUL. N ecrit que dans `cartes\`.
"""
import argparse
import io
import os
import sys
from datetime import datetime

import bougies_reperes as br

SORTIE = "cartes"
# 500 lignes / 3 par repere, 500 etiquettes / 1 par repere.
PLAFOND_PINE = 166


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dossier", default=br.DOSSIER)
    p.add_argument("--symbole", default="MES-continu")
    p.add_argument("--centile", type=float, default=99.5)
    p.add_argument("--depuis", default=None, help="AAAA-MM-JJ")
    p.add_argument("--jusqua", default=None, help="AAAA-MM-JJ")
    p.add_argument("--dims", default=None,
                   help="ne garder que les reperes portant CES "
                        "dimensions, ex : VITESSE+,PRESSION+")
    p.add_argument("--max", type=int, default=150)
    a = p.parse_args()

    print("=" * 78)
    print("PINE -- les bougies reperes sur TradingView")
    print("=" * 78)
    print("  AUCUN PRIX DE CHEZ NOUS N EST EXPORTE. Le 14/08, MES cotait")
    print("  7826 quand le US500 d IC Markets etait a 7757 : un future et")
    print("  un CFD ne partagent pas leur echelle. Seuls les INSTANTS")
    print("  partent ; TradingView lit ses propres niveaux dessus.")
    print()

    barres, msg = br.charge(a.dossier)
    for m in msg:
        print(m)
    for sym, r in br.sans_carnet(barres):
        print("  %-16s ECARTE : %s" % (sym, r))
    if a.symbole not in barres:
        print()
        print("KO : symbole %s absent. Disponibles : %s"
              % (a.symbole, ", ".join(sorted(barres)) or "aucun"))
        return 1

    serie = barres[a.symbole]
    jours = {}
    for b in serie:
        jours.setdefault(b["t"].date(), []).append(b)
    cpt = sorted(len(v) for v in jours.values())
    seuil_j = max(30, (cpt[len(cpt) // 2] if cpt else 0) // 2)
    mtr = [br.med([b["n"] for b in v]) or 0.0 for v in jours.values()]
    seuil_tr = (br.med(mtr) or 0.0) / 2.0

    # TROIS compteurs, pas deux. La premiere version affichait
    # `len(jours) - mortes` et annoncait 174 seances la ou
    # bougies_reperes.py en comptait 107 sur les memes donnees : elle
    # oubliait les seances rejetees par la densite de barres -- les
    # reouvertures fantomes du dimanche soir. Deux outils qui ne
    # comptent pas les memes seances pour le meme symbole, c est la
    # faute du 17/08, et elle ne s est vue que parce que l autre outil
    # affiche son propre compte.
    reperes, mortes, minces, retenues = [], 0, 0, 0
    for jour in sorted(jours):
        j = jours[jour]
        if len(j) < seuil_j:
            minces += 1
            continue
        if (br.med([b["n"] for b in j]) or 0.0) < seuil_tr:
            mortes += 1
            continue
        retenues += 1
        br.dimensions(j)
        res = br.bornes(j, a.centile)
        haut, bas = res[0], res[1]
        for b in j:
            q = []
            for d in br.DIMS:
                if haut[d] is not None and b[d] >= haut[d]:
                    q.append(d + "+")
                elif bas[d] is not None and b[d] <= bas[d]:
                    q.append(d + "-")
            if q:
                b["quoi"] = q
                reperes.append(b)

    print("  %-16s %d seance(s) retenue(s) sur %d dates"
          % (a.symbole, retenues, len(jours)))
    print("  %-16s %d ecartee(s) sans activite reelle, %d trop peu de "
          "barres" % ("", mortes, minces))
    print("  %-16s %d bougie(s) repere(s) au centile %.1f"
          % ("", len(reperes), a.centile))

    # --- les filtres, et ce qu ils retirent -------------------------
    n0 = len(reperes)
    if a.depuis:
        d0 = datetime.strptime(a.depuis, "%Y-%m-%d").date()
        reperes = [b for b in reperes if b["t"].date() >= d0]
        print("  --depuis %s   : %d -> %d" % (a.depuis, n0, len(reperes)))
        n0 = len(reperes)
    if a.jusqua:
        d1 = datetime.strptime(a.jusqua, "%Y-%m-%d").date()
        reperes = [b for b in reperes if b["t"].date() <= d1]
        print("  --jusqua %s   : %d -> %d" % (a.jusqua, n0, len(reperes)))
        n0 = len(reperes)
    if a.dims:
        veut = set(x.strip().upper() for x in a.dims.split(",") if x.strip())
        reperes = [b for b in reperes if veut & set(b["quoi"])]
        print("  --dims %-8s : %d -> %d" % (a.dims, n0, len(reperes)))

    # --- le plafond, ANNONCE ----------------------------------------
    plafond = min(a.max, PLAFOND_PINE)
    trop = len(reperes) - plafond
    if trop > 0:
        # On garde les plus marquees : d abord le nombre de dimensions
        # franchies, puis la vitesse.
        reperes.sort(key=lambda b: (-len(b["quoi"]), -b["VITESSE"]))
        reperes = reperes[:plafond]
        print()
        print("  PLAFOND : %d repere(s) NON traces." % trop)
        print("  Pine plafonne a 500 lignes et 500 etiquettes ; chaque")
        print("  repere en coute 3 et 1, donc 166 au maximum.")
        print("  Les %d gardes sont les plus marques -- d abord par le" % plafond)
        print("  nombre de dimensions franchies, puis par la vitesse.")
        print("  Pour voir les autres : --depuis, --jusqua ou --dims.")
    reperes.sort(key=lambda b: b["t"])

    if not reperes:
        print()
        print("Aucun repere apres filtrage. Rien n a ete ecrit.")
        return 1

    # --- le Pine ----------------------------------------------------
    tabl = "\n".join(
        '    T.push(timestamp("UTC", %d, %d, %d, %d, %d))\n'
        '    N.push(%d)\n'
        '    D.push("%s")'
        % (b["t"].year, b["t"].month, b["t"].day, b["t"].hour,
           b["t"].minute, len(b["quoi"]),
           " ".join(x[:4] + x[-1] for x in b["quoi"]))
        for b in reperes)

    pine = PINE % {
        "sym": a.symbole,
        "n": len(reperes),
        "cent": a.centile,
        "gen": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "d1": str(reperes[0]["t"].date()),
        "d2": str(reperes[-1]["t"].date()),
        "table": tabl,
    }

    if not os.path.isdir(SORTIE):
        os.makedirs(SORTIE)
    nom = "reperes_%s.pine" % a.symbole.replace("-", "_")
    che = os.path.join(SORTIE, nom)
    io.open(che, "w", encoding="utf-8").write(pine)

    print()
    print("  ecrit : %s (%d octets, %d reperes)"
          % (che, len(pine.encode("utf-8")), len(reperes)))
    print("  periode : %s -> %s" % (reperes[0]["t"].date(),
                                    reperes[-1]["t"].date()))
    print()
    print("A FAIRE DANS TRADINGVIEW :")
    print("  1. ouvrir un graphique de %s"
          % ("S&P 500 (US500, ES, SPX)" if a.symbole.startswith("MES")
             else "Dow Jones (US30, YM)"))
    print("  2. Pine Editor -> tout remplacer par le contenu du fichier")
    print("  3. Add to chart")
    print()
    print("  Le fichier ne contient QUE des instants UTC. Les niveaux")
    print("  sont ceux de VOTRE serie, lus a la bougie qui contient")
    print("  l instant -- justes sur n importe quel courtier, et sur")
    print("  n importe quelle unite de temps.")
    print()
    print("  Un fichier %s colle sur un graphique de Dow marquerait les"
          % a.symbole)
    print("  bonnes heures du mauvais actif. Le symbole vise est dans le")
    print("  titre de l indicateur.")
    return 0


PINE = '''// =====================================================================
// Bougies reperes -- %(sym)s
//
// Genere le %(gen)s par pine_reperes.py
// %(n)d bougie(s) repere(s), centile %(cent).1f, du %(d1)s au %(d2)s
//
// CE FICHIER NE CONTIENT AUCUN PRIX. Seulement des INSTANTS en UTC.
// Les niveaux traces sont ceux de CE graphique, lus sur la bougie qui
// contient l instant -- un future CME et un CFD ne partagent pas leur
// echelle, et melanger les deux tracerait des niveaux faux.
//
// A COLLER SUR UN GRAPHIQUE DE %(sym)s (meme sous-jacent, n importe
// quel courtier, n importe quelle unite de temps).
//
// Ce que ca ne dit pas : rien sur la suite. Un rayon sur le plus haut
// d une bougie repere est un NIVEAU, pas une prevision.
// =====================================================================
//@version=5
indicator("Reperes %(sym)s", overlay=true, max_lines_count=500,
   max_labels_count=500)

montrer_haut  = input.bool(true,  "Rayon sur le plus haut")
montrer_bas   = input.bool(true,  "Rayon sur le plus bas")
montrer_trait = input.bool(true,  "Trait vertical sur la bougie")
montrer_texte = input.bool(true,  "Etiquette")
mini_dims     = input.int(1, "Dimensions franchies au minimum", minval=1,
   maxval=6)
coul_h        = input.color(color.new(color.orange, 0), "Couleur haut")
coul_b        = input.color(color.new(color.aqua, 0),   "Couleur bas")

var int[]    T = array.new_int()
var int[]    N = array.new_int()
var string[] D = array.new_string()

if barstate.isfirst
%(table)s

// Pointeur qui avance : la table est triee, on ne la reparcourt pas a
// chaque barre.
//
// ATTENTION : Pine n evalue PAS ses `and` en court-circuit. Ecrire
// `k < array.size(T) and array.get(T, k) < time` appelle array.get
// MEME quand k est hors bornes -- d ou l erreur RE10045 "Index 150 is
// out of bounds, array size is 150". La borne se teste donc dans un
// `if` separe, et la boucle sort par `break`.
var int k = 0

if barstate.isconfirmed
    for i = 0 to 199
        if k >= array.size(T)
            break
        ts = array.get(T, k)
        if ts >= time_close
            break
        if ts >= time
            nd = array.get(N, k)
            if nd >= mini_dims
                c = array.get(D, k)
                if montrer_trait
                    line.new(bar_index, low, bar_index, high,
                       color=color.new(color.gray, 40), width=1,
                       extend=extend.both, style=line.style_dotted)
                if montrer_haut
                    line.new(bar_index, high, bar_index + 1, high,
                       color=coul_h, width=1, extend=extend.right)
                if montrer_bas
                    line.new(bar_index, low, bar_index + 1, low,
                       color=coul_b, width=1, extend=extend.right)
                if montrer_texte
                    label.new(bar_index, high, str.tostring(nd),
                       color=color.new(color.black, 100),
                       textcolor=coul_h, style=label.style_label_down,
                       size=size.tiny, tooltip=c)
        k += 1
'''


if __name__ == "__main__":
    sys.exit(main())
