# HYPOTHESES — écrites le 14/08/2026, avant les données

Ce fichier existe pour une seule raison : **une hypothèse écrite après
avoir vu le résultat n'est pas une hypothèse.** C'est une description.

La stack est gelée pour 15 jours. Pendant ce gel, les collecteurs
écrivent le contexte d'entrée, le contexte de sortie, le plateau et la
séance de chaque ticket, sur les quatre unités x10 / x20 / x30 / x60.
À la fin, on lira. Ce qui est écrit ici est ce qu'on prédit **avant**
de lire, avec, pour chacune, ce qui la tuerait.

Toute conclusion tirée fin août qui ne correspond à aucune ligne de ce
fichier devra être traitée comme une trouvaille de fouille — à
re-tester sur des données neuves, pas à mettre en production.

---

## 0. La règle de comptage, posée avant de compter

Pour distinguer un edge *e* du bruit avec un écart-type par ticket σ :

    n > (z · σ / e)²

Trois conséquences, à accepter maintenant plutôt qu'à découvrir en
septembre :

**σ n'est pas connu.** Il doit être mesuré sur les tickets réels et
reporté ici avant toute lecture. Tant qu'il est inconnu, tous les *n*
ci-dessous sont des ordres de grandeur, calculés avec σ ≈ 60 € — un
chiffre plausible, pas une mesure. **Premier travail de fin de gel :
remplacer ce 60 par le vrai.**

