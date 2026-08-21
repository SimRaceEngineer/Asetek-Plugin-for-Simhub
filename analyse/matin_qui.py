# -*- coding: utf-8 -*-
"""
matin_qui.py -- QUI saigne avant 13h ? Et le fait-il aussi l apres-midi ?

  python matin_qui.py
  python matin_qui.py --coupure 13 --decalage 0
  python matin_qui.py --dimension magic

CE QUI PRECEDE

    matin_rendu.py a etabli que le bloc d avant 13h perd -15 820 sur 19
    seances, 16 rouges sur 19, binomial p = 0,0022, et que le total ne
    vire pas au vert en retirant les trois pires seances. Le bloc d
    apres 13h gagne +11 489. Ce script ne rejoue pas ce constat : il le
    decompose.

LA QUESTION, ET POURQUOI ELLE A DEUX REPONSES OPPOSEES

    Un magic peut perdre avant 13h pour deux raisons tres differentes :

      PROBLEME D HORAIRE  il perd le matin et GAGNE l apres-midi.
                          -> le magic est bon, son creneau ne l est pas.

      PROBLEME DE MAGIC   il perd le matin ET l apres-midi.
                          -> l heure n y est pour rien, c est le magic.

    Les deux colonnes sont donc imprimees cote a cote. Un classement du
    seul bloc du matin melangerait les deux cas et ferait couper des
    magics qui n ont pas de probleme d horaire du tout.

LE PIEGE DU CLASSEMENT

    Avec une vingtaine de magics et 19 seances, chercher lesquels sont
    "significativement" perdants revient a faire vingt tests. Trois ou
    quatre sortiront sous 0,05 par pur hasard. Le script compte les
    tests, dit combien de faux positifs attendre, et n emploie nulle
    part le mot significatif pour une ligne isolee. Le total et le
    compte de seances rouges sont la pour etre lus ensemble.

CE QU IL NE FAIT PAS

    Il ne recommande aucune coupure. Retirer les trades du matin
    changerait la marge, l exposition, l etat des trailings et le
    conditionnement des regles : l apres-midi ne se rejouerait pas a
    l identique. Les colonnes sont des constats, pas un contrefactuel.
"""
import argparse
import io
import json
import math
import os
import sys

try:
    import oos_v9 as O
except ImportError:
    print("KO : oos_v9.py introuvable a cote de ce script.")
    print("Il porte la normalisation des champs rails.")
    sys.exit(1)

DEFAUT = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
LARG = 78

# oos_v9 ne connait ni le magic ni le symbole : listes locales, et le
# script DIT laquelle a repondu au lieu de la supposer.
CLEFS_MAGIC = ["magic", "magic_number", "magicnumber", "mg", "expert_id",
               "expert", "magik"]
CLEFS_ACTIF = ["symbol", "actif", "symbole", "instrument", "asset",
               "pair", "sym"]


def trait(c="-"):
    print("  " + c * LARG)


def titre(t):
    print("")
    print("=" * (LARG + 4))
    print(t)
    print("=" * (LARG + 4))


def mediane(v):
    if not v:
        return 0.0
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def binom_unilateral(k, n):
    """P(X >= k) avec p = 1/2, exact."""
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(k, n + 1)) / float(2 ** n)


def quelle_clef(objets, clefs):
    """Quelle clef repond, et sur combien d objets. Pas de supposition."""
    for c in clefs:
        n = sum(1 for o in objets if o.get(c) not in (None, ""))
        if n:
            return c, n
    return None, 0


def charger(chemins):
    par, brut, bruts = {}, 0, []
    for ch in chemins:
        if not os.path.isfile(ch):
            continue
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
            par[tk] = {"jour": ts[:10], "heure": int(ts[11:13]), "pnl": pnl,
                       "brut": o}
            bruts.append(o)
    if not par:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        print("Repertoire courant : %s" % os.getcwd())
        sys.exit(1)
    return list(par.values()), bruts


