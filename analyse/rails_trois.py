# -*- coding: utf-8 -*-
"""
rails_trois.py -- le panel rails en trois periodes : tendance, range, repare

  python rails_trois.py
  python rails_trois.py --bascule 2026-08-05 --patch 2026-08-12

POURQUOI TROIS COLONNES
    rails_range.py scindait au 05/08 pour que la jambe de tendance du
    28/07-04/08 ne contamine plus le range. Le 11/08 au soir, deux patchs
    ont change le chemin des ordres : le cran BE du trailing sort desormais
    de la fenetre de veto de C14, et les familles 207 d US30 rentrent dans
    le dispositif.

    Une troisieme periode commence donc le 12/08. La noyer dans le range
    referait exactement l erreur qu on a corrigee le 11 au matin : une
    moyenne entre deux regimes ne decrit aucun des deux.

CE QUE CE PANEL NE PEUT PAS FAIRE, ET C EST L ESSENTIEL
    Il ne mesure PAS l effet des patchs.

    La troisieme colonne separe deux choses qu on ne peut pas demeler ici :
    le trailing repare, et ce que le marche fait apres le 12/08. Si le P&L
    monte, on ne saura pas si c est le stop ou la seance. Si il baisse, pas
    davantage.

    Ce qui mesure les patchs, c est bande_morte.py, et pour une raison
    precise : il compte des MECANISMES -- le stop a-t-il ete pose, oui ou
    non -- pas des euros. Un mecanisme ne depend pas de l humeur du marche.

    Ce panel-la sert a autre chose : eviter que les statistiques d apres
    12/08 soient melangees a celles d avant. C est de l hygiene, pas une
    preuve.

LE PIEGE DE LA TROISIEME COLONNE
    Elle commencera avec une seance et une trentaine de tickets. A cette
    taille, n importe quelle cellule peut afficher n importe quoi.

    Le script marque donc toute cellule sous MINI tickets d un ?, comme
    rails_range, ET refuse de considerer la troisieme periode comme lisible
    tant qu elle compte moins de SEANCES_MINI seances. Le rappel est
    imprime en tete et en pied, parce que c est la seule ligne du fichier
    qui empechera de lire un bruit de trois jours comme un resultat.

CE QU IL LIT
    Les memes rails_trades*.jsonl que oos_v9.py, avec SA normalisation --
    importee, jamais recopiee. Plus le magic, comme rails_range.

    Et, s il le trouve, mfe_trail_events.csv : de quoi afficher par periode
    la part des tickets qui ont reellement obtenu un deplacement de stop.
    C est le pont entre "le mecanisme a change" et "le P&L a change", et il
    faut les deux pour conclure quoi que ce soit.
"""
import argparse
import csv
import io
import json
import os
import sys

try:
    import oos_v9 as O
except ImportError:
    print("KO : oos_v9.py introuvable a cote de ce script.")
    print("Il porte la normalisation des champs rails. La recopier ici")
    print("produirait deux lectures du meme fichier, donc des chiffres")
    print("incomparables avec rails_range et avec le gel V9.")
    sys.exit(1)

BASCULE = "2026-08-05"
PATCH = "2026-08-12"
MINI = 30           # sous ce nombre de tickets, une cellule ne se lit pas
SEANCES_MINI = 10   # sous ce nombre de seances, une periode ne se lit pas
CLEFS_MAGIC = ["magic", "magic_number", "magicnumber", "mg"]
CSV_TRAIL = "mfe_trail_events.csv"
OK = 10009          # TRADE_RETCODE_DONE
LARG = 100


def charger(chemins):
    """Comme oos_v9.charger, plus le magic. Meme normalisation, importee."""
    par = {}
    brut = 0
    for ch in chemins:
        for l in io.open(ch, encoding="utf-8-sig"):
            l = l.strip()
            if not l or l[0] != "{":
                continue
            brut += 1
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ts = str(O._prem(o, O.CLEFS_TS) or "")
            pnl = O._nombre(O._prem(o, O.CLEFS_PNL))
            tk = O._prem(o, O.CLEFS_TICKET)
            if len(ts) < 16 or pnl is None or tk is None or tk in par:
                continue
            mg = O._nombre(O._prem(o, CLEFS_MAGIC))
            s = {"jour": ts[:10], "hm": ts[11:16], "heure": ts[11:13],
                 "ticket": str(tk), "pnl": pnl, "sens": O._sens(o),
                 "magic": ("M%d" % int(mg)) if mg else "M?"}
            for tf in O.TFS:
                s["biais_" + tf.lower()] = O._etat_tf(o, tf)[0]
            par[tk] = s
    if not par:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        print("Lance  python oos_v9.py --champs  pour voir leur contenu.")
        sys.exit(1)
    return list(par.values())


