# -*- coding: utf-8 -*-
r"""
extraire_cycles.py -- 34 Go de cycles ramenes a quelques Mo

  python extraire_cycles.py --schema
  python extraire_cycles.py
  python extraire_cycles.py --jours 2026-08-13,2026-08-14

POURQUOI

    docs\buddha\<jour>\cycles.jsonl contient un instantané COMPLET du
    moteur par cycle : 352 000 caracteres par ligne, ~1,8 Go par
    journee.

    DIX-HUIT journees sont disponibles, dont dix-sept en
    `cycles.jsonl.gz` -- 62 a 547 Mo compresses. Seules les deux plus
    recentes sont en clair. Une premiere version ne cherchait que le
    nom sans extension : elle annoncait "2 journees a traiter" et
    personne n aurait vu qu elle en ignorait dix-sept.

    On ne peut pas relire ca a chaque essai. On passe donc UNE fois,
    on garde une quinzaine de champs par actif, et on ecrit un CSV par
    journee. Le resultat tient dans quelques Mo et se relit en une
    seconde autant de fois qu on veut.

CE QU ON GARDE, ET POURQUOI CES CHAMPS-LA

    On ne definit AUCUNE notion nouvelle. La stack calcule deja ses
    propres cassures, ses propres ranges et ses propres niveaux ; on
    extrait les siennes.

      zones.bid                 le prix
      zones.nearest_top/bot     le niveau au-dessus / en dessous, avec
                                sa distance et son nombre de TENUES
      bollinger.upper/lower     un range chiffre
      bollinger.width_ratio     la largeur relative -- la volatilite
      bollinger.state           NORMAL / SQUEEZE / ...
      fractal.canal             TRENDING_UP / RANGE / ...
      fractal.fb                HL_BROKEN, LH_BROKEN : une structure
                                qui cede
      fractal.ev_label          TREND_DYING / ...
      fake_breakout_trap.level  le detecteur de FAUSSE cassure de la
                                stack, avec son side et son peak_price
      ib_state.range_status     l initial balance
      ib_state.position_pct     ou on est dedans

    Et a la racine, une fois par cycle :

      global_state.alignment    ALIGNED / DIVERGENT
      global_state.leader       l actif meneur, ou vide
      global_state.weakest      l actif le plus faible

    C est `leader` / `weakest` / `alignment` qui portent le "un actif
    casse pendant que les deux autres rendent" -- la stack le nomme
    deja, personne ne l a jamais mesure.

CE QU IL NE FAIT PAS

    Aucune analyse. Aucune definition de breakout. Il transcrit, il
    ne juge pas. Le qualificateur viendra ensuite, sur les CSV, et il
    pourra etre reecrit dix fois sans jamais relire les 34 Go.

REPRISE

    Un CSV par journee dans cartes\cycles\. Une journee deja extraite
    est sautee, sauf --force. On peut donc l arreter et le relancer :
    il reprend ou il en etait, ce qui compte quand une passe dure
    plusieurs minutes.

LECTEUR SEUL. Il n ouvre aucun fichier de la stack en ecriture, ne
touche a aucun processus, et peut tourner pendant que les traders
tournent -- il ne fait que lire des archives du jour precedent.
"""
import argparse
import csv
import gzip
import io
import json
import os
import sys
import time

RACINE = os.path.join("docs", "buddha")
SORTIE = os.path.join("cartes", "cycles")
ACTIFS = ("US30", "US500", "US100")

