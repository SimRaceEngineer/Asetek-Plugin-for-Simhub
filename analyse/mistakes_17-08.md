<!-- A concatener a la fin de mistakes.md sur le VPS. -->
<!-- Tout ce que le 17/08 ajoute a ce document, en UN seul -->
<!-- morceau. Remplace les fragments separes, desormais -->
<!-- prefixes _PERIME_ sur le Drive. -->

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
