# mistakes.md — ce que j'ai cassé, et ce que ça a appris

Ce fichier est tenu par Claude. **Chaque erreur y est écrite le jour
même**, qu'elle ait été rattrapée ou non : une erreur interceptée par
un garde-fou compte autant qu'une erreur en production, parce que le
garde-fou aurait pu manquer.

Une entrée ne sert à rien si elle dit seulement « j'ai fait une
faute ». Chacune porte donc cinq choses :

1. **ce que j'ai fait** ;
2. **le raisonnement faux** qui m'y a conduit — c'est la partie utile,
   parce que c'est elle qui se répète ;
3. **la conséquence réelle**, sans l'adoucir ;
4. **le correctif** ;
5. **la règle** qui en découle, écrite pour être vérifiable.

Ce n'est pas un journal de contrition. Une erreur bien décrite est un
garde-fou gratuit ; une erreur résumée en « attention à X » ne sert à
personne.

---

## Les règles nées de ces erreurs

À relire avant d'écrire un patch. Chacune vient d'un incident daté,
plus bas.

- **Un garde-fou doit vérifier la portée où l'on écrit**, pas
  l'existence d'un nom quelque part dans le fichier. `ast.walk`
  descend dans les fonctions.
- **Le code généré n'emprunte aucun nom au module cible.** Builtins
  uniquement, ou import local dans la fonction générée.
- **Avant de toucher une fonction partagée, énumérer ses appelants.**
- **Une ancre se pose sur un NOM, jamais sur une valeur** — sinon la
  marche arrière est impossible dès la première application.
- **La marche arrière s'imprime depuis ce qu'on a lu**, jamais depuis
  une constante écrite d'avance.
- **`ast.parse` dit que ça compile, pas que ça marche.** Tout patch
  passe sur un banc avec des données fabriquées avant d'approcher un
  fichier vivant.
- **Un garde-fou se teste contre le changement qu'il garde**, sinon
  c'est un troisième bug qui bloque les deux autres.
- **Le nom d'un champ se lit dans les données (`--schema`), jamais
  dans le code qui les écrit.**
- **Une attente fixe n'est pas une vérification.** On boucle jusqu'à
  la condition, avec un délai maximum et un message si on l'atteint.
- **Une colonne dont le signe change de sens doit le dire dans sa
  propre sortie.**
- **Deux constantes jumelles finissent toujours par diverger en
  silence.** Une seule source, toujours.
- **Une commande de diagnostic filtre avant d'afficher**, et met en
  premier les parties qui ne peuvent pas échouer.
- **Un bloc de code EST une commande.** Ce qui n'est pas exécutable se
  cite en ligne. Relire le bloc, et son dernier caractère.
- **Un service supervisé s'arrête, il ne se relance pas.** Chercher qui
  le supervise, attendre son retour, vérifier que le pid a changé.
- **Un panneau = une route + un bouton.** L'un sans l'autre vaut zéro.
- **Sur une interface qui existe, on recopie ; on ne conçoit pas.**
  Extraire la convention du fichier, la rendre à l'identique.
- **Une limite d'affichage n'est pas un résultat.** Pour prouver une
  absence : compter d'abord, afficher ensuite. Jamais `-First N`.
- **Un verdict se lit dans la colonne qu'il commente.** S'il est
  calculé par un chemin que le tableau ne montre pas, il finira par
  dire le contraire du tableau — et personne ne le verra. La colonne
  qui décide doit être imprimée.
- **Une branche par défaut n'est pas un fourre-tout.** « Rien de
  mesurable » et « rien de significatif » sont deux réponses
  différentes ; les faire tomber dans le même `else` produit une
  phrase fausse au-dessus de chiffres justes.
- **Sous le plancher de cotation, une statistique mesure l'arrondi.**
  Un mouvement médian d'un tic n'est pas un petit mouvement, c'est
  l'absence de mesure.
- **Avant d'écrire un outil, chercher s'il existe.** Poser la question
  coûte trente secondes ; le réécrire coûte une matinée, et le pire est
  qu'on ne s'en aperçoit pas. `PROTOCOLE.md` est là pour ça.
- **Une plage de dates n'est pas une couverture.** C'est une
  enveloppe, pas une densité — mesurer ce qu'elle contient avant
  d'annoncer un effectif. Sur des futures, un contrat n'est liquide que
  sur son trimestre.
- **Un horizon en jours se compte en SÉANCES**, jamais en jours
  calendaires — et une séance se définit par sa densité de barres, pas
  par sa présence dans une liste de dates.
- **Un effectif non monotone est un bug.** Si l'horizon du milieu a
  moins de points que ses deux voisins, on compte mal ; ce n'est pas un
  manque de données.
- **Quand on corrige un seuil inventé, chercher ses frères** dans le
  même fichier avant de refermer.
- **Une règle notée mais appliquée à un seul endroit n'est pas une
  règle**, c'est une anecdote — la reporter dans cette liste fait
  partie du correctif.
- **Toujours afficher ce qu'un filtre GARDE**, pas seulement ce qu'il
  jette. Un seuil d'occurrences sélectionne les événements *fréquents*,
  pas les *importants* — l'inverse de ce qu'on croit.
- **Vérifier qu'un témoin reste un témoin.** Si les fenêtres
  d'événement couvrent une fraction importante de la période, la
  comparaison est devenue une comparaison de périodes.

---

## 14/08/2026 21:18 — j'ai fait tomber le panneau

**Ce que j'ai fait.** `patch_repl_reasoner_plafond.py` (v1) a écrit
`_os.environ.get(...)` au niveau module de `repl_web.py`. La page est
morte au chargement :

```
repl_web error: name '_os' is not defined
```

**Le raisonnement faux.** J'avais écrit un garde-fou pour savoir sous
quel nom `os` était importé, et il utilisait `ast.walk`. **`ast.walk`
descend dans les corps de fonctions.** Il a trouvé `import os as _os`
à l'intérieur de `_ensure_init()` et en a conclu que `_os` existait au
niveau module. Il n'y existe pas.

Le contrôle était juste dans son intention et faux dans sa portée : il
vérifiait que `os` était importé **quelque part**, pas **là où
j'écrivais**.

**La conséquence.** Panneau mort jusqu'à restauration depuis
`repl_web.py.bak-20260814-211842`. La restauration a aussi annulé le
patch qu'elle était censée sauver — il a fallu tout refaire.

**Le correctif.** La fonction générée importe `os` elle-même
(`import os as _o`). Il n'y a plus rien à deviner. Vérifié sur trois
cas : `os` au niveau module, `os` dans une fonction seulement, `os`
absent.

**La règle.** Un garde-fou vérifie la portée où l'on écrit. Et mieux
encore : le code généré n'emprunte aucun nom au module cible.
`patch_route_profils.py`, écrit le même soir, n'utilise que `open`,
`Exception`, `str` et `len` — il n'y a rien à vérifier, donc rien à se
tromper.

---

## 14/08/2026 — une docstring qui affirmait ce qu'elle n'avait pas vérifié

**Ce que j'ai fait.** `patch_repl_ctx.py` proposait de relever
`REPL_CTX_MAX`, et sa docstring affirmait que `build_system_message`
n'était appelée que par le REPL.

**Le raisonnement faux.** Je l'avais déduit du nom de la fonction.

**La conséquence.** Aucune : le patch n'a pas été appliqué tel quel.
Mais **deux traders vivants** appellent cette fonction. Relever la
constante aurait changé leur contexte pendant le gel — exactement ce
que le gel interdit.

**Le correctif.** Un paramètre optionnel `ctx_max=None` ; seul
`repl_web` passe une valeur. Les traders sont inchangés par
construction, pas par espoir.

**La règle.** Avant de toucher une fonction partagée, énumérer ses
appelants. Une docstring n'est pas un lieu où l'on suppose.

---

## 14/08/2026 — un patch qui bloquait sa propre marche arrière

**Ce que j'ai fait.** `patch_docs_plafond.py` portait ses ancres avec
les valeurs littérales (`_DOCS_MAX = 200000`). Relancé pour revenir en
arrière, il refusait : l'ancre ne correspondait plus, puisqu'il venait
lui-même de la changer.

**Le raisonnement faux.** J'avais confondu « idempotent » et
« réversible ». Un patch qui refuse de se rejouer n'est pas sûr, il
est coincé.

**Le correctif.** Ancres par **nom** :
`^_DOCS_MAX\b[ \t]*=[ \t]*(\d+)[ \t]*$`. Et `[ \t]*` et non `\s*` —
`\s` mange les retours à la ligne, ce qu'un contrôle de nombre de
lignes a heureusement attrapé.

**La règle.** Une ancre se pose sur un nom. Une marche arrière se teste
dans les deux sens avant livraison.

---

## 14/08/2026 — une marche arrière annoncée en dur

**Ce que j'ai fait.** `patch_repl_ctx_v3.py` imprimait
`Marche arriere : --web 175000`, écrit en dur.

**La conséquence.** Vrai à la première application, faux à toutes les
suivantes. Le message conduisait à restaurer une valeur qui n'était
pas celle d'avant.

**Le correctif.** Imprimer la valeur **lue** avant modification.

**La règle.** Ce qu'on affiche vient de ce qu'on a lu, jamais d'une
constante écrite d'avance. Même motif que l'entrée suivante.

---

## 14/08/2026 — deux constantes jumelles, une seule levée

