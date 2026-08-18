# -*- coding: utf-8 -*-
r"""
papers_encode.py -- les 36 cles de l export en PREDICATS, chacun verifie

  python papers_encode.py
  python papers_encode.py --magics      (ajoute les 46 magics croises)

LECTEUR SEUL. N ECRIT RIEN.

CE QUI REND CE FICHIER VERIFIABLE

    Chaque cle de l export porte un EFFECTIF ANNONCE : TC_CLEAN dit
    214, M15_T_CL dit 441, M5_AGA_CH dit 365. Ces nombres ne viennent
    pas de nous.

    Donc chaque predicat que j ecris se controle contre son propre
    nombre. Un predicat faux ne tombe pas juste par hasard sur 441.
    Le script imprime, pour chaque cle, le compte obtenu sur les trois
    colonnes de session et l ecart a l effectif annonce. Une cle qui ne
    retombe pas sur son nombre est declaree NON VALIDEE et EXCLUE des
    croisements -- pas corrigee jusqu a ce qu elle tombe juste.

    C est le meme principe que la verification de papers_constate, mais
    applique 36 fois au lieu de 4.

LES DEFINITIONS SONT CELLES DU PANNEAU

    Recopiees de rails_trades_panel.py (papers_extrait.py, 18/08) :
    _bucket, _tf_tight, _tf_sig, _sess, _tdir, _vs_pack. TIGHT_SPREAD
    vaut 15.0 -- verifie present a l identique dans le panneau
    (ligne 90) et dans churn_trade_logger (ligne 59).

CINQ CLES NE SONT PAS ENCODEES, ET C EST DIT

    M5_ET_YES, M5_ET_NO_A, M5_ET_NO_C, M15_NO_MX  dependent du `nest`
    (YES/NO), calcule par une fonction de rails_trades_panel autour de
    la ligne 846 que je n ai pas encore extraite. L etoile, elle, n est
    qu un caractere marquant l ancre M5 -- ce n est pas la condition.

    P_M15_BULLP depend des pentes (wt1_slope), calculees sur K barres
    dans churn_regime.py et NON figees dans le ticket.

    Elles bloquent six magics : 220001, 220005, 220009, 220010,
    230108, 230208. Les quarante autres sont encodables.

CE QUE CE SCRIPT NE FAIT PAS

    Il ne prend aucun trade et n ecrit aucun journal. Il dit quels
    predicats sont justes et quels sont les VRAIS effectifs croises --
    ceux que `agrege()` estimait jusqu ici par un minimum.
"""
import argparse
import io
import json
import os
import sys

CIBLE = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
TIGHT_SPREAD = 15.0                  # rails_trades_panel.py:90
TFS = ("M1", "M3", "M5", "M15")      # rails_trades_panel.py:92


# --- recopiees du panneau ---------------------------------------------
def _bucket(v):
    if v in ("CHURN", "NOISE"):
        return "churn"
    if v in ("CLEAN", "OK", "TRADE"):
        return "clean"
    return "mixed"


def _tf_tight(x):
    if not x or x.get("spread") is None:
        return None
    if x.get("rails_pos") == "STRADDLE":
        return "S"
    return "T" if x["spread"] <= TIGHT_SPREAD else "W"


def _sess(t):
    ts = t.get("entry_ts") or ""
    try:
        return "US" if int(ts[11:13]) >= 14 else "EUR"
    except Exception:
        return "?"


def _tdir(s):
    return "BULL" if s.get("dir") == "BUY" else "BEAR"


def _vs_pack(s, tf):
    hc = (s.get("hlc_churn_entry") or {}).get(tf)
    if not hc:
        return None
    maj = hc.get("maj_dir")
    if maj not in ("BULL", "BEAR"):
        return None
    return "WITH" if _tdir(s) == maj else "AGAINST"


# --- acces ------------------------------------------------------------
def ver(t):
    d = t.get("churn_entry")
    return _bucket(d.get("verdict")) if isinstance(d, dict) else None


def hlc(t, tf, champ):
    d = (t.get("hlc_churn_entry") or {}).get(tf)
    return d.get(champ) if isinstance(d, dict) else None


def moi(t, tf):
    """Les rails DE L ACTIF TRADE, pour une unite de temps."""
    return ((t.get("rails_entry") or {}).get(t.get("asset")) or {}).get(tf)


