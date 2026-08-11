# -*- coding: utf-8 -*-
"""
rails_join.py -- rendre le verdict V9 calculable, sans toucher au moteur

  python rails_join.py
  python rails_join.py --tolerance 300 --sortie docs/rails_trades/tickets_rails.jsonl

CE QU ON A DECOUVERT LE 11/08
    oos_v9 --champs annoncait une couverture famille X de 0 pour cent, et
    j en ai conclu que le panel ne persistait pas les rails. C etait faux.
    churn_trade_logger._write_series() ecrit, par actif ET par pas de temps :

        {"ts", "asset", "tf", "spread", "bear", "bull", "rsi",
         "rails_pos", "rsi_pos", "fresh", "cycle_dir"}

    dans docs/rails_trades/series_<date>.jsonl. rails_pos et rsi_pos sont
    exactement les deux champs dont le gel V9 a besoin. Ils ne sont pas
    dans le journal des tickets, voila tout : ils vivent dans une serie
    temporelle a cote.

    Consequence : aucune modification du moteur n est necessaire, et le
    verdict du 01/09 redevient calculable RETROACTIVEMENT, sur toute la
    profondeur des series -- pas seulement sur les vingt jours restants.

CE QUE FAIT CE SCRIPT
    Pour chaque ticket, il cherche l etat des rails de SON actif, pour
    chacun des quatre pas de temps, au dernier instant CONNU AVANT son
    entree. Puis il reecrit le ticket enrichi de

        rails_pos_m1, rails_pos_m3, rails_pos_m5, rails_pos_m15
        rsi_pos_m1,   rsi_pos_m3,   rsi_pos_m5,   rsi_pos_m15

    Ces noms ne sont pas choisis au hasard : CLEFS_POS et CLEFS_RSIPOS de
    oos_v9.py les contiennent deja. Le fichier produit se lit donc tel quel,
    sans patcher le harnais une fois de plus.

JAMAIS D INSTANT POSTERIEUR
    Un instantane pris apres l entree contiendrait de l information que le
    trade n avait pas. Toute la valeur d un gel out-of-sample disparait si
    on laisse passer ca. La recherche est donc strictement ts <= entry_ts,
    et le decalage est mesure et affiche.

LE DECALAGE EST LA VRAIE LIMITE
    Si l instantane le plus proche a vingt minutes, l etat des rails a pu
    changer entre-temps, et on attribuerait au ticket une configuration
    qu il n a pas connue. --tolerance fixe l age maximal accepte, par
    defaut cinq minutes. Au-dela, le champ est laisse vide : mieux vaut une
    couverture plus basse et honnete qu une couverture pleine et fausse.

    La distribution des decalages est imprimee. Si la mediane est de
    quelques secondes, la jointure est solide ; si elle approche la
    tolerance, il faudra le dire dans le verdict.
"""
import argparse
import bisect
import glob
import io
import json
import os
import sys

TICKETS = [os.path.join("docs", "churn_trades", "churn_trades_archive.jsonl"),
           os.path.join("docs", "churn_trades", "churn_trades.jsonl"),
           "churn_trades_archive.jsonl", "churn_trades.jsonl"]
SERIES = [os.path.join("docs", "rails_trades", "series_*.jsonl"),
          os.path.join("docs", "churn_trades", "series_*.jsonl"),
          "series_*.jsonl"]
SORTIE = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
TFS = ["m1", "m3", "m5", "m15"]
TOLERANCE = 300          # secondes : age maximal d un instantane accepte


def secondes(ts):
    """'AAAA-MM-JJ HH:MM:SS' -> entier comparable. Aucun fuseau en jeu :
    les deux fichiers sont ecrits par le meme processus, donc la meme
    horloge, et seule leur difference nous interesse."""
    try:
        j, h = str(ts)[:10], str(ts)[11:19]
        a, m, d = int(j[:4]), int(j[5:7]), int(j[8:10])
        hh, mm = int(h[:2]), int(h[3:5])
        ss = int(h[6:8]) if len(h) >= 8 else 0
        return ((a * 12 + m) * 31 + d) * 86400 + hh * 3600 + mm * 60 + ss
    except (ValueError, IndexError):
        return None


def normalise_tf(v):
    v = str(v).strip().lower().replace("min", "").replace("_", "")
    return v if v in TFS else None


def normalise_actif(v):
    v = str(v).strip().upper()
    return {"SPX500": "US500", "NAS100": "US100", "DJ30": "US30",
            "SP500": "US500", "NDX100": "US100"}.get(v, v)


