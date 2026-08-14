# -*- coding: utf-8 -*-
"""
patch_x60_miroir.py -- le meme releve pour x10, x20 et x30 que pour x60

  python patch_x60_miroir.py --essai
  python patch_x60_miroir.py

CE QUI MANQUE, ET POURQUOI C EST URGENT AU MEME TITRE QUE LE CONTEXTE

    x60_onset ecrit une ligne CLOTURE pour TOUS les tickets -- ca, c est
    acquis. Mais X60_ENTREE et X60_SORTIE, qui portent le `plateau`,
    ne sont ecrites QUE pour les x60.

    Le plateau, c est la photo de qui est en position a l instant ou
    une cellule entre : ticket, magic, actif, sens, volume, latent,
    age. C est exactement la matiere de la question posee -- "qui
    accompagne un x10 quand il entre, et ces accompagnants gagnent-ils"
    -- et c est une photo de positions VIVANTES. Elle ne se reconstitue
    pas apres coup : l historique dit qu un trade a existe, pas qui
    etait ouvert a la seconde ou un autre s ouvrait, ni avec quel
    latent.

    Donc, comme le contexte du papier : chaque heure sans ce patch est
    une heure ou les x10, x20 et x30 entrent et sortent sans temoin.

CE QUE LE PATCH FAIT

    1. SETUPS = ("10", "20", "30", "60"). SETUP reste a "60" et
       est_x60() n est pas touche.
    2. `plateau()` porte desormais le `setup` de chaque tierce, en plus
       du drapeau x60. Sans lui, "qui est la quand un x10 entre" ne
       distingue pas un voisin M2 d un voisin H1.
    3. Les entrees et sorties des setups 10, 20 et 30 produisent
       X_ENTREE et X_SORTIE -- meme charge utile que X60_*, plus un
       champ `setup`.
    4. CLOTURE porte le setup, ce qui permet de classer toutes les
       clotures sans redecouper le magic a la lecture.

CE QUI N EST PAS TOUCHE, ET C EST VOLONTAIRE

    X60_ENTREE et X60_SORTIE gardent leur nom et leur contenu exact.
    Le rapport existant lit les memes lignes qu avant et rend les memes
    chiffres. On AJOUTE un type d evenement a cote ; on n en renomme
    aucun, on n en fusionne aucun.

    Consequence pour qui lira : le setup 60 est dans X60_*, les trois
    autres dans X_*. Un lecteur qui veut les quatre prend l union et
    traite X60_* comme setup "60". C est le prix a payer pour ne pas
    casser ce qui tourne, et il est ecrit ici plutot que devine.

SIX ANCRES, chacune verifiee unique. IDEMPOTENT. Sauvegarde horodatee.
ast.parse, puis controle SUR L ARBRE que X_ENTREE et X_SORTIE sont
bien dans boucle() -- ailleurs elles compileraient sans jamais etre
ecrites -- et que est_x60, SETUP et les deux evenements d origine sont
intacts.

Observateur en lecture seule : aucun ordre. Prend effet au prochain
demarrage de x60_onset.
"""
import argparse
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "x60_onset.py"
MARQUEUR = "SETUPS = ("

A1 = '''SETUP = "60"
'''
N1 = '''SETUP = "60"
# Les quatre unites surveillees. SETUP reste a "60" et est_x60() n est
# pas touche : tout ce qui existe -- les tableaux du rapport, le
# filtrage des evenements -- continue de rendre exactement les memes
# chiffres. On AJOUTE le releve des trois autres a cote.
SETUPS = ("10", "20", "30", "60")
'''

A2 = '''            "x60": est_x60(p.magic),
        })
'''
N2 = '''            "x60": est_x60(p.magic),
            # Le setup de CHAQUE tierce, pas seulement le drapeau x60 :
            # sans lui, "qui est la quand un x10 entre" ne distingue pas
            # un voisin M2 d un voisin H1, et le croisement demande est
            # impossible. Ce releve photographie des positions vivantes
            # -- il ne se reconstitue pas apres coup.
            "setup": setup_de(p.magic),
        })
'''

A3 = '''                    connus[t] = {"magic": int(p.magic), "actif": str(p.symbol),
                                 "pic": lat, "creux": lat, "dernier": lat,
                                 "ouvert": maintenant(),
                                 "x60": est_x60(p.magic)}
'''
N3 = '''                    connus[t] = {"magic": int(p.magic), "actif": str(p.symbol),
                                 "pic": lat, "creux": lat, "dernier": lat,
                                 "ouvert": maintenant(),
                                 "x60": est_x60(p.magic),
                                 "setup": setup_de(p.magic)}
'''

A4 = '''                        print("[%s] X60_ENTREE  %d  M%d  %s  (%d autres en"
                              " position)" % (maintenant()[11:], t, p.magic,
                                              p.symbol, len(pos) - 1))
                else:
'''
N4 = '''                        print("[%s] X60_ENTREE  %d  M%d  %s  (%d autres en"
                              " position)" % (maintenant()[11:], t, p.magic,
                                              p.symbol, len(pos) - 1))
                    elif connus[t]["setup"] in SETUPS:
                        # LE MIROIR de X60_ENTREE, pour x10, x20, x30.
                        # Meme charge utile, plus le setup. On n ecrase
                        # pas X60_ENTREE et on ne la renomme pas : le
                        # rapport existant doit continuer de lire
                        # exactement les memes lignes qu avant.
                        ecrire({"quoi": "X_ENTREE", "ts": maintenant(),
                                "setup": connus[t]["setup"],
                                "ticket": t, "magic": int(p.magic),
                                "actif": str(p.symbol),
                                "sens": "BUY" if p.type == 0 else "SELL",
                                "volume": float(p.volume),
                                "plateau": plateau(pos, sauf=t)})
                        print("[%s] X%s_ENTREE  %d  M%d  %s  (%d autres en"
                              " position)"
                              % (maintenant()[11:], connus[t]["setup"], t,
                                 p.magic, p.symbol, len(pos) - 1))
                else:
'''

