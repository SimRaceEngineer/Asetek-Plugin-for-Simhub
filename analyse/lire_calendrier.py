# -*- coding: utf-8 -*-
r"""
lire_calendrier.py -- le calendrier MT5 remis a l heure de nos cycles

  python lire_calendrier.py calendrier.csv --verifie
  python lire_calendrier.py calendrier.csv --importance HIGH
  python lire_calendrier.py calendrier.csv --pays US --sortie cartes\cal.csv

LE DECALAGE EST MESURE, PAS SUPPOSE

    L export du 17/08 porte ses trois horloges en en-tete :

        TimeGMT               08:26   UTC
        TimeLocal (machine)   10:26   UTC+2  -- le VPS, nos cycles
        TimeCurrent (serveur) 11:26   UTC+3  -- le broker

    Et le CPI y sort a 15:30 alors qu il est publie a 14:30 heure de
    Paris. Le calendrier est donc rendu en HEURE SERVEUR, et la regle
    est : heure_calendrier - 1 h = heure_cycles.

    Ce script RELIT ces trois lignes dans le fichier et en deduit le
    decalage lui-meme. Si vous exportez depuis un autre broker, ou
    apres un changement d heure, il s ajustera tout seul -- une
    constante ecrite en dur aurait tenu jusqu au 25 octobre.

    Et `--verifie` va plus loin : il cherche le CPI du 12/08 et
    controle qu apres correction il tombe bien a 14:30. Un decalage
    qu on calcule sans le confronter a un repere connu est une
    hypothese, pas une mesure.

LA SURPRISE, ET QUAND ELLE N EXISTE PAS

    surprise = actual - forecast, et RIEN quand l un des deux manque.
    Un forecast absent rendu a zero ferait une surprise egale a
    l actual : le plus gros evenement du fichier serait alors celui
    dont on ne sait rien.

    Une colonne `surprise_rel` donne l ecart rapporte a |forecast|,
    pour comparer un CPI a 0,1 pres et un NFP a 100 000 pres. Elle est
    vide quand le forecast vaut zero -- diviser par zero produirait un
    infini qui dominerait tous les classements.

RESERVE ECRITE AVANT USAGE : LE FORECAST MT5 N EST PAS FIABLE PARTOUT

    Sur le CPI y/y du 12/08, MT5 annonce un forecast de 2,7 quand
    TradingEconomics donne un consensus de 3,4 -- pour un actual de
    3,4. Selon la source, cette publication est soit parfaitement
    conforme, soit la plus grosse surprise d inflation de l annee.

    Le prix tranche en faveur de TradingEconomics : ce jour-la, la
    plus grosse amplitude sur quinze minutes valait 0,54 %, EN DESSOUS
    du maximum journalier median. Une surprise de +0,7 point n aurait
    pas donne une journee plus calme que la moyenne.

    Donc : le champ `forecast` de MT5 est utilisable, mais il doit
    etre CONFRONTE a une seconde source avant qu une surprise serve a
    decider quoi que ce soit. Cette reserve est imprimee dans la
    sortie, pas seulement ici.

LECTEUR SEUL : lit le CSV exporte par export_calendrier.mq5, ecrit un
CSV. Ne touche a rien d autre.
"""
import argparse
import io
import os
import sys
import datetime as dt

SORTIE = os.path.join("cartes", "calendrier.csv")
RANGS = {"NONE": 0, "LOW": 1, "MODERATE": 2, "HIGH": 3}
LARG = 100


def horo(s):
    """MT5 ecrit `2026.08.12 15:30`. On accepte aussi les tirets."""
    s = (s or "").strip().replace("/", ".").replace("-", ".")
    for f in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"):
        try:
            return dt.datetime.strptime(s, f)
        except ValueError:
            pass
    return None


def flt(x):
    x = (x or "").strip()
    if not x:
        return None
    try:
        return float(x)
    except ValueError:
        return None


