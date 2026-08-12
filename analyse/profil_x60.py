# -*- coding: utf-8 -*-
"""
profil_x60.py -- ce que sont les x60, caracteristique par caracteristique

  python profil_x60.py --sources
  python profil_x60.py
  python profil_x60.py --setup 60 --contre 05

CE QUE CE SCRIPT PEUT DIRE, ET CE QU IL NE PEUT PAS

    Il ne sait PAS ce que « 60 » designe. Aucune donnee ne le dit : le
    magic est un nombre, et le sens de ses chiffres vit dans le code de
    l EA, pas dans les tickets. Pour ca :

        Select-String -Path *.py,*.mq5 -Pattern "206160|207260|206360"

    Ce qu il peut faire, c est DECRIRE les x60 par ce qu ils font :
    quand ils entrent, combien de temps ils tiennent, ce qu ils voient
    au maximum, comment ils sortent, dans quel sens, a quelle taille,
    dans quel regime. Une description mesuree vaut mieux qu une
    definition supposee.

LES CARACTERISTIQUES, DANS L ORDRE OU ELLES SONT PRODUITES

    1. combien, et sur combien de jours -- la frequence d abord
    2. l heure d entree
    3. la duree de vie, de l entree a la cloture
    4. MFE et MAE en points, et la part du MFE reellement encaissee
    5. la raison de cloture
    6. le sens
    7. le volume
    8. le verdict churn a l entree
    9. l espacement entre deux x60 -- arrivent-ils groupes ?

    Chaque ligne est donnee POUR LE SETUP et POUR LE RESTE, cote a cote.
    Un chiffre seul ne caracterise rien ; c est l ecart qui parle.

--sources REPOND A « JUSQU OU PEUT-ON REMONTER »

    Il liste tous les .jsonl candidats trouves, avec leur nombre de
    lignes exploitables et leurs dates extremes. C est la seule facon
    honnete de repondre : je ne sais pas ce qui traine sur cette
    machine, le script va voir.

LECTURE SEULE. Aucun ordre. Ecrit panels/profil_x60.txt.
"""
import argparse
import io
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

try:
    import horloge_regime as H
except ImportError:
    print("KO : horloge_regime.py introuvable a cote de ce script.")
    sys.exit(1)

O = H.O

CLEFS_MAGIC = ["magic", "magic_number", "magicnumber", "mg"]
CLEFS_FIN = ["close_ts", "exit_ts", "close_time"]
CLEFS_RAISON = ["close_reason", "reason", "exit_reason"]
CLEFS_SENS = ["dir", "sens", "side", "type", "direction"]
CLEFS_VOL = ["volume", "lots", "lot"]
CLEFS_MFE = ["mfe_pts", "mfe_points"]
CLEFS_MAE = ["mae_pts", "mae_points"]
CLEFS_MFE_E = ["mfe_eur"]

DOSSIERS = [".", "docs", os.path.join("docs", "rails_trades"),
            os.path.join("docs", "churn_trades"), "archives",
            r"C:\ScalpExport", os.path.join(r"C:\ScalpExport", "docs")]
MINI = 20
DEST = os.path.join(_ICI, "panels")
LARG = 100


def _n(v):
    return O._nombre(v)


def charger(chemins):
    """Un enregistrement par ticket, avec tout ce qui sert au profil."""
    par, brut = {}, 0
    for ch in chemins:
        try:
            f = io.open(ch, encoding="utf-8-sig")
        except IOError:
            continue
        for l in f:
            l = l.strip()
            if not l or l[0] != "{":
                continue
            brut += 1
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ts = str(O._prem(o, O.CLEFS_TS) or "")
            tk = O._prem(o, O.CLEFS_TICKET)
            if len(ts) < 16 or tk is None or tk in par:
                continue
            mg = _n(O._prem(o, CLEFS_MAGIC))
            fin = str(O._prem(o, CLEFS_FIN) or "")
            duree = None
            if len(fin) >= 16:
                try:
                    a = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
                    b = datetime.strptime(fin[:19], "%Y-%m-%dT%H:%M:%S")
                    duree = (b - a).total_seconds() / 60.0
                except ValueError:
                    duree = None
            par[tk] = {
                "ts": ts, "jour": ts[:10], "heure": ts[11:13],
                "ticket": str(tk), "actif": H._actif(o),
                "pnl": _n(O._prem(o, O.CLEFS_PNL)),
                "magic": ("M%d" % int(mg)) if mg else "M?",
                "duree": duree,
                "raison": str(O._prem(o, CLEFS_RAISON) or "(vide)"),
                "sens": str(O._prem(o, CLEFS_SENS) or "(vide)").upper(),
                "vol": _n(O._prem(o, CLEFS_VOL)),
                "mfe": _n(O._prem(o, CLEFS_MFE)),
                "mae": _n(O._prem(o, CLEFS_MAE)),
                "mfe_eur": _n(O._prem(o, CLEFS_MFE_E)),
                "churn": O._churn(o),
            }
    return list(par.values()), brut


def setup_de(magic):
    d = str(magic).lstrip("M")
    return d[4:] if d.isdigit() and len(d) == 6 else None