def sig(t):
    """_tf_sig : signature des TF serres de l actif trade, ex 'M1+M3'."""
    a = (t.get("rails_entry") or {}).get(t.get("asset")) or {}
    tight = [tf for tf in TFS if _tf_tight(a.get(tf)) == "T"]
    return "+".join(tight) if tight else "aucun-tight"


# ======================================================================
# LES 36 CLES. (cle, libelle, n annonce, predicat ou None, note)
# Un predicat None = cle NON ENCODEE, exclue des croisements.
# ======================================================================
def _c(seau):
    return lambda t: ver(t) == seau


CLES = [
 ("TC_CLEAN",   "TIGHT_CROSS / CLEAN", 214,
  lambda t: t.get("rails_setup") == "TIGHT_CROSS" and ver(t) == "clean", ""),
 ("TC_MIXED",   "TIGHT_CROSS / MIXED", 154,
  lambda t: t.get("rails_setup") == "TIGHT_CROSS" and ver(t) == "mixed", ""),
 ("MID_CLEAN",  "MID / CLEAN", 251,
  lambda t: t.get("rails_setup") == "MID" and ver(t) == "clean", ""),
 ("WIDE_CLEAN", "WIDE / CLEAN", 231,
  lambda t: t.get("rails_setup") == "WIDE" and ver(t) == "clean", ""),

 ("M1_T_CL",  "M1 T / CLEAN", 299,
  lambda t: _tf_tight(moi(t, "M1")) == "T" and ver(t) == "clean", ""),
 ("M1_S_CH",  "M1 S / CHURN", 295,
  lambda t: _tf_tight(moi(t, "M1")) == "S" and ver(t) == "churn", ""),
 ("M3_T_MX",  "M3 T / MIXED", 271,
  lambda t: _tf_tight(moi(t, "M3")) == "T" and ver(t) == "mixed", ""),
 ("M5_T_CL",  "M5 T / CLEAN", 401,
  lambda t: _tf_tight(moi(t, "M5")) == "T" and ver(t) == "clean", ""),
 ("M15_T_CL", "M15 T / CLEAN", 441,
  lambda t: _tf_tight(moi(t, "M15")) == "T" and ver(t) == "clean", ""),
 ("M15_T_MX", "M15 T / MIXED", 359,
  lambda t: _tf_tight(moi(t, "M15")) == "T" and ver(t) == "mixed", ""),

 ("M1M15",     "M1+M15 / CLEAN", 24,
  lambda t: sig(t) == "M1+M15" and ver(t) == "clean", ""),
 ("M1M3M5M15", "M1+M3+M5+M15 / CLEAN", 62,
  lambda t: sig(t) == "M1+M3+M5+M15" and ver(t) == "clean", ""),
 ("M3M5M15",   "M3+M5+M15 / MIXED", 38,
  lambda t: sig(t) == "M3+M5+M15" and ver(t) == "mixed", ""),

 ("M1_ALBU_CL",  "M1 ALIGNED_BULL / CLEAN", 211,
  lambda t: hlc(t, "M1", "consensus") == "ALIGNED_BULL" and ver(t) == "clean", ""),
 ("M15_ALBU_CL", "M15 ALIGNED_BULL / CLEAN", 167,
  lambda t: hlc(t, "M15", "consensus") == "ALIGNED_BULL" and ver(t) == "clean", ""),
 ("M15_SPL_CL",  "M15 SPLIT / CLEAN", 243,
  lambda t: hlc(t, "M15", "consensus") == "SPLIT" and ver(t) == "clean", ""),
 ("M15_SCA_MX",  "M15 SCATTER / MIXED", 73,
  lambda t: hlc(t, "M15", "consensus") == "SCATTER" and ver(t) == "mixed", ""),

 ("M5_WIDE_CL",  "M5 WIDENING / CLEAN", 355,
  lambda t: hlc(t, "M5", "self_mom") == "WIDENING" and ver(t) == "clean", ""),
 ("M15_WIDE_CL", "M15 WIDENING / CLEAN", 301,
  lambda t: hlc(t, "M15", "self_mom") == "WIDENING" and ver(t) == "clean", ""),

 ("M3_CONV_CL",  "M3 CONVERGING / CLEAN", 84,
  lambda t: hlc(t, "M3", "transition") == "CONVERGING" and ver(t) == "clean", ""),
 ("M5_DIV_CL",   "M5 DIVERGING / CLEAN", 46,
  lambda t: hlc(t, "M5", "transition") == "DIVERGING" and ver(t) == "clean", ""),
 ("M15_CONV_MX", "M15 CONVERGING / MIXED", 53,
  lambda t: hlc(t, "M15", "transition") == "CONVERGING" and ver(t) == "mixed", ""),

 ("M15_LEAD", "M15 leader / CLEAN", 313,
  lambda t: hlc(t, "M15", "self_role") == "leader" and ver(t) == "clean", ""),
 ("M5_DIVG",  "M5 divergent / CLEAN", 190,
  lambda t: hlc(t, "M5", "self_role") == "divergent" and ver(t) == "clean", ""),

 ("M5_AGA_CH",   "M5 AGAINST / CHURN", 365,
  lambda t: _vs_pack(t, "M5") == "AGAINST" and ver(t) == "churn", ""),
 ("C_M15_VENTE", "M15 CONFLIT vente", 358,
  lambda t: _vs_pack(t, "M15") == "AGAINST" and t.get("dir") == "SELL",
  "CONFLIT lu comme AGAINST"),

 ("US30_BE_CL",  "US30 BEAR / CLEAN", 124,
  lambda t: t.get("asset") == "US30" and t.get("dir") == "SELL"
  and ver(t) == "clean", ""),
 ("US30_BE_MX",  "US30 BEAR / MIXED", 107,
  lambda t: t.get("asset") == "US30" and t.get("dir") == "SELL"
  and ver(t) == "mixed", ""),
 ("US500_BU_CL", "US500 BULL / CLEAN", 108,
  lambda t: t.get("asset") == "US500" and t.get("dir") == "BUY"
  and ver(t) == "clean", ""),

 ("RSI_M1_BU",  "M1 bull RSI dedans / achat", 171,
  lambda t: hlc(t, "M1", "maj_dir") == "BULL" and t.get("dir") == "BUY"
  and (moi(t, "M1") or {}).get("rsi_pos") == "INSIDE",
  "bull lu comme maj_dir"),
 ("RSI_M15_BU", "M15 bull RSI au-dessus / achat", 186,
  lambda t: hlc(t, "M15", "maj_dir") == "BULL" and t.get("dir") == "BUY"
  and (moi(t, "M15") or {}).get("rsi_pos") == "ABOVE",
  "bull lu comme maj_dir"),

 # --- non encodees ---------------------------------------------------
 ("M5_ET_YES",   "M5 * YES WITH / MIXED", 43, None, "nest YES non extrait"),
 ("M5_ET_NO_A",  "M5 * NO AGAINST / CHURN", 104, None, "nest NO non extrait"),
 ("M5_ET_NO_C",  "M5 * NO / CLEAN", 290, None, "nest NO non extrait"),
 ("M15_NO_MX",   "M15 NO / MIXED", 396, None, "nest NO non extrait"),
 ("P_M15_BULLP", "M15 bull+", 248, None, "pente non figee dans le ticket"),
]


