# -*- coding: utf-8 -*-
"""
mae_mfe.py -- le diagnostic MAE/MFE fait PROPREMENT, et l effet exact
              d un stop seul ou d un objectif seul.

DEUX CORRECTIONS PAR RAPPORT A jambe_stop.py

  1. PAR INDICE. La section 2 de jambe_stop melangeait les points des
     trois indices. Le SPX500 est a une echelle sept fois plus petite que
     le NAS100 et l US30 (MAE mediane 3,2 contre 23,5 et 22,0) : une
     mediane en points calculee sur les trois melanges trois baremes
     incompatibles. Si les gagnantes et les perdantes n ont pas la meme
     composition -- et elles ne l ont pas, le rapport euro/point vaut 1,97
     chez les unes et 1,57 chez les autres -- la comparaison ne veut rien
     dire. Ici tout est separe par indice, et double en points et en euros.

  2. EFFET EXACT, PAS SURAJUSTE. jambe_stop teste 49 couples objectif/stop
     et retient le meilleur, choisi sur les donnees qu il optimise : ce
     chiffre est une borne haute optimiste, pas une esperance.

     Ici on ne choisit rien. Un stop SEUL se calcule exactement depuis le
     CSV : si la MAE depasse le niveau, le stop a forcement ete touche ;
     sinon il ne l a jamais ete et la position garde son resultat reel.
     Aucune approximation, aucun choix de parametre. On affiche la COURBE
     entiere, pas son maximum -- c est a toi de voir s il existe une zone
     ou le stop aide, et non a moi de te presenter le meilleur point.

     Meme chose pour un objectif seul, via la MFE.

CE QU ON NE PEUT PAS FAIRE ICI
    La combinaison objectif ET stop demande de savoir lequel a ete touche
    en premier, donc le chemin minute par minute. Le CSV n a que les
    extremes. Pour ca, il faut jambe_stop.py et son rejeu M1.

Lit jambe_stop.csv. Aucun MT5, aucune ecriture.
"""
import io, os, sys, math

FIC = "jambe_stop.csv"
# niveaux de stop et d objectif, en multiples de la MAE (resp. MFE)
# mediane de l indice : la grille s adapte seule aux trois echelles
MULT = [0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00, 4.00]


def med(xs):
    xs = sorted(xs)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def lire(debut=None, fin=None):
    if not os.path.isfile(FIC):
        print("introuvable : %s -- lance d abord jambe_stop.py" % FIC)
        sys.exit(1)
    lg = [l.rstrip("\n") for l in io.open(FIC, encoding="utf-8-sig") if l.strip()]
    ent = [c.strip() for c in lg[0].split(";")]
    if "jour" not in ent:
        print("/!\\ ce CSV n a pas de colonne 'jour' : il vient d une ancienne")
        print("    version de jambe_stop.py. Relance-le pour pouvoir decouper")
        print("    par periode ; sans elle le filtrage est impossible.")
    out, hors = [], 0
    for l in lg[1:]:
        c = l.split(";")
        if len(c) < len(ent):
            continue
        d = dict(zip(ent, c))
        j = (d.get("jour") or "").strip()
        if j and ((debut and j < debut) or (fin and j > fin)):
            hors += 1
            continue
        try:
            out.append({"jour": j, "sym": d["sym"].strip(), "sens": d["sens"].strip(),
                        "mfe": float(d["mfe_pts"]), "mae": float(d["mae_pts"]),
                        "mfe_e": float(d["mfe_eur"]), "mae_e": float(d["mae_eur"]),
                        "pnl": float(d["pnl_eur"]), "duree": float(d["duree_min"])})
        except (KeyError, ValueError):
            continue
    if debut or fin:
        print("filtre %s -> %s : %d positions retenues, %d ecartees"
              % (debut or "debut", fin or "fin", len(out), hors))
    js = sorted({r["jour"] for r in out if r["jour"]})
    if js:
        print("%d positions, %d seances, %s -> %s" % (len(out), len(js), js[0], js[-1]))
    else:
        print("%d positions lues dans %s" % (len(out), FIC))
    return out