A5 = '''                        "x60": c["x60"], "final": round(c["dernier"], 2),
'''
N5 = '''                        "x60": c["x60"], "setup": c.get("setup"),
                        "final": round(c["dernier"], 2),
'''

A6 = '''                    print("[%s] X60_SORTIE  %d  M%d  MFE %+.2f  MAE %+.2f"
                          "  (%d tierces restent)"
                          % (maintenant()[11:], t, c["magic"], c["pic"],
                             c["creux"], len(pos)))
'''
N6 = '''                    print("[%s] X60_SORTIE  %d  M%d  MFE %+.2f  MAE %+.2f"
                          "  (%d tierces restent)"
                          % (maintenant()[11:], t, c["magic"], c["pic"],
                             c["creux"], len(pos)))
                elif c.get("setup") in SETUPS:
                    # Le miroir de X60_SORTIE. Le plateau est releve
                    # APRES la disparition du ticket, comme pour le x60
                    # -- meme convention, sinon les deux ne se comparent
                    # pas.
                    ecrire({"quoi": "X_SORTIE", "ts": maintenant(),
                            "setup": c.get("setup"),
                            "ticket": t, "magic": c["magic"],
                            "actif": c["actif"],
                            "mfe": round(c["pic"], 2),
                            "mae": round(c["creux"], 2),
                            "plateau": plateau(pos)})
                    print("[%s] X%s_SORTIE  %d  M%d  MFE %+.2f  MAE %+.2f"
                          "  (%d tierces restent)"
                          % (maintenant()[11:], c.get("setup"), t,
                             c["magic"], c["pic"], c["creux"], len(pos)))
'''

ANCRES = ((A1, N1, "la constante SETUP"),
          (A2, N2, "le dict de plateau()"),
          (A3, N3, "la creation de connus[t]"),
          (A4, N4, "la fin du bloc X60_ENTREE"),
          (A5, N5, "le dict CLOTURE"),
          (A6, N6, "la fin du bloc X60_SORTIE"))

# Ce qui doit rester mot pour mot : le rapport en depend.
INTOUCHABLES = ('def est_x60(', 'SETUP = "60"', '"quoi": "X60_ENTREE"',
                '"quoi": "X60_SORTIE"', '"quoi": "CLOTURE"',
                'def setup_de(', 'def plateau(')


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = io.open(a.fichier, encoding="utf-8", errors="replace").read()
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    neuf = src
    for anc, nouv, nom in ANCRES:
        n = neuf.count(anc)
        if n != 1:
            print("KO : %d occurrence(s) de %s, il en faut 1." % (n, nom))
            print("Rien n a ete ecrit.")
            return 1
        neuf = neuf.replace(anc, nouv, 1)
    print("Six ancres, chacune unique.")

    try:
        arbre = ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    for t in INTOUCHABLES:
        if src.count(t) != neuf.count(t):
            print("KO : %s n apparait plus le meme nombre de fois." % t)
            print("Rien n a ete ecrit.")
            return 1
    print("Intacts : est_x60, SETUP, setup_de, plateau, et les trois")
    print("evenements d origine X60_ENTREE, X60_SORTIE, CLOTURE.")

    # Posees ailleurs que dans boucle(), les deux nouvelles ecritures
    # compileraient sans jamais s executer -- et le fichier resterait
    # vide de x10/x20/x30 sans que rien ne le signale.
    ok = False
    for f in ast.walk(arbre):
        if isinstance(f, ast.FunctionDef) and f.name == "boucle":
            d = ast.dump(f)
            ok = "X_ENTREE" in d and "X_SORTIE" in d and "SETUPS" in d
            break
    if not ok:
        print("KO : X_ENTREE / X_SORTIE ne sont pas dans boucle(), ou")
        print("     SETUPS n y est pas lu. Elles compileraient sans")
        print("     jamais ecrire. Rien n a ete ecrit.")
        return 1
    print("Arbre verifie : les deux nouveaux evenements sont dans")
    print("boucle(), avec SETUPS a portee.")

    print()
    print("Ce que ca ajoute au fichier d evenements :")
    print("  X_ENTREE   entree d un x10 / x20 / x30, avec le plateau")
    print("  X_SORTIE   sa sortie, avec le plateau")
    print("  setup      sur chaque tierce du plateau et sur CLOTURE")
    print()
    print("A LA LECTURE : le setup 60 reste dans X60_*, les trois autres")
    print("dans X_*. Qui veut les quatre prend l union et traite X60_*")
    print("comme setup 60. C est le prix de ne pas casser le rapport qui")
    print("tourne, et il est ecrit plutot que devine.")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DE x60_onset. Les positions")
    print("deja ouvertes n auront pas d evenement d entree -- meme regle")
    print("que pour les x60, et meme raison de ne pas trainer.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique. Relancer x60_onset pour que ca prenne effet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
