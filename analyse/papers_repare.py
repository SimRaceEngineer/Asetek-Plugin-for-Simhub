# -*- coding: utf-8 -*-
r"""
papers_repare.py -- les predicats corriges par le panneau, pas par moi

  python papers_repare.py
  python papers_repare.py --coupure "2026-08-17 19:26:10"

LECTEUR SEUL. N ECRIT RIEN, NE PREND AUCUN TRADE.

CE QUE LA LECTURE DU 18/08 A DONNE

 1. LA COUPURE EST REPAREE, ET ELLE L EST PAR DEDUCTION.
    Les 15 cles justes epinglent l intervalle
      [ 2026-08-17 19:00:04 , 2026-08-18 14:09:38 )
    et la fenetre de M1_S_CH ouvre a 19:26:10, DEDANS. Une coupure a
    19:26:10 rend donc 16 cles au lieu de 15, sans en casser une seule.
    Ce n est pas un reglage : l intervalle etait impose par 15
    effectifs que nous n avons pas choisis, et le 16e y est tombe.

 2. "US30 BEAR" N EST PAS LE SENS DU TRADE.
    _section_leader (rails_trades_panel.py:419) agrege sur
    _leader_sig(t["ll_entry"]), qui rend "<leader> <leg>" a partir de
    ll_entry["M1"] -- la CONFIG LEADER. Sa legende le dit mot pour mot
    (ligne 426) : "US100 BEAR = NAS chute en tete". Je lisais
    asset=="US30" and dir=="SELL". D ou les +24, +10, et le deficit de
    US500_BU_CL : deux vocabulaires differents sous le meme mot.

 3. DEUX VUES DU PANNEAU N ONT PAS DE COLONNE DE SESSION.
    Dans _section_hlc_churn (ligne 594), la vue A (consensus) agrege
    sur ("ALL", s) -- trois colonnes. Mais la vue B (self_role, ligne
    619) et la vue C (transition, ligne 622) agregent sur "ALL"
    SEULEMENT. Les cles qui en viennent -- M15_LEAD, M5_DIVG,
    M3_CONV_CL, M5_DIV_CL, M15_CONV_MX -- n ont donc jamais eu de
    colonne US a comparer. M3_CONV_CL le montrait deja : exact sur ALL.

 4. LE NEST EST ENTIEREMENT LU (_nest_for, ligne 844).
    Il n est pas recopie ici de memoire : _ANCHOR_BELOW est EVALUE
    depuis le source du panneau au moment du run. Une constante
    recopiee est une constante qui divergera -- c est ce qui a produit
    les deux TIGHT_SPREAD du 18/08.

CE QUE CE SCRIPT FAIT

    Il teste chaque cle sur les TROIS colonnes contre son effectif
    annonce. Une cle n a qu une seule bonne colonne et un seul bon
    predicat ; si elle tombe pile sur un des trois, ce n est pas un
    choix, c est une lecture confirmee. Si elle ne tombe nulle part, il
    le dit et montre la fenetre, sans rien ajuster.
"""
import argparse
import ast
import io
import os
import re
import sys

COUPURE = "2026-08-17 19:26:10"
NOMS = ["rails_trades_panel.py"]

CONSTANTES = ["_ANCHOR_BELOW", "_ANCHOR_ORDER", "_SESS_ORDER", "ASSETS",
              "_HC_ROLE_ORDER", "_HC_CONS_ORDER", "_MOM_ORDER", "_SETUP_ORDER"]


def trouve_panneau(racines):
    for racine in racines:
        if not os.path.isdir(racine):
            continue
        for dossier, sous, fichiers in os.walk(racine):
            sous[:] = [d for d in sous if d not in
                       (".git", "__pycache__", "node_modules",
                        "site-packages", "AppData")]
            for f in fichiers:
                if f in NOMS:
                    return os.path.join(dossier, f)
    return None


