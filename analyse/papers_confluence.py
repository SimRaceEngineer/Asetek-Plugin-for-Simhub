# -*- coding: utf-8 -*-
r"""
papers_confluence.py -- C_M15_VENTE, fermee par le source et non par moi

  python papers_confluence.py
  python papers_confluence.py --instant "2026-08-18 13:51:27"

LECTEUR SEUL. N ECRIT RIEN, NE PREND AUCUN TRADE.

CE QUE confluence_section.py DIT, MOT POUR MOT

    _BIAIS   = {"BOTH>50": "BULL", "BOTH<50": "BEAR"}          rails_pos
    _ALIGNED = {"ALIGNED_BULL": "BULL", "ALIGNED_BEAR": "BEAR"} consensus

    def _etat(s, tf):
        r, h = _rails_avis(s, tf), _hlc_avis(s, tf)
        if r is None or h is None:
            return None
        return ("ACCORD", r) if r == h else ("CONFLIT", None)

    def _t_par_tf(sigs):
        ...
            lbl = "achat" if d == "BULL" else "vente"
            _add(agg[(i, tf, "CONFLIT", lbl)], s)

    "M15 CONFLIT vente" est donc : l avis RAILS du M15 existe, l avis
    HLC du M15 existe, ILS SE CONTREDISENT, et le trade est un SELL.

    Aucun seau, aucune session : la section agrege sur (TF, etat, sens)
    et rien d autre. La colonne que mon parseur cherchait n existe pas.

CE QUE JE MESURAIS A LA PLACE, ET POURQUOI C ETAIT SANS ESPOIR

    _vs_pack(t, "M15") == "AGAINST" and dir == "SELL"

    _vs_pack demande si LE TRADE va contre le consensus HLC. Le CONFLIT
    ne regarde pas le trade pour exister : il oppose les RAILS au HLC.
    Deux grandeurs sans rapport. Aucune coupure, aucune population et
    aucune colonne ne pouvaient rattraper ca -- je comptais autre chose.

CE QUE FAIT CE SCRIPT

    A. Il transcrit _rails_avis / _hlc_avis / _etat / _dir a
       l identique (confluence_section.py lignes 58 a 80) et reconstruit
       la table complete TF x etat x sens, sur les DEUX populations --
       tickets bruts et signaux dedoublonnes. Le module dit lui-meme
       qu il tourne sur les deux (8097 et 8095) : c est donc une
       question ouverte, et on la pose aux deux.

    B. Il cherche 358 dans cette table, a l instant de reference ou
       29 autres cles sont exactes, et publie la fenetre de chaque
       cellule. Une cellule unique identifie ; plusieurs n identifient
       rien, et le script le dit.

UNE HYPOTHESE, ET ELLE EST MARQUEE COMME TELLE

    _BIAIS mappe rails_pos "BOTH>50" sur BULL. Le libelle "M15 bull+"
    (n= 248), jamais encode, ressemble a cette valeur. Le script teste
    donc M15 x rails_pos == "BOTH>50", en le nommant HYPOTHESE SUR LE
    LIBELLE. Si sa fenetre contient l instant de reference, elle vaut
    ce que valent les 29 autres. Sinon elle ne vaut rien, et c est dit.
"""
import argparse
import sys

INSTANT_DEFAUT = "2026-08-18 13:51:27"
TFS = ("M1", "M3", "M5", "M15")
_ALIGNED = {"ALIGNED_BULL": "BULL", "ALIGNED_BEAR": "BEAR"}
_BIAIS = {"BOTH>50": "BULL", "BOTH<50": "BEAR"}


def _tf(s, tf):
    return ((s.get("rails_entry") or {}).get(s.get("asset")) or {}).get(tf) \
        or {}


def _hlc(s, tf):
    return (s.get("hlc_churn_entry") or {}).get(tf) or {}


def _rails_avis(s, tf):
    return _BIAIS.get(_tf(s, tf).get("rails_pos"))


def _hlc_avis(s, tf):
    return _ALIGNED.get(_hlc(s, tf).get("consensus"))


def _etat(s, tf):
    r, h = _rails_avis(s, tf), _hlc_avis(s, tf)
    if r is None or h is None:
        return None
    return ("ACCORD", r) if r == h else ("CONFLIT", None)


def _dir(s):
    d = s.get("dir")
    if d in ("BUY", "LONG"):
        return "BULL"
    if d in ("SELL", "SHORT"):
        return "BEAR"
    return None


def table(sigs):
    """(tf, etat, sens) -> [entry_ts]. _t_par_tf, sans le HTML."""
    agg, sans = {}, 0
    for s in sigs:
        e_ts = s.get("entry_ts")
        if not isinstance(e_ts, str):
            continue
        d = _dir(s)
        if d is None:
            continue
        for tf in TFS:
            e = _etat(s, tf)
            if e is None:
                sans += 1
                continue
            kind, side = e
            if kind == "ACCORD":
                cle = (tf, "ACCORD %s" % side,
                       "WITH" if side == d else "CONTRE")
            else:
                cle = (tf, "CONFLIT", "achat" if d == "BULL" else "vente")
            agg.setdefault(cle, []).append(e_ts)
    for k in agg:
        agg[k].sort()
    return agg, sans