def decalage(lignes):
    """Le decalage serveur -> machine, LU dans l en-tete.

    Une constante en dur aurait tenu jusqu au prochain changement
    d heure. Ici les deux horloges viennent du fichier lui-meme."""
    serveur = machine = None
    for l in lignes:
        if not l.startswith("#"):
            break
        if "TimeCurrent" in l:
            serveur = horo(l.split("=", 1)[-1])
        elif "TimeLocal" in l:
            machine = horo(l.split("=", 1)[-1])
    if serveur is None or machine is None:
        return None, ("en-tete sans TimeCurrent/TimeLocal : impossible "
                      "d etablir le decalage sans supposer")
    d = round((machine - serveur).total_seconds() / 60.0)
    return dt.timedelta(minutes=d), None


def charge(chemin):
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        lignes = f.read().splitlines()
    dec, err = decalage(lignes)
    if err:
        return None, None, err
    out = []
    entete_vue = False
    for l in lignes:
        if l.startswith("#") or not l.strip():
            continue
        p = l.split(";")
        if not entete_vue:
            entete_vue = True
            if p and p[0].strip() == "ts":
                continue
        if len(p) < 8:
            continue
        t = horo(p[0])
        if t is None:
            continue
        a, fc, pv = flt(p[5]), flt(p[6]), flt(p[7])
        out.append({"ts": t + dec, "ts_serveur": t,
                    "pays": p[1].strip(), "devise": p[2].strip(),
                    "evenement": p[3].strip(),
                    "importance": p[4].strip().upper() or "NONE",
                    "actual": a, "forecast": fc, "previous": pv})
    out.sort(key=lambda r: r["ts"])
    return out, dec, None


