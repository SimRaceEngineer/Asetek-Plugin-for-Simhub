# -*- coding: utf-8 -*-
r"""
patch_cartes_pine.py -- un bouton "copier" par fichier .pine sur /cartes

  python patch_cartes_pine.py --essai
  python patch_cartes_pine.py

POURQUOI

  TradingView ne lit aucun fichier local et n expose aucune API pour
  mettre a jour la source d un indicateur. Le seul canal officiel,
  Pine Seeds, veut un depot GitHub public agree et des donnees
  JOURNALIERES de fin de seance : nos instants sont a la minute.

  Le collage est donc incompressible. Ce qui l est, c est le chemin
  jusqu au presse-papier : ouvrir l explorateur, trouver cartes\,
  ouvrir le .pine, tout selectionner. Un bouton le remplace.

CE QUE CA AJOUTE

  Sous la barre de navigation de /cartes, une ligne par fichier .pine
  du dossier cartes\ : un bouton "copier <nom>", sa taille et sa date.
  Un clic met le fichier entier dans le presse-papier ; il ne reste
  qu a faire Ctrl+A puis Ctrl+V dans le Pine Editor.

DEUX PIEGES, TOUS DEUX RENCONTRES AVANT

  1. `navigator.clipboard` EXIGE un contexte sur. La page est servie en
     http:// sur un nom de machine (vmi654074:8095) : l API y est
     ABSENTE, et un bouton ecrit naivement ne fait rien du tout, sans
     la moindre erreur visible. On passe donc par execCommand("copy"),
     qui marche dans les deux cas -- c est deja ce que fait le bouton
     Copy All Raw Data de la carte.

  2. Le contenu du Pine vit dans un <script type="text/plain">, PAS
     dans un <textarea>. `document.body.innerText` embarque le texte
     d un textarea : le bouton "Copy All Raw Data" de la carte serait
     reparti avec huit kilo-octets de Pine colles dedans.

     Dans un bloc script, aucun echappement HTML n est possible -- le
     texte n y est pas desechappe. Seul `</` doit etre neutralise,
     parce que l analyseur ferme au premier `</script`. Le JS le
     restitue avant de copier.

BANC, sur un .pine contenant `<`, `>`, `&`, `</script>` et `</style>`

     1. les fausses fermetures ne ferment rien
     2. les deux `</` sont neutralises
     3. la restitution rend le Pine OCTET POUR OCTET
     4. aucun textarea ne porte le Pine
     5. bouton, taille, date, et ordre CSS / BLOC / SEL / PINE / JS
     6. le JS restitue exactement ce que Python a echappe
     7. dossier sans .pine : aucun bloc ajoute

INDEPENDANT de patch_cartes_css.py : les deux touchent des regions
distinctes et s appliquent dans n importe quel ordre.

Sauvegarde horodatee, refuse de s appliquer deux fois, compile avant de
remplacer. LECTEUR SEUL par ailleurs.
"""
import argparse
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "price_action.py"
MARQUE = "LES .pine DU DOSSIER, AVEC UN BOUTON COPIER"

ANCIEN = '                _js = (\'<textarea id="_zc" style="position:absolute;left:\'\n                       \'-9999px;top:0"></textarea><script>function \'\n                       \'_copieCarte(){var z=document.getElementById("_zc");\'\n                       \'z.value=document.body.innerText;z.select();\'\n                       \'document.execCommand("copy");}</script>\')\n\n                _tete = _css + _bloc + _sel + _js\n'

