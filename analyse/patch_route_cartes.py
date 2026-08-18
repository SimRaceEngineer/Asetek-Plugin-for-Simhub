# -*- coding: utf-8 -*-
r"""
patch_route_cartes.py -- les cartes HTML servies par le 8095, avec la
                         barre du tableau de bord, RECOPIEE

  python patch_route_cartes.py --essai
  python patch_route_cartes.py

CE QU IL AJOUTE

    /cartes          l INDEX : tout fichier .html depose dans cartes\
                     y apparait, du plus recent au plus ancien.
    /carte?f=nom     une carte precise.
    un bouton        CARTES dans la barre, sur le modele du seul
                     bouton de route existant.

LA BARRE EST LUE, JAMAIS REECRITE -- C EST LA LECON DU 14/08

    Le 14/08 a 00:05 j ai livre une navigation INVENTEE : mes couleurs,
    mes tailles, mon ordre alphabetique, au lieu de celle du tableau de
    bord qui a ses libelles et ses couleurs depuis des mois. Le reproche
    a ete net : "mets juste le header identique aux autres panels, c est
    rien, ca prend 2 secondes, ca fait 20 min qu on est dessus". Et
    c etait exact : ca prenait deux secondes A CONDITION DE RECOPIER
    AU LIEU DE CONCEVOIR.

    Donc ici, a chaque requete, la route relit `price_action.py` et en
    extrait DEUX choses telles quelles :

      - le premier bloc <style>...</style>, qui porte la classe `.tab`
        et tout le reste de l apparence ;
      - toutes les lignes <div class="tab" ... onclick=...>.

    Rien n est reecrit. Une route ajoutee demain dans le tableau de bord
    apparaitra ici sans qu on y touche.

    SEULE TRANSFORMATION : les `onclick="showTab('x')"` deviennent
    `onclick="location.href='/'"`. Un onglet interne designe un bloc
    cache DE LA PAGE D ACCUEIL ; sur une autre page il n existe pas, et
    un bouton qui ne fait rien est pire qu un bouton qui ramene au
    tableau de bord. Les `window.open('/route')` sont laisses intacts.

POURQUOI UN INDEX ET PAS UNE ROUTE PAR CARTE

    `bougies_reperes.py --html <date>` produit un fichier par journee.
    Une route par fichier voudrait dire un patch par journee sur le
    processus qui sert le 8095 -- toucher le panneau vivant chaque fois
    qu on regarde une date.

    L index relit le dossier a CHAQUE requete : deposer un fichier
    suffit a le rendre visible. Exactement ce qui avait ete fait le
    12/08 pour les documents du REPL.

CE QUI EST RESPECTE, PARCE QUE NOTES_panneaux.md L ECRIT

    - cascade `if parsed.path == "..."` dans `_do_GET_impl`,
      INDENTATION A 12 ESPACES, chaque branche finit par son `return` ;
    - chemins en barres OBLIQUES, jamais inverses ;
    - si le fichier manque, on repond 200 avec une page qui DIT quoi
      lancer. Jamais de trace de pile, jamais de 500 muet : le panneau
      ne tombe pas parce qu une carte n a pas ete generee ;
    - le bouton est copie sur le modele existant, couleur `#58a6ff`,
      parce que c est une route et non un onglet.

LES IMPORTS SONT LOCAUX -- CORRECTION DU 14/08 A 21:18

    Le code genere importe `os` et `time` LUI-MEME. Ce jour-la un patch
    a fait tomber la page en ecrivant `_os.environ` apres avoir
    "verifie" que `os` etait importe : le controle utilisait `ast.walk`,
    qui descend dans les fonctions, et avait pris un import local pour
    un import de module.

LE CHEMIN EST FILTRE

    `?f=` n accepte qu un nom de fichier : ni `/`, ni `\`, ni `..`, et
    il doit finir par `.html`. Une route qui sert un fichier nomme par
    le client sert n importe quel fichier si on ne l en empeche pas.

QUAND CA PREND EFFET

    Au prochain demarrage de `price_action.py`. Il se termine SEUL
    toutes les ~40 min (PA_RESTART_SEC) et le gardien le relance.
    Lancer le script a la main est sans danger -- `__main__` pose
    `PA_ROLE=panel` par `setdefault`, verifie le 18/08 -- mais inutile :
    deux processus se disputeraient le port 8095 et la garde
    anti-multi-bind en tuerait un.

Sauvegarde horodatee, refuse de s appliquer deux fois, compile avant
de remplacer.
"""
import argparse
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "price_action.py"
MARQUE = '"/cartes"'

A_ROUTE = '''            if parsed.path == "/profils":
'''
A_BOUTON = ('''<div class="tab" onclick="window.open('/profils','_blank')"'''
            ''' style="color:#58a6ff;font-weight:bold;">PROFILS</div>''')