def trail(chemin):
    """(tickets vus par le trail, tickets ayant obtenu un stop). Vide si
    le journal n est pas la : le panel tourne quand meme, sans ce bloc."""
    vus, avec = set(), set()
    if not os.path.isfile(chemin):
        return vus, avec
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            tk = str(r.get("ticket") or "").strip()
            if not tk:
                continue
            vus.add(tk)
            try:
                if int(float(r.get("retcode"))) == OK:
                    avec.add(tk)
            except (TypeError, ValueError):
                continue
    return vus, avec


def agrege(lot):
    p = sum(s["pnl"] for s in lot)
    n = len(lot)
    w = sum(1 for s in lot if s["pnl"] > 0)
    return p, n, w


def trio(lab, lots, largeur=22):
    """Une ligne : la meme cellule dans les trois periodes, cote a cote."""
    out = "%-*s" % (largeur, lab[:largeur])
    for lot in lots:
        if not lot:
            out += "%24s" % "-"
            continue
        p, n, w = agrege(lot)
        out += "%10.2f %5d %5s%2s" % (p / n, n, "%.0f%%" % (100.0 * w / n),
                                      "?" if n < MINI else "")
    return out


def bloc(titre, clef, lots, ordre=None, largeur=22):
    print()
    print("=" * LARG)
    print("  " + titre)
    print("=" * LARG)
    print("%-*s%24s%24s%24s"
          % (largeur, "", "1 TENDANCE", "2 RANGE", "3 REPARE"))
    print("%-*s%s" % (largeur, "", 3 * ("%10s %5s %5s%2s"
                                        % ("EUR/tr", "N", "WR", ""))))
    print("-" * LARG)
    g = [{} for _ in lots]
    for i, lot in enumerate(lots):
        for s in lot:
            g[i].setdefault(clef(s), []).append(s)
    cles = ordre if ordre is not None else sorted(
        set().union(*[set(x) for x in g]) if g else set())
    vu = False
    for c in cles:
        if not any(x.get(c) for x in g):
            continue
        print(trio(str(c), [x.get(c, []) for x in g], largeur))
        vu = True
    if not vu:
        print("  (aucune donnee -- le champ n est pas renseigne)")
    print("-" * LARG)