NOUVEAU = '                # --- LES .pine DU DOSSIER, AVEC UN BOUTON COPIER -------------\n                # Le contenu vit dans un <script type="text/plain"> et NON dans\n                # un <textarea> : document.body.innerText embarque le texte d un\n                # textarea, et le bouton "Copy All Raw Data" de la carte\n                # repartirait avec huit kilo-octets de Pine colles dedans.\n                #\n                # Seul `</` est neutralise -- l analyseur HTML ferme le script au\n                # premier `</script`. Le JS le restitue avant de copier.\n                #\n                # execCommand et non navigator.clipboard : la page est servie en\n                # http:// sur un nom de machine, donc hors contexte sur, et l API\n                # moderne y est ABSENTE -- un bouton ecrit naivement ne ferait\n                # rien du tout, sans erreur visible.\n                _pine = ""\n                try:\n                    _np = sorted(_x2 for _x2 in _o.listdir(_d)\n                                 if _x2.endswith(".pine"))\n                except Exception:\n                    _np = []\n                _pp = []\n                for _i2 in range(len(_np)):\n                    _x2 = _np[_i2]\n                    try:\n                        _fh = open(_d + "/" + _x2, "r", encoding="utf-8",\n                                   errors="replace")\n                        _s2 = _fh.read()\n                        _fh.close()\n                    except Exception:\n                        continue\n                    _mk2 = _t.strftime("%d/%m %H:%M", _t.localtime(\n                        _o.path.getmtime(_d + "/" + _x2)))\n                    _id2 = "_zp" + str(_i2)\n                    _pp.append(\n                        \'<script type="text/plain" id="\' + _id2 + \'">\'\n                        + _s2.replace("</", "<" + chr(92) + "/")\n                        + "</scr" + "ipt>"\n                        + \'<button onclick="_copiePine(\' + chr(39) + _id2\n                        + chr(39) + \',this)" style="background:#1f6feb;\'\n                        \'color:#fff;border:none;padding:5px 12px;\'\n                        \'border-radius:6px;cursor:pointer;font:inherit;\'\n                        \'font-size:11px;font-weight:700;margin-right:8px">\'\n                        \'copier \' + _x2 + "</button>"\n                        + \'<span style="color:#7d8590;font:12px system-ui;\'\n                        \'margin-right:20px">\' + str(len(_s2)) + " o &middot; "\n                        + _mk2 + "</span>")\n                if _pp:\n                    _pine = (\'<div style="padding:8px 14px;border-top:\'\n                             \'1px solid #21262d">\' + "".join(_pp) + "</div>")\n\n                _js = (\'<textarea id="_zc" style="position:absolute;left:\'\n                       \'-9999px;top:0"></textarea><scr\' + \'ipt>function \'\n                       \'_copieCarte(){var z=document.getElementById("_zc");\'\n                       \'z.value=document.body.innerText;z.select();\'\n                       \'document.execCommand("copy");}\'\n                       \'function _copiePine(i,b){\'\n                       \'var e=document.getElementById(i);\'\n                       \'var z=document.getElementById("_zc");\'\n                       \'z.value=e.textContent.split("<\' + chr(92) + chr(92) + \'/")\'\n                       \'.join("</");z.focus();z.select();\'\n                       \'try{document.execCommand("copy");}catch(x){}\'\n                       \'var o=b.textContent;b.textContent="copie !";\'\n                       \'setTimeout(function(){b.textContent=o;},1200);}\'\n                       \'</scr\' + \'ipt>\')\n\n                _tete = _css + _bloc + _sel + _pine + _js\n'


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
    print("%s : %d lignes." % (a.fichier, src.count("\n") + 1))

    if os.path.isdir("cartes"):
        n = len([x for x in os.listdir("cartes") if x.endswith(".pine")])
        print("  fichiers .pine dans cartes\\ : %d" % n)
        if n == 0:
            print("  (aucun pour l instant -- le bloc n affichera rien")
            print("   tant que pine_reperes.py n en aura pas ecrit un)")

    if MARQUE in src:
        print("Deja applique -- rien a faire.")
        return 0

    n = src.count(ANCIEN)
    print("  ancre : %d occurrence(s), attendu 1" % n)
    if n != 1:
        print()
        print("KO : ancre absente ou ambigue. RIEN n a ete ecrit.")
        print("Applique d abord patch_cartes_header.py.")
        return 1

    out = src.replace(ANCIEN, NOUVEAU, 1)
    try:
        compile(out, a.fichier, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (ligne %s : %s)."
              % (e.lineno, e.msg))
        print("Rien n a ete ecrit. L original est intact.")
        return 1
    print("  le resultat compile.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauv = "%s.bak-%s" % (a.fichier,
                          datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauv)
    io.open(a.fichier, "w", encoding="utf-8", newline="").write(out)
    print()
    print("Sauvegarde : %s" % sauv)
    print("%d -> %d lignes." % (len(src.splitlines()),
                                len(out.splitlines())))
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DU PANNEAU -- il se termine")
    print("seul toutes les ~40 min et le gardien le relance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
