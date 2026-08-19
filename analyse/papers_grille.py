# -*- coding: utf-8 -*-
r"""
papers_grille.py -- l espace des lignes que CHAQUE section produit

  python papers_grille.py
  python papers_grille.py --famille nest
  python papers_grille.py --coupure "2026-08-18 12:20:06"

LECTEUR SEUL. N ECRIT RIEN, NE PREND AUCUN TRADE.

CE QUE LA LECTURE DU SOURCE A DONNE, ET C EST DECISIF

 1. LE "dv" DU NEST EST UNE DIMENSION A TROIS VALEURS, PAS UN JOKER.

    _nest_for (panneau:844) rend ("NO", None) dans DEUX sorties
    anticipees -- ancre non alignee, ou actif divergent sur l ancre --
    et ("NO"|"YES", "WITH"|"AGAINST") sinon.

    Et _section_mtf_nest (panneau:876) fait :

        agg.setdefault(nest, {}).setdefault(dv or "-", {})...
        for dv in ("WITH", "AGAINST", "-"):

    "-" est donc une LIGNE, la troisieme. J avais lu veut_dv=None
    comme "n importe laquelle" et je comptais l UNION des trois : 665
    pour 290 annonces, 724 pour 396. Le facteur ~2 n etait pas un
    mystere, c etait une somme.

 2. _section_vs_pack N A AUCUNE DIMENSION DE SENS.

    Ses lignes sont TF x (WITH|AGAINST) x churn (panneau:816-819).
    C_M15_VENTE portait `dir == "SELL"` -- un filtre qui n existe
    nulle part dans cette section. Le mot "vente" du libelle ne
    designe pas une colonne du panneau.

 3. LA VUE A EMET DEUX LIGNES PAR TRADE.

        for ss in ("ALL", s):   (panneau:615)

    Chaque trade compte dans la ligne ALL *et* dans celle de sa
    session. Rien n oblige les 35 cles a venir toutes de la meme
    colonne : ce sont des lignes relevees dans un panneau, pas un
    export homogene. M15_SCA_MX est en deficit sur US (43 pour 73) --
    la ligne ALL, elle, n a jamais ete regardee.

CE QUE FAIT CE SCRIPT

    Il ne propose pas de variantes : il reconstruit l ESPACE DES
    LIGNES de chaque section, exactement comme le code l ecrit, et
    compte chaque cellule a la coupure. Puis il cherche les effectifs
    annonces DEDANS.

    La grille est publiee en entier. Si un effectif tombe dans
    plusieurs cellules, le script les montre TOUTES et le dit : une
    correspondance unique identifie une ligne, trois correspondances
    n identifient rien.

CE QUE LE BALAYAGE A DEJA DIT, ET QUI CHANGE LA LECTURE

    Les quatre cles "TROP TARD" -- M15_WIDE_CL, M15_LEAD, M5_WIDE_CL,
    M5_DIVG -- ont chacune une fenetre etroite, disjointe des trois
    autres, mais TOUTES SITUEES DANS la bande de 94 minutes sur
    laquelle 25 cles s accordent.

    Un predicat faux pose sa fenetre n importe ou -- les trois qui
    debordent ont la leur des JOURS avant. Quatre fenetres qui
    atterrissent toutes dans la meme bande de 94 minutes disent autre
    chose : que l export n a pas ete releve en un seul instant.

    Ce script ne le suppose pas. Il donne pour chacune la coupure qui
    la rend exacte, et laisse la coincidence se voir.
"""
import argparse
import glob
import io
import os
import sys


def _ts(t):
    e = t.get("entry_ts")
    return e if isinstance(e, str) else None


def cellules(records, cle_de):
    """{coordonnees: [entry_ts]}. cle_de rend une coordonnee ou None."""
    out = {}
    for r in records:
        e = _ts(r)
        if e is None:
            continue
        for k in cle_de(r):
            out.setdefault(k, []).append(e)
    for k in out:
        out[k].sort()
    return out


def compte_a(ts, coupure):
    return sum(1 for e in ts if e <= coupure)


def fenetre_pour(ts, n):
    if len(ts) < n:
        return None, None
    return ts[n - 1], (ts[n] if len(ts) > n else "(ouverte)")


