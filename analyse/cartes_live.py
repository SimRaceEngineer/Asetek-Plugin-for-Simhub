#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""cartes_live.py -- le panneau des papers, mais rempli par le compte 182109.

  python cartes_live.py
  python cartes_live.py --html-seul
  python cartes_live.py --instantane docs\cartes_live\compte.json

CE QUE C EST
------------
La copie EXACTE de `cartes\panel_papers.txt` -- memes sections, memes
champs, meme ordre -- ou la seule chose qui change est la source de la
colonne CONSTATE : elle ne vient plus du papier mais du compte dedie
182109, celui que le pont alimente en copie conforme.

LES CHAMPS NE SONT PAS RECOPIES A LA MAIN, ILS SONT IMPORTES
------------------------------------------------------------
`papers_optimized.py` est importe. STRATEGIES, EXPORT, HORAIRE,
agrege(), wilson_bas() et rr_equilibre() viennent de lui. Une strategie
ajoutee la-bas apparait ici sans qu on y touche, avec ses vrais
libelles -- c est la lecon du 14/08 sur la barre de navigation :
RECOPIER AU LIEU DE CONCEVOIR, et mieux encore, ne pas recopier du tout.

L import est sans effet de bord : le module ne definit que des
constantes et des fonctions, son main() est sous `if __name__`.

Les noms des deux autres familles -- 2301xx-2303xx et 240001-240010 --
sont LUS dans papers_moteur.py et papers_regles.py par expression
reguliere, sans import : ces deux-la tirent des modules de la stack
derriere eux, et un panneau n a pas a les reveiller.

D OU VIENNENT LES CHIFFRES
--------------------------
De `docs\cartes_live\compte.json`, depose toutes les dix secondes par
l ENVOYEUR du pont. C est le seul processus connecte au terminal dedie,
et un processus Python ne peut etre connecte qu a un terminal : lui
seul peut rendre compte de ce compte. Ce panneau ne touche jamais MT5.

Si l instantane est absent ou vieux, il le DIT et n imprime pas de
chiffres. Un panneau qui affiche des zeros quand la source manque est
pire qu un panneau vide : on le lit comme un resultat.

CE QUI EST COMPTE
-----------------
Une AFFAIRE, pas un deal : les deals d une meme position sont sommes,
commissions et swaps compris. Compter les deals compterait deux fois
chaque trade et donnerait un taux de reussite faux.

Le miroir 2 porte le magic du miroir 1 prefixe d un 4 -- 4240004 pour
240004. Les deux branches sont comptees SEPAREMENT et affichees l une
sous l autre : elles ont la meme entree mais pas la meme sortie, et
c est precisement ce qu on veut pouvoir comparer.

OU IL ECRIT
-----------
    cartes\panel_papers_live.txt     le texte
    cartes\cartes_live.html          le meme, servi par /carte?f=...