**Ce que j'ai fait (le matin).** `patch_council_plafond` a porté
`COUNCIL_MAX_TOKENS` à 60 000. **Et (l'après-midi)**
`patch_repl_modeles` a introduit un dictionnaire `REPL_MAX_TOKENS`
propre au REPL, avec `8000` **écrit en dur** — et c'est lui que la
ligne d'appel consultait.

**La conséquence.** Le REPL n'a jamais vu les 60 000. À 21:10 :
`(vide / completion=8000/8000 PLAFOND ATTEINT)` — 130 secondes de
raisonnement, réponse vide. Sur un modèle de raisonnement, `max_tokens`
couvre le raisonnement **et** la réponse.

Le commentaire laissé au-dessus disait : « 8000 est la valeur de
`COUNCIL_MAX_TOKENS` ; on revient simplement au défaut ». C'était exact
à la minute où il a été écrit, et faux l'heure suivante. **Rien, dans
l'un ou l'autre fichier, ne pouvait le montrer.**

**Le correctif.** Suppression de la jumelle : la valeur se règle par
variable d'environnement avec un défaut explicite. Une seule source.

**La règle.** Deux constantes jumelles divergent toujours, et le
commentaire qui les relie vieillit sans prévenir. Le même motif est
revenu le soir même, en plus petit : la légende du dégradé de
`carte_html.py` était peinte en Python pendant que les cases l'étaient
en JavaScript — une couture visible au centre de l'échelle. Corrigé
en faisant peindre la légende par la fonction des cases.

---

## 14/08/2026 — une erreur que `ast.parse` ne pouvait pas voir

**Ce que j'ai fait.** Dans `patch_section7_cassure.py`, écrit :

```python
"a commence. C est un choix." % a.cassure
```

Le `%` s'était lié à une chaîne sans marqueur de format.

**La conséquence.** `TypeError` à l'exécution. Le patch compilait
parfaitement. Seul un passage sur données fabriquées l'a trouvé.

**La règle.** `ast.parse` dit que ça compile, pas que ça marche. Tout
patch passe sur un banc avec des données synthétiques avant d'approcher
un fichier vivant. C'est ce banc qui a validé
`patch_route_profils.py` : fichier absent, fichier présent, routes
voisines intactes, marche arrière identique à l'octet près.

---

## 14/08/2026 — un garde-fou qui était lui-même faux

**Ce que j'ai fait.** Dans le même patch, un contrôle attendait que
`table4` apparaisse **une fois de plus** après modification.

**Le raisonnement faux.** Le nouveau code appelle `table4` **dans une
boucle** : le nombre d'occurrences textuelles ne change pas.

**La conséquence.** Un patch correct refusait de s'appliquer. Trois
bugs valent mieux que deux, mais celui-là bloquait les deux autres.

**Le correctif.** Un contrôle AST sur la présence de la boucle
`CAMPS7`.

**La règle.** Un garde-fou se teste contre le changement qu'il garde.
Compter des occurrences textuelles ne vaut que si la forme du code ne
change pas.

---

## 14/08/2026 — un nom de champ deviné dans le code

**Ce que j'ai fait.** Écrit un lecteur qui cherchait `mom` dans les
enregistrements de trajectoire du gap. Le champ s'appelle `self_mom`.

**La conséquence.** Aucune, parce que `--schema` a été passé sur les
3 610 enregistrements avant toute lecture de chiffre. Sans lui, la
cellule serait revenue vide et j'aurais écrit « le widening ne croise
avec rien » — une conclusion fausse, tirée d'un champ absent.

**La règle.** Le nom d'un champ se lit dans les données, jamais dans le
code qui les écrit. `--schema` d'abord, toujours.

---

## 14/08/2026 — une sauvegarde qui écrasait l'originale

**Ce que j'ai fait.** Nommé les sauvegardes `fichier.bak-AAAAMMJJ-HHMMSS`.

**La conséquence.** Deux exécutions dans la même seconde écrasaient la
sauvegarde de la première — c'est-à-dire l'original.

**Le correctif.** Suffixe incrémental tant que le nom existe.

**La règle.** Un nom de sauvegarde qui peut entrer en collision n'est
pas une sauvegarde.

---

## 14/08/2026 — une colonne qui se lisait à l'envers

**Ce que j'ai fait.** Publié une matrice avec une colonne `apport`
dont le signe s'interprète **à l'envers pour les règles
d'abstention** : un apport négatif y est une bonne nouvelle. Je ne
l'avais écrit nulle part.

**La conséquence.** Le REPL a construit trois « interdits » I1 à I3 à
l'envers, en toute logique, à partir de ma sortie.

**Le correctif.** L'avertissement est imprimé dans la table elle-même.

**La règle.** Une colonne dont le signe change de sens selon la lecture
doit le dire dans sa propre sortie. Ce n'est pas au lecteur de le
savoir.

---

## 14/08/2026 23:05 — une attente fixe prise pour une vérification

**Ce que j'ai fait.** Écrit un redémarrage qui arrête le panneau, attend
`Start-Sleep -Seconds 4`, puis relance.

**Le raisonnement faux.** J'ai supposé qu'un délai raisonnable valait
une condition. Ce n'est pas une vérification, c'est un pari.

**La conséquence.** Rattrapée : j'avais ajouté un contrôle qui refuse
de relancer tant que 8095 ou 18095 est écouté, et il a dit
`KO : 2 ecouteur(s) encore, rien relance`. Rien n'a été lancé
par-dessus un processus vivant. Sans ce contrôle, on retombait sur le
`EXIT (anti multi-bind)` d'une heure plus tôt, ou pire, sur deux
panneaux qui se disputent le port.

**Le correctif à écrire.** Une boucle qui attend que le port soit
rendu, avec un délai maximum, et qui dit au bout de combien de temps
il ne l'a pas été — au lieu d'un nombre choisi au jugé.

**La règle.** Une attente fixe n'est jamais une vérification. On boucle
jusqu'à la condition ou jusqu'à l'échec, et on dit lequel des deux est
arrivé.

**Et la vraie erreur était en amont, vue seulement à 23:23.** J'ai
écrit trois redémarrages manuels d'un service **qui a un
superviseur**. Il le relance tout seul dans les secondes qui suivent
l'arrêt. Les trois fois, j'ai perdu la course :

```
23:23:03  arret de pid 11752
23:23:05  apres 2 s : libre        <- ma boucle, corrigée, dit vrai
23:23:05  mon lancement demarre
23:23:06  [PA-PANEL] port-token 18095 deja tenu -> EXIT (anti multi-bind)
```

La boucle corrigée n'y pouvait rien : entre le constat et le bind, le
superviseur avait repris la main. **La garde du panneau a tenu à chaque
fois** — c'est elle qui a évité deux panneaux sur un port, pas moi.

**La règle.** Avant de relancer quoi que ce soit sur cette machine,
chercher qui le supervise. Un service supervisé s'arrête, il ne se
relance pas : on attend son retour et on vérifie que **le pid a
changé**. Écrit dans `NOTES_panneaux.md`, procédure en deux temps.

---

## 14/08/2026 23:08 — une route sans bouton

**Ce que j'ai fait.** Ajouté la route `/profils` au panneau, annoncé
que la carte était « sur le 8095 », et livré une adresse à taper à la
main. Aucun bouton dans la barre.

**Le raisonnement faux.** J'ai traité « servir une page » et « rendre
une page accessible » comme la même tâche. Sur ce panneau ce sont deux
choses : la route répond, le bouton la rend trouvable — et un panneau
qu'il faut savoir nommer pour l'atteindre n'existe pas.

**Le rappel de l'utilisateur.** « Un panel = un bouton pour y accéder,
et c'est toujours pareil, ne perdons plus de temps à refaire dix fois
les choses. »

**Ce que j'aurais dû lire avant d'écrire.** La convention était déjà
dans le fichier, en trois lignes :

```
onclick="showTab('x60onset')"                  color:#3fb950   onglet interne
onclick="window.open('/rails_cycle','_blank')" color:#58a6ff   route servie
```

**Le correctif.** Le bouton, sur le modèle exact de la ligne 4361 —
`window.open` et bleu, puisque c'est une route et non un onglet. Et
`NOTES_panneaux.md`, qui décrit la convention une fois pour toutes :
les deux façons d'ouvrir, le code couleur, l'endroit où s'insère un
bouton.

**La règle.** **Un panneau = une route + un bouton.** Livrer l'un sans
l'autre n'est pas la moitié du travail, c'est zéro. Et avant d'ajouter
quoi que ce soit à une interface existante, inventorier la convention
qui s'y trouve déjà plutôt que d'en inventer une.

**Et ce n'était encore que la moitié, 23:32.** La page ouverte, il
manquait tout le reste du châssis : **aucun retour vers le panneau,
aucun en-tête, aucun bouton copier**. Une page servie par le panneau
est une page *du* panneau — elle doit permettre d'en revenir et de
copier son contenu, comme toutes les autres.

Le bouton copier n'est pas décoratif sur cette machine : c'est par lui
que le contenu part dans le REPL. Une page sans bouton copier est une
page dont les chiffres ne peuvent pas être discutés.

**La règle complète, donc.** Un panneau = **une route + un bouton dans
la barre + un châssis** : retour vers `/`, en-tête qui dit ce qu'on
regarde et de quand ça date, et bouton copier qui rend le contenu en
**texte** — pas en HTML, puisque la destination est un modèle.

**Et une troisième fois, 23:52 : la navigation.** Le châssis livré ne
permettait de revenir qu'au tableau de bord. J'ai d'abord répondu que
les 177 autres boutons étaient des onglets internes, donc non
liables — puis j'ai vérifié avant de m'y tenir : `price_action.py`
sert en réalité **environ 150 routes** hors `/api/`. Presque chaque
panneau a son adresse. Mon affirmation était fausse et je l'aurais
tenue pour vraie sans ce contrôle.

La barre est donc **lue dans `price_action.py` à la génération**, pas
écrite en dur : une liste figée divergerait à la première route
ajoutée, et c'est le motif des deux constantes jumelles qui a déjà
coûté une soirée.

**Et une quatrième fois, 00:05 : j'ai inventé la barre.** Livrée
enfin, la navigation était **la mienne** — tout en bleu, mes tailles,
mon ordre alphabétique — au lieu de celle du tableau de bord, qui a
ses libellés, ses couleurs et son ordre depuis des mois.

Le reproche a été net : *« pfiooouuu tu as changé les couleurs et
police… mets juste le header identique aux autres panels, c'est rien,
ça prend 2 secondes, ça fait 20 min qu'on est dessus »*. Et c'est
exact : ça prenait deux secondes **à condition de recopier au lieu de
concevoir**.

**Le raisonnement faux.** J'ai traité « ajouter une navigation » comme
un problème de design. C'en était un de **transcription**. Il existait
déjà 178 boutons, avec leurs couleurs — la seule bonne réponse était
de les relire et de les rendre tels quels.

**Le correctif.** `onglets()` extrait les divs de la barre depuis
`price_action.py` : libellé, couleur, ordre. Chaque bouton dont le
libellé correspond à une route servie pointe dessus ; les autres, qui
sont des onglets internes, renvoient au tableau de bord. Rien n'est
écrit en dur, donc la barre suivra la vôtre sans qu'on y pense.

**La règle.** **Sur une interface qui existe, on recopie ; on ne
conçoit pas.** Avant d'ajouter un élément visuel à un outil déjà en
service, extraire la convention du fichier et la rendre à l'identique.
Un deuxième style, même joli, est un deuxième style à maintenir — et
il se voit immédiatement.

Trois tours pour livrer une barre de navigation : d'abord sans, puis
inventée, puis recopiée. Les deux premiers étaient évitables en lisant
d'abord.

**Le piège technique qui va avec.** `navigator.clipboard` exige un
contexte sûr. La page est servie en `http://` sur un nom de machine
(`vmi654074:8095`), donc **l'API est absente** — un bouton copier
écrit naïvement ne fait rien du tout, sans erreur visible. Il faut la
zone de texte cachée et `document.execCommand("copy")`, qui fonctionne
dans les deux cas.

---

## 14/08/2026 — deux commandes de diagnostic mal écrites

**La première** interrogeait les connexions du port 8095 sans filtrer
sur l'état : elle a déversé **1 182 lignes `TimeWait`** et poussé hors
écran la seule information demandée.

**La seconde** faisait `(Select-String ...).Matches` sur un motif qui
ne correspondait à rien — ma regex cherchait des guillemets doubles là
où le code utilise autre chose. L'objet était vide, `.Matches` a levé
une exception, **et elle a emporté la seconde moitié de la ligne**, y
compris les compteurs qui, eux, auraient fonctionné.

**La règle.** Une commande de diagnostic filtre avant d'afficher, et
place en premier les parties qui ne peuvent pas échouer. Sur cette
machine, une sortie illisible coûte un aller-retour complet.

---

## 14/08/2026 — un bloc Python collé dans PowerShell

**Ce que j'ai fait.** Affiché un bloc de code Python dans une réponse
où l'utilisateur attendait une commande. Il l'a collé dans PowerShell.

**La conséquence.** Un mur d'erreurs `CommandNotFoundException`. Sans
gravité, mais entièrement de ma faute : sur cette machine, ce qui est
présenté comme un bloc se colle dans un terminal.

**La règle.** Une réponse contient **une** commande, exécutable telle
quelle dans PowerShell. Le reste est de la prose.

**Récidive à 23:15.** Une commande de diagnostic s'est terminée par un
`</parameter>` parasite — un fragment de mon propre outillage tombé
dans le bloc. Elle a été collée telle quelle, et
`Format-Table -AutoSize</parameter>` a fait échouer la moitié de la
ligne. Un bloc de code est un contrat : ce qu'il contient part dans un
terminal sans être relu. **Relire le bloc caractère par caractère
avant d'envoyer**, en particulier son dernier caractère.

**Troisième récidive, 01:00 : `python -c` sur cette machine.** J'ai
envoyé une commande de la forme
`python -c 'import json; ... open(r"chemin", ...)'`. PowerShell passe
le contenu de l'apostrophe au programme, **mais l'analyseur
d'arguments de Windows retire les guillemets doubles internes avant
que Python ne les voie** : `r"docs\..."` est arrive comme
`rdocs\...` et Python a rendu
`SyntaxError: unexpected character after line continuation character`.
Deux tentatives, deux echecs identiques.

**La regle, propre a cette machine.** `python -c` avec du code cite
est inutilisable ici. Soit on ecrit du **PowerShell pur** (`Get-Content
-TotalCount 1 | ConvertFrom-Json` fait le meme travail), soit on ecrit
un fichier `.py` et on le lance. Ne jamais faire dependre une commande
de la survie de guillemets a travers deux analyseurs.

**Deuxième récidive à 23:19.** J'ai montré la ligne HTML 4361 dans un
bloc de code pour la commenter. Elle a été collée dans PowerShell :
`The term '<' is not recognized`. Un bloc de code, sur cette machine,
**est** une commande — c'est le contrat, quelle que soit mon
intention. Du contenu qui n'est pas exécutable se cite en ligne, ou
dans un bloc explicitement annoncé comme « à ne pas coller ». Trois
salves d'erreurs en une soirée pour une seule règle de mise en forme.

---

## 14/08/2026 23:45 — j'ai lu une troncature comme une absence

**Ce que j'ai fait.** Cherché `_DOCS_MAX` avec
`Select-String -Path *.py ... | Select-Object -First 10`. Les dix
lignes rendues venaient toutes de mes propres scripts de patch.
J'en ai conclu que la constante **n'existait plus** dans
`repl_web.py`, donc que la restauration de 21:18 avait effacé trois
patches.

**Le raisonnement faux.** Il y avait exactement dix lignes de scripts
de patch **avant** celles de `repl_web.py`, par ordre alphabétique de
nom de fichier. `-First 10` les a toutes consommées. Une liste tronquée
n'est pas une liste vide, et une absence dans un extrait n'est pas une
absence dans le fichier.

**La conséquence.** Cinq allers-retours de diagnostic construits sur
une prémisse fausse — recherche du vrai chargeur, lecture de
`_gather_static_context`, hypothèse d'un balayage de dossier, puis
d'une liste en dur. Tout ça pour découvrir en appliquant que
`patch_repl_docs_v2` répondait « garde déjà posée », que `_DOCS_MAX`
valait déjà 400 000 et que les 19 documents étaient déjà lus.

Une demi-heure de la nuit de quelqu'un.

**La règle.** **Une limite d'affichage n'est pas un résultat.** Quand
une recherche sert à prouver une ABSENCE, ne jamais la tronquer :
compter d'abord (`.Count`), et n'afficher qu'ensuite. Un `-First N` a
sa place quand on cherche un exemple, jamais quand on conclut « ça
n'existe pas ».

---

## 15/08/2026 00:35 — un document livre a un modele sans ses garde-fous

**Ce que j'ai fait.** Installe un document relu a chaque question du
REPL, avec un en-tete qui dit *« s'il contredit un panneau plus ancien
du contexte, c'est lui qui fait foi »* — et rien d'autre.

**Ce qui s'est passe dans la question suivante.** Le modele a lu la
carte, trouve la seule cellule post-cassure qui franchit le seuil, et
ecrit : *« c'est exactement le setup que je dois jouer quand les
entrees rouvrent lundi : suivre l'US100 contre US30/US500 […] c'est le
trade a surveiller »*.

**La carte ne contient aucune direction.** Elle agrege les BUY et les
SELL, elle ne connait aucune paire, et la ligne en question est
calculee sur `actif TOUS`. `PASALIGNE` veut dire « les trois indices
ne sont pas alignes », pas « acheter le leader contre les autres ». Le
passage de l'un a l'autre est une invention complete, et elle est
arrivee **des la premiere question** posee sur le document.

**Le raisonnement faux — le mien.** J'ai traite l'en-tete comme une
etiquette de fraicheur. C'est une etiquette d'AUTORITE : « c'est lui
qui fait foi » invite a s'en servir, et je n'ai rien ecrit sur ce
qu'il ne dit pas.

**La regle.** **Un document remis a un modele porte ses garde-fous
dans le document.** Pas dans la conversation, pas dans le fichier
d'a cote : dans l'en-tete meme. Au minimum, ce que les colonnes ne
contiennent pas (ici : aucune direction, aucun actif), que le maximum
d'une enumeration n'est pas une regle, et quelles contraintes
exterieures s'appliquent (ici : le gel interdit tout changement de
parametre).

