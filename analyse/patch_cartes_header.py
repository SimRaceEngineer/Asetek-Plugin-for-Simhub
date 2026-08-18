# -*- coding: utf-8 -*-
r"""
patch_cartes_header.py -- la route /cartes reprend le VRAI header du
                          panneau, et affiche une carte au lieu d une
                          liste de fichiers.

  python patch_cartes_header.py --essai
  python patch_cartes_header.py

CE QU IL CORRIGE, ET POURQUOI CE N ETAIT PAS UNE ERREUR D EXECUTION

  patch_route_cartes.py (18/08, 07:29) recopiait la barre LIGNE PAR
  LIGNE depuis price_action.py. Trois consequences, toutes visibles a
  l ecran :

    1. Les onglets sortaient SANS leur conteneur `<div class="tabs">`,
       qui porte le display:flex. Chaque pastille devenait une bande
       pleine largeur.

    2. Le filtre `'class="tab"' in _l and "onclick=" in _l` retenait
       SA PROPRE LIGNE SOURCE, qui contient les deux motifs. Elle
       s affichait telle quelle en bas de la barre.

    3. Aucune route n etait resolue : tous les onglets renvoyaient a
       `/`, alors que price_action.py sert environ 150 adresses.

  Et le vrai defaut est en amont des trois. `onglets()` existe dans
  carte_html.py DEPUIS LE 14/08, ecrite au troisieme essai apres le
  reproche "mets juste le header identique aux autres panels". Sa
  docstring dit : "Une premiere version inventait sa propre barre.
  Ce n est pas comme les autres panneaux, c est un deuxieme style a
  maintenir." J en ai ecrit un second a cote, moins bon.

  mistakes.md, 14/08 : "Sur une interface qui existe, on recopie ; on
  ne concoit pas." La regle etait ecrite. Elle n a pas ete relue.

CE QUE FAIT CELUI-CI

  Il ne recopie plus des lignes : il prend la TRANCHE de source, de
  `<div class="hdr">` jusqu a la fermeture de `<div class="tabs">`,
  telle quelle, conteneurs compris. Le titre, la pastille d etat, le
  bouton d export et les douze rangees d onglets arrivent avec leur
  balisage d origine.

  Trois reecritures, chacune parce que la cible n existe pas hors du
  tableau de bord :

    showTab('x')      -> /x si cette route est servie, sinon la route
                         du libelle, sinon `/` ou l onglet existe.
                         L ARGUMENT D ABORD : onglets() n essaie que le
                         libelle, et "VIX (tout)" donne /vix_(tout),
                         qui n existe pas, quand son argument donne
                         /vixall, qui est servi. Aucun lien mort.
    copyRawExport()   -> une copie locale. navigator.clipboard est
                         absent en http:// sur un nom de machine :
                         zone de texte cachee + execCommand.
    <div id="meta">   -> le nom de la carte et sa date. C est le
                         chassis exige le 14/08 : "un en-tete qui dit
                         ce qu on regarde et de quand ca date".

  Et /cartes affiche DIRECTEMENT la carte la plus recente, avec les
  autres en selecteur d une ligne. Un onglet montre un contenu ; il ne
  demande pas un clic de plus.

Sauvegarde horodatee, refuse de s appliquer deux fois, compile avant
de remplacer. LECTEUR SEUL par ailleurs.
"""
import argparse
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "price_action.py"
MARQUE = "TRANCHE hdr..tabs"

DEBUT = '            if parsed.path == "/cartes" or parsed.path == "/carte":\n'
FIN = '            if parsed.path == "/profils":\n'

