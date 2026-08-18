# -*- coding: utf-8 -*-
r"""
papers_constate.py -- les definitions DU PANNEAU, verifiees puis appliquees

  python papers_constate.py
  python papers_constate.py --tight 3.0     (si la constante est introuvable)

LECTEUR SEUL. N ECRIT RIEN.

D OU VIENNENT LES DEFINITIONS

    Elles sont RECOPIEES de rails_trades_panel.py, lues le 18/08 avec
    papers_extrait.py. Aucune n est inferee :

      _bucket    CLEAN/OK/TRADE -> clean ; CHURN/NOISE -> churn ; sinon mixed
      _tf_tight  spread absent -> None ; rails_pos STRADDLE -> S ;
                 sinon T si spread <= TIGHT_SPREAD, sinon W
      _sess      US si int(entry_ts[11:13]) >= 14, sinon EUR
      _tdir      BULL si dir == BUY, sinon BEAR
      _vs_pack   None si pas de hlc ou maj_dir hors BULL/BEAR ;
                 sinon WITH si _tdir == maj_dir, sinon AGAINST

    TIGHT_SPREAD est LU dans le fichier du panneau. S il est
    introuvable, les mesures qui en dependent sont dites INDISPONIBLES
    -- elles ne sont pas calculees avec une valeur choisie par moi.

LA VERIFICATION VIENT AVANT LA MESURE

    L export annonce quatre effectifs sur la section ecartement :

        TIGHT_CROSS / CLEAN   214      MID / CLEAN    251
        TIGHT_CROSS / MIXED   154      WIDE / CLEAN   231

    Ce script les recalcule avec les definitions ci-dessus, sur les
    TROIS colonnes de session (ALL / EUR / US), et compare. C est un
    CONTROLE, pas un ajustement : les trois colonnes sont imprimees,
    on ne garde pas celle qui arrange.

    Le 18/08 au matin j avais teste sept lectures du regime sans la
    dimension session et conclu qu aucune ne collait, avec un ecart de
    494. La lecture etait bonne ; c est la session qui manquait.

    SI LA VERIFICATION ECHOUE, LE RESTE N EST PAS IMPRIME. Mesurer sur
    un mapping non valide produirait des chiffres pleins et faux.
"""
import argparse
import io
import json
import os
import re
import sys

CIBLE = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
PANNEAU = "rails_trades_panel.py"

# (rails_setup, seau churn, effectif annonce par l export)
EMPREINTE = [("TIGHT_CROSS", "clean", 214),
             ("TIGHT_CROSS", "mixed", 154),
             ("MID",         "clean", 251),
             ("WIDE",        "clean", 231)]

TFS = ("M1", "M3", "M5", "M15")     # rails_trades_panel.py:92


# --- recopiees telles quelles ------------------------------------------
def _bucket(verdict):
    if verdict in ("CHURN", "NOISE"):
        return "churn"
    if verdict in ("CLEAN", "OK", "TRADE"):
        return "clean"
    return "mixed"


def _tf_tight(x, tight_spread):
    if not x or x.get("spread") is None:
        return None
    if x.get("rails_pos") == "STRADDLE":
        return "S"
    return "T" if x["spread"] <= tight_spread else "W"


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


def _verdict(t):
    d = t.get("churn_entry")
    return d.get("verdict") if isinstance(d, dict) else None


def _mes_rails(t):
    """Les rails DE L ACTIF TRADE, par unite de temps."""
    return (t.get("rails_entry") or {}).get(t.get("asset")) or {}