Le contexte des autres panneaux est du texte descriptif ; celui-ci est
un classement trie par performance. **Un classement invite a choisir
son sommet.** C'est precisement pour ca qu'il fallait l'accompagner.

---

## 15/08/2026 00:40 — j'ai agrege les actifs pour economiser un fichier

**Ce que j'ai fait.** Sorti la carte texte du REPL en `--actif TOUS`,
en ecrivant que les decoupes par actif « divisent l effectif par trois
pour un echantillon qui ne suit deja pas, et quadrupleraient le
fichier pour du bruit ».

**Ce que l utilisateur a vu, lui, sur trois graphiques.** Le 13/08 les
trois indices cassent leur range ; **un seul tient**. Le US100 reste
au-dessus de sa cassure, le US30 rend tout, le US500 est entre les
deux. Un changement de regime propre a un actif — et aucun de nos
outils ne pouvait le produire.

**Le raisonnement faux.** J'ai traite l agregation comme une economie
de place. C est une decision de mesure : **l agregation est faite pour
lisser, et un decrochage isole est exactement ce qu elle lisse.**
Trois actifs moyennes ensemble ne peuvent pas montrer que l un d eux
diverge.

**Et il y avait pire en amont.** Toute l analyse repose sur UNE date
de cassure, le 5 aout, appliquee aux trois actifs et choisie a l oeil.
Si un actif change de regime a une autre date, sa periode « depuis »
melange deux regimes et la reference commune ne decrit plus personne.
Cinq hypotheses datees reposent sur ce decoupage.

