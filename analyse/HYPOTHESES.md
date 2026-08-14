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

    Découpes non prévues examinées :
      - 14/08 14:00 — participation à la séance US (→ H9),
        trouvée en cherchant H8.  Total : 1

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

**Ce qu'il manque pour la tester — corrigé le 14/08 à 12:55.** Rien.
J'avais écrit qu'il faudrait reconstruire l'instant de bascule depuis
les barres, faute de trace. C'était faux, et c'est une erreur de
méthode : j'ai conclu à l'absence d'une donnée sans avoir cherché les
fichiers. `logs\regime_history.jsonl` (14 Mo) porte, par actif et par
instant :

    {"iso":"2026-08-14 12:52:23","regimes":{"US30":{
      "type":"INDETERMINATE","confidence":"PRE_SESSION",
      "reason":"us_cash_opens_in_157min","elapsed_min":0}}}

`elapsed_min` **est** la variable de H8. Le test se réduit à joindre
chaque ticket à `regime_history` par horodatage et à tracer le PnL
contre `elapsed_min`. **Testable sur l'historique déjà accumulé, sans
attendre la fin du gel.**

**Deux avertissements sur les instruments, à respecter dans le test :**

*Ne pas utiliser `frg_transitions.jsonl` comme source des bascules.*
Deux transitions relevées à une minute d'écart, `chop` 52,6 et 48,2 :
le seuil est à ~50 et aucune hystérésis n'est visible. Quand le chop
oscille autour du seuil — c'est-à-dire exactement dans les phases
indécises qui nous intéressent — le journal produit des bascules en
rafale qui ne correspondent à aucun changement de marché. Le piège
prévu était l'inertie du classifieur ; le vrai est son **bégaiement**.
Utiliser la valeur `chop` et sa distance au seuil, pas les événements.

*Deux classifieurs coexistent et se contredisent.* `regime_history`
étiquette la matinée `INDETERMINATE / PRE_SESSION`, pas « range ».
Toute la lecture « 09h-11h en range, ça perd » (H3) vient d'un autre
instrument. Avant de conclure sur H3 ou H4, établir lequel des deux
alimente les chiffres des panneaux. **Deux régimes contradictoires sur
la même heure, c'est une conclusion qui dépend du fichier qu'on
ouvre.**

**Piste annexe, non prévue :** `refusal_log.py` porte `range_pos`. Un
journal de refus horodaté avec son contexte, c'est le seul endroit du
dossier où l'on observe les **non**-trades. Tout le reste ne voit que
ce qui a été pris — un biais de sélection dont on n'a aucune mesure.

**Statut au 14/08 à 14:00 : TOUJOURS PAS TESTÉE. Et le fichier sur
lequel je comptais ne porte pas ce que je croyais.**

`elapsed_min` n'est **pas** l'âge du régime. C'est le temps écoulé
depuis l'ouverture du cash US, vérifié trois fois : premier
enregistrement à 21:45:07 avec `elapsed_min` 375,1 et `n_bars` 376
(15h30 + 375 min = 21:45, exact) ; valeur `0` à 12:52 avec
`PRE_SESSION / us_cash_opens_in_157min` ; « durée médiane de régime »
de 509,7 min, soit 15h30 → minuit, avec 39 remises à zéro pour 3
actifs = 13 séances.

Pire : `phase` est une fonction déterministe d'`elapsed_min`. Les deux
tableaux que `regime_elapsed.py` produisait comme « l'énoncé » et « la
forme » sont **la même table deux fois** — trois cellules identiques au
centime, totaux compris (STABLE ≡ 120-240 min, CONFIRMATION ≡ 60-120,
MONEY_HOUR_END ≡ 30-60).

Et le garde-fou n'a rien vu : le « sous 2 minutes : 0 % » validait une
horloge de séance qui n'a jamais bégayé, pas le classifieur de régime.
Un garde-fou qui surveille la mauvaise variable rassure sans protéger.

**Huitième instance du motif, la quatrième de moi.** L'erreur n'est pas
d'avoir mal lu un champ : c'est d'avoir écrit un lecteur autour d'une
hypothèse sur le sens d'un champ, sans vérifier ce sens sur trois
points de la donnée avant de construire.