def literal_apres(src, nom):
    """Evalue la valeur de `nom = <litteral>` LUE DANS LE SOURCE.

    On coupe sur les delimiteurs equilibres a partir du signe egal, puis
    on passe a ast.literal_eval -- qui refuse tout ce qui n est pas une
    constante. Rien n est execute, et rien n est recopie a la main.
    """
    m = re.search(r"^%s\s*=\s*" % re.escape(nom), src, re.M)
    if not m:
        return None, "absent du panneau"
    i = m.end()
    if i >= len(src) or src[i] not in "([{":
        j = src.find("\n", i)
        bout = src[i:j if j > 0 else len(src)]
    else:
        paires = {"(": ")", "[": "]", "{": "}"}
        ouvre = src[i]
        prof, j = 0, i
        while j < len(src):
            c = src[j]
            if c == ouvre:
                prof += 1
            elif c == paires[ouvre]:
                prof -= 1
                if prof == 0:
                    j += 1
                    break
            j += 1
        bout = src[i:j]
    try:
        return ast.literal_eval(bout.strip()), None
    except Exception as e:
        return None, "non evaluable (%s)" % e


def enclosante(lignes, k):
    ind = len(lignes[k]) - len(lignes[k].lstrip())
    for j in range(k, -1, -1):
        l = lignes[j]
        if not l.strip():
            continue
        m = re.match(r"(\s*)def\s+(\w+)\s*\(", l)
        if m and len(m.group(1)) < ind:
            return m.group(2)
    return "<module>"


def partie_source(add, chemin, consts):
    add("=" * 78)
    add("PARTIE 1 -- CE QUI MANQUAIT ENCORE, LU DANS LE PANNEAU")
    add("=" * 78)
    add("")
    if not chemin:
        add("  rails_trades_panel.py introuvable. --racine CHEMIN.")
        return
    src = io.open(chemin, encoding="utf-8", errors="replace").read()
    lignes = src.split("\n")

    add("  CONSTANTES, EVALUEES DEPUIS LE SOURCE (pas recopiees)")
    for nom in CONSTANTES:
        v, err = consts.get(nom, (None, "non lue"))
        if err:
            add("    %-16s %s" % (nom, err))
        else:
            add("    %-16s %s" % (nom, repr(v)[:500]))
    add("")

    add("  D OU VIENNENT trades ET signals")
    pat = re.compile(r"^\s*(trades|signals)\s*=|\.jsonl|def\s+(charge|_load|load|_lire|lire)\b")
    hits = [(i + 1, l.rstrip()) for i, l in enumerate(lignes) if pat.search(l)]
    for n, l in hits[:90]:
        add("    %5d  [%s]  %s" % (n, enclosante(lignes, n - 1), l.strip()[:220]))
    if len(hits) > 90:
        add("    ... %d lignes de plus" % (len(hits) - 90))
    add("")

    add("  OU LE PANNEAU PARLE DE RSI")
    rx = re.compile(r"rsi", re.I)
    rh = [(i + 1, l.rstrip()) for i, l in enumerate(lignes) if rx.search(l)]
    if not rh:
        add("    Aucune occurrence. Les deux cles RSI_* viennent donc d un")
        add("    AUTRE module -- a chercher avant de les encoder.")
    else:
        fns = []
        for n, l in rh:
            f = enclosante(lignes, n - 1)
            if f not in fns:
                fns.append(f)
            add("    %5d  [%s]  %s" % (n, f, l.strip()[:220]))
        add("")
        add("    Fonctions concernees : %s" % ", ".join(fns))
    add("")


# ======================================================================
# PARTIE 2 -- LES PREDICATS CORRIGES
# ======================================================================
def _lsig(t):
    """_leader_sig du panneau (ligne 194), sur ll_entry['M1']."""
    m1 = (t.get("ll_entry") or {}).get("M1") or {}
    leader, leg = m1.get("leader"), m1.get("leg")
    if not leader or not leg:
        return "?"
    return "%s %s" % (leader, leg)