# ------------------------------------------------------------ mesures

def med(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else None


def fmt(x, n=1):
    return "-" if x is None else ("%.*f" % (n, x))


def part(lot, clef, valeur):
    v = [s for s in lot if s[clef] is not None]
    if not v:
        return None
    return 100.0 * sum(1 for s in v if s[clef] == valeur) / len(v)


def deux(nom, a, b, f):
    """Une ligne : la mesure pour le setup, puis pour le reste."""
    return "%-34s %16s %16s" % (nom, f(a), f(b))


def repartition(lot, clef, combien=5):
    g = defaultdict(int)
    for s in lot:
        g[s[clef]] += 1
    tot = sum(g.values()) or 1
    return [(k, v, 100.0 * v / tot)
            for k, v in sorted(g.items(), key=lambda kv: -kv[1])[:combien]]


def sources_jsonl():
    """[(chemin, lignes, premier jour, dernier jour)] -- jusqu ou on remonte."""
    vus, out = set(), []
    for d in DOSSIERS:
        if not os.path.isdir(d):
            continue
        try:
            noms = sorted(os.listdir(d))
        except OSError:
            continue
        for n in noms:
            if not n.lower().endswith(".jsonl"):
                continue
            p = os.path.abspath(os.path.join(d, n))
            if p in vus:
                continue
            vus.add(p)
            lignes, jours = 0, []
            try:
                for l in io.open(p, encoding="utf-8-sig", errors="replace"):
                    l = l.strip()
                    if not l or l[0] != "{":
                        continue
                    lignes += 1
                    if lignes % 50 == 1 or lignes < 200:
                        try:
                            o = json.loads(l)
                        except ValueError:
                            continue
                        t = str(O._prem(o, O.CLEFS_TS) or "")
                        if len(t) >= 10:
                            jours.append(t[:10])
            except IOError:
                continue
            out.append((p, lignes,
                        min(jours) if jours else "-",
                        max(jours) if jours else "-"))
    return sorted(out, key=lambda x: -x[1])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--setup", default="60")
    p.add_argument("--contre", default="")
    p.add_argument("--depuis")
    p.add_argument("--sources", action="store_true")
    p.add_argument("--dest", default=DEST)
    a = p.parse_args()

    if a.sources:
        print("=" * LARG)
        print(" JUSQU OU PEUT-ON REMONTER -- tous les .jsonl trouves")
        print("=" * LARG)
        print("%-62s %10s %12s %12s"
              % ("fichier", "lignes", "du", "au"))
        print("-" * LARG)
        v = sources_jsonl()
        if not v:
            print("  aucun .jsonl dans %s" % ", ".join(DOSSIERS))
        for chemin, lignes, d0, d1 in v:
            print("%-62s %10d %12s %12s"
                  % (chemin[-62:], lignes, d0, d1))
        print("-" * LARG)
        print("  Les dates sont echantillonnees, pas lues ligne a ligne :")
        print("  une archive peut commencer un peu plus tot que ce qui est")
        print("  affiche. Pour l utiliser :")
        print("      python profil_x60.py --fichier <chemin> [<chemin>...]")
        return 0

    chemins = a.fichier or O.sources(None)
    lot, brut = charger(chemins)
    if not lot:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        return 1
    if a.depuis:
        lot = [s for s in lot if s["jour"] >= a.depuis]

    for s in lot:
        s["setup"] = setup_de(s["magic"])

    fam = [s for s in lot if s["setup"] == a.setup]
    if not fam:
        print("Aucun ticket de setup %s." % a.setup)
        return 1
    if a.contre:
        aut = [s for s in lot if s["setup"] == a.contre]
        nom_b = "setup %s" % a.contre
    else:
        aut = [s for s in lot if s["setup"] != a.setup]
        nom_b = "tout le reste"

    L = []
    L.append("=" * LARG)
    L.append("  PROFIL DU SETUP %s -- caracteristique par caracteristique"
             % a.setup)
    L.append("=" * LARG)
    L.append("%d tickets au total, %s -> %s"
             % (len(lot), min(s["jour"] for s in lot),
                max(s["jour"] for s in lot)))
    L.append("")
    L.append("  Ce script ne sait pas ce que « %s » DESIGNE -- le sens des"
             % a.setup)
    L.append("  chiffres du magic vit dans le code de l EA, pas dans les")
    L.append("  tickets. Il decrit ce que ces trades FONT. Pour le nom :")
    L.append("      Select-String -Path *.py,*.mq5 -Pattern"
             " \"206160|207260|206360\"")
    L.append("")

    L.append("%-34s %16s %16s"
             % ("", "setup %s" % a.setup, nom_b))
    L.append("-" * LARG)
    L.append(deux("tickets", fam, aut, lambda x: "%d" % len(x)))
    L.append(deux("jours ou il trade", fam, aut,
                  lambda x: "%d" % len(set(s["jour"] for s in x))))
    L.append(deux("tickets par jour trade", fam, aut,
                  lambda x: fmt(float(len(x))
                                / max(1, len(set(s["jour"] for s in x))))))
    L.append(deux("EUR par ticket", fam, aut,
                  lambda x: fmt(sum(s["pnl"] for s in x
                                    if s["pnl"] is not None)
                                / max(1, len(x)), 2)))
    L.append(deux("part gagnante", fam, aut,
                  lambda x: "%.0f%%" % (100.0 * sum(1 for s in x
                                                    if (s["pnl"] or 0) > 0)
                                        / max(1, len(x)))))
    L.append("-" * LARG)
    L.append(deux("duree mediane, minutes", fam, aut,
                  lambda x: fmt(med([s["duree"] for s in x]))))
    L.append(deux("duree 9e decile", fam, aut,
                  lambda x: fmt(_decile([s["duree"] for s in x], 0.9))))
    L.append(deux("MFE median, points", fam, aut,
                  lambda x: fmt(med([s["mfe"] for s in x]))))
    L.append(deux("MAE median, points", fam, aut,
                  lambda x: fmt(med([s["mae"] for s in x]))))
    L.append(deux("MFE median, EUR", fam, aut,
                  lambda x: fmt(med([s["mfe_eur"] for s in x]), 2)))
    L.append(deux("capture : PnL / MFE", fam, aut, _capture))
    L.append(deux("volume median", fam, aut,
                  lambda x: fmt(med([s["vol"] for s in x]), 2)))
    L.append("-" * LARG)
    L.append("  capture = somme des PnL divisee par la somme des MFE en")
    L.append("  euros. Elle dit ce qu on garde de ce qu on a vu.")
    L.append("")

    for titre, clef in (("L HEURE D ENTREE", "heure"),
                        ("LA RAISON DE CLOTURE", "raison"),
                        ("LE SENS", "sens"),
                        ("LE VERDICT CHURN A L ENTREE", "churn"),
                        ("L ACTIF", "actif")):
        L.append("=" * LARG)
        L.append("  %s" % titre)
        L.append("=" * LARG)
        L.append("%-22s %10s %8s %14s %10s %8s"
                 % ("", "setup %s" % a.setup, "part", nom_b, "part",
                    "EUR/tk"))
        L.append("-" * LARG)
        cles = [k for k, _n2, _p in repartition(fam, clef, 8)]
        for k in cles:
            va = [s for s in fam if s[clef] == k]
            vb = [s for s in aut if s[clef] == k]
            eur = (sum(s["pnl"] for s in va if s["pnl"] is not None)
                   / len(va)) if va else 0.0
            L.append("%-22s %10d %7.0f%% %14d %9.0f%% %8.2f"
                     % (str(k)[:22], len(va),
                        100.0 * len(va) / max(1, len(fam)), len(vb),
                        100.0 * len(vb) / max(1, len(aut)), eur))
        L.append("-" * LARG)
        L.append("")

    L.append("=" * LARG)
    L.append("  ARRIVENT-ILS GROUPES ?")
    L.append("=" * LARG)
    par_jour = defaultdict(list)
    for s in fam:
        par_jour[s["jour"]].append(s)
    ecarts = []
    for jour, v in par_jour.items():
        v.sort(key=lambda s: s["ts"])
        for i in range(1, len(v)):
            try:
                x = datetime.strptime(v[i]["ts"][:19], "%Y-%m-%dT%H:%M:%S")
                y = datetime.strptime(v[i - 1]["ts"][:19], "%Y-%m-%dT%H:%M:%S")
                ecarts.append((x - y).total_seconds() / 60.0)
            except ValueError:
                continue
    if ecarts:
        courts = 100.0 * sum(1 for e in ecarts if e <= 2) / len(ecarts)
        L.append("  %d intervalles entre deux entrees du setup %s"
                 % (len(ecarts), a.setup))
        L.append("  mediane : %s minutes" % fmt(med(ecarts)))
        L.append("  %.0f%% des entrees suivent la precedente de 2 min ou"
                 " moins" % courts)
        L.append("")
        L.append("  Une part elevee signifie qu ils partent en salve -- donc")
        L.append("  que « 177 tickets » compte moins d evenements")
        L.append("  independants qu il n y parait, et que les moyennes par")
        L.append("  ticket sont plus fragiles qu elles n en ont l air.")
    else:
        L.append("  Pas assez d entrees pour mesurer un espacement.")

    for l in L:
        print(l)
    H.ecrire(["# profil_x60.txt",
              "# ecrit le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "# via profil_x60.py --setup %s" % a.setup, ""] + L,
             os.path.join(a.dest, "profil_x60.txt"))
    print()
    print("ecrit : %s" % os.path.join(a.dest, "profil_x60.txt"))
    return 0


def _decile(v, q):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    return v[min(len(v) - 1, int(len(v) * q))]


def _capture(lot):
    p = sum(s["pnl"] for s in lot if s["pnl"] is not None)
    m = sum(s["mfe_eur"] for s in lot if s["mfe_eur"] is not None)
    if not m:
        return "-"
    return "%.0f%%" % (100.0 * p / m)


if __name__ == "__main__":
    sys.exit(main())