**Ce qu'il faut pour tester H8, et qui reste à trouver :** un
horodatage de changement de régime dérivé du prix. `frg_transitions`
existe mais bégaie autour du seuil chop 50. `regime_history` porte
`type` par instantané — un changement de `type` entre deux instantanés
successifs est une bascule, et c'est probablement la bonne source, à
condition de mesurer d'abord combien de ces bascules durent moins de
deux minutes.

---

## H10 — Le porteur doit être en avance, pas le plus grand

**Prédiction.** Un petit timeframe (M2, M5) profite de la couverture
d'un M10-M30, et pas de celle d'un H1. Le H1 qui s'allume est déjà en
retard pour un scalp.

**Base — mesurée le 14/08, depuis le 05/08 uniquement :**

```
x02  porte par x10/x20/x30   n= 63   +12.92
x02  porte par x60           n=144    -7.56
x05  porte par x10/x20/x30   n= 44   +15.25
x05  porte par x60           n= 81   -28.47
```

Regroupé : **+13,89 €/tk sous porteur M10-M30 (107 tickets) contre
−15,09 sous porteur H1 (225)**. Vingt-neuf euros d'écart, t ≈ 4,1.
Signe cohérent sur les huit cellules.

**Le mécanisme, qui n'est pas une corrélation.** Le x60 est le seul
setup non perdant depuis le 05/08 **et** un désastre comme signal de
couverture. Ce n'est pas contradictoire : quand un H1 s'allume, le
mouvement est engagé. Le H1 tient jusqu'au reverse et encaisse tout ce
qui reste ; un M5 qui entre au même instant ne récupère que la queue.
**Le même trade est bon pour qui tient et mauvais pour qui scalpe.**
Ça recoupe H1 (« ne pas tronquer les gagnantes ») par l'autre bout, et
ça réinterprète la bande 30-60 min de x05 à −26,58 : ce n'était pas la
couverture qui vieillissait, c'était un porteur déjà en retard au
moment de s'allumer.

**Ce qui la tue.** Les porteurs M10-M30 négatifs, ou le porteur H1
positif, sur ≥ 10 séances distinctes.

**Ce qui la rendrait vraie par construction — et c'est le point.**
Les 107 tickets viennent de 43 allumages x10/x20/x30, **tous
postérieurs au 13/08 13:10**. Une journée et demie. Le t de 4,11
suppose des tickets indépendants ; des tickets d'une même séance ne le
sont pas. **L'unité de mesure correcte est la séance, et on en a une
et demie.** Une bonne session suffirait à tout produire.

**Statut : meilleure hypothèse du dossier, avec un mécanisme et un
échantillon d'une séance et demie. C'est la cible nommée du gel —
quinze jours donneront ~200 allumages au lieu de 43. Aucune action
avant.**

---

## H11 — Le contre-sens survit à la coupure du 5 août

**Prédiction.** Un M5 pris à contre-sens d'un grand récent reste
nettement pire qu'un M5 dans le même sens, dans le régime actuel.

**Base — depuis le 05/08, fenêtre 60 min :**

```
x05  SANS          n=385   -10.95
x05  AVEC-MEME     n= 53    +1.69
x05  AVEC-CONTRE   n= 72   -23.94
```

25,63 € d'écart, t ≈ 2,4. `x05 AVEC-MEME` est **la seule cellule
positive à effectif non trivial de tout le tableau post-05/08**.

Sur x02 : −2,07 contre −0,18, rien. Le sens décide pour le M5, pas
pour le M2. Deux mécanismes sous le même tableau — pour le M2, la
présence d'un grand signale un régime (les deux camps battent le
SANS) ; pour le M5, elle signale une direction.

**Ce qui la tue.** L'écart MEME/CONTRE qui s'annule sur la fenêtre du
gel, ou qui se retrouve identique sur x01 et x03 — ce qui en ferait un
effet d'heure et non de direction.

**Statut : la seule règle du dossier qui ait survécu à un changement
de régime. Prédite par l'utilisateur avant d'être mesurée, ce qui est
rare ici et compte double.**

---

## H12 — La loi de départ qui s'auto-annule