def fabrique_nest(below_map, PE):
    """_nest_for du panneau (ligne 844). below_map vient du SOURCE."""
    def _nest_for(t, anchor):
        hce = t.get("hlc_churn_entry") or {}
        hca = hce.get(anchor)
        if not hca:
            return (None, None)
        cons, maj = hca.get("consensus"), hca.get("maj_dir")
        if cons not in ("ALIGNED_BULL", "ALIGNED_BEAR") \
                or maj not in ("BULL", "BEAR"):
            return ("NO", None)
        if hca.get("self_role") == "divergent":
            return ("NO", None)
        below = below_map.get(anchor, ())
        low_div = any((hce.get(tf) or {}).get("self_role") == "divergent"
                      for tf in below)
        return ("YES" if low_div else "NO",
                "WITH" if PE._tdir(t) == maj else "AGAINST")
    return _nest_for


def construit_cles(PE, nest):
    """Rend [(cle, n, predicat, origine)]. Origine = la ligne du panneau
    qui justifie le predicat, ou '' si inchange depuis papers_encode."""
    out = []
    remplace = {
        "US30_BE_CL": ("panneau:419 config leader, pas le sens du trade",
                       lambda t: _lsig(t) == "US30 BEAR"
                       and PE.ver(t) == "clean"),
        "US30_BE_MX": ("panneau:419 config leader",
                       lambda t: _lsig(t) == "US30 BEAR"
                       and PE.ver(t) == "mixed"),
        "US500_BU_CL": ("panneau:419 config leader",
                        lambda t: _lsig(t) == "US500 BULL"
                        and PE.ver(t) == "clean"),
    }
    for cle, lib, n, pred, _note in PE.CLES:
        if cle in remplace:
            org, p = remplace[cle]
            out.append((cle, n, p, org))
        elif pred is not None:
            out.append((cle, n, pred, ""))
    if nest is None:
        return out
    # --- les quatre cles du nest, maintenant lisibles
    def N(anchor, veut_nest, veut_dv, seau):
        def p(t):
            nz, dv = nest(t, anchor)
            if nz != veut_nest:
                return False
            if veut_dv is not None and dv != veut_dv:
                return False
            return PE.ver(t) == seau
        return p
    out += [
        ("M5_ET_YES",  43,  N("M5", "YES", "WITH", "mixed"),
         "panneau:844 _nest_for, ancre M5"),
        ("M5_ET_NO_A", 104, N("M5", "NO", "AGAINST", "churn"),
         "panneau:844 _nest_for"),
        ("M5_ET_NO_C", 290, N("M5", "NO", None, "clean"),
         "panneau:844, sens non precise dans le libelle"),
        ("M15_NO_MX",  396, N("M15", "NO", None, "mixed"),
         "panneau:844, ancre M15"),
    ]
    return out


def compte(tickets, pred, colonne, coupure, PE):
    c = 0
    for t in tickets:
        e = t.get("entry_ts")
        if not isinstance(e, str) or e > coupure:
            continue
        if colonne != "ALL" and PE._sess(t) != colonne:
            continue
        try:
            if pred(t):
                c += 1
        except Exception:
            pass
    return c


def fenetre(tickets, pred, n, colonne, PE):
    ts = []
    for t in tickets:
        e = t.get("entry_ts")
        if not isinstance(e, str):
            continue
        if colonne != "ALL" and PE._sess(t) != colonne:
            continue
        try:
            if pred(t):
                ts.append(e)
        except Exception:
            pass
    ts.sort()
    if len(ts) < n:
        return len(ts), None, None
    return len(ts), ts[n - 1], (ts[n] if len(ts) > n else None)


