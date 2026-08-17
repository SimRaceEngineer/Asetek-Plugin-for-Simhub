# -*- coding: utf-8 -*-
r"""
audit_cadence.py -- quelle source de temps est saine, et laquelle ment

  python audit_cadence.py
  python audit_cadence.py --jours 2026-08-12,2026-08-13
  python audit_cadence.py --echantillon 1

POURQUOI CE FICHIER EXISTE

    Le 17/08, l autopsie de la bougie du 12/08 a imprime une fenetre
    "de 15 minutes" dont l ancre etait a 13:22:22 et la fin a
    15:22:24. Deux heures. Le compte de cycles etait juste ; la duree
    annoncee, fausse.

    La cause est simple et elle contamine TOUT ce qui a ete ecrit
    jusqu ici : mes outils comptent en NOMBRE DE CYCLES et convertissent
    en minutes avec un pas median. Un pas median de 10 s ne dit rien
    des trous. Des qu il y en a, "90 cycles" n est plus "15 minutes",
    et une amplitude sur 90 cycles n est plus comparable a une autre.

        cycles.jsonl -> breakout_range.py, bruit_par_actif.py,
                        rotation_tech_value.py, autopsie_choc.py

    Les quatre sont concernes. Avant de les corriger, il faut savoir
    de combien : un flux a 10 s avec trois trous par jour se repare en
    mesurant en temps ; un flux dont la moitie des intervalles depasse
    la minute ne se repare pas, il se remplace.

CE QU ON MESURE, POUR CHAQUE SOURCE ET CHAQUE JOURNEE

    n            nombre de lignes
    desordre     lignes dont l horodatage recule par rapport a la
                 precedente. Une seule suffit a fausser toute mesure
                 qui suppose l ordre -- c est-a-dire toutes les
                 miennes.
    p50 / p90    intervalle median et neuvieme decile, en secondes
    max          le plus grand trou de la journee
    > 60 s       combien d intervalles depassent la minute
    couvert      duree entre le premier et le dernier horodatage
    utile        la meme, MOINS la somme des trous de plus de 60 s.
                 C est le temps reellement observe.

    Le rapport `utile / couvert` est le seul chiffre qui compte : a
    90 %, une fenetre temporelle est fiable ; a 40 %, la journee est
    un gruyere et aucune fenetre glissante n a de sens dedans.

LES DEUX SOURCES COMPAREES

    cartes\cycles\cycles_<jour>.csv   la transcription de cycles.jsonl
    docs\buddha\<jour>\snapshots.csv  90 journees, 1,9 Go, avec les
                                      prix ET les positions ET le PnL

    snapshots.csv couvre 90 journees la ou cycles n en a que 18. Si sa
    cadence est saine, c est elle la base de travail, et cycles.jsonl
    ne sert plus qu aux champs d etat du moteur.

    Les snapshots sont gros : par defaut on ne lit que la premiere
    colonne, une ligne sur --echantillon, et jamais plus de --max-lignes
    par journee. Un echantillonnage regulier ne fausse pas la mesure
    des trous tant qu on le dit : un trou de plus de 60 s reste visible
    si on lit une ligne sur cinq d un flux a 10 s. Il fausserait la
    mesure du pas median, qui est donc affichee comme "pas x
    echantillon" et pas comme le pas reel.

LECTEUR SEUL. Aucun fichier ouvert en ecriture hors le .txt de sortie.
"""
import argparse
import io
import os
import sys
import datetime as dt

CYCLES = os.path.join("cartes", "cycles")
BUDDHA = os.path.join("docs", "buddha")
SORTIE = os.path.join("cartes", "panel_cadence.txt")
LARG = 100

_ECHO = []


def dis(s=""):
    _ECHO.append(s)
    print(s)


