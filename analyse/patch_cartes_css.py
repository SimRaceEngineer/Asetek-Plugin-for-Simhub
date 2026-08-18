# -*- coding: utf-8 -*-
r"""
patch_cartes_css.py -- la feuille de style servie avec /cartes est celle
                       qui PRECEDE le header, pas la premiere du fichier.

  python patch_cartes_css.py --essai
  python patch_cartes_css.py

LE DEFAUT

  patch_cartes_header.py a bien pris : le nom de la carte apparait dans
  la pastille #meta, le bouton Copy All Raw Data est la, la ligne de
  code parasite a disparu, les onglets sont resolus.

  Mais AUCUNE classe n est appliquee. Le titre, les pastilles et le
  conteneur sortent en style navigateur par defaut -- d ou des onglets
  empiles au lieu du bandeau. Seules les couleurs tiennent, parce
  qu elles sont en style="" DANS chaque div.

LA CAUSE

  Le bloc lisait la feuille ainsi :

      _i = _src.find("<style>")

  c est-a-dire LE PREMIER bloc <style> de price_action.py, 23 797
  lignes et plusieurs pages servies. Rien ne dit que c est celui du
  tableau de bord.

LA CORRECTION, et c est le meme principe que la tranche

  On prend ce qui est ADJACENT a ce qu on recopie : le </style> le plus
  proche AVANT le header, et le <style> qui l ouvre. La feuille qui
  style ce header est celle qui le precede.

  `<style` sans le chevron fermant, pour tolerer un attribut.

Ce patch imprime au passage le nombre de blocs <style> du fichier :
c est le fait qui manquait pour diagnostiquer sans deviner.

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
MARQUE = "LA FEUILLE DE STYLE EST CELLE QUI PRECEDE LE"

ANCIEN = '                    _i = _src.find("<style>")\n                    _j = _src.find("</style>", _i) if _i >= 0 else -1\n                    if _i >= 0 and _j > _i:\n                        _css = _src[_i:_j + 8]\n                    # LES ANCRES SONT ASSEMBLEES A L EXECUTION, jamais\n                    # ecrites en toutes lettres. Ce bloc vit DANS\n                    # price_action.py : une ancre litterale s y\n                    # trouverait elle-meme, et la tranche partirait du\n                    # code au lieu du HTML. C est le defaut exact que ce\n                    # patch corrige -- le reintroduire ici serait la\n                    # troisieme fois.\n                    _q = chr(34)\n                    _ah = "<div class=" + _q + "hdr" + _q + ">"\n                    _at = "<div class=" + _q + "tabs" + _q + ">"\n                    _a = _src.find(_ah)\n                    _b = _src.find(_at, _a) if _a >= 0 else -1\n'

NOUVEAU = '                    _q = chr(34)\n                    _ah = "<div class=" + _q + "hdr" + _q + ">"\n                    _at = "<div class=" + _q + "tabs" + _q + ">"\n                    _a = _src.find(_ah)\n                    _b = _src.find(_at, _a) if _a >= 0 else -1\n                    # LA FEUILLE DE STYLE EST CELLE QUI PRECEDE LE\n                    # HEADER, pas la premiere du fichier. price_action.py\n                    # porte plusieurs blocs <style> ; prendre le premier\n                    # ramenait celui d une autre page, et le header\n                    # sortait sans une seule classe appliquee -- titre,\n                    # pastilles et conteneur en style navigateur par\n                    # defaut, d ou les onglets empiles.\n                    # Meme principe que la tranche : on prend ce qui est\n                    # ADJACENT a ce qu on recopie, pas ce qui vient en\n                    # premier.\n                    if _a > 0:\n                        _fs = _src.rfind("</style>", 0, _a)\n                        _ds = _src.rfind("<style", 0, _fs) if _fs > 0 else -1\n                        if _ds >= 0 and _fs > _ds:\n                            _css = _src[_ds:_fs + 8]\n'


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

    n_style = src.count("<style")
    print("  blocs <style> dans le fichier : %d" % n_style)
    if n_style > 1:
        print("  -> c est bien la cause : `find(\"<style>\")` en ramenait")
        print("     un autre que celui du tableau de bord.")

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
