#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_miroir_cvd5.py -- la branche 5 : meme entree, filtree par le CVD.

CE QU ELLE MESURE, ET POURQUOI ELLE EST NECESSAIRE
--------------------------------------------------
Le 25/08, la regle du delta croissant a ete mesuree a rebours sur 343
entrees : +403 EUR, positive aux cinq seuils essayes. Encourageant, et
pas une preuve -- 91 prises gardees sur huit jours.

La reconstruction a rebours a coute une journee : ticks introuvables,
horodatages dans deux bases differentes, delta lisse contre delta brut.
Une troisieme branche VIVANTE supprime toutes ces questions d un coup.
Elle prend la meme entree, au meme instant, au meme lot, avec la meme
sortie que le miroir 1 -- et le CVD pour SEULE difference.

    miroir 1   240004     sans filtre, sort avec son parent
    miroir 2  4240004     sans filtre, ancien regime de sortie
    miroir 5  5240004     FILTRE CVD, sort avec son parent

L ecart 1 contre 5 ne mesure donc que le filtre d entree. C est la
raison d etre de la branche, et c est ce qui impose qu elle sorte comme
le miroir 1 et non comme le miroir 2 : melanger deux differences, c est
ne plus savoir laquelle a joue.

LE FILTRE, EN LIVE, N A PAS BESOIN DE TICKS
    A rebours il fallait reconstituer la bougie en cours depuis les
    ticks. En live, MT5 la tient deja :

        copy_rates_from_pos(sym, TIMEFRAME_M1, 0, 2)

    rend la bougie EN COURS -- open, high, low, close du moment,
    tick_volume ecoule -- et la precedente close. La decomposition
    d Ankit s applique aux deux :

        delta = signe(close-open) x volume x |close-open| / (high-low)

    vente : on entre si delta_courant <= delta_precedent - CVD_PAS
    achat : on entre si delta_courant >= delta_precedent + CVD_PAS

    LE BRUT, PAS LE LISSE. L EMA14 qu affiche le panneau donne
    l inverse du bon signe : -56 EUR contre +403 sur les memes entrees.

MAX_MIROIRS PASSE DE 60 A 90, ET CE N EST PAS COSMETIQUE
    Ce plafond compte les BRANCHES, pas les parents. Le laisser a 60
    avec trois branches ne couvrirait plus que vingt parents au lieu de
    trente : les miroirs 1 et 2 changeraient de comportement et la
    comparaison en cours entre eux serait contaminee. 90 preserve le
    nombre de parents traites. Le garde-fou reste NIVEAU_MINI = 300 %.

LA DECISION EST JOURNALISEE MEME QUAND ELLE REFUSE
    Une entree refusee par le CVD ne laisse sinon aucune trace, et on
    ne saurait pas ce qu on a evite. Chaque decision ecrit sa ligne,
    avec les deux deltas qui l ont produite.

CE QUE CE PATCH NE FAIT PAS
    Il n exempte pas la branche 5 des modules de sortie : c est le role
    de papers_exempt, et il faut appliquer patch_exempt_cvd5.py AUSSI,
    sinon la branche 5 sortirait comme le miroir 2 et la mesure ne
    voudrait rien dire. Le patch refuse de s appliquer si ce module ne
    l est pas encore.

USAGE
-----
    python patch_miroir_cvd5.py                 <- simulation
    python patch_miroir_cvd5.py --appliquer
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

CIBLE_DEFAUT = r"C:\SVPS\Scalp-EA-main\miroir_papers.py"
SUFFIXE_BAK = ".bak_cvd5"
MARQUEUR = "def cvd_autorise("

R = []

R.append(('''MIROIR2 = True

MAX_MIROIRS = 60        # compte les DEUX branches''',
          '''MIROIR2 = True

# --- MIROIR 5 : la meme entree, filtree par le CVD ------------------------
# Le miroir 5 porte le magic prefixe d un 5 -- 240004 -> 5240004. Il sort
# COMME LE MIROIR 1 (papers_exempt doit couvrir la plage 5220000-5250000,
# c est le role de patch_exempt_cvd5.py) : l ecart 1 contre 5 ne mesure
# alors que le filtre d entree, et rien d autre.
#
# La regle : on n entre que si le desequilibre S AGGRAVE par rapport a la
# bougie M1 precedente close. Mesuree a rebours sur 343 entrees le 25/08,
# elle rapportait +403 EUR, positive aux cinq seuils de 0 a 10. Ce n est
# pas une preuve -- 91 prises gardees sur huit jours -- c est ce que
# cette branche est la pour trancher.
MIROIR5 = True
CVD_PAS = 1.0           # de combien le delta doit s aggraver

MAX_MIROIRS = 90        # compte les TROIS branches. 60 a deux branches
                        # couvrait trente parents ; le garder ici n en
                        # couvrirait plus que vingt, et les miroirs 1 et
                        # 2 changeraient de comportement.''', 1))