Le dossier `cartes\` est relu a chaque requete par la route /cartes :
deposer le fichier suffit a le rendre visible, sans toucher a
price_action.py et donc sans redemarrer le panneau.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
from datetime import datetime

RACINE = os.path.dirname(os.path.abspath(__file__))
INSTANTANE = os.path.join(RACINE, "docs", "cartes_live", "compte.json")
SORTIE = os.path.join(RACINE, "cartes")
RASSIS = 120.0           # s au-dela desquelles l instantane est dit vieux
LARGE = 118


# ----------------------------------------------------------------------
# LES DEFINITIONS, IMPORTEES OU LUES -- JAMAIS RECOPIEES
# ----------------------------------------------------------------------
def charge_optimized():
    """STRATEGIES, EXPORT et les trois fonctions de papers_optimized."""
    if RACINE not in sys.path:
        sys.path.insert(0, RACINE)
    try:
        import papers_optimized as po
    except Exception as e:
        return None, "papers_optimized introuvable ou illisible (%s)" % e
    for nom in ("STRATEGIES", "EXPORT", "HORAIRE", "agrege", "wilson_bas",
                "rr_equilibre", "decoupe"):
        if not hasattr(po, nom):
            return None, "papers_optimized n a pas %s" % nom
    return po, ""


def noms_lus(fichier, motif):
    """(magic, nom) lus par expression reguliere, SANS import.

    papers_moteur et papers_regles importent des modules de la stack ;
    un panneau n a pas a les reveiller pour afficher un libelle."""
    chemin = os.path.join(RACINE, fichier)
    out = {}
    try:
        src = io.open(chemin, encoding="utf-8", errors="replace").read()
    except (IOError, OSError):
        return out
    for m in re.finditer(motif, src):
        try:
            out[int(m.group(1))] = m.group(2).strip()
        except (ValueError, IndexError):
            pass
    return out


def familles():
    """magic -> (nom, famille). Les trois familles du miroir."""
    t = {}
    for mag, nom in noms_lus("papers_moteur.py",
                             r"\((23\d{4}),\s*\"([^\"]+)\"").items():
        t[mag] = (nom, "DS")
    for mag, nom in noms_lus("papers_regles.py",
                             r"\((24\d{4}),\s*\"([^\"]+)\"").items():
        t[mag] = (nom, "MR")
    return t


# ----------------------------------------------------------------------
# L INSTANTANE
# ----------------------------------------------------------------------
def lis_instantane(chemin):
    try:
        with io.open(chemin, encoding="utf-8") as f:
            return json.load(f), ""
    except (IOError, OSError):
        return None, "absent"
    except ValueError:
        return None, "illisible (ecriture en cours ?)"


def base_et_branche(magic):
    """4240004 -> (240004, 2). 240004 -> (240004, 1)."""
    m = int(magic)
    if 4220000 <= m <= 4249999:
        return m - 4000000, 2
    return m, 1


def mesure(paquet):
    """(base, branche) -> compteurs. Une AFFAIRE, pas un deal."""
    par = {}

    def case(mag):
        b, br = base_et_branche(mag)
        return par.setdefault((b, br), {"n": 0, "gagnants": 0, "pnl": 0.0,
                                        "ouvertes": 0, "latent": 0.0,
                                        "volume": 0.0, "symboles": set()})

    for a in paquet.get("closes", []):
        mag = int(a.get("magic", 0) or 0)
        if not mag:
            continue
        c = case(mag)
        c["n"] += 1
        r = float(a.get("resultat", 0.0))
        c["pnl"] += r
        if r > 0:
            c["gagnants"] += 1
        c["volume"] += float(a.get("volume", 0.0))
        if a.get("sym"):
            c["symboles"].add(a["sym"])
    for p in paquet.get("ouvertes", []):
        mag = int(p.get("magic", 0) or 0)
        if not mag:
            continue
        c = case(mag)
        c["ouvertes"] += 1
        c["latent"] += float(p.get("latent", 0.0))
        if p.get("sym"):
            c["symboles"].add(p["sym"])
    return par


def constate(c, po):
    """Les memes grandeurs que la ligne ATTENDU, pour qu elles se
    comparent colonne par colonne. n=0 rend des tirets, pas des zeros :
    un taux de 0 % sur zero trade est un mensonge de mise en page."""
    if not c or c["n"] == 0:
        return None
    p = c["gagnants"] / float(c["n"])
    return {"n": c["n"], "taux": p, "borne": po.wilson_bas(p, c["n"]),
            "rr": po.rr_equilibre(p) if p > 0 else float("inf"),
            "pnl": c["pnl"], "pnl_tr": c["pnl"] / float(c["n"]),
            "ouvertes": c["ouvertes"], "latent": c["latent"]}


def masque(n):
    s = str(n)
    return s if len(s) < 5 else s[:2] + "*" * (len(s) - 4) + s[-2:]


# ----------------------------------------------------------------------
# LE RENDU -- MEMES SECTIONS, MEMES CHAMPS
# ----------------------------------------------------------------------
def rendu(paquet, po, noms, chemin):
    L = []
    a = L.append
    cpt = paquet["compte"]
    par = mesure(paquet)
    age = time.time() - float(paquet.get("ts", 0))

    a("=" * LARGE)
    a("PAPERS LIVE -- les memes strategies, remplies par le compte dedie")
    a("=" * LARGE)
    a("  horaire commun : %s" % po.HORAIRE)
    a("  magics         : 220001 -> 220012, 2301xx -> 2303xx,"
      " 240001 -> 240010")
    a("                   et leur miroir 2, le meme magic prefixe d un 4")
    a("  compte         : %s  %s  %s"
      % (masque(cpt.get("login", 0)), cpt.get("serveur", ""),
         cpt.get("devise", "")))
    a("  solde %.2f   equite %.2f   marge %.2f   niveau %.0f %%"
      % (cpt.get("solde", 0.0), cpt.get("equite", 0.0),
         cpt.get("marge", 0.0), cpt.get("niveau", 0.0)))
    a("  instantane     : %s, depose il y a %.0f s"
      % (os.path.basename(chemin), age))
    a("")
    a("  LA COLONNE ATTENDU EST CELLE DU PANNEAU PAPIER, INCHANGEE. Elle")
    a("  a ete figee avant, sur un export dont toutes les lignes etaient")
    a("  positives parce qu elles avaient ete retenues pour ca.")
    a("")
    a("  LA COLONNE CONSTATE EST REELLE. Elle vient des affaires closes")
    a("  du jour sur le compte %s, une affaire par position, commissions"
      % masque(cpt.get("login", 0)))
    a("  et swaps compris. C est elle qui tranchera.")
    a("")
    a("  Un jour d execution ne juge rien. Ce panneau ne sert qu a voir")
    a("  la copie vivre ; le verdict demandera des semaines.")
    a("")

    # ------------------------------------------------- le tableau
    a("-" * LARGE)
    a("%-8s %-30s %-2s | %5s %5s %6s %7s | %4s %5s %5s %7s %9s %11s"
      % ("MAGIC", "NOM", "BR", "nmax", "taux", "borne", "PnL/tr",
         "n", "taux", "borne", "PnL/tr", "PnL", "ouvertes"))
    a("%-8s %-30s %-2s | %-26s | %s"
      % ("", "", "", "  A T T E N D U", "  C O N S T A T E  (compte %s)"
         % masque(cpt.get("login", 0))))
    a("-" * LARGE)

    vus = set()
    for s in po.STRATEGIES:
        n_max, n_tot, taux, pnl_tr = po.agrege(s["croise"])
        b = po.wilson_bas(taux, n_tot)
        for br in (1, 2):
            c = constate(par.get((s["magic"], br)), po)
            if br == 2 and c is None:
                continue
            vus.add((s["magic"], br))
            a(ligne_tableau(s["magic"], s["nom"], br, n_max, taux, b,
                            pnl_tr, c))

    # Les deux autres familles : pas d ATTENDU chiffre derriere elles
    # dans papers_optimized. On ne l invente pas -- on laisse la moitie
    # gauche vide et on remplit ce qui est mesure.
    autres = sorted(k for k in par if k not in vus)
    if autres:
        a("-" * LARGE)
        for mag, br in autres:
            nom, fam = noms.get(mag, ("(non repertorie)", "?"))
            c = constate(par.get((mag, br)), po)
            a(ligne_tableau(mag, "%s [%s]" % (nom[:26], fam), br,
                            None, None, None, None, c))
    a("-" * LARGE)
    a("")
    a("  DS / MR la famille : DS = les strategies DeepSeek, 2301xx a")
    a("          2303xx ; MR = mes propres regles, 240001 a 240010.")
    a("  BR      1 = miroir 1, le magic du paper. 2 = miroir 2, le meme")
    a("          magic prefixe d un 4 : MEME entree, MEME lot, MEME")
    a("          instant -- seule la SORTIE differe. L ecart entre les")
    a("          deux lignes ne mesure donc que la gestion de sortie.")
    a("  nmax    PLAFOND d effectif du papier, pas une prevision.")
    a("  borne   borne basse de Wilson a 95 %. Sur quatre trades elle")
    a("          tombe tres bas, et c est exact : quatre trades ne")
    a("          disent rien. C est la seule colonne qui l avoue.")
    a("  ouvertes  positions encore en cours, et leur latent. Elles ne")
    a("          comptent NI dans n, NI dans le taux, NI dans le PnL.")
    a("")

    # ------------------------------------------------- le detail
    a("=" * LARGE)
    a("LE DETAIL, ET LA JUSTIFICATION DE CHAQUE CROISEMENT")
    a("=" * LARGE)
    for s in po.STRATEGIES:
        n_max, n_tot, taux, pnl_tr = po.agrege(s["croise"])
        a("")
        a("-" * LARGE)
        a("  %d  %s" % (s["magic"], s["nom"]))
        a("-" * LARGE)
        a("     unites   : %s" % s["tf"])
        a("     actifs   : %s" % s["actif"])
        a("     sens     : %s" % s["sens"])
        a("     horaire  : %s" % po.HORAIRE)
        a("     regle    : %s" % s["regle"])
        a("")
        a("     croise %d section(s) :" % len(s["croise"]))
        for k in s["croise"]:
            lib, n, t, p, x = po.EXPORT[k]
            sup = ("   [col. non identifiee : %s]" % x) if x else ""
            a("        %-30s n=%4d  %3.0f%%  PnL %+9.2f  (%5.2f/tr)%s"
              % (lib, n, 100 * t, p, p / float(n), sup))
        a("")
        a("     ATTENDU  n max %d   taux %.0f%%   borne basse %.0f%%"
          % (n_max, 100 * taux, 100 * po.wilson_bas(taux, n_tot)))
        a("              RR d equilibre %.2f   PnL/trade %.2f"
          % (po.rr_equilibre(taux), pnl_tr))
        for br in (1, 2):
            for ligne in bloc_constate(par.get((s["magic"], br)), po, br,
                                       cpt.get("login", 0)):
                a(ligne)
        a("")
        for ligne in po.decoupe(s["pourquoi"], LARGE - 10):
            a("     %s" % ligne)

    if autres:
        a("")
        a("=" * LARGE)
        a("LES DEUX AUTRES FAMILLES DU MIROIR")
        a("=" * LARGE)
        a("  Elles tournent sur le compte et le pont les copie comme les")
        a("  autres. Leur ligne ATTENDU n existe pas dans")
        a("  papers_optimized.py : je ne la fabrique pas. Les champs")
        a("  affiches sont ceux qui existent vraiment.")
        for mag, br in autres:
            nom, fam = noms.get(mag, ("(non repertorie)", "?"))
            a("")
            a("-" * LARGE)
            a("  %d  %s   [%s]   miroir %d" % (mag, nom, fam, br))
            a("-" * LARGE)
            a("     ATTENDU  -- absent, et non fabrique")
            for ligne in bloc_constate(par.get((mag, br)), po, br,
                                       cpt.get("login", 0)):
                a(ligne)

    a("")
    a("=" * LARGE)
    a("CE QUE CE PANNEAU NE DIT PAS")
    a("=" * LARGE)
    a("  Il ne dit pas si une strategie est bonne. Il dit ce qu elle a")
    a("  fait sur un compte, un jour, avec quelques trades.")
    a("")
    a("  Il ne dit rien non plus des entrees que le miroir n a PAS")
    a("  prises. Le pont copie ce qui existe ; ce qui a ete bloque en")
    a("  amont ne laisse aucune trace ici.")
    a("")
    a("  Genere le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return "\n".join(L)


def ligne_tableau(magic, nom, br, n_max, taux, borne, pnl_tr, c):
    if n_max is None:
        gauche = "%5s %5s %6s %7s" % ("--", "--", "--", "--")
    else:
        gauche = "%5d %4.0f%% %5.0f%% %7.2f" % (n_max, 100 * taux,
                                                100 * borne, pnl_tr)
    if c is None:
        droite = "%4s %5s %5s %7s %9s %8s" % ("0", "--", "--", "--", "--", "--")
    else:
        droite = "%4d %4.0f%% %4.0f%% %7.2f %+9.2f %4d %+7.2f" % (
            c["n"], 100 * c["taux"], 100 * c["borne"], c["pnl_tr"],
            c["pnl"], c["ouvertes"], c["latent"])
    return "%-8d %-30s %-2d | %s | %s" % (magic, nom[:30], br, gauche, droite)


def bloc_constate(c, po, br, login):
    """La ligne CONSTATE du panneau papier, remplie par le reel."""
    d = constate(c, po)
    tete = "     CONSTATE (%s, miroir %d)" % (masque(login), br)
    if d is None:
        if not c:
            return [] if br == 2 else ["%s  aucune affaire close" % tete]
        return ["%s  aucune affaire close -- %d ouverte(s), latent %+.2f"
                % (tete, c["ouvertes"], c["latent"])]
    L = ["%s  n %d   taux %.0f%%   borne basse %.0f%%"
         % (tete, d["n"], 100 * d["taux"], 100 * d["borne"]),
         "              RR d equilibre %.2f   PnL/trade %+.2f   PnL %+.2f"
         % (d["rr"], d["pnl_tr"], d["pnl"])]
    if d["ouvertes"]:
        L.append("              %d ouverte(s), latent %+.2f  -- non comptees"
                 % (d["ouvertes"], d["latent"]))
    return L


def page_html(txt):
    """Un FRAGMENT, pas une page complete : la route /carte prepose
    elle-meme le style et la barre du tableau de bord, lus dans
    price_action.py. Ecrire un <html> ici les ferait doublon."""
    e = (txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return ('<div style="padding:14px 18px">'
            '<h1 style="font-size:17px;color:#58a6ff;margin:6px 0">'
            'Cartes live -- papers sur le compte dedie</h1>'
            '<pre style="font:12px ui-monospace,Consolas,monospace;'
            'color:#c9d1d9;background:#0d1117;line-height:1.35;'
            'overflow-x:auto">' + e + '</pre></div>')


def defaut(chemin, raison, motif):
    L = ["=" * LARGE,
         "PAPERS LIVE -- pas de chiffres, et c est voulu",
         "=" * LARGE, "",
         "  L instantane du compte est %s." % raison,
         "      %s" % chemin, "",
         "  %s" % motif, "",
         "  Un panneau qui afficherait des zeros ici serait pire que ce",
         "  message : on lirait le zero comme un resultat.", "",
         "  L instantane est depose par l ENVOYEUR du pont, toutes les",
         "  dix secondes. S il manque : le pont ne tourne pas, ou il",
         "  tourne encore dans la version d avant le correctif.", "",
         "  Genere le %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instantane", default=INSTANTANE)
    ap.add_argument("--sortie", default=SORTIE)
    ap.add_argument("--html-seul", action="store_true",
                    help="n imprime pas le texte sur la console")
    args = ap.parse_args()

    po, erreur = charge_optimized()
    if po is None:
        print("REFUS : %s" % erreur)
        print("Ce panneau importe ses champs au lieu de les recopier.")
        print("Sans papers_optimized il n a rien a afficher, et il ne va")
        print("pas inventer douze strategies pour remplir la page.")
        return 1

    paquet, souci = lis_instantane(args.instantane)
    if paquet is None:
        txt = defaut(args.instantane, souci,
                     "Rien n a ete mesure, donc rien n est affiche.")
    else:
        age = time.time() - float(paquet.get("ts", 0))
        if age > RASSIS:
            txt = defaut(args.instantane, "vieux de %.0f s" % age,
                         "L envoyeur ne l a pas rafraichi : le pont est"
                         " arrete, ou bloque.")
        else:
            txt = rendu(paquet, po, familles(), args.instantane)

    if not args.html_seul:
        print(txt)

    if not os.path.isdir(args.sortie):
        os.makedirs(args.sortie)
    t = os.path.join(args.sortie, "panel_papers_live.txt")
    h = os.path.join(args.sortie, "cartes_live.html")
    io.open(t, "w", encoding="utf-8", newline="").write(txt + "\n")
    io.open(h, "w", encoding="utf-8", newline="").write(page_html(txt))
    print("")
    print("  ecrit : %s" % t)
    print("  ecrit : %s" % h)
    print("  visible sur  /carte?f=cartes_live.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
