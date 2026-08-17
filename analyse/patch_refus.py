# -*- coding: utf-8 -*-
r"""
patch_refus.py -- trois defauts de refus_continuation.py, trouves par sa
                  propre premiere sortie

  python patch_refus.py --essai
  python patch_refus.py
  puis : python refus_continuation.py

1. TICK-NYSE N AURAIT JAMAIS DU ETRE MESURE

    Sortie du 17/08 :

        TICK-NYSE   APPROCHE  ecart 728   p 0.0005
        MES-continu APPROCHE  ecart  32   p 0.77
        YM-continu  APPROCHE  ecart  16   p 0.48

    Le SEUL declencheur detecte est sur le seul symbole qui ne peut
    pas en avoir. Le `delta` de TICK est un COMPTEUR MONOTONE -- z =
    +11,7, 130 seances positives sur 130 -- parce qu un indice n a pas
    de carnet d ordres. Le sommer sur soixante minutes ne mesure pas un
    flux, ca mesure la position dans la journee.

    Et 323 refus contre 83 continuations, ratio inverse des deux autres
    actifs, dit la meme chose autrement : un oscillateur borne revient
    toujours, ses cassures echouent par construction.

    TICK etait deja ecarte dans `flux_contre_prix.py`, dans
    `ecart_fenetre.py`, dans `bougie_deux_actifs.py`. J ai ecrit
    `refus_continuation.py` de zero et je n ai pas reporte l exclusion.

    C est mot pour mot l entree du 17/08 dans mistakes.md : "une regle
    notee mais appliquee a un seul endroit n est pas une regle, c est
    une anecdote". Elle vient de se verifier sur elle-meme.

    Le correctif ecarte EN TETE, avec la raison affichee, par les deux
    tests deja etablis ailleurs :

        min(cloture) <= 0            la serie traverse zero
        delta journalier de signe    compteur monotone, pas un carnet
        fige a plus de 95 %

2. LA COLONNE `DECISION` EST QUASI TAUTOLOGIQUE

        MES-continu   DECISION  -2120   p 0.0005

    Ca ressemble a un resultat. Ca n en est pas un. Le delta de la
    fenetre [t, t+H] et l issue mesuree en t+H sont presque la meme
    chose : on a mesure le meme jour que `rho(delta, rendement) = 0,675`
    sur MES a l echelle horaire.

    Dire "les refus ont un delta de decision negatif" revient a dire
    "les refus ont un rendement negatif" -- c est-a-dire leur
    DEFINITION.

    La colonne reste affichee, parce que la retirer cacherait le
    probleme au lieu de le nommer. Mais elle est marquee et elle ne
    porte plus aucun verdict.

3. UNE COLONNE SIGNIFICATIVE QUE LE VERDICT IGNORAIT

        YM-continu    VOLUME    ecart +2,1   p 0.0005

    Les refus se produisent sur un volume nettement superieur aux
    continuations. Significatif, et NON circulaire -- le volume n entre
    pas dans la definition de l issue.

    Le verdict ne le disait pas : sa logique ne regardait qu approche
    et decision. Le tableau imprimait le chiffre, la conclusion
    l ignorait. C est la faute du verdict qui ne lit pas sa table, une
    troisieme fois dans la journee, et cette fois par omission.

    Le verdict se calcule desormais sur APPROCHE et VOLUME, les deux
    seules colonnes qui ne redisent pas l issue.

4. `--jours` AU LIEU D UNE LISTE EN DUR

    Le 14/08 a ete ajoute par l utilisateur apres coup. Une liste de
    dates ecrite en dur vieillit entre deux messages.

CE QUE LE PATCH NE CHANGE PAS

    Ni la definition de l evenement, ni W, ni H, ni k, ni la
    permutation. Les 497 et 486 tentatives resteront 497 et 486 : si
    ces deux nombres bougent, le patch a touche autre chose que prevu.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import argparse
import io
import os
import shutil
import sys

CIBLE = "refus_continuation.py"
MARQUE = "ecarte_sans_carnet"

A1 = '''CITEES = ("2026-08-05", "2026-08-12", "2026-08-17")
'''
B1 = '''CITEES = "2026-08-05,2026-08-12,2026-08-14,2026-08-17"
'''

A2 = '''    p.add_argument("--tirages", type=int, default=2000)
    a = p.parse_args()
'''
B2 = '''    p.add_argument("--tirages", type=int, default=2000)
    p.add_argument("--jours", default=CITEES,
                   help="dates a MARQUER dans la table, separees par des "
                        "virgules ; elles ne sont pas traitees a part")
    a = p.parse_args()
    cites = tuple(x.strip() for x in a.jours.split(",") if x.strip())
'''

A3 = '''    if len(barres) < 1:
        dis("KO : aucun of_*.csv dans %s." % a.dossier)
        return 1
'''
B3 = '''    if len(barres) < 1:
        dis("KO : aucun of_*.csv dans %s." % a.dossier)
        return 1

    ecartes = ecarte_sans_carnet(barres)
    if ecartes:
        dis()
        for sym, raison in ecartes:
            dis("  %-16s ECARTE : %s" % (sym, raison))
        dis("  Un `delta` n est un carnet que si la serie EN A un. Sur")
        dis("  un indice, la colonne existe et ne veut rien dire : la")
        dis("  sommer sur une fenetre mesure la position dans la")
        dis("  journee, pas un flux.")
    if len(barres) < 1:
        dis("KO : plus aucun symbole apres exclusion.")
        return 1
'''

A4 = '''        vus = [e for e in tout[sym] if str(e["jour"]) in CITEES]
'''
B4 = '''        vus = [e for e in tout[sym] if str(e["jour"]) in cites]
'''

A5 = '''    dis("  Trois journees remarquees a l oeil sont trois journees")
    dis("  VECUES. Si elles se perdent au milieu de quarante, elles n")
    dis("  avaient rien de special et la regularite est ailleurs.")
    dis()
'''
B5 = '''    dis("  Marquees : %s" % ", ".join(cites))
    dis()
    dis("  Des journees remarquees a l oeil sont des journees VECUES.")
    dis("  Si elles se perdent au milieu de centaines, elles n avaient")
    dis("  rien de special et la regularite est ailleurs. Elles sont")
    dis("  comptees comme les autres, et seulement signalees ici.")
    dis()
'''

A6 = '''def par_jour(serie):
'''
B6 = '''def ecarte_sans_carnet(barres):
    """Retire les series qui n ont pas de carnet, et dit pourquoi.

    Deux tests, tous deux deja utilises ailleurs dans la stack -- ce
    qui est le point : ils existaient, et un outil ecrit de zero ne les
    avait pas repris.

    1. `min(cloture) <= 0` : la serie traverse zero, ce n est pas un
       prix mais un oscillateur signe.
    2. le delta journalier garde le meme signe sur plus de 95 % des
       seances : c est un compteur monotone, pas un solde acheteur
       contre vendeur. TICK-NYSE rend 130 sur 130.

    Le second est independant du premier : une serie pourrait etre
    positive et porter quand meme un faux delta."""
    out = []
    for sym in sorted(barres):
        cl = [b[1] for b in barres[sym]]
        if not cl:
            continue
        if min(cl) <= 0:
            out.append((sym, "la serie traverse zero -- oscillateur, "
                             "pas un prix"))
            continue
        pj = {}
        for b in barres[sym]:
            d = b[0].date()
            pj[d] = pj.get(d, 0.0) + b[2]
        s = [v for v in pj.values() if v]
        if len(s) >= 20:
            pos = sum(1 for v in s if v > 0)
            if pos >= 0.95 * len(s) or pos <= 0.05 * len(s):
                out.append((sym, "delta de signe fige, %d/%d seances "
                                 "du meme cote -- compteur monotone, "
                                 "pas un carnet" % (max(pos, len(s) - pos),
                                                    len(s))))
    for sym, _ in out:
        del barres[sym]
    return out


def par_jour(serie):
'''

A7 = '''        dis("    %-12s %12s %10s %10s" % ("mesure", "ecart", "p", "jours"))
'''
B7 = '''        dis("    %-12s %12s %10s %10s" % ("mesure", "ecart", "p", "jours"))
'''

A8 = '''        ea, pa = r["approche"]
        ed, pd = r["decision"]
        parle_avant = ea is not None and pa is not None and pa < 0.05
        parle_pendant = ed is not None and pd is not None and pd < 0.05
        if parle_avant and parle_pendant:
            dis("  %-16s le carnet DIFFERE DEJA PENDANT L APPROCHE." % sym)
            dis("  %-16s Il y a un declencheur mesurable avant que le" % "")
            dis("  %-16s refus ait lieu. C est le seul cas qui donne une" % "")
            dis("  %-16s avance, et il demande une verification hors" % "")
            dis("  %-16s echantillon avant d en faire quoi que ce soit." % "")
        elif parle_pendant:
            dis("  %-16s le carnet ne distingue les deux issues que" % sym)
            dis("  %-16s PENDANT. Il DECRIT le refus au moment ou il a" % "")
            dis("  %-16s lieu -- exact, instructif, et sans avance. Un" % "")
            dis("  %-16s flux live serait un compte rendu, pas un signal." % "")
        elif parle_avant:
            dis("  %-16s le carnet differe AVANT et plus apres." % sym)
            dis("  %-16s Resultat inhabituel : a verifier avant d y" % "")
            dis("  %-16s croire, il ressemble plus a un artefact qu a un" % "")
            dis("  %-16s signal." % "")
        else:
            dis("  %-16s AUCUNE des trois mesures ne separe les refus" % sym)
            dis("  %-16s des continuations. Sur cette definition d" % "")
            dis("  %-16s evenement, le carnet ne distingue pas les deux." % "")
'''
B8 = '''        ea, pa = r["approche"]
        ev, pv = r["vol"]
        parle_avant = ea is not None and pa is not None and pa < 0.05
        parle_vol = ev is not None and pv is not None and pv < 0.05
        if parle_avant:
            dis("  %-16s le carnet DIFFERE DEJA PENDANT L APPROCHE." % sym)
            dis("  %-16s Il y a un declencheur mesurable avant que le" % "")
            dis("  %-16s refus ait lieu. C est le seul cas qui donne une" % "")
            dis("  %-16s avance, et il demande une verification hors" % "")
            dis("  %-16s echantillon avant d en faire quoi que ce soit." % "")
            if parle_vol:
                dis("  %-16s Le volume aussi separe les deux issues." % "")
        elif parle_vol:
            dis("  %-16s rien n ANNONCE le refus, mais il se produit" % sym)
            dis("  %-16s sur un volume different (ecart %+.1f fois le" % ("", ev))
            dis("  %-16s volume minute median, p = %.4f). Ce n est pas" % ("", pv))
            dis("  %-16s une avance -- c est une signature SIMULTANEE," % "")
            dis("  %-16s lisible au moment ou ca se joue, pas avant." % "")
        else:
            dis("  %-16s ni l APPROCHE ni le VOLUME ne separent les" % sym)
            dis("  %-16s refus des continuations. Sur cette definition" % "")
            dis("  %-16s d evenement, le carnet ne previent de rien." % "")
'''

A9 = '''    dis("  Ecart = mediane(REFUS) - mediane(CONTINUATION).")
'''
B9 = '''    dis("  Ecart = mediane(REFUS) - mediane(CONTINUATION).")
    dis()
    dis("  LA COLONNE `DECISION` NE PORTE AUCUN VERDICT. Le delta de")
    dis("  [t, t+H] et l issue mesuree en t+H sont presque la meme")
    dis("  chose -- rho(delta, rendement) vaut 0,675 sur MES a l heure.")
    dis("  Dire `les refus ont un delta de decision negatif` revient a")
    dis("  dire `les refus ont un rendement negatif`, c est-a-dire leur")
    dis("  definition. Elle reste affichee pour que ce soit visible,")
    dis("  pas pour etre lue comme un resultat.")
    dis()
    dis("  Seules APPROCHE et VOLUME ne redisent pas l issue.")
'''

REMPLACEMENTS = [
    ("liste des dates -> chaine reglable", A1, B1),
    ("option --jours", A2, B2),
    ("exclusion des series sans carnet", A3, B3),
    ("usage de la liste reglable", A4, B4),
    ("annonce des journees marquees", A5, B5),
    ("fonction ecarte_sans_carnet()", A6, B6),
    ("mise en garde sur DECISION", A9, B9),
    ("verdict sur APPROCHE et VOLUME", A8, B8),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable." % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique. Rien n a ete touche.")
        return 0

    manque = []
    for nom, av, _ in REMPLACEMENTS:
        n = src.count(av)
        if n != 1:
            manque.append((nom, n))
    if manque:
        print("KO : ancres introuvables ou ambigues, rien n a ete ecrit.")
        for nom, n in manque:
            print("  %-40s %d occurrence(s), attendu 1" % (nom, n))
        return 1
    print("  les %d ancres sont uniques." % len(REMPLACEMENTS))

    out = src
    for nom, av, ap in REMPLACEMENTS:
        out = out.replace(av, ap, 1)

    try:
        compile(out, a.fichier, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (ligne %s : %s)."
              % (e.lineno, e.msg))
        print("Rien n a ete ecrit. L original est intact.")
        return 1

    print()
    print("Apres patch :")
    print("  - TICK-NYSE ecarte en tete, avec la raison affichee")
    print("  - DECISION affichee mais ne portant plus de verdict")
    print("  - verdict calcule sur APPROCHE et VOLUME")
    print("  - --jours au lieu d une liste de dates en dur")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauv = a.fichier + ".avant_refus"
    if not os.path.isfile(sauv):
        shutil.copy2(a.fichier, sauv)
    io.open(a.fichier, "w", encoding="utf-8", newline="").write(out)

    print()
    print("sauvegarde : %s" % sauv)
    print("%s : %d -> %d lignes."
          % (a.fichier, len(src.splitlines()), len(out.splitlines())))
    print()
    print("A VERIFIER SUR LA PROCHAINE SORTIE :")
    print("  MES-continu doit garder 497 tentatives, YM-continu 486.")
    print("  Si ces deux nombres bougent, le patch a touche autre chose")
    print("  que prevu -- la definition de l evenement n est pas censee")
    print("  changer d un iota.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