R.append(('''def magic_double(magic):
    """240004 -> 4240004. Hors de toute plage exemptee."""
    return int("4%d" % int(magic))''',
          '''def magic_double(magic):
    """240004 -> 4240004. Hors de toute plage exemptee."""
    return int("4%d" % int(magic))


def magic_cvd(magic):
    """240004 -> 5240004. DANS la plage exemptee, comme le miroir 1."""
    return int("5%d" % int(magic))


def _ankit(o, h, l, c, vol):
    """Le delta d une bougie selon V13_CVD.mq5, forme fermee.

    L indicateur repartit le volume autour de 50/50 en proportion du
    corps : buy = vol x (0,5 + p/2), sell = vol x (0,5 - p/2) avec
    p = |close-open| / (high-low). La difference se reduit donc a
    signe x vol x p, et une bougie a grosse meche contraire -- corps
    etroit, etendue large -- rend naturellement un delta faible.
    """
    etendue = h - l
    if etendue <= 0 or vol <= 0:
        return 0.0
    return vol * (abs(c - o) / etendue) * (1.0 if c >= o else -1.0)


def cvd_autorise(mt5, symbole, achat, pas=None):
    """(ok, delta_courant, delta_precedent). ok=None si illisible.

    En live, aucun tick n est necessaire : MT5 tient la bougie M1 EN
    COURS avec son OHLC du moment et son tick_volume ecoule. On la
    compare a la precedente CLOSE.

    Illisible -> None, et l appelant LAISSE PASSER. Un filtre qui
    bloquerait sur une lecture manquante transformerait une panne de
    donnees en decision de trading.
    """
    pas = CVD_PAS if pas is None else pas
    try:
        r = mt5.copy_rates_from_pos(symbole, mt5.TIMEFRAME_M1, 0, 2)
    except Exception:
        r = None
    if r is None or len(r) < 2:
        return None, 0.0, 0.0
    d = []
    for b in (r[0], r[1]):        # r[0] = precedente close, r[1] = en cours
        vol = float(b["real_volume"]) or float(b["tick_volume"])
        d.append(_ankit(float(b["open"]), float(b["high"]),
                        float(b["low"]), float(b["close"]), vol))
    prec, cour = d[0], d[1]
    ok = (cour >= prec + pas) if achat else (cour <= prec - pas)
    return ok, cour, prec''', 1))

R.append(('''                combien = 2 if MIROIR2 else 1
                tm, e = self.envoie(pos, rec, magic, nom, t_signal, combien)''',
          '''                # La decision CVD est prise AVANT le premier envoi :
                # elle determine combien d ordres la marge doit couvrir.
                cvd_ok, d_cour, d_prec = (None, 0.0, 0.0)
                if MIROIR5:
                    cvd_ok, d_cour, d_prec = cvd_autorise(
                        mt5, pos.symbol, pos.type == 0)
                prend_cvd = MIROIR5 and (cvd_ok is not False)
                combien = (1 + (1 if MIROIR2 else 0)
                           + (1 if prend_cvd else 0))
                tm, e = self.envoie(pos, rec, magic, nom, t_signal, combien)''',
          1))