B_ROUTE = '''            if parsed.path == "/cartes" or parsed.path == "/carte":
                import os as _o
                import time as _t
                # LA BARRE ET LE STYLE SONT LUS DANS CE FICHIER, jamais
                # reecrits : le 14/08 une navigation inventee a coute
                # vingt minutes pour un resultat qui se voyait au premier
                # coup d oeil. Une route ajoutee demain apparaitra ici
                # sans qu on y touche.
                _css, _bar = "", ""
                try:
                    _src = open("price_action.py", "r", encoding="utf-8",
                                errors="ignore").read()
                    _i = _src.find("<style>")
                    _j = _src.find("</style>", _i) if _i >= 0 else -1
                    if _i >= 0 and _j > _i:
                        _css = _src[_i:_j + 8]
                    _tabs = []
                    for _l in _src.split("\\n"):
                        if 'class="tab"' in _l and "onclick=" in _l:
                            _x = _l.strip()
                            if "showTab(" in _x:
                                # Un onglet interne designe un bloc cache
                                # de la page d accueil. Ailleurs il n
                                # existe pas : on ramene au tableau de
                                # bord plutot que de laisser un bouton
                                # mort.
                                _a1 = _x.find('onclick="')
                                if _a1 >= 0:
                                    _b1 = _x.find('"', _a1 + 9)
                                    if _b1 > _a1:
                                        _x = (_x[:_a1]
                                              + "onclick=\\"location.href='/'\\""
                                              + _x[_b1 + 1:])
                            if _x not in _tabs:
                                _tabs.append(_x)
                    _bar = "".join(_tabs)
                except Exception:
                    _css, _bar = "", ""
                _d = "cartes"
                _f = ""
                if parsed.query:
                    for _kv in parsed.query.split("&"):
                        if _kv.startswith("f="):
                            _f = _kv[2:]
                if _f and ("/" in _f or "\\\\" in _f or ".." in _f
                           or not _f.endswith(".html")):
                    _f = ""
                _tete = (_css + '<div style="padding:6px 10px">'
                         + _bar + '</div>')
                body = None
                if _f:
                    try:
                        _h = open(_d + "/" + _f, "rb")
                        _raw = _h.read()
                        _h.close()
                        body = ((_tete + '<div style="padding:4px 12px;'
                                 'font:13px system-ui;color:#8b949e">'
                                 '<a href="/cartes" style="color:#58a6ff">'
                                 '&larr; toutes les cartes</a> &nbsp;|&nbsp; '
                                 + _f + '</div>').encode("utf-8") + _raw)
                    except Exception:
                        body = None
                if body is None:
                    _li = []
                    try:
                        _n = [x for x in _o.listdir(_d)
                              if x.endswith(".html")]
                        _n.sort(key=lambda x: _o.path.getmtime(_d + "/" + x),
                                reverse=True)
                        for _x in _n:
                            _s2 = _o.path.getsize(_d + "/" + _x)
                            _m = _t.strftime("%Y-%m-%d %H:%M", _t.localtime(
                                _o.path.getmtime(_d + "/" + _x)))
                            _li.append('<tr><td style="padding:4px 16px 4px 0">'
                                       '<a href="/carte?f=' + _x
                                       + '" style="color:#58a6ff">' + _x
                                       + '</a></td><td style="color:#8b949e;'
                                       'padding-right:16px">' + _m
                                       + '</td><td style="color:#8b949e">'
                                       + str(_s2 // 1024) + ' Ko</td></tr>')
                    except Exception:
                        _li = []
                    if _li:
                        _c = ('<table style="border-collapse:collapse">'
                              + "".join(_li) + '</table>')
                    else:
                        _c = ('<p style="color:#8b949e">Aucune carte dans '
                              '<code>cartes\\\\</code>. Pour en produire une : '
                              '<code style="color:#c9d1d9">python '
                              'bougies_reperes.py --html 2026-08-14</code>'
                              '</p>')
                    body = ('<!doctype html><meta charset="utf-8">'
                            '<title>Cartes</title>'
                            '<body style="background:#0d1117;color:#c9d1d9;'
                            'font:14px system-ui;margin:0">' + _tete
                            + '<div style="padding:14px 18px">'
                            '<h1 style="font-size:17px;color:#58a6ff;'
                            'margin:6px 0">Cartes</h1>'
                            '<p style="color:#8b949e">Relu a chaque requete : '
                            'deposer un .html dans <code>cartes\\\\</code> '
                            'suffit a le faire apparaitre.</p>'
                            + _c + '</div>').encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

'''

B_BOUTON = ('''<div class="tab" onclick="window.open('/cartes','_blank')"'''
            ''' style="color:#58a6ff;font-weight:bold;">CARTES</div>'''
            '''<div class="tab" onclick="window.open('/profils','_blank')"'''
            ''' style="color:#58a6ff;font-weight:bold;">PROFILS</div>''')


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

    manque = []
    for nom, anc in (("la route /profils dans _do_GET_impl", A_ROUTE),
                     ("le bouton PROFILS dans la barre", A_BOUTON)):
        n = src.count(anc)
        if n != 1:
            manque.append((nom, n))
    if manque:
        print()
        print("KO : ancres introuvables ou ambigues. RIEN n a ete ecrit.")
        for nom, n in manque:
            print("  %-40s %d occurrence(s), attendu 1" % (nom, n))
        print()
        print("Ce patch s insere a cote de la route /profils, decrite dans")
        print("NOTES_panneaux.md. Si elle a change, envoie-moi les deux")
        print("lignes correspondantes : je ne devine pas ou m inserer dans")
        print("le processus qui sert le 8095.")
        return 1
    print("  les 2 ancres sont uniques.")

    # Controle utile : la barre existe-t-elle vraiment sous la forme
    # attendue ? Si `class="tab"` est absent, la route servira une page
    # sans navigation -- ce qui est le defaut qu on corrige.
    n_tabs = src.count('class="tab"')
    print("  %d ligne(s) <div class=\"tab\"> a recopier." % n_tabs)
    if n_tabs < 5:
        print("  ATTENTION : moins de 5 onglets trouves. La barre sera")
        print("  probablement vide. Verifier avant d appliquer.")

    out = src.replace(A_ROUTE, B_ROUTE + A_ROUTE, 1)
    out = out.replace(A_BOUTON, B_BOUTON, 1)

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
    print("Puis : bouton CARTES, ou http://vmi654074:8095/cartes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