def charge(chemin):
    out, ko = [], 0
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


def coupure_deduite(tickets):
    """Meme deduction que papers_constate : le trou commun aux quatre."""
    ref = [("TIGHT_CROSS", "clean", 214), ("TIGHT_CROSS", "mixed", 154),
           ("MID", "clean", 251), ("WIDE", "clean", 231)]
    bornes = []
    for setup, seau, n in ref:
        ts = sorted(t["entry_ts"] for t in tickets
                    if t.get("rails_setup") == setup and ver(t) == seau
                    and _sess(t) == "US" and isinstance(t.get("entry_ts"), str))
        if len(ts) > n:
            bornes.append((ts[n - 1], ts[n]))
    if len(bornes) != len(ref):
        return None
    bas, haut = max(b[0] for b in bornes), min(b[1] for b in bornes)
    return bas if bas < haut else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--jusqua", default=None)
    p.add_argument("--magics", action="store_true",
                   help="ajoute les vrais effectifs croises des magics")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable." % a.fichier)
        return 1
    tickets, ko = charge(a.fichier)

    coupure = a.jusqua or coupure_deduite(tickets)
    if coupure:
        tickets = [t for t in tickets
                   if isinstance(t.get("entry_ts"), str)
                   and t["entry_ts"] <= coupure]

    L = []
    add = L.append
    add("=" * 88)
    add("LES 36 CLES DE L EXPORT, ENCODEES ET VERIFIEES UNE PAR UNE")
    add("=" * 88)
    add("  %d tickets retenus%s" % (len(tickets),
                                    "  (coupure %s)" % coupure if coupure else ""))
    add("  Chaque cle porte un effectif ANNONCE par l export. Un predicat")
    add("  faux ne retombe pas dessus par hasard. Une cle qui n y retombe")
    add("  pas est declaree NON VALIDEE et EXCLUE des croisements.")
    add("")
    add("  %-13s %-30s %6s %6s %6s %6s  %s"
        % ("CLE", "LIBELLE", "annonce", "ALL", "EUR", "US", "verdict"))
    add("  " + "-" * 84)

    valides = {}
    n_ok = n_ko = n_non = 0
    for cle, lib, attendu, pred, note in CLES:
        if pred is None:
            n_non += 1
            add("  %-13s %-30s %6d %6s %6s %6s  NON ENCODEE (%s)"
                % (cle, lib[:30], attendu, "-", "-", "-", note))
            continue
        c = {"ALL": 0, "EUR": 0, "US": 0}
        for t in tickets:
            try:
                if not pred(t):
                    continue
            except Exception:
                continue
            c["ALL"] += 1
            s = _sess(t)
            if s in c:
                c[s] += 1
        best = min(c, key=lambda k: abs(c[k] - attendu))
        ec = abs(c[best] - attendu)
        if ec == 0:
            n_ok += 1
            valides[cle] = pred
            v = "OK sur %s" % best
        else:
            n_ko += 1
            v = "NON VALIDEE (%s a %+d)" % (best, c[best] - attendu)
        add("  %-13s %-30s %6d %6d %6d %6d  %s%s"
            % (cle, lib[:30], attendu, c["ALL"], c["EUR"], c["US"], v,
               ("  [%s]" % note) if note else ""))

    add("  " + "-" * 84)
    add("  %d validees, %d non validees, %d non encodees."
        % (n_ok, n_ko, n_non))
    add("")
    add("  Une cle NON VALIDEE ne sera pas retouchee jusqu a ce qu elle")
    add("  tombe juste : ajuster un predicat en regardant son ecart, c est")
    add("  choisir la reponse. Elle sort du jeu et son magic avec.")

    if a.magics:
        add("")
        add("=" * 88)
        add("LES VRAIS EFFECTIFS CROISES")
        add("=" * 88)
        add("  agrege() estimait le croisement par le MINIMUM des effectifs.")
        add("  Voici le compte reel : combien de tickets verifient TOUTES")
        add("  les cles d un magic en meme temps.")
        add("")
        sys.path.insert(0, os.path.dirname(os.path.abspath(a.fichier)) or ".")
        try:
            import papers_optimized as po
            import papers_compare as pc
        except ImportError:
            add("  papers_optimized / papers_compare introuvables ici.")
            print("\n".join(L))
            return 0
        lignes = [(s["magic"], s["nom"], s["croise"]) for s in po.STRATEGIES]
        for d in pc.DEEPSEEK:
            for act in d["actifs"]:
                lignes.append((230000 + pc.ACTIFS[act] + d["i"],
                               d["nom"] + " (" + act + ")", d["src"]))
        add("  %-7s %-30s %7s %7s  %s"
            % ("MAGIC", "NOM", "estime", "REEL", "etat"))
        add("  " + "-" * 76)
        for magic, nom, cles in sorted(lignes):
            manque = [k for k in cles if k not in valides]
            est = po.agrege(cles)[0]
            if manque:
                add("  %-7d %-30s %7d %7s  bloque par %s"
                    % (magic, nom[:30], est, "-", ",".join(manque)))
                continue
            n = 0
            for t in tickets:
                if all(valides[k](t) for k in cles):
                    n += 1
            add("  %-7d %-30s %7d %7d  %s"
                % (magic, nom[:30], est, n,
                   "MESURE" if n >= 30 else "trop mince pour juger"))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