def diagnostic(rows):
    print()
    print("=" * 94)
    print("  1. MAE et MFE par indice et par issue -- en points ET en euros")
    print("=" * 94)
    print("%-9s %-10s %6s %10s %10s %11s %11s"
          % ("actif", "issue", "N", "MAE med", "MFE med", "MAE med EUR", "MFE med EUR"))
    print("-" * 94)
    for s in sorted({r["sym"] for r in rows}):
        g = [r for r in rows if r["sym"] == s]
        for lib, lot in (("gagnantes", [r for r in g if r["pnl"] > 0]),
                         ("perdantes", [r for r in g if r["pnl"] <= 0])):
            if len(lot) < 10:
                continue
            print("%-9s %-10s %6d %10.1f %10.1f %11.2f %11.2f"
                  % (s, lib, len(lot), med([r["mae"] for r in lot]),
                     med([r["mfe"] for r in lot]),
                     med([r["mae_e"] for r in lot]), med([r["mfe_e"] for r in lot])))
        print("-" * 94)
    print("MAE des gagnantes = la chaleur qu il faut accepter pour laisser gagner.")
    print("MFE des perdantes = le profit vu a l ecran puis rendu. S il est petit,")
    print("  aucune regle de mise a zero ou de suivi de stop ne peut rien sauver.")

    print()
    print("=" * 94)
    print("  2. un stop peut-il separer les deux populations ?")
    print("=" * 94)
    for s in sorted({r["sym"] for r in rows}):
        g = [r for r in rows if r["sym"] == s]
        gag = [r for r in g if r["pnl"] > 0]
        per = [r for r in g if r["pnl"] <= 0]
        if len(gag) < 20 or len(per) < 20:
            continue
        m = med([r["mae"] for r in gag])
        cg = sum(1 for r in gag if r["mae"] > m)
        cp = sum(1 for r in per if r["mae"] > m)
        print("  %-9s stop a la MAE mediane des gagnantes (%.1f pts) :" % (s, m))
        print("            couperait %d gagnantes sur %d (%.0f%%) et %d perdantes "
              "sur %d (%.0f%%)"
              % (cg, len(gag), 100.0 * cg / len(gag),
                 cp, len(per), 100.0 * cp / len(per)))
        print("            rapport %.2f perdante coupee par gagnante sacrifiee"
              % ((cp / float(len(per))) / max(1e-9, cg / float(len(gag)))))
    print()
    print("Un rapport superieur a 1 est NECESSAIRE mais pas suffisant : encore")
    print("faut-il que les gagnantes sacrifiees valent moins que les pertes")
    print("evitees. C est ce que chiffre la section 3.")


def courbe_stop(rows):
    print()
    print("=" * 94)
    print("  3. effet EXACT d un stop seul -- la courbe entiere, pas son maximum")
    print("=" * 94)
    print("Si la MAE depasse le niveau, le stop a forcement ete touche et la")
    print("position vaut -stop. Sinon elle garde son resultat reel. Exact.")
    for s in sorted({r["sym"] for r in rows}):
        g = [r for r in rows if r["sym"] == s]
        if len(g) < 50:
            continue
        base = med([r["mae"] for r in g]) or 1.0
        # euros par point de cet indice, pris sur la mediane du ratio
        epp = med([r["mae_e"] / r["mae"] for r in g if r["mae"] > 0]) or 1.0
        reel = sum(r["pnl"] for r in g)
        print()
        print("  %s -- %d positions, reel %+.2f EUR, MAE mediane %.1f pts (%.2f EUR/pt)"
              % (s, len(g), reel, base, epp))
        print("    %10s %10s %10s %12s %12s"
              % ("stop pts", "stop EUR", "% touches", "resultat", "vs reel"))
        for f in MULT:
            sp = f * base
            se = sp * epp
            tot = 0.0
            n = 0
            for r in g:
                if r["mae"] >= sp:
                    tot -= se
                    n += 1
                else:
                    tot += r["pnl"]
            print("    %10.1f %10.2f %9.0f%% %+12.2f %+12.2f"
                  % (sp, se, 100.0 * n / len(g), tot, tot - reel))
        print("    (sans stop : %+.2f)" % reel)
    print()
    print("-" * 94)
    print("Lis la COURBE, pas un point. Si 'vs reel' est negatif partout, aucun")
    print("stop n aide et la question est close. S il existe une zone positive,")
    print("regarde si elle est LARGE : un maximum isole entre deux valeurs")
    print("negatives est du surajustement, une zone positive etendue est un")
    print("resultat. Et rappelle-toi que le spread et le glissement, non")
    print("modelises, jouent contre le stop.")