def horo(s):
    """Un horodatage, quel que soit le separateur date/heure.

    cycles.csv ecrit `2026-08-12 13:22:22`, churn_trades.jsonl ecrit
    `2026-08-12T13:22:22`. On ne suppose pas le format : on remplace le
    T et on coupe a 19 caracteres."""
    if not s:
        return None
    s = s.strip().replace("T", " ")
    try:
        return dt.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def quantile(v, q):
    if not v:
        return None
    v = sorted(v)
    i = int(q * (len(v) - 1))
    return v[i]


def lis_ts(chemin, colonne, sep, echantillon, maxi):
    """Les horodatages d un CSV, sans charger le reste.

    On ne lit QUE la colonne demandee. Sur un fichier de 150 Mo, tout
    parser pour en extraire une colonne prendrait des minutes et de la
    memoire pour rien."""
    out = []
    n = 0
    try:
        with io.open(chemin, encoding="utf-8", errors="replace") as f:
            tete = f.readline()
            if not tete:
                return out, 0, None
            cols = [c.strip() for c in tete.rstrip("\r\n").split(sep)]
            try:
                idx = cols.index(colonne)
            except ValueError:
                return out, 0, "colonne `%s` absente (en-tete : %s)" % (
                    colonne, ", ".join(cols[:6]))
            for l in f:
                n += 1
                if echantillon > 1 and n % echantillon:
                    continue
                p = l.split(sep, idx + 1)
                if len(p) <= idx:
                    continue
                t = horo(p[idx])
                if t:
                    out.append(t)
                if maxi and len(out) >= maxi:
                    break
    except OSError as e:
        return out, n, "illisible : %s" % e
    return out, n, None


def analyse(ts, facteur):
    """Ordre, intervalles, trous. Rien d autre.

    UN TROU EST RELATIF A LA SOURCE, PAS A UNE CONSTANTE. La premiere
    version ecrivait `d > 60.0` en dur. Sur un flux a 10 s c est
    raisonnable ; sur snapshots.csv, qui tourne a trois minutes, CHAQUE
    intervalle normal depassait 60 s, donc tout comptait comme trou et
    la part utile sortait a 0 % pour les vingt et une journees. Le
    fichier n y etait pour rien : c est le seuil qui etait faux.

    Un trou est donc un intervalle qui depasse `facteur` fois le pas
    median DE CETTE SOURCE-LA. Le seuil retenu est affiche, parce qu un
    seuil calcule qu on ne montre pas ne vaut pas mieux qu un seuil
    invente."""
    if len(ts) < 3:
        return None
    ecarts, desordre = [], 0
    for i in range(1, len(ts)):
        d = (ts[i] - ts[i - 1]).total_seconds()
        if d < 0:
            desordre += 1
            continue
        ecarts.append(d)
    if not ecarts:
        return None
    p50 = quantile(ecarts, 0.5) or 0.0
    seuil = facteur * p50 if p50 > 0 else 60.0
    tri = sorted(ts)
    couvert = (tri[-1] - tri[0]).total_seconds()
    trous = [d for d in ecarts if d > seuil]
    utile = couvert - sum(trous)
    return {"n": len(ts), "desordre": desordre,
            "p50": p50, "p90": quantile(ecarts, 0.9),
            "max": max(ecarts), "gros": len(trous), "seuil": seuil,
            "couvert": couvert, "utile": max(0.0, utile),
            "debut": tri[0], "fin": tri[-1]}


def ligne(nom, a, echantillon):
    if a is None:
        dis("  %-12s %s" % (nom, "trop peu de lignes pour juger"))
        return
    part = (a["utile"] / a["couvert"] * 100.0) if a["couvert"] > 0 else 0.0
    dis("  %-12s %7d %8d %7.0f %7.0f %8.0f %8.0f %6d %8.1f %8.1f %6.0f%%   %s"
        % (nom, a["n"], a["desordre"], a["p50"], a["p90"], a["max"],
           a["seuil"], a["gros"], a["couvert"] / 3600.0,
           a["utile"] / 3600.0, part,
           a["debut"].strftime("%H:%M") + "-" + a["fin"].strftime("%H:%M")))