# Les colonnes, dans l ordre. Ecrites une fois ici et nulle part
# ailleurs : l en-tete du CSV et l extraction viennent de la meme
# liste, donc elles ne peuvent pas diverger.
CHAMPS = (
    ("bid", ("zones", "bid")),
    ("haut_prix", ("zones", "nearest_top", "price")),
    ("haut_dist", ("zones", "nearest_top", "dist")),
    ("haut_tenues", ("zones", "nearest_top", "held")),
    ("bas_prix", ("zones", "nearest_bot", "price")),
    ("bas_dist", ("zones", "nearest_bot", "dist")),
    ("bas_tenues", ("zones", "nearest_bot", "held")),
    ("bb_haut", ("bollinger", "upper")),
    ("bb_bas", ("bollinger", "lower")),
    ("bb_sma", ("bollinger", "sma20")),
    ("bb_ratio", ("bollinger", "width_ratio")),
    ("bb_etat", ("bollinger", "state")),
    ("fr_canal", ("fractal", "canal")),
    ("fr_fb", ("fractal", "fb")),
    ("fr_ev", ("fractal", "ev_label")),
    ("piege_niv", ("fake_breakout_trap", "level")),
    ("piege_side", ("fake_breakout_trap", "side")),
    ("piege_pic", ("fake_breakout_trap", "peak_price")),
    ("ib_etat", ("ib_state", "range_status")),
    ("ib_pos", ("ib_state", "position_pct")),
    ("biais", ("__racine__", "bias")),
    ("score", ("__racine__", "total_score")),
)


def source(dossier):
    """Le fichier de cycles d une journee, compresse ou non.

    Les journees archivees sont en `cycles.jsonl.gz` ; seules les deux
    plus recentes sont encore en clair. Une premiere version ne
    cherchait que le nom sans extension et ignorait donc DIX-SEPT
    journees sur dix-neuf, sans rien dire -- elle annoncait simplement
    "2 journees a traiter", ce qui ressemblait a une reponse.

    Un chercheur de fichiers qui ignore silencieusement la majorite de
    ses candidats est pire qu une erreur : il rend un resultat
    plausible."""
    for nom in ("cycles.jsonl", "cycles.jsonl.gz"):
        c = os.path.join(dossier, nom)
        if os.path.isfile(c):
            return c
    return None


def ouvre(chemin):
    """Un flux de texte, que le fichier soit compresse ou non."""
    if chemin.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(chemin, "rb"),
                                encoding="utf-8", errors="replace")
    return io.open(chemin, encoding="utf-8", errors="replace")


def creuse(d, chemin):
    """Descend un chemin de cles. Rend "" des qu une cle manque --
    jamais d exception : sur 100 000 cycles, un champ absent une fois
    ne doit pas arreter une passe de plusieurs minutes."""
    cur = d
    for c in chemin:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(c)
        if cur is None:
            return ""
    if isinstance(cur, (dict, list)):
        return ""
    return cur


def ligne_csv(rec):
    """Une ligne par cycle : l horodatage, l etat global, puis les
    champs de chaque actif."""
    g = rec.get("global_state") or {}
    out = [rec.get("ts") or "",
           g.get("alignment") or "",
           g.get("leader") or "",
           g.get("weakest") or ""]
    actifs = rec.get("assets") or {}
    for nom in ACTIFS:
        a = actifs.get(nom) or {}
        b = a.get("breakdown") or {}
        for _, chemin in CHAMPS:
            if chemin[0] == "__racine__":
                v = a.get(chemin[1])
                out.append("" if v is None or isinstance(v, (dict, list))
                           else v)
            else:
                out.append(creuse(b, chemin))
    return out


def entete():
    out = ["ts", "alignment", "leader", "weakest"]
    for nom in ACTIFS:
        for col, _ in CHAMPS:
            out.append("%s_%s" % (nom, col))
    return out


