# -*- coding: utf-8 -*-
"""
regime_elapsed.py -- H8 : est-ce le regime qui coute, ou l entree dans
                     le regime ?

  python regime_elapsed.py --diag
  python regime_elapsed.py
  python regime_elapsed.py --nmin 54 --tolerance 180

LECTEUR SEUL. Aucun import MT5, aucun ordre, aucune ecriture dans les
fichiers de la stack. Il ouvre trois fichiers en lecture et imprime.

CE QU IL TESTE

    H8 dit : a l interieur d un meme regime, le resultat n est pas
    constant -- les premieres minutes apres la bascule concentrent la
    perte, et le regime installe est proche de zero.

    Ni le decoupage horaire (H3) ni l etiquette de regime (H4) ne
    peuvent voir ca : tous deux supposent l etiquette stable sur sa
    duree, et diluent sur toute la plage une perte concentree sur la
    bascule.

    logs/regime_history.jsonl porte deja les deux variables qu il
    faut :

        "phase":       STABLE ou non -- l enonce direct de H8
        "elapsed_min": minutes depuis le debut du regime -- sa forme

    Plus, en cadeau, de quoi calculer la position dans le range de
    seance :

        (current_bid - session_low) / (session_high - session_low)

    ATTENTION : ce range est celui de la SEANCE (ancre sur
    session_open_15h30). Le range_pos a 7 jours affiche par les
    panneaux est un AUTRE nombre qui porte le meme nom. Les deux ne se
    comparent pas. C est ecrit dans l en-tete du tableau, pas seulement
    ici.

CE QU IL NE FAIT PAS, ET POURQUOI

    Il ne devine pas le champ de resultat. Les tickets peuvent porter
    leur PnL sous une dizaine de noms, ou ne pas le porter du tout --
    auquel cas il faut le chercher dans un second fichier, par numero
    de ticket. Le script CHERCHE, ANNONCE ce qu il a trouve, et
    s ARRETE s il ne trouve rien. Il ne moyenne jamais un champ dont il
    n est pas sur.

    Il ne masque pas les tickets qu il n a pas pu rattacher. Un ticket
    sans instantane de regime assez proche est compte a part et le
    nombre est imprime. Une jointure silencieuse qui perd la moitie de
    l echantillon donnerait des moyennes propres et fausses.

    Il ne conclut pas sous le seuil. Toute cellule sous --nmin porte un
    `?`. Le defaut est 54, qui vient du paragraphe 0 de HYPOTHESES.md :
    une comparaison annoncee d avance, sigma = 60 EUR, edge = 16 EUR.
    Pour une cellule qu on regarde parmi cent, le seuil est ~172.

LE PIEGE DEJA IDENTIFIE, ET CE QUE LE SCRIPT EN FAIT

    frg_transitions.jsonl begaye : deux bascules relevees a une minute
    d ecart, chop 52.6 et 48.2, de part et d autre d un seuil a 50 sans
    hysteresis visible. Quand le chop oscille autour du seuil -- c est
    a dire exactement dans les phases indecises qui nous interessent --
    ce journal produit des bascules qui ne correspondent a aucun
    changement de marche.

    DONC : ce script n ouvre PAS frg_transitions. Il ne lit que
    `phase` et `elapsed_min`, produits par le module de regime
    lui-meme.

    Ca ne supprime pas le probleme, ca le deplace : si `elapsed_min` se
    remet a zero a chaque bavardage du seuil, la premiere tranche sera
    peuplee de faux redemarrages. Le script imprime donc la
    distribution des durees de regime. Si la moitie des regimes durent
    moins de deux minutes, le bavardage est dans la donnee et le
    resultat ne vaut rien -- c est imprime en toutes lettres.
"""
import argparse
import collections
import io
import json
import os
import sys
from datetime import datetime

RH = os.path.join("logs", "regime_history.jsonl")
TR = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")

# Les noms sous lesquels un resultat peut se cacher. L ordre compte :
# le premier trouve gagne, et il est annonce.
CLES_PNL = ("profit", "pnl", "net", "net_eur", "resultat", "result",
            "gain", "pl", "profit_eur", "exit_pnl", "pnl_eur",
            "profit_net", "final")
CLES_SORTIE = ("exit_ts", "close_ts", "sortie_ts", "exit_time",
               "closed_at", "ts_sortie")