**La regle.** **Une agregation est une hypothese, pas une commodite.**
Agreger des actifs suppose qu ils partagent le regime ; agreger des
periodes suppose qu on sait ou elles se separent. Les deux doivent
etre ecrites comme des hypotheses testables, pas glissees dans un
argument de taille de fichier.

Consigne dans HYPOTHESES.md sous « Une reserve qui pese sur H22 a
H26 », avec les trois mesures a faire avant les echeances.

---

## 14/08/2026 — deux affirmations fausses, dites avec assurance

**La première.** J'ai attribué le `prompt=205719` du REPL à
l'historique de conversation. Une remise à zéro a montré 206 323
ensuite : l'historique n'y était pour rien.

**La seconde.** J'ai repris à mon compte « le flux SierraChart est
différé de dix minutes, donc aucune règle d'orderflow n'est
exploitable ». C'est faux tel quel : un flux retardé ne supprime pas
le filtre, **il définit la variable** — à l'instant T on connaît
l'état à T−10, et cette valeur est disponible en direct. C'est
l'utilisateur qui a dû me le faire remarquer. H20 en est née.

**La règle.** Une explication plausible n'est pas une mesure. Quand je
ne sais pas, l'écrire ; quand une mesure existe, la faire avant de
conclure.

---

## 14/08/2026 — j'ai abrégé au lieu de cartographier

**Ce que j'ai fait.** Devant une carte de 23 040 cellules dont presque
aucune n'atteint son seuil, j'ai commencé à livrer un verdict — « tout
sera gris » — au lieu de l'outil.

**Le rappel de l'utilisateur.** « Notre rôle n'est pas d'abréger mais
au contraire d'établir une croisée des chemins pour obtenir un frontier
model qui est jouable, mais pas forcément en visant que le
suroptimisé. »

**Le correctif.** La frontière de Pareto : à chaque effectif
atteignable, le meilleur écart disponible. Un profil à 400 signaux et
+4 € est plus jouable qu'un profil à 60 signaux et +25, et aucun des
deux ne « passe » un seuil.

**La règle.** « Rien ne passe le seuil » est une information, pas une
conclusion. Le livrable est la carte du compromis, pas le verdict.

---

## 17/08/2026 — quatre versions d'un verdict qui contredisait sa table

**Ce que j'ai fait.** `bruit_par_actif.py` imprime une colonne de
ratios de variance par horizon, puis une phrase qui la résume. Trois
versions de suite, la phrase a dit le contraire de la colonne.

- **v1** ne cherchait qu'un franchissement de 1 **vers le haut**. Les
  trois actifs descendent : rien trouvé, branche par défaut, verdict
  « les mouvements persistent » imprimé sous une colonne allant de
  1,06 à 0,76.
- **v2** cherchait dans les deux sens, mais exigeait un point
  significativement **au-dessus** de 1 suivi d'un point
  significativement en dessous. Or les courbes *partent* de 1 : aucun
  point n'est significativement au-dessus, donc aucun couple ne
  qualifiait, et la même branche par défaut reprenait la main avec la
  même phrase fausse. Une condition plus stricte n'est pas une
  condition plus prudente : elle rend juste la mauvaise réponse plus
  souvent.
- **v3** prenait le premier horizon à plus d'une erreur type de 1.
  Elle désignait 0,5 min pour US30 et US500 — où le mouvement médian
  du US500 vaut **0,25 point, soit un tic**. Le tampon proposé valait
  un tic de cotation, et la RÉSERVE imprimée dix lignes plus bas dans
  le même fichier disait déjà de ne pas lire cet horizon-là. J'avais
  écrit le garde-fou et je ne l'avais pas branché.

**Ce que ça aurait coûté.** Ce tampon devait entrer dans la définition
de cassure de `breakout_range.py`. Un tampon d'un tic, c'est un tampon
nul : on aurait « ajouté un filtre de bruit » qui ne filtre rien, et
mesuré ensuite l'effet du filtre.

**Le correctif (v4).** Trois changements, dont deux sont des aveux :

1. Une colonne **`z`** est imprimée à côté de VR. Le verdict ne peut
   plus être calculé par un chemin invisible : la valeur qui décide est
   sur la ligne.
2. Les horizons dont le mouvement médian tient en **trois tics** sont
   marqués `plancher` et exclus du verdict. Le tic n'est pas déclaré en
   dur, il est **lu dans les données** (plus petit écart non nul
   représentant au moins 2 % des écarts).
3. L'écart doit être **confirmé par l'horizon suivant** — en balayant
   huit horizons on en trouve toujours un — et on retient non pas le
   premier mais le **plus grand vers le bas**, l'échelle où le retour
   en arrière est le plus net. C'est ça, la question posée.

**Ce qui l'a attrapé.** Trois journées synthétiques : une marche au
hasard pure, une série sous le plancher, une série à retour en
arrière. La marche au hasard a rendu « indiscernable », la série sous
le plancher a rendu « VR reste à moins d'une erreur type de 1 » —
**faux, sa colonne allait de 0,47 à 0,18**. Quatrième phrase contredite
par sa propre table, attrapée au banc et pas en production, d'où la
branche NON MESURABLE. La branche PERSISTE, elle, n'avait jamais été
exécutée : je l'ai déclenchée avec une quatrième série avant de
déposer.

**Les règles.** Un verdict se lit dans la colonne qu'il commente. Une
branche par défaut n'est pas un fourre-tout. Sous le plancher de
cotation, une statistique mesure l'arrondi.

---

## 17/08/2026 — « 90 cycles = 15 minutes », et c'était faux depuis le début

**Ce que j'ai fait.** Tous mes outils sur `cycles.jsonl` définissent une
fenêtre en **nombre de cycles**, converti en minutes avec un pas médian
de 10 s : `k = round(minutes * 60 / pas_median)`. Quatre fichiers
reposent dessus — `breakout_range.py`, `bruit_par_actif.py`,
`rotation_tech_value.py`, `autopsie_choc.py`.

**Le raisonnement faux.** J'ai pris une **médiane** pour une
**garantie**. Un pas médian de 10 s dit que la moitié des intervalles
font 10 s. Il ne dit rien des autres, et surtout rien des trous.

**Comment ça s'est vu.** L'autopsie du 12/08 a imprimé sa propre
réfutation : ancre à `13:22:22`, ligne marquée `<-- fin de fenetre`
(90 cycles plus loin) à **`15:22:24`**. Deux heures annoncées comme
quinze minutes. Le compte de lignes était juste ; la durée, fausse. Je
ne l'ai vu que parce que la trajectoire imprimait les horodatages —
si j'avais affiché des indices, ça passait.

**La conséquence.** Toutes les amplitudes, tous les ratios de variance
et toutes les cassures calculés sur ces fenêtres comparent des durées
différentes entre elles. Ce ne sont pas des mesures bruitées, ce sont
des mesures **incommensurables** : deux « fenêtres de 15 min » peuvent
durer 15 min et 2 h. Les 22 événements de divergence et leur colonne
« différence » sont à jeter en l'état.

**Deux défauts frères, trouvés dans la foulée.**
- Ma colonne `debut`/`fin` prenait la première et la dernière **ligne**
  du fichier, en supposant l'ordre. Plusieurs journées affichent
  `début 23:59 / fin 23:58` : les lignes ne sont pas triées. Il faut le
  min et le max, pas le premier et le dernier.
- Aucun de mes outils ne trie par horodatage avant de mesurer.

**Le correctif.** `audit_cadence.py` d'abord — mesurer l'horloge avant
de mesurer le marché : désordre, p50/p90 des intervalles, plus grand
trou, et surtout **part utile** = durée couverte moins la somme des
trous de plus de 60 s. Ensuite, remplacer partout « fenêtre de k
lignes » par « fenêtre de W secondes », avec **rejet** de toute fenêtre
dont la durée réelle dépasse le double de W — une fenêtre qui enjambe
un trou n'est pas une fenêtre élargie, c'est une absence de mesure.

**Les règles.** Une médiane n'est pas une garantie : ce qui est
converti doit être mesuré, pas déduit. Une fenêtre se définit en temps,
jamais en nombre de lignes. Et l'ordre d'un fichier se vérifie, il ne
se suppose pas.

---

## 17/08/2026 — un seuil en dur, une heure après avoir écrit qu'il ne faut pas