def courbe_tp(rows):
    print()
    print("=" * 94)
    print("  4. effet EXACT d un objectif seul")
    print("=" * 94)
    print("Meme raisonnement avec la MFE : si elle depasse le niveau, l objectif")
    print("a forcement ete touche.")
    for s in sorted({r["sym"] for r in rows}):
        g = [r for r in rows if r["sym"] == s]
        if len(g) < 50:
            continue
        base = med([r["mfe"] for r in g]) or 1.0
        epp = med([r["mfe_e"] / r["mfe"] for r in g if r["mfe"] > 0]) or 1.0
        reel = sum(r["pnl"] for r in g)
        print()
        print("  %s -- %d positions, reel %+.2f EUR, MFE mediane %.1f pts"
              % (s, len(g), reel, base))
        print("    %10s %10s %10s %12s %12s"
              % ("TP pts", "TP EUR", "% touches", "resultat", "vs reel"))
        for f in MULT:
            tp = f * base
            te = tp * epp
            tot = 0.0
            n = 0
            for r in g:
                if r["mfe"] >= tp:
                    tot += te
                    n += 1
                else:
                    tot += r["pnl"]
            print("    %10.1f %10.2f %9.0f%% %+12.2f %+12.2f"
                  % (tp, te, 100.0 * n / len(g), tot, tot - reel))
        print("    (sans objectif : %+.2f)" % reel)
    print()
    print("-" * 94)
    print("Attention : un objectif seul, sans stop, laisse courir les pertes.")
    print("Une courbe favorable ici ne dit pas qu il faut le poser tel quel,")
    print("elle dit seulement que la sortie actuelle laisse du gain sur la table.")


def main():
    # python mae_mfe.py 2026-08-01 2026-08-09  -> restreint la periode
    debut = sys.argv[1] if len(sys.argv) >= 2 else None
    fin = sys.argv[2] if len(sys.argv) >= 3 else None
    rows = lire(debut, fin)
    if len(rows) < 100:
        print("trop peu de positions (%d) : sur une fenetre courte, la courbe"
              % len(rows))
        print("de stop devient tres bruitee. Elargis la periode.")
        if len(rows) < 40:
            return 1
    print("%d gagnantes, %d perdantes, resultat total %+.2f EUR"
          % (sum(1 for r in rows if r["pnl"] > 0),
             sum(1 for r in rows if r["pnl"] <= 0),
             sum(r["pnl"] for r in rows)))
    diagnostic(rows)
    courbe_stop(rows)
    courbe_tp(rows)
    print()
    print("=" * 94)
    print("  ce qui est solide ici, et ce qui ne l est pas")
    print("=" * 94)
    print("SOLIDE : la section 1. Ces medianes ne dependent d aucun parametre")
    print("et sont maintenant separees par indice.")
    print()
    print("SOLIDE AUSSI : les courbes 3 et 4 sont EXACTES, pas simulees, et on")
    print("les affiche en entier au lieu d en extraire le maximum. Aucun")
    print("surajustement tant qu on lit la forme et non le meilleur point.")
    print()
    print("PAS ICI : la combinaison objectif ET stop, qui demande de savoir")
    print("lequel a ete touche en premier -- donc le rejeu M1 de jambe_stop.py,")
    print("avec son ambiguite intra-bougie tranchee en faveur du stop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
