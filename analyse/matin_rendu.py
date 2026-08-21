# -*- coding: utf-8 -*-
"""
matin_rendu.py -- le gain du matin est-il RENDU a la preouverture US ?

  python matin_rendu.py
  python matin_rendu.py --decalage 1
  python matin_rendu.py --matin 8 9 --rendu 10 13

L HYPOTHESE, POSEE AVANT DE REGARDER

    "lorsque 08/09h paris sont rentables alors c est la tranche a 10h
     jusqu a 14h ou on reperd tout (preouverture us et actions qui
     commencent a coter)"

    Elle est directionnelle et anterieure aux chiffres : le test est
    donc unilateral, et c est une vraie pre-specification, pas une
    trouvaille d apres coup.

LE PIEGE, ET POURQUOI CE SCRIPT EXISTE

    Si la tranche 10h-14h perd TOUT LE TEMPS, alors en ne regardant que
    les seances ou le matin a gagne on verra "le gain est rendu" sans
    qu il y ait le moindre lien entre les deux. Le meme graphique
    illustre deux mondes tres differents :

      effet CRENEAU     10h-14h est negative, matin gagnant ou non.
                        -> la reponse est d abaisser le risque sur ce
                           creneau, tous les jours.

      effet DEPENDANCE  10h-14h est PLUS negative les jours ou le matin
                        a gagne.  <- c est l enonce de l utilisateur
                        -> la reponse est de couper APRES un bon matin,
                           ce qui est une regle entierement differente.

    Ce script mesure les deux separement. Le second est teste par
    permutation : on rebat au hasard quelles seances portent l etiquette
    "matin gagnant" et on regarde combien de fois le hasard fait aussi
    bien. Aucune loi normale n est supposee -- avec vingt seances elle
    ne tiendrait pas.

L HEURE

    entry_ts est journalise tel quel, dans l heure du serveur du
    courtier, qui n est pas forcement Paris. --decalage ajoute N heures
    pour obtenir Paris. Le script ne devine pas : il imprime l histogramme
    horaire des entrees, ou les bornes de seance se lisent a l oeil, et
    rappelle a quelles heures BRUTES correspondent les tranches choisies.
    Si l histogramme montre de l activite a 03h du matin, le decalage
    est faux.

CE QUE CA NE PROUVE PAS

    Le decoupage se fait sur l heure d ENTREE. Un ticket entre a 09h50
    et ferme a 12h compte dans le matin, alors que sa perte se realise
    dans la tranche suivante. "Le matin gagne puis rend" et "les memes
    positions se retournent" ne sont alors PAS distinguables. Si le
    journal porte une heure de cloture, le script refait le calcul
    dessus et compare ; sinon il le dit et s arrete la.
"""
import argparse
import io
import json
import math
import os
import random
import sys

try:
    import oos_v9 as O
except ImportError:
    print("KO : oos_v9.py introuvable a cote de ce script.")
    print("Il porte la normalisation des champs rails. La recopier ici")
    print("donnerait des chiffres incomparables avec le reste de l etude.")
    sys.exit(1)

DEFAUT = os.path.join("docs", "rails_trades", "tickets_rails.jsonl")
BASCULE = "2026-08-05"
SEANCES_MINI = 8
TIRAGES = 20000
GRAINE = 12345
LARG = 74

# Additif, et local : oos_v9 ne connait pas l heure de cloture. On ne
# touche pas au module partage pour autant -- il est la reference des
# autres scripts.
CLEFS_CLOSE = ["close_ts", "exit_ts", "close_time", "time_close",
               "exit_time", "ts_close", "closed_at"]


def trait(c="-"):
    print("  " + c * LARG)


def titre(t):
    print("")
    print("=" * (LARG + 4))
    print(t)
    print("=" * (LARG + 4))


