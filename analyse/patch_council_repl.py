# -*- coding: utf-8 -*-
"""
patch_council_repl.py -- rendre DeepSeek au REPL web, et a lui seul

  python patch_council_repl.py --essai    montre, n ecrit rien
  python patch_council_repl.py            applique

LE PROBLEME
    Le REPL web (:8095/repl) affiche "no DeepSeek key". Ses appels passent
    par council_shadow._load_deepseek_key(), qui cherche la variable
    DEEPSEEK_API_KEY puis les fichiers deepseek_api_key.txt et
    DEEPSEEK_API_KEY.txt.

    Mais on ne peut PAS simplement poser une de ces trois sources :

    1. council_shadow est importe par onze modules, dont quatre traders --
       nemotron_trader, reasoning_ab_trader, stats_llm_trader,
       janira_martingale_loop -- plus ai_master_agent a trois endroits.
       Poser un fichier le rend bavard pour tous, dans tous les processus.

    2. repl_web.py:37 fait "import ai_master_agent as ai" au niveau du
       module. L agent est donc DEJA CHARGE dans le processus 8095. Or il
       est arme et n attend que la cle :

           MINI_ENABLED   = True     (le master : gate 50004 + closer)
           CLOSER_ENABLED = True     (cycle 7s, force=True, tous magics
                                      des trois indices, bypass du
                                      let-run guard)
           RAW_ENABLED    = False    (coupe le 18/06)

       Poser DEEPSEEK_API_KEY dans l environnement de 8095 reveillerait
       donc le closer en meme temps que le REPL.

CE QUE FAIT CE PATCH
    Il ajoute a council_shadow une quatrieme source de cle, que PERSONNE
    d autre ne connait : le fichier deepseek_api_key_repl.txt, lu
    uniquement si la variable d environnement REPL_DEEPSEEK vaut 1.

    Le processus 8095 demarrera avec REPL_DEEPSEEK=1 et SANS
    DEEPSEEK_API_KEY. Consequences, dans ce meme processus :

        council_shadow  -> trouve la cle, le REPL parle
        ai_master_agent -> cherche DEEPSEEK_API_KEY, ne trouve rien,
                           reste idle, sans qu on ait touche a un seul
                           de ses drapeaux

    Et dans les autres processus -- les traders -- REPL_DEEPSEEK est
    absent, donc council_shadow reste exactement aussi muet qu aujourd hui.

POURQUOI DEUX VARIABLES PLUTOT QU UN DRAPEAU
    Un drapeau "DeepSeek ne trade pas" se retourne par erreur, par un
    collegue, par un patch mal relu. Deux clefs differentes pour deux
    consommateurs differents, c est une propriete du systeme, pas un
    reglage. L agent n est pas desactive : il n a pas de cle.

    Troisieme barriere pour memoire : council_shadow.py ecrit lui-meme,
    lignes 8 et 27, qu il ne touche ni MT5 ni order_send -- "Pure file
    I/O". Meme avec une cle, il ne sait pas envoyer d ordre.

LE CAS DES DEUX CLES A LA FOIS
    Si REPL_DEEPSEEK=1 ET DEEPSEEK_API_KEY sont presentes ensemble, c est
    que quelqu un a pose la vraie cle dans ce processus -- donc que
    l agent est arme. Le patch refuse alors de charger quoi que ce soit
    et l ecrit sur la sortie du processus. Ca ne protege rien (l agent a
    deja sa cle par l environnement), mais ca rend la faute VISIBLE tout
    de suite, au lieu d un REPL qui marche pendant que le closer tourne.

CE QU IL NE FAIT PAS
    Il ne touche a aucun autre fichier. Il ne modifie ni MINI_ENABLED, ni
    CLOSER_ENABLED, ni le comportement actuel quand REPL_DEEPSEEK est
    absent : sans cette variable, _load_deepseek_key se comporte au
    caractere pres comme avant.

IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
PREND EFFET AU PROCHAIN DEMARRAGE DU PROCESSUS 8095 -- qui porte le
trailing SAR, donc a faire a la cloture, pas en seance.
"""
import argparse
import ast
import io
import os
import re
import shutil
import sys
from datetime import datetime

CIBLE = "council_shadow.py"
MARQUEUR = "REPL_DEEPSEEK"
FICHIER_REPL = "deepseek_api_key_repl.txt"

RE_TETE = re.compile(
    r'^([ \t]*)k = os\.environ\.get\("DEEPSEEK_API_KEY", ""\)\.strip\(\)[ \t]*\n'
    r'[ \t]*if k:[ \t]*\n'
    r'[ \t]*return k[ \t]*$',
    re.M)

