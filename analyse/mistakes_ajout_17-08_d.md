<!-- A concatener a la fin de mistakes.md sur le VPS -->

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