**Ce que j'ai fait.** Dans `audit_cadence.py`, un trou était défini par
`d > 60.0`, écrit en dur. Sur `cycles.csv` (pas ~10 s) c'est
raisonnable. Sur `snapshots.csv`, qui tourne à **trois minutes**,
*chaque intervalle normal* dépasse 60 s : tous ont été comptés comme
trous, la part utile est sortie à **0 % sur les vingt et une
journées**, et le verdict a présenté comme inutilisable une source
parfaitement régulière.

**Le raisonnement faux.** J'ai écrit l'outil en pensant à la source que
je connaissais, et je l'ai pointé sur une source dont j'ignorais la
cadence — c'est précisément ce que l'outil était censé découvrir. Le
seuil supposait la réponse à la question posée.

**Ce qui aggrave le cas.** Une heure plus tôt, dans le même fichier,
j'avais remplacé un « finit avant 18 h » en dur par une médiane
mesurée, et j'avais écrit la règle. Je l'ai appliquée à une fonction et
pas à sa voisine. Une règle notée mais appliquée à un seul endroit
n'est pas une règle, c'est une anecdote.

**La conséquence.** Failli conclure « snapshots est inexploitable » —
alors que c'est la seule source à 21 journées, avec les prix, les
positions et le PnL. La bascule de base de travail se jouait sur ce
chiffre.

**Le correctif.** Un trou = plus de cinq fois le **pas médian de la
source elle-même**, et le seuil retenu est **affiché dans le tableau**.
Un seuil calculé qu'on ne montre pas ne vaut pas mieux qu'un seuil
inventé.

**La règle.** Quand on corrige un seuil inventé, chercher ses frères
dans le même fichier avant de refermer.

---

## 17/08/2026 — ce que j'ai refusé de faire, et pourquoi

**La demande.** « Si tu dois corriger les flux pour qu'on log toutes
les 10 s jusqu'à début septembre, fais-le si on obtient un meilleur
flux d'information. »

**Pourquoi je n'ai pas modifié le flux existant.** Je ne sais pas ce
qui cause les trous de `cycles.jsonl`, et les deux causes possibles
appellent des actions opposées :

- si la période est celle de la **boucle du moteur** — ce que suggère
  le fait que les seules journées régulières (95-100 % de part utile)
  soient les journées de **marché fermé** — alors forcer 10 s revient à
  toucher la boucle de trading pendant le gel ;
- si c'est l'**écriture** qui saute, le correctif est inoffensif.

Agir avant de savoir, c'est parier sur du code vivant. Le gel interdit
ce pari, et la demande dit « si on obtient un meilleur flux » — donc
elle porte sur le résultat, pas sur la méthode.

**Ce que j'ai fait à la place.** Un collecteur **indépendant** qui
interroge le panneau en lecture seule et écrit son propre fichier. Il
ne modifie aucun module, ne redémarre aucun service, n'approche pas
MT5. Même résultat pour nous, risque nul pour la stack.

**La règle.** Quand une demande porte sur un résultat, chercher le
chemin qui l'atteint sans toucher au vivant. Et ne jamais « réparer »
un flux dont on n'a pas identifié la cause de la panne.

---

## 17/08/2026 — j'ai réécrit un lecteur `.scid` qui existait déjà

**Ce que j'ai fait.** Passé une matinée à écrire `lire_scid.py`, à
expliquer à l'utilisateur comment régler SierraChart, et à réclamer un
export NinjaTrader avant le 22 août.

**Ce qui existait.** Une capture du dossier Drive a montré
`scid_orderflow.py` et `scid_orderflow_lu.py` (02/08), cinq versions
d'`orderflow_join`, un `orderflow_panel`, un `ScalpOrderflowExport.cs`,
deux documents `ROADMAP_` et `INSTALL_ORDERFLOW.md` — et des sorties
`scalp_orderflow_*.txt` **déposées toutes les quinze minutes**, donc un
pipeline qui tournait pendant que je demandais comment en construire un.

**Le raisonnement faux.** J'ai traité une question technique comme un
problème neuf, alors que la première chose à faire était de regarder ce
qui était déjà là. Personne ne me l'avait caché : je n'ai pas cherché.

**Le mot de l'utilisateur.** « Il ne m'est même pas venu à l'idée que
tu n'avais pas ce dont tu avais besoin car nous l'avions déjà codé. »
C'est exact, et ce n'est pas à lui d'y penser.

**Le correctif.** `PROTOCOLE.md`, qui inventorie ce qui existe, et une
consigne en tête de `CLAUDE.md` : lire ce fichier **avant** d'écrire
quoi que ce soit, et vérifier qu'une chose n'existe pas avant de la
construire.

**La règle.** Avant d'écrire un outil, chercher s'il existe. Poser la
question coûte trente secondes ; la réécrire coûte une matinée, et le
pire est qu'on ne s'en aperçoit pas.

---

## 17/08/2026 — une plage de dates n'est pas une couverture

**Ce que j'ai dit.** « YM remonte au 2 février : quatre mois de
recouvrement avec le calendrier, une centaine d'événements
mesurables. » Puis, devant 22 événements seulement, j'ai accusé le
calendrier d'être trop court et proposé de le ré-exporter depuis
janvier.

**Ce qui était vrai.** Le contrat `YMU26` est l'échéance de
**septembre**. Avant le roulement de mi-juin, le contrat actif était
`YMM26`. De février à juin, `YMU26` ne cotait presque pas. La médiane
est de **131 barres d'une minute par jour** pour une moyenne de 471 —
un future qui cote 23 h devrait en avoir 1 380. La fenêtre réellement
exploitable faisait deux mois et demi, pas six et demi.

**Le raisonnement faux.** J'ai lu `du 2026-02-02 au 2026-08-17` comme
une couverture. C'est une **enveloppe**, pas une densité. Le même
défaut que le pas médian de `cycles.jsonl` : un résumé qui cache la
distribution.

**Ce que ça aurait coûté.** Un ré-export du calendrier vers janvier —
du travail pour l'utilisateur — qui n'aurait rien changé, faute de
prix en face.

**Ce qui l'a attrapé.** Le filtre de séances, écrit pour une autre
raison, a imprimé « médiane journalière de 131 ». Le chiffre n'était
pas cherché ; il était affiché.

**La règle.** Une plage de dates ne dit rien de ce qu'elle contient.
Avant d'annoncer une couverture, mesurer la **densité** — et sur des
futures, se rappeler qu'un contrat n'est liquide que sur son
trimestre.

---

## 17/08/2026 — deux façons de mal compter les jours

**La première.** Les horizons `1j / 3j / 5j` avançaient de N jours
**calendaires**. La colonne `3j` est sortie à **zéro point** : la
plupart des publications américaines tombent mercredi ou jeudi, et
+3 jours civils atterrit le samedi ou le dimanche.

**La seconde, après correction.** J'ai compté en avançant dans la
liste des **dates présentes** dans les barres. Les futures CME rouvrent
le **dimanche soir** : quelques barres suffisent à faire entrer le
dimanche dans la liste, et +3 crans depuis un mercredi retombait sur ce
dimanche fantôme, sans barre à 12:30 UTC. Symptôme : `3j` à 10 points
quand `1j` en avait 22 et `5j` 20.

**Ce qui l'a attrapé.** L'effectif **non monotone**. Il n'existe aucune
raison légitime pour que l'horizon du milieu ait moins de points que
ses deux voisins. Ce n'était pas un manque de données, c'était un
comptage faux.

**Le correctif.** Une séance est une date portant au moins la moitié du
nombre médian de barres par jour — seuil **mesuré sur la série**,
affiché dans la sortie.

**La conséquence à retenir.** Cette seule correction a fait passer la
différence de prix à 5 jours de **+0,066 % à −0,377 %** : changement de
signe, amplitude triplée. À n = 20, ces nombres bougent avec n'importe
quelle décision de méthode — ce ne sont pas des mesures.

**Les règles.** Un horizon en jours se compte en séances. Un effectif
non monotone est un bug, pas un hasard.

---

## 17/08/2026 — un filtre qui sélectionne le contraire de ce qu'on croit

**Ce que j'ai fait.** Pour normaliser une surprise macro, j'ai exigé
au moins quatre occurrences du même événement — sinon l'écart-type se
calcule sur deux points. Statistiquement défendable.

**Ce que ça gardait.** Vérification faite en l'imprimant :

```
EIA Crude Oil Stocks Change    11 evenement(s)
Initial Jobless Claims         11 evenement(s)
```

22 = 11 + 11. **Deux séries hebdomadaires, et rien d'autre.** Zéro CPI,
zéro NFP, zéro Fed — tous à trois occurrences sur un export de trois
mois, tous écartés.

**Le raisonnement faux.** Un seuil d'occurrences ne sélectionne pas les
événements **importants**, il sélectionne les événements **fréquents**.
Ce sont deux notions opposées en macro : les poids lourds sont
mensuels, les broutilles sont hebdomadaires.

**La conséquence.** Un tableau intitulé « réaction aux surprises
macro », calculé correctement, contrôlé par un témoin apparié, et
mesurant en réalité la réaction du S&P aux **stocks de pétrole**. Je
l'aurais présenté tel quel : rien dans la sortie ne disait le
contraire.

**Ce qui l'a attrapé.** Rien d'automatique. J'affichais la liste des
événements ÉCARTÉS et pas celle des RETENUS. En lisant les écartés —
CPI, NFP, ISM, chômage, tous à 3 — j'ai déduit ce qui pouvait rester.
Le correctif est d'imprimer les deux listes.

