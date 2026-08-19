# -*- coding: utf-8 -*-
r"""
papers_instants.py -- l export n a pas ete releve en un instant. Preuve.

  python papers_instants.py
  python papers_instants.py --cle M5_DIVG

LECTEUR SEUL. N ECRIT RIEN, NE PREND AUCUN TRADE.

CE QUE LA GRILLE A IDENTIFIE, CELLULE PAR CELLULE

    Sept effectifs sont tombes dans UNE SEULE cellule de l espace que
    leur section produit -- pas dans deux, pas dans trois :

      M5_ET_YES    43  -> M5  x YES x WITH x mixed
      M15_NO_MX   396  -> M15 x NO  x "-"  x mixed
      M5_AGA_CH   365  -> M5  x AGAINST x churn
      M15_WIDE_CL 301  -> M15 x WIDENING x clean
      M1_ALBU_CL  211  -> M1  x ALIGNED_BULL x clean x US
      M15_ALBU_CL 167  -> M15 x ALIGNED_BULL x clean x US
      M15_SCA_MX   73  -> M15 x SCATTER x mixed x ALL

    Les deux corrections que ca impose :

      M15_NO_MX  le "-" est une LIGNE (panneau:881), pas un joker. Je
                 comptais l union des trois -> 724 pour 396.
      M15_SCA_MX la colonne est ALL, pas US. La vue A emet DEUX lignes
                 par trade (panneau:615) et je n avais jamais regarde
                 la premiere. Le "deficit" de 43 pour 73 n existait pas.

    Deux effectifs tombent dans plusieurs cellules -- M5_ET_NO_A (104,
    deux cellules) et M15_SPL_CL (243, trois). Le compte ne tranche
    pas ; le LIBELLE, ecrit avant toute mesure, designe M5 x NO x
    AGAINST x churn et M15 x SPLIT x clean x US. On garde ceux-la, et
    on dit que c est le nom qui a tranche, pas le nombre.

CE QUI A FERME LA QUESTION DU "PREDICAT FAUX"

    Deux cles de DEUX SECTIONS DIFFERENTES ont la meme fenetre, a la
    seconde pres :

      M5 x NO x "-" x clean   (nest)   exacte a [13:51:27, 13:54:04)
      M5 x divergent x clean  (vue B)  exacte a [13:51:27, 13:54:04)

    Un intervalle de 2 min 37 partage par deux lignes independantes
    n est pas une coincidence : elles ont ete relevees au meme moment.

CE QUE MESURE CE SCRIPT, ET POURQUOI C EST FALSIFIABLE

    Si l export a ete recopie d un panneau vivant pendant une seance,
    alors il existe une DUREE courte qui explique presque toutes les
    cles -- chacune etant juste a un instant de cette duree.

    Le script calcule, pour K allant de 20 a 35, le PLUS PETIT
    intervalle qui rend K cles exactes. Si expliquer 33 cles demande
    une heure et demie et que la 34e en demande cinq jours, la these
    tient et la cle qui resiste est designee. Si au contraire il faut
    deja trois jours pour 28, la these tombe -- et le script l ecrira.

    C est une prediction avec un moyen d echouer, pas une lecture.

CE QUI RESTE OUVERT, ET N EST PAS MAQUILLE

    C_M15_VENTE (358) ne tombe dans aucune cellule de vs pack. Ses
    trois candidates par le nom -- M15 x AGAINST x {clean, mixed,
    churn} -- sont affichees avec leur fenetre, sans en choisir une.

    RSI_M1_BU / RSI_M15_BU : rsi_pos n apparait dans AUCUNE section du
    panneau ; il est ecrit par churn_trade_logger.py:158. Les valeurs
    que mon predicat cherchait -- "INSIDE", "ABOVE" -- ne figurent
    dans aucun vocabulaire du depot. Je les ai inventees. Le script
    compte donc les valeurs REELLES du champ dans les tickets, au lieu
    d en supposer une de plus.
"""
import argparse
import io
import os
import sys

INFINI = "9999-99-99 99:99:99"


def _sec(ts):
    """Horodate -> secondes. Sert UNIQUEMENT a mesurer des durees."""
    if ts >= INFINI:
        return 10 ** 12
    try:
        import calendar
        return calendar.timegm((int(ts[0:4]), int(ts[5:7]), int(ts[8:10]),
                                int(ts[11:13]), int(ts[14:16]),
                                int(ts[17:19]), 0, 1, 0))
    except (ValueError, IndexError):
        return 0


