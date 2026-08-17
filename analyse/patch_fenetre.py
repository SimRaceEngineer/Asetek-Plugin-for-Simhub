# -*- coding: utf-8 -*-
r"""
patch_fenetre.py -- trois defauts de ecart_fenetre.py, dont un qui
multipliait l effectif par cinq

  python patch_fenetre.py

1. LE MEME INSTANT COMPTE CINQ FOIS

    Sortie reelle du 17/08 :

        2026-06-10   12:30 UTC   +1.9   -66.7   CPI m/m
        2026-06-10   12:30 UTC   +1.9   -66.7   Core CPI m/m
        2026-06-10   12:30 UTC   +1.9   -66.7   CPI y/y
        2026-06-10   12:30 UTC   +1.9   -66.7   Core CPI n.s.a. m/m
        2026-06-10   12:30 UTC   +1.9   -66.7   CPI

        cpi   n=15   ...   15/15 bas

    Le BLS publie cinq lignes de CPI a la meme seconde. Ce sont CINQ
    NOMS pour UNE FENETRE. Il n y a que trois dates de CPI dans la
    plage, et le tableau affichait quinze observations.

    Consequence directe : `15/15 bas` se lit comme une unanimite
    ecrasante -- une chance sur trente-deux mille -- alors que c est
    `3/3`, soit une chance sur huit. L effectif etait multiplie par
    cinq et la vraisemblance par quatre mille.

    Correctif : une fenetre = un (jour, heure, minute). Les noms
    fusionnes sont comptes et affiches, pour qu on voie ce qu on
    additionnait.

2. TICK-NYSE N AVAIT RIEN A FAIRE LA

    Mesure du matin : 130 seances positives sur 130, z = +11,4. Son
    `delta` est un compteur monotone -- un indice n a pas de carnet
    acheteur/vendeur. `ecart_carnets.py` l ecarte pour cette raison ;
    `ecart_fenetre.py`, ecrit apres, ne le faisait pas.

    Deux des trois tableaux de la sortie ne mesuraient donc rien, et
    le chiffre le plus spectaculaire -- `cpi 15/15 bas` -- etait dans
    l un d eux.

    Correctif : un symbole dont le CVD par seance ne change jamais de
    signe est ecarte, avec la raison affichee.

3. `nonfarm` AVALE L ADP

    `ADP Nonfarm Employment Change` contient "nonfarm" : il tombait
    dans la famille des `Nonfarm Payrolls`. Deux statistiques
    differentes, a deux heures differentes (12:15 et 12:30 UTC), dans
    la meme ligne de tableau.

    Correctif : les motifs sont essayes DU PLUS SPECIFIQUE AU PLUS
    GENERAL en cas d ambiguite, et surtout chaque famille affiche la
    liste des noms d evenements qu elle a absorbes. Une fusion abusive
    se voit alors immediatement, au lieu de se deduire.

Sauvegarde avant ecriture, refuse de s appliquer deux fois, et compile
le resultat AVANT de remplacer l original.
"""
import io
import os
import shutil
import sys

CIBLE = "ecart_fenetre.py"
MARQUE = "def fusionne("

# ---------------------------------------------------------------- 1
A1 = '''def main():
    p = argparse.ArgumentParser()
'''
B1 = '''def fusionne(evs):
    """Une FENETRE = un (jour, heure, minute).

    Le BLS publie cinq lignes de CPI a la meme seconde -- `CPI m/m`,
    `Core CPI m/m`, `CPI y/y`, `Core CPI n.s.a. m/m`, `CPI`. Ce sont
    cinq noms pour une fenetre. Les compter cinq fois multiplie
    l effectif par cinq et la vraisemblance d une unanimite par
    quatre mille : `15/15` se lit comme une chance sur trente-deux
    mille quand c est `3/3`, une chance sur huit.

    On garde le premier evenement de chaque instant comme
    representant, et on conserve TOUS les noms pour pouvoir les
    afficher."""
    par = {}
    for e in evs:
        cle = (e["t"].date(), e["t"].hour, e["t"].minute)
        if cle in par:
            par[cle]["noms"].append(e["ev"])
        else:
            e = dict(e)
            e["noms"] = [e["ev"]]
            par[cle] = e
    out = sorted(par.values(), key=lambda x: x["t"])
    return out


def signe_fige(serie):
    """Le CVD par seance de ce symbole change-t-il de signe ?

    TICK-NYSE sort 130 seances positives sur 130 : son `delta` est un
    compteur monotone, pas un desequilibre acheteur/vendeur. Un indice
    n a pas de carnet. `ecart_carnets.py` l ecarte deja ; ce fichier,
    ecrit apres, ne le faisait pas -- et deux de ses trois tableaux ne
    mesuraient donc rien."""
    par = {}
    for x in serie:
        j = x[0].date()
        par[j] = par.get(j, 0.0) + x[2]
    if len(par) < 20:
        return False
    return len(set(v > 0 for v in par.values())) < 2


def main():
    p = argparse.ArgumentParser()
'''

# ---------------------------------------------------------------- 2
A2 = '''    motifs = [x.strip().lower() for x in a.motif.split(",") if x.strip()]
    evs = lis_calendrier(a.calendrier, a.pays, a.importance, motifs)
    if not evs:
        print("KO : aucun evenement %s / %s portant les motifs %s."
              % (a.pays, a.importance, a.motif))
        return 1
'''
B2 = '''    # UN SYMBOLE SANS CARNET N EST PAS COMPARABLE.
    figes = [s for s, v in barres.items() if signe_fige(v)]
    for s in figes:
        del barres[s]
    if len(barres) < 2:
        print("KO : moins de deux symboles exploitables apres exclusion")
        print("     des signes figes (%s)." % ", ".join(figes))
        return 1

    motifs = [x.strip().lower() for x in a.motif.split(",") if x.strip()]
    evs = lis_calendrier(a.calendrier, a.pays, a.importance, motifs)
    if not evs:
        print("KO : aucun evenement %s / %s portant les motifs %s."
              % (a.pays, a.importance, a.motif))
        return 1
    brut = len(evs)
    evs = fusionne(evs)
'''