**L'énoncé, de l'utilisateur, le 14/08 :** *« il n'y a qu'un seul
départ propre, une seule entrée ignition qui lance le marché, et tout
le reste est du FOMO »*, puis *« on approche d'une loi de départ qui
s'auto-annule jusqu'à la suivante »*.

Ce n'est pas un filtre, c'est un **état avec une durée de vie** : un
départ s'ouvre, il autorise, il meurt, et plus rien n'est valide
jusqu'au suivant.

**Ce qu'elle explique sans avoir été formulée pour ça :**

| observation | lecture |
|---|---|
| hors séance −5,48 / séance +9,80 | les départs sont dans la séance |
| x60 mauvais porteur (−15,09), seul setup non perdant | le H1 **confirme** un départ, il ne l'ouvre pas |
| `jamais` : x02 −9,65 (451), x05 −14,59 (232) | entrer sans départ = le gros du volume et de la perte |
| TREND +12,2 / RANGE −5,95 | un trend est un départ vu sur sa durée |
| effondrement du 05/08 | en range, les allumages produisent de **faux départs** |

**L'auto-annulation est déjà visible.** x05 depuis le 05/08, par bande :
`0-15 +4,08 · 15-30 −15,93 · 30-60 −26,58 · 120-240 −2,58 · jamais
−14,59`. Le pire moment n'est ni le départ ni l'absence de départ,
c'est **30 à 60 minutes après** — pire que n'avoir jamais eu de départ.
Courbe en U : le départ meurt, et la zone juste après est plus
dangereuse que le calme plat, parce qu'on y entre encore avec la
conviction d'un départ qui n'existe plus.

**Chaque instrument a sa place dans la vie du départ.** x02 (effectifs
plus solides) : `0-15 −4,94 (62) · 30-60 +1,21 (102) · 60-120 −8,21
(152)`. Le M5 prend les quinze premières minutes, le M2 seulement la
tranche 30-60. Mécanisme plausible : le départ est violent, un M2 s'y
fait secouer et ne devient exploitable qu'une fois le mouvement
installé.

**LE DANGER DE CETTE HYPOTHÈSE.** Elle explique tout. C'est le propre
des bonnes histoires, et c'est exactement ce qui doit rendre méfiant :
une loi construite après coup sur des données déjà vues n'a aucun
pouvoir de prédiction tant qu'elle n'a rien interdit. Sa valeur est
donc **entièrement** dans ce qui suit.

**Ce que H12 interdit — quatre choses qui ne doivent pas se produire :**

1. **Le rang ne doit pas être neutre.** À délai égal, la première
   entrée d'un départ doit battre la troisième. Des rangs identiques
   dans une même bande videraient la loi de son cœur : il n'y aurait
   pas « un départ propre », seulement une fenêtre horaire.
   *(testé par `rang_ignition.py`, section D)*
2. **La densité doit coûter.** Un départ produisant huit entrées doit
   être moins bon par entrée qu'un départ qui en produit deux. Sinon
   il n'y a pas de FOMO, seulement du volume. *(section A)*
3. **Le contre-sens doit être mauvais partout**, pas seulement sur
   x05. Aujourd'hui x02 ne le montre pas (−2,07 contre −0,18). Si ça
   persiste, ce sont **deux lois** — directionnelle pour le M5,
   régimique pour le M2 — et non une.
4. **La zone morte doit exister pour tous.** x05 creuse à 30-60 min,
   x02 à 60-120. Si chaque setup creuse à un endroit choisi après
   coup, ce n'est plus une loi, c'est une description.

**Instrument manquant.** Le point 4 demande le temps depuis la **fin**
de l'épisode, pas depuis son début — la mesure directe de
l'auto-annulation. À écrire.

**Statut : la synthèse la plus prometteuse du dossier et la plus
exposée. Elle vit ou meurt sur ces quatre interdits, dont deux sont
déjà instrumentés et non lancés.**

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

## H9 — Ne pas trader hors séance US

**Découverte le 14/08 à 14:00, en cherchant autre chose.** Elle n'était
pas prédite. Elle est donc, au sens du §0, une **trouvaille de
fouille** — à traiter comme telle, quelle que soit sa taille.

