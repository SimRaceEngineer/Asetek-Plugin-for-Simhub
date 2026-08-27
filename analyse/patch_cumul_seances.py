#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""patch_cumul_seances.py -- le panneau cumule N seances au lieu d une

  python patch_cumul_seances.py                    simulation
  python patch_cumul_seances.py --appliquer
  python patch_cumul_seances.py --jours 10 --appliquer

POURQUOI
    "Tous les jours ne se ressemblent pas." Un panneau borne au jour en
    cours est vide a 8 h du matin et ne pese rien a 18 h : quatre trades
    par branche, des bornes de Wilson a 6 %. Le cumul est la seule
    lecture qui puisse trancher quoi que ce soit.

OU CA SE JOUE
    Pas dans le panneau. cartes_live.py ne borne rien : il lit
    l instantane docs/cartes_live/compte.json, et c est l ENVOYEUR du
    pont qui le fabrique. Dans pont_miroirs.py, affaires_du_jour()
    interroge large -- un jour de part et d autre -- puis la ligne 620
    jette tout ce qui precede minuit serveur. C est ce couperet, et lui
    seul, qui fait du panneau un panneau du jour.

    On recule donc le couperet de N seances, et on elargit la requete
    d autant. Le reste de la fonction ne bouge pas : le regroupement par
    POSITION, les commissions et les swaps restent identiques.

ET LE TEXTE
    Le panneau ecrit "les affaires closes DU JOUR". Si on cumule sans
    corriger la phrase, il ment -- et un panneau qui affiche une chose
    fausse avec l air d etre juste est precisement ce qui a coute une
    heure le 26/08. Les trois phrases concernees sont donc reecrites
    dans cartes_live.py.

CE QU IL NE FAIT PAS
    Il ne touche a aucune autre ligne des deux fichiers. Lecture et
    ecriture en latin-1, indentation et fin de ligne d origine
    conservees, sauvegarde horodatee avant toute ecriture, relecture et
    controle de l ecart de taille apres.

