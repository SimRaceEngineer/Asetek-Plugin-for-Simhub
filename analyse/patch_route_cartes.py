# -*- coding: utf-8 -*-
r"""
patch_route_cartes.py -- les cartes HTML servies par le 8095, avec un
                         index qui n aura plus jamais besoin de patch

  python patch_route_cartes.py --essai
  python patch_route_cartes.py

CE QU IL AJOUTE

    /cartes          l INDEX : tout fichier .html depose dans cartes\
                     y apparait, trie du plus recent au plus ancien,
                     avec sa taille et sa date.
    /carte?f=nom     une carte precise, avec un bandeau de retour.
    un bouton        CARTES, dans la barre, sur le modele du seul
                     bouton de route qui existe.

POURQUOI UN INDEX ET PAS UNE ROUTE PAR CARTE

    `bougies_reperes.py --html <date>` produit un fichier par journee.
    Une route par fichier voudrait dire un patch par journee, sur le
    processus qui sert le 8095 -- c est-a-dire toucher le panneau
    vivant chaque fois qu on regarde une date.

    L index relit le dossier a CHAQUE requete. Deposer un fichier
    suffit desormais a le rendre visible. C est exactement ce qui avait
    ete fait le 12/08 pour les documents du REPL avec
    `patch_repl_docs_v3` : "Deposer un fichier la suffit desormais a le
    rendre lisible -- aucun patch a rejouer."

CE QUI EST RESPECTE, PARCE QUE C EST ECRIT DANS NOTES_panneaux.md

    - cascade `if parsed.path == "..."` dans `_do_GET_impl`,
      INDENTATION A 12 ESPACES, chaque branche finit par son `return` ;
    - chemins en barres OBLIQUES, jamais inverses : une barre inverse
      dans une chaine non brute est une source d echappement parasite ;
    - si le fichier manque, on repond 200 avec une page qui DIT quoi
      lancer. Jamais une trace de pile, jamais un 500 muet : le panneau
      ne doit pas tomber parce qu une carte n a pas ete generee ;
    - le bouton est copie sur le modele existant, couleur `#58a6ff`,
      parce que c est une route et non un onglet. Sur une interface qui
      existe, on recopie ; on ne concoit pas.

LES IMPORTS SONT LOCAUX, ET C EST LA CORRECTION DU 14/08

    L index a besoin de lister un dossier, donc de `os`. Le code
    genere l importe LUI-MEME (`import os as _o`) au lieu de supposer
    qu il existe au niveau module.

    Le 14/08 a 21:18 un patch a fait tomber la page en ecrivant
    `_os.environ` apres avoir "verifie" que `os` etait importe : le
    controle utilisait `ast.walk`, qui descend dans les fonctions, et
    avait pris un import local pour un import de module. La lecon
    ecrite ce jour-la est exactement celle qu on applique ici.

LE CHEMIN EST FILTRE

    `?f=` n accepte qu un nom de fichier : ni `/`, ni `\`, ni `..`, et
    il doit finir par `.html`. Sinon on renvoie l index. Une route qui
    sert un fichier nomme par le client sert n importe quel fichier si
    on ne l en empeche pas.

QUAND CA PREND EFFET

    Au prochain demarrage de `price_action.py`. Le panneau se termine
    SEUL toutes les ~40 minutes (PA_RESTART_SEC) et le gardien le
    relance avec PA_ROLE=panel. NE JAMAIS le lancer a la main : sans
    cette variable, `_run_trading` est vrai et de vrais ordres partent.

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
MARQUE = "/carte"

# Ancres documentees dans NOTES_panneaux.md. Si l une manque, on refuse
# et on dit laquelle : un patch qui devine ou s inserer dans le
# processus du 8095 est un patch qui fait tomber le panneau.
A_ROUTE = '''            if parsed.path == "/profils":
'''
A_BOUTON = ('''<div class="tab" onclick="window.open('/profils','_blank')"'''
            ''' style="color:#58a6ff;font-weight:bold;">PROFILS</div>''')

B_ROUTE = '''            if parsed.path == "/cartes" or parsed.path == "/carte":
                import os as _o
                import time as _t
                _d = "cartes"
                _f = ""
                if parsed.query:
                    for _kv in parsed.query.split("&"):
                        if _kv.startswith("f="):
                            _f = _kv[2:]
                # Un nom de fichier, rien d autre. Une route qui sert
                # un fichier nomme par le client sert n importe quel
                # fichier si on ne l en empeche pas.
                if _f and ("/" in _f or "\\\\" in _f or ".." in _f
                           or not _f.endswith(".html")):
                    _f = ""
                _p = ""
                if _f:
                    _p = _d + "/" + _f
                _ret = ('<div style="background:#161b22;padding:8px 14px;'
                        'font:13px system-ui;color:#8b949e">'
                        '<a href="/" style="color:#58a6ff">&larr; panneau'
                        '</a> &nbsp;|&nbsp; <a href="/cartes" '
                        'style="color:#58a6ff">cartes</a>')
                body = None
                if _p:
                    try:
                        _h = open(_p, "rb")
                        body = _h.read()
                        _h.close()
                        body = ((_ret + ' &nbsp;|&nbsp; ' + _f
                                 + '</div>').encode("utf-8") + body)
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
                            _s = _o.path.getsize(_d + "/" + _x)
                            _m = _t.strftime("%Y-%m-%d %H:%M", _t.localtime(
                                _o.path.getmtime(_d + "/" + _x)))
                            _li.append('<tr><td style="padding:4px 16px 4px 0">'
                                       '<a href="/carte?f=' + _x
                                       + '" style="color:#58a6ff">' + _x
                                       + '</a></td><td style="color:#8b949e;'
                                       'padding-right:16px">' + _m
                                       + '</td><td style="color:#8b949e">'
                                       + str(_s // 1024) + ' Ko</td></tr>')
                    except Exception:
                        _li = []
                    if _li:
                        _c = ('<table style="border-collapse:collapse">'
                              + "".join(_li) + '</table>')
                    else:
                        _c = ('<p style="color:#8b949e">Aucune carte dans '
                              '<code>cartes\\</code>.<br>Pour en produire '
                              'une :<br><code style="color:#c9d1d9">python '
                              'bougies_reperes.py --html 2026-08-14</code>'
                              '</p>')
                    body = ('<!doctype html><meta charset="utf-8">'
                            '<title>Cartes</title>'
                            '<body style="background:#0d1117;color:#c9d1d9;'
                            'font:14px system-ui;margin:0">'
                            + _ret + '</div><div style="padding:18px">'
                            '<h1 style="font-size:17px;color:#58a6ff">Cartes'
                            '</h1><p style="color:#8b949e">Relu a chaque '
                            'requete : deposer un fichier .html dans '
                            '<code>cartes\\</code> suffit a le faire '
                            'apparaitre ici.</p>' + _c
                            + '</div>').encode("utf-8")
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
        print("Ce patch s inserte a cote de la route /profils, decrite")
        print("dans NOTES_panneaux.md. Si elle a change de nom ou de")
        print("forme, envoie-moi les deux lignes correspondantes et je")
        print("refais les ancres -- je ne devine pas ou m inserer dans")
        print("le processus qui sert le 8095.")
        return 1
    print("  les 2 ancres sont uniques.")

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
    print("PREND EFFET AU PROCHAIN DEMARRAGE DU PANNEAU.")
    print("Il se termine SEUL toutes les ~40 minutes et le gardien le")
    print("relance avec PA_ROLE=panel. NE PAS le lancer a la main :")
    print("sans cette variable, de vrais ordres partent.")
    print()
    print("Ensuite : le bouton CARTES dans la barre, ou directement")
    print("http://vmi654074:8095/cartes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