**Et un second défaut, révélé par le premier.** Onze événements
hebdomadaires avec un horizon de 5 séances couvrent **55 séances sur
106**. Le groupe « surprises » et le groupe témoin se partagent alors
la période moitié-moitié : on ne compare plus événement contre
non-événement, mais **une moitié du calendrier à l'autre**. Le témoin
apparié cesse d'être un témoin dès que les événements sont assez
fréquents pour paver la période.

**Les règles.** Toujours afficher ce qu'un filtre GARDE, pas seulement
ce qu'il jette. Et vérifier qu'un témoin reste un témoin : si les
fenêtres d'événement couvrent une fraction importante de la période,
la comparaison est devenue une comparaison de périodes.

---

## 17/08/2026 — `c > 0` : la moitié d'une série jetée sans un mot

**La ligne.** Dans `lis_barres()`, depuis la première version :

```python
if t and c and c > 0:
    serie.append(...)
```

Écrite comme garde-fou contre une valeur de prix corrompue. Sur un
indice ou un future, elle ne fait rien : aucun prix n'est négatif.

**Ce qu'elle faisait sur `$TICK-NYSE`.** Le TICK n'est pas un prix.
C'est un compteur signé — nombre de valeurs NYSE en hausse moins celles
en baisse — qui traverse zéro plusieurs fois par heure. La garde
supprimait **toutes les barres négatives**, c'est-à-dire tous les
moments de faiblesse, et ne gardait que la moitié haussière.

Mesuré sur le banc : médiane de **91 barres par jour** au lieu de 181.
Exactement la moitié. Le tableau affichait `5426 barres` avec aplomb.

**Le second défaut, par-dessus.** Sur ce qui restait, la réaction était
calculée en `(p1-p0)/p0`. Un rendement suppose que `p0` est une
**échelle** — passer de 100 à 200, c'est +100 %. Une base de +3 sur un
oscillateur ne mesure que la petitesse de la base. D'où la sortie
réelle :

```
15min  -94 %    30min  +63 %    60min  -145 %    1j  -264 %
```

Aucun de ces nombres ne veut dire quoi que ce soit, et aucun n'a fait
planter le programme.

**Le correctif.** Garder tout ce qui est numérique, et décider de
l'unité **sur la série** : si elle traverse zéro, on mesure en points.
Pas de liste de symboles écrite à la main — la règle vaudra pour le
prochain oscillateur qu'on ajoutera sans y penser (un delta, un spread,
une différence d'indices).

**La règle.** Une garde de validité écrite pour un type de série
devient un filtre destructeur sur une autre. `c > 0` ne dit pas « prix
valide », ça dit « positif » — et il faut avoir vérifié que toutes les
séries du dossier sont positives avant de l'écrire.

---

## 17/08/2026 — trois fichiers, les mêmes barres, et un avertissement au lieu d'un correctif

**La situation.** `contrat_continu.py` écrit `of_MES-continu.csv` dans
`cartes\scid\`, à côté de `of_MESM26-CME.csv` et `of_MESU26-CME.csv`
dont il est le raccord. `reaction_evenements.py` lit tout ce qui
s'appelle `of_*.csv`. Les mêmes barres sont donc comptées deux fois :
une fois seules, une fois dans le raccord.

Vérifié sur le banc : `3982 + 6878 = 10860`, au tiers de barre près le
compte du continu. La duplication est exacte.

**Ce que ça produit.** Pas une erreur : **trois blocs de résultats**
dont deux sont des sous-ensembles du troisième. Rien ne plante, rien ne
sonne. Et devant trois tableaux, on finit par retenir celui qui parle
le mieux — la faute exacte contre laquelle tout le reste du protocole
est écrit.

**Ce que j'ai proposé d'abord.** Déplacer les deux échéances hors du
dossier à la main, puis relancer. C'est-à-dire : faire dépendre la
justesse d'une mesure d'un geste manuel à refaire à chaque
téléchargement, et que personne ne refera. Un avertissement imprimé
n'est pas un correctif ; c'est le report du correctif sur l'humain qui
lit la sortie, un jour où il sera pressé.

**Le correctif.** Le raccord porte une colonne `contrat` qui **nomme,
barre par barre, son échéance d'origine**. Les fichiers qu'il absorbe
sont donc lisibles dans les données, pas déduits d'un nom de fichier ni
d'une convention. `ecarte_doublons()` les retire de la mesure, affiche
lesquels et pourquoi, et **ne déplace ni n'efface rien**.

**La règle.** Quand un outil détecte lui-même une condition qui fausse
sa mesure, il doit l'écarter, pas la signaler. Et un dédoublonnage se
fonde sur ce que les données déclarent — ici la colonne `contrat` —
jamais sur un motif de nom de fichier.

---

## 17/08/2026 — un résultat significatif qui n'était qu'un changement d'échéance

**Le chiffre.** Après avoir corrigé le décompte des doublons, mesuré le
TICK en points, et ajouté une permutation par journée stratifiée par
jour de semaine, un seul nombre survivait sur trente-six tests :

```
MES-continu   15min delta   -1330 contrats   p = 0,0015
```

Trois symboles, douze tests chacun. Un seul sortait. C'était, au sens
strict, le premier résultat mesuré de la journée.

**Pourquoi je ne l'ai pas rapporté.** Trois faits ne collaient pas :

```
YMU26-CBOT   un seul contrat sur sa plage    rien sur 12 tests
TICK-NYSE    pas de contrat du tout          rien sur 12 tests
MES-continu  le seul qui bascule d echeance  le seul qui sort
```

Le raccord passe de `MESM26` à `MESU26` le 16 juin. Le calendrier
commence le 1er juin. Les journées témoins étaient donc prises pour
l'essentiel **avant** juin — c'est-à-dire sur l'autre échéance, avec un
autre niveau de volume. Un delta cumulé ne se compare pas d'un contrat
à l'autre.

**Ce que la correction a donné.** En bornant le témoin à la plage que
le calendrier couvre réellement : **−1330 → −267**, et plus aucune
p-value, parce que plus rien n'est testable.

**La faute de fond, et elle n'est pas dans le code.** Une journée était
déclarée « sans publication » dès qu'elle n'apparaissait pas dans le
fichier d'événements. Or le fichier commençait en juin. De janvier à
mai il n'y avait aucun événement **dans le fichier** — il y en a eu des
dizaines dans le marché. **L'absence de donnée était lue comme une
donnée d'absence.**

155 des 235 journées témoins tombaient hors calendrier. Le groupe
témoin était à ~85 % constitué de journées dont on ne savait rien, et
la comparaison n'était pas « avec surprise contre sans surprise » mais
**juin-août contre janvier-mai**, avec un changement de contrat au
milieu.

**Ce qui l'a attrapé.** Pas un contrôle automatique : la table de
composition par jour de semaine. Elle affichait 22 mercredis témoins et
21 jeudis témoins, alors que EIA tombe tous les mercredis et les
inscriptions au chômage tous les jeudis. Ces témoins-là ne pouvaient
pas exister à l'intérieur du calendrier — donc ils venaient d'ailleurs.
C'est en cherchant d'où qu'on trouve le reste.

**Les règles.** Absence de donnée n'est pas donnée d'absence : un
témoin doit être une journée **vérifiée** sans événement, dans une
plage **couverte**, et la plage se lit dans le fichier. Et quand un
seul symbole sur trois sort un résultat, chercher d'abord ce que ce
symbole a de particulier — ici, il était le seul à changer de contrat.

**Le contre-poids, pour être juste.** La chaîne a fonctionné : chacun
des quatre correctifs de la journée a été prédit, benché sur données
synthétiques, puis vérifié sur les vraies. Le seul résultat
significatif de la journée est mort d'une objection formulée **avant**
de le tester. C'est le fonctionnement normal, pas un échec — mais s'il
n'y avait pas eu de table de composition, il serait dans un panel, et
on construirait dessus la semaine prochaine.

---

## 17/08/2026 — j'ai lu une heure et j'ai dit une journée

**Ce que j'ai écrit**, après la description de la bougie du 12/08 :

> « Le Dow est vendu **plus fort** que le S&P n'est acheté. C'est
> exactement ce que tu décrivais depuis le début. »

Appuyé sur les 61 minutes autour de 14h30 : `MES +815` contrats,
`YM −170`. Deux CVD qui ne croisent jamais zéro, signes opposés,
et une conversion en notionnel qui rendait l'écart spectaculaire
(+31,7 M$ contre −45,9 M$).

**Ce que la séance entière dit :**

```
2026-08-12   MES-continu  CVD  -8773   centile 24.8
             YM-continu   CVD  -1735   centile  8.0
```

**Les deux sont négatifs.** Personne n'achetait le S&P ce jour-là. Le
`+815` existe uniquement dans ma fenêtre d'une heure — c'est un
rebond local à l'intérieur d'une journée vendeuse, et j'en ai fait le
comportement de la journée.

**Pourquoi c'est une faute et pas une nuance.** J'avais choisi la
fenêtre (`--avant 30 --apres 30`) pour décrire une bougie. Décrire, la
fenêtre est légitime. Mais dès que j'ai écrit « le Dow est vendu
pendant que le S&P est acheté », j'ai changé d'objet sans changer de
mesure : j'ai parlé d'un régime de séance avec un chiffre d'une heure.
Rien dans la sortie ne m'y autorisait, et rien ne m'en empêchait non
plus — l'outil ne montrait pas la journée.

**Ce qui reste vrai, et qui est plus fort.** Le Dow est vendu de façon
**disproportionnée par rapport à sa propre histoire** : centile 8 sur
112 séances, contre centile 25 pour le S&P. En notionnel, −469 M$
contre −341 M$. La lecture de l'utilisateur tient donc — l'US30
travaillé à la baisse ce jour-là — mais par une intensité, pas par une
opposition.

**Les règles.** Une fenêtre choisie pour décrire ne se transforme pas
en fenêtre de mesure parce que le résultat est joli. Et tout chiffre
sur une fenêtre doit être accompagné du même chiffre sur la séance :
le centile du jour dans sa propre distribution était à trois lignes de
code, et il aurait empêché la phrase.

---

## 17/08/2026 — le verdict contredit sa table, deuxième fois dans la journée

**La sortie**, paire `MES-continu` × `TICK-NYSE` :

```
                    TICK-NYSE +    TICK-NYSE -
