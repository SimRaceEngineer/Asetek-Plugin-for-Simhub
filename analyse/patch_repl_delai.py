# -*- coding: utf-8 -*-
r"""
patch_repl_delai.py -- donner un delai au REPL, et une trace a ses appels

  python patch_repl_delai.py --essai      montre ce qui changerait
  python patch_repl_delai.py              applique
  python patch_repl_delai.py --defaire    restaure les .bak

CE QU IL CORRIGE, ET POURQUOI

    council_shadow._call_model construit sa requete sans AUCUN delai :

        _kw = {"model": mid, "messages": messages,
               "max_tokens": max_tokens, "temperature": 0.3,
               "stream": False}
        resp = cli.chat.completions.create(**_kw)

    COUNCIL_TIMEOUT vaut 120 ligne 61 et n est utilise nulle part. Sans
    delai, le SDK applique son defaut -- 600 s par tentative, deux
    reprises. Et repl_web fait `t.join()` sans borne : le gestionnaire
    HTTP tient la connexion tout ce temps.

    Le seul composant de la chaine qui ait une limite, c est le
    navigateur. C est donc lui qui lache, et quand il lache il ne peut
    produire qu une erreur reseau. "Failed to fetch" n est pas le
    symptome d une panne, c est le symptome d une ABSENCE DE DELAI.

LES QUATRE CHANGEMENTS, ET LEUR PORTEE

    1. council_shadow._call_model gagne un parametre `timeout=None`,
       pose dans _kw SEULEMENT s il est fourni.

       PORTEE : ce fichier est importe par onze modules, dont quatre
       traders et ai_master_agent. Le defaut None laisse leur
       comportement RIGOUREUSEMENT inchange -- aucun d eux ne passe
       l argument. C est la seule forme acceptable ici : on ajoute une
       possibilite, on ne modifie aucune trajectoire existante.

    2. repl_web passe son propre delai, reglable par
       REPL_REASONER_TIMEOUT, defaut 300 s. Pas COUNCIL_TIMEOUT :
       120 s est trop court pour un raisonneur a 32000 jetons -- il
       mettait deja 130 s a 8000.

    3. repl_web borne son join a delai + 30 s. Le gestionnaire repond
       TOUJOURS, meme pour dire qu il n a pas eu de reponse.

    4. repl_web enregistre chaque appel dans docs\repl_ops.jsonl :
       modele, duree, jetons demandes et rendus, erreur, horodatage.

       Aujourd hui RIEN n enregistre. _log_ops n est appele que par
       les voies council ; _log_gemini_ops et _log_grok_ops ne
       couvrent que gemini et grok. repl_web appelle _call_model
       directement. Zero trace -- d ou repl_err.txt et repl_out.txt
       vides, et d ou une semaine de suppositions.

    5. repl_web ligne 507 enregistrait la reponse du CHAT dans
       l historique :

           _conversation.append({"role": "assistant",
                                 "content": g["text"]})

       Or REPL_MODELES = ("deepseek_reasoner",) : le chat n est jamais
       interroge, son texte vaut "(non interroge -- voir
       REPL_MODELES)". A chaque tour, c est cette phrase qui entrait
       dans l historique a la place de la reponse. Le raisonneur ne
       revoyait jamais ce qu il avait dit. `g` -> `gl`.

CE QU IL NE FAIT PAS

    Il ne touche a aucun trader, a aucun fichier d etat, a aucun
    processus. Il ne redemarre rien : les modifications prennent effet
    au prochain demarrage du 8095, choisi par toi.

    Chaque fichier modifie est sauvegarde en .bak avant ecriture, et
    --defaire les restaure.
"""
import argparse
import io
import os
import shutil
import sys