def main():
    global MINI
    p = argparse.ArgumentParser()
    p.add_argument("--bascule", default=BASCULE)
    p.add_argument("--patch", default=PATCH)
    p.add_argument("--fichier", nargs="*")
    p.add_argument("--csv", default=CSV_TRAIL)
    p.add_argument("--mini", type=int, default=MINI)
    a = p.parse_args()
    MINI = a.mini
    if not a.bascule < a.patch:
        print("KO : --bascule doit preceder --patch (%s >= %s)."
              % (a.bascule, a.patch))
        return 1

    ch = O.sources(a.fichier)
    lot = charger(ch)
    lot.sort(key=lambda s: (s["jour"], s["hm"]))

    p1 = [s for s in lot if s["jour"] < a.bascule]
    p2 = [s for s in lot if a.bascule <= s["jour"] < a.patch]
    p3 = [s for s in lot if s["jour"] >= a.patch]
    lots = [p1, p2, p3]
    jours = [sorted(set(s["jour"] for s in x)) for x in lots]
    noms = ["1 TENDANCE", "2 RANGE", "3 REPARE"]

    print("=== SCALP-EA / PANEL RAILS EN TROIS PERIODES ===")
    print("fichiers : %s" % ", ".join(os.path.basename(c) for c in ch))
    print("%d tickets, %s -> %s" % (len(lot), lot[0]["jour"], lot[-1]["jour"]))
    print()
    print("%-12s %-28s %8s %9s %12s %6s"
          % ("periode", "bornes", "seances", "tickets", "EUR total", "WR"))
    print("-" * LARG)
    bornes = ["j < %s" % a.bascule,
              "%s <= j < %s" % (a.bascule, a.patch),
              "j >= %s" % a.patch]
    for i in range(3):
        if not lots[i]:
            print("%-12s %-28s %8d %9d %12s %6s"
                  % (noms[i], bornes[i], 0, 0, "-", "-"))
            continue
        pn, n, w = agrege(lots[i])
        print("%-12s %-28s %8d %9d %12.2f %5.0f%%"
              % (noms[i], bornes[i], len(jours[i]), n, pn, 100.0 * w / n))
    print("-" * LARG)

    if not p3:
        print()
        print("LA TROISIEME PERIODE EST VIDE.")
        print("Les patchs ont pris effet au demarrage du moteur du 12/08 ;")
        print("avant la premiere seance complete, il n y a rien a y lire.")
        print("Le tableau ci-dessous montre le cadre, colonne 3 a blanc.")
    elif len(jours[2]) < SEANCES_MINI:
        print()
        print("LA TROISIEME PERIODE COMPTE %d SEANCE(S) SUR LES %d QU IL"
              % (len(jours[2]), SEANCES_MINI))
        print("FAUDRAIT. Elle ne se lit pas encore -- ni en bien ni en mal.")
        print("A cette taille, deux journees suffisent a retourner n importe")
        print("laquelle des lignes qui suivent. Regarde-la, ne conclus pas.")

    # ------------------------------------------------- sante du trailing
    vus, avec = trail(a.csv)
    print()
    print("=" * LARG)
    print("  LE MECANISME -- part des tickets ayant obtenu un stop")
    print("=" * LARG)
    if not vus:
        print("  %s introuvable : bloc non calcule." % a.csv)
        print("  C est pourtant lui qui dit si les patchs agissent. Sans ce")
        print("  fichier, les colonnes de P&L ci-dessous ne se rattachent a")
        print("  aucun mecanisme et ne prouvent rien.")
    else:
        print("%-12s %14s %14s %10s" % ("periode", "suivis trail",
                                        "avec stop", "part"))
        print("-" * LARG)
        for i in range(3):
            sv = [s for s in lots[i] if s["ticket"] in vus]
            if not sv:
                print("%-12s %14d %14s %10s" % (noms[i], 0, "-", "-"))
                continue
            na = sum(1 for s in sv if s["ticket"] in avec)
            print("%-12s %14d %14d %9.0f%%"
                  % (noms[i], len(sv), na, 100.0 * na / len(sv)))
        print("-" * LARG)
        print("  'suivis trail' ne compte que les tickets presents dans")
        print("  mfe_trail_events.csv : ceux dont le pic a franchi le seuil")
        print("  d armement, sur les actifs et magics que le module gere.")
        print("  C EST CETTE COLONNE QUI MESURE LES PATCHS. Elle doit bondir")
        print("  entre la periode 2 et la periode 3. Si elle ne bouge pas,")
        print("  les patchs n agissent pas et le reste du panel n a rien a")
        print("  voir avec eux.")

    # ------------------------------------------------------------ panneaux
    bloc("PAR HEURE D ENTREE", lambda s: s["heure"] + "h", lots,
         ordre=["%02dh" % h for h in range(24)])

    # Les magics sont composes : base + actif + pas de temps. La famille
    # regroupe le module, le magic entier isole la variante.
    fams = sorted(set(s["magic"][:4] for s in lot),
                  key=lambda f: -sum(1 for s in p2 if s["magic"][:4] == f))
    bloc("PAR FAMILLE DE MAGIC", lambda s: s["magic"][:4], lots, ordre=fams)

    mags = sorted(set(s["magic"] for s in lot),
                  key=lambda m: -sum(1 for s in p2 if s["magic"] == m))
    bloc("PAR MAGIC ENTIER", lambda s: s["magic"], lots, ordre=mags[:24])

    bloc("PAR SENS", lambda s: s["sens"] or "(inconnu)", lots,
         ordre=["ACHAT", "VENTE", "(inconnu)"])

    for tf in ("m1", "m3", "m5", "m15"):
        bloc("BIAIS DES RAILS %s x SENS" % tf.upper(),
             lambda s, t=tf: "%s / %s" % (s["biais_" + t] or "?",
                                          s["sens"] or "?"), lots)

    # ------------------------------------------------------------ lecture
    print()
    print("=" * LARG)
    print("  COMMENT LIRE, ET SURTOUT COMMENT NE PAS LIRE")
    print("=" * LARG)
    print("  1. Ce panel NE MESURE PAS les patchs. La colonne 3 melange le")
    print("     trailing repare et ce que le marche fait depuis le %s."
          % a.patch)
    print("     Les deux sont indemelables ici. Ce qui mesure les patchs,")
    print("     c est le bloc MECANISME ci-dessus et bande_morte.py : ils")
    print("     comptent des stops poses, pas des euros.")
    print("  2. L unite honnete est la seance, pas le ticket. La periode 3")
    print("     en compte %d." % (len(jours[2]) if p3 else 0))
    print("  3. Une cellule suivie de ? compte moins de %d tickets. Elle est"
          % MINI)
    print("     imprimee pour que rien ne soit cache, pas pour etre lue.")
    print("     Trois lectures externes du panel ont deja presente des")
    print("     cellules de 2 a 26 tickets comme des regles.")
    print("  4. Le gel V9 est ferme et rend son verdict le 01/09. Rien de ce")
    print("     qui sort d ici ne s y substitue, et rien ne se gele avant.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