# ---------------------------------------------------------------- 3
A3 = '''    dis()
    dis("  %d evenement(s) retenu(s), a %d heure(s) distincte(s) :"
        % (len(evs), len(heures)))
'''
B3 = '''    dis()
    if figes:
        dis("  ECARTE(S) -- signe de CVD fige sur toutes les seances :")
        for s in figes:
            dis("    %s : son delta ne change jamais de signe. C est un"
                % s)
            dis("    compteur, pas un desequilibre acheteur/vendeur. Un")
            dis("    indice n a pas de carnet.")
        dis()
    if brut != len(evs):
        dis("  %d ligne(s) de calendrier ramenee(s) a %d FENETRE(S)."
            % (brut, len(evs)))
        dis("  Le BLS publie plusieurs lignes a la meme seconde -- cinq")
        dis("  pour un CPI. Les compter separement multiplie l effectif")
        dis("  sans ajouter une seule observation : une unanimite sur")
        dis("  %d LIGNES n est pas une unanimite sur %d OBSERVATIONS,"
            % (brut, brut))
        dis("  et la seule qui compte est celle sur %d." % len(evs))
        dis()
    dis("  %d fenetre(s) retenue(s), a %d heure(s) distincte(s) :"
        % (len(evs), len(heures)))
'''

# ---------------------------------------------------------------- 4
A4 = '''                lignes.append((d, e, ea, ed))
                dis("  %-12s %-10s %+9.1f %+9.1f   %s"
                    % (d, "%02d:%02d UTC" % (hh, mm), ea, ed,
                       e["ev"][:34]))
'''
B4 = '''                lignes.append((d, e, ea, ed))
                nom = e["ev"][:30]
                if len(e.get("noms", [])) > 1:
                    nom = "%s (+%d)" % (nom, len(e["noms"]) - 1)
                dis("  %-12s %-10s %+9.1f %+9.1f   %s"
                    % (d, "%02d:%02d UTC" % (hh, mm), ea, ed, nom))
'''

# ---------------------------------------------------------------- 5
A5 = '''            dis()
            dis("  `bas` = %s vendu plus durement que %s." % (sb, sa))
'''
B5 = '''            dis()
            dis("  CE QUE CHAQUE FAMILLE CONTIENT REELLEMENT :")
            for f in sorted(fam, key=lambda k: -len(fam[k])):
                noms = []
                for d, e, ea, ed in lignes:
                    if e["fam"] == f:
                        for n in e.get("noms", [e["ev"]]):
                            if n not in noms:
                                noms.append(n)
                dis("    %-10s %s" % (f[:10], ", ".join(noms[:4])))
                if len(noms) > 4:
                    dis("               ... et %d autre(s)"
                        % (len(noms) - 4))
            dis()
            dis("  Une famille qui melange deux statistiques differentes")
            dis("  -- ADP et Nonfarm Payrolls tombent tous deux sous le")
            dis("  motif `nonfarm`, a deux heures differentes -- produit")
            dis("  une mediane qui ne decrit ni l une ni l autre. Le")
            dis("  voir ici evite de le deduire.")
            dis()
            dis("  `bas` = %s vendu plus durement que %s." % (sb, sa))
'''

REMPLACEMENTS = [
    ("fonctions fusionne() et signe_fige()", A1, B1),
    ("exclusion des signes figes et fusion des instants", A2, B2),
    ("rapport de fusion et d exclusion", A3, B3),
    ("nom d evenement avec le compte des fusionnes", A4, B4),
    ("contenu reel de chaque famille", A5, B5),
]


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable." % CIBLE)
        return 1
    src = io.open(CIBLE, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique. Rien n a ete touche.")
        return 0

    manque = []
    for nom, a, _ in REMPLACEMENTS:
        n = src.count(a)
        if n != 1:
            manque.append((nom, n))
    if manque:
        print("KO : ancres introuvables ou ambigues, rien n a ete ecrit.")
        for nom, n in manque:
            print("  %-46s %d occurrence(s), attendu 1" % (nom, n))
        return 1

    out = src
    for nom, a, b in REMPLACEMENTS:
        out = out.replace(a, b, 1)

    try:
        compile(out, CIBLE, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (ligne %s : %s)."
              % (e.lineno, e.msg))
        print("Rien n a ete ecrit. L original est intact.")
        return 1

    sauv = CIBLE + ".avant_fenetre"
    if not os.path.isfile(sauv):
        shutil.copy2(CIBLE, sauv)
    io.open(CIBLE, "w", encoding="utf-8", newline="").write(out)

    print("%s : %d lignes -> %d lignes, %d remplacements."
          % (CIBLE, len(src.splitlines()), len(out.splitlines()),
             len(REMPLACEMENTS)))
    print("sauvegarde : %s" % sauv)
    print()
    print("CE QUI VA CHANGER, ET C EST BEAUCOUP :")
    print()
    print("  - TICK-NYSE disparait : deux des trois tableaux n avaient")
    print("    aucun sens. Il ne restera que YM contre MES.")
    print("  - cpi passe de n=15 a n=3, ism de n=12 a n=6. Le")
    print("    `15/15 bas` devient `2/3 bas`, ce qu il a toujours ete.")
    print("  - chaque famille affiche les noms qu elle contient : la")
    print("    fusion ADP / Nonfarm Payrolls sera visible.")
    print()
    print("Relancer : python ecart_fenetre.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
