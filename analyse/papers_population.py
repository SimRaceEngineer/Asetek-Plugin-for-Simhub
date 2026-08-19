# -*- coding: utf-8 -*-
r"""
papers_population.py -- ou le panneau va-t-il chercher chaque effectif

  python papers_population.py
  python papers_population.py --cle M5_AGA_CH

LECTEUR SEUL. N ECRIT RIEN, NE PREND AUCUN TRADE.

CE QUE LE PREMIER ESSAI A APPRIS

    J avais suppose que les quinze cles fausses venaient d une base plus
    large : _load_trades fusionne churn_trades_archive.jsonl et
    churn_trades.jsonl jusqu a 20 000 lignes, nous en lisons 4 681.

    Le decompte a repondu : churn 4 695, rails 4 689. Six lignes d ecart.
    J avais lu limite=20000 comme une TAILLE alors que c est un PLAFOND.
    L hypothese est morte, et c est le script qui l a tuee -- pas moi.

    Deux fautes m appartenaient dans ce premier essai :

      1. Je cherchais la coupure DANS chaque population, y compris les
         populations de signaux. Or la coupure se deduit d effectifs
         annonces au niveau TICKET. La demander a un ensemble
         dedoublonne, c est demander l impossible : zero partout.

      2. Je mesurais avec papers_encode.CLES -- les definitions dont je
         savais deja qu elles etaient fausses. D ou 15 exactes au lieu
         de 20, et cinq cles reparees rangees parmi les irreductibles.

CE QUE FAIT CETTE VERSION : elle ne cherche plus, elle verifie

    Le panneau DIT, section par section, sur quoi il compte. La table
    SECTIONS ci-dessous ne fait que transcrire ce que son code fait :

      _section_vs_pack, _section_mtf_nest, _section_mom  -> signals
          (signals = _signals(trades), jumeaux 206/207 regroupes)
      _section_hlc_churn vue A                           -> ("ALL", s)
      vue B (self_role) et vue C (transition)            -> "ALL" seul
      tout le reste                                      -> trades

    Les predicats viennent de papers_repare -- les corriges, ceux qui
    tombent juste sur vingt cles -- et non plus de papers_encode.

    La coupure est deduite UNE fois, sur les tickets, par intersection
    des fenetres [Nieme, (N+1)ieme). Les populations de signaux en
    heritent : elles descendent des memes tickets.

    Et la conclusion se lit PAR FAMILLE, pas cle par cle. Une cle qui
    tombe juste seule peut le devoir au hasard. Une section entiere qui
    tombe juste ne le peut pas.

CE QUE LE RESULTAT TRANCHERA

    Si une famille tombe juste avec la population que son code designe,
    la lecture est confirmee et les cles restantes de cette famille
    n ont plus qu un predicat a corriger.

    Si une famille echoue avec TOUTES les populations et TOUTES les
    colonnes, alors la cause n est ni la base, ni la coupure, ni la
    session : c est le predicat. Le script le dira dans ces termes.

LA SEULE CHOSE QUE JE SUPPOSE, ET ELLE EST MARQUEE

    _signals appelle _ts_epoch, que je n ai pas extraite. Je la
    reimplemente comme la conversion evidente d un 'AAAA-MM-JJ
    HH:MM:SS' en secondes. Un decalage constant de base ne changerait
    QUE les paires a cheval sur une frontiere de 30 s -- le script
    compte donc les groupes formes et le dit, pour qu une erreur de
    base se voie au lieu de se cacher.

    RSI_M1_BU et RSI_M15_BU ne sont produites par AUCUNE section du
    panneau. Le mot rsi n y apparait que dans des legendes. Elles sont
    marquees hors panneau et non comptees comme des echecs : leur
    source est ailleurs, et c est la qu il faudra la chercher.
"""
import argparse
import calendar
import io
import json
import os
import sys

RAILS = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
CHURN = [os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
         os.path.join("docs", "churn_trades", "churn_trades.jsonl")]
LIMITE = 20000


def lire(chemin):
    out, ko = [], 0
    if not os.path.isfile(chemin):
        return out, ko
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
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