**Le chiffre.** Sur 3 370 tickets rattachés (28/07 → 14/08) :

| | tickets | €/ticket | total |
|---|---|---|---|
| hors séance US | 2 353 | **−6,16** | **−14 490 €** |
| en séance 15h30-19h30 | 1 017 | **+12,32** | **+12 535 €** |

Dix-huit euros d'écart par ticket, sur des effectifs treize et six fois
au-dessus du seuil le plus sévère du §0 (~172). Deux tickets sur trois
sont pris hors séance, et toute la perte y est. Le net global de
−1 954 € est la somme d'une machine qui gagne en séance et se le fait
reprendre en dehors.

**Où ça saigne.** x05 hors séance : −14,62 × 616 = **−9 006 €**, deux
tiers du total à lui seul — alors qu'en séance le même x05 fait +36,20
puis +91,04. Puis x02 (−3 492 € sur 1 015) et x01 (−885 € sur 250).
**x60 est le seul setup positif hors séance** (+12,01 sur 89).

**Les bons moments.** MONEY_HOUR_OPEN (15h35-16h00) +33,95 €/tk sur
195 ; MONEY_HOUR_END (16h00-16h30) +16,47 sur 135 ; CONFIRMATION
(16h30-17h30) +1,76 sur 257 ; STABLE (17h30-19h30) +7,53 sur 430. La
demi-heure suivant l'ouverture vaut vingt fois le reste de la séance.
Et **zéro ticket au-delà de 19h30** — la coupure dure déjà observée sur
les sorties de 19:30:06.

**Ce qui la tue.** Trois choses, dans cet ordre :

1. *La concentration.* Dix tickets à −1 000 € fabriqueraient les deux
   tiers du chiffre. Il faut la moyenne élaguée à 1 % et le détail
   jour par jour. Si la perte tient à deux ou trois journées, c'est un
   événement, pas un régime.
2. *La dépendance au classifieur.* Le camp « hors séance » vient d'un
   champ produit par le module de régime. Le contrôle doit se faire sur
   **l'heure d'entrée seule**, sans lui — sinon on mesure le module.
3. *L'absence de mécanisme.* Si le spread hors séance n'explique pas
   l'écart, il faut chercher plus loin avant d'agir.

**Ce qui la rendrait vraie par construction.** Le hors-séance est aussi
là où le papier brillait (+35 à +95 €/tk) — et le papier ne paie ni
spread ni slippage. Que le live perde exactement là où le papier
gagnait le plus n'est pas une coïncidence : **c'est la signature d'un
coût de transaction, pas d'un signal.** Ce qui rend H9 plus crédible,
pas moins — mais déplace la conclusion : ce n'est peut-être pas
« mauvais moment », c'est « moment cher ».

**Rapport avec H3.** Si H9 tient, elle *explique* H3 : 09h-11h sont
hors séance US par construction. Une seule cause pour deux
observations, ce qui est meilleur que deux règles.

### Les trois contrôles, passés le 14/08 à 14:15

Sur l'heure d'entrée seule, **sans le classifieur** :

```
HORS SEANCE          n=2461  moy -5.48  total -13478.55  elaguee1pc -5.71
SEANCE 15h30-19h30   n=1099  moy +9.80  total +10775.19  elaguee1pc +8.69
```

1. *Concentration :* la moyenne élaguée à 1 % est **−5,71**, soit
   légèrement **pire** que la brute. Retirer les extrêmes n'améliore
   rien : ce n'est pas une queue. Pire ticket −535 € sur −13 479, soit
   4 % du total.
2. *Dépendance au classifieur :* écartée, le découpage est fait sur
   `entry_ts` seul.
3. *Répartition :* le camp hors séance est négatif **11 jours sur 14**.

H9 tient. **Mais le détail par jour en montre une plus grosse.**

### H9 bis — la vraie coupure est le 5 août, pas la séance

| | séance | hors séance | net |
|---|---|---|---|
| 29/07 → 04/08 | **+13 300 €** | −1 136 € | **+12 164 €** |
| 05/08 → 14/08 | **−2 524 €** | −12 343 € | **−14 867 €** |