def entete():
    dis("  %-12s %7s %8s %7s %7s %8s %8s %6s %8s %8s %6s   %s"
        % ("jour", "n", "desordre", "p50 s", "p90 s", "max s", "seuil s",
           "trous", "couvert", "utile", "part", "plage"))


def bilan(nom, tout, echantillon):
    dis()
    if not tout:
        dis("  %s : aucune journee lisible." % nom)
        return None
    n = len(tout)
    parts = [x["utile"] / x["couvert"] * 100.0 for x in tout
             if x["couvert"] > 0]
    des = sum(x["desordre"] for x in tout)
    dis("  %s : %d journee(s), part utile mediane %.0f %%, %d ligne(s)"
        % (nom, n, quantile(parts, 0.5) or 0.0, des))
    dis("  dans le desordre au total, pas median %.0f s%s."
        % (quantile([x["p50"] for x in tout], 0.5) or 0.0,
           " (x %d par l echantillonnage)" % echantillon
           if echantillon > 1 else ""))
    return quantile(parts, 0.5) or 0.0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cycles", default=CYCLES)
    p.add_argument("--buddha", default=BUDDHA)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--jours", default=None)
    p.add_argument("--echantillon", type=int, default=5,
                   help="une ligne sur N dans snapshots.csv")
    p.add_argument("--max-lignes", type=int, default=200000,
                   help="plafond de lignes retenues par journee")
    p.add_argument("--facteur", type=float, default=5.0,
                   help="un trou = plus de N fois le pas median")
    a = p.parse_args()
    voulus = set(x.strip() for x in a.jours.split(",")) if a.jours else None

    dis("=" * LARG)
    dis("AUDIT DE CADENCE -- QUELLE SOURCE DE TEMPS EST SAINE")
    dis("=" * LARG)
    dis("  genere %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dis()
    dis("  Ecrit apres avoir constate qu une fenetre annoncee a 15 min")
    dis("  durait deux heures : mes outils comptent des CYCLES et")
    dis("  convertissent avec un pas median, ce qui est faux des qu il")
    dis("  y a des trous.")
    dis()
    dis("  `utile` = duree couverte MOINS la somme des TROUS, un trou")
    dis("  etant un intervalle depassant %.0f fois le pas median DE LA"
        % a.facteur)
    dis("  SOURCE. Un seuil fixe a 60 s -- ce que faisait la premiere")
    dis("  version -- classait chaque intervalle normal de snapshots")
    dis("  (pas de trois minutes) comme un trou, et sortait 0 %% de part")
    dis("  utile sur vingt et une journees saines.")
    dis()
    dis("  Le rapport utile/couvert est le seul chiffre qui")
    dis("  decide : au-dessus de 90 %, une fenetre temporelle a un sens ;")
    dis("  a 40 %, la journee est un gruyere.")
    dis()
    dis("  `desordre` compte les lignes dont l horodatage RECULE. Une")
    dis("  seule suffit a fausser toute mesure qui suppose l ordre --")
    dis("  c est-a-dire toutes les miennes.")
    dis("=" * LARG)

    # ---- cycles ----
    dis()
    dis("-" * LARG)
    dis("SOURCE 1 : cartes\\cycles\\cycles_<jour>.csv  (issue de cycles.jsonl)")
    dis("-" * LARG)
    entete()
    tout_c = []
    if os.path.isdir(a.cycles):
        for nom in sorted(os.listdir(a.cycles)):
            if not nom.startswith("cycles_") or not nom.endswith(".csv"):
                continue
            j = nom[7:-4]
            if voulus and j not in voulus:
                continue
            ts, _, err = lis_ts(os.path.join(a.cycles, nom), "ts", ";",
                                1, a.max_lignes)
            if err:
                dis("  %-12s %s" % (j, err))
                continue
            r = analyse(ts, a.facteur)
            ligne(j, r, 1)
            if r:
                tout_c.append(r)
    else:
        dis("  %s introuvable." % a.cycles)
    part_c = bilan("cycles", tout_c, 1)

    # ---- snapshots ----
    dis()
    dis("-" * LARG)
    dis("SOURCE 2 : docs\\buddha\\<jour>\\snapshots.csv")
    dis("-" * LARG)
    dis("  Lecture d une ligne sur %d, colonne `ts` seule, %d lignes au"
        % (a.echantillon, a.max_lignes))
    dis("  plus par journee. L echantillonnage ne cache pas un trou de")
    dis("  plus de 60 s ; il multiplie en revanche le pas median par %d,"
        % a.echantillon)
    dis("  ce qui est signale et non corrige en douce.")
    dis()
    entete()
    tout_s = []
    if os.path.isdir(a.buddha):
        for j in sorted(os.listdir(a.buddha)):
            if voulus and j not in voulus:
                continue
            c = os.path.join(a.buddha, j, "snapshots.csv")
            if not os.path.isfile(c):
                continue
            ts, brut, err = lis_ts(c, "ts", ",", a.echantillon,
                                   a.max_lignes)
            if err:
                dis("  %-12s %s" % (j, err))
                continue
            r = analyse(ts, a.facteur)
            ligne(j, r, a.echantillon)
            if r:
                tout_s.append(r)
    else:
        dis("  %s introuvable." % a.buddha)
    part_s = bilan("snapshots", tout_s, a.echantillon)

    # ---- verdict ----
    dis()
    dis("=" * LARG)
    dis("VERDICT")
    dis("=" * LARG)
    if part_c is None and part_s is None:
        dis("  Aucune source lisible.")
    else:
        dis("  part utile mediane : cycles %s, snapshots %s"
            % ("%.0f %%" % part_c if part_c is not None else "n/a",
               "%.0f %%" % part_s if part_s is not None else "n/a"))
        dis("  journees disponibles : cycles %d, snapshots %d"
            % (len(tout_c), len(tout_s)))
        dis()
        if part_c is not None and part_c < 80:
            dis("  cycles.jsonl est TROUE. Les fenetres comptees en")
            dis("  nombre de cycles n y ont pas de duree fixe, donc les")
            dis("  amplitudes, les ratios de variance et les cassures")
            dis("  deja calcules dessus ne sont pas comparables entre")
            dis("  eux. Ce n est pas un reglage a ajuster : c est une")
            dis("  hypothese de base qui etait fausse.")
        elif part_c is not None:
            dis("  cycles.jsonl est assez regulier pour qu une fenetre")
            dis("  mesuree EN TEMPS ait un sens -- mais il faut quand")
            dis("  meme la mesurer en temps, pas en nombre de lignes.")
        if tout_s:
            dis()
            dis("  snapshots.csv couvre %d journees contre %d pour"
                % (len(tout_s), len(tout_c)))
            dis("  cycles, avec les prix, les positions et le PnL du")
            dis("  jour dans le meme fichier. Si sa part utile est")
            dis("  bonne, c est elle la base de travail, et cycles ne")
            dis("  sert plus que pour les champs d etat du moteur")
            dis("  (Bollinger, fractales, piege, IB) qu il est seul a")
            dis("  porter.")
        if sum(x["desordre"] for x in tout_c + tout_s):
            dis()
            dis("  ATTENTION : des lignes reculent dans le temps. Tout")
            dis("  outil qui lit ces fichiers doit TRIER par horodatage")
            dis("  avant de mesurer quoi que ce soit. Aucun des miens ne")
            dis("  le fait aujourd hui.")

    dis()
    dis("  Ce fichier ne mesure aucun marche. Il mesure la qualite de")
    dis("  l horloge, ce qui aurait du etre fait avant la premiere")
    dis("  statistique.")

    d = os.path.dirname(a.sortie)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.sortie, "w", encoding="utf-8").write("\n".join(_ECHO) + "\n")
    print()
    print("ecrit : %s (%d octets)" % (a.sortie, os.path.getsize(a.sortie)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
