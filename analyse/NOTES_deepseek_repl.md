# DeepSeek rendu au REPL, et a lui seul -- 12/08/2026

## La demande

Reactiver DeepSeek **uniquement** pour le REPL web (`:8095/repl`) : lecture
des documents, aucune capacite d ouvrir ou de fermer une position, ni par
le closer ni par la loop.

## Pourquoi ce n etait pas qu une histoire de cle

`repl_web.py:37` fait `import ai_master_agent as ai` **au niveau du
module**. L agent est donc deja charge dans le processus 8095, et il y est
arme :

    MINI_ENABLED   = True     gate 50004 + closer
    CLOSER_ENABLED = True     cycle 7 s, force=True, tous magics des trois
                              indices, bypass du let-run guard
    RAW_ENABLED    = False    coupe le 18/06

Poser `DEEPSEEK_API_KEY` dans ce processus aurait donc reveille le closer
en meme temps que le REPL. Et poser un `deepseek_api_key.txt` a la racine
aurait rendu la cle a **onze** modules, dont quatre traders.

L isolation ne pouvait pas venir d un drapeau : un drapeau se retourne.

## Ce qui a ete construit

Trois barrieres independantes, aucune n etant un reglage :

1. **Deux fichiers de cle pour deux consommateurs.** `council_shadow` lit
   `deepseek_api_key_repl.txt`, que personne d autre ne connait.
   `ai_master_agent` cherche `DEEPSEEK_API_KEY`, qui n existe ni en
   variable ni en fichier. L agent n est pas desactive : **il n a pas de
   cle**.
2. **Le declencheur est l identite du processus**, pas un reglage :
   `os.path.basename(sys.argv[0]).lower() == "price_action.py"`.
3. **`council_shadow` n a ni MT5 ni `order_send`** -- il l ecrit lui-meme
   lignes 8 et 27, "Pure file I/O". Meme avec une cle, il ne sait pas
   envoyer un ordre.

Garde-fou supplementaire : si `DEEPSEEK_API_KEY` apparait dans le
processus du REPL, rien n est charge et le processus l ecrit. Ca ne
protege rien -- l agent aurait deja sa cle -- mais ca rend la faute
visible tout de suite.

## Les quatre versions, et pourquoi

| v | declencheur | pourquoi elle a change |
|---|---|---|
| v1 | -- | refusee par sa propre garde : `council_shadow` n importe pas `sys` |
| v2 | `REPL_DEEPSEEK=1` | appliquee, mais le REPL restait muet |
| v3 | variable **OU** `argv[0]` | la variable n atteignait jamais le processus 8095 |
| v4 | `argv[0]` **seul** | la variable etait devenue le seul chemin de fuite |

### Pourquoi la v3

`REPL_DEEPSEEK=1` verifiee en console rendait une cle de 35 caracteres,
donc le patch et le fichier etaient bons. Mais le REPL affichait toujours
"no DeepSeek key" sur un processus neuf, avec **deux** methodes de
lancement differentes. Plutot que de chercher pourquoi l heritage
echouait, on a cesse d en dependre : `sys.argv[0]` est intrinseque au
processus, il ne se perd ni au lancement, ni par un `.bat`, ni par le
planificateur.

### Pourquoi la v4

Le test d isolation a rendu la cle a un faux `nemotron_trader.py`. Le
patch n y etait pour rien : le shell de test portait encore
`REPL_DEEPSEEK=1`, posee une heure plus tot. La condition etant un OU, la
premiere branche suffisait.

La lecon tient quand meme : une variable d environnement se propage a
tout ce qu on lance depuis la fenetre ou elle est posee. Un trader lance
depuis le mauvais shell aurait recu la cle **sans un mot dans les logs**.
Cette branche ne servait plus a rien depuis la v3 et portait tout le
risque. Retiree.

## Verification finale, sur la machine

| processus | environnement | cle obtenue |
|---|---|---|
| `price_action.py` (8095) | rien de pose | **35 caracteres** |
| `nemotron_trader.py` | shell propre | `''` |
| `nemotron_trader.py` | `REPL_DEEPSEEK=1` posee | `''` |
| `price_action.py` | `DEEPSEEK_API_KEY` posee | `''` + avertissement |

Reproduire (une seule ligne, le collage recolle les lignes separees) :

    $env:REPL_DEEPSEEK="1"; python -c "import sys; sys.argv[0]='nemotron_trader.py'; import council_shadow as c; print(repr(c._load_deepseek_key()))"; Remove-Item Env:REPL_DEEPSEEK -ErrorAction SilentlyContinue

## Ce que le REPL peut lire

`patch_repl_docs_v2` ajoute a `_static_ctx`, dans `repl_web` **et nulle
part ailleurs**, une liste **explicite** de documents :

    notes\*.md
    docs\JOURNAL.md
    G:\My Drive\ScalpEA\panels\*.{md,txt}