def duree(a, b):
    s = _sec(b) - _sec(a)
    if s >= 10 ** 11:
        return "infinie"
    if s < 90:
        return "%d s" % s
    if s < 5400:
        return "%d min" % (s // 60)
    if s < 86400 * 2:
        return "%d h %02d" % (s // 3600, (s % 3600) // 60)
    return "%d jours" % (s // 86400)


def span_mini(fen, K):
    """Le plus petit [a, b] qui rend K cles exactes.

    Une cle est rendue exacte par [a, b] s il existe un instant de
    [a, b] dans sa fenetre, c est-a-dire si [lo, hi) et [a, b] se
    coupent. On n essaie que les bornes reelles : l optimum est
    toujours atteint sur l une d elles."""
    vals = [(lo, hi) for lo, hi in fen if lo]
    bornes = sorted(set([lo for lo, _h in vals] + [h for _l, h in vals]))
    best = None
    for i, a in enumerate(bornes):
        for b in bornes[i:]:
            c = sum(1 for lo, hi in vals if lo <= b and a < hi)
            if c >= K:
                d = _sec(b) - _sec(a)
                if best is None or d < best[0]:
                    best = (d, a, b, c)
                break          # b croissant : le premier qui atteint K
    return best


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rails", default=None)
    p.add_argument("--cle", default=None)
    a = p.parse_args()

    try:
        import papers_encode as PE
        import papers_population as PP
        import papers_coupure as PC
        import papers_repare as PR
    except ImportError as e:
        print("KO : papers_encode, papers_population, papers_coupure et")
        print("     papers_repare doivent etre la. (%s)" % e)
        return 1

    src = io.open(PR.trouve_panneau([".", "..", os.path.join("..", "..")]),
                  encoding="utf-8", errors="replace").read()
    below, _e = PR.literal_apres(src, "_ANCHOR_BELOW")
    if not isinstance(below, dict):
        print("KO : _ANCHOR_BELOW illisible.")
        return 1
    nest_for = PR.fabrique_nest(below, PE)

    chemin = a.rails or PP.RAILS
    trades, ko = PP.lire(chemin)
    sigs, ecartes = PP.signaux(trades)

    # ---- les definitions FINALES ------------------------------------
    cles = [(c, n, pr) for c, n, pr, _o in PR.construit_cles(PE, nest_for)]
    SEC = dict(PP.SECTIONS)
    SEC["M15_SCA_MX"] = ("trades", "ALL")      # vue A emet ALL et session

    def nest_tiret(anchor, seau):
        # dv "-" = les DEUX sorties anticipees de _nest_for, celles qui
        # rendent (NO, None). Une ligne du tableau, pas une absence.
        def f(t):
            return nest_for(t, anchor) == ("NO", None) and PE.ver(t) == seau
        return f

    remplace = {
        "M5_ET_NO_C": (nest_tiret("M5", "clean"),
                       'dv "-" (panneau:881), pas le joker'),
        "M15_NO_MX": (nest_tiret("M15", "mixed"),
                      'dv "-" (panneau:881), pas le joker'),
    }
    cles = [(c, n, remplace[c][0] if c in remplace else pr)
            for c, n, pr in cles]

    L = []
    add = L.append
    add("=" * 96)
    add("L INSTANT PROPRE A CHAQUE CLE -- l export a-t-il ete releve d un")
    add("seul tenant, ou recopie au fil d une seance ?")
    add("=" * 96)
    add("")
    add("  Lecteur seul. Rien n est ecrit, aucun trade n est pris.")
    add("")
    add("  %s : %d lignes (%d illisibles)" % (chemin, len(trades), ko))
    add("  signaux : %d (%d ecarte(s))" % (len(sigs), ecartes))
    add("")
    add("  Deux definitions corrigees par la grille :")
    for c, (_f, pourquoi) in sorted(remplace.items()):
        add("    %-13s %s" % (c, pourquoi))
    add("    %-13s colonne ALL et non US (panneau:615)" % "M15_SCA_MX")
    add("")

    # ---- la fenetre de chaque cle -----------------------------------
    fen, meta = {}, {}
    for cle, n, pred in cles:
        genre, col = SEC.get(cle, (None, None))
        if genre is None:
            fen[cle] = (None, None)
            meta[cle] = (n, "hors panneau", "-")
            continue
        pop = sigs if genre == "signaux" else trades
        ts = PC.horodates(pop, pred, col or "US", PE)
        lo, hi = PC.fenetre(ts, n)
        fen[cle] = (lo, hi)
        meta[cle] = (n, genre, col or "US")

    add("=" * 96)
    add("CHAQUE CLE ET L INSTANT QUI LA REND EXACTE")
    add("=" * 96)
    add("  %-13s %5s %-8s %-4s  %-19s %-19s %s"
        % ("CLE", "N", "POP", "COL", "de", "a (exclu)", "large"))
    add("  " + "-" * 88)
    ordonne = sorted(cles, key=lambda x: (fen[x[0]][0] or "~~~~"))
    for cle, _n, _p in ordonne:
        n, genre, col = meta[cle]
        lo, hi = fen[cle]
        if lo is None:
            add("  %-13s %5d %-8s %-4s  %s"
                % (cle, n, genre, col,
                   "AUCUN instant ne rend cet effectif"))
        else:
            add("  %-13s %5d %-8s %-4s  %-19s %-19s %s"
                % (cle, n, genre, col, lo,
                   "(ouverte)" if hi == INFINI else hi, duree(lo, hi)))
    add("")
    sans = [c for c in fen if fen[c][0] is None]
    add("  %d cle(s) sans aucun instant : %s"
        % (len(sans), ", ".join(sorted(sans)) or "aucune"))
    add("")

    # ---- LA MESURE DECISIVE -----------------------------------------
    add("=" * 96)
    add("COMBIEN DE TEMPS FAUT-IL POUR EXPLIQUER K CLES ?")
    add("=" * 96)
    add("  Si l export a ete recopie d un panneau vivant, une duree")
    add("  COURTE doit suffire a en expliquer presque toutes. Si au")
    add("  contraire il faut deja des jours pour la moitie, la these")
    add("  tombe -- et c est ce tableau qui le dira.")
    add("")
    add("  %5s  %-10s %-19s %-19s" % ("K", "duree", "de", "a"))
    add("  " + "-" * 58)
    valides = sum(1 for v in fen.values() if v[0])
    saut = None
    prec = None
    for K in range(20, valides + 1):
        r = span_mini(list(fen.values()), K)
        if r is None:
            add("  %5d  %s" % (K, "impossible"))
            continue
        d, deb, fin, _c = r
        add("  %5d  %-10s %-19s %-19s" % (K, duree(deb, fin), deb, fin))
        if prec is not None and prec > 0 and d > prec * 8 and saut is None:
            saut = (K, prec, d)
        prec = d
    add("")
    add("  %d cles ont un instant sur %d." % (valides, len(cles)))
    if saut:
        add("  Le saut est a K=%d : passer de %d a %d cles multiplie la"
            % (saut[0], saut[0] - 1, saut[0]))
        add("  duree necessaire par %d. Les cles au-dela de ce seuil ne"
            % (saut[2] // max(saut[1], 1)))
        add("  viennent pas de la meme seance.")
    else:
        add("  Aucun saut net : la duree croit regulierement avec K. La")
        add("  these du releve etale n est PAS confirmee par ce tableau.")
    add("")

    # ---- ce qui reste ouvert ----------------------------------------
    add("=" * 96)
    add("C_M15_VENTE -- les trois candidates, sans en choisir une")
    add("=" * 96)
    for seau in ("clean", "mixed", "churn"):
        def f(t, s=seau):
            return PE._vs_pack(t, "M15") == "AGAINST" and PE.ver(t) == s
        ts = PC.horodates(sigs, f, "ALL", PE)
        lo, hi = PC.fenetre(ts, 358)
        add("  M15 x AGAINST x %-6s  total %4d   %s"
            % (seau, len(ts),
               ("exacte a [%s, %s)" % (lo, hi)) if lo
                else "n atteint jamais 358"))
    add("")
    add("  Le libelle dit CONFLIT et vente. _section_vs_pack n a aucune")
    add("  dimension de sens : si aucune de ces trois fenetres ne tombe")
    add("  dans la seance, la ligne ne vient pas de cette section.")
    add("")

    add("=" * 96)
    add("RSI_M1_BU / RSI_M15_BU -- les valeurs REELLES du champ")
    add("=" * 96)
    add("  Mon predicat cherchait rsi_pos == INSIDE et == ABOVE. Ces")
    add("  deux mots ne figurent dans aucun vocabulaire du depot. Voici")
    add("  ce que les tickets portent vraiment.")
    add("")
    for tf in PE.TFS:
        vus = {}
        for t in trades:
            v = (PE.moi(t, tf) or {}).get("rsi_pos")
            vus[v] = vus.get(v, 0) + 1
        bout = sorted(vus.items(), key=lambda x: -x[1])[:8]
        add("  %-4s  %s" % (tf, "   ".join("%s=%d" % (k, v)
                                           for k, v in bout)))
    add("")

    if a.cle:
        add("=" * 96)
        add("DETAIL -- %s" % a.cle)
        add("=" * 96)
        if a.cle not in fen:
            add("  Cle inconnue.")
        else:
            n, genre, col = meta[a.cle]
            lo, hi = fen[a.cle]
            add("  annonce %d, population %s, colonne %s" % (n, genre, col))
            add("  exacte a [%s, %s)  large de %s"
                % (lo, hi, duree(lo, hi) if lo else "-"))
        add("")

    add("=" * 96)
    add("  Ce script n a rien ecrit et n a pris aucun trade.")
    add("=" * 96)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