def bloc_dimension(tk, dec, coupure, clef, nom):
    titre("%s -- avant %02dh et apres, cote a cote" % (nom.upper(), coupure))
    groupes = {}
    for t in tk:
        v = t["brut"].get(clef)
        if v in (None, ""):
            v = "(absent)"
        h = (t["heure"] + dec) % 24
        g = groupes.setdefault(str(v), {"av": [], "ap": [], "sav": {}})
        if h < coupure:
            g["av"].append(t["pnl"])
            g["sav"][t["jour"]] = g["sav"].get(t["jour"], 0.0) + t["pnl"]
        else:
            g["ap"].append(t["pnl"])

    lignes = []
    for v, g in groupes.items():
        s_av = sum(g["av"])
        s_ap = sum(g["ap"])
        seances = list(g["sav"].values())
        rouges = sum(1 for x in seances if x < 0)
        lignes.append((s_av, v, len(g["av"]), s_av, len(g["ap"]), s_ap,
                       rouges, len(seances)))
    lignes.sort()

    print("")
    print("   %-12s  n_av    avant %02dh   n_ap    apres %02dh   rouges"
          % (nom, coupure, coupure))
    trait()
    n_tests = 0
    for _k, v, n_av, s_av, n_ap, s_ap, rouges, n_s in lignes:
        if n_s:
            n_tests += 1
        verdict = ""
        if s_av < 0 and s_ap > 0:
            verdict = "  horaire"
        elif s_av < 0 and s_ap <= 0:
            verdict = "  perd partout"
        elif s_av >= 0 and s_ap > 0:
            verdict = "  gagne partout"
        print("   %-12s %5d %11.2f  %5d %11.2f   %2d/%-2d%s"
              % (v[:12], n_av, s_av, n_ap, s_ap, rouges, n_s, verdict))
    trait()
    tot_av = sum(l[3] for l in lignes)
    tot_ap = sum(l[5] for l in lignes)
    print("   %-12s %5d %11.2f  %5d %11.2f"
          % ("TOTAL", sum(l[2] for l in lignes), tot_av,
             sum(l[4] for l in lignes), tot_ap))

    print("")
    print("  horaire       : perd avant, gagne apres. Le magic va bien,")
    print("                  son creneau non.")
    print("  perd partout  : l heure n y est pour rien.")
    print("")
    print("  %d groupe(s) compares sur les memes 19 seances. A 0,05, il" % n_tests)
    print("  faut s attendre a %.1f ligne(s) faussement remarquable(s)."
          % (0.05 * n_tests))
    print("  Une ligne ne vaut donc rien seule : ce qui vaut, c est")
    print("  qu elle soit rouge EN SOMME et rouge SEANCE apres seance.")

    gros = [l for l in lignes if l[3] < 0 and l[7] >= 5]
    if gros:
        print("")
        print("  Les lignes rouges dont le signe est le plus regulier :")
        for _k, v, n_av, s_av, n_ap, s_ap, rouges, n_s in gros[:6]:
            p = binom_unilateral(rouges, n_s)
            print("    %-12s %8.2f avant, %2d/%-2d seances rouges, p = %.4f"
                  % (v[:12], s_av, rouges, n_s, p))
        print("    (p brut, non corrige du nombre de lignes essayees)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*", default=[DEFAUT])
    p.add_argument("--decalage", type=int, default=0)
    p.add_argument("--coupure", type=int, default=13,
                   help="premiere heure du bloc GARDE, en heure Paris")
    p.add_argument("--dimension", default="tout",
                   choices=["tout", "magic", "actif", "sens"])
    a = p.parse_args()

    tk, bruts = charger(a.fichier)
    jours = sorted(set(t["jour"] for t in tk))

    titre("QUI SAIGNE AVANT %02dh ?" % a.coupure)
    print("")
    print("  %d tickets, %d seances, du %s au %s"
          % (len(tk), len(jours), jours[0], jours[-1]))
    print("  coupure : %02dh Paris (decalage %+d h sur le journal)"
          % (a.coupure, a.decalage))
    print("  Lecture seule. Rien n est ecrit, rien n est envoye.")

    titre("CE QUE LE JOURNAL PORTE REELLEMENT")
    print("")
    dims = []
    for nom, clefs in (("magic", CLEFS_MAGIC), ("actif", CLEFS_ACTIF),
                       ("sens", O.CLEFS_SENS)):
        c, n = quelle_clef(bruts, clefs)
        if c is None:
            print("  %-8s : AUCUNE clef trouvee parmi %s"
                  % (nom, ", ".join(clefs)))
            continue
        vals = sorted(set(str(o.get(c)) for o in bruts
                          if o.get(c) not in (None, "")))
        print("  %-8s : clef \"%s\", %d/%d tickets, %d valeur(s)"
              % (nom, c, n, len(bruts), len(vals)))
        print("             %s%s"
              % (", ".join(vals[:12]), " ..." if len(vals) > 12 else ""))
        dims.append((nom, c))
    if not dims:
        print("")
        print("  Aucune des trois dimensions n existe dans ce journal.")
        print("  Rien a decomposer. Lance  python oos_v9.py --champs")
        print("  pour voir la liste exacte des colonnes disponibles.")
        sys.exit(1)

    for nom, c in dims:
        if a.dimension in ("tout", nom):
            bloc_dimension(tk, a.decalage, a.coupure, c, nom)

    print("")
    print("=" * (LARG + 4))
    print(" Aucune coupure n est recommandee ici. Retirer les trades du")
    print(" matin changerait marge, exposition et trailings : l apres-midi")
    print(" ne se rejouerait pas a l identique. Ce sont des constats.")
    print("=" * (LARG + 4))


if __name__ == "__main__":
    main()