def fenetre(ts, n):
    if len(ts) < n:
        return None, None
    return ts[n - 1], (ts[n] if len(ts) > n else "(ouverte)")


def cherche(add, agg, nom, n, instant):
    add("")
    add("  %s -- annonce %d" % (nom, n))
    egales = [k for k in sorted(agg)
              if sum(1 for e in agg[k] if e <= instant) == n]
    if egales:
        for k in egales:
            lo, hi = fenetre(agg[k], n)
            add("    EXACTE A L INSTANT : %s   [%s, %s)"
                % (" x ".join(k), lo, hi))
        if len(egales) > 1:
            add("    %d cellules donnent ce compte : ce n est pas une"
                " identification." % len(egales))
        return
    proches = sorted(
        ((abs(sum(1 for e in agg[k] if e <= instant) - n), k) for k in agg),
        key=lambda x: (x[0], str(x[1])))[:5]
    add("    aucune cellule exacte a l instant. Les cinq plus proches :")
    for _ecart, k in proches:
        v = sum(1 for e in agg[k] if e <= instant)
        lo, hi = fenetre(agg[k], n)
        add("      %-28s %6d  %+5d   %s"
            % (" x ".join(k), v, v - n,
               ("exacte a [%s, %s)" % (lo, hi)) if lo
                else "n atteint jamais %d (total %d)" % (n, len(agg[k]))))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--instant", default=INSTANT_DEFAUT)
    p.add_argument("--rails", default=None)
    a = p.parse_args()

    try:
        import papers_population as PP
    except ImportError as e:
        print("KO : papers_population.py doit etre dans ce dossier. (%s)" % e)
        return 1

    chemin = a.rails or PP.RAILS
    trades, ko = PP.lire(chemin)
    sigs, _ec = PP.signaux(trades)

    L = []
    add = L.append
    add("=" * 96)
    add("CONFLUENCE rails x HLC -- la section transcrite, pas devinee")
    add("=" * 96)
    add("")
    add("  Lecteur seul. Rien n est ecrit, aucun trade n est pris.")
    add("")
    add("  %s : %d lignes (%d illisibles)" % (chemin, len(trades), ko))
    add("  instant de reference : %s  (29 cles y sont exactes)" % a.instant)
    add("")

    for nom, pop in (("tickets bruts", trades), ("signaux", sigs)):
        agg, sans = table(pop)
        add("=" * 96)
        add("TABLE PAR TF -- population : %s  (%d lignes)" % (nom, len(pop)))
        add("=" * 96)
        add("  %d couple(s) (signal, TF) sans double avis, exclus." % sans)
        add("")
        add("  %-28s %8s %8s" % ("cellule", "instant", "total"))
        add("  " + "-" * 48)
        for k in sorted(agg):
            add("  %-28s %8d %8d"
                % (" x ".join(k),
                   sum(1 for e in agg[k] if e <= a.instant), len(agg[k])))
        cherche(add, agg, "C_M15_VENTE = M15 x CONFLIT x vente", 358,
                a.instant)
        add("")

    # --- l hypothese sur le libelle, nommee comme telle ---------------
    add("=" * 96)
    add("HYPOTHESE SUR LE LIBELLE -- 'M15 bull+' = rails_pos BOTH>50 ?")
    add("=" * 96)
    add("  _BIAIS mappe 'BOTH>50' sur BULL. Le libelle 'M15 bull+' n a")
    add("  jamais ete encode. Ce n est pas une deduction : c est une")
    add("  ressemblance de mots, testee et affichee comme telle.")
    add("")
    for nom, pop in (("tickets bruts", trades), ("signaux", sigs)):
        ts = sorted(s["entry_ts"] for s in pop
                    if isinstance(s.get("entry_ts"), str)
                    and _tf(s, "M15").get("rails_pos") == "BOTH>50")
        v = sum(1 for e in ts if e <= a.instant)
        lo, hi = fenetre(ts, 248)
        add("  %-14s total %5d   a l instant %5d  %+5d   %s"
            % (nom, len(ts), v, v - 248,
               "EXACTE A L INSTANT" if lo and lo <= a.instant < hi
               else (("exacte a [%s, %s)" % (lo, hi)) if lo
                     else "n atteint jamais 248")))
    add("")
    add("  Les valeurs de rails_pos reellement presentes, par TF :")
    for tf in TFS:
        vus = {}
        for s in trades:
            v = _tf(s, tf).get("rails_pos")
            vus[v] = vus.get(v, 0) + 1
        add("    %-4s  %s" % (tf, "   ".join(
            "%s=%d" % (k, n) for k, n in
            sorted(vus.items(), key=lambda x: -x[1])[:6])))
    add("")

    add("=" * 96)
    add("  Ce script n a rien ecrit et n a pris aucun trade.")
    add("=" * 96)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