def verifie(evs, dec):
    """Confronte le decalage a un repere connu.

    Le CPI americain est publie a 14:30 heure de Paris. Si apres
    correction il ne tombe pas la, le decalage est faux -- et tout ce
    qu on croiserait ensuite le serait aussi, sans que rien ne le
    signale."""
    print("-" * LARG)
    print("VERIFICATION DU DECALAGE CONTRE UN REPERE CONNU")
    print("-" * LARG)
    print("  decalage lu dans l en-tete : %+d minutes"
          % (dec.total_seconds() / 60))
    cands = [e for e in evs
             if e["pays"] == "US" and "CPI" in e["evenement"].upper()
             and e["importance"] == "HIGH"]
    if not cands:
        print("  Aucun CPI americain HIGH dans le fichier : rien a")
        print("  confronter. Le decalage reste une deduction.")
        return
    print()
    print("  %-21s %-21s %s" % ("serveur", "corrige", "evenement"))
    heures = {}
    for e in cands[:10]:
        print("  %-21s %-21s %s"
              % (e["ts_serveur"].strftime("%Y-%m-%d %H:%M"),
                 e["ts"].strftime("%Y-%m-%d %H:%M"), e["evenement"][:40]))
    for e in cands:
        heures[e["ts"].strftime("%H:%M")] = heures.get(
            e["ts"].strftime("%H:%M"), 0) + 1
    dom = sorted(heures.items(), key=lambda x: -x[1])[0]
    print()
    print("  Heure corrigee la plus frequente pour un CPI US : %s"
          " (%d fois sur %d)" % (dom[0], dom[1], len(cands)))
    if dom[0] == "14:30":
        print("  => 14:30. C est l heure de publication reelle. Le")
        print("     decalage est confirme par un repere externe, pas")
        print("     seulement par l arithmetique de l en-tete.")
    else:
        print("  => ATTENTION : attendu 14:30, obtenu %s." % dom[0])
        print("     Le decalage deduit de l en-tete ne recolle pas avec")
        print("     la realite. Ne croiser AUCUNE donnee tant que ce")
        print("     desaccord n est pas compris.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("fichier")
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--importance", default="LOW",
                   help="garde ce niveau et au-dessus")
    p.add_argument("--pays", default=None, help="ex : US,EA")
    p.add_argument("--verifie", action="store_true")
    a = p.parse_args()

    evs, dec, err = charge(a.fichier)
    if err:
        print("KO : %s" % err)
        return 1

    print("=" * LARG)
    print("CALENDRIER MT5 REMIS A L HEURE DES CYCLES")
    print("=" * LARG)
    print("  %d evenement(s), du %s au %s (heure corrigee)."
          % (len(evs), evs[0]["ts"].strftime("%Y-%m-%d"),
             evs[-1]["ts"].strftime("%Y-%m-%d")))
    print()
    verifie(evs, dec)

    seuil = RANGS.get(a.importance.upper(), 1)
    pays = set(x.strip().upper()
               for x in a.pays.split(",")) if a.pays else None
    gardes = [e for e in evs
              if RANGS.get(e["importance"], 0) >= seuil
              and (pays is None or e["pays"].upper() in pays)]

    print()
    print("-" * LARG)
    print("SELECTION")
    print("-" * LARG)
    rep = {}
    for e in evs:
        rep[e["importance"]] = rep.get(e["importance"], 0) + 1
    print("  par importance : %s"
          % ", ".join("%s %d" % (k, rep[k]) for k in sorted(rep)))
    print("  retenus : %d (importance >= %s%s)"
          % (len(gardes), a.importance.upper(),
             ", pays %s" % a.pays if a.pays else ""))

    sans = sum(1 for e in gardes
               if e["actual"] is None or e["forecast"] is None)
    print("  dont %d sans surprise calculable (actual ou forecast"
          " absent)" % sans)

    d = os.path.dirname(a.sortie)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(a.sortie, "w", encoding="utf-8", newline="") as g:
        g.write("ts;ts_serveur;pays;devise;evenement;importance;"
                "actual;forecast;previous;surprise;surprise_rel\n")
        for e in gardes:
            s = ""
            sr = ""
            if e["actual"] is not None and e["forecast"] is not None:
                v = e["actual"] - e["forecast"]
                s = "%.6f" % v
                if e["forecast"] != 0:
                    sr = "%.4f" % (v / abs(e["forecast"]))
            g.write("%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s\n"
                    % (e["ts"].strftime("%Y-%m-%d %H:%M:%S"),
                       e["ts_serveur"].strftime("%Y-%m-%d %H:%M:%S"),
                       e["pays"], e["devise"],
                       e["evenement"].replace(";", ","),
                       e["importance"],
                       "" if e["actual"] is None else "%.6f" % e["actual"],
                       "" if e["forecast"] is None else "%.6f" % e["forecast"],
                       "" if e["previous"] is None else "%.6f" % e["previous"],
                       s, sr))
    print()
    print("  ecrit : %s (%d octets)"
          % (a.sortie, os.path.getsize(a.sortie)))

    print()
    print("=" * LARG)
    print("RESERVE A LIRE AVANT D UTILISER LA COLONNE `surprise`")
    print("=" * LARG)
    print("  Le forecast MT5 n est pas fiable partout. Sur le CPI y/y du")
    print("  12/08, MT5 annonce 2,7 quand TradingEconomics donne 3,4,")
    print("  pour un actual de 3,4. Selon la source, la publication est")
    print("  soit parfaitement conforme, soit la plus grosse surprise")
    print("  d inflation de l annee.")
    print()
    print("  Le prix tranche en faveur de TradingEconomics : ce jour-la")
    print("  la plus grosse amplitude sur 15 min valait 0,54 %, en")
    print("  DESSOUS du maximum journalier median.")
    print()
    print("  Donc : confronter le forecast a une seconde source avant")
    print("  qu une surprise serve a decider. Un evenement dont les deux")
    print("  sources desaccordent sort de l echantillon -- on ne choisit")
    print("  pas celle qui arrange le resultat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
