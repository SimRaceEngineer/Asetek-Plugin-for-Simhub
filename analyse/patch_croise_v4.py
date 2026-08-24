# -*- coding: utf-8 -*-
"""
patch_croise_v4.py -- le hors echantillon couvre AUSSI la barre precedente

  python patch_croise_v4.py --essai
  python patch_croise_v4.py

LE DEFAUT, MESURE ET PAS SUPPOSE

    Sortie du 24/08, parents US30 :

        PARENTS -- barre M1 PRECEDENTE
        ecart meilleure - pire : 18.22 par trade
        le hasard fait aussi bien 0 fois sur 400, soit 0.0 %

    C est le seul tableau significatif de tout le passage. Et le test
    hors echantillon ne l a jamais vu : etudie() ne transmettait que
    les bandes de la lecture LIVE. Le candidat le plus prometteur
    echappait donc au seul test qui distingue une regle d une
    coincidence.

CE QUE LE PATCH CHANGE

    etudie() rend desormais les deux series de bandes, et le hors
    echantillon tourne separement sur chacune -- parents comme miroirs.
    Rien d autre ne bouge : aucun seuil, aucune borne, aucun calcul.

    Le fichier passe de 51399 a 51957 octets. Si le patch annonce autre
    chose, la base n est pas la v3 et il ne faut pas l appliquer.

IDEMPOTENT. Sauvegarde horodatee avant ecriture.
"""
import argparse
import datetime
import io
import os
import shutil
import sys

CIBLE = "croise_flux.py"
ATTENDU_AVANT = 51399
ATTENDU_APRES = 51957

PAIRES = [
("    lignes, ninja, flux, trois = [], [], [], []\n",
 "    lignes, ninja, flux, trois, trois_n = [], [], [], [], []\n"),

("""        mn = mesure(S, debut_barre, duree, pas)
        if mn is not None:
            ninja.append((mn["bande"], res))
""",
 """        mn = mesure(S, debut_barre, duree, pas)
        if mn is not None:
            ninja.append((mn["bande"], res))
            trois_n.append((mn["bande"], res, sec))
"""),

("""        print("  Le fichier ne couvre probablement pas ces dates.")
        return None, None
""",
 """        print("  Le fichier ne couvre probablement pas ces dates.")
        return None, None, None
"""),

("""    bloc_contreflux(flux, MINI_CASE, rng, tirages)
    return lignes, trois
""",
 """    bloc_contreflux(flux, MINI_CASE, rng, tirages)
    return lignes, trois, trois_n
"""),

("""    tous_mou = []
    tous_trois = []
""",
 """    tous_mou = []
    tous_trois = []
    tous_ninja = []
"""),

("""        if par:
            _l, tp = etudie("PARENTS", par, S, decalage, a.tirages, rng,
                            retard=a.retard, duree=a.barre, pas=a.pas)
            if tp:
                bloc_hors_echantillon("PARENTS %s" % S.nom, tp,
                                      a.tirages, rng)
        m, tm = etudie("MIROIRS 220/230/240", mir, S, decalage, a.tirages,
                       rng, retard=a.retard, duree=a.barre, pas=a.pas)
        if m:
            tous_mou.extend(m)
        if tm:
            tous_trois.extend(tm)
""",
 """        if par:
            _l, tp, tpn = etudie("PARENTS", par, S, decalage, a.tirages,
                                 rng, retard=a.retard, duree=a.barre,
                                 pas=a.pas)
            if tp:
                bloc_hors_echantillon("PARENTS %s, flux LIVE" % S.nom, tp,
                                      a.tirages, rng)
            if tpn:
                bloc_hors_echantillon("PARENTS %s, barre M1 PRECEDENTE"
                                      % S.nom, tpn, a.tirages, rng)
        m, tm, tmn = etudie("MIROIRS 220/230/240", mir, S, decalage,
                            a.tirages, rng, retard=a.retard, duree=a.barre,
                            pas=a.pas)
        if m:
            tous_mou.extend(m)
        if tm:
            tous_trois.extend(tm)
        if tmn:
            tous_ninja.extend(tmn)
"""),

("""    if tous_trois:
        bloc_hors_echantillon("MIROIRS 220/230/240, les deux actifs",
                              tous_trois, a.tirages, rng)
""",
 """    if tous_trois:
        bloc_hors_echantillon("MIROIRS 220/230/240, flux LIVE",
                              tous_trois, a.tirages, rng)
    if tous_ninja:
        bloc_hors_echantillon("MIROIRS 220/230/240, barre M1 PRECEDENTE",
                              tous_ninja, a.tirages, rng)
"""),

("""    m, trois = etudie("BANC", trades, S, decalage, a.tirages, rng,
                      retard=a.retard, duree=a.barre, pas=a.pas)
""",
 """    m, trois, _tn = etudie("BANC", trades, S, decalage, a.tirages, rng,
                           retard=a.retard, duree=a.barre, pas=a.pas)
"""),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--essai", action="store_true",
                   help="verifie sans rien ecrire")
    p.add_argument("--fichier", default=CIBLE)
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("introuvable : %s" % a.fichier)
        return 1
    s = io.open(a.fichier, encoding="utf-8").read()
    avant = len(s.encode("utf-8"))
    print("%s : %d octets" % (a.fichier, avant))

    deja = sum(1 for _v, n in PAIRES if n in s)
    if deja == len(PAIRES):
        print("deja applique -- rien a faire.")
        return 0
    if deja:
        print("ETAT MIXTE : %d greffe(s) sur %d deja presente(s)."
              % (deja, len(PAIRES)))
        print("Ne pas continuer. Repars de croise_flux_v3.py.")
        return 1
    if avant != ATTENDU_AVANT:
        print("ATTENTION : %d octets au lieu de %d attendus."
              % (avant, ATTENDU_AVANT))
        print("La base n est pas la v3. Recopie croise_flux_v3.py")
        print("depuis le Drive avant d appliquer ce patch.")
        return 1

    for i, (vieux, _n) in enumerate(PAIRES, 1):
        c = s.count(vieux)
        if c != 1:
            print("ANCRE %d : %d occurrence(s) au lieu de 1." % (i, c))
            print("Rien n a ete ecrit.")
            return 1
    print("les %d ancres sont uniques." % len(PAIRES))

    neuf = s
    for vieux, nouveau in PAIRES:
        neuf = neuf.replace(vieux, nouveau, 1)
    apres = len(neuf.encode("utf-8"))
    print("resultat : %d octets (attendu %d)" % (apres, ATTENDU_APRES))
    if apres != ATTENDU_APRES:
        print("TAILLE INATTENDUE -- rien n a ete ecrit.")
        return 1

    try:
        compile(neuf, a.fichier, "exec")
    except SyntaxError as e:
        print("SYNTAXE CASSEE ligne %s : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1
    print("syntaxe verifiee.")

    if a.essai:
        print("")
        print("--essai : rien n a ete ecrit. Relance sans --essai.")
        return 0

    horo = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    sauve = "%s.%s.bak" % (a.fichier, horo)
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8", newline="\n").write(neuf)
    print("")
    print("sauvegarde : %s" % sauve)
    print("ecrit      : %s, %d octets" % (a.fichier, apres))
    return 0


if __name__ == "__main__":
    sys.exit(main())