def charger(chemins):
    """jour / heure d entree / heure de cloture / pnl. Lecture oos_v9."""
    par, brut, avec_close = {}, 0, 0
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
            cts = str(O._prem(o, CLEFS_CLOSE) or "")
            hc = None
            if len(cts) >= 16:
                try:
                    hc = int(cts[11:13])
                    avec_close += 1
                except ValueError:
                    hc = None
            par[tk] = {"jour": ts[:10], "heure": int(ts[11:13]),
                       "heure_close": hc, "jour_close": cts[:10] or None,
                       "pnl": pnl, "ticket": str(tk)}
    if not par:
        print("Aucun enregistrement exploitable sur %d lignes lues." % brut)
        print("Repertoire courant : %s" % os.getcwd())
        print("Verifie le chemin, ou lance  python oos_v9.py --champs")
        sys.exit(1)
    return list(par.values()), avec_close


def mediane(v):
    if not v:
        return 0.0
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def moyenne(v):
    return sum(v) / float(len(v)) if v else 0.0


def rangs(v):
    """Rangs moyens, ex aequo compris -- sans quoi rho est faux."""
    ordre = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(ordre):
        j = i
        while j + 1 < len(ordre) and v[ordre[j + 1]] == v[ordre[i]]:
            j += 1
        moy = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[ordre[k]] = moy
        i = j + 1
    return r