# (fichier, ancre, remplacement, description)
CHANGEMENTS = [
 ("council_shadow.py",
  "def _call_model(model: str, messages, max_tokens=COUNCIL_MAX_TOKENS):",
  "def _call_model(model: str, messages, max_tokens=COUNCIL_MAX_TOKENS,\n"
  "                timeout=None):",
  "1/5  _call_model accepte un delai (defaut None = inchange)"),

 ("council_shadow.py",
  '        _kw = {"model": mid, "messages": messages, "max_tokens": max_tokens, "temperature": 0.3, "stream": False}',
  '        _kw = {"model": mid, "messages": messages, "max_tokens": max_tokens, "temperature": 0.3, "stream": False}\n'
  "        # 19/08/2026 -- sans delai, le SDK applique 600 s par tentative\n"
  "        # et deux reprises. Le seul composant de la chaine qui avait une\n"
  "        # limite etait le navigateur : c est lui qui lachait, en erreur\n"
  "        # reseau illisible. Pose SEULEMENT si l appelant le fournit.\n"
  "        if timeout is not None:\n"
  "            _kw[\"timeout\"] = float(timeout)",
  "2/5  le delai entre dans la requete, s il est fourni"),

 ("repl_web.py",
  "_REASONER_DEFAUT = 32000",
  "_REASONER_DEFAUT = 32000\n"
  "\n"
  "# 19/08/2026 -- LE DELAI, QUI N EXISTAIT NULLE PART\n"
  "#\n"
  "# council_shadow._call_model ne passait aucun timeout : defaut SDK,\n"
  "# 600 s par tentative, deux reprises. Le navigateur lachait avant et\n"
  "# rendait 'Failed to fetch' -- une erreur reseau pour une cause qui n\n"
  "# en etait pas une.\n"
  "#\n"
  "# 300 et non COUNCIL_TIMEOUT (120) : un raisonneur a 32000 jetons\n"
  "# mettait deja 130 s a 8000. Trop court couperait des reponses valides.\n"
  "_REASONER_DELAI_DEFAUT = 300.0\n"
  "\n"
  "\n"
  "def _delai_reasoner():\n"
  "    \"\"\"Delai de l appel, en secondes. REPL_REASONER_TIMEOUT.\n"
  "\n"
  "    Meme forme que _plafond_reasoner : import local, valeur illisible\n"
  "    retombant sur le defaut plutot que de casser la page.\"\"\"\n"
  "    import os as _o\n"
  "    try:\n"
  "        return float(_o.environ.get(\"REPL_REASONER_TIMEOUT\",\n"
  "                                    _REASONER_DELAI_DEFAUT))\n"
  "    except (TypeError, ValueError):\n"
  "        return _REASONER_DELAI_DEFAUT\n"
  "\n"
  "\n"
  "def _ops(modele, el, usage, err, to, plafond, delai):\n"
  "    \"\"\"Une ligne par appel dans docs\\\\repl_ops.jsonl.\n"
  "\n"
  "    Rien n enregistrait les appels du REPL : _log_ops n est appele que\n"
  "    par les voies council, _log_gemini_ops et _log_grok_ops ne couvrent\n"
  "    que gemini et grok, et repl_web appelle _call_model directement.\n"
  "    Un echec sans trace ne se diagnostique pas -- il se suppose.\n"
  "\n"
  "    N echoue jamais dans l appelant : une trace qui casse ce qu elle\n"
  "    observe ne vaut rien.\"\"\"\n"
  "    try:\n"
  "        import json as _j, os as _o, io as _i\n"
  "        from datetime import datetime as _d\n"
  "        u = usage or {}\n"
  "        r = {\"iso\": _d.now().strftime(\"%Y-%m-%d %H:%M:%S\"),\n"
  "             \"modele\": modele, \"secondes\": round(float(el or 0), 2),\n"
  "             \"plafond\": plafond, \"delai\": delai, \"timeout\": bool(to),\n"
  "             \"prompt_tokens\": u.get(\"prompt_tokens\"),\n"
  "             \"completion_tokens\": u.get(\"completion_tokens\"),\n"
  "             \"plafond_atteint\": bool(u.get(\"completion_tokens\")\n"
  "                                     and u[\"completion_tokens\"] >= plafond),\n"
  "             \"err\": (str(err)[:300] if err else None)}\n"
  "        d = _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), \"docs\")\n"
  "        if not _o.path.isdir(d):\n"
  "            _o.makedirs(d)\n"
  "        with _i.open(_o.path.join(d, \"repl_ops.jsonl\"), \"a\",\n"
  "                     encoding=\"utf-8\", newline=\"\") as f:\n"
  "            f.write(_j.dumps(r, ensure_ascii=True) + \"\\n\")\n"
  "    except Exception:\n"
  "        pass",
  "3/5  le delai reglable + le journal des appels"),

 ("repl_web.py",
  "            _mt = REPL_MAX_TOKENS.get(mk, 3000)\n"
  "            txt, usage, el, to, err = cs._call_model(mk, messages, _mt)\n"
  "            txt = _repl_txt(txt, usage, err, to, _mt)",
  "            _mt = REPL_MAX_TOKENS.get(mk, 3000)\n"
  "            _dl = _delai_reasoner()\n"
  "            txt, usage, el, to, err = cs._call_model(mk, messages, _mt,\n"
  "                                                     timeout=_dl)\n"
  "            _ops(mk, el, usage, err, to, _mt, _dl)\n"
  "            txt = _repl_txt(txt, usage, err, to, _mt)",
  "4/5  l appel porte le delai, et laisse une trace"),

 ("repl_web.py",
  "    for t in ths:\n"
  "        t.start()\n"
  "    for t in ths:\n"
  "        t.join()",
  "    for t in ths:\n"
  "        t.start()\n"
  "    # Borne le join : le gestionnaire HTTP doit REPONDRE, meme pour dire\n"
  "    # qu il n a pas eu de reponse. Sans borne il tenait la connexion\n"
  "    # jusqu a ce que le navigateur abandonne -- d ou 'Failed to fetch'.\n"
  "    # +30 s sur le delai de l appel : le fil doit pouvoir rendre sa\n"
  "    # propre erreur de timeout avant qu on cesse de l attendre.\n"
  "    _attente = _delai_reasoner() + 30.0\n"
  "    for t in ths:\n"
  "        t.join(_attente)\n"
  "    for _m in REPL_MODELES:\n"
  "        if _m not in out:\n"
  "            out[_m] = {\"text\": \"(pas de reponse en %.0f s -- le fil\"\n"
  "                               \" tourne encore)\" % _attente,\n"
  "                       \"elapsed\": round(_attente, 1)}",
  "5a/5 le join est borne, et l absence de reponse se dit"),

 ("repl_web.py",
  '        _conversation.append({"role": "assistant", "content": g["text"]})',
  "        # 19/08/2026 -- c etait g, le CHAT, qui entrait dans l historique.\n"
  "        # REPL_MODELES = ('deepseek_reasoner',) : le chat n est jamais\n"
  "        # interroge, son texte vaut '(non interroge -- voir REPL_MODELES)'.\n"
  "        # Le raisonneur ne revoyait donc jamais ce qu il avait dit.\n"
  '        _conversation.append({"role": "assistant", "content": gl["text"]})',
  "5b/5 l historique garde la reponse du raisonneur, pas celle du chat"),
]


