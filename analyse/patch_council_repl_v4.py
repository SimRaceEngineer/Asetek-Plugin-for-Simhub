# -*- coding: utf-8 -*-
"""
patch_council_repl_v4.py -- supprimer la variable d environnement

  python patch_council_repl_v4.py --essai
  python patch_council_repl_v4.py

POURQUOI CETTE VERSION

    La v3 acceptait DEUX declencheurs, en OU :

        REPL_DEEPSEEK=1 dans l environnement
        OU sys.argv[0] se termine par price_action.py

    Le 12/08 a 10h31, le test d isolation a rendu la cle a un faux
    nemotron_trader.py. Le patch n y etait pour rien : le shell de test
    portait encore REPL_DEEPSEEK=1, pose une heure plus tot pour la v2.
    La premiere branche a suffi.

    Mais la lecon tient quand meme. Une variable d environnement se
    propage a tout ce qu on lance depuis la fenetre ou elle est posee.
    Tant qu elle existe, lancer un trader depuis le mauvais shell arme
    DeepSeek dans ce trader. Personne ne s en apercevrait : il n y a
    aucun message, le trader se mettrait simplement a parler.

    Depuis la v3, cette branche ne sert plus a rien -- l identite du
    processus fait tout le travail. Elle n apporte donc aucune fonction
    et porte tout le risque. On la retire.

APRES CE PATCH

    Une seule condition, intrinseque au processus :

        os.path.basename(sys.argv[0]).lower() == "price_action.py"

    Aucune variable d environnement ne peut plus armer DeepSeek, ni par
    heritage, ni par erreur, ni par un shell oublie. Le seul moyen de
    donner la cle a un autre programme est de le renommer
    price_action.py -- ce qui ne se fait pas par accident.

CE QUE CA NE CHANGE PAS

    Le garde-fou du double reste : si DEEPSEEK_API_KEY est presente dans
    le processus, on ne charge rien et on l ecrit. ai_master_agent, qui
    cherche cette variable-la, reste sans cle dans le 8095.

    Le fichier lu reste deepseek_api_key_repl.txt, connu du seul
    council_shadow.

A APPLIQUER SUR UN council_shadow.py DEJA PATCHE PAR LA v3.
IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
PREND EFFET AU PROCHAIN DEMARRAGE DU 8095.

APRES APPLICATION, pense a retirer la variable des shells ouverts :
    Remove-Item Env:REPL_DEEPSEEK -ErrorAction SilentlyContinue
Elle ne fait plus rien, mais autant ne pas la laisser trainer.
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

# Le bloc pose par la v3, tel quel. On capture l indentation.
RE_V3 = re.compile(
    r'^([ \t]*)_repl_ok = os\.environ\.get\("REPL_DEEPSEEK", ""\)'
    r'\.strip\(\) == "1"[ \t]*\n'
    r'[ \t]*if not _repl_ok:[ \t]*\n'
    r'[ \t]*_a0 = os\.path\.basename\(str\(_sys\.argv\[0\] or ""\)\)\.lower\(\)'
    r'[ \t]*\n'
    r'[ \t]*_repl_ok = _a0 == "price_action\.py"[ \t]*$',
    re.M)

NEUF = '''    # 12/08 (v4) : la branche REPL_DEEPSEEK a ete retiree. Une variable
    # d environnement se propage a tout ce qu on lance depuis la fenetre
    # ou elle est posee -- un trader lance depuis le mauvais shell
    # recevait la cle, sans un mot. Elle ne servait plus a rien depuis
    # que l identite du processus fait le travail. Seul declencheur :
    _a0 = os.path.basename(str(_sys.argv[0] or "")).lower()
    _repl_ok = _a0 == "price_action.py"'''


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

    if "_repl_ok" not in src:
        print("KO : la v3 n est pas appliquee sur ce fichier.")
        print("Applique patch_council_repl_v3.py d abord.")
        return 1

    if 'os.environ.get("REPL_DEEPSEEK"' not in src:
        print("Deja applique -- la variable a deja disparu du code.")
        return 0

    trouve = RE_V3.findall(src)
    if len(trouve) != 1:
        print("KO : %d occurrence(s) du bloc v3, il en faut 1." % len(trouve))
        print("Attendu, a n importe quelle indentation :")
        print('    _repl_ok = os.environ.get("REPL_DEEPSEEK", "").strip() == "1"')
        print("    if not _repl_ok:")
        print('        _a0 = os.path.basename(str(_sys.argv[0] or "")).lower()')
        print('        _repl_ok = _a0 == "price_action.py"')
        print("Rien n a ete ecrit.")
        return 1

    ind = trouve[0]
    corps = "\n".join(ind + l[4:] if l.startswith("    ") else (ind + l if l else "")
                      for l in NEUF.split("\n"))
    neuf = RE_V3.sub(lambda m: corps, src, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    # Post-condition : plus une seule lecture de la variable dans le fichier.
    if 'os.environ.get("REPL_DEEPSEEK"' in neuf:
        print("KO : il reste une lecture de REPL_DEEPSEEK apres substitution.")
        print("Rien n a ete ecrit.")
        return 1

    print("bloc v3 trouve : indentation %d espaces" % len(ind))
    print()
    print("Apres patch, un seul declencheur :")
    print('    os.path.basename(sys.argv[0]).lower() == "price_action.py"')
    print()
    print("Aucune variable d environnement ne peut plus armer DeepSeek.")
    print("Un trader lance depuis un shell ou REPL_DEEPSEEK traine")
    print("restera muet, ce qui n etait PAS le cas avant ce patch.")

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
    print("Controle, dans un shell PROPRE :")
    print("    Remove-Item Env:REPL_DEEPSEEK -ErrorAction SilentlyContinue")
    print("    python -c \"import sys; sys.argv[0]='nemotron_trader.py';"
          " import council_shadow as c; print(repr(c._load_deepseek_key()))\"")
    print("Doit rendre ''. Et avec price_action.py, une cle de 35.")
    print()
    print("Redemarre ensuite le 8095.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
