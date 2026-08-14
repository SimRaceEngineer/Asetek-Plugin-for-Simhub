# -*- coding: utf-8 -*-
"""
patch_council_client.py -- le client DeepSeek ne survit pas a la nuit

  python patch_council_client.py --essai
  python patch_council_client.py

CE QUI SE PASSE, ET POURQUOI CA N ARRIVE QUE LE MATIN

    Le 14/08, le REPL rendait "(vide / APIConnectionError: Connection
    error.)" en 1,1 a 4,2 secondes. Tout le reste etait sain, verifie
    un par un depuis le meme interpreteur :

        cle          35 caracteres, GET /v1/models -> 200
        reseau       pas de proxy, certifi en place, TLS bon
        modeles      deepseek-reasoner, deepseek-chat et
                     deepseek-v4-pro repondent tous les trois

    Le defaut est dans _get_deepseek_client(), et il tient en deux
    lignes prises ensemble :

        if _deepseek_client is not None:
            return _deepseek_client              # garde a vie
        ...
        OpenAI(..., max_retries=0)               # aucune reprise

    Le client porte un pool de connexions HTTP. Apres une nuit
    d inactivite les sockets dormantes sont coupees cote reseau. La
    premiere reutilisation leve ConnectError, que le SDK enveloppe en
    APIConnectionError -- et avec max_retries=0 il n y a pas de
    seconde tentative, alors qu une connexion neuve serait passee.

    D ou la signature : panne en une seconde et non un delai d attente,
    le lendemain matin et pas le soir, sur un processus qui dort depuis
    la veille 20:05 alors que la veille a 13:10 tout marchait.

CE QUE LE PATCH CHANGE -- DEUX CHOSES, PAS UNE

    1. Le client en cache a desormais un AGE MAXIMAL de 300 s. Au-dela
       il est jete et reconstruit. Rouvrir une connexion coute quelques
       millisecondes ; une socket morte coute la reponse.
    2. max_retries passe de 0 a 2. Une socket dormante se voit au
       premier essai et a disparu au second.

    Les deux, parce qu ils ne couvrent pas le meme cas. Le TTL evite
    d aller au casse-pipe quand on SAIT que le client est vieux ; la
    reprise sauve le cas ou il devient mort entre deux appels
    rapproches. L un sans l autre laisse un trou.

CE QUE LE PATCH NE CHANGE PAS

    Ni la cle, ni son chargement, ni la base_url, ni le timeout, ni le
    choix du modele, ni _load_deepseek_key et sa regle d identite par
    argv[0]. Une seule fonction est reecrite.

OU CA S APPLIQUE, ET QUAND CA PREND EFFET

    council_shadow.py est importe par price_action.py, qui sert le
    REPL (argv[0] == "price_action.py", l.287). Le patch modifie le
    FICHIER ; le processus en cours garde son code en memoire.

    ATTENTION : price_action.py a deux roles. Lance sans PA_ROLE=panel
    il demarre en role MOTEUR et passe de vrais ordres. Ne pas le
    relancer sans avoir relu le .bat qui le lance. Le patch, lui, ne
    lance rien et ne redemarre rien.

UNE ANCRE, relevee sur le fichier du VPS (l.327-341), verifiee unique.
IDEMPOTENT. Sauvegarde horodatee. ast.parse, puis controle que
max_retries=0 a bien disparu, que la fonction existe toujours, et que
rien d autre n a bouge.
"""
import argparse
import ast
import io
import os
import shutil
import sys
from datetime import datetime

CIBLE = "council_shadow.py"
MARQUEUR = "_DEEPSEEK_TTL"

ANCRE = '''def _get_deepseek_client():
    global _deepseek_client, _deepseek_err
    if _deepseek_client is not None:
        return _deepseek_client
    key = _load_deepseek_key()
    if not key:
        _deepseek_err = "no DeepSeek key (env DEEPSEEK_API_KEY or deepseek_api_key.txt)"
        return None
    try:
        from openai import OpenAI
        _deepseek_client = OpenAI(api_key=key, base_url=DEEPSEEK_BASE_URL, timeout=COUNCIL_TIMEOUT, max_retries=0)
        return _deepseek_client
    except Exception as e:
        _deepseek_err = f"{type(e).__name__}: {e}"
        return None
'''