`export_panels.py` ecrit dans ce dernier dossier : rails trades,
orderflow, rails post 05/08, rails 3 periodes. Deposer un fichier la
suffit desormais a le rendre lisible -- aucun patch a rejouer.

**Le cout est reel** : ces documents partent dans le message systeme a
**chaque** question. 158 900 caracteres charges, soit ~40 000 jetons par
question. Plafonds poses a 100 000 caracteres par document et 200 000 au
total ; le processus ecrit au demarrage ce qu il a charge et ce qu il a
coupe, pour que la facture ne se decouvre pas apres coup.

Le REPL relit ce dossier **au demarrage du processus 8095**, pas a chaque
question : un export fait apres coup n est visible qu au redemarrage
suivant.

Etat verifie au 12/08 13h09, DeepSeek citant lui-meme ses sources :

    panel_orderflow.txt        export 11:18:51
    panel_rails_post0508.txt   export 11:18:53
    panel_rails_trades.txt     export 11:18:41
    panel_rails_trois.txt      export 11:18:55
    NOTES_c14_trail.md         etat au 11/08 19h30
    NOTES_gel_v9.md            gel pose le 11/08

`docs\JOURNAL.md` est annonce absent au demarrage -- il n existe pas.
La periode 3 de `panel_rails_trois.txt` est vide : elle demarre au patch
trail/BE du 11/08 20h14 et le panneau refuse de la lire sous dix seances.
Comparaison P2/P3 lisible vers le 27/08.

## Trois plafonds muets, une seule faute

Donner les documents au REPL a demande quatre heures pour une raison
unique, repetee trois fois : **du code qui jette des donnees sans le
dire**.

1. **Le dossier du Drive.** `G:\My Drive\ScalpEA\panels` contenait ~60
   archives orderflow triees avant les `panel_*.txt`. Elles epuisaient le
   plafond total. Corrige par `patch_repl_docs_v3` : lecture d un
   `panels\` **local**, et toute source absente est desormais ecrite.

2. **`build_system_message`.** `ai_master_repl.py` coupait a
   `static_ctx[:25000]` en dur. `panel_orderflow.txt` (20 453) passait,
   les cinq autres tombaient. Le symptome etait parfait : DeepSeek
   repondait normalement, sur un seul document, sans que rien n indique
   qu il en manquait cinq. Corrige par `patch_repl_ctx` -- 175 000, et
   la coupe s ecrit quand elle mord.

3. **Les print de `_ensure_init`.** Le 8095 lance par `Start-Process`
   survit a la fermeture de sa fenetre : sa sortie standard devient
   fermee, et tout `print` leve `I/O operation on closed file`. Ces
   print-la etaient places AVANT `_inited = True`, donc l initialisation
   n aboutissait jamais et **toutes** les questions echouaient, pour
   toujours. Corrige par `patch_repl_print` : un `print` de module,
   dans `repl_web` seulement, qui ne peut pas lever.

Le troisieme est le plus instructif : mon propre correctif du deuxieme
(un `print` d avertissement) portait exactement la meme faute et a casse
la premiere question. Un diagnostic ne doit jamais pouvoir tuer ce qu il
diagnostique -- d ou `patch_repl_ctx_v2`, ou le message part **dans le
contexte**, la ou le modele peut le citer, plutot que sur une console
qu on ne peut meme pas ecrire.

`diag_repl_ask.py` rejoue `ask()` avec la sortie fermee et imprime la
trace sur stderr. C est lui qui a tranche : les deux passes reussissaient,
donc le probleme n etait pas `ask()` mais le **moment** de
`_ensure_init()`.

## Sauvegardes

    council_shadow.py.bak-20260812-091341   avant v2
    council_shadow.py.bak-20260812-102849   avant v3
    council_shadow.py.bak-20260812-104818   avant v4
    repl_web.py.bak-20260812-094009         avant patch_repl_docs_v2
    repl_web.py.bak-20260812-112007         avant patch_repl_docs_v3
    ai_master_repl.py.bak-20260812-114016   avant patch_repl_ctx
    ai_master_repl.py.bak-20260812-115705   avant patch_repl_ctx_v2
    repl_web.py.bak-20260812-130832         avant patch_repl_print

## Ce qui reste ouvert

- **deepseek raw** : le user a demande de l integrer. Recommandation
  contraire, non tranchee : `render_snapshot_page()` ne fait que redonner
  l instantane MT5 que le REPL recoit deja a chaque question. L ajouter
  doublerait le cout en jetons sans rien apprendre de neuf.
- Le panneau rails 3 periodes n est pas encore dans la page 8095 --
  seulement exporte en texte pour le REPL. Le panneau existant porte des
  `trades` sans champs rails, il faut un module qui relise
  `docs\rails_trades\tickets_rails.jsonl` lui-meme.