def cible(nom, racines):
    for r in racines:
        c = os.path.join(r, nom)
        if os.path.isfile(c):
            return c
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", action="append", default=None)
    p.add_argument("--essai", action="store_true",
                   help="montre ce qui changerait, n ecrit rien")
    p.add_argument("--defaire", action="store_true",
                   help="restaure les .bak")
    a = p.parse_args()
    racines = a.racine or ["."]

    fichiers = sorted(set(c[0] for c in CHANGEMENTS))
    chemins = {}
    for nom in fichiers:
        c = cible(nom, racines)
        if c is None:
            print("KO : %s introuvable dans %s" % (nom, ", ".join(racines)))
            return 1
        chemins[nom] = c

    if a.defaire:
        n = 0
        for nom, che in chemins.items():
            bak = che + ".bak"
            if os.path.isfile(bak):
                shutil.copyfile(bak, che)
                print("  restaure : %s <- %s" % (che, bak))
                n += 1
            else:
                print("  pas de sauvegarde pour %s" % che)
        print("\n%d fichier(s) restaure(s)." % n)
        return 0

    # --- verification de TOUTES les ancres avant d ecrire quoi que ce soit
    src = dict((nom, io.open(che, encoding="utf-8").read())
               for nom, che in chemins.items())
    absentes, deja = [], []
    for nom, ancre, remp, desc in CHANGEMENTS:
        s = src[nom]
        # Le deja-fait se teste EN PREMIER : plusieurs remplacements
        # contiennent leur propre ancre (on ajoute autour d elle). Tester
        # l ancre d abord les declarait "a faire" alors qu ils etaient
        # faits -- la boucle d ecriture les sautait quand meme, mais le
        # rapport mentait, et un rapport qui ment sur ce qu il a fait est
        # pire qu un rapport absent.
        if remp in s:
            deja.append(desc)
        elif s.count(ancre) != 1:
            absentes.append((desc, nom, s.count(ancre)))

    print("=" * 74)
    print("PATCH REPL -- delai, journal, memoire du raisonneur")
    print("=" * 74)
    for nom in fichiers:
        print("  %-22s %s" % (nom, chemins[nom]))
    print()

    if deja:
        print("  DEJA APPLIQUE :")
        for d in deja:
            print("    %s" % d)
        print()
    if absentes:
        print("  ANCRE INTROUVABLE -- rien ne sera ecrit :")
        for d, nom, n in absentes:
            print("    %s   (%s, %d occurrence(s) au lieu de 1)"
                  % (d, nom, n))
        print()
        print("  Le fichier n est pas dans l etat attendu. Plutot que de")
        print("  patcher a l aveugle, envoie-moi les lignes concernees :")
        print("      python repl_fetch.py --lignes FICHIER:DEBUT-FIN")
        return 1
    if not deja and not absentes:
        print("  Les %d ancres sont trouvees, une seule fois chacune."
              % len(CHANGEMENTS))
        print()

    for nom, ancre, remp, desc in CHANGEMENTS:
        if remp in src[nom]:
            continue
        src[nom] = src[nom].replace(ancre, remp, 1)
        print("  %s" % desc)
    print()

    if a.essai:
        print("  --essai : RIEN n a ete ecrit.")
        print("  Relance sans --essai pour appliquer.")
        return 0

    for nom in fichiers:
        che = chemins[nom]
        bak = che + ".bak"
        if not os.path.isfile(bak):
            shutil.copyfile(che, bak)
            print("  sauvegarde : %s" % bak)
        io.open(che, "w", encoding="utf-8", newline="").write(src[nom])
        print("  ecrit      : %s" % che)
    print()
    print("  Aucun processus n a ete touche. Les changements prennent")
    print("  effet au prochain demarrage du 8095, quand TU le decides.")
    print("  Pour revenir en arriere : python patch_repl_delai.py --defaire")
    return 0


if __name__ == "__main__":
    sys.exit(main())