def pearson(x, y):
    n = len(x)
    if n < 3:
        return None
    mx, my = moyenne(x), moyenne(y)
    num = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    dx = sum((x[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((y[i] - my) ** 2 for i in range(n)) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def spearman(x, y):
    return pearson(rangs(x), rangs(y))


def hist_horaire(tk, dec):
    titre("REPERAGE DE L HEURE -- ou tombent les entrees")
    print("")
    print("  decalage applique : %+d h  (heure journal -> heure Paris)" % dec)
    print("  Si l activite ci-dessous ne colle pas a une seance connue,")
    print("  le decalage est faux et TOUT le reste l est aussi.")
    print("")
    print("   h Paris   entrees      P&L total    P&L median   par ticket")
    trait()
    for h in range(24):
        v = [t["pnl"] for t in tk if (t["heure"] + dec) % 24 == h]
        if not v:
            continue
        print("     %02d h  %8d  %12.2f  %12.2f  %11.2f"
              % (h, len(v), sum(v), mediane(v), moyenne(v)))
    trait()


def par_seance(tk, dec, h0, h1):
    """{jour: (pnl, n)} sur la tranche [h0, h1] incluse, heure Paris."""
    d = {}
    for t in tk:
        h = (t["heure"] + dec) % 24
        if h0 <= h <= h1:
            p, n = d.get(t["jour"], (0.0, 0))
            d[t["jour"]] = (p + t["pnl"], n + 1)
    return d


def permutation(a_signe, b_val, observe):
    """
    On rebat au hasard l appariement entre l etiquette "matin gagnant"
    et le resultat de l apres-midi. Le nombre de seances gagnantes est
    conserve : seul le lien est detruit. Unilateral, l enonce dit
    "plus negatif".
    """
    rng = random.Random(GRAINE)
    n = len(b_val)
    k = sum(1 for s in a_signe if s)
    if k == 0 or k == n:
        return None, 0
    idx = list(range(n))
    pire = 0
    for _ in range(TIRAGES):
        rng.shuffle(idx)
        ga = moyenne([b_val[idx[i]] for i in range(k)])
        pe = moyenne([b_val[idx[i]] for i in range(k, n)])
        if (ga - pe) <= observe:
            pire += 1
    return (pire + 1.0) / (TIRAGES + 1.0), k


def bloc_conditionnel(jours, A, B, etiquette):
    titre("L ENONCE : 10h-14h est-il PIRE quand le matin a gagne ?  %s"
          % etiquette)
    communs = sorted(set(A) & set(B))
    if len(communs) < 3:
        print("")
        print("  %d seance(s) portent les DEUX tranches. Rien a dire."
              % len(communs))
        return
    a_val = [A[j][0] for j in communs]
    b_val = [B[j][0] for j in communs]
    a_signe = [v > 0 for v in a_val]

    print("")
    print("   seance        matin    n     10h-14h    n      cumul")
    trait()
    for i, j in enumerate(communs):
        print("   %s  %9.2f %4d  %10.2f %4d  %9.2f"
              % (j, a_val[i], A[j][1], b_val[i], B[j][1],
                 a_val[i] + b_val[i]))
    trait()

    ga = [b_val[i] for i in range(len(communs)) if a_signe[i]]
    pe = [b_val[i] for i in range(len(communs)) if not a_signe[i]]
    print("")
    print("  EFFET CRENEAU -- 10h-14h, toutes seances confondues")
    print("    %d seances, total %.2f, mediane %.2f par seance"
          % (len(b_val), sum(b_val), mediane(b_val)))
    print("    seances rouges : %d / %d"
          % (sum(1 for v in b_val if v < 0), len(b_val)))
    print("")
    print("  EFFET DEPENDANCE -- 10h-14h selon le signe du matin")
    print("    matin GAGNANT (%2d seances) : 10h-14h moyenne %9.2f  mediane %9.2f"
          % (len(ga), moyenne(ga), mediane(ga)))
    print("    matin PERDANT (%2d seances) : 10h-14h moyenne %9.2f  mediane %9.2f"
          % (len(pe), moyenne(pe), mediane(pe)))
    if not ga or not pe:
        print("    Un des deux groupes est vide : rien de conditionnel a dire.")
        return
    ecart = moyenne(ga) - moyenne(pe)
    print("    ecart : %+.2f  (negatif = va dans le sens de l enonce)" % ecart)
    p, k = permutation(a_signe, b_val, ecart)
    if p is not None:
        print("    permutation unilaterale, %d tirages : p = %.4f"
              % (TIRAGES, p))
        if p > 0.10:
            print("    -> le hasard fait aussi bien une fois sur %d."
                  % max(1, int(round(1.0 / p))))
            print("       L effet DEPENDANCE n est pas etabli. Ce qui reste")
            print("       vrai, c est l effet creneau ci-dessus, et lui seul.")
        elif p > 0.05:
            print("    -> a la limite. Avec %d seances, c est insuffisant"
                  % len(b_val))
            print("       pour armer une regle.")
        else:
            print("    -> l ecart resiste au rebattage.")
    rho = spearman(a_val, b_val)
    if rho is not None:
        print("    rho de Spearman(matin, 10h-14h) = %+.3f" % rho)
        print("       negatif = plus le matin gagne, plus l apres perd.")
        print("       C est la version continue du meme enonce : si les")
        print("       deux se contredisent, aucun des deux ne tient.")

    print("")
    print("  \"ON REPERD TOUT\" -- litteralement, sur les %d matins gagnants"
          % len(ga))
    rendus, total_a, total_b = 0, 0.0, 0.0
    parts = []
    for i in range(len(communs)):
        if not a_signe[i]:
            continue
        total_a += a_val[i]
        total_b += b_val[i]
        if a_val[i] + b_val[i] <= 0:
            rendus += 1
        parts.append(-b_val[i] / a_val[i])
    print("    gagne le matin : %9.2f" % total_a)
    print("    rendu ensuite  : %9.2f" % total_b)
    if total_a:
        print("    soit %.0f %% du gain du matin" % (-100.0 * total_b / total_a))
    print("    seances ou tout est rendu (cumul <= 0) : %d / %d"
          % (rendus, len(ga)))
    print("    part rendue, mediane par seance : %.2f" % mediane(parts))
    print("    (1.00 = exactement tout rendu, >1 = au-dela du gain)")

    if len(b_val) < SEANCES_MINI:
        print("")
        print("  A LIRE AVEC PRUDENCE : %d seances seulement. Aucun p"
              % len(b_val))
        print("  n est interpretable a ce compte.")


def binom_unilateral(k, n):
    """P(X >= k) avec p = 1/2. Exact : n est petit, pas d approximation."""
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(k, n + 1)) / float(2 ** n)


def bloc_coupure(tk, dec):
    """
    L hypothese de depart parlait d une tranche qui rend le matin. Les
    chiffres montrent autre chose : un bloc d heures perdantes suivi
    d un bloc gagnant. Ce bloc-ci cherche ou passe la frontiere -- et
    surtout, verifie qu elle tient SEANCE par seance, pas seulement en
    somme. Une somme se fabrique avec deux mauvais jours.
    """
    titre("LA VRAIE COUPURE -- a quelle heure la stack bascule-t-elle ?")
    heures = sorted(set((t["heure"] + dec) % 24 for t in tk))
    print("")
    print("   couper a    avant (jete)   apres (garde)   tickets gardes")
    trait()
    meilleur, best = None, None
    for H in heures[1:]:
        av = sum(t["pnl"] for t in tk if (t["heure"] + dec) % 24 < H)
        ap = sum(t["pnl"] for t in tk if (t["heure"] + dec) % 24 >= H)
        n_ap = sum(1 for t in tk if (t["heure"] + dec) % 24 >= H)
        if best is None or ap > best:
            best, meilleur = ap, H
        print("     %02d h    %12.2f    %12.2f   %10d"
              % (H, av, ap, n_ap))
    trait()
    print("   Le total sans coupure : %.2f" % sum(t["pnl"] for t in tk))
    if meilleur is None:
        return
    print("")
    print("  L heure qui maximise ce qu on garde est %02d h (%+.2f)."
          % (meilleur, best))
    print("  Elle est choisie APRES avoir vu les chiffres, sur %d seaux"
          % (len(heures) - 1))
    print("  possibles. C est un choix in-sample : le chiffre ci-dessus")
    print("  est un plafond optimiste, jamais une esperance.")

    print("")
    print("  LE TEST QUI COMPTE -- le bloc jete est-il perdant SEANCE")
    print("  par seance, et pas seulement en somme ?")
    print("")
    print("   seance        avant %02dh      n" % meilleur)
    trait()
    par = {}
    for t in tk:
        if (t["heure"] + dec) % 24 < meilleur:
            p_, n_ = par.get(t["jour"], (0.0, 0))
            par[t["jour"]] = (p_ + t["pnl"], n_ + 1)
    lignes = sorted(par.items())
    for j, (p_, n_) in lignes:
        print("   %s  %11.2f   %4d" % (j, p_, n_))
    trait()
    vals = [p_ for _j, (p_, _n) in lignes]
    if not vals:
        return
    neg = sum(1 for v in vals if v < 0)
    n = len(vals)
    print("  %d seances, total %.2f, mediane %.2f"
          % (n, sum(vals), mediane(vals)))
    print("  seances rouges : %d / %d" % (neg, n))
    p = binom_unilateral(neg, n)
    print("  binomial exact unilateral contre 50/50 : p = %.4f" % p)
    if p > 0.05:
        print("  -> a ce compte de seances, un bloc aussi rouge peut sortir")
        print("     d une piece equilibree. Le total n est pas une preuve.")
    else:
        print("  -> le signe lui-meme est trop regulier pour du hasard.")
    print("")
    print("  Concentration -- le total tient-il sans les pires seances ?")
    ordonne = sorted(vals)
    for k in (1, 2, 3):
        if n - k >= 3:
            print("    sans les %d pire(s) : %11.2f  sur %d seances"
                  % (k, sum(ordonne[k:]), n - k))
    print("    Si le total vire au vert en retirant deux jours, il n y a")
    print("    pas de creneau perdant : il y a eu deux mauvais jours.")


def contrefactuel(tk, dec, h0, h1, r0, r1):
    titre("CE QUE COUTERAIT L ABSTENTION")
    tot = sum(t["pnl"] for t in tk)
    dedans = [t["pnl"] for t in tk
              if r0 <= (t["heure"] + dec) % 24 <= r1]
    matin = [t["pnl"] for t in tk
             if h0 <= (t["heure"] + dec) % 24 <= h1]
    print("")
    print("  total, toutes heures        : %10.2f  (%d tickets)"
          % (tot, len(tk)))
    print("  tranche %02dh-%02dh              : %10.2f  (%d tickets)"
          % (r0, r1, sum(dedans), len(dedans)))
    print("  total SANS la tranche       : %10.2f" % (tot - sum(dedans)))
    print("  tranche matin %02dh-%02dh        : %10.2f  (%d tickets)"
          % (h0, h1, sum(matin), len(matin)))
    print("")
    print("  Couper une tranche entiere n est pas la meme decision que")
    print("  couper apres un bon matin. Le premier chiffre depend de")
    print("  l effet creneau, le second de l effet dependance.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", nargs="*", default=[DEFAUT])
    p.add_argument("--decalage", type=int, default=0,
                   help="heures a AJOUTER a entry_ts pour obtenir Paris")
    p.add_argument("--matin", nargs=2, type=int, default=[8, 9],
                   help="tranche du matin, heures Paris incluses")
    p.add_argument("--rendu", nargs=2, type=int, default=[10, 13],
                   help="tranche de restitution, heures Paris incluses")
    p.add_argument("--bascule", default=BASCULE)
    a = p.parse_args()
    h0, h1 = a.matin
    r0, r1 = a.rendu
    dec = a.decalage

    tk, avec_close = charger(a.fichier)
    jours = sorted(set(t["jour"] for t in tk))

    titre("LE GAIN DU MATIN EST-IL RENDU A LA PREOUVERTURE US ?")
    print("")
    print("  %d tickets, %d seances, du %s au %s"
          % (len(tk), len(jours), jours[0], jours[-1]))
    print("  matin  : %02dh-%02dh Paris  (heures journal %02d-%02d)"
          % (h0, h1, (h0 - dec) % 24, (h1 - dec) % 24))
    print("  rendu  : %02dh-%02dh Paris  (heures journal %02d-%02d)"
          % (r0, r1, (r0 - dec) % 24, (r1 - dec) % 24))
    print("  Lecture seule. Rien n est ecrit, rien n est envoye.")

    hist_horaire(tk, dec)

    A = par_seance(tk, dec, h0, h1)
    B = par_seance(tk, dec, r0, r1)
    bloc_conditionnel(jours, A, B, "-- tout l historique")

    av = [t for t in tk if t["jour"] < a.bascule]
    ap = [t for t in tk if t["jour"] >= a.bascule]
    for sous, nom in ((av, "avant %s" % a.bascule),
                      (ap, "a partir du %s" % a.bascule)):
        if len(set(t["jour"] for t in sous)) >= 3:
            bloc_conditionnel(sorted(set(t["jour"] for t in sous)),
                              par_seance(sous, dec, h0, h1),
                              par_seance(sous, dec, r0, r1),
                              "-- %s" % nom)

    bloc_coupure(tk, dec)
    contrefactuel(tk, dec, h0, h1, r0, r1)

    titre("ATTRIBUTION -- entree ou cloture ?")
    print("")
    if avec_close == 0:
        print("  Aucune heure de cloture dans le journal (cherchee sous")
        print("  %s)." % ", ".join(CLEFS_CLOSE))
        print("")
        print("  Tout ci-dessus decoupe sur l heure d ENTREE. Un ticket")
        print("  entre a %02dh50 et ferme a %02dh compte donc dans le matin,"
              % (h1, r0 + 1))
        print("  alors que sa perte se realise apres. Avec ce journal,")
        print("  \"le matin gagne puis rend\" et \"les memes positions se")
        print("  retournent\" ne sont PAS distinguables. C est une limite")
        print("  du fichier, pas du raisonnement.")
    else:
        print("  %d ticket(s) sur %d portent une heure de cloture."
              % (avec_close, len(tk)))
        pont = [t for t in tk
                if t["heure_close"] is not None
                and h0 <= (t["heure"] + dec) % 24 <= h1
                and r0 <= (t["heure_close"] + dec) % 24 <= r1]
        print("  Entres le matin, fermes dans la tranche 10h-14h : %d,"
              % len(pont))
        print("  pour %.2f EUR. Ceux-la sont comptes dans le MATIN alors"
              % sum(t["pnl"] for t in pont))
        print("  que leur sort se joue apres : c est la part de l effet")
        print("  qui n est pas une histoire de creneau mais de duree.")

    print("")
    print("=" * (LARG + 4))
    print(" Rien n a ete ecrit, rien n a ete envoye.")
    print("=" * (LARG + 4))


if __name__ == "__main__":
    main()