MES-continu +                60              0
MES-continu -                59              0

Les quatre cases sont peuplees : le signe du CVD
varie d une seance a l autre sur les deux symboles.
```

Deux cases à zéro, et la phrase juste en dessous affirme que les
quatre sont peuplées.

**La cause.** Je testais la case **dominante** (`> 85 %`). Avec 60 et
59 répartis sur une seule colonne, aucune case ne domine — le code
tombait donc dans la branche « tout va bien » sans jamais compter les
cases réellement remplies. Le test répondait à une question voisine de
celle que la phrase prétendait trancher.

**C'est la faute de `bruit_par_actif` de ce matin, à l'identique** : un
verdict calculé à côté de la table qu'il résume, dans un fichier écrit
le jour même où j'ai consigné cette faute. Écrire la règle ne suffit
pas à l'appliquer.

**La règle, reformulée pour être utilisable.** Un verdict doit être
calculé **sur les mêmes nombres que ceux qui sont affichés**, et pas
sur une statistique dérivée qui leur ressemble. Si la table montre
quatre cases, le verdict compte quatre cases.

**Le contre-poids.** Le défaut était visible parce que la table était
imprimée à côté du verdict. Un outil qui n'aurait affiché que sa
conclusion aurait passé le contrôle.

## 17/08/2026 — j'ai corrigé un `print`, pas la sortie

Le REPL DeepSeek du 8095 rendait, **tous les jours** :

```
DEEPSEEK reasoner · 7.8s → (vide / ValueError: I/O operation on closed file.)
```

Le 12/08 j'avais déjà rencontré cette exception. Je l'avais corrigée
dans `_ensure_init` de `repl_web` — l'endroit où elle se **voyait**.
Elle est ressortie six jours plus tard dans `council_shadow._call_model`,
c'est-à-dire ailleurs, pour la même raison.

**La cause n'était pas dans le REPL.** Trois lanceurs coexistent et ne
lancent pas le 8095 pareil :

```
Superviseur.ps1:203       -RedirectStandardOutput + -RedirectStandardError
Gardien-Stack.ps1:258     aucune redirection
Redemarrer-Stack.ps1:164  aucune redirection
```

Sans redirection, le processus hérite de la console de son parent. Le
gardien est une tâche planifiée `/SC MINUTE /MO 5` lancée
`-WindowStyle Hidden` : elle naît, relance ce qui manque, puis meurt.
Sa console meurt avec elle, et le 8095 qu'elle vient de lancer garde
un descripteur fermé. **Le même code marche ou ne marche pas selon qui
l'a relancé** — et comme le gardien passe toutes les cinq minutes,
c'est presque toujours lui qui gagne après un incident.

**La règle.** Corriger une faute à son point d'impact ne la corrige
pas : il y a autant de points d'impact que de `print` dans le
processus, et on ne les épuise jamais. Quand la même exception
réapparaît ailleurs, ce n'est pas une récidive, c'est la preuve qu'on
n'avait pas touché la cause.

**Le corollaire, plus large que le REPL.** Le gardien relance aussi
les **traders** avec cette même sortie morte. Tout `print` chez eux
lève la même exception, et rien ne l'écrit nulle part.

## 17/08/2026 — un correctif qui emprunte les imports de sa cible

`patch_repl_sortie.py` insère un bloc dans `repl_web.py`, un fichier
que je ne peux pas lire. Première version : le bloc se servait de `io`,
`os` et `datetime` **supposés présents** en tête de la cible.

Au banc, l'en-tête horodaté du journal n'a pas été écrit. `NameError`
sur `datetime`, avalé par le `except` qui protège justement cette
écriture. Le correctif fonctionnait à 90 % et perdait sa trace
d'audit en silence.

**La règle.** Du code injecté dans un fichier qu'on ne peut pas lire
ne doit rien lui emprunter. Il refait ses imports sous des noms privés.

**Ce qui l'a attrapé** : le banc, pas la relecture. Et il ne l'a
attrapé que parce que le banc **affichait le journal produit** au lieu
de se contenter de vérifier que le patch s'appliquait.

## 17/08/2026 — j'ai déclaré perdu ce qui partait en un appel

`git push` refusé, API GitHub refusée : les trois documents de
référence n'existaient que dans un conteneur éphémère. J'ai annoncé
qu'il faudrait les monter sur le Drive en gzip + base64, ~95 000
caractères à réémettre à la main, avec le risque qu'un seul caractère
faux détruise l'archive entière.

`SendUserFile` prend un **chemin** et livre le fichier. Aucun octet ne
passe par le contexte. Les trois documents sont partis en un appel.

**La règle.** Avant de bâtir un contournement coûteux, faire
l'inventaire des outils disponibles. J'ai passé plusieurs échanges à
planifier un transport de 95 Ko à travers ma propre fenêtre alors
qu'un outil de la liste faisait exactement ça, gratuitement.

## 17/08/2026 — la règle était écrite dans trois outils, pas dans le quatrième

`refus_continuation.py`, première sortie réelle, trois symboles :

```
TICK-NYSE     APPROCHE  écart 728   p 0,0005
MES-continu   APPROCHE  écart  32   p 0,77
YM-continu    APPROCHE  écart  16   p 0,48
```

Le **seul** déclencheur détecté était sur le seul symbole qui ne peut
pas en avoir. Le `delta` de TICK est un compteur monotone — z = +11,7,
130 séances positives sur 130 — parce qu'un indice n'a pas de carnet.
Le sommer sur soixante minutes ne mesure pas un flux, ça mesure la
position dans la journée. Et 323 refus contre 83 continuations, ratio
inversé par rapport aux deux autres actifs, dit la même chose
autrement : un oscillateur borné revient toujours, ses cassures
échouent par construction.

TICK était déjà écarté dans `flux_contre_prix.py`, dans
`ecart_fenetre.py`, dans `bougie_deux_actifs.py`. J'ai écrit ce
quatrième outil de zéro et je n'ai repris aucune des exclusions.

**C'est mot pour mot l'entrée que j'avais écrite le matin même** — « une
règle notée mais appliquée à un seul endroit n'est pas une règle, c'est
une anecdote ». Elle s'est vérifiée sur elle-même dans la journée.

**La règle, reformulée pour être opérante.** Un outil neuf qui lit les
mêmes fichiers qu'un outil existant hérite de ses exclusions, ou il
justifie pourquoi il ne les reprend pas. Écrire de zéro n'est pas
repartir de zéro.

**Ce qui l'a attrapé.** Rien d'automatique, encore : la lecture de la
sortie. Le résultat était *trop* isolé — un seul symbole sur trois, et
justement celui dont on savait déjà tout. Un chiffre qui sort seul est
d'abord suspect d'être un artefact de son symbole, pas la découverte de
la journée. C'est la même heuristique qui avait tué le `−1330`.

## 17/08/2026 — un verdict qui ignore une colonne significative

Même sortie, même outil :

```
YM-continu    VOLUME    écart +2,1   p 0,0005
```

Les refus se produisent sur un volume nettement supérieur aux
continuations. Significatif, non circulaire — le volume n'entre pas
dans la définition de l'issue. **Et le verdict n'en disait pas un mot** :
sa logique ne regardait qu'approche et décision.

Ce n'est pas le verdict qui contredit sa table, c'est le verdict qui en
saute une ligne. Troisième variante de la même faute dans la journée,
après `bruit_par_actif` et `cvd_journalier`. Les deux premières
disaient le contraire du tableau ; celle-ci se tait sur une de ses
colonnes, ce qui est plus discret et se corrige moins vite.

**Et la colonne qui, elle, portait un verdict n'aurait pas dû.**
`DECISION −2120, p 0,0005` mesure le delta de `[t, t+H]` contre une
issue déterminée en `t+H`. Avec `rho(delta, rendement) = 0,675` mesuré
le même jour, dire « les refus ont un delta de décision négatif »
revient à dire « les refus ont un rendement négatif » — leur
définition. J'ai laissé une quasi-tautologie porter la conclusion
pendant que la seule colonne informative restait muette.

**La règle.** Avant de faire porter un verdict à une mesure, vérifier
qu'elle ne contient pas déjà la variable qu'elle prétend expliquer. Une
fenêtre de mesure qui recouvre la fenêtre de l'issue n'est pas une
prédiction, c'est une reformulation.

## 17/08/2026 — j'ai déclaré un diagnostic confirmé avant d'en avoir la preuve

Après le redémarrage du 8095, j'ai écrit : « le diagnostic tient de
bout en bout ». Je le déduisais de la séquence — deux questions en
échec, puis une réussie après relance.

`Test-Path docs\repl_sortie.log` est revenu **False**. Le garde ne
s'était pas armé : la sortie du nouveau processus était vivante. Donc
le REPL aurait probablement fonctionné **sans** mon correctif, et le
simple redémarrage suffisait. Le correctif n'a rien eu à faire.

**Le raisonnement faux.** J'ai pris une corrélation temporelle — « ça
marche après le patch » — pour une confirmation causale, alors que le
patch écrivait précisément un fichier destiné à trancher, et que je
n'avais pas attendu de le regarder. La preuve était à une commande, et
j'ai conclu avant.

**La règle.** Quand un correctif embarque son propre témoin, on ne
conclut pas avant de l'avoir lu. Un « ça marche maintenant » n'est
jamais un diagnostic : il faut que le témoin dise *par quel chemin*.

## 18/08/2026 — six outils d'orderflow, cinq colonnes sur quatorze

**Ce que j'ai fait.** Écrit `reaction_evenements.py`, `ecart_carnets.py`,
`ecart_fenetre.py`, `flux_contre_prix.py`, `bougie_deux_actifs.py` et
`refus_continuation.py` — six outils dont l'objet est l'orderflow — en
lisant systématiquement les mêmes cinq colonnes : `ts`, `close`,
`delta`, `volume`, `contrat`.

**Ce que le fichier contenait :**

```
ts;open;high;low;close;trades;volume;bid_vol;ask_vol;delta;cvd;
spread_moy;contrat;roulement
```

Quatorze. Je n'ai jamais ouvert `open`, `high`, `low`, `trades`,
`bid_vol`, `ask_vol` ni `spread_moy`. Sur 183 314 barres, depuis le
premier jour.

**Le raisonnement faux.** J'ai recopié le lecteur du premier outil dans
le deuxième, puis dans les quatre suivants. Il marchait, donc je ne l'ai
jamais relu. Un lecteur qui fonctionne n'invite pas à vérifier ce qu'il
ignore — il ne se plaint pas des colonnes qu'il ne lit pas.

**Ce que ça a coûté, et c'est mesurable.** `refus_continuation.py`
mesure une SOMME de delta sur 60 minutes et sort `p = 0,77`. Or ce que
l'utilisateur observe — « le flux à l'intra-bougie va beaucoup plus
vite » — est dans `trades`, qui était là. Deux bougies de même volume et
même delta, l'une remplie en cinq secondes et l'autre étalée sur
soixante, étaient **le même point** dans toutes mes mesures. J'ai
conclu « le carnet ne prévient pas » sur cinq quatorzièmes du carnet.

**C'est le point 8 de notre propre protocole**, écrit le 17/08 : *« Le
format se lit dans les données (`--schema`, `--colonnes`, en-tête du
fichier), jamais dans un souvenir. »* Je l'ai appliqué aux `.jsonl` et
aux `snapshots`, jamais aux CSV que je produisais moi-même — comme si
un fichier qu'on a fabriqué n'avait pas besoin d'être relu.

**Ce qui l'a attrapé.** L'utilisateur, en deux phrases : *« tu as
complètement squizé ces variables dans ton code, or c'est le propre de
l'orderflow de nous permettre de visualiser les ordres. »* Aucun de mes
garde-fous ne pouvait le voir : ils vérifient que ce qu'on lit est
correct, jamais qu'on lit tout.

**La règle.** Avant d'écrire le premier outil sur une source, **imprimer
son en-tête et le commenter colonne par colonne** — y compris celles
qu'on ne compte pas utiliser, surtout celles-là. Et quand on recopie un
lecteur d'un outil à l'autre, la copie est le moment où l'on relit, pas
celui où l'on se dispense de relire.

**Le contre-poids.** La correction est gratuite : `trades` et
`spread_moy` sont déjà là, sur toute la profondeur. Rien à
retélécharger, rien à payer. La donnée n'a jamais manqué — c'est
l'attention qui a manqué.

## 18/08/2026 — j'ai cité dans un bloc la ligne exacte qui envoie des ordres

**Ce que j'ai fait.** En expliquant que `Redemarrer-Stack.ps1` lance
`price_action.py` sans `PA_ROLE`, j'ai recopié sa ligne 164 dans un
bloc ```powershell pour la commenter :

