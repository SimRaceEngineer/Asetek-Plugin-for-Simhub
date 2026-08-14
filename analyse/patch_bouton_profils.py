# -*- coding: utf-8 -*-
r"""
patch_bouton_profils.py -- le bouton PROFILS dans la barre du 8095

  python patch_bouton_profils.py --essai
  python patch_bouton_profils.py
  python patch_bouton_profils.py --retire        (marche arriere)

POURQUOI CE PATCH EXISTE

    La route /profils a ete ajoutee sans bouton. Le panneau etait
    servi, et introuvable. **Un panneau = une route + un bouton** ;
    l un sans l autre ne vaut rien. C est ecrit dans mistakes.md et
    dans NOTES_panneaux.md, ce fichier-ci repare l oubli.

LE MODELE COPIE, ET POURQUOI CELUI-LA

    Sur 178 boutons de la barre, 177 font `showTab('id')` -- le
    contenu est deja dans la page -- et UN SEUL ouvre une route :

        <div class="tab" onclick="window.open('/rails_cycle','_blank')"
             style="color:#58a6ff;font-weight:bold;">RAILS CYCLE</div>

    C est celui-la le modele, et le choix n est pas cosmetique : le
    tableau de bord se recharge tout seul toutes les cinq secondes
    (`setTimeout(() => location.reload(), 5000)`). Une page a menus
    deroulants placee en onglet interne serait balayee a chaque
    rechargement, et ses 383 425 octets s ajouteraient au poids du
    tableau de bord a chaque fois.

    Couleur #58a6ff : celle du seul precedent. La barre compte une
    soixantaine de teintes distinctes, donc il n y a AUCUN code
    couleur a respecter -- raison de plus pour ne pas en inventer un.

L INDENTATION EST RELUE, PAS SUPPOSEE

    Je n ai vu la ligne d ancrage que dans une capture d ecran. Compter
    des espaces sur une image est exactement le genre de certitude qui
    casse un fichier de 23 612 lignes. Le patch capture donc
    l indentation de la ligne d ancrage par groupe de regex et
    l applique a la sienne : quelle qu elle soit, elle sera la meme.

    Meme raison pour la ligne entiere : l ancre est une EXPRESSION
    REGULIERE ancree sur `window.open('/rails_cycle','_blank')`, pas
    une chaine litterale recopiee a la main.

CE QUI EST VERIFIE AVANT D ECRIRE

    - l ancre existe et est UNIQUE ;
    - le resultat passe `ast.parse` -- la ligne est inseree DANS une
      chaine Python ; une guillemet de travers casserait le fichier ;
    - le nombre de `class="tab"` augmente d exactement 1 ;
    - le bouton RAILS CYCLE est toujours la, une seule fois ;
    - le fichier gagne exactement une ligne.

REJOUABLE dans les deux sens (--retire). Sauvegarde horodatee,
suffixee en cas de collision.

Ne prend effet qu au prochain demarrage de price_action.py -- JAMAIS a
la main sans PA_ROLE=panel.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "price_action.py"
ROUTE = "/profils"
LIBELLE = "PROFILS"
COULEUR = "#58a6ff"

# L ancre : le seul bouton de route de la barre. On capture son
# indentation (groupe 1) pour la rendre a l identique.
R_ANCRE = re.compile(
    r"^([ \t]*)<div class=\"tab\" onclick=\"window\.open\("
    r"'/rails_cycle','_blank'\)\"[^\n]*</div>[ \t]*$", re.M)

# Le bouton pose. Sert aussi d ancre a la marche arriere : on le
# reconnait par la route, pas par le libelle ni par la couleur.
R_MIEN = re.compile(
    r"\n[ \t]*<div class=\"tab\" onclick=\"window\.open\("
    r"'" + re.escape(ROUTE) + r"','_blank'\)\"[^\n]*</div>[ \t]*(?=\n)")


def bouton(indent):
    return ('%s<div class="tab" onclick="window.open(\'%s\',\'_blank\')"'
            ' style="color:%s;font-weight:bold;">%s</div>'
            % (indent, ROUTE, COULEUR, LIBELLE))


def lire(c):
    return io.open(c, encoding="utf-8", errors="replace").read()


def sauver(c, t):
    base = "%s.bak-%s" % (c, datetime.now().strftime("%Y%m%d-%H%M%S"))
    s, k = base, 1
    while os.path.exists(s):
        s = "%s-%d" % (base, k)
        k += 1
    shutil.copy2(c, s)
    io.open(c, "w", encoding="utf-8").write(t)
    print("Sauvegarde : %s" % s)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    p.add_argument("--retire", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1
    src = lire(a.fichier)
    n0 = src.count("\n") + 1
    onglets0 = src.count('class="tab"')
    print("%s : %d lignes, %d boutons" % (a.fichier, n0, onglets0))

    try:
        ast.parse(src)
    except SyntaxError as e:
        print("KO : %s ne compile pas AVANT modification (ligne %s)."
              % (a.fichier, e.lineno))
        print("     Je ne touche pas a un fichier dans cet etat.")
        return 1

    deja = R_MIEN.search(src)

    if a.retire:
        if not deja:
            print("Le bouton %s n est pas la -- rien a retirer." % LIBELLE)
            return 0
        if len(R_MIEN.findall(src)) != 1:
            print("KO : %d boutons %s, il en faut 1."
                  % (len(R_MIEN.findall(src)), LIBELLE))
            return 1
        neuf = R_MIEN.sub("", src, count=1)
        attendu_lignes, attendu_onglets = -1, -1
    else:
        if deja:
            print("Le bouton %s est deja la -- rien a faire." % LIBELLE)
            print("Pour le retirer : --retire")
            return 0
        m = R_ANCRE.findall(src)
        if len(m) != 1:
            print("KO : %d occurrence(s) du bouton RAILS CYCLE, il en"
                  " faut 1." % len(m))
            print("     C est lui qui sert de modele et d ancre.")
            print("Rien n a ete ecrit.")
            return 1
        indent = m[0]
        print("  indentation relue sur l ancre : %d caractere(s)"
              % len(indent))
        neuf = R_ANCRE.sub(
            lambda x: x.group(0) + "\n" + bouton(x.group(1)), src, count=1)
        attendu_lignes, attendu_onglets = 1, 1

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("     La ligne s insere DANS une chaine Python : une")
        print("     guillemet de travers casse tout le fichier.")
        print("Rien n a ete ecrit.")
        return 1

    n1 = neuf.count("\n") + 1
    onglets1 = neuf.count('class="tab"')
    if n1 - n0 != attendu_lignes:
        print("KO : %+d lignes, attendu %+d." % (n1 - n0, attendu_lignes))
        print("Rien n a ete ecrit.")
        return 1
    if onglets1 - onglets0 != attendu_onglets:
        print("KO : %+d boutons, attendu %+d."
              % (onglets1 - onglets0, attendu_onglets))
        print("Rien n a ete ecrit.")
        return 1
    if len(R_ANCRE.findall(neuf)) != 1:
        print("KO : le bouton RAILS CYCLE n est plus unique apres coup.")
        print("Rien n a ete ecrit.")
        return 1

    print()
    print("  %s le bouton %s -> %s (%d boutons)"
          % ("retire" if a.retire else "ajoute", LIBELLE, ROUTE, onglets1))
    if not a.retire:
        print("  juste apres RAILS CYCLE, meme modele, meme couleur %s"
              % COULEUR)
        print("  window.open et non showTab : le tableau de bord se")
        print("  recharge toutes les 5 s et effacerait les menus.")
        print("Marche arriere : --retire")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DE price_action.py.")
    print("NE JAMAIS le lancer a la main sans PA_ROLE=panel.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauver(a.fichier, neuf)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