def lire_series(motifs):
    """{(actif, tf): ([instants tries], [(rails_pos, rsi_pos)])}"""
    fichiers = []
    for m in motifs:
        fichiers.extend(sorted(glob.glob(m)))
    if not fichiers:
        print("KO : aucun series_*.jsonl trouve. Cherches :")
        for m in motifs:
            print("    " + m)
        print()
        print("C est churn_trade_logger._write_series() qui les ecrit.")
        print("Si le dossier est vide, la fonction ne tourne pas -- et la")
        print("famille X du gel V9 restera incalculable.")
        sys.exit(1)
    brut = {}
    lignes = 0
    for f in fichiers:
        for l in io.open(f, encoding="utf-8-sig"):
            l = l.strip()
            if not l or l[0] != "{":
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            t = secondes(o.get("ts"))
            tf = normalise_tf(o.get("tf"))
            if t is None or tf is None:
                continue
            k = (normalise_actif(o.get("asset")), tf)
            brut.setdefault(k, []).append(
                (t, o.get("rails_pos"), o.get("rsi_pos")))
            lignes += 1
    print("series : %d fichiers, %d lignes utilisables" % (len(fichiers), lignes))
    out = {}
    for k, v in brut.items():
        v.sort(key=lambda x: x[0])
        out[k] = ([x[0] for x in v], [(x[1], x[2]) for x in v])
    return out


def lire_tickets(exp):
    ch = exp or [p for p in TICKETS if os.path.isfile(p)]
    if not ch:
        print("KO : aucun churn_trades*.jsonl trouve. Utilise --tickets CHEMIN.")
        sys.exit(1)
    vus, lot = set(), []
    for f in ch:
        for l in io.open(f, encoding="utf-8-sig"):
            l = l.strip()
            if not l or l[0] != "{":
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            tk = o.get("ticket")
            if tk is None or tk in vus or secondes(o.get("entry_ts")) is None:
                continue
            vus.add(tk)
            lot.append(o)
    print("tickets : %d fichiers, %d enregistrements uniques" % (len(ch), len(lot)))
    return lot


def avant(instants, t):
    """Index du dernier instant <= t, ou None. Jamais d instant posterieur."""
    i = bisect.bisect_right(instants, t)
    return i - 1 if i else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tickets", nargs="*")
    p.add_argument("--series", nargs="*")
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--tolerance", type=int, default=TOLERANCE)
    a = p.parse_args()

    print("=== SCALP-EA / JOINTURE TICKETS x RAILS ===")
    print("tolerance : %d secondes" % a.tolerance)
    ser = lire_series(a.series or SERIES)
    lot = lire_tickets(a.tickets)
    print("couples (actif, pas de temps) disponibles : %s"
          % ", ".join("%s/%s" % k for k in sorted(ser)))

    decalages = []
    complets = trop_vieux = sans_serie = 0
    os.makedirs(os.path.dirname(a.sortie) or ".", exist_ok=True)
    with io.open(a.sortie, "w", encoding="utf-8") as f:
        for o in lot:
            t = secondes(o.get("entry_ts"))
            actif = normalise_actif(o.get("asset"))
            n = 0
            for tf in TFS:
                s = ser.get((actif, tf))
                if not s:
                    sans_serie += 1
                    continue
                i = avant(s[0], t)
                if i is None:
                    continue
                age = t - s[0][i]
                if age > a.tolerance:
                    trop_vieux += 1
                    continue
                decalages.append(age)
                rp, xp = s[1][i]
                if rp not in (None, ""):
                    o["rails_pos_" + tf] = rp
                    n += 1
                if xp not in (None, ""):
                    o["rsi_pos_" + tf] = xp
            if n == len(TFS):
                complets += 1
            f.write(json.dumps(o, ensure_ascii=True) + "\n")

    print()
    print("ecrit : %s" % a.sortie)
    print("  %d tickets avec les quatre pas de temps renseignes  %.0f%%"
          % (complets, 100.0 * complets / max(1, len(lot))))
    if trop_vieux:
        print("  %d couples ecartes : instantane plus vieux que la tolerance"
              % trop_vieux)
    if sans_serie:
        print("  %d couples sans serie du tout pour cet actif/pas de temps"
              % sans_serie)

    if decalages:
        decalages.sort()
        n = len(decalages)
        print()
        print("DECALAGE entre l entree et l instantane retenu")
        print("  median %ds | moyen %ds | 90e centile %ds | maximum %ds"
              % (decalages[n // 2], sum(decalages) // n,
                 decalages[int(n * 0.9)], decalages[-1]))
        if decalages[n // 2] > 60:
            print("  Mediane au-dela d une minute : l etat des rails a pu")
            print("  changer entre l instantane et l entree. A dire dans le")
            print("  verdict, et a garder en tete avant d y croire.")
        else:
            print("  Mediane sous la minute : la jointure est solide.")

    print()
    print("ETAPE SUIVANTE")
    print("  python oos_v9.py --champs --fichier %s" % a.sortie)
    print()
    print("  La couverture famille X doit franchir les 60% requis. Si elle")
    print("  y arrive, le gel V9 pourra rendre son verdict le 01/09 -- et")
    print("  meme etre relu retroactivement sur toute la profondeur des")
    print("  series, ce qu on croyait perdu ce matin.")
    print()
    print("  Rien n a ete modifie : ni le moteur, ni le journal d origine,")
    print("  ni regles_gelees_v9.py. Ce script ecrit un fichier de plus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