def une_journee(chemin, sortie, chaque):
    t0 = time.time()
    lus = casses = 0
    f = io.open(sortie, "w", encoding="utf-8", newline="")
    w = csv.writer(f, delimiter=";")
    w.writerow(entete())
    for l in ouvre(chemin):
        if not l.strip():
            continue
        try:
            rec = json.loads(l)
        except ValueError:
            casses += 1
            continue
        w.writerow(ligne_csv(rec))
        lus += 1
        if chaque and lus % chaque == 0:
            sys.stdout.write("\r    %d cycles, %.0f s" % (lus, time.time() - t0))
            sys.stdout.flush()
    f.close()
    if chaque:
        sys.stdout.write("\r")
        sys.stdout.flush()
    return lus, casses, time.time() - t0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", default=RACINE)
    p.add_argument("--sortie", default=SORTIE)
    p.add_argument("--jours", default=None,
                   help="liste separee par des virgules ; defaut : tous")
    p.add_argument("--force", action="store_true",
                   help="refait une journee deja extraite")
    p.add_argument("--chaque", type=int, default=500,
                   help="frequence d affichage de l avancement")
    p.add_argument("--schema", action="store_true",
                   help="lit UN cycle et montre ce qui serait extrait")
    a = p.parse_args()

    if not os.path.isdir(a.racine):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.racine)
        return 1
    jours = sorted(d for d in os.listdir(a.racine)
                   if source(os.path.join(a.racine, d)))
    if a.jours:
        voulus = set(x.strip() for x in a.jours.split(","))
        jours = [j for j in jours if j in voulus]
    if not jours:
        print("KO : aucune journee avec un cycles.jsonl.")
        return 1

    if a.schema:
        j = jours[-1]
        c = source(os.path.join(a.racine, j))
        rec = json.loads(ouvre(c).readline())
        cols = entete()
        vals = ligne_csv(rec)
        print("journee %s, premier cycle" % j)
        print("%d colonnes :" % len(cols))
        for k, v in zip(cols, vals):
            print("  %-22s %s" % (k, repr(v)[:60]))
        vides = sum(1 for v in vals if v == "")
        print()
        print("%d colonnes vides sur %d." % (vides, len(cols)))
        if vides > len(cols) / 2:
            print("ATTENTION : plus de la moitie est vide. Soit ce cycle")
            print("est hors seance, soit les chemins de CHAMPS sont faux.")
            print("Verifier sur un cycle de pleine seance avant la passe.")
        return 0

    if not os.path.isdir(a.sortie):
        os.makedirs(a.sortie)

    print("%d journee(s) a traiter." % len(jours))
    poids = sum(os.path.getsize(source(os.path.join(a.racine, j)))
                for j in jours)
    gz = sum(1 for j in jours
             if source(os.path.join(a.racine, j)).endswith(".gz"))
    print("Une passe complete lit %.1f Go sur disque (%d journee(s)"
          " compressee(s))." % (poids / 1e9, gz))
    if gz:
        print("Les .gz se decompressent a la volee : compter environ")
        print("trois a quatre fois ce poids en donnees lues.")
    print()
    total_l = total_c = 0
    t0 = time.time()
    for j in jours:
        dest = os.path.join(a.sortie, "cycles_%s.csv" % j)
        if os.path.isfile(dest) and not a.force:
            print("  %s : deja extrait (%d octets), saute."
                  % (j, os.path.getsize(dest)))
            continue
        src = source(os.path.join(a.racine, j))
        print("  %s : %.2f Go%s ..."
              % (j, os.path.getsize(src) / 1e9,
                 " compresse" if src.endswith(".gz") else ""))
        lus, casses, sec = une_journee(src, dest, a.chaque)
        total_l += lus
        total_c += casses
        print("  %s : %d cycles, %d lignes illisibles, %.0f s -> %d octets"
              % (j, lus, casses, sec, os.path.getsize(dest)))

    print()
    print("%d cycles extraits, %d lignes illisibles, %.0f s au total."
          % (total_l, total_c, time.time() - t0))
    if total_c:
        print("Les lignes illisibles sont comptees et ignorees ; si leur")
        print("nombre est important, le fichier source a ete tronque.")
    print("Sortie : %s" % a.sortie)
    print()
    print("Rien n a ete analyse. C est une transcription, pas une mesure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