# Tranches de temps depuis le debut du regime. Les trois premieres sont
# serrees : c est la ou H8 attend l effet.
TRANCHES = ((0, 5), (5, 15), (15, 30), (30, 60),
            (60, 120), (120, 240), (240, 10 ** 9))

BANDES_RANGE = ((0, 20), (20, 40), (40, 60), (60, 80), (80, 101))


def _dt(s):
    """'2026-08-14 13:09:19' -> datetime, ou None."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip().replace("T", " ")
    if len(s) > 19:
        s = s[:19]
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    return None


def _nombre(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def lignes(chemin):
    if not os.path.isfile(chemin):
        return None
    out = []
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for l in f:
            l = l.strip()
            if not l:
                continue
            try:
                out.append(json.loads(l))
            except ValueError:
                continue
    return out


# ----------------------------------------------------------------- regimes

def charger_regimes(chemin):
    """[(datetime, actif, dict)] trie, par actif."""
    brut = lignes(chemin)
    if brut is None:
        return None, "introuvable"
    par_actif = collections.defaultdict(list)
    for d in brut:
        t = _dt(d.get("iso"))
        if t is None:
            continue
        reg = d.get("regimes") or {}
        if not isinstance(reg, dict):
            continue
        for actif, r in reg.items():
            if isinstance(r, dict):
                par_actif[actif].append((t, r))
    for a in par_actif:
        par_actif[a].sort(key=lambda x: x[0])
    return par_actif, None


def position_range(r):
    """(bid - bas) / (haut - bas) * 100, sur le range de SEANCE."""
    h = _nombre(r.get("session_high"))
    b = _nombre(r.get("session_low"))
    c = _nombre(r.get("current_bid"))
    if h is None or b is None or c is None:
        return None
    if h - b <= 0:
        return None
    return max(0.0, min(100.0, (c - b) / (h - b) * 100.0))


def avant(serie, t, tolerance_s):
    """Dernier instantane a <= t, si l ecart tient dans la tolerance.

    Recherche dichotomique : la serie fait 21 500 lignes et on la
    consulte une fois par ticket.
    """
    lo, hi = 0, len(serie)
    while lo < hi:
        mi = (lo + hi) // 2
        if serie[mi][0] <= t:
            lo = mi + 1
        else:
            hi = mi
    if lo == 0:
        return None, None
    ts, r = serie[lo - 1]
    ecart = (t - ts).total_seconds()
    if ecart > tolerance_s:
        return None, ecart
    return r, ecart


# ----------------------------------------------------------------- tickets

def trouver_pnl(tickets):
    """Quel champ porte le resultat ? Cherche, annonce, ou renonce."""
    freq = collections.Counter()
    for d in tickets:
        for k, v in d.items():
            if _nombre(v) is not None:
                freq[k] += 1
    n = len(tickets)
    for k in CLES_PNL:
        if freq.get(k, 0) >= 0.5 * n:
            return k, freq[k], None
    # Rien au premier niveau : on regarde un cran plus bas, mais on ne
    # descend pas plus loin -- au-dela, on tomberait sur des champs de
    # contexte qui ressemblent a des resultats sans en etre.
    freq2 = collections.Counter()
    for d in tickets:
        for k, v in d.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    if _nombre(v2) is not None:
                        freq2["%s.%s" % (k, k2)] += 1
    for k in CLES_PNL:
        for plein, c in freq2.items():
            if plein.split(".")[-1] == k and c >= 0.5 * n:
                return plein, c, None
    return None, 0, freq


def lire_pnl(d, cle):
    if "." in cle:
        a, b = cle.split(".", 1)
        sous = d.get(a)
        return _nombre(sous.get(b)) if isinstance(sous, dict) else None
    return _nombre(d.get(cle))


def setup_de(magic):
    """M 206 1 60 -> '60'. Les magics a 4 chiffres n en ont pas."""
    try:
        d = str(int(magic))
    except (TypeError, ValueError):
        return None
    return d[4:] if len(d) == 6 else None


# ----------------------------------------------------------------- tableaux

def cellule(vals, nmin):
    n = len(vals)
    if not n:
        return "%8s %6s" % ("-", "0")
    m = sum(vals) / n
    marque = "?" if n < nmin else " "
    return "%+8.2f %5d%s" % (m, n, marque)


def tableau(titre, groupes, ordre, nmin, note=None):
    print()
    print(titre)
    if note:
        print("  " + note)
    print("  " + "-" * 62)
    print("  %-26s %8s %5s  %10s" % ("", "EUR/tk", "n", "total"))
    for cle in ordre:
        vals = groupes.get(cle) or []
        n = len(vals)
        if not n:
            print("  %-26s %8s %5d" % (str(cle), "-", 0))
            continue
        tot = sum(vals)
        m = tot / n
        marque = "?" if n < nmin else " "
        print("  %-26s %+8.2f %5d%s %+10.2f" % (str(cle), m, n, marque, tot))
    print("  " + "-" * 62)


def tranche_de(minutes):
    if minutes is None:
        return None
    for a, b in TRANCHES:
        if a <= minutes < b:
            return "%d-%d min" % (a, b) if b < 10 ** 9 else "%d min et +" % a
    return None


def bande_de(pos):
    if pos is None:
        return None
    for a, b in BANDES_RANGE:
        if a <= pos < b:
            return "%d-%d %%" % (a, min(b, 100))
    return None


# ----------------------------------------------------------------- principal

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--regimes", default=RH)
    p.add_argument("--tickets", default=TR)
    p.add_argument("--nmin", type=int, default=54,
                   help="sous ce n, la cellule porte un ? (defaut 54)")
    p.add_argument("--tolerance", type=int, default=180,
                   help="ecart max, en secondes, entre l entree et "
                        "l instantane de regime (defaut 180)")
    p.add_argument("--diag", action="store_true",
                   help="ne fait que decrire les fichiers et s arreter")
    a = p.parse_args()

    par_actif, err = charger_regimes(a.regimes)
    if err:
        print("KO : %s %s" % (a.regimes, err))
        return 1
    total_r = sum(len(v) for v in par_actif.values())
    print("%s : %d instantanes, %d actifs" % (a.regimes, total_r,
                                              len(par_actif)))
    for actif in sorted(par_actif):
        s = par_actif[actif]
        print("  %-8s %6d  du %s au %s" % (actif, len(s),
                                           s[0][0].strftime("%d/%m %H:%M"),
                                           s[-1][0].strftime("%d/%m %H:%M")))

    # Le bavardage du seuil : si les regimes durent quelques secondes,
    # elapsed_min ne mesure rien.
    print()
    print("Duree des regimes (elapsed_min au moment ou il retombe a 0)")
    durees = []
    for actif, serie in par_actif.items():
        prec = None
        for _, r in serie:
            e = _nombre(r.get("elapsed_min"))
            if e is None:
                continue
            if prec is not None and e < prec:
                durees.append(prec)
            prec = e
    if durees:
        durees.sort()
        q = lambda f: durees[min(len(durees) - 1, int(len(durees) * f))]
        court = sum(1 for d in durees if d < 2.0)
        print("  %d regimes termines   median %.1f min   q25 %.1f   q75 %.1f"
              % (len(durees), q(0.5), q(0.25), q(0.75)))
        print("  sous 2 minutes : %d  (%.0f %%)"
              % (court, 100.0 * court / len(durees)))
        if court > 0.4 * len(durees):
            print("  ATTENTION : plus de 40 %% des regimes durent moins de")
            print("  deux minutes. C est le bavardage du seuil, pas le")
            print("  marche. La premiere tranche sera peuplee de faux")
            print("  redemarrages et le resultat ci-dessous ne vaut rien.")
    else:
        print("  aucune fin de regime observee -- elapsed_min ne retombe")
        print("  jamais, ou le champ est absent.")

    tickets = lignes(a.tickets)
    if tickets is None:
        print()
        print("KO : %s introuvable." % a.tickets)
        return 1
    print()
    print("%s : %d tickets" % (a.tickets, len(tickets)))

    cle, freq, toutes = trouver_pnl(tickets)
    if cle is None:
        print()
        print("ARRET : aucun champ de resultat trouve sur au moins la")
        print("moitie des tickets. Les noms cherches etaient :")
        print("  " + ", ".join(CLES_PNL))
        print()
        print("Champs numeriques presents, par frequence :")
        for k, n in sorted(toutes.items(), key=lambda x: -x[1])[:30]:
            print("  %-28s %d" % (k, n))
        print()
        print("Si le resultat vit dans un autre fichier -- trades.jsonl,")
        print("ou les CLOTURE de x60_onset -- il faut une jointure par")
        print("numero de ticket. Je ne moyenne pas un champ dont je ne")
        print("suis pas sur : c est exactement comme ca qu on fabrique")
        print("un chiffre garanti par sa methode de calcul.")
        return 2
    print("champ de resultat retenu : %s  (present sur %d/%d)"
          % (cle, freq, len(tickets)))

    if a.diag:
        print()
        print("--diag : je m arrete la.")
        return 0

    # ---- jointure
    par_phase = collections.defaultdict(list)
    par_tranche = collections.defaultdict(list)
    par_bande = collections.defaultdict(list)
    par_type = collections.defaultdict(list)
    par_setup_tranche = collections.defaultdict(list)
    ecarts = []
    sans_regime = sans_date = sans_pnl = 0

    for d in tickets:
        v = lire_pnl(d, cle)
        if v is None:
            sans_pnl += 1
            continue
        t = _dt(d.get("entry_ts"))
        if t is None:
            sans_date += 1
            continue
        actif = d.get("asset")
        serie = par_actif.get(actif)
        if not serie:
            sans_regime += 1
            continue
        r, ecart = avant(serie, t, a.tolerance)
        if r is None:
            sans_regime += 1
            continue
        ecarts.append(ecart)

        ph = r.get("phase") or "(sans phase)"
        par_phase[ph].append(v)
        par_type[r.get("type") or "(sans type)"].append(v)
        tr = tranche_de(_nombre(r.get("elapsed_min")))
        if tr:
            par_tranche[tr].append(v)
            s = setup_de(d.get("magic"))
            par_setup_tranche[("x%s" % s if s else "hors setup", tr)].append(v)
        ba = bande_de(position_range(r))
        if ba:
            par_bande[ba].append(v)

    retenus = len(ecarts)
    print()
    print("Jointure : %d tickets rattaches, %d sans instantane de regime"
          " a moins de %d s, %d sans date, %d sans resultat."
          % (retenus, sans_regime, a.tolerance, sans_date, sans_pnl))
    if ecarts:
        ecarts.sort()
        print("  ecart entree / instantane : median %.0f s, max %.0f s"
              % (ecarts[len(ecarts) // 2], ecarts[-1]))
    perdus = sans_regime + sans_date + sans_pnl
    if perdus > 0.2 * len(tickets):
        print("  ATTENTION : %.0f %% des tickets sont hors jointure. Les"
              % (100.0 * perdus / len(tickets)))
        print("  moyennes ci-dessous portent sur un echantillon amoindri")
        print("  dont rien ne garantit qu il ressemble au reste.")
    if not retenus:
        print("Rien a afficher.")
        return 1

    nm = a.nmin
    tableau("H8 -- par PHASE de regime  (l enonce direct)",
            par_phase, sorted(par_phase, key=lambda k: -len(par_phase[k])), nm)

    ordre_tr = [tranche_de((x[0] + x[1]) / 2.0 if x[1] < 10 ** 9
                           else x[0] + 1) for x in TRANCHES]
    tableau("H8 -- par TEMPS DEPUIS LE DEBUT DU REGIME  (la forme)",
            par_tranche, [o for o in ordre_tr if o], nm,
            "H8 est vraie si la premiere tranche decroche des suivantes.")

    tableau("Position dans le range DE SEANCE",
            par_bande, ["%d-%d %%" % (x[0], min(x[1], 100))
                        for x in BANDES_RANGE], nm,
            "range de SEANCE (ancre sur session_open_15h30) -- ce n est"
            " PAS le range_pos 7 jours des panneaux.")

    tableau("Par TYPE de regime",
            par_type, sorted(par_type, key=lambda k: -len(par_type[k])), nm)

    print()
    print("Croisement setup x tranche  (les magics a 4 chiffres n ont pas")
    print("de setup : ils sont dans 'hors setup', affiches et non filtres)")
    print("  " + "-" * 62)
    setups = sorted(set(k[0] for k in par_setup_tranche))
    for s in setups:
        print("  %s" % s)
        for o in ordre_tr:
            if not o:
                continue
            vals = par_setup_tranche.get((s, o)) or []
            print("    %-24s %s" % (o, cellule(vals, nm)))
    print("  " + "-" * 62)

    print()
    print("`?` = moins de %d tickets. Le seuil vient du paragraphe 0 de"
          % nm)
    print("HYPOTHESES.md : une comparaison annoncee d avance, sigma = 60,")
    print("edge = 16. Pour une cellule regardee parmi cent, il faut ~172.")
    print("Une moyenne sans son n est un chiffre sans unite.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