def montre(add, titre, grille, cibles, coupure, largeur=34):
    """La grille entiere, puis ou chaque effectif annonce se trouve."""
    add("")
    add("-" * 96)
    add(titre)
    add("-" * 96)
    add("  %-*s %7s %7s" % (largeur, "ligne", "a la coupure", "total"))
    for k in sorted(grille):
        ts = grille[k]
        add("  %-*s %7d %7d"
            % (largeur, " x ".join(str(x) for x in k),
               compte_a(ts, coupure), len(ts)))
    add("")
    for cle, n in cibles:
        egales = [k for k in sorted(grille)
                  if compte_a(grille[k], coupure) == n]
        if egales:
            add("  %-13s %5d  ->  %s"
                % (cle, n, " | ".join(" x ".join(str(x) for x in k)
                                      for k in egales)))
            if len(egales) > 1:
                add("  %-13s %5s      %d cellules donnent ce compte : ce n est"
                    " pas une identification." % ("", "", len(egales)))
        else:
            # Aucune cellule ne tombe juste. Plutot que de lister au
            # hasard, on montre les SIX PLUS PROCHES : c est la que la
            # bonne ligne se trouve si elle existe, et un ecart de 200
            # se voit aussi bien qu un ecart de 2.
            proches = sorted(
                ((abs(compte_a(grille[k], coupure) - n), k) for k in grille),
                key=lambda x: (x[0], str(x[1])))[:6]
            add("  %-13s %5d  ->  aucune cellule exacte. Les six plus"
                " proches :" % (cle, n))
            for ecart, k in proches:
                v = compte_a(grille[k], coupure)
                lo, hi = fenetre_pour(grille[k], n)
                add("  %-13s %5s      %-34s %6d  %+5d   %s"
                    % ("", "", " x ".join(str(x) for x in k), v, v - n,
                       ("exacte a [%s, %s)" % (lo, hi)) if lo
                       else "n atteint jamais %d" % n))


