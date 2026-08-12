# -*- coding: utf-8 -*-
"""
patch_council_repl_v3.py -- ne plus dependre d une variable d environnement

  python patch_council_repl_v3.py --essai
  python patch_council_repl_v3.py

CE QUI S EST PASSE
    La v2 conditionnait la lecture de deepseek_api_key_repl.txt a la
    variable REPL_DEEPSEEK=1, posee dans le shell de lancement du
    processus 8095.

    Verifie en console : REPL_DEEPSEEK=1 puis python -c "..." rend une cle
    de 35 caracteres. Le patch et le fichier sont donc bons.

    Verifie dans le REPL : toujours "no DeepSeek key", sur un processus
    neuf, avec deux methodes de lancement differentes -- Start-Process
    avec $env: pose avant, puis cmd /c set ... && python. La variable
    n arrive pas.

    Plutot que de chercher pourquoi l heritage echoue, on cesse d en
    dependre.

CE QUE FAIT CETTE VERSION
    Le declencheur devient l IDENTITE DU PROCESSUS :

        sys.argv[0] se termine par price_action.py  ->  c est le 8095

    C est intrinseque. Ca ne se perd pas au lancement, ca ne depend
    d aucun shell, d aucun ordre de commandes, et ca survit a un
    redemarrage par le .bat, par le planificateur ou a la main.

    REPL_DEEPSEEK=1 reste accepte -- si tu veux forcer depuis un shell,
    ca marche toujours. Les deux conditions sont un OU.

CE QUE CA NE CHANGE PAS
    Les traders tournent chacun dans leur processus, avec leur propre
    argv[0] : nemotron_trader.py, reasoning_ab_trader.py,
    stats_llm_trader.py, janira_martingale_loop.py. Aucun ne s appelle
    price_action.py, donc aucun ne recoit la cle.

    ai_master_agent, charge dans le meme processus 8095 par repl_web:37,
    cherche toujours DEEPSEEK_API_KEY -- qui n existe ni en variable ni
    en fichier. Il reste idle. Rien de ce patch ne le concerne.

    Le garde-fou du double reste : si DEEPSEEK_API_KEY apparait, on ne
    charge rien et on l ecrit.

L IMPORT DE sys EST LOCAL
    council_shadow n importe pas sys. Comme pour macro_feed et repl_web,
    le bloc l importe lui-meme sous un alias.

IDEMPOTENT. Sauvegarde horodatee. ast.parse avant ecriture.
S APPLIQUE SUR UN council_shadow.py DEJA PATCHE PAR LA v2.
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
MARQUEUR = "_repl_ok"

RE_COND = re.compile(
    r'^([ \t]*)if os\.environ\.get\("REPL_DEEPSEEK", ""\)\.strip\(\) == "1":'
    r'[ \t]*$', re.M)

NEUF = '''    # 12/08 : l heritage de REPL_DEEPSEEK ne passe pas jusqu au
    # processus 8095, quelle que soit la methode de lancement. On se
    # base donc sur l identite du processus, qui elle ne se perd pas.
    # import local : council_shadow n importe pas sys.
    import sys as _sys
    _repl_ok = os.environ.get("REPL_DEEPSEEK", "").strip() == "1"
    if not _repl_ok:
        _a0 = os.path.basename(str(_sys.argv[0] or "")).lower()
        _repl_ok = _a0 == "price_action.py"
    if _repl_ok:'''


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
        print("Deja applique -- rien a faire.")
        return 0

    if "REPL_DEEPSEEK" not in src:
        print("KO : la v2 n est pas appliquee sur ce fichier.")
        print("Applique patch_council_repl_v2.py d abord.")
        return 1

    trouve = RE_COND.findall(src)
    if len(trouve) != 1:
        print("KO : %d occurrence(s) de la condition, il en faut 1."
              % len(trouve))
        print("Attendu :")
        print('    if os.environ.get("REPL_DEEPSEEK", "").strip() == "1":')
        print("Rien n a ete ecrit.")
        return 1

    ind = trouve[0]
    corps = "\n".join(ind + l[4:] if l.startswith("    ") else (ind + l if l else "")
                      for l in NEUF.split("\n"))
    neuf = RE_COND.sub(lambda m: corps, src, count=1)

    try:
        ast.parse(neuf)
    except SyntaxError as e:
        print("KO : ne compile pas (ligne %s) : %s" % (e.lineno, e.msg))
        print("Rien n a ete ecrit.")
        return 1

    print("condition trouvee : indentation %d espaces" % len(ind))
    print()
    print("Apres patch, la cle du REPL est chargee si :")
    print("    REPL_DEEPSEEK=1 dans l environnement   (comme avant)")
    print("  OU sys.argv[0] se termine par price_action.py")
    print()
    print("Aucun trader ne s appelle price_action.py :")
    print("    nemotron_trader.py, reasoning_ab_trader.py,")
    print("    stats_llm_trader.py, janira_martingale_loop.py")
    print("Ils restent muets, et ai_master_agent reste sans cle.")

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
    print("Redemarre le 8095 -- plus besoin de poser la moindre variable :")
    print("    Start-Process -FilePath python.exe -ArgumentList price_action.py")
    print("    -WorkingDirectory <dossier de la stack>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