def partie_donnees(add, fichier, coupure, PE, nest):
    add("=" * 78)
    add("PARTIE 2 -- CHAQUE CLE CONTRE SON EFFECTIF, SUR TROIS COLONNES")
    add("=" * 78)
    add("")
    if not os.path.isfile(fichier):
        add("  Fichier introuvable : %s" % fichier)
        return
    tickets, ko = PE.charge(fichier)
    add("  %s : %d tickets, %d illisibles" % (fichier, len(tickets), ko))
    add("  Coupure : %s" % coupure)
    add("  Nest    : %s" % ("lisible" if nest else "INDISPONIBLE"))
    add("")

    cles = construit_cles(PE, nest)
    cols = ("US", "EUR", "ALL")
    add("  %-13s %5s %6s %6s %6s   %s"
        % ("CLE", "N", "US", "EUR", "ALL", "verdict"))
    add("  " + "-" * 74)
    justes, rates = [], []
    for cle, n, pred, org in cles:
        c = dict((k, compte(tickets, pred, k, coupure, PE)) for k in cols)
        bonnes = [k for k in cols if c[k] == n]
        if bonnes:
            v = "EXACT sur %s" % "/".join(bonnes)
            justes.append((cle, n, bonnes[0], org))
        else:
            v = "aucune colonne"
            rates.append((cle, n, pred, c, org))
        add("  %-13s %5d %6d %6d %6d   %s"
            % (cle, n, c["US"], c["EUR"], c["ALL"], v))
    add("")
    add("  %d cles sur %d tombent EXACTEMENT sur leur effectif annonce."
        % (len(justes), len(cles)))
    add("")

    nouvelles = [x for x in justes if x[3]]
    if nouvelles:
        add("  REPAREES PAR LA LECTURE DU PANNEAU")
        for cle, n, col, org in nouvelles:
            add("    %-13s n=%d, colonne %s -- %s" % (cle, n, col, org))
        add("")

    if rates:
        add("  ENCORE FAUSSES -- fenetre par colonne, sans rien ajuster")
        for cle, n, pred, c, org in rates:
            for k in cols:
                m, lo, hi = fenetre(tickets, pred, n, k, PE)
                if lo is None:
                    add("    %-13s %-3s N=%d jamais atteint (max %d)"
                        % (cle, k, n, m))
                else:
                    etat = ("TARD" if lo > coupure
                            else ("TOT" if hi is not None and hi <= coupure
                                  else "OK"))
                    add("    %-13s %-3s %-4s %s -> %s"
                        % (cle, k, etat, lo, hi or "(fin)"))
            add("")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", action="append", default=None)
    p.add_argument("--fichier", default=None)
    p.add_argument("--coupure", default=COUPURE)
    a = p.parse_args()

    L = []
    add = L.append
    add("=" * 78)
    add("PREDICATS CORRIGES PAR LE PANNEAU")
    add("=" * 78)
    add("")

    racines = a.racine or [".", "..", os.path.join("..", "..")]
    chemin = trouve_panneau(racines)
    consts = {}
    if chemin:
        src = io.open(chemin, encoding="utf-8", errors="replace").read()
        for nom in CONSTANTES:
            consts[nom] = literal_apres(src, nom)
    partie_source(add, chemin, consts)

    try:
        import papers_encode as PE
    except ImportError:
        add("  papers_encode.py doit etre dans le meme dossier.")
        print("\n".join(L))
        return 1

    below, err = consts.get("_ANCHOR_BELOW", (None, "panneau introuvable"))
    nest = None
    if isinstance(below, dict):
        nest = fabrique_nest(below, PE)
    else:
        add("  _ANCHOR_BELOW %s : les quatre cles du nest restent" % err)
        add("  non encodees. Aucune valeur n est supposee a leur place.")
        add("")

    partie_donnees(add, a.fichier or PE.CIBLE, a.coupure, PE, nest)
    add("=" * 78)
    add("  Ce script n a rien ecrit et n a pris aucun trade.")
    add("=" * 78)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