NEUF = '''
    # 12/08/2026 -- CLE RESERVEE AU REPL WEB
    #
    # council_shadow est importe par onze modules, dont quatre traders et
    # ai_master_agent. Et repl_web.py:37 charge ai_master_agent dans le
    # processus 8095, ou il attend sa cle avec CLOSER_ENABLED=True et un
    # cycle de 7 secondes en force=True.
    #
    # On ne peut donc pas poser DEEPSEEK_API_KEY ici sans reveiller le
    # closer. Quatrieme source, connue de ce seul fichier : lue uniquement
    # si REPL_DEEPSEEK=1, variable que seul le processus 8095 porte.
    if os.environ.get("REPL_DEEPSEEK", "").strip() == "1":
        if k:
            print("[council_shadow] REPL_DEEPSEEK=1 ET DEEPSEEK_API_KEY"
                  " presente en meme temps : aucune cle chargee."
                  " La vraie cle est dans ce processus, donc ai_master"
                  " est arme. Retire DEEPSEEK_API_KEY de cet"
                  " environnement.", file=sys.stderr)
            return ""
        _pr = os.path.join(_HERE, "%s")
        if os.path.exists(_pr):
            try:
                with open(_pr, "r", encoding="utf-8") as _f:
                    _raw = _f.read().strip()
                if _raw.lower().startswith("export "):
                    _raw = _raw[7:].strip()
                if "=" in _raw and not _raw.startswith("sk-"):
                    _raw = _raw.split("=", 1)[1].strip()
                return _raw.strip().strip('"').strip("'").strip()
            except Exception:
                pass
        return ""''' % FICHIER_REPL


def lire(chemin):
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return io.open(chemin, encoding=enc).read(), enc
        except (UnicodeDecodeError, ValueError):
            continue
    raise IOError("encodage non reconnu pour %s" % chemin)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fichier", default=CIBLE)
    p.add_argument("--essai", action="store_true")
    a = p.parse_args()

    if not os.path.isfile(a.fichier):
        print("KO : %s introuvable -- lance depuis le dossier de la stack."
              % a.fichier)
        return 1

    src, enc = lire(a.fichier)
    print("%s : %d lignes, encodage %s" % (a.fichier, src.count("\n") + 1, enc))

    if MARQUEUR in src:
        print("Garde deja posee -- rien a faire.")
        return 0

    trouve = RE_TETE.findall(src)
    if len(trouve) != 1:
        print("KO : %d occurrence(s) du point d insertion, il en faut 1."
              % len(trouve))
        print("Attendu, a n importe quelle indentation :")
        print('    k = os.environ.get("DEEPSEEK_API_KEY", "").strip()')
        print("    if k:")
        print("        return k")
        print("Rien n a ete ecrit.")
        return 1

    # _HERE et sys doivent exister : le bloc insere les utilise.
    manque = [n for n in ("_HERE", "import sys", "import os") if n not in src]
    if manque:
        print("KO : %s absent de %s. Le bloc insere s en sert."
              % (", ".join(manque), a.fichier))
        print("Rien n a ete ecrit.")
        return 1

    ind = trouve[0]
    corps = "\n".join(ind + l[4:] if l.startswith("    ") else (ind + l if l else "")
                      for l in NEUF.split("\n"))

    def remplace(m):
        lignes = m.group(0).split("\n")
        return lignes[0] + corps + "\n" + "\n".join(lignes[1:])

    neuf = RE_TETE.sub(remplace, src, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print("point d insertion trouve : indentation %d espaces" % len(ind))
    print()
    print("Comportement apres patch, dans le processus 8095 :")
    print("  REPL_DEEPSEEK=1, pas de DEEPSEEK_API_KEY")
    print("    council_shadow  -> lit %s, le REPL parle" % FICHIER_REPL)
    print("    ai_master_agent -> pas de cle, reste idle")
    print("  Ailleurs (traders, moteur) : REPL_DEEPSEEK absent, donc")
    print("    council_shadow aussi muet qu aujourd hui.")

    if not os.path.exists(FICHIER_REPL):
        print()
        print("ATTENTION : %s n existe pas dans ce dossier." % FICHIER_REPL)
        print("Le patch s applique quand meme, mais le REPL restera muet")
        print("tant que le fichier n est pas la.")

    if os.path.exists("deepseek_api_key.txt"):
        print()
        print("DANGER : deepseek_api_key.txt EXISTE.")
        print("Ce fichier est lu par council_shadow dans TOUS les")
        print("processus, y compris ceux des traders, et par")
        print("ai_master_agent, session_brief, trading_council,")
        print("trading_council3 et v4_supervisor. Le patch ne le")
        print("neutralise pas. Deplace-le avant de redemarrer quoi que")
        print("ce soit.")

    if a.essai:
        print()
        print("--essai : rien n a ete ecrit.")
        return 0

    sauve = "%s.bak-%s" % (a.fichier, datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(a.fichier, sauve)
    io.open(a.fichier, "w", encoding=enc).write(neuf)
    print()
    print("Sauvegarde : %s" % sauve)
    print("Applique.")
    print()
    print("PREND EFFET AU PROCHAIN DEMARRAGE DU PROCESSUS 8095.")
    print("Ce processus porte le trailing SAR (price_action.py, lignes")
    print("2906-2916 et 3308-3324). Le redemarrer en seance ouvre un trou")
    print("de protection : fais-le a la cloture.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