Cinq jours à +12 164 €, puis **huit jours à −14 867 €**, la séance
elle-même passée négative. Net sur la fenêtre : −2 703 €. Tout le gain
du début a été rendu, et davantage.

L'écart séance / hors séance **survit** à la coupure — post-05/08, la
séance perd 3,46 €/tk contre 8,49 hors séance — donc H9 garde sa
*direction*. Elle perd son énoncé : ce n'est pas « la séance gagne ».
C'est « **depuis le 5 août tout perd, et le hors-séance perd deux fois
plus** ».

Le 5 août n'est pas une date choisie après coup : c'est celle que la
stack elle-même retient en nommant `panel_rails_post0508`. Le
décrochage était connu. Chiffré à onze jours consécutifs et à
−14 867 €, il change de nature.

**Ce que ça fait au gel.** Le gel de 15 jours a été décidé sur la
prémisse « on a un setup concluant, laissons tourner ». Au rythme
constaté, quinze jours de plus coûteraient de l'ordre de −15 000 €
supplémentaires. La décision appartient à l'utilisateur et n'est pas
rediscutée ici ; elle est simplement notée comme ayant été prise
**avant** que ce chiffre existe.

**La question qui départage** « tout arrêter » et « couper une
partie » : le setup 60 est-il encore positif depuis le 05/08 sur les
tickets réels, comme `familles.txt` le donne ? Si oui, la réponse est
étroite — couper les autres, x05 en tête (−9 006 € à lui seul hors
séance). Si non, ce n'est pas un problème de setup, et le gel garde
tout son sens : il faudra chercher ailleurs, et pour ça il faut les
données.

**Statut : le résultat le mieux étayé du dossier en effectif, le moins
étayé en discipline — non prédit, trouvé en cherchant autre chose.**

---

## Pré-enregistrement — séance US du 14/08, écrit à 13:30

Écrit **avant** l'ouverture du cash US (15:30). Une prédiction notée
après coup ne vaut rien ; celle-ci est datée et vérifiable ce soir.

**Configuration de départ, relevée à 12:51-12:52.** US100 puis US500
passent `CHOP → TREND_WEAK`, chop 52,6 et 48,2 — de part et d'autre du
seuil 50. `regime_history` classe les trois actifs `INDETERMINATE /
PRE_SESSION`, motif `us_cash_opens_in_157min`. US30 laggard, au milieu
de son range, pendant qu'US500 et US100 sont proches du haut.

**P1 (teste H7).** Les x60 de la séance US ne seront pas
systématiquement perdants. Si le total US ressort négatif, il sera
dominé par un à trois tickets. *Vérification : compter les tickets et
retirer les trois plus grosses pertes — pas lire le total.*

**P2 (teste H8).** Le chop vient de traverser son seuil ; la journée
devrait produire des bascules en série. Les tickets ouverts dans les
minutes suivant une bascule seront plus mauvais que ceux ouverts en
régime installé. *Vérification : PnL contre `elapsed_min`.*

**P3 (teste la contradiction des classifieurs).** Si ce soir un panneau
qualifie la matinée de « range » alors que `regime_history` la classe
`INDETERMINATE`, alors la conclusion « 09h-11h ne pas trader » (H3)
dépend de l'instrument qu'on ouvre, et non du marché. *Vérification :
comparer les deux étiquettes sur la même plage horaire.*

**P4 (aucune action).** Aucune position ne sera prise sur la foi d'un
signal x10 / x20 / x30. En live ils totalisent 13 tickets — M10 +150,12
sur 9, M20 −158,33 sur 3, M30 +45,91 sur 1 — contre un seuil de ~54.
Un seul trade retourne le signe du M20 comme du M30. Le M10 est le seul
positif à la fois en live et dans la partie du papier comparable au
live (en séance : M10 +13,43 · M20 −16,31 · M30 −51,72). C'est un
indice, pas un feu vert.

---

## Ce qui ferait abandonner l'exercice

Si, à la fin du gel, aucune cellule du tableau quadruple ne se détache
du bruit une fois le seuil du §0 appliqué, la conclusion à écrire est
« aucun setup ne se distingue sur cette fenêtre » — pas « il faut
découper autrement ». Le droit de redécouper s'achète avec des données
neuves, jamais avec les mêmes.