def charge_churn(chemins=None, limite=LIMITE):
    """_load_trades du panneau (ligne 119), recopiee dans son ordre.

    L archive d abord, le vivant ensuite : a ticket egal le vivant
    ecrase, parce qu il porte le pnl definitif d un trade encore ouvert
    au moment de l archivage. Inverser les deux donnerait des pnl
    perimes sans qu aucun compte ne bouge."""
    merged, ko = {}, 0
    for chemin in (chemins or CHURN):
        lignes, k = lire(chemin)
        ko += k
        for r in lignes[-limite:]:
            cle = r.get("ticket")
            if cle is None:
                cle = ("nokey", r.get("magic"), r.get("asset"),
                       r.get("entry_ts"))
            merged[cle] = r
    out = sorted(merged.values(), key=lambda r: r.get("entry_ts") or "")
    return out[-limite:], ko


def _ts_epoch(ts):
    """SUPPOSEE : conversion evidente. Voir l en-tete."""
    try:
        an, mo, jo = int(ts[0:4]), int(ts[5:7]), int(ts[8:10])
        h, m, s = int(ts[11:13]), int(ts[14:16]), int(ts[17:19])
        return calendar.timegm((an, mo, jo, h, m, s, 0, 1, 0))
    except (ValueError, IndexError):
        return 0