IDEMPOTENT.
"""
import argparse
import io
import os
import shutil
import sys
import time

PONT = "pont_miroirs.py"
CARTE = "cartes_live.py"
MARQUE = "JOURS_CUMUL"


def charge(chemin):
    with io.open(chemin, encoding="latin-1", newline="") as f:
        return f.read()


def decoupe(ligne):
    """(indentation, corps, fin de ligne) d une ligne brute."""
    fin = "\r" if ligne.endswith("\r") else ""
    corps = ligne[:-1] if fin else ligne
    creux = corps[:len(corps) - len(corps.lstrip())]
    return creux, corps, fin


def trouve(lignes, strip_cible):
    """L index de LA ligne dont le contenu strippe vaut la cible, ou -1.

    On exige l unicite : deux lignes identiques rendent le patch
    ambigu, et un patch ambigu ne doit pas s appliquer.
    """
    vus = [i for i, l in enumerate(lignes)
           if l.rstrip("\r").strip() == strip_cible]
    return vus[0] if len(vus) == 1 else (-2 if vus else -1)


def dis_echec(nom, strip_cible, code):
    if code == -1:
        print("  ABANDON : introuvable dans %s -- %s" % (nom, strip_cible[:70]))
    else:
        print("  ABANDON : plusieurs lignes identiques dans %s -- %s"
              % (nom, strip_cible[:70]))


def applique(chemin, edits, jours, verbe):
    """edits : liste de (mode, cible_strip, contenu). mode = R ou I."""
    texte = charge(chemin)
    lignes = texte.split("\n")
    print("%s : %d lignes, %d octets"
          % (chemin, len(lignes), len(texte.encode("latin-1"))))
    if MARQUE in texte and chemin == PONT:
        print("  DEJA PATCHE : %s est present." % MARQUE)
        return texte, texte, True

    for mode, cible, contenu in edits:
        i = trouve(lignes, cible)
        if i < 0:
            # Une ancre absente peut vouloir dire DEJA FAIT, et non ratee.
            # Crier a l ancre manquante sur un fichier deja correct est une
            # fausse alerte -- pire qu un echec net, parce qu elle pousse a
            # restaurer une sauvegarde inutilement. On verifie donc d abord
            # que le resultat attendu n est pas deja la.
            deja = contenu.format(J=jours).strip().split("\n")[-1].strip()
            if deja and any(l.rstrip("\r").strip() == deja for l in lignes):
                print("  deja fait : %s" % deja[:70])
                continue
            dis_echec(chemin, cible, i)
            return texte, None, False
        creux, corps, fin = decoupe(lignes[i])
        if mode == "R":
            neuf = creux + contenu.format(J=jours) + fin
            print("  ligne %d" % (i + 1))
            print("    avant : %s" % corps.strip())
            print("    apres : %s" % neuf.strip())
            lignes[i] = neuf
        else:
            bloc = [creux + x.format(J=jours) + fin
                    for x in contenu.split("\n")]
            print("  ligne %d, insertion de %d ligne(s) apres :"
                  % (i + 1, len(bloc)))
            print("    %s" % corps.strip())
            for b in bloc:
                print("      + %s" % b.strip())
            lignes[i + 1:i + 1] = bloc
    return texte, "\n".join(lignes), True


def ecrit(chemin, avant, apres):
    sauve = "%s.avant_cumul_%s" % (chemin, time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(chemin, sauve)
    with io.open(chemin, "w", encoding="latin-1", newline="") as f:
        f.write(apres)
    relu = charge(chemin)
    ok = relu == apres
    print("  sauvegarde   : %s" % sauve)
    print("  ecart taille : %+d octets"
          % (len(relu.encode("latin-1")) - len(avant.encode("latin-1"))))
    print("  VERIFICATION : %s" % ("ok" if ok else "ECHEC -- restaurer"))
    return ok


# ------------------------------------------------------------------ edits

EDITS_PONT = [
    # 1. la constante, juste sous le chemin de l instantane
    ("I", 'COMPTE_JSON = os.path.join(DOSSIER_LIVE, "compte.json")',
     '\n'
     '# 27/08 : le panneau etait borne au jour en cours, ce qui le rend vide\n'
     '# le matin et sans poids le soir -- quatre trades par branche, des\n'
     '# bornes de Wilson a 6 %. Le couperet etait la ligne "< minuit" de\n'
     '# affaires_du_jour(). On le recule de N seances et on elargit la\n'
     '# requete d autant. 1 = le comportement d avant.\n'
     'JOURS_CUMUL = {J}'),
    # 2. la borne basse, calculee une fois
    ("I", 'minuit, maintenant, _fuseau = minuit_serveur()',
     'depuis = minuit - 86400 * (JOURS_CUMUL - 1)'),
    # 3. la requete, elargie d autant
    ("R", 'datetime.utcfromtimestamp(minuit - 86400),',
     'datetime.utcfromtimestamp(depuis - 86400),'),
    # 4. le couperet lui-meme
    ("R", 'if int(getattr(d, "time", 0) or 0) < minuit:',
     'if int(getattr(d, "time", 0) or 0) < depuis:'),
    # 5. le paquet dit sur combien de seances il porte
    ("I", '"minuit_serveur": _minuit, "fuseau": _fuseau,',
     '"jours_cumul": JOURS_CUMUL,'),
]

EDITS_CARTE = [
    ("R", 'a("  du jour sur le compte %s, une affaire par position, commissions"',
     'a("  cumulees sur le compte %s, une affaire par position, commissions"'),
    ("R", 'a("  Un jour d execution ne juge rien. Ce panneau ne sert qu a voir")',
     'a("  Quelques seances ne jugent rien. Ce panneau ne sert qu a voir")'),
    ("R", 'a("  fait sur un compte, un jour, avec quelques trades.")',
     'a("  fait sur un compte, sur la periode cumulee de l instantane.")'),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jours", type=int, default=5)
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    if a.jours < 1:
        print("ABANDON : --jours doit valoir au moins 1.")
        return 2
    for f in (PONT, CARTE):
        if not os.path.exists(f):
            print("ABANDON : %s introuvable dans %s" % (f, os.getcwd()))
            return 2

    print("cumul demande : %d seance(s)" % a.jours)
    print("")
    av1, ap1, ok1 = applique(PONT, EDITS_PONT, a.jours, "pont")
    print("")
    av2, ap2, ok2 = applique(CARTE, EDITS_CARTE, a.jours, "carte")
    if not (ok1 and ok2):
        print("")
        print("RIEN N A ETE ECRIT -- une ancre manque, le fichier deploye")
        print("differe de celui que j ai lu. Envoie-moi la ligne en cause.")
        return 2

    print("")
    if not a.appliquer:
        print("SIMULATION -- rien n a ete ecrit.")
        print("Relancer avec --appliquer pour ecrire.")
        return 0

    bon = True
    if ap1 is not None and ap1 != av1:
        print("ecriture de %s" % PONT)
        bon = ecrit(PONT, av1, ap1) and bon
    if ap2 is not None and ap2 != av2:
        print("ecriture de %s" % CARTE)
        bon = ecrit(CARTE, av2, ap2) and bon
    print("")
    print("Le pont doit etre relance pour que ca prenne effet :")
    print("  un processus python ne relit pas son fichier apres son demarrage.")
    return 0 if bon else 2


if __name__ == "__main__":
    sys.exit(main())