R.append(('''                else:
                    dit("    M%s REFUSE : %s  -- paire incomplete,"
                        " ce parent ne comptera pas" % (m2, e2))
            ecrit_liens(self.liens)''',
          '''                else:
                    dit("    M%s REFUSE : %s  -- paire incomplete,"
                        " ce parent ne comptera pas" % (m2, e2))
                if not MIROIR5:
                    continue
                # La decision est dite DANS LES DEUX CAS : une entree
                # refusee ne laisserait sinon aucune trace, et on ne
                # saurait pas ce qu on a evite.
                m5 = magic_cvd(magic)
                if cvd_ok is None:
                    dit("    M%s CVD illisible -- laisse passer" % m5)
                elif not cvd_ok:
                    dit("    M%s CVD REFUSE  courant %+.1f contre"
                        " precedent %+.1f" % (m5, d_cour, d_prec))
                    continue
                else:
                    dit("    M%s CVD ok  courant %+.1f contre"
                        " precedent %+.1f" % (m5, d_cour, d_prec))
                tm5, e5 = self.envoie(pos, rec, m5, nom, t_signal, 1)
                if tm5:
                    self.liens.setdefault(tk, []).append((m5, tm5))
                    dit("    M%s envoye, ticket %s  (filtre CVD)"
                        % (m5, tm5))
                else:
                    dit("    M%s REFUSE : %s" % (m5, e5))
            ecrit_liens(self.liens)''', 1))


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cible", default=CIBLE_DEFAUT)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    print("=" * 68)
    print("patch_miroir_cvd5 -- %s"
          % ("APPLIQUER" if a.appliquer else "SIMULATION"))
    print("=" * 68)

    if not os.path.isfile(a.cible):
        print("introuvable : %s" % a.cible)
        return 2
    s = lire(a.cible)
    print("cible : %s  (%d lignes)" % (a.cible, s.count("\n") + 1))

    if MARQUEUR in s:
        print("")
        print("Deja corrige : cvd_autorise() est present.")
        return 0

    # L exemption d abord. Sans elle la branche 5 sortirait comme le
    # miroir 2, et l ecart mesure melangerait entree et sortie.
    exempt = os.path.join(os.path.dirname(a.cible), "papers_exempt.py")
    if os.path.isfile(exempt) and "5220000" not in lire(exempt):
        print("")
        print("REFUS : papers_exempt.py ne couvre pas encore la plage 5.")
        print("Sans elle, la branche 5 sortirait comme le miroir 2 et")
        print("l ecart mesure melangerait le filtre d entree et le regime")
        print("de sortie -- c est-a-dire ne mesurerait rien.")
        print("Appliquer patch_exempt_cvd5.py d abord.")
        return 1

    for i, (vieux, _n, att) in enumerate(R, 1):
        c = s.count(vieux)
        if c != att:
            print("")
            print("REFUS : motif %d attendu %d fois, trouve %d." % (i, att, c))
            print("   %s..." % vieux.strip().split("\n")[0][:58])
            return 1
    print("        les %d motifs sont la, aux bons comptes." % len(R))
    print("")
    print("a faire :")
    print("   + MIROIR5, CVD_PAS, magic_cvd(), _ankit(), cvd_autorise()")
    print("   ~ MAX_MIROIRS 60 -> 90, pour que les miroirs 1 et 2 gardent")
    print("     le meme nombre de parents")
    print("   + troisieme envoi, seulement si le CVD passe")
    print("   + la decision journalisee meme quand elle refuse")

    if not a.appliquer:
        print("")
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer.")
        return 0

    bak = a.cible + SUFFIXE_BAK
    if not os.path.exists(bak):
        shutil.copy2(a.cible, bak)
        print("")
        print("sauvegarde : %s" % bak)
    for vieux, neuf, _x in R:
        s = s.replace(vieux, neuf, 1)
    with io.open(a.cible, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print("ecrit : %s" % a.cible)

    relu = lire(a.cible)
    manques = [x for x in (MARQUEUR, "def magic_cvd(", "MAX_MIROIRS = 90",
                           "CVD REFUSE", "(filtre CVD)")
               if x not in relu]
    if manques:
        print("relu   : INCOMPLET, manque %s -- restaurer %s"
              % (", ".join(manques), bak))
        return 1
    print("relu   : les cinq marques attendues sont presentes.")
    try:
        compile(relu, a.cible, "exec")
        print("syntaxe: le fichier compile.")
    except SyntaxError as e:
        print("syntaxe: ERREUR ligne %s -- restaurer %s" % (e.lineno, bak))
        return 1

    print("")
    print("-" * 68)
    print("A FROID SEULEMENT. Ce module ouvre des positions reelles : il")
    print("prend effet a son prochain demarrage, pas maintenant.")
    print("Il reste ensuite a etendre la plage du pont (5220000-5249999),")
    print("sinon le compte dedie ne verra jamais la branche 5.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