NEUF = '''# Age maximal du client en cache, en secondes -- ajoute le 14/08.
# Le client porte un pool de connexions HTTP. Apres une nuit
# d inactivite, les sockets dormantes sont coupees cote reseau et la
# premiere reutilisation leve ConnectError, enveloppe en
# APIConnectionError. Le 14/08 au matin, le REPL echouait ainsi en
# 1,1 seconde alors que la cle, le reseau et les trois modeles
# repondaient parfaitement depuis un processus neuf.
_DEEPSEEK_TTL = 300.0
_deepseek_ne_le = 0.0


def _get_deepseek_client():
    global _deepseek_client, _deepseek_err, _deepseek_ne_le
    import time as _t
    if _deepseek_client is not None:
        if (_t.time() - _deepseek_ne_le) < _DEEPSEEK_TTL:
            return _deepseek_client
        # Trop vieux : on le jette sans meme l essayer. Rouvrir une
        # connexion coute quelques millisecondes ; une socket morte
        # coute la reponse -- et sans reprise elle la coutait
        # definitivement.
        _deepseek_client = None
    key = _load_deepseek_key()
    if not key:
        _deepseek_err = "no DeepSeek key (env DEEPSEEK_API_KEY or deepseek_api_key.txt)"
        return None
    try:
        from openai import OpenAI
        # DEUX reprises, la ou il n y en avait aucune : une socket
        # dormante se voit au premier essai et a disparu au second.
        # Le TTL ci-dessus ne
        # suffit pas seul -- il ne couvre pas le client qui meurt
        # entre deux appels rapproches.
        _deepseek_client = OpenAI(api_key=key, base_url=DEEPSEEK_BASE_URL, timeout=COUNCIL_TIMEOUT, max_retries=2)
        _deepseek_ne_le = _t.time()
        return _deepseek_client
    except Exception as e:
        _deepseek_err = f"{type(e).__name__}: {e}"
        return None
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
    print("%s : %d lignes" % (a.fichier, src.count("\n") + 1))

    if MARQUEUR in src:
        print("Deja applique -- rien a faire.")
        return 0

    n = src.count(ANCRE)
    if n != 1:
        print("KO : %d occurrence(s) de _get_deepseek_client(), il en faut 1."
              % n)
        print("     L ancre a ete relevee sur les lignes 327-341 du VPS le")
        print("     14/08. Si elle ne correspond plus, le fichier a change")
        print("     depuis -- relire avant de reecrire l ancre.")
        print("Rien n a ete ecrit.")
        return 1

    neuf = src.replace(ANCRE, NEUF, 1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # On COMPTE, on ne cherche pas la presence : council_shadow porte
    # d autres clients (Kimi, OpenAI) construits eux aussi sans reprise.
    # Chercher la chaine dans tout le fichier les attrapait et bloquait
    # un patch pourtant correct -- une garde trop large est une garde
    # qui refuse le bon travail.
    _av = src.count("max_retries=0")
    _ap = neuf.count("max_retries=0")
    if _ap != _av - 1:
        print("KO : la reprise a zero n a pas ete retiree exactement une")
        print("     fois (%d avant, %d apres). Rien n a ete ecrit."
              % (_av, _ap))
        return 1
    if neuf.count("max_retries=2") != src.count("max_retries=2") + 1:
        print("KO : la nouvelle reprise n a pas ete ajoutee exactement une")
        print("     fois. Rien n a ete ecrit.")
        return 1
    print("Reprise : %d client(s) sans reprise avant, %d apres -- un seul"
          % (_av, _ap))
    print("a change, les autres clients du fichier sont intacts.")

    # Rien d autre ne doit avoir bouge : ni le chargement de la cle,
    # ni la base_url, ni le timeout, ni la regle d identite par argv[0].
    for t in ('def _load_deepseek_key(', 'DEEPSEEK_BASE_URL',
              'COUNCIL_TIMEOUT', '_repl_ok', 'deepseek_api_key_repl.txt'):
        if src.count(t) != neuf.count(t):
            print("KO : %s n apparait plus le meme nombre de fois." % t)
            print("Rien n a ete ecrit.")
            return 1
    print("Intacts : _load_deepseek_key, DEEPSEEK_BASE_URL,")
    print("COUNCIL_TIMEOUT, la regle argv[0] et le fichier de cle REPL.")

    ok = False
    for f in ast.walk(ast.parse(neuf)):
        if isinstance(f, ast.FunctionDef) and f.name == "_get_deepseek_client":
            d = ast.dump(f)
            ok = "_DEEPSEEK_TTL" in d and "_deepseek_ne_le" in d
            break
    if not ok:
        print("KO : la fonction n a pas ete reecrite comme prevu.")
        print("Rien n a ete ecrit.")
        return 1
    print("Arbre verifie : _get_deepseek_client lit bien le TTL.")

    print()
    print("Deux changements, dans une seule fonction :")
    print("  - le client en cache expire au bout de 300 s")
    print("  - max_retries passe de 0 a 2")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DE price_action.py, qui sert")
    print("le REPL. ATTENTION : lance sans PA_ROLE=panel, ce script")
    print("demarre en role MOTEUR et passe de vrais ordres. Relire le")
    print(".bat avant toute relance -- ce patch, lui, ne lance rien.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding="utf-8").write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