```
Start-Process -FilePath "python" -ArgumentList $argus -WorkingDirectory $STACK -WindowStyle Minimized
```

**Elle a été collée dans le terminal**, comme tout bloc de code sur
cette machine. Elle a échoué sur `ParameterBindingValidationException`
parce que `$argus` était vide dans ce shell.

**Ce qui serait arrivé sinon.** `$argus` vaut `price_action.py` dans le
script d'origine. Avec la variable définie, cette ligne lance
`price_action.py` **sans `PA_ROLE=panel`** — donc en rôle MOTEUR, avec
ses boucles de trading, pendant le gel. C'est l'interdit n°2, et je
venais de passer trois paragraphes à expliquer pourquoi il ne fallait
jamais faire ça.

**Rien n'a été lancé.** Le sauvetage vient d'une variable vide, pas
d'une précaution de ma part.

**Le constat de l'utilisateur, et c'est lui qui fonde la règle :**

> « la ligne start process était encadrée dans le chat comme si je
> devais la coller, c'est une erreur à ne pas reproduire si tu ne veux
> pas que je colle ça. »

C'est exactement ça. **L'encadrement EST l'instruction.** Ce que je
croyais dire — « regarde cette ligne du script » — n'existe pas dans
l'interface : un cadre, sur cette machine, veut dire « colle-moi ».
L'intention de l'auteur n'est pas lisible ; seule la mise en forme
l'est.

C'est pour ça que trois rappels n'avaient rien corrigé : je corrigeais
mon attention alors que le défaut était dans le contrat de la mise en
forme.

**La règle existait déjà, écrite trois fois.** 14/08 : *« un bloc de
code EST une commande, c'est le contrat, quelle que soit mon
intention »*. Puis récidive à 23:15, puis à 23:19, puis à 01:00 sur
`python -c`. Quatrième fois.

**Ce qui change, parce que la répéter ne suffit visiblement pas.** La
règle n'était pas assez précise. Elle devient :

> **Ce qui est cité n'est jamais mis en forme comme ce qui est
> exécuté.** Une ligne de code d'un fichier tiers se cite en texte
> indenté, jamais dans un bloc `powershell`. Le bloc à trois
> apostrophes avec un langage est RÉSERVÉ à ce que l'utilisateur doit
> taper.

Et une seconde, propre à cette machine :

> **Une ligne qui peut lancer un processus ne se cite pas du tout.**
> On la décrit — « la ligne 164 lance python sans poser PA_ROLE » — et
> on donne son numéro. Le lecteur peut l'ouvrir ; personne ne peut la
> coller par accident.

**Ce que ça dit du reste.** Trois répétitions n'avaient rien corrigé
parce que je traitais ça comme un défaut d'attention. C'en était un de
convention : tant que « citer » et « exécuter » ont la même apparence,
l'accident n'attend qu'une variable non vide.

## 18/08/2026 — un détecteur aveugle du côté où vit le phénomène

**Ce que j'ai fait.** `bougies_reperes.py` signale une minute quand
elle **dépasse** le centile 99 de sa séance, sur l'une des six
dimensions. Une seule queue, la haute, sur les six.

**Ce que ça rate.** La moitié des phénomènes qu'on cherche vivent en
bas :

```
ABSORPTION      RENDU bas    beaucoup de flux, peu d'amplitude
petits ordres   TAILLE bas   "beaucoup de petits ordres pressés"
compression     AMPLEUR bas  le prix ne bouge plus du tout
```

**La preuve était dans ma propre sortie.** Les vingt-cinq minutes les
plus marquées de MES ont presque toutes un `RENDU` entre **0,1 et
0,5** — ce sont des minutes absorbées, et pas une n'est signalée pour
ça. Elles passent par VITESSE, AMPLEUR et PRESSION. Le phénomène que
l'utilisateur décrivait depuis le début était dans mes chiffres, à
l'écran, et mon détecteur ne savait pas le nommer.

**C'est la faute de `bruit_par_actif` v1, à l'identique**, consignée le
17/08 : *« ne cherchait qu'un franchissement de 1 vers le haut. Les
trois actifs descendent : rien trouvé. »* Troisième fois qu'une
recherche unilatérale rate ce qu'elle cherchait, dans trois outils
différents.

**La règle, reformulée pour être utilisable.** Un seuil sur une
distribution a **deux** côtés. Avant d'en écrire un, dire lequel des
deux porte le phénomène — et si la réponse est « je ne sais pas »,
prendre les deux. Une queue unique n'est pas plus prudente, elle est
aveugle de moitié.

**Ce qui l'a attrapé.** La lecture de la table, pas le code. Les
`RENDU 0,1` alignés dans la colonne de droite sautaient aux yeux dès
qu'on regardait les chiffres au lieu des libellés. Encore une fois
c'est d'avoir imprimé la table à côté du verdict qui a sauvé la
mesure.

**Le correctif.** `patch_queues.py` : chaque dimension teste ses deux
bornes, le libellé porte le sens — `VITE+` rapide, `TAIL-` petits
ordres, `REND-` absorbé. Et une table des repères par heure, parce que
la même sortie a montré autre chose : **treize des vingt-cinq minutes
les plus marquées de YM tombent à 13:30 UTC exactement**, l'ouverture
du cash NYSE. Ce n'est pas un événement, c'est une horloge — le piège
déjà écrit au §2 du protocole à propos de 14:30 et de l'initial
balance.