**Le nombre de comparaisons décide du seuil.** On regardera 4 setups ×
3 actifs × 4 séances × 2 bras, plus les régimes et les heures. C'est de
l'ordre de **100 cellules**. À 100 comparaisons, le seuil à 5 % global
correspond à z ≈ 3,5 par cellule, pas 1,96. Avec σ = 60 et e = 16 €/tk
(l'écart 206/207 mesuré) :

| comparaisons | z | n par cellule |
|---|---|---|
| 1 (annoncée d'avance) | 1,96 | ~54 |
| 20 | 2,9 | ~118 |
| 100 | 3,5 | ~172 |

**Donc : une cellule à moins de ~50 tickets ne conclut rien, quelle que
soit sa moyenne.** Elle décrit. Le tableau quadruple affichera le n de
chaque cellule à côté de la moyenne, et marquera d'un `?` toute cellule
sous le seuil. Une moyenne sans son n est un chiffre sans unité.

**Le compteur de comparaisons.** Chaque fois qu'on regarde une
découpe qui n'est pas listée dans ce fichier, on l'ajoute à la liste
ci-dessous. C'est le seul garde-fou honnête contre le fait de trouver
après coup la découpe qui gagne.

    Découpes non prévues examinées : (aucune au 14/08)

---

## 1. Le motif qu'on cherche à ne pas reproduire

Sept fois depuis le début, un chiffre s'est révélé garanti par sa
méthode de calcul et non par le marché :

1. le gain du PARTIEL70, garanti par la prise de bénéfice elle-même
2. les entrées x60 inventées au redémarrage du collecteur
3. le camp AVEC vide, garanti par le filtre qui le peuplait
4. l'archive détruite par son propre rafraîchissement
5. « le bras 206 ne bouge jamais son stop » — réfuté 20 min plus tard,
   mon échantillon ne contenait que des positions perdantes et le
   déclencheur est le profit
6. un contenu de réponse vide garanti par `max_tokens=5`
7. l'hypothèse « la clôture de séance a tronqué les gagnantes » —
   réfutée par mon propre diagnostic : les deux sorties de 19:30:06 ont
   des MFE de −2,72 et −2,08, elles n'ont **jamais** été en profit

Trois des sept sont de moi. Le motif n'est pas une maladresse
ponctuelle, c'est le mode d'échec par défaut de ce travail. Chaque
hypothèse ci-dessous porte donc, explicitement, **ce qui la rendrait
vraie par construction**.

---

## H1 — Ne pas tronquer les gagnantes

**Prédiction.** Aucun TP fixe, à aucun niveau, sur aucun des trois
actifs, ne battra la sortie hold-until-reverse actuelle.

**Base.** Trois mesures indépendantes convergent déjà : le TP fixe est
négatif à tous les niveaux ; le stop seul est négatif partout, les deux
seuls réglages positifs étant des maxima isolés que le script étiquette
lui-même « overfitting » ; et le bras 206 (hold) bat le 207 (partiel
70 %) de **+16,76 €/ticket sur les trois actifs**, à entrées
identiques — confirmé par des sorties jumelles partageant MFE et MAE au
centime.

**Ce qui la tue.** Un TP qui bat le hold sur au moins deux actifs, avec
n ≥ 50 par actif, et qui reste positif quand on retire le meilleur
décile de trades.

**Ce qui la rendrait vraie par construction.** Comparer un TP à un hold
sur un échantillon dominé par des tendances. C'est pourquoi la
comparaison doit être refaite **par régime**, pas en agrégé.

**Statut : la mieux étayée des sept. Aucune action.**

---

## H2 — Le risque appartient au lot, pas à la distance de stop

**Prédiction.** Resserrer le filet fixe dégradera le résultat net, quel
que soit le niveau testé.

**Base.** Le filet est absurde comme chiffre de risque — US30 = 17,6 %
du compte, 183 × la MAE médiane — et correct comme choix de
conception : la MAE médiane est de 21,8 pts sur US30 (q75 39,0), 23,5
sur NAS100 (40,5), 3,2 sur SPX500 (5,8). Un stop posé à 55 / 100 / 4
points coupe dans la distribution des trades qui finissent gagnants. La
grille l'a chiffré : **−334 €** sur l'échantillon.

**Ce qui la tue.** Un niveau de stop qui améliore le net **et** dont
les voisins immédiats l'améliorent aussi (pas un maximum isolé).

**Ce qui la rendrait vraie par construction.** Mesurer sur une période
sans gap ni trou de liquidité. Le filet existe pour le jour où le
marché saute ; son coût se voit tous les jours, son bénéfice une fois
par an. **Un test de 15 jours ne peut pas voir ce bénéfice.**

**Statut : hands-off confirmé par l'utilisateur. Aucune action.**

---

## H3 — 09h-11h : ne pas trader

**Prédiction.** Sur les 15 jours, les tranches 09h, 10h et 11h seront
négatives en régime range, sur les trois actifs, tous setups confondus.

**Base.** C'est la seule affirmation à ce jour qui repose sur un gros
échantillon **et** deux sources indépendantes : `panel_rails_post0508`
(3517 tickets) donne 09h −10,65, 10h −8,22, 11h −10,69 €/trade en
range ; `panel_orderflow` section 7 donne, aux mêmes heures, un ER
majoritairement CARNAGE/MOU avec des PnL de −18,18 (09h) et −13,64
(10h). Deux instruments qui ne partagent pas leur calcul.

**Ce qui la tue.** Une des trois heures positive avec n ≥ 100 sur la
nouvelle fenêtre, ou l'effet qui disparaît quand on contrôle par
actif — c'est-à-dire s'il n'est qu'un effet US30 déguisé en effet
horaire.

**Ce qui la rendrait vraie par construction.** L'heure et le régime ne
sont pas indépendants : si le range est sur-représenté le matin, on
mesure le régime en croyant mesurer l'heure. **Il faut le tableau
heure × régime, pas les deux marges séparément.**

**Statut : la meilleure candidate au « quand ne pas trader ». À
re-mesurer croisée avec le régime.**

---

## H4 — CHURN = standby

**Prédiction.** Le régime CHURN restera négatif sur les trois actifs et
les quatre setups.

**Base.** `horloge_regime` du 12/08 : CHURN −16,29 €/ticket sur 109
tickets, DOUTEUX −5,26 sur 166. Croise avec l'orderflow, où les tickets
classés CARNAGE sont négatifs (−4,79 à −8,91) quelle que soit la classe
rails.

**Ce qui la tue.** CHURN positif sur un setup, avec n ≥ 50 sur ce
setup.

**Ce qui la rendrait vraie par construction.** Une seule journée pour
l'horloge. Et surtout : **le régime est calculé par le même moteur qui
décide des entrées.** Si `churn_regime` filtre déjà partiellement, on
mesure le résidu de son propre filtre, pas le régime. À vérifier dans
le code avant de conclure quoi que ce soit.

**Statut : plausible, contaminée par une dépendance possible entre le
classifieur et le déclencheur.**

---

## H5 — Le x60 gagne seul

**Prédiction.** Sur les 15 jours, la présence d'un x60 en position
n'améliorera pas le résultat des autres bras présents en même temps.

**Base.** `familles.txt` depuis le 05/08 : les 5 fenêtres d'allumage
x60 totalisent −267,40 € ; les tickets du x60 lui-même font +3,29, ceux
des autres −270,69.

**Ce qui la tue.** Les accompagnants d'un x60 significativement
meilleurs que les mêmes bras hors présence x60, n ≥ 50 de chaque côté.

**Ce qui la rendrait vraie par construction.** **Cinq fenêtres.** C'est
le chiffre le plus fragile de tout le dossier — cinq événements, dont
un seul suffirait à retourner le signe. Le releveur `X_ENTREE` /
`X_SORTIE` posé le 14/08 existe précisément pour que cette question
devienne mesurable : il photographie le plateau — qui est en position,
avec quel latent, à quel âge — à la seconde où une cellule entre. Cette
photo ne se reconstitue pas après coup.

**Statut : question ouverte, instrument posé, échantillon nul.
C'est LA raison d'être du gel.**

---

## H6 — Leader de prix ≠ leader de setup

**Prédiction.** L'actif qui mène le mouvement de prix ne sera pas
l'actif le plus rentable sur le setup 60.

**Base.** Observation du 14/08 : US100 mène le momentum M15 (range_pos
80 %, angle +4,12) alors qu'il est le membre **le plus faible** du H1
depuis le 05/08 (206 −0,15 / 207 +4,46, contre US500 206 +33,09).

**Ce qui la tue.** Une corrélation positive entre rang de leadership et
rendement du setup, sur les 15 jours.

**Ce qui la rendrait vraie par construction.** Une observation d'un
seul jour érigée en règle. Elle est ici parce qu'elle est *falsifiable*
et intéressante, pas parce qu'elle est établie.

**Statut : hypothèse au sens propre. Rien derrière.**

---

## H7 — La séance US n'est pas hostile au x60

**Prédiction — celle-ci va CONTRE la lecture actuelle.** L'écart
EUROPE +102,74 / US −364,86 relevé sur le panel x60 ne survivra pas à
l'échantillon.

**Pourquoi je prédis le contraire de ce que montre le panel.** Le camp
US compte **cinq clôtures**. Trois d'entre elles expliquent la quasi-
totalité du chiffre : un `M206360` avec MAE −266,95, et deux US30
sortis à 19:30:06 à ≈ −88 € chacun. Ce n'est pas un effet de séance,
c'est trois trades. Et pour les deux de 19:30:06, on a déjà vérifié
qu'ils n'ont jamais été en profit (MFE −2,72 et −2,08) : rien n'a été
tronqué par l'horloge, ils étaient faux dès l'entrée.

Nommer « séance US » un total dominé par trois tickets, c'est le motif
n°1 de la liste, dans sa forme la plus classique.

**Ce qui la tue.** L'écart EUROPE/US persiste avec n ≥ 50 de chaque
côté, **et** persiste après retrait des trois plus grosses pertes.

**Statut : hypothèse posée à contre-courant, exprès. Si les données
la réfutent, l'effet de séance sera d'autant plus crédible qu'il aura
été prédit absent.**

---

## H8 — Ce n'est pas le range qui coûte, c'est l'entrée dans le range

**Prédiction.** À l'intérieur d'un même régime range, le résultat n'est
pas constant : les premières minutes après la bascule tendance → range
concentrent l'essentiel de la perte, et le range installé depuis
longtemps est proche de zéro plutôt que négatif.

**D'où ça vient.** Observation du 14/08 au matin : une matinée
« perdante en range » qui avait été gagnante pendant un temps, avec
US30 revenu au milieu de son range pendant que les techs et le SP500
restaient près du VAH. Le régime n'a pas changé de nom pendant que le
résultat changeait de signe.

**Pourquoi c'est différent de H3 et H4.** H3 découpe par heure, H4 par
étiquette de régime. Les deux supposent que l'étiquette est stable sur
sa durée. Si la perte est concentrée à la **bascule**, ni l'heure ni
l'étiquette ne la voient : elles la diluent sur toute la plage. C'est
exactement le mécanisme qui rend une moyenne horaire négative sans
qu'aucune heure ne soit mauvaise.

**Ce qui la tue.** Le PnL par ticket, tracé contre le temps écoulé
depuis la dernière bascule de régime, reste plat. n ≥ 50 par tranche de
temps-depuis-bascule.

**Ce qui la rendrait vraie par construction.** Le classifieur de régime
a une inertie : il étiquette « range » avec du retard. Si ce retard est
du même ordre que la fenêtre où l'on cherche l'effet, on mesure la
latence du classifieur et on l'appelle un effet de marché. **Il faut
donc relever la bascule à partir du prix, pas à partir de l'étiquette.**

**Ce qu'il manque pour la tester.** L'instant de bascule, et la
position dans le range, minute par minute. Les panneaux ne le gardent
pas : ce sont des instantanés réécrits à chaque rafraîchissement —
artefact n°4 de la liste. En revanche, depuis le 13/08 15:37, les
barres de l'orderflow portent `close`, `high` et `low` : **la position
dans le range se recalcule** pour toute minute couverte par l'historique
des barres, à condition de retenir la même définition de fenêtre (7 j
ou 24 h) que celle affichée par les panneaux. C'est la seule voie de
reconstruction disponible, et elle ne remonte pas avant le 13/08.

**Statut : hypothèse la plus récente, et la plus prometteuse des trois
« quand ne pas trader », parce qu'elle est la seule qui explique
pourquoi une moyenne peut être négative sans qu'aucun moment ne soit
franchement mauvais.**

---

## Ce qui n'est PAS une hypothèse et ne le deviendra pas ici

- **Le papier hors séance.** +35,34 €/tk sur M10, +94,82 sur M20,
  +56,69 sur M30 — sans spread ni slippage, aux heures où le spread est
  précisément le plus large. Le papier hors séance est optimiste **par
  construction**. Il n'entrera dans aucune conclusion. La seule partie
  comparable au live est la partie en séance, et elle est nettement
  moins flatteuse (M10 +13,43 · M20 −16,31 · M30 −51,72).
- **Le setup 60 à +15,52 €/tk sur 83 tickets.** Avec σ = 60, l'erreur
  type est 6,6 € et t ≈ 2,35 : correct pour **une** comparaison
  annoncée d'avance. Mais le setup 60 a été **choisi** comme le
  meilleur parmi une dizaine de candidats. Après correction, il ne
  passe plus. Ce n'est pas une raison de l'abandonner — c'est une
  raison de ne pas construire dessus avant d'avoir les n du §0.
- **Toute conclusion tirée d'un LLM entraîné sur ces données.** Voir le
  §0 : de l'ordre de 15 000 tickets pour que la centaine de cellules
  signifie quelque chose. Quinze jours n'y suffiront pas. Ce qu'on
  collecte est le jeu d'entraînement d'un travail ultérieur, pas de
  celui-là.

---

## Ce qui ferait abandonner l'exercice

Si, à la fin du gel, aucune cellule du tableau quadruple ne se détache
du bruit une fois le seuil du §0 appliqué, la conclusion à écrire est
« aucun setup ne se distingue sur cette fenêtre » — pas « il faut
découper autrement ». Le droit de redécouper s'achète avec des données
neuves, jamais avec les mêmes.
