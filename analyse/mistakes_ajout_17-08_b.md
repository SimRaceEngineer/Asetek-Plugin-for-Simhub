<!-- A concatener a la fin de mistakes.md sur le VPS -->

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