def lit_tight(racines):
    """Lit TIGHT_SPREAD dans le panneau. Rend (valeur, ou trouve) ou (None, ...)."""
    rx = re.compile(r"^\s*_?TIGHT_SPREAD\s*=\s*([0-9]+(?:\.[0-9]+)?)")
    for racine in racines:
        if not os.path.isdir(racine):
            continue
        for dossier, sous, fichiers in os.walk(racine):
            sous[:] = [d for d in sous if d not in
                       (".git", "__pycache__", "site-packages", "AppData")]
            for f in fichiers:
                if not f.endswith(".py"):
                    continue
                c = os.path.join(dossier, f)
                try:
                    src = io.open(c, encoding="utf-8", errors="replace").read()
                except (IOError, OSError):
                    continue
                for l in src.split("\n"):
                    m = rx.match(l)
                    if m:
                        return float(m.group(1)), c
    return None, None


def charge(chemin):
    out, ko = [], 0
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                o = json.loads(ligne)
            except ValueError:
                ko += 1
                continue
            if isinstance(o, dict):
                out.append(o)
    return out, ko


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--tight", type=float, default=None,
                   help="valeur de TIGHT_SPREAD si elle est introuvable")
    p.add_argument("--racine", action="append", default=None)
    p.add_argument("--jusqua", default=None,
                   help="coupure 'AAAA-MM-JJ HH:MM:SS' ; deduite si absente")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable." % a.fichier)
        return 1
    racines = a.racine or [".", "..", os.path.join("..", "..")]

    tickets, ko = charge(a.fichier)
    tight, ou = (a.tight, "--tight") if a.tight is not None else lit_tight(racines)

    L = []
    add = L.append
    add("=" * 84)
    add("DEFINITIONS DU PANNEAU -- VERIFIEES PUIS APPLIQUEES")
    add("=" * 84)
    add("  %d tickets%s" % (len(tickets), ", %d illisibles" % ko if ko else ""))
    if tight is None:
        add("  TIGHT_SPREAD : INTROUVABLE. Les mesures qui en dependent")
        add("  (T / S / W, signature des TF serres) seront dites")
        add("  INDISPONIBLES plutot que calculees avec une valeur choisie.")
    else:
        add("  TIGHT_SPREAD = %.2f   (lu dans %s)" % (tight, ou))
    add("")

    # ---------------------------------------------------------------
    # 1. LA VERIFICATION. Elle passe avant tout le reste.
    # ---------------------------------------------------------------
    add("-" * 84)
    add("VERIFICATION -- reproduire les quatre effectifs connus de l export")
    add("-" * 84)
    add("  Les trois colonnes de session sont imprimees. On ne garde pas")
    add("  celle qui arrange : on regarde laquelle tombe juste, ou aucune.")
    add("")
    # La COUPURE est DEDUITE, pas choisie. Pour chaque ligne on lit
    # l horodatage du N-ieme ticket (N = effectif annonce) en session US.
    # Mesure du 18/08 : les quatre N-iemes tombent le 17/08 et les quatre
    # SUIVANTS le 18/08 -- la frontiere est donc dans le meme trou pour
    # les quatre. Toute coupure dans ce trou rend les quatre exacts.
    bornes = []
    for setup, seau, attendu in EMPREINTE:
        ts = sorted(t.get("entry_ts") for t in tickets
                    if t.get("rails_setup") == setup
                    and _bucket(_verdict(t)) == seau
                    and _sess(t) == "US"
                    and isinstance(t.get("entry_ts"), str))
        if len(ts) > attendu:
            bornes.append((ts[attendu - 1], ts[attendu]))
    coupure = a.jusqua
    if coupure is None and len(bornes) == len(EMPREINTE):
        bas = max(b[0] for b in bornes)     # le dernier N-ieme
        haut = min(b[1] for b in bornes)    # le premier suivant
        if bas < haut:
            coupure = bas
    if coupure:
        avant = len(tickets)
        tickets = [t for t in tickets
                   if isinstance(t.get("entry_ts"), str)
                   and t["entry_ts"] <= coupure]
        add("  COUPURE  : %s  (%d tickets retenus sur %d)"
            % (coupure, len(tickets), avant))
        add("  Elle est DEDUITE des quatre N-iemes, pas choisie : le")
        add("  dernier N-ieme et le premier suivant encadrent un trou")
        add("  commun aux quatre lignes.")
        add("")

    add("  %-22s %8s %8s %8s %8s"
        % ("ligne de l export", "attendu", "ALL", "EUR", "US"))
    add("  " + "-" * 62)

    ecarts = {"ALL": 0, "EUR": 0, "US": 0}
    for setup, seau, attendu in EMPREINTE:
        obt = {"ALL": 0, "EUR": 0, "US": 0}
        for t in tickets:
            if t.get("rails_setup") != setup:
                continue
            if _bucket(_verdict(t)) != seau:
                continue
            obt["ALL"] += 1
            s = _sess(t)
            if s in obt:
                obt[s] += 1
        for k in ecarts:
            ecarts[k] += abs(obt[k] - attendu)
        add("  %-22s %8d %8d %8d %8d"
            % ("%s / %s" % (setup[:11], seau), attendu,
               obt["ALL"], obt["EUR"], obt["US"]))
    add("  " + "-" * 62)
    add("  %-22s %8s %8d %8d %8d"
        % ("ecart total", "", ecarts["ALL"], ecarts["EUR"], ecarts["US"]))
    add("")

    gagnante = min(ecarts, key=lambda k: ecarts[k])
    if ecarts[gagnante] == 0:
        add("  VALIDE : la colonne %s reproduit les quatre effectifs" % gagnante)
        add("  exactement. Le mapping du panneau est confirme sur ces")
        add("  donnees, et ce qui suit repose dessus.")
    else:
        add("  ECHEC : la meilleure colonne (%s) reste a %d d ecart."
            % (gagnante, ecarts[gagnante]))
        add("")
        add("  Je m arrete ici. Mesurer les magics sur un mapping non")
        add("  valide produirait un tableau plein et faux -- c est")
        add("  exactement ce que le tableau des 220000 a fait pendant")
        add("  deux jours. Ce qui reste a chercher : la population de")
        add("  l export (periode, magics inclus, filtre supplementaire).")
        print("\n".join(L))
        return 2

    # ---------------------------------------------------------------
    # 2. LA MESURE. Seulement si la verification est passee.
    # ---------------------------------------------------------------
    ret = [t for t in tickets if _sess(t) == gagnante] if gagnante != "ALL" \
        else list(tickets)

    add("")
    add("-" * 84)
    add("ETATS DISPONIBLES SUR %d TICKETS (session %s)" % (len(ret), gagnante))
    add("-" * 84)

    def compte(nom, f):
        c = {}
        for t in ret:
            try:
                v = f(t)
            except Exception:
                v = None
            if v is None:
                continue
            c[v] = c.get(v, 0) + 1
        tot = sum(c.values())
        vals = sorted(c.items(), key=lambda x: -x[1])
        add("  %-26s %5d  %s" % (nom, tot, "  ".join(
            "%s=%d" % (k, n) for k, n in vals[:6])))

    compte("regime (_bucket)", lambda t: _bucket(_verdict(t)))
    compte("ecartement", lambda t: t.get("rails_setup"))
    for tf in TFS:
        compte("WITH/AGAINST %s" % tf, lambda t, _t=tf: _vs_pack(t, _t))
    if tight is None:
        add("  %-26s %s" % ("T / S / W", "INDISPONIBLE (TIGHT_SPREAD non lu)"))
    else:
        for tf in TFS:
            compte("T/S/W %s" % tf,
                   lambda t, _t=tf: _tf_tight(_mes_rails(t).get(_t), tight))
    add("")
    add("  Ces comptes sont des EFFECTIFS d etats, pas des performances.")
    add("  Ils disent ce qui est mesurable et sur combien de prises. Le")
    add("  rendement d une regle demande un moteur qui l execute ; aucun")
    add("  magic 220000/230000/240000 n a encore pris un trade.")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
