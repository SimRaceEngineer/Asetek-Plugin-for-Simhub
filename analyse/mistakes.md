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

**Deuxième récidive à 23:19.** J'ai montré la ligne HTML 4361 dans un
bloc de code pour la commenter. Elle a été collée dans PowerShell :
`The term '<' is not recognized`. Un bloc de code, sur cette machine,
**est** une commande — c'est le contrat, quelle que soit mon
intention. Du contenu qui n'est pas exécutable se cite en ligne, ou
dans un bloc explicitement annoncé comme « à ne pas coller ». Trois
salves d'erreurs en une soirée pour une seule règle de mise en forme.

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