B_ROUTE = r'''            if parsed.path == "/cartes" or parsed.path == "/carte":
                import os as _o
                import re as _re
                import time as _t
                # TRANCHE hdr..tabs -- RECOPIEE, pas reconstruite.
                # Le 14/08 une barre inventee a coute trois tours ; le
                # 18/08 une barre recopiee ligne par ligne a perdu son
                # conteneur. On prend le bloc entier.
                _css, _bloc = "", ""
                try:
                    _src = open("price_action.py", "r", encoding="utf-8",
                                errors="ignore").read()
                    _i = _src.find("<style>")
                    _j = _src.find("</style>", _i) if _i >= 0 else -1
                    if _i >= 0 and _j > _i:
                        _css = _src[_i:_j + 8]
                    # LES ANCRES SONT ASSEMBLEES A L EXECUTION, jamais
                    # ecrites en toutes lettres. Ce bloc vit DANS
                    # price_action.py : une ancre litterale s y
                    # trouverait elle-meme, et la tranche partirait du
                    # code au lieu du HTML. C est le defaut exact que ce
                    # patch corrige -- le reintroduire ici serait la
                    # troisieme fois.
                    _q = chr(34)
                    _ah = "<div class=" + _q + "hdr" + _q + ">"
                    _at = "<div class=" + _q + "tabs" + _q + ">"
                    _a = _src.find(_ah)
                    _b = _src.find(_at, _a) if _a >= 0 else -1
                    if _a >= 0 and _b > _a:
                        # Fermeture de .tabs par comptage de profondeur,
                        # jamais par rfind : rfind ramasserait un
                        # </div> ecrit dans du code plus bas.
                        _k = _b + len(_at)
                        _prof = 1
                        while _prof > 0:
                            _o1 = _src.find("<div", _k)
                            _c1 = _src.find("</div>", _k)
                            if _c1 < 0:
                                break
                            if 0 <= _o1 < _c1:
                                _prof += 1
                                _k = _o1 + 4
                            else:
                                _prof -= 1
                                _k = _c1 + 6
                        if _prof == 0:
                            _bloc = _src[_a:_k]
                except Exception:
                    _css, _bloc = "", ""

                _d = "cartes"
                _f = ""
                if parsed.query:
                    for _kv in parsed.query.split("&"):
                        if _kv.startswith("f="):
                            _f = _kv[2:]
                if _f and ("/" in _f or chr(92) in _f or ".." in _f
                           or not _f.endswith(".html")):
                    _f = ""
                _n = []
                try:
                    _n = [x for x in _o.listdir(_d) if x.endswith(".html")]
                    _n.sort(key=lambda x: _o.path.getmtime(_d + "/" + x),
                            reverse=True)
                except Exception:
                    _n = []
                if not _f and _n:
                    _f = _n[0]

                # --- resolution des onglets ------------------------
                if _bloc:
                    _vraies = set(_re.findall(r'parsed[.]path == "(/[^"]*)"',
                                              _src))

                    def _route(_arg, _lib):
                        # DEUX pistes avant d abandonner. onglets()
                        # dans carte_html.py ne tente que le libelle :
                        # "VIX (tout)" donne /vix_(tout), qui n existe
                        # pas, alors que showTab('vixall') donne
                        # /vixall, qui est servi. On essaie l argument
                        # d abord, le libelle ensuite.
                        for _c in (_arg.strip().strip(chr(39) + chr(34)),
                                   _lib.strip().lower().replace(" ", "_")
                                   .replace("-", "_")):
                            if _c and ("/" + _c) in _vraies:
                                return "/" + _c
                        return "/"

                    _bloc = _re.sub(
                        r'<div class="tab([^"]*)"([^>]*)onclick="'
                        r'showTab\(([^)]*)\)"([^>]*)>([^<]*)</div>',
                        lambda m: ('<div class="tab' + m.group(1) + '"'
                                   + m.group(2) + 'onclick="location.href='
                                   + chr(39) + _route(m.group(3), m.group(5))
                                   + chr(39) + '"' + m.group(4) + '>'
                                   + m.group(5) + '</div>'),
                        _bloc)
                    # Le bouton d export du tableau de bord appelle une
                    # fonction qui n existe pas ici. Un bouton copier
                    # muet est pire que pas de bouton : c est par lui
                    # que le contenu part dans le REPL.
                    _bloc = _bloc.replace("copyRawExport()", "_copieCarte()")
                    _bloc = _bloc.replace(
                        '<div class="meta" id="meta">--</div>',
                        '<div class="meta" id="meta">' + (_f or "aucune carte")
                        + '</div>')

                _sel = ""
                if len(_n) > 1:
                    _parts = []
                    for _x in _n:
                        _mk = _t.strftime("%Y-%m-%d %H:%M", _t.localtime(
                            _o.path.getmtime(_d + "/" + _x)))
                        _parts.append(
                            '<a href="/cartes?f=' + _x + '" style="color:'
                            + ("#e6edf3" if _x == _f else "#58a6ff")
                            + ';margin-right:16px;text-decoration:none">'
                            + _x + ' <span style="color:#7d8590">' + _mk
                            + '</span></a>')
                    _sel = ('<div style="padding:6px 14px;font:12px system-ui'
                            '">' + "".join(_parts) + '</div>')

                _js = ('<textarea id="_zc" style="position:absolute;left:'
                       '-9999px;top:0"></textarea><script>function '
                       '_copieCarte(){var z=document.getElementById("_zc");'
                       'z.value=document.body.innerText;z.select();'
                       'document.execCommand("copy");}</script>')

                _tete = _css + _bloc + _sel + _js
                body = None
                if _f:
                    try:
                        _h = open(_d + "/" + _f, "rb")
                        _raw = _h.read()
                        _h.close()
                        body = _tete.encode("utf-8") + _raw
                    except Exception:
                        body = None
                if body is None:
                    body = (_tete + '<div style="padding:14px 18px;font:'
                            '14px system-ui;color:#8b949e">Aucune carte '
                            'lisible dans le dossier cartes. Pour en '
                            'produire une : <code style="color:#c9d1d9">'
                            'python bougies_reperes.py --html 2026-08-14'
                            '</code></div>').encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

'''


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

    if MARQUE in src:
        print("Deja applique -- rien a faire.")
        return 0

    i = src.find(DEBUT)
    if i < 0:
        print()
        print("KO : la route /cartes de patch_route_cartes.py est absente.")
        print("Ce patch REMPLACE ce bloc ; il ne sait pas s inserer seul.")
        print("Applique d abord patch_route_cartes.py.")
        return 1
    j = src.find(FIN, i)
    if j < 0:
        print()
        print("KO : la route /profils qui borne le bloc est introuvable.")
        print("RIEN n a ete ecrit.")
        return 1
    print("  bloc a remplacer : %d caracteres." % (j - i))

    # Le header doit exister sous la forme attendue, sinon la page
    # servira une navigation vide -- le defaut qu on corrige.
    for motif, quoi in (('<div class="hdr">', "le bloc titre"),
                        ('<div class="tabs">', "le conteneur des onglets")):
        n = src.count(motif)
        print("  %-22s %d occurrence(s)" % (quoi, n))
        if n < 1:
            print()
            print("KO : %s est absent de %s. RIEN n a ete ecrit."
                  % (quoi, a.fichier))
            return 1

    out = src[:i] + B_ROUTE + src[j:]
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