def signaux(trades):
    """_signals du panneau (ligne 694). Seules les familles 206 et 207
    fusionnent ; tout le reste compte pour un."""
    groupes, ordre, ecartes = {}, [], 0
    for t in trades:
        # Le panneau ecarte ce qui n a pas ete capture en direct. Si un
        # fichier ne porte pas ce champ, TOUT disparait -- et un zero
        # silencieux se lirait comme une population vide plutot que
        # comme un champ absent. On les compte.
        if not t.get("entry_captured_live"):
            ecartes += 1
            continue
        m = int(t.get("magic") or 0)
        fam = m // 1000
        if fam in (206, 207):
            b = int(_ts_epoch(t.get("entry_ts") or "") // 30)
            cle = ("IGN", t.get("asset"), t.get("dir"), m % 1000, b)
        else:
            cle = ("SOLO", t.get("ticket"))
        if cle not in groupes:
            groupes[cle] = []
            ordre.append(cle)
        groupes[cle].append(t)
    sigs = []
    for cle in ordre:
        arr = groupes[cle]
        base = arr[0]
        pnls = [float(x.get("pnl_eur", 0) or 0) for x in arr]
        mfes = [float(x.get("mfe_eur", 0) or 0) for x in arr]
        maes = [float(x.get("mae_eur", 0) or 0) for x in arr]
        s = dict(base)
        s["pnl_eur"] = sum(pnls) / len(pnls)
        s["mfe_eur"] = max(mfes)
        s["mae_eur"] = min(maes)
        s["_n_bras"] = len(arr)
        sigs.append(s)
    return sigs, ecartes


def coupure_deduite(tickets, PE, colonne):
    """Le trou commun aux quatre effectifs de la section ecartement."""
    ref = [("TIGHT_CROSS", "clean", 214), ("TIGHT_CROSS", "mixed", 154),
           ("MID", "clean", 251), ("WIDE", "clean", 231)]
    bornes = []
    for setup, seau, n in ref:
        ts = sorted(t["entry_ts"] for t in tickets
                    if t.get("rails_setup") == setup and PE.ver(t) == seau
                    and (colonne == "ALL" or PE._sess(t) == colonne)
                    and isinstance(t.get("entry_ts"), str))
        if len(ts) > n:
            bornes.append((ts[n - 1], ts[n]))
    if len(bornes) != len(ref):
        return None
    bas, haut = max(b[0] for b in bornes), min(b[1] for b in bornes)
    return bas if bas < haut else None


# ======================================================================
# CE QUE LE PANNEAU DIT DE CHAQUE SECTION   (lu, pas devine)
# ======================================================================
# Chercher au hasard la meilleure combinaison parmi vingt-quatre serait
# de l ajustement deguise : avec assez d essais, une cle finit par
# tomber juste par accident. On teste donc la combinaison que LE CODE
# ANNONCE, et un echec devient alors une information -- pas une
# invitation a essayer autre chose.
#
#   pop : "trades" ou "signaux", selon l argument de la section
#   col : "US"/"EUR"/"ALL" -- "ALL" quand la section n a PAS de
#         dimension de session dans son agregation
#
#   _section_setup(trades)        _agg_sess -> session          ligne 312
#   _section_per_tf(trades)       for ss in ("ALL", s)          ligne 395
#   _section_tf_pattern(trades)   _agg_sess -> session          ligne 372
#   _section_leader(trades)       _agg_sess -> session          ligne 424
#   _section_hlc_churn(trades)    vue A : ("ALL", s)            ligne 615
#                                 vue B : "ALL" SEUL            ligne 619
#                                 vue C : "ALL" SEUL            ligne 622
#   _section_vs_pack(signals)     aucune session                ligne 814
#   _section_mtf_nest(signals)    aucune session                ligne 876
#   _section_mom(signals)         aucune session                ligne 918
SECTIONS = {
    "TC_CLEAN": ("trades", None), "TC_MIXED": ("trades", None),
    "MID_CLEAN": ("trades", None), "WIDE_CLEAN": ("trades", None),
    "M1_T_CL": ("trades", None), "M1_S_CH": ("trades", None),
    "M3_T_MX": ("trades", None), "M5_T_CL": ("trades", None),
    "M15_T_CL": ("trades", None), "M15_T_MX": ("trades", None),
    "M1M15": ("trades", None), "M1M3M5M15": ("trades", None),
    "M3M5M15": ("trades", None),
    "M1_ALBU_CL": ("trades", None), "M15_ALBU_CL": ("trades", None),
    "M15_SPL_CL": ("trades", None), "M15_SCA_MX": ("trades", None),
    "M15_LEAD": ("trades", "ALL"), "M5_DIVG": ("trades", "ALL"),
    "M3_CONV_CL": ("trades", "ALL"), "M5_DIV_CL": ("trades", "ALL"),
    "M15_CONV_MX": ("trades", "ALL"),
    "US30_BE_CL": ("trades", None), "US30_BE_MX": ("trades", None),
    "US500_BU_CL": ("trades", None),
    "M5_AGA_CH": ("signaux", "ALL"), "C_M15_VENTE": ("signaux", "ALL"),
    "M5_ET_YES": ("signaux", "ALL"), "M5_ET_NO_A": ("signaux", "ALL"),
    "M5_ET_NO_C": ("signaux", "ALL"), "M15_NO_MX": ("signaux", "ALL"),
    "M5_WIDE_CL": ("signaux", "ALL"), "M15_WIDE_CL": ("signaux", "ALL"),
    # RSI_* : aucune section du panneau ne les produit. Le mot rsi n y
    # apparait que dans des legendes. Elles viennent d ailleurs.
    "RSI_M1_BU": (None, None), "RSI_M15_BU": (None, None),
}


def compte(tickets, pred, colonne, coupure, PE):
    c = 0
    for t in tickets:
        e = t.get("entry_ts")
        if not isinstance(e, str) or (coupure and e > coupure):
            continue
        if colonne != "ALL" and PE._sess(t) != colonne:
            continue
        try:
            if pred(t):
                c += 1
        except Exception:
            pass
    return c


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rails", default=RAILS)
    p.add_argument("--churn", action="append", default=None)
    p.add_argument("--cle", default=None,
                   help="detail d une seule cle, sur les quatre populations")
    a = p.parse_args()

    try:
        import papers_encode as PE
    except ImportError:
        print("KO : papers_encode.py doit etre dans le meme dossier.")
        return 1

    # Les predicats CORRIGES du 19/08 -- leader relu, nest lisible.
    # Sans eux on remesurerait avec les definitions dont on sait deja
    # qu elles sont fausses, et on rangerait cinq cles reparees parmi
    # les irreductibles.
    corrige = None
    try:
        import papers_repare as PR
        below, err = PR.literal_apres(
            io.open(PR.trouve_panneau([".", "..", os.path.join("..", "..")]),
                    encoding="utf-8", errors="replace").read(),
            "_ANCHOR_BELOW")
        nest = PR.fabrique_nest(below, PE) if isinstance(below, dict) else None
        # Liste et non dict : l ordre de papers_encode groupe les cles
        # par section. Un tri alphabetique melangerait les familles, et
        # c est justement par famille qu on lit ce tableau.
        corrige = [(c, n, p) for c, n, p, _o in PR.construit_cles(PE, nest)]
    except Exception:
        corrige = None

    L = []
    add = L.append
    add("=" * 96)
    add("QUELLE POPULATION PRODUIT L EXPORT")
    add("=" * 96)
    add("")
    add("  Lecteur seul. Rien n est ecrit, aucun trade n est pris.")
    add("")

    rails, ko_r = lire(a.rails)
    churn, ko_c = charge_churn(a.churn)
    add("  rails : %-52s %6d lignes" % (a.rails, len(rails)))
    for c in (a.churn or CHURN):
        add("          %-52s %6s" % (c, "present" if os.path.isfile(c)
                                     else "ABSENT"))
    add("  churn : fusionne (archive puis vivant)          %6d lignes"
        % len(churn))
    if ko_r or ko_c:
        add("  %d + %d ligne(s) illisibles" % (ko_r, ko_c))
    if not churn:
        add("")
        add("  AUCUN churn_trades lisible. Les quatre populations se")
        add("  reduisent a deux, et la comparaison perd son objet.")
        add("  Relance avec --churn CHEMIN si les fichiers sont ailleurs.")
    add("")

    rails_s, ec_r = signaux(rails)
    churn_s, ec_c = signaux(churn)
    for nom, brut, sig, ec in (("rails", rails, rails_s, ec_r),
                               ("churn", churn, churn_s, ec_c)):
        fus = sum(1 for s in sig if s.get("_n_bras", 1) > 1)
        add("  %-6s %6d -> %6d signaux   (%d groupe(s) de plusieurs bras,"
            " %d ecarte(s) sans entry_captured_live)"
            % (nom, len(brut), len(sig), fus, ec))
    add("")
    add("  Un regroupement a zero groupe multiple signalerait que les")
    add("  jumeaux ne sont pas la ou je les cherche -- famille 206/207,")
    add("  meme cellule, meme tranche de 30 s. Et un nombre d ecartes")
    add("  egal au total dirait que le champ entry_captured_live n existe")
    add("  pas dans ce fichier, ce qui n est pas la meme chose qu une")
    add("  population vide.")
    add("")

    pops = [("rails", rails), ("churn", churn),
            ("rails/sig", rails_s), ("churn/sig", churn_s)]
    if corrige:
        cles = corrige
        add("  Predicats : papers_repare (corriges le 19/08), %d cles."
            % len(cles))
    else:
        cles = [(c, n, pr) for c, _l, n, pr, _x in PE.CLES if pr is not None]
        add("  Predicats : papers_encode SEUL -- papers_repare.py absent.")
        add("  Cinq cles reparees le 19/08 vont donc ressortir fausses.")
    add("")

    # --- la coupure se deduit sur les TICKETS, une seule fois. Les
    # populations de signaux en HERITENT : les quatre effectifs de
    # reference sont comptes au niveau ticket, les chercher dans une
    # population dedoublonnee revenait a exiger l impossible -- c est
    # ce qui a fait sortir zero partout au premier essai.
    CP = coupure_deduite(rails, PE, "US")
    add("=" * 96)
    add("LA COUPURE, DEDUITE SUR LES TICKETS ET HERITEE PAR LES SIGNAUX")
    add("=" * 96)
    add("  %s" % (CP or "NON DEDUCTIBLE -- tout ce qui suit compte le total"))
    add("")

    parpop = dict(pops)
    add("=" * 96)
    add("CHAQUE CLE A LA COMBINAISON QUE LE PANNEAU ANNONCE")
    add("=" * 96)
    add("  On ne cherche pas la meilleure des vingt-quatre combinaisons :")
    add("  avec assez d essais une cle tombe juste par accident. On teste")
    add("  celle que le CODE annonce, et un echec devient alors une")
    add("  information plutot qu une invitation a essayer autre chose.")
    add("")
    add("  %-13s %5s %-9s %-4s %8s %8s %8s"
        % ("CLE", "N", "POP", "COL", "rails", "churn", "verdict"))
    add("  " + "-" * 62)
    bilan = {}
    for cle, n, pred in cles:
        genre, col_fixe = SECTIONS.get(cle, (None, None))
        if genre is None:
            add("  %-13s %5d %-9s %-4s %8s %8s  hors panneau"
                % (cle, n, "?", "?", "-", "-"))
            bilan[cle] = None
            continue
        noms = (("rails", "churn") if genre == "trades"
                else ("rails/sig", "churn/sig"))
        cols = [col_fixe] if col_fixe else ["US", "EUR", "ALL"]
        ok = []
        vus = {}
        for col in cols:
            for nom in noms:
                pop = parpop.get(nom) or []
                v = compte(pop, pred, col, CP, PE)
                vus[(nom, col)] = v
                if v == n:
                    ok.append("%s/%s" % (nom, col))
        principal = cols[0] if col_fixe else "US"
        add("  %-13s %5d %-9s %-4s %8d %8d  %s"
            % (cle, n, genre, principal,
               vus.get((noms[0], principal), 0),
               vus.get((noms[1], principal), 0),
               ("EXACT " + ", ".join(ok)) if ok else "aucune"))
        bilan[cle] = ok

    add("")
    justes = [c for c, v in bilan.items() if v]
    add("  %d cles sur %d tombent exactement la ou le code les annonce."
        % (len(justes), len(cles)))
    add("")

    # --- par famille : une cause commune vaut mieux qu un succes isole
    add("=" * 96)
    add("PAR FAMILLE -- une explication qui tient pour TOUTE une section")
    add("=" * 96)
    add("  Une cle qui tombe juste seule peut le devoir au hasard. Une")
    add("  section entiere qui tombe juste ne le peut pas.")
    add("")
    FAM = [
        ("ecartement    (trades, session)",
         ["TC_CLEAN", "TC_MIXED", "MID_CLEAN", "WIDE_CLEAN"]),
        ("par TF        (trades, session)",
         ["M1_T_CL", "M1_S_CH", "M3_T_MX", "M5_T_CL", "M15_T_CL",
          "M15_T_MX"]),
        ("accords TF    (trades, session)",
         ["M1M15", "M1M3M5M15", "M3M5M15"]),
        ("hlc vue A     (trades, session)",
         ["M1_ALBU_CL", "M15_ALBU_CL", "M15_SPL_CL", "M15_SCA_MX"]),
        ("hlc vue B     (trades, ALL)", ["M15_LEAD", "M5_DIVG"]),
        ("hlc vue C     (trades, ALL)",
         ["M3_CONV_CL", "M5_DIV_CL", "M15_CONV_MX"]),
        ("leader        (trades, session)",
         ["US30_BE_CL", "US30_BE_MX", "US500_BU_CL"]),
        ("vs pack       (SIGNAUX, ALL)", ["M5_AGA_CH", "C_M15_VENTE"]),
        ("nest          (SIGNAUX, ALL)",
         ["M5_ET_YES", "M5_ET_NO_A", "M5_ET_NO_C", "M15_NO_MX"]),
        ("trajectoire   (SIGNAUX, ALL)", ["M5_WIDE_CL", "M15_WIDE_CL"]),
        ("RSI           (hors panneau)", ["RSI_M1_BU", "RSI_M15_BU"]),
    ]
    connues = set(c for c, _n, _p in cles)
    for nom, membres in FAM:
        m = [c for c in membres if c in connues]
        if not m:
            continue
        bons = [c for c in m if bilan.get(c)]
        etat = ("TOUTE la section" if len(bons) == len(m)
                else ("aucune" if not bons else "%d sur %d" % (len(bons),
                                                              len(m))))
        add("  %-34s %-16s %s" % (nom, etat,
                                  ", ".join(c for c in m if not bilan.get(c))))
    add("")

    if a.cle:
        add("")
        add("=" * 96)
        add("DETAIL -- %s" % a.cle)
        add("=" * 96)
        trouve = [(c, n, pr) for c, n, pr in cles if c == a.cle]
        if not trouve:
            add("  Cle inconnue.")
        else:
            _c, n, pred = trouve[0]
            add("  effectif annonce : %d" % n)
            for nom, pop in pops:
                if not pop:
                    continue
                for col in ("US", "EUR", "ALL"):
                    cp = coupure_deduite(pop, PE, col)
                    v = compte(pop, pred, col, cp, PE)
                    add("  %-12s %-4s coupure %-21s %6d  %s"
                        % (nom, col, cp or "-", v,
                           "EXACT" if v == n else "%+d" % (v - n)))
    add("")
    add("=" * 96)
    add("  Ce script n a rien ecrit et n a pris aucun trade.")
    add("=" * 96)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