def scan_rsi(add, racine="."):
    add("")
    add("-" * 96)
    add("D OU VIENNENT RSI_M1_BU ET RSI_M15_BU -- rsi_pos dans le source")
    add("-" * 96)
    add("  Aucune des sections lues ne porte rsi_pos. Voici qui le porte.")
    add("")
    try:
        import papers_repare as PR
        enclosante = PR.enclosante
    except Exception:
        def enclosante(lignes, k):
            return "?"
    vus = 0
    for f in sorted(glob.glob(os.path.join(racine, "*.py"))):
        base = os.path.basename(f)
        if base.startswith("papers_"):
            continue
        try:
            lignes = io.open(f, encoding="utf-8",
                             errors="replace").read().split("\n")
        except Exception:
            continue
        for i, l in enumerate(lignes):
            if "rsi_pos" in l:
                add("  %-28s %5d  %-24s %s"
                    % (base, i + 1, enclosante(lignes, i), l.strip()[:44]))
                vus += 1
                if vus >= 40:
                    add("  ... (arrete a 40)")
                    return
    if not vus:
        add("  rsi_pos n apparait dans AUCUN .py de ce dossier. Le champ")
        add("  vient donc d ailleurs -- collecteur ou fichier de rails.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--coupure", default=None)
    p.add_argument("--famille", action="append", default=None)
    p.add_argument("--rails", default=None)
    a = p.parse_args()

    try:
        import papers_encode as PE
        import papers_population as PP
        import papers_coupure as PC
        import papers_repare as PR
    except ImportError as e:
        print("KO : papers_encode, papers_population, papers_coupure et")
        print("     papers_repare doivent etre dans ce dossier. (%s)" % e)
        return 1

    src = io.open(PR.trouve_panneau([".", "..", os.path.join("..", "..")]),
                  encoding="utf-8", errors="replace").read()
    below, _e1 = PR.literal_apres(src, "_ANCHOR_BELOW")
    ordre, _e2 = PR.literal_apres(src, "_ANCHOR_ORDER")
    if not isinstance(below, dict):
        print("KO : _ANCHOR_BELOW illisible dans le panneau.")
        return 1
    ANCHORS = list(ordre) if isinstance(ordre, (list, tuple)) else \
        ["M5", "M3", "M15"]
    nest_for = PR.fabrique_nest(below, PE)

    chemin = a.rails or PP.RAILS
    trades, ko = PP.lire(chemin)
    sigs, ecartes = PP.signaux(trades)

    L = []
    add = L.append
    add("=" * 96)
    add("L ESPACE DES LIGNES DE CHAQUE SECTION, ET OU TOMBE CHAQUE EFFECTIF")
    add("=" * 96)
    add("")
    add("  Lecteur seul. Rien n est ecrit, aucun trade n est pris.")
    add("")
    add("  %s : %d lignes (%d illisibles)" % (chemin, len(trades), ko))
    add("  signaux : %d (%d ecarte(s))" % (len(sigs), ecartes))
    add("  ancres  : %s" % ", ".join(ANCHORS))
    add("")

    # --- la coupure : reprise du balayage, pas un chiffre recopie
    if a.coupure:
        COUPURE = a.coupure
        add("  Coupure imposee en ligne de commande : %s" % COUPURE)
    else:
        cles = [(c, n, pr) for c, n, pr, _o in
                PR.construit_cles(PE, nest_for)]
        fen = {}
        for cle, n, pred in cles:
            genre, col_fixe = PP.SECTIONS.get(cle, (None, None))
            if genre is None:
                continue
            pop = sigs if genre == "signaux" else trades
            ts = PC.horodates(pop, pred, col_fixe or "US", PE)
            lo, hi = PC.fenetre(ts, n)
            fen[cle] = (lo, hi)
        prof = PC.balaye(fen)
        if not prof:
            print("KO : aucune fenetre exploitable.")
            return 1
        COUPURE = prof[0][0]
        add("  Coupure rededuite par balayage : %s  (%d cles exactes)"
            % (COUPURE, prof[0][2]))
    add("")

    veut = set(a.famille or [])

    def actif(nom):
        return not veut or nom in veut

    # ------------------------------------------------------------------
    # nest -- panneau:863. dv a TROIS valeurs, "-" comprise.
    # ------------------------------------------------------------------
    if actif("nest"):
        def k_nest(s):
            b = PE.ver(s)
            out = []
            for anchor in ANCHORS:
                nest, dv = nest_for(s, anchor)
                if nest is None:
                    continue
                out.append((anchor, nest, dv or "-", b))
            return out
        montre(add, "NEST -- ancre x nest x dv x churn   (signaux)",
               cellules(sigs, k_nest),
               [("M5_ET_YES", 43), ("M5_ET_NO_A", 104),
                ("M5_ET_NO_C", 290), ("M15_NO_MX", 396)], COUPURE)

    # ------------------------------------------------------------------
    # vs pack -- panneau:804. AUCUNE dimension de sens.
    # ------------------------------------------------------------------
    if actif("pack"):
        def k_pack(s):
            b = PE.ver(s)
            out = []
            for tf in PE.TFS:
                vp = PE._vs_pack(s, tf)
                if vp is None:
                    continue
                out.append((tf, vp, b))
            return out
        montre(add, "VS PACK -- TF x WITH/AGAINST x churn   (signaux)",
               cellules(sigs, k_pack),
               [("M5_AGA_CH", 365), ("C_M15_VENTE", 358)], COUPURE)

    # ------------------------------------------------------------------
    # trajectoire (self_mom)
    # ------------------------------------------------------------------
    if actif("mom"):
        def k_mom(s):
            b = PE.ver(s)
            out = []
            for tf in PE.TFS:
                m = PE.hlc(s, tf, "self_mom")
                if not m or m == "NODATA":
                    continue
                out.append((tf, m, b))
            return out
        montre(add, "TRAJECTOIRE -- TF x self_mom x churn   (signaux)",
               cellules(sigs, k_mom),
               [("M5_WIDE_CL", 355), ("M15_WIDE_CL", 301)], COUPURE)

    # ------------------------------------------------------------------
    # hlc vue A -- panneau:615, DEUX lignes par trade : ALL et la session
    # ------------------------------------------------------------------
    if actif("vueA"):
        def k_vueA(t):
            if not t.get("entry_captured_live"):
                return []
            b = PE.ver(t)
            s = PE._sess(t)
            out = []
            for tf in PE.TFS:
                cons = PE.hlc(t, tf, "consensus")
                if not cons or cons == "NODATA":
                    continue
                for ss in ("ALL", s):
                    out.append((tf, cons, b, ss))
            return out
        montre(add, "HLC VUE A -- TF x consensus x churn x session   (trades)",
               cellules(trades, k_vueA),
               [("M1_ALBU_CL", 211), ("M15_ALBU_CL", 167),
                ("M15_SPL_CL", 243), ("M15_SCA_MX", 73)], COUPURE, 40)

    # ------------------------------------------------------------------
    # hlc vue B -- panneau:619, "ALL" SEUL
    # ------------------------------------------------------------------
    if actif("vueB"):
        def k_vueB(t):
            if not t.get("entry_captured_live"):
                return []
            b = PE.ver(t)
            out = []
            for tf in PE.TFS:
                role = PE.hlc(t, tf, "self_role")
                if not role or role == "nodata":
                    continue
                out.append((tf, role, b))
            return out
        montre(add, "HLC VUE B -- TF x self_role x churn   (trades, ALL seul)",
               cellules(trades, k_vueB),
               [("M15_LEAD", 313), ("M5_DIVG", 190)], COUPURE)

    if actif("rsi"):
        scan_rsi(add)

    add("")
    add("=" * 96)
    add("  Ce script n a rien ecrit et n a pris aucun trade.")
    add("=" * 96)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
