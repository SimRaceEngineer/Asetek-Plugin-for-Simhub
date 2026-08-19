# -*- coding: utf-8 -*-
r"""
papers_population.py -- laquelle des quatre populations produit l export

  python papers_population.py
  python papers_population.py --cle M5_AGA_CH

LECTEUR SEUL. N ECRIT RIEN, NE PREND AUCUN TRADE.

LE PROBLEME, ET POURQUOI IL N EST NI LA COUPURE NI LE PREDICAT

    Vingt cles sur trente-cinq retombent exactement sur leur effectif
    annonce. Les quinze autres echouent, et huit d entre elles viennent
    de sections que le panneau calcule au niveau SIGNAL --
    _section_vs_pack, _section_mtf_nest, _section_mom.

    _load_trades (rails_trades_panel.py:119) fusionne DEUX fichiers :

        for path in (_ARCHIVE, _TRADES):
            ...
            merged[k] = r        # a ticket egal, le vivant ecrase

    soit docs\churn_trades\churn_trades_archive.jsonl PUIS
    churn_trades.jsonl, jusqu a 20 000 lignes. Nous lisons
    tickets_rails.jsonl, 4 681 lignes. Ce n est pas le meme ensemble.

    Et _signals (ligne 694) regroupe les JUMEAUX -- mais seulement les
    familles 206 et 207 (magic // 1000), par (actif, sens, magic % 1000,
    tranche de 30 s). Tout le reste compte pour un.

    Deux effets en sens CONTRAIRE : une base plus large, un
    dedoublonnage qui la reduit. C est pourquoi certaines cles debordent
    et d autres manquent -- une seule explication ne pouvait pas rendre
    compte des deux.

CE QUE FAIT CE SCRIPT

    Il ne choisit pas la population : il les essaie toutes les quatre,
    sur les trois colonnes de session, et laisse les effectifs annonces
    designer la bonne.

        rails         tickets_rails.jsonl, ce qu on lit aujourd hui
        churn         churn_trades.jsonl + son archive, fusionnes
        rails/sig     rails, jumeaux regroupes
        churn/sig     churn + archive, jumeaux regroupes

    Pour chacune, la coupure est DEDUITE comme dans papers_constate --
    le trou commun aux quatre effectifs de la section ecartement -- puis
    les 35 cles sont comptees. La population qui en rend le plus est la
    bonne, et ce n est pas un avis : c est un decompte.

LA SEULE CHOSE QUE JE SUPPOSE, ET ELLE EST MARQUEE

    _signals appelle _ts_epoch, que je n ai pas extraite. Je la
    reimplemente comme la conversion evidente d un 'AAAA-MM-JJ
    HH:MM:SS' en secondes. Un decalage constant de base ne changerait
    QUE les paires a cheval sur une frontiere de 30 s -- le script
    compte donc les groupes formes et le dit, pour qu une erreur de
    base se voie au lieu de se cacher.
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
    cles = [(c, n, pr) for c, _l, n, pr, _x in PE.CLES if pr is not None]

    add("=" * 96)
    add("COMBIEN DE CLES CHAQUE POPULATION REND EXACTEMENT")
    add("=" * 96)
    add("  %-12s %-5s %-21s %8s" % ("POPULATION", "COL", "COUPURE DEDUITE",
                                    "EXACTES"))
    add("  " + "-" * 60)
    detail = {}
    for nom, pop in pops:
        if not pop:
            continue
        for col in ("US", "EUR", "ALL"):
            cp = coupure_deduite(pop, PE, col)
            justes = []
            for cle, n, pred in cles:
                if compte(pop, pred, col, cp, PE) == n:
                    justes.append(cle)
            detail[(nom, col)] = justes
            add("  %-12s %-5s %-21s %5d / %d"
                % (nom, col, cp or "aucune -- compte TOTAL",
                   len(justes), len(cles)))
    add("")

    if not detail:
        add("  Aucune population exploitable.")
        print("\n".join(L))
        return 1

    meilleur = max(detail.items(), key=lambda kv: len(kv[1]))
    add("  MEILLEURE : %s / %s -- %d cles sur %d."
        % (meilleur[0][0], meilleur[0][1], len(meilleur[1]), len(cles)))
    add("")

    # --- ce que chaque cle prefere
    add("=" * 96)
    add("PAR CLE -- ou elle tombe juste, et nulle part sinon")
    add("=" * 96)
    ou = {}
    for (nom, col), justes in detail.items():
        for c in justes:
            ou.setdefault(c, []).append("%s/%s" % (nom, col))
    jamais = []
    for cle, n, pred in cles:
        if cle in ou:
            add("  %-13s n=%-5d %s" % (cle, n, ", ".join(sorted(ou[cle]))))
        else:
            jamais.append((cle, n))
    add("")
    if jamais:
        add("  AUCUNE POPULATION NE LES REND (%d) :" % len(jamais))
        for cle, n in jamais:
            add("    %-13s n=%d" % (cle, n))
        add("")
        add("  Pour celles-la, ce n est ni la population, ni la coupure,")
        add("  ni la colonne. C est le predicat, et il faudra le relire")
        add("  dans le panneau plutot que de continuer a l essayer.")

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
