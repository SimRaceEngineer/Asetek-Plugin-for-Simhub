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

    Découpes non prévues examinées, journée du 14/08 :
       1. participation à la séance US            (→ H9)
       2. coupure du 05/08                        (→ H9 bis)
       3. type de régime TREND/RANGE/INDETERMINATE
       4. position dans le range de séance
       5. bandes de délai disjointes
       6. porteur × petit setup                   (→ H10)
       7. sens MEME / CONTRE                      (→ H11, prédite)
       8. rang dans l'épisode                     (→ H12, H13)
       9. rang × délai
      10. rang × sens
      11. richesse d'épisode × rang               (→ H14)
      12. setup × camp de séance
                                              Total : 12

**CONSÉQUENCE, à appliquer rétroactivement.** Douze comparaisons non
annoncées demandent z ≈ 2,9, pas 1,96. Les t mesurés le 14/08 se
reclassent :

| résultat | t | verdict à z = 2,9 |
|---|---|---|
| riche vs pauvre (H14) | 4,85 | **tient** |
| hors séance vs séance (H9) | ≫ 3,5 | **tient** |
| porteur M10-M30 vs H1 (H10) | 4,11 | tient sur le t, **mais 1,5 séance** |
| x02 sous couverture 60 min | 3,09 | **tient** |
| x02 rangs 1-4 | 2,86 | **limite, ne tient pas** |
| contre-sens rangs 1-9 (H11) | 2,82 | **limite, ne tient pas** |
| bande 0-15 min, tous rangs | 2,57 | **ne tient pas** |

Trois résultats que j'ai présentés comme acquis dans la journée
passent sous la barre une fois le compteur tenu honnêtement. Ils ne
sont pas faux — ils sont **non démontrés**, ce qui n'est pas la même
chose et n'autorise aucune action.

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

## H9 — CONFIRMÉE PAR UN SECOND INSTRUMENT, le 14/08 à 18:10

`panel_rails_trades.txt` mesure la même chose par un chemin qui ne
partage rien avec le mien : classifieur rails RSI × leader × churn,
agrégation par cellule, **et une frontière de séance différente —
14h00 Paris au lieu de 15h30**.

Sur ses lignes TOUS ASSETS :

```
TIGHT_CROSS MIXED US  133  62%  +4228.93  +31.80
TIGHT_CROSS CLEAN US  173  60%  +1611.58   +9.32
MID         CLEAN US  187  63%  +2125.93  +11.37
WIDE        CLEAN US  183  56%  +2533.20  +13.84

TIGHT_CROSS CLEAN EUR 116  28%  -1993.46  -17.19
MID         CLEAN EUR 109  40%  -1393.88  -12.79
WIDE        CHURN EUR 374  39%  -2410.79   -6.45
```

**Toutes les lignes US positives sauf une. Toutes les lignes EUR
négatives, sans exception.** Regroupé : **US +6,93 €/trade sur 1 616,
EUR −6,97 sur 2 087.** Écart 13,90 €, **t ≈ 7,0**.

**CE QUE CETTE SECONDE MESURE PROUVE, ET CE QU'ELLE NE PROUVE PAS.**

Elle prouve que l'effet ne vient **ni d'une erreur de mon code, ni du
choix de la frontière horaire** : deux découpages différents (14h et
15h30), deux agrégations différentes, même signe et même ordre de
grandeur. C'est une robustesse *à la méthode*.

Elle ne prouve **pas** que l'effet survivrait à une autre période. Les
deux mesures portent sur la même fenêtre — grosso modo 21/07 → 14/08 —
et largement sur les **mêmes tickets** (3 714 contre 3 560). Ce ne sont
donc pas deux échantillons indépendants, mais **deux lectures
indépendantes du même échantillon**. La quantité de preuve n'a pas
doublé ; sa fragilité méthodologique, elle, a disparu.

Une asymétrie mineure à noter : les lignes `NO_DATA` n'existent que
côté EUR (105 et 50 tickets). Les retirer déplace la moyenne EUR de
moins d'un euro — l'effet ne tient pas à elles.

**Statut : le seul résultat du dossier confirmé par deux instruments
indépendants. Il se distingue des dix-sept autres et doit être traité
comme tel — c'est le seul sur lequel une décision serait défendable
aujourd'hui.**

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

### VERDICT du 14/08 — deux interdits levés, un violé

Lancé aux deux réglages : `--fusion 30 --portee 120` et
`--fusion 15 --portee 60`. Tout ce qui suit tient aux deux.

**Interdit n°1 — VIOLÉ. « Un seul départ propre » est faux.**
À délai égal, dans la bande 0-15 min :

```
30/120   rang 1 +6.98 (64)  rang 2 +7.28 (55)  rang 3 +11.69  rang 4 +20.57
15/60    rang 1 +5.90 (74)  rang 2 +6.90 (64)  rang 3  +9.87  rang 4 +17.90
```

Le rang 1 est le **plus mauvais** du lot, et la performance **monte**
avec le rang. L'effet de rang ne disparaît pas quand on contrôle le
délai — il s'inverse. Les entrées suivantes ne sont pas du FOMO, elles
sont meilleures.

**Interdit n°2 — LEVÉ, et il me réfute moi.** La densité est
identique de part et d'autre du 5 août : 9,59 contre 9,84
petits/épisode (réglage large), 5,22 contre 5,30 (réglage serré). Ma
crainte que l'effondrement post-05/08 soit une densité de FOMO mal lue
était **fausse**. La conclusion du 05/08 tient, elle n'était pas un
artefact d'agrégation. Un contrôle posé contre moi-même, qui passe.

**Ce qui survit, et qui est le fait dominant du rapport :**

```
hors episode   n=1975  -3.50/tk  -6905.51   (reglage 30/120)
hors episode   n=2395  -3.44/tk  -8243.12   (reglage 15/60)
rangs 1-4      n= 401  +6.73/tk  +2696.88
bande 0-15 min n= 191 +11.18/tk  +2134.90   (tous rangs confondus)
```

**Deux tickets sur trois — quatre sur cinq au réglage serré — sont
pris en dehors de tout épisode, et c'est là que passe la perte.** Le
débat rang 1 contre rang 3 porte sur 401 tickets ; celui-ci sur les
deux tiers du volume.

**Le sens se renforce au réglage serré.** Rangs 1-9 regroupés :
`MEME +9,67 (377) contre CONTRE −4,51 (229)`, écart 14,18 €,
**t ≈ 2,8** — contre t ≈ 2,0 au réglage large. Épisode plus serré =
épisode plus pur = effet directionnel plus net. Le contraire d'un
artefact de réglage. H11 se renforce.

**L'asymétrie M2/M5 tient aux deux réglages.** `x02 rangs 1-4 :
+11,77 €/tk sur 213 tickets, t ≈ 2,9` — le M2 entre tôt et gagne.
`x05 rang 1 −15,43, rang 2 −9,30, rang 3 +16,74` — **le M5 est le
pire quand il entre le premier.** Deux instruments, deux places dans
la vie du départ.

**Interdit n°4 — NON TESTÉ.** La zone morte après la *fin* de
l'épisode. L'instrument mesure le temps depuis le début, jamais depuis
la mort du départ. À écrire.

**Statut : H12 survit amputée. L'épisode existe et décide de presque
tout ; la fenêtre de quinze minutes est propre ; le sens compte. Mais
« un seul départ propre » est réfuté aux deux réglages.**

---

## H13 — La confirmation par répétition

**Énoncé.** Le nombre d'entrées déjà déclenchées dans l'épisode en
cours est un signal, disponible en direct et gratuit, que l'épisode
est réel. Le moteur ne re-tire pas quatre fois dans un faux départ ;
il re-tire quand les conditions tiennent.

**Base.** L'inversion de l'interdit n°1 ci-dessus : à délai égal, le
rang 4 bat le rang 1 aux deux réglages, sur les deux moitiés du jeu.

**Pourquoi c'est actionnable et pas circulaire.** Au moment où le
quatrième ticket s'ouvre, on sait que trois ont déjà été prises depuis
l'allumage. Aucune information future n'est requise. C'est un
compteur, pas une prédiction.

**Ce qui la tue.** Le rang qui cesse de monter, ou qui monte aussi
chez les tickets **hors** épisode — ce qui en ferait un effet de
grappe générique et non une confirmation de départ.

**Ce qui la rendrait vraie par construction.** Un épisode ne compte
quatre entrées que s'il en a produit quatre. Si les épisodes riches
sont mécaniquement ceux où le marché bougeait, on mesure l'amplitude
du mouvement et on l'appelle une confirmation. **Contrôle à écrire :
comparer le rang 4 des épisodes à 4 entrées au rang 4 des épisodes à
10 entrées.** Si seul le second est bon, c'est la richesse de
l'épisode qui parle, pas le rang.

**Statut : renversement de la thèse de départ de l'utilisateur, tiré
de son propre test. Non prédite — donc à traiter comme une trouvaille
de fouille jusqu'à confirmation sur données neuves.**

---

## H13 — VERDICT : réfutée, et par l'inverse

Le contrôle a tourné le 14/08. **La richesse d'épisode compte, mais
dans le sens opposé à celui que j'avais supposé.**

```
episodes a 1-4 entrees    n= 81   +25.04   +2028.09
episodes a 5-9 entrees    n=180   +12.71   +2288.34
episodes a 10+ entrees    n=808    -4.18   -3376.93
```

Monotone décroissant. À **rang fixé**, l'effondrement est net :

```
rang 1  taille 3-4  +21.68   |  rang 4  taille 3-4  +29.71
rang 1  taille 5-9  +11.38   |  rang 4  taille 5-9  +16.83
rang 1  taille 10-19 -4.46   |  rang 4  taille 10-19 +1.07
rang 1  taille 20+  -32.32   |  rang 4  taille 20+  -15.33
```

54 € d'écart sur le rang 1, 45 € sur le rang 4. La pente du rang à
taille fixée ne vaut que +8 à +17, et elle est **négative** dans la
taille 5-9. **La richesse écrase le rang d'un facteur cinq.**

J'avais lu une pente de rang comme une confirmation ; elle cachait un
effet de richesse de signe opposé. Dixième instance du motif, la
mienne.

---

## H14 — Un bon départ est avare

**Énoncé.** Un départ réel déclenche trois ou quatre entrées puis
laisse courir. Un moteur qui ne cesse plus de tirer signale l'absence
de départ, pas sa force.

C'est la thèse initiale de l'utilisateur — « un seul départ propre, le
reste est du FOMO » — remise au bon niveau : le FOMO n'est pas dans le
**rang** (dans un bon épisode les rangs 1 à 4 font +21 à +33), il est
dans l'**épisode**.

**Base.**

```
tailles 1-9   n=261   +16.54/tk   +4316   (52 episodes)
tailles 10+   n=808    -4.18/tk   -3377   (54 episodes)
```

21 € d'écart. **Et l'échantillon tient enfin à l'unité qui compte :
52 épisodes contre 54**, pas une séance et demie comme H10.

**Le problème pratique.** La taille finale n'est pas connue au moment
d'entrer : les rangs 1-4 des épisodes riches sont déjà négatifs et
rien ne les signale à l'avance. Ce que le comptage permet, c'est de
**s'arrêter** — au rang 5 on sait que quatre entrées ont eu lieu.
Couper à quatre par épisode donnait **+2 696 € au lieu de +940 €** sur
les tickets rattachés. C'est un compteur, il ne devine rien.

**Ce qui la tue.** L'écart pauvre/riche qui s'annule sur la fenêtre du
gel, ou qui s'inverse dès qu'on contrôle la durée.

**Ce qui la rendrait vraie par construction — deux pièges ouverts.**

1. **Riche ou simplement long ?** La fusion à 30 min enchaîne les
   allumages et étire la fenêtre. Il faut séparer *taille*, *durée* et
   *nombre d'allumages* avant d'attribuer l'effet à la densité.
2. **Tickets corrélés.** Les `?` des cellules croisées sont mérités ;
   seul le regroupement porte le résultat, et l'unité reste l'épisode.

**Instrument suivant.** *La richesse se voit-elle tôt ?* Si un épisode
à vingt entrées en produit six dans ses dix premières minutes, le
débit précoce prédit la richesse — et on refuse l'épisode entier au
lieu de le tronquer. Mesurable sur les mêmes données.

**Statut : le résultat le mieux fondé du dossier, et le seul dont
l'effectif tient à l'unité correcte.**

---

## H15 — La richesse se voit dans les dix premières minutes

**ÉCRITE LE 14/08 À 15:10, AVANT QUE LE SCRIPT TOURNE.** C'est le
point : annoncée d'avance, elle n'alourdit pas le compteur du §0. Le
seuil reste z ≈ 2,9.

**Prédiction.** Le nombre d'entrées produites dans les **dix premières
minutes** d'un épisode prédit sa taille finale, et donc son résultat.
Un épisode qui déclenche quatre fois avant la dixième minute finira
riche et perdant.

**Pourquoi ça compte.** H14 est établie mais **manchote** : la taille
finale n'est pas connue au moment d'entrer, donc elle ne permet que de
s'*arrêter* (compter jusqu'à quatre), jamais de *refuser*. Si le débit
précoce prédit la richesse, on refuse l'épisode entier dès la dixième
minute. C'est la différence entre tronquer une perte et ne pas la
prendre.

**Le protocole est strictement causal.** On observe les dix premières
minutes, on décide, et **on n'évalue que les tickets ouverts après la
dixième minute**. Aucune information postérieure à la décision n'entre
dans le camp jugé. Si l'écart apparaît, il est exploitable tel quel —
contrairement à H14, qui classe par une taille connue seulement à la
fin.

**Ce qui la tue.**
- Le débit précoce ne sépare pas les tailles finales (section A) —
  alors tout le reste est sans objet.
- Ou l'écart existe sur les tickets **du guet** (section D, témoin)
  aussi fort que sur les postérieurs : la règle constaterait un état
  au lieu de l'anticiper, et n'éviterait rien.

**Ce qui la rendrait vraie par construction — deux pièges.**

1. **La volatilité.** Fort débit et mauvais résultat peuvent avoir la
   même cause sans que l'un prédise l'autre. La section E contrôle
   durée et nombre d'allumages ; elle ne peut pas contrôler
   l'amplitude, faute de prix dans `tickets_rails`. **Ce test peut
   donc confirmer une règle utilisable sans en donner la cause** — et
   une règle dont on ignore la cause meurt sans prévenir quand le
   régime change.
2. **Zéro n'est pas faible.** Un épisode sans aucune entrée pendant le
   guet n'a pas un débit faible : il n'a peut-être pas commencé. Il
   est compté à part, jamais fusionné avec les faibles débits.

**Rappel d'unité.** L'unité est l'**épisode**, pas le ticket : ~106
épisodes en tout. Un n de 400 tickets répartis sur 20 épisodes vaut 20
observations, pas 400.

### VERDICT du 14/08 — RÉFUTÉE, sur données post-05/08

```
0 pendant le guet   n=304   -8.71   -2647.74
2-3 entrees         n=278   -4.63   -1287.05
1 entree            n= 18  +10.87    +195.68  ?
4-6 entrees         n= 19   -3.49     -66.26  ?
```

La prédiction était : fort débit précoce → épisode riche → mauvais.
**L'ordre est inverse** — le pire camp est celui sans aucune entrée
pendant le guet. Et l'écart entre les deux gros camps (4,08 €) a un
**t de 0,82** : pas d'inversion démontrée non plus. **Le débit précoce
ne porte aucune information utilisable, dans un sens ni dans l'autre.**

Aucun seuil de refus ne produit un camp gardé positif, et le seuil à 3
refuse le seul camp positif du tableau (`garde −4 359 / refuse +553`).

**Pourquoi ça ne pouvait pas marcher (section A).** Il y a un peu de
séparation — 71 % des épisodes à 2-3 entrées précoces finissent
riches, contre 41 % de ceux à zéro — mais la catégorie décisive
n'existe pas : **3 épisodes à 4-6 entrées, aucun à 7 et plus.** Les
épisodes riches le deviennent lentement, pas d'un coup.

Le contrôle E passe (durées 91/102/94 min, allumages 1,9/2,0/1,7) : ce
n'est ni la durée ni les allumages. Il ne sert simplement à rien,
faute d'effet à contrôler.

**Conséquence pour H14 : le plafond à quatre reste une règle d'ARRÊT,
et rien d'autre. On ne sait pas refuser un épisode riche à l'avance.**

**Piste ouverte, NON exploitée.** Le camp le plus mauvais est celui
dont la première entrée arrive tard : ce serait la **latence** du
premier ticket, pas le débit. Variable différente, **treizième
découpe** — elle monterait le seuil pour toutes les autres. À décider
froidement, pas dans la foulée d'un résultat.

**Statut : réfutée. Écrite avant d'être lancée, morte en une commande,
sans que rien n'ait été construit dessus. C'est exactement ce que le
pré-enregistrement doit produire.**

---

## H16 — Un départ qui tarde est un faux départ

**ÉCRITE LE 14/08 À 15:45, AVANT QUE LE SCRIPT TOURNE.** Déclarée
d'avance, elle n'entre pas dans le compteur du §0 : le seuil reste
z ≈ 2,9 et H14, déjà à t = 2,5, n'est pas pénalisée par cette
recherche. C'est la deuxième fois qu'on paie zéro pour explorer.

**D'où elle vient.** H15 est réfutée — le débit précoce ne porte rien.
Mais sa section B laissait voir autre chose :

```
0 entree pendant le guet   n=304   -8.71
2-3 entrees                n=278   -4.63
```

Le **pire** camp est celui qui n'a rien produit dans les dix premières
minutes. Pas une histoire de débit : une histoire de **latence**. Un
allumage qui met longtemps à entraîner une entrée n'a entraîné
personne, et ce qui vient ensuite arrive sur un départ déjà mort.

Ça recoupe la bande 30-60 min de x05 à −26,58 — pire que pas de
couverture du tout.

**Prédiction.** Plus la première entrée d'un épisode tarde, plus les
suivantes sont mauvaises. Le camp `latence ≥ 20 min` sera nettement
sous le camp `latence < 5 min`.

**Pourquoi c'est causal.** La latence du premier ticket est connue à
la seconde où ce ticket s'ouvre. On juge donc les tickets de **rang
≥ 2**. Le rang 1 est inévitable — c'est lui qui révèle la latence — et
sert de témoin en section C.

**Ce qui la tue.** Pas d'ordre monotone entre les tranches, ou un
écart déjà entièrement présent sur le rang 1 (témoin) : la règle
constaterait un état sans rien éviter.

**Ce qui la rendrait vraie par construction — trois pièges.**

1. **Troncature mécanique.** Un épisode dont le premier ticket arrive
   à la minute 40 a moins de temps restant dans la portée. S'il a
   simplement moins de tickets après, on mesure une troncature. La
   section E affiche `suite médiane` par tranche. *(Sur le jeu de test
   à données aléatoires, cette médiane tombe déjà de 3,0 à 1,0 tickets
   quand la latence monte — le piège est réel et pas théorique.)*
2. **Biais de composition.** Un épisode à un seul ticket ne contribue
   pas à la section B. Or ce sont les meilleurs selon H14. Le camp
   jugé est donc biaisé vers les épisodes longs, c'est-à-dire vers les
   mauvais.
3. **Unité.** L'épisode, pas le ticket. 300 tickets sur 25 épisodes
   valent 25 observations.

### VERDICT du 14/08 — RÉFUTÉE

```
0-2 min    n=139   -1.28      10-20 min  n=159   -6.76
2-5 min    n= 91  -11.92      20-40 min  n= 91  -13.59
5-10 min   n=130   -1.63      40 min +   n= 28   +1.28  ?
```

**Aucun ordre.** La prédiction était monotone ; le tableau zigzague —
2-5 min est le deuxième pire camp, 5-10 min presque le meilleur. Le
seuil de refus à 10 min donne 4,08 € d'écart, **t = 0,85**.

Témoin (section C) : le rang 1 n'ordonne pas non plus, et toutes ses
cellules sont sous 17 tickets.

**Le piège n°1 s'est déclenché comme prévu.** Suite médiane : 11 → 6
tickets quand la latence monte. La troncature mécanique est réelle.

**Le vrai plafond est l'unité.** 67 épisodes, cellules de 5 à 16.
638 tickets qui pèsent 67 observations. Visible dans la section A
avant même de lire les résultats.

**CONTRE-TEST du 14/08 15:30, sur objection de l'utilisateur.** La
section B regroupait tous les rangs ≥ 2 — un sac dominé par les rangs
5-9 et 10+, les mauvais. Objection juste : un effet dans la zone qui
paie y était noyé par construction. Restreint aux rangs 2-4 :

```
0-2 min   n=38   -9.18 ?     10-20 min  n=46   -4.01 ?
2-5 min   n=25  -10.54 ?     20-40 min  n=31   -2.34 ?
5-10 min  n=33   +0.24 ?     40 min +   n=13  -16.98 ?
```

Toujours aucun ordre, et la latence la **plus courte** est parmi les
pires. Toutes les cellules sous 54.

**Mais le contre-test a produit un résultat inattendu et important :**
total des rangs 2-4 post-05/08 = **−1 082 € sur 186 tickets, soit
−5,82 €/tk**. **Depuis le 5 août, le sweet spot perd aussi.** Le
+10,47 / +8,88 des rangs 3-4 était un effet de fenêtre complète, donc
d'avant la coupure.

Il ne survit que dans les épisodes pauvres et moyens — `taille 5-9 :
rang 3 +17,00, rang 4 +12,84` contre `taille 10-19 : rang 3 −11,29`.
**Ce n'est pas le rang qui sauve, c'est l'épisode.** H14, encore.

**Statut : réfutée, y compris sur le sous-groupe ciblé. Troisième test
pré-enregistré mort en une commande, compteur inchangé.**

---

## BILAN DE L'INTÉRIEUR DE L'ÉPISODE — 14/08

Quatre angles essayés : le **rang** (H13, réfuté), la **richesse**
(H14, survit en évitement seulement, t = 2,5), le **débit précoce**
(H15, réfuté), la **latence** (H16, réfuté).

**Depuis le 5 août, tous les camps de tous ces découpages sont
négatifs.** Les rangs ≥ 2 font −5,88 €/ticket quelle que soit la
façon dont on les trie.

Deux choses restent debout, pas une de plus :

1. **Ne pas trader hors séance US** (H9) — le seul edge démontrable.
2. **Ne pas trader un épisode qui s'emballe** (H14) — direction
   correcte, sous la barre à t = 2,5.

Les deux sont des règles d'**évitement**. Aucune règle d'entrée n'a
survécu à la journée.

---

## H17 et H18 — Le délai en BOUGIES, pas en minutes

**ÉCRITES LE 14/08 À 16:05, AVANT TOUTE MESURE.** Déclarées d'avance,
elles n'entrent pas dans le compteur du §0.

**L'objection qui les produit, de l'utilisateur.** Mes tranches de
latence (0-2, 2-5, 5-10, 10-20, 20-40, 40+ minutes) sont arbitraires —
je les ai choisies « à peu près logarithmiques », sans justification.
Or *une minute n'a pas le même sens pour un M2 et un M5*. La tranche
10-20 min met dans la même case un M2 qui a vu **dix bougies** et un
M5 qui en a vu **quatre**. Ce n'est pas le même événement.

**Pourquoi DEUX hypothèses et pas une.** Le délai en bougies peut se
compter de deux façons, et elles ne donnent pas la même réponse.
Choisir après avoir vu les résultats serait exactement la fouille que
le §0 interdit. On déclare donc les deux, et **on lira les deux
tableaux ensemble** quel que soit celui qui gagne.

---

### H17 — En bougies du PETIT qui entre

**Prédiction.** Le résultat s'ordonne par le nombre de bougies du
setup entrant écoulées depuis l'allumage — un M5 à 3 bougies se
compare à un M2 à 3 bougies, pas à un M2 à 3 minutes.

**Mon a priori, posé d'avance : je n'y crois pas.** En re-paramétrant
ce qu'on a déjà, x02 a sa bonne bande à 30-60 min soit **15 à 30
bougies M2**, et x05 à 0-15 min soit **0 à 3 bougies M5**. En bougies
propres, les deux fenêtres ne se rapprochent pas — elles s'éloignent.

**Ce qui la tue.** Pas d'ordre en bougies propres, ou un ordre moins
net qu'en minutes.

---

### H18 — En bougies du PORTEUR qui a allumé

**Prédiction.** Le résultat s'ordonne par le nombre de bougies du
grand timeframe écoulées depuis son allumage.

**Pourquoi c'est la plus prometteuse des deux.** Elle donnerait un
mécanisme à H10, qui n'en a pas encore : un x60 qui s'allume, puis
trente minutes, c'est **une demi-bougie H1** — très tôt en temps H1,
très tard en temps marché. Le H1 serait mauvais porteur non pas par
nature mais parce que sa bougie est trop lente pour un scalp. Un x10
à trente minutes, c'est trois bougies : le mouvement a eu le temps de
se déclarer *dans l'échelle du porteur*.

**Ce qui la tue.** Pas d'ordre en bougies de porteur, ou un écart
x60/x10-x30 qui persiste **à nombre de bougies de porteur égal** — ce
qui voudrait dire que le porteur compte pour autre chose que sa
vitesse.

---

**Ce que les deux partagent comme piège.** Le nombre de bougies est
une transformation monotone du temps *à setup fixé*. À l'intérieur
d'un même setup, H17 ne peut donc rien dire de plus que la latence en
minutes — elle ne change quelque chose qu'en **comparant les setups
entre eux**. Le test doit donc être lu sur les colonnes, pas sur les
lignes ; un « effet » visible seulement à l'intérieur d'un setup serait
la latence déjà réfutée, redécorée.

**Statut : les deux pré-enregistrées, aucune lancée.**

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

## H19 — Le SAR/h M5 des 30 dernières minutes annonce les 30 suivantes

**ÉCRITE LE 14/08 À 19:05, AVANT TOUTE MESURE.** Déclarée d'avance,
elle n'entre pas dans le compteur du §0.

**D'où elle vient.** Du REPL, à sa première lecture de
`signal_avance.txt` — un fichier qu'il n'avait jamais chargé, parce que
`REPL_CTX_MAX` le coupait avant. Il en tire que le SAR/h M5 mesuré sur
les 30 minutes écoulées est *« la seule mesure monotone dans le sens
attendu »*, et cite `Q2 −7,59 €/tk` et `Q3 −11,61 €/tk`.

**Pourquoi on ne la prend pas telle quelle.** Trois raisons, dans
l'ordre de gravité :

1. **Il cite deux quartiles sur quatre.** Une monotonie se juge sur les
   quatre. Deux points au milieu d'une série ne montrent rien : Q1 et Q4
   manquent, et ce sont eux qui portent l'écart.
2. **Seuils et verdict sur le même corpus.** Les bornes de quartile
   sont calculées sur les données mêmes où l'écart est lu. C'est la
   définition d'un résultat garanti par sa méthode de calcul — le motif
   qu'on a rencontré dix fois dans ce dossier.
3. **`signal_avance.py` le dit lui-même** : il faut couper le corpus en
   deux. Ce n'est pas fait. Le module annonce sa propre validation et ne
   l'exécute pas.

### Le test, tel qu'il sera exécuté

**Découpe par DATE, jamais au hasard.** Première moitié des séances →
calcul des trois bornes de quartile du SAR/h M5. Seconde moitié →
lecture du résultat par quartile, **avec les bornes de la première
moitié, figées**. Un tirage aléatoire mettrait des tickets d'une même
séance des deux côtés : ils ne sont pas indépendants, et la fuite
suffirait à fabriquer l'effet.

**Prédiction.** Dans la seconde moitié, l'ordre des quatre quartiles est
celui établi sur la première, et l'écart Q1 vs Q4 dépasse le seuil.

**Critère de réfutation.** H19 est fausse si, sur la seconde moitié,
l'ordre des quartiles n'est pas monotone, **ou** si l'écart Q1-Q4 a un
`t < 1,96` (seuil d'une comparaison annoncée d'avance), **ou** si une
cellule tombe sous 54 observations — auquel cas on n'a rien mesuré du
tout et on l'écrit ainsi.

### Ce qui la rendrait vraie par construction — à vérifier AVANT de lire

**La fenêtre passée ne doit pas toucher la fenêtre future.** Si le
SAR/h est calculé sur 30 minutes qui chevauchent, même d'une minute,
les 30 minutes dont on lit le résultat, ce n'est pas un indicateur
avancé : c'est le même intervalle lu deux fois. À contrôler dans le
code avant tout tableau.

**L'unité n'est pas la fenêtre glissante.** Des fenêtres de 30 minutes
qui se recouvrent produisent des observations corrélées : 200 fenêtres
glissantes sur 13 séances valent 13 observations, pas 200. Le `n` à
opposer au seuil est **le nombre de séances distinctes**, et il sera
affiché à côté de chaque cellule.

**Le sens attendu est un sens d'ABSTENTION.** Les deux quartiles cités
sont négatifs tous les deux. Si les quatre le sont, H19 ne dit pas
« entrer quand le SAR/h est bas » — elle dit « ne pas entrer », comme
H9 et H14. Ce serait le troisième résultat du dossier à ne parler que
de s'abstenir, et il faudra le dire au lieu de l'habiller en signal.

**Le handicap est connu d'avance.** Couper par date place la seconde
moitié presque entièrement **après le 5 août**, là où tous les edges
mesurés disparaissent. Si H19 survit là, elle vaut plus cher que les
autres ; si elle meurt, on ne saura pas distinguer « fausse » de
« tuée par la cassure ». Ce sera écrit dans le verdict.

### Ce qu'on ne pré-enregistre PAS, et pourquoi

Le REPL propose une seconde piste : filtrer selon **l'identité du
premier allumeur** (`M206102, 22 allumages, −78,65 €/fenêtre`). Vingt-
deux observations. Sous la barre de 54, quelle que soit la moyenne.
La règle du §0 vaut aussi quand le chiffre nous plaît — cette piste
attend le gel, elle n'a pas de numéro.

---

## H20 — Le flux d'il y a dix minutes, connu à l'entrée

**ÉCRITE LE 14/08 À 20:15, AVANT TOUTE MESURE.** Déclarée d'avance,
elle n'entre pas dans le compteur du §0.

**D'où elle vient, et pourquoi j'avais tort de l'écarter.** J'ai repris
à mon compte la conclusion « le flux SierraChart est différé de 10 min,
donc aucune règle d'orderflow n'est exploitable en direct ». C'est
faux tel quel. Un flux retardé **ne supprime pas le filtre, il définit
la variable** : à l'instant T on connaît l'état du flux à T−10, et
cette valeur-là est parfaitement disponible en direct. La seule
question ouverte est de savoir si un décalage de dix minutes détruit
le contenu prédictif. Ça se mesure ; ça ne se décrète pas.

**Énoncé.** L'état du flux **à T−10**, connu à T, sépare les allumages
de grand timeframe (x10/x20/x30/x60) qui paient de ceux qui ne paient
pas.

### Le test, tel qu'il sera exécuté

**La cible mesurée** est le PnL moyen de **tous les tickets entrés dans
l'épisode** ouvert par cet allumage — c'est la décision réelle de la
stack (« prendre ou non les entrées de cet épisode »), pas le résultat
du grand tout seul.

**L'unité est l'ÉPISODE, pas le ticket.** Au 14/08 il y a 124 épisodes.

**DEUX camps, pas quatre.** 124 épisodes coupés en quartiles donnent
~31 par cellule, sous la barre de 54 : le test serait mort-né. On coupe
donc à la **médiane**, deux camps de ~62. Ce choix est fait ici,
maintenant, avant d'avoir vu la moindre valeur. Les quartiles pourront
être affichés, mais comme description et jamais comme verdict.

**Prédiction.** Le camp « flux favorable à T−10 » bat le camp
« défavorable », avec un écart dont le `t` dépasse 1,96 (comparaison
annoncée d'avance).

**Critère de réfutation.** H20 est fausse si l'écart entre les deux
camps a un `t < 1,96`, **ou** si une cellule tombe sous 54 épisodes —
auquel cas on écrit qu'on n'a rien mesuré, pas qu'on n'a rien trouvé.

### Ce qui la rendrait vraie par construction — à vérifier AVANT

**Le piège principal, et il tuerait tout : H20 pourrait n'être que H9
déguisée.** Le flux est mauvais le matin — `CARNAGE` de 09h à 12h dans
`panel_orderflow` — c'est-à-dire exactement hors séance US, là où H9 dit
déjà de ne pas trader. Un test naïf trouverait donc un écart qui ne
serait que la redécouverte de l'heure. **Le test se fera donc À
L'INTÉRIEUR DE LA SÉANCE US SEULEMENT.** Si l'effectif n'y suffit pas,
la conclusion à écrire est « non testable à ce stade », jamais un
résultat obtenu en relâchant cette contrainte.

**La fenêtre de flux doit se terminer STRICTEMENT avant T−10.** Si elle
touche l'allumage, même d'une minute, on relit l'événement dans son
propre miroir et l'effet est garanti.

**L'ER de la barre qui contient l'entrée est postérieur.** Il faut la
barre précédente CLÔTURÉE. C'est ce que `_er_prec` fournit ; on
vérifiera dans le code que c'est bien celle-là qui est lue.

**Le délai de dix minutes est une affirmation, pas une mesure.** Il faut
le vérifier sur les horodatages du flux lui-même, pas sur l'heure
d'écriture du fichier par la machine. Si le vrai délai est de vingt
minutes, le test construit sur dix est faux dans le sens flatteur.

**Le signe attendu est celui d'une ABSTENTION.** Comme H9 et H14, H20
dira probablement quand ne pas entrer. Si les deux camps sont négatifs
et que l'un l'est moins, il faut l'écrire ainsi et non l'habiller en
signal d'entrée.

---

## H21 — Séance US et jambe fraîche sur M5

**ÉCRITE LE 14/08 À 21:00, AVANT TOUTE MESURE NOUVELLE.** Déclarée
d'avance, elle n'entre pas dans le compteur du §0. Mais elle est née
d'une cellule déjà vue, et c'est une différence qui doit rester
visible : voir plus bas.

**L'énoncé.** Un signal entré **pendant la séance US** (15h30-19h30) et
dont le gap HLC **M5 est en `WIDENING`** (`self_mom`, la jambe verte
s'écarte de la rouge) fait mieux que la moyenne des signaux de la même
période.

**D'où elle vient — et l'aveu qui va avec.** Cette cellule est le
**maximum de 78 paires** de la matrice de croisement du 14/08. Elle n'a
pas été prédite ; elle a été trouvée en regardant. Ce qui la distingue
des soixante-dix-sept autres n'est pas sa valeur, c'est son
**comportement à travers la cassure du 5 août** :

```
AVANT  : +25,32 sur 96 signaux    (référence +9,37)  ->  +15,95 au-dessus
DEPUIS : +5,58 sur 250 signaux    (référence -5,46)  ->  +11,04 au-dessus
```

Là où la séance US seule perd **86 %** de sa prime sur la référence
(+20,76 → +3,00), ce croisement n'en perd que **31 %**. C'est le seul
candidat d'entrée du dossier positif des deux côtés de la cassure.

### Le test, tel qu'il sera exécuté

**L'unité est le SIGNAL**, jumeaux 206/207 fusionnés — même règle que
`_signals()` de `rails_trades_panel.py`, sinon un signal compte deux
fois.

**La mesure se fait sur des données NEUVES**, à partir du 15/08. Les
2 424 signaux qui ont produit l'hypothèse ne peuvent pas la tester.

**Prédiction.** Sur les signaux postérieurs au 15/08, la cellule
`séance US + M5 WIDENING` bat la moyenne de la même période d'un écart
dont le `t` dépasse 1,96 — seuil d'une comparaison annoncée d'avance,
puisque c'est désormais le cas.

**Critère de réfutation.** H21 est fausse si l'écart a un `t < 1,96`,
**ou** s'il change de signe, **ou** si la cellule reste sous 54 signaux
— auquel cas on écrit « non testable », pas « non trouvée ».

### Ce qui la rendrait vraie par construction — à vérifier AVANT

**Elle pourrait n'être que H9 avec un accessoire.** La séance US porte
déjà +3,00 sur la référence post-cassure. Il faut donc mesurer l'écart
**à l'intérieur de la séance US seule** : `M5 WIDENING` contre
`M5 non-WIDENING`, toutes deux en séance. Si l'écart disparaît là, H21
n'ajoute rien à H9 et doit être écrite comme telle.

**Le seuil honnête n'est pas 1,96 aujourd'hui, il l'est demain.** À
z = 2,9 il faut 248 signaux pour démontrer 11,04 € ; la cellule en a
250. Elle passe de deux signaux. Mais à z = 3,3 — le seuil d'un maximum
choisi parmi 78 — il en faudrait 321, et elle échoue. **C'est pourquoi
elle est pré-enregistrée et non adoptée.** Le compteur repart à un sur
données neuves ; c'est tout ce que la pré-inscription achète, et c'est
déjà beaucoup.

**`self_mom` et non `mom`.** Le champ de trajectoire du gap porte ce
nom dans les enregistrements. Une première version du lecteur cherchait
`mom` et aurait renvoyé une cellule vide, lue comme « le widening ne
croise avec rien ». À revérifier dans tout code qui testera H21.

**Le WIDENING de M5 n'est pas indépendant de celui de M1, M3, M15.**
Les quatre blocs portent les mêmes signaux repartitionnés. Si le test
est reconduit sur une autre unité de temps et « confirme », ce n'est
pas une confirmation.

### Ce que H21 n'autorise pas

Elle ne dit rien sur le sens, ni sur la taille, ni sur la sortie. Elle
ne remplace aucune abstention : H9 reste au-dessus d'elle dans l'ordre
de décision. Et tant qu'elle n'est pas mesurée hors échantillon, **elle
ne justifie aucun changement de paramètre pendant le gel.**

---

## H22 — Ne pas entrer quand les trois indices sont alignés sur M15

**ÉCRITE LE 14/08 À 21:30, ALORS QUE LA QUESTION EST ENCORE
INDÉCIDABLE.** C'est le point de cette hypothèse : il manque environ
deux séances de données pour trancher, et elle est posée maintenant
plutôt que dans deux jours, quand on saurait déjà de quel côté ça
penche. Écrite après, elle ne vaudrait rien.

**L'énoncé.** Un signal entré alors que le consensus HLC M15 des trois
indices est `ALIGNED` (`ALIGNED_BULL` ou `ALIGNED_BEAR`) fait moins
bien que la moyenne des signaux de la même période.

### L'état exact au 14/08, et la date d'échéance

```
DEPUIS le 05/08   M15 ALIGNE   n = 941   moy -10,49   vs réf -5,04
                               n requis à z = 2,9 : 1 193
```

941 sur 1 193, soit **79 %** de l'exigence. À ~118 signaux `M15 ALIGNE`
par séance depuis le 5 août (941 sur 8 séances), il manque **environ
deux séances** : la question devient tranchable autour du **18 août**.

C'est la première fois dans ce dossier qu'on peut **dater** une
décision au lieu d'écrire « il faudrait plus de données ».

### Ce que l'abstention coûterait, chiffré d'avance

`M15 ALIGNE` couvre **941 des 1 645 signaux** post-cassure, soit
**57 %**. S'abstenir là supprime plus de la moitié de l'activité.

Le contrefactuel arithmétique, sur la fenêtre qui a produit
l'hypothèse : retirer ces 941 signaux laisse 704 signaux dont la
moyenne passe de **−5,46 à +1,26 €/signal**.

**Ce chiffre est vrai et ne prouve rien.** Le filtre a été choisi
*parce qu'il était le plus négatif des treize* : retirer le pire d'un
lot fait monter le reste par construction. Il est écrit ici pour
qu'on sache ce qu'on jouerait, pas comme un argument.

### Le test, tel qu'il sera exécuté

**Dès que `n ≥ 1 276`** — le seuil corrigé, voir plus bas — lire
l'écart à la référence de la période et son `t`.

**L'unité est le SIGNAL** (jumeaux 206/207 fusionnés), et le **nombre
de séances distinctes** sera affiché à côté : 941 signaux répartis sur
8 séances ne valent pas 941 observations indépendantes.

**Critère de réfutation.** H22 est fausse si l'écart a un `|t| < 2,9`
une fois l'effectif atteint, **ou** s'il devient positif, **ou** si
l'effet ne tient que sur l'une des deux directions (voir ci-dessous).

### Ce qui la rendrait vraie par construction — à vérifier AVANT

**Le seuil n'est pas 2,9 mais ~3,0, et l'exigence ~1 276.** `M15
ALIGNE` a été retenu comme **le plus négatif de treize filtres**. Le
choix parmi treize monte la barre. Le chiffre de 1 193 vaut pour une
comparaison annoncée d'avance ; celui qui s'applique ici est 1 276.
La différence est d'une demi-séance, mais elle doit être écrite.

**`ALIGNED_BULL` et `ALIGNED_BEAR` doivent être lus SÉPARÉMENT.** Si
l'effet ne vient que du camp baissier, ce n'est pas « l'alignement qui
coûte », c'est un biais directionnel sur une fenêtre où le marché a
baissé — et ça ne survivra pas à un marché haussier. **Ce contrôle est
obligatoire avant tout verdict.**

**H22 n'existait pas avant le 5 août.** Sur la période antérieure,
`M15 ALIGNE` valait `+9,54` contre une référence de `+9,37`, soit un
écart de **+0,16** : indiscernable. Ce filtre n'est donc pas passé de
bon à mauvais, il est passé de **neutre** à mauvais. C'est mieux qu'un
changement de signe, et c'est quand même un avertissement : le
phénomène est **postérieur à la cassure**, et rien ne garantit qu'il
survive au régime suivant. Si le marché change à nouveau début
septembre, H22 devra être re-mesurée avant d'être conservée.

**Le mécanisme n'est pas une preuve.** L'histoire — « tout le monde
d'accord = mouvement déjà installé = entrée tardive », cohérente avec
H10 — est une explication *après* le chiffre. Elle rend le résultat
plausible, elle ne le rend pas vrai, et elle ne doit jamais servir à
sauver H22 si le test échoue.

**Ne pas la « confirmer » sur une autre unité de temps.** M1, M3, M5 et
M15 partitionnent les **mêmes** signaux. `M1 ALIGNE` et `M3 ALIGNE`
sont aussi négatifs (−1,62 et −1,75) : ce n'est pas une confirmation
indépendante, c'est le même échantillon vu sous un autre angle.

**Le croisement n'apporte rien.** `M1 WIDENING × M15 ALIGNE` fait
−5,40 sur 511 signaux, contre −5,04 sur 941 pour `M15 ALIGNE` seul :
un écart à peine plus grand pour la moitié de l'effectif. **La règle
simple bat la règle croisée** — à ne pas compliquer pour faire joli.

### Ce que H22 n'autorise pas

Elle ne dit rien du sens, de la taille, ni de la sortie. Elle
n'autorise **aucun changement de paramètre pendant le gel** : c'est une
mesure à faire, pas une règle à appliquer. Et si elle passe, elle
devra encore être vérifiée hors échantillon avant d'entrer en
production — comme H9, qui a passé le seuil sur une période et ne le
passe plus sur la suivante.

---

## H23 — Ne pas entrer en séance US quand les rails sont MID

Écrite le 14/08/2026 à 22:20, **après** avoir vu le chiffre. C'est une
hypothèse, pas un résultat.

### Ce qu'on a vu

Sur la carte des profils (`profils_croises.py --ut M5 --actif TOUS`),
côté **DEPUIS** la cassure du 5 août — 1 645 signaux, référence
**−5,46 €** :

| profil | n | moyenne | écart | t | prof. |
|---|---|---|---|---|---|
| `US + MID` | 222 | −13,21 | −7,75 | −1,93 | 2 |
| `US + MID + PASALIGNE` | 88 | −22,52 | −17,06 | −2,67 | 3 |
| `US + MID + CHURN` | 69 | −20,24 | −14,78 | −2,05 | 3 |
| `US + MID + horsCHURN + PASALIGNE` | 56 | −22,77 | −17,31 | −2,16 | 4 |
| `MID + STEADY` | 69 | −21,50 | −16,04 | −2,22 | 2 |

`MID` est le seau de rails le plus systématiquement rouge de la page,
et il l'est à **profondeur 2**, c'est-à-dire sans qu'on ait eu besoin
d'empiler des conditions pour le faire apparaître.

### L'hypothèse, à la profondeur 2 et pas plus

**`séance US + rails MID` sous-performe la référence de sa propre
période d'au moins 7,75 € par signal.**

C'est délibérément la forme la *moins* impressionnante du tableau.
Descendre à `US + MID + PASALIGNE` double l'écart (−17,06) et divise
l'effectif par deux et demi (88) : l'écart grandit parce que
l'échantillon rétrécit, c'est le mécanisme habituel. La forme à
profondeur 2 est la seule qui garde de quoi être mesurée, et elle ne
dépend d'**aucune unité de temps** — elle ne contraint ni le gap ni le
consensus, donc elle n'est pas quatre fois le même échantillon.

### Le critère de falsification, et sa date

Avec σ ≈ 60 € et e = 7,75 €, la règle du §0 `n > (z·σ/e)²` donne :

- **z = 1,96**, parce que cette hypothèse-ci est annoncée d'avance et
  qu'elle est seule : **n > 230**.
- z = 4,14, le seuil de Bonferroni des 1 440 cellules énumérées pour
  la trouver : n > 1 027. C'est le chiffre honnête pour les données
  qui l'ont suggérée — et c'est pourquoi on ne les réutilise pas.

Sur **données neuves à partir du 15/08**, à raison d'environ 206
signaux par séance dont ~13,5 % tombent dans `US + MID`, soit ~28 par
séance, les 230 signaux requis sont atteints en **8 séances, autour du
26 août**. (Le taux est estimé sur 1 645 signaux / 8 séances depuis le
5 août : à revérifier plutôt qu'à croire.)

**H23 est fausse si**, sur ≥ 230 signaux `US + MID` postérieurs au
15/08, l'écart à la référence de la même période est ≥ 0, ou si son
intervalle de confiance à 95 % contient 0.

### Ce qui la rendrait vraie par construction

Trois pièges, et le troisième est le vrai.

**Compter les jumeaux deux fois.** Les magic 206/207 sont fusionnés en
un signal par `signaux()`. Un comptage par ticket gonflerait n de
~50 % et ferait passer le seuil sans qu'aucune information nouvelle
n'arrive.

**Rechercher la profondeur.** Si le test à profondeur 2 échoue, il
sera tentant de sauver H23 en la relisant à `+ PASALIGNE`. C'est
interdit : ce serait choisir la coupe après avoir vu le résultat, dans
un espace où l'on sait déjà que 354 profils sur 720 ont un effectif
suffisant.

**Confondre l'abstention avec un gain.** H23 ne dit pas que ne pas
prendre ces signaux fait gagner 7,75 € par signal évité. Elle dit
qu'ils sont plus mauvais que la moyenne d'une période **qui perd déjà
5,46 € par signal**. S'abstenir sur `US + MID` remonte la moyenne des
signaux restants ; ça ne la rend pas positive, et ça ne dit rien de ce
que devient le compte. Le seul énoncé défendable est comparatif.

### Le voisin qui doit servir d'avertissement

Sur la même carte, la famille du gap **change de signe à la cassure** :

- **AVANT** : `US + NARROWING`, n=89, écart **+30,20**, t = **+4,75**
  — une des cinq lignes qui passent le seuil de Bonferroni.
- **DEPUIS** : c'est `US + WIDENING` qui tient le haut de la frontière
  (n=250, +11,04), et `NARROWING` a disparu des neuf points de la
  frontière.

Un filtre dont le **sens s'inverse** au changement de régime ne peut
pas devenir une règle permanente. Il exigerait un détecteur de régime
— lequel devrait lui-même être annoncé d'avance, faute de quoi on
n'aurait fait que déplacer le sur-ajustement d'un cran. C'est la
raison pour laquelle H23 porte sur `MID`, qui est rouge des deux côtés
de sa propre période, et non sur la trajectoire du gap.

### Ce que dit la carte, et qu'il ne faut pas oublier

Les **cinq** profils qui passent |t| ≥ 4,14 sont **tous du côté
AVANT**. Aucun profil postérieur au 5 août n'atteint son seuil, sur
1 440 cellules énumérées. La référence elle-même est passée de
**+9,37** à **−5,46** : c'est un écart de près de 15 € par signal, et
c'est le seul fait de cette page qui ne demande aucune statistique
pour être vu.

---

## H24 — Séance US, gap M1 plat, pas de consensus, flux propre

Écrite le 15/08/2026 à 00:20, **après** avoir vu le chiffre. C'est la
première hypothèse d'ENTRÉE depuis H21 ; les trois précédentes
disaient quand s'abstenir.

### Ce qu'on a vu

Carte des profils, côté **DEPUIS** la cassure, séance US, rails
indifférent, actif TOUS — 613 signaux dans la page, référence de
période **−5,46 €/signal** :

```
ut M1   gap indiff / consensus PAS ALIGNE / churn CLEAN
        n = 92    moyenne +20,2    ecart +25,66    t = +4,11
```

C'est la case la plus verte de la page et elle est **mesurable** :
92 signaux, bien au-dessus des 54 requis pour qu'un `t` veuille dire
quelque chose.

### L'énoncé

**Un signal entré en séance US, dont le gap HLC M1 n'est ni en
expansion ni en contraction (`indiff`), dont le consensus M1 n'est pas
aligné, et dont le churn est `CLEAN`, bat la référence de sa propre
période.**

Lecture possible — et elle n'est qu'une histoire : marché ouvert, pas
de direction commune entre les trois indices, géométrie propre. Le
coup se jouerait sur un décrochage relatif plutôt que sur un mouvement
d'ensemble. **Cette explication ne fait pas partie de l'hypothèse** et
ne doit jamais servir à la sauver si le test échoue.

### L'avertissement principal : M1 est le maximum de quatre

La même cellule, sur les quatre unités de temps, porte les **mêmes
signaux repartitionnés** :

| ut | n | moyenne | t |
|---|---|---|---|
| **M1** | 92 | **+20,2** | +4,11 |
| M3 | 85 | +8,6 | +2,17 |
| M5 | 76 | +4,5 | +1,45 |
| M15 | 85 | +14,5 | +3,06 |

M1 n'a pas été choisie pour une raison théorique : **c'est la plus
haute des quatre**. Une hypothèse bâtie sur le maximum d'un jeu de
vues du même échantillon est le cas d'école du sur-ajustement. Si M1
échoue sur données neuves, il sera interdit de se rabattre sur M15 —
ce serait refaire le même choix une seconde fois.

Le fait que les quatre soient positives est en revanche informatif :
la famille `PAS ALIGNE + CLEAN` penche du bon côté partout, entre
+4,5 et +20,2. C'est la seule chose que ce tableau démontre.

### Le critère de falsification, et sa date

σ ≈ 60 €, écart mesuré e = 25,66 €, règle du §0 `n > (z·σ/e)²` :

- **z = 1,96** — comparaison annoncée d'avance et seule : **n > 22**.
  Ce chiffre est écrit pour mémoire ; il ne s'applique pas ici.
- **z = 4,74** — le seuil de Bonferroni des 23 040 cellules énumérées
  pour la trouver, majoré par le choix de M1 parmi quatre :
  **n > 123**. **C'est celui qui compte.**

À ~11,5 signaux de ce profil par séance (92 sur 8 séances depuis le
5 août), les 123 signaux **neufs** sont atteints en **environ onze
séances, soit autour du 1er septembre 2026**.

**H24 est fausse si**, sur ≥ 123 signaux de ce profil postérieurs au
15/08, l'écart à la référence de la même période est ≤ 0, ou si son
intervalle de confiance à 95 % contient 0.

### Ce qui la rendrait vraie par construction

**La cousine instable.** `WIDENING / PAS ALIGNE / CLEAN` en M1 affiche
**+42,5 sur 42 signaux** — deux fois l'écart, moins de la moitié de
l'effectif, et sous la barre des 54. C'est la même idée dans sa
version invérifiable. Elle est **exclue d'avance** : si H24 échoue, on
ne la remplace pas par sa cousine.

**Changer d'unité de temps.** Interdit, voir ci-dessus.

**Compter les jumeaux deux fois.** Les magic 206/207 sont fusionnés en
un signal par `signaux()`. Un comptage par ticket gonflerait n de
~50 % et ferait passer le seuil sans qu'aucune information nouvelle
n'arrive.

**Oublier que la référence est négative.** +20,2 est un niveau, pas un
écart : la période perd 5,46 € par signal. Ici, pour une fois, la
cellule est franchement positive en niveau — c'est ce qui la distingue
de H22 et H23, qui ne parlent que de moindre perte.

### Ce que H24 n'autorise pas

Elle ne dit rien du sens, ni de la taille, ni de la sortie, et
**n'autorise aucun changement de paramètre pendant le gel**. Elle
n'entre en concurrence avec aucune abstention : H22 et H23 restent
au-dessus d'elle dans l'ordre de décision. Une entrée qu'une
abstention interdit reste interdite.

---

## H25 — Flux propre, gap M1 en expansion, pas de consensus

Écrite le 15/08/2026 à 00:30, **après** avoir vu le chiffre. C'est la
**seule ligne postérieure au 5 août** qui passe son seuil sur la carte
complète — et elle le passe de 0,01.

### Ce qu'on a vu

Carte des profils sur les quatre unités de temps, actif TOUS,
5 400 cellules énumérées, seuil de Bonferroni **|t| ≥ 4,44** :

```
DEPUIS  ut M1   CLEAN + WIDENING + PASALIGNE
        n = 69   moyenne +26,72   ecart +32,18   t = +4,45
```

Sur treize lignes qui franchissent le seuil, **douze sont antérieures
au 5 août**. Celle-ci est la treizième, et la seule d'après.

### L'énoncé

**Un signal dont le churn est `CLEAN`, dont le gap HLC M1 est en
`WIDENING` et dont le consensus M1 n'est pas aligné bat la référence
de sa propre période.**

Ni séance, ni rails : profondeur 3, et aucune contrainte d'horaire.

### Pourquoi « passer le seuil » ne veut presque rien dire ici

**Passer le seuil et avoir l'effectif requis sont la même phrase.** À
σ = 60 et e = 32,18, la règle du §0 avec z = 4,44 exige
`n > (4,44 × 60 / 32,18)² = 69`. La cellule en a **69**. Le `t` de
4,45 ne dit rien de plus que « n est arrivé pile au chiffre requis ».

**Et le verdict dépend d'une constante estimée.** σ ≈ 60 € est une
estimation, pas une mesure. Avec σ = 62, le même écart donne
t = 4,31 : la ligne ne passe plus. Une conclusion qui bascule sur la
deuxième décimale d'un paramètre supposé n'est pas une conclusion.

**C'est le maximum de 5 400 cellules.** Le seuil de Bonferroni corrige
précisément ce fait, et il est franchi de 0,01. Autant dire qu'il ne
l'est pas.

### Le critère de falsification, et sa date

- **z = 1,96**, annoncée d'avance et seule : **n > 14**. Écrit pour
  mémoire ; trop peu pour qu'on s'y fie.
- **z = 4,44**, le seuil d'énumération : **n > 69**. C'est celui qu'on
  retient, parce qu'on ne peut pas faire semblant de ne pas avoir
  regardé 5 400 cases.

À ~8,6 signaux de ce profil par séance (69 sur 8 séances), les 69
signaux **neufs** sont atteints en **huit séances, soit autour du
26 août 2026** — la même échéance que H23.

**H25 est fausse si**, sur ≥ 69 signaux de ce profil postérieurs au
15/08, l'écart à la référence de la même période est ≤ 0, ou si son
intervalle de confiance à 95 % contient 0.

### Ce qui la rendrait vraie par construction

**Elle est encore un maximum de quatre unités de temps.** La même
famille donne, sur les mêmes signaux repartitionnés : M15 → n=75,
écart +21,90, t=3,16 ; M5 → n=77, +12,92, t=1,89. M1 est la plus
haute des trois mesurables. Si M1 échoue, se rabattre sur M15 est
interdit.

**Elle chevauche H24.** `US + CLEAN + PASALIGNE` (H24, n=92) et
`CLEAN + WIDENING + PASALIGNE` (H25, n=69) partagent une partie de
leurs signaux : ce ne sont pas deux tests indépendants. Si les deux
passent, ça ne fait pas deux confirmations — c'est la même famille
`CLEAN + PASALIGNE` vue sous deux angles.

**Compter les jumeaux deux fois** gonflerait n de ~50 % et ferait
franchir le seuil à ce qui ne le franchit pas.

---

## H26 — Pas de consensus M15 : le revers de H22, et rien de plus

Écrite le 15/08/2026 à 00:30. **Cette hypothèse n'apporte aucune
information nouvelle par rapport à H22.** Elle est écrite pour que ce
fait soit consigné plutôt que redécouvert.

### Ce qu'on a vu

```
DEPUIS  ut M15   PASALIGNE seul
        n = 704   moyenne +1,27   ecart +6,73   t = +2,98
```

704 signaux : **43 % de toute l'activité post-cassure**, à profondeur
1, sans aucun empilement. C'est le point de la frontière qui offre le
plus grand effectif au-dessus de sa référence.

### Pourquoi ce n'est PAS une découverte

`M15 ALIGNE` et `M15 PAS ALIGNE` **partitionnent l'échantillon** :
941 + 704 = 1 645, la totalité des signaux post-cassure. Leurs écarts
à la moyenne commune sont donc de signes opposés **par arithmétique**,
pas par observation.

H22 dit : `M15 ALIGNE` fait −5,04 sous la référence sur 941 signaux.
H26 dit : le complément fait +6,73 au-dessus sur 704. **C'est la même
mesure, écrite deux fois.** Le contrefactuel calculé pour H22 le
montrait déjà : retirer les 941 alignés laissait 704 signaux à
+1,26 €/signal — exactement la moyenne de H26 à un centime près.

**Conséquence : H26 ne compte pas comme une seconde confirmation de
H22, et H22 ne compte pas comme une confirmation de H26.** Si les deux
sont « validées » le même jour, une seule chose aura été démontrée.

### À quoi elle sert quand même

À changer de **rôle**. H22 est une règle d'abstention : elle dit de ne
pas entrer sur 57 % des signaux. H26 est la même chose formulée comme
règle d'entrée : elle dit ce qui reste, et sur quel effectif. Les deux
lectures n'ont pas la même conséquence opérationnelle, et c'est la
seule raison d'écrire les deux.

### Le critère de falsification, et sa date — la plus proche du dossier

σ ≈ 60, e = 6,73 :

- **z = 1,96**, annoncée d'avance : **n > 305**.
- **z = 4,44**, seuil d'énumération : **n > 1 567**.

Comme H22 porte déjà la même mesure et qu'elle a été pré-enregistrée
le 14/08 à 21:30 **avant** que la question soit tranchable, c'est le
seuil annoncé d'avance qui s'applique : **305 signaux neufs**.

À ~88 signaux `M15 PAS ALIGNE` par séance (704 sur 8), les 305 sont
atteints en **environ trois séances et demie, soit autour du
20 août 2026**. C'est la première échéance du dossier, avant H22 le
18 — dont elle est le revers — et avant H23 le 26.

**H26 est fausse si**, sur ≥ 305 signaux `M15 PAS ALIGNE` postérieurs
au 15/08, l'écart à la référence de la même période est ≤ 0.

### Ce qui la rendrait vraie par construction

**Lire H22 et H26 comme deux résultats.** C'est le piège principal, et
il est écrit en tête de cette entrée.

**Oublier que +1,27 est un niveau proche de zéro.** La référence perd
5,46 € par signal ; s'abstenir sur les alignés ramène le reste à
**+1,27**, pas à un gain franc. Sur 704 signaux, c'est une activité
qui cesse de coûter, pas une activité qui rapporte. Le dire autrement
serait mentir sur l'ordre de grandeur.

**`ALIGNED_BULL` et `ALIGNED_BEAR` doivent être lus séparément**, ici
comme dans H22 : si l'effet ne vient que d'un camp directionnel, il ne
survivra pas à un marché qui change de sens.

---

## Une réserve qui pèse sur H22 à H26 — la cassure unique

Écrite le 15/08/2026 à 00:40, après une observation graphique de
l'utilisateur qu'aucun de nos outils n'aurait produite.

### L'observation

Le 13/08 vers 15h, les trois indices cassent leur range. **Un seul
tient.** Le US100 franchit ~29 846 et reste au-dessus (30 044 au
moment où c'est écrit). Le US30 monte à 53 984 et rend tout — il
clôture sous sa cassure. Le US500 est intermédiaire.

### Ce que ça met en cause

**Toutes les mesures de ce dossier reposent sur UNE date de cassure,
le 5 août, appliquée aux trois actifs.** Cette date a été choisie à
l'œil sur des séries agrégées.

Si le US100 a changé de régime le 13, alors :

- sa période « DEPUIS » **mélange deux régimes** ;
- la référence commune de **−5,46 €/signal** est une moyenne qui peut
  ne décrire aucun des trois actifs ;
- et les écarts de H22 à H26, tous calculés contre cette référence,
  portent une erreur dont on ne connaît ni le signe ni la taille.

Ces hypothèses ne sont pas fausses pour autant. Leur **référence** est
possiblement mal posée, et ça doit être écrit avant de les mesurer,
pas après le verdict.

### Pourquoi nos outils ne pouvaient pas le montrer

La carte texte est sortie en `--actif TOUS`, au motif que les découpes
par actif divisent l'effectif par trois. C'est vrai en moyenne — et
c'est exactement ce qui **efface un changement de régime propre à un
actif**. L'agrégation est faite pour lisser ; un décrochage isolé est
précisément ce qu'elle lisse.

Il y a une ironie utile : `PASALIGNE`, autour de quoi tournent H24,
H25 et H26, **est** la signature de cet état — un indice qui tient
pendant que les autres rendent. La carte contenait donc le phénomène,
sous forme de statistique agrégée, jamais comme un événement daté et
attribué. Et `PASALIGNE` ne dit pas **lequel** décroche : la lecture
graphique le dit, la donnée non.

### Ce qui a été mesuré, le 15/08 à 00:42

`cassure_par_actif.py` cherche, pour chaque actif, la date qui sépare
le mieux ses signaux en deux moitiés de moyennes différentes, et
calibre ce maximum par **permutation de journées en bloc** — 400
tirages, graine fixe. Résultat :

| actif | meilleure date | avant → après | écart | p |
|---|---|---|---|---|
| **US500** | 05/08 | +22,00 → −7,45 | **−29,45** | **0,005** |
| TOUS | 05/08 | +9,37 → −5,46 | −14,83 | 0,040 |
| US30 | 05/08 | +7,09 → −5,73 | −12,82 | 0,115 |
| US100 | 05/08 | +2,83 → −3,55 | −6,38 | 0,382 |

**La date du 5 août est confirmée pour les quatre.** Sur 8 à 11 dates
candidates par actif, aucune ne sépare mieux. Le choix fait à l'œil
était le bon, et ce n'était pas acquis d'avance.

**La réserve initiale — « un actif se casse peut-être ailleurs » — est
donc levée.** Aucun actif ne réclame une autre date.

### Mais elle est remplacée par une autre, chiffrée

**Les amplitudes n'ont rien à voir entre elles.** Le US500 perd
29,45 € par signal à la cassure ; le US100 en perd 6,38, indiscernable
du bruit (p = 0,38). Ce n'est pas le même événement vécu trois fois :
c'est un choc violent sur le S&P, moyen sur le Dow, et quasi nul sur
le Nasdaq.

**Conséquence directe sur H22 à H26.** Les références post-cassure par
actif valent **−3,55 (US100), −5,73 (US30), −7,45 (US500)**, contre
**−5,46** en commun. La référence unique est à peu près centrale —
elle ne ment pas grossièrement. Mais **l'étalement entre actifs vaut
3,9 €**, quand l'écart testé par H26 vaut **+6,73**.

Du même ordre de grandeur. **Une hypothèse mesurée sur `TOUS` peut
donc se déplacer d'un tiers de son effet par simple changement de la
composition par actif du flux** — sans qu'aucune règle de marché
n'ait bougé.

**Ce que ça impose au moment de trancher.** Les cinq échéances (20,
18, 26 août, 1er septembre) devront être lues **avec la répartition
par actif des signaux neufs affichée à côté du verdict**. Si cette
répartition diffère de celle de la fenêtre de découverte, l'écart
mesuré n'est pas comparable à l'écart annoncé, et il faut le dire
avant de conclure — pas après.

### Le chiffre qui justifie tout l'appareil

Sous H0, sur les vraies données, le maximum de |t| obtenu **en
cherchant la meilleure date dans du bruit de même structure** vaut en
médiane **1,53** pour US100, **2,36** pour US30, **3,22** pour TOUS.

Chercher rapporte deux à trois, systématiquement, sans qu'il y ait
quoi que ce soit à trouver. Ce n'est plus une mise en garde
théorique : c'est mesuré sur ce dossier.

---

## H27 — Sortir d'un range par le BAS dit quelque chose du quart d'heure suivant

Écrite le 17/08/2026 à 09:00, **après** avoir vu le tableau. Elle
porte sur un MOTIF, pas sur la meilleure case — et c'est délibéré.

### Ce qu'on a vu

`breakout_range.py`, 18 journées, 42 597 cycles, pas de 10 s. Sortie
d'un range défini par le plus haut / plus bas des W minutes
précédentes, période réfractaire de W, témoin apparié à moins de 10 %
de la largeur du bord sans le franchir.

Sur 51 cellules, la permutation par blocs de journées donne
**p = 0,010** : maximum observé 25,3 points, médiane sous H0 13,5,
seuil 95 % à 20,1.

**Mais ce maximum est `US500 60m BAS` sur 28 événements.** Ce n'est
pas lui l'hypothèse.

### Le motif, qui est l'hypothèse

Les six meilleurs écarts sont **tous à la baisse**. Les seules valeurs
négatives sont des cassures **hautes à horizon 120 minutes**. Et
l'effet est concentré au quart d'heure : à 15 min les écarts sont les
plus grands, à 120 min ils s'annulent ou s'inversent.

Forme retenue — la plus simple et la plus peuplée, **fenêtre 15 min,
sens BAS, horizon 15 min**, trois actifs :

| actif | n | continue | témoin | écart |
|---|---|---|---|---|
| US100 | 141 | 51,1 % | 38,8 % | **+12,2** |
| US500 | 141 | 43,3 % | 36,5 % | **+6,8** |
| US30 | 149 | 45,6 % | 47,3 % | **−1,7** |
| **cumulé** | **431** | | | **+5,6** |

**L'énoncé.** Une sortie de range par le bas est suivie, quinze
minutes plus tard, d'un maintien sous le niveau franchi plus souvent
qu'un simple passage au voisinage de ce niveau, d'au moins **5,6
points de pourcentage**.

### Pourquoi le témoin est indispensable ici

À la hausse, le taux de base est de **45 à 64 %** : sur ces dix-huit
journées les indices montent, donc « être encore au-dessus » quinze
minutes plus tard n'a rien de remarquable. À la baisse il tombe à
**28 à 50 %**. Sans témoin apparié on aurait conclu que les cassures
hautes « marchent mieux » — alors qu'elles ne font que suivre la
dérive de la période.

### Le critère de falsification, et sa date

Écart de deux proportions, p ≈ 0,45, e = 5,6 points :

`n > (1,96 / 0,056)² × p(1−p)` ≈ **303 événements** de ce profil sur
données neuves.

À 431 événements pour 18 journées, soit ~24 par jour tous actifs
confondus, les 303 sont atteints en **13 séances, autour du
30 août 2026**.

**H27 est fausse si**, sur ≥ 303 sorties de range basses postérieures
au 17/08 (fenêtre 15 min, horizon 15 min), l'écart au témoin apparié
est ≤ 0, ou si son intervalle de confiance à 95 % contient 0.

### Ce qui la rendrait vraie par construction

**Prendre le maximum au lieu du motif.** `US500 60m BAS` à +25,3 sur
28 événements est le point le plus sur-ajusté du tableau. Il est exclu
d'avance : si H27 échoue, on ne se rabat pas dessus.

**Oublier que US30 est négatif.** Deux actifs sur trois portent
l'effet ; le troisième va dans l'autre sens (−1,7). Le cumul à +5,6
masque cette dispersion. Si le test réussit globalement mais que US30
reste négatif, il faudra l'écrire — et non prétendre que « ça marche
sur les indices ».

**Empiler les fenêtres.** Une cassure de 15 min est souvent aussi une
cassure de 30 et de 60 : cumuler les trois fenêtres gonflerait n sans
ajouter d'information indépendante. H27 porte sur **la fenêtre 15 min
seule**, exprès.

**Confondre continuation et gain.** Le tableau ne contient **aucune
direction jouable et aucun PnL**. « Le prix est encore sous le niveau
15 minutes plus tard » ne dit rien de ce qu'aurait rapporté une
position — ni du point d'entrée, ni du stop, ni du glissement. Le lien
avec les trades de la stack est une mesure séparée, qui n'a pas été
faite.

### AMENDEMENT du 17/08 à 09:20 — trois hypothèses, pas une

**Le cumulé à +5,6 est retiré.** Il moyenne trois comportements dont
un va à contresens ; une moyenne de choses différentes ne décrit
aucune d'elles.

L'objection, formulée par l'utilisateur : *« chaque asset a son
comportement et on le sait. Le plus volatil en points est l'US30, mais
les volumes sont sur SPX et US100, et le SPX est le plus dur à
transformer en range — c'est lui qui fait tout perdre à la stack. Il y
a des notions de bruit à prendre en compte par actif : les bougies,
les spikes sont totalement différents de l'un à l'autre. »*

Elle est confirmée par nos propres mesures, que j'avais lues sans en
tirer la conséquence : `cassure_par_actif.py` donne au 5 août
**−29,45 € par signal sur US500** (p = 0,005), −12,82 sur US30,
**−6,38 sur US100 dont la rupture n'est même pas détectable**
(p = 0,382). Trois régimes, pas un.

**Cet amendement est écrit AVANT toute nouvelle donnée.** Aucune
mesure postérieure au 17/08 n'a été consultée ; c'est un argument a
priori sur l'unité d'analyse, pas un ajustement au vu d'un résultat.
La distinction est ce qui sépare une pré-inscription corrigée d'un
sauvetage.

**H27a — US100.** Écart observé +12,2 points sur 141 événements.
Seuil : `n > (1,96/0,122)² × p(1−p)` ≈ **64 événements** neufs. À ~7,8
par séance : **environ 8 séances, autour du 27 août**.

**H27b — US500.** Écart observé +6,8 sur 141. Seuil : **≈ 206
événements** neufs. À ~7,8 par séance : **environ 26 séances, autour
du 22 septembre**. C'est loin, et c'est le prix d'un effet deux fois
plus petit.

**H27c — US30, le témoin négatif.** Écart observé **−1,7**. On ne
pré-enregistre pas un effet ici : on pré-enregistre son ABSENCE.
**H27c est fausse si US30 montre, sur ≥ 206 événements neufs, un écart
positif dont l'intervalle de confiance exclut 0.** Si c'est le cas,
c'est l'ensemble du motif qu'il faudra revoir — pas ajouter US30 aux
gagnants.

Les trois sont mesurées séparément et **ne se confirment pas l'une
l'autre** : trois indices corrélés à 90 % ne fournissent pas trois
échantillons indépendants.

### Ce qui manque encore, et qui vient de la même objection

L'événement est aujourd'hui défini sans **unité de bruit propre à
l'actif** : franchir le bord d'un range d'un centième de point compte
autant que le franchir de dix points. Sur l'actif le plus agité en
points, tout franchissement est du bruit ; sur le plus calme, aucun ne
l'est. La correction est un **tampon exprimé dans le bruit propre de
chaque actif** — par exemple k fois la variation médiane par cycle,
avec k balayé comme un axe de la grille et non choisi.

Tant que ce tampon n'existe pas, H27a/b/c portent sur des événements
dont la définition avantage mécaniquement les actifs calmes. C'est
écrit ici pour que le verdict, quel qu'il soit, soit lu avec cette
réserve.

### Ce que H27 n'autorise pas

Aucun changement de paramètre pendant le gel. Elle n'entre en
concurrence avec aucune abstention : H22, H23 et H26 restent au-dessus
d'elle dans l'ordre de décision.

---

## Ce qui ferait abandonner l'exercice

Si, à la fin du gel, aucune cellule du tableau quadruple ne se détache
du bruit une fois le seuil du §0 appliqué, la conclusion à écrire est
« aucun setup ne se distingue sur cette fenêtre » — pas « il faut
découper autrement ». Le droit de redécouper s'achète avec des données
neuves, jamais avec les mêmes.

---

## H28 — Payer l'orderflow SierraChart, ou garder MT5

**Écrite le 17/08 à 10:35, avant d'avoir lu une seule ligne d'un
`.scid`.** C'est tout l'intérêt : fin août, on décidera avec un critère
posé à froid plutôt qu'avec l'impression du moment.

### Ce qui est en jeu

La stack calcule un CVD, une absorption et des bursts à partir de MT5.
Or sur des CFD d'indices, **MT5 ne fournit pas de volume échangé** — il
fournit un compteur de ticks. Le « delta » qui en sort est une
inférence, pas une mesure. SierraChart donne `BidVolume` et `AskVolume`
séparés sur les futures : du volume réel.

Le réel est meilleur par construction. La seule question qui vaut de
l'argent est : **est-ce que la différence change une décision ?**

### Le critère, en trois conditions dont une seule suffit

On paie si **au moins l'une** est vérifiée :

1. le CVD MT5 se trompe de **signe** plus de **25 %** du temps contre le
   CVD SierraChart, sur les instants à fort volume ;
2. le CVD réel prédit le mouvement à +15 min avec un écart au témoin
   **significativement supérieur** à celui du CVD MT5 — même règle, même
   témoin apparié, permutation par journée ;
3. l'orderflow réel montre des événements — publications macro,
   ouvertures, bursts — que MT5 ne voit **pas du tout**.

Sinon on garde MT5, et l'abonnement va ailleurs.

### Ce qui ne comptera pas comme argument

- « Le réel est forcément mieux. » Vrai et hors sujet : la question est
  l'écart mesuré, pas la supériorité de principe.
- Une corrélation élevée entre les deux CVD. Une forte corrélation avec
  25 % de désaccords de signe reste disqualifiante — c'est le signe qui
  décide d'un sens de position, pas l'amplitude.
- Le décalage de dix minutes du flux. Sur de l'historique horodaté il
  ne coûte rien ; il ne compte que pour du live, ce qui est une autre
  décision.

### La limite, écrite d'avance

`MNQU26-CME.scid` fait **1 Ko** : il n'y a pas de Nasdaq dans le flux
disponible. **La rotation tech/value ne sera donc pas validable en
orderflow réel**, quel que soit le résultat de H28. On testera le CVD
sur YM et MES ; la jambe qui portait l'hypothèse d'origine reste hors
d'atteinte, et aucun résultat sur ES/YM ne devra être présenté comme la
validant.

### Rendez-vous

**Fin août**, après transcription des `.scid` et croisement avec les
snapshots. Si les trois conditions échouent, la réponse est « on garde
MT5 » — et c'est une réponse, pas un échec.

---

## H29 — Les deux règles d'abstention du contrefactuel orderflow

**Pré-enregistrée le 17/08 à 10:45**, à partir de la sortie
`scalp_orderflow_20260817-1025.txt` du pipeline existant (153 481
barres orderflow depuis le 29/04, 2 550 tickets rails, 1 635 appariés
à une barre Ninja).

Ces deux règles sont **les mieux classées du contrefactuel**. Elles ne
sont pas de moi : elles sortent d'un tableau déjà calculé. Ce que
j'ajoute ici, c'est la seule chose qui leur manquait — **une date de
coupure et un critère de réfutation écrits avant la suite**.

### Les deux règles, avec le chiffre qu'elles doivent reproduire

| | testables | retirés | PnL/signal avant | après | Δ annoncé |
|---|---|---|---|---|---|
| **A — flux CARNAGE ou MOU (ER < 0,40)** | 1 635 | 1 212 (74 %) | −0,97 € | +3,68 € | **+4,65** |
| **B — heures 09h–11h** | 2 550 | 757 (30 %) | −0,97 € | +2,72 € | **+3,69** |

La règle A ne s'applique qu'aux tickets appariés à une barre Ninja —
**64 % du total**, et **zéro sur US100**, qui n'a aucune donnée
SierraChart. La règle B s'applique à tout le monde : elle ne demande
qu'une horloge.

### Pourquoi elles ne prouvent rien en l'état

Elles sont nées des 2 550 tickets qu'elles jugent. Le document le dit
lui-même : *in-sample*, contrefactuel naïf (retirer un trade ne change
rien au reste), et un Δ sur moins de 30 signaux est du bruit. Un
tableau qui classe dix règles par Δ **trouvera toujours une première**,
même sur du hasard — c'est le motif qu'on documente depuis trois
semaines.

### La coupure

**Tous les tickets clos à partir du 18/08/2026 00:00.** Ceux d'avant
ont servi à écrire les règles ; ils ne peuvent pas les tester.

### Ce qui compterait comme confirmation

Sur les tickets postérieurs, **la même règle appliquée telle quelle**
doit rendre un Δ positif. Pas « le même Δ » — un intervalle qui
contient +4,65 serait déjà remarquable.

Combien de signaux ? Avec σ ≈ 60 € et un effet de +4,65 €/signal :
n > (1,96 × 60 / 4,65)² ≈ **640 signaux évalués**. Au rythme observé
(2 550 tickets sur 110 jours, soit ~23/jour), c'est **~28 jours de
trading** → **rendez-vous le 15 octobre**, avec un regard intermédiaire
au 15 septembre qui ne servira qu'à vérifier que la mesure tourne, pas
à conclure.

### Ce qui compterait comme réfutation

- Δ ≤ 0 sur les tickets postérieurs : la règle ne survit pas à sa
  sortie d'échantillon.
- Δ > 0 pour B mais ≤ 0 pour A : l'heure suffisait, et l'orderflow
  n'apportait rien — ce qui **répondrait aussi à H28** sur
  l'abonnement SierraChart, par la négative.
- Δ > 0 pour les deux mais A ≈ B : elles retirent les mêmes trades,
  l'orderflow est redondant avec l'horloge. À vérifier par le
  recouvrement des ensembles retirés, pas par les seuls Δ.

### Ce que H29 n'autorise pas

Aucun changement de paramètre avant le 15 octobre. Ces règles ne sont
pas appliquées, elles sont **observées**. Et le calcul du Δ doit être
refait par le même code, sans re-choisir le seuil de 0,40 ni la plage
horaire — les re-choisir sur les données nouvelles annulerait
exactement ce que ce pré-enregistrement sert à protéger.

---

## H30 — Le NFP pousse le Dow relativement au S&P, dans l'heure qui suit

**Statut : PRÉ-ENREGISTRÉE le 17/08/2026. Non appliquée. Vérification
le 04/09/2026.**

### Ce qui a été observé, et sur quoi exactement

Trois publications de `Nonfarm Payrolls` dans la plage commune aux deux
carnets SierraChart. Écart de centiles `YM-continu − MES-continu`,
chaque symbole rapporté à sa propre distribution :

```
                     journée entière      décision [T, T+60min]
2026-06-05           rang 107 / 110              +53.9
2026-07-02           rang  62 / 110               +3.9
2026-08-07           rang  77 / 110              +16.2
```

**3/3 du même côté sur les deux mesures.** C'est la seule observation
du 17/08 qui ait survécu aux quatre corrections de la journée —
dédoublonnage des barres, exclusion du TICK, fusion des cinq lignes
BLS par instant, et passage de la journée à la fenêtre.

Positif signifie : le Dow **moins vendu** (ou plus acheté) que le S&P,
relativement à ce que chacun fait d'ordinaire **à cette heure-là**.

### Ce qui n'est pas observé, et qu'il faut se rappeler

- **L'ADP ne suit pas** : +50,9 / −11,6 / −9,6, soit 1/3. Ce n'est
  donc pas « l'emploi » en général, c'est le NFP.
- **Le CPI va dans l'autre sens mais ne tient pas** : 3/3 sur la
  journée, 2/3 sur la fenêtre. Écarté.
- **La phase d'attente ne dit rien** : −9,4 / −32,9 / +44,2. Si l'effet
  existe, il naît à la publication, pas avant.

### Trois points. C'est tout.

Sous l'hypothèse nulle, trois tirages du même côté arrivent **une fois
sur huit**. Ce n'est pas un résultat, et aucun traitement statistique
ne le rendra plus solide. La seule chose qui puisse le confirmer ou le
tuer, c'est une occurrence **hors échantillon**.

### Les paramètres sont GELÉS

Toute modification de l'un d'eux annule le pré-enregistrement :

```
outil        ecart_fenetre.py
symboles     YM-continu, MES-continu   (raccords par volume dominant)
fenêtre      --avant 60 --apres 60
mesure       centile(YM) − centile(MES), phase DÉCISION
référence    la même fenêtre horaire sur toutes les séances
motif        "Nonfarm Payrolls" SEUL — pas "nonfarm", qui avale l'ADP
instant      lu dans le calendrier MT5, converti UTC = serveur − 3 h
```

Refaire la mesure avec 15, 30 ou 120 minutes jusqu'à ce qu'elle parle
serait un balayage, et un balayage trouve toujours un maximum.

### Ce qu'il faut voir le 04/09, et ce qui la tue

**Prochaine occurrence : vendredi 4 septembre 2026, 12:30 UTC.**

- écart de décision **positif** → 4/4. Passe à une chance sur seize.
  Toujours pas un résultat ; on continue d'observer.
- écart de décision **négatif** → 3/4. L'observation tombe, et on
  l'écrit ici.

Deux occurrences supplémentaires (octobre, novembre) seront
nécessaires avant même d'envisager d'en faire quoi que ce soit.

**Aucune décision de trading ne s'appuie sur H30 avant le 15/12/2026
au plus tôt.** Elle est **observée**, pas appliquée.

### Pourquoi cette hypothèse existe malgré sa faiblesse

Parce qu'elle a été trouvée en regardant les données — ce qui est
exactement la façon dont le `−1330` du matin est né, et il était faux.
La seule différence entre une piste et une illusion, c'est qu'une
piste est écrite AVANT sa vérification, avec ses paramètres gelés et
sa date. C'est fait.

### H30 — ANNOTATION du 17/08/2026, quelques heures après le pré-enregistrement

**L'hypothèse n'est ni retirée ni modifiée** — retirer une hypothèse
parce qu'un résultat ultérieur dérange est exactement ce qu'on
s'interdit. Mais une mesure faite après elle en fragilise le support,
et elle doit être lue en même temps qu'elle.

```
flux_contre_prix.py, correlation de rang delta / rendement, par seance
  MES-continu   n=133   rho = 0.569   p = 0.0005   informatif
  YM-continu    n=112   rho = 0.015   p = 0.8726   MUET
```

**Le delta quotidien de `YM-continu` n'a aucun rapport avec le
mouvement de prix de `YM-continu`.** Or H30 est construite sur le
centile de delta de YM. Le `3/3` du NFP pourrait donc être du bruit
tombé trois fois du même côté — ce qui arrive une fois sur huit,
précisément la probabilité déjà notée.

**Deux réserves, avant d'en conclure quoi que ce soit :**

- `rho` est mesuré sur des **agrégats journaliers**. Un delta
  informatif à l'échelle de la minute peut se laver entièrement sur
  une séance de 1250 barres.
- H30 mesure une **fenêtre de 60 minutes**, pas une journée. Le
  résultat journalier ne la touche donc pas directement.

**Ce qui tranchera, et qui reste à faire :** la même corrélation
`delta / rendement` à l'échelle de la fenêtre horaire, sur les deux
symboles. Si YM y est aussi muet, H30 s'appuie sur du bruit et tombe
sans attendre le 4 septembre. Si YM y est informatif, l'asymétrie est
un effet d'agrégation et H30 tient jusqu'à sa date.

**Cette mesure doit être faite AVANT le 04/09**, faute de quoi on
vérifiera une hypothèse sans savoir si son support existe.

Une conséquence tient déjà, indépendamment : le flux SierraChart n'a
pas la même valeur sur les deux symboles. Sur le 12/08, MES échange
35 979 contrats dans l'heure contre 3 132 pour YM. **H28 ne se pose
plus en « payer ou non » mais en « payer pour quel actif ».**

### H30 — RÉSOLUTION DE L'ANNOTATION, 17/08/2026 au soir

**Le support de H30 existe. L'hypothèse tient jusqu'au 04/09, sans
modification de ses paramètres gelés.**

```
flux_contre_prix.py, rho(delta, rendement), permutation par journee
                 echelle SEANCE            echelle 60 MINUTES
  MES-continu    n=133  rho 0.569  p .0005   n=3013  rho 0.675  p .0005
  YM-continu     n=112  rho 0.015  p .8726   n=2615  rho 0.296  p .0005
                        ^ MUET                       ^ informatif
```

Le silence journalier de YM était un **effet d'agrégation** : un signal
horaire réel, lavé par la somme de 1 250 barres. H30 mesurant une
fenêtre de 60 minutes, elle porte sur l'échelle où le delta de YM parle.

**Ce qui reste vrai de l'inquiétude** : le delta de YM est nettement
plus bruité que celui de MES — 0,296 contre 0,675. Le `3/3` du NFP
reste trois points sur une série de qualité inférieure. La
vérification du 4 septembre n'en est que plus nécessaire.

---

## H31 — Les prix bougent ensemble, les flux non

**Statut : MESURÉE le 17/08/2026, n = 2565. Pas pré-enregistrée —
trouvée en cherchant autre chose. À confirmer hors échantillon.**

```
MES-continu / YM-continu, 2565 blocs horaires, permutation par journee
  rho PRIX    0.800   p 0.0005
  rho DELTA   0.209   p 0.0005
```

Les rendements horaires des deux indices partagent l'essentiel de leur
variation ; leurs deltas presque rien. **La rotation entre les deux
actifs est invisible dans les prix et lisible dans les carnets** — ce
qui est précisément ce que l'orderflow apporte et qu'aucun graphique
de prix ne donne.

C'est le premier élément de réponse mesuré à **H28**.

### Les trois réserves, à lire avec le résultat

1. **Le seuil de 0,25 qui déclenche le verdict de l'outil est
   inventé.** 0,209 est juste en dessous ; à 0,26 la phrase ne serait
   pas sortie. Le résultat à retenir n'est pas le verdict binaire mais
   le couple `0,800 / 0,209`, dont le rapport ne dépend d'aucun seuil.

2. **0,209 est un PLANCHER.** Le delta de YM est plus bruité que celui
   de MES (0,296 contre 0,675 face à leur propre prix). Un bruit de
   mesure atténue mécaniquement toute corrélation à laquelle la série
   participe : la vraie corrélation entre flux est donc supérieure à
   0,209, d'un montant non chiffré. La dissociation est réelle, son
   ampleur est majorée par l'inégalité de qualité des deux sources.

3. **Aucune causalité.** Un flux qui pousse le prix et un prix qui
   attire le flux produisent la même corrélation.

### Ce qui la confirmerait ou la tuerait

Refaire la mesure sur une période disjointe — les données de septembre
à novembre, quand elles existeront — sans changer d'outil ni
d'échelle. Si le couple reste de l'ordre de `0,8 / 0,2`, H31 tient. Si
`rho DELTA` remonte vers `rho PRIX`, elle tombe.

**Aucune décision de trading ne s'appuie sur H31.** Une corrélation
d'ensemble n'empêche aucune séance de faire exactement le contraire.

### H29 — ANNOTATION DE COUPURE, 17/08/2026 au soir

**Écrite AVANT la coupure du 18/08 00:00**, pour dater le point de
départ. Elle ne modifie ni les règles, ni les seuils, ni la date de
rendez-vous du 15 octobre.

**Le chiffre a bougé dans la journée, sur le même échantillon
in-sample.**

```
                              tickets    apparies    dA      dB
17/08 10:25  pre-enregistrement  2 550   1 635 (64,1%)  +4,65   +3,69
17/08 18:56  meme contrefactuel  2 790   1 764 (63,0%)  +3,75   +3,31
```

240 tickets de plus, et les deux Δ baissent — A de 19 %, B de 10 %.

**Ce que ça veut dire, et ce que ça ne veut pas dire.** Les deux
mesures sont **antérieures à la coupure** : aucune des deux n'est le
test. Ce n'est donc pas une réfutation, et il serait faux de l'écrire.

Mais c'est le comportement attendu d'un effet né du tableau qui le
juge. Une règle choisie comme la meilleure de dix sur un échantillon
donné voit son avantage s'éroder dès qu'on ajoute des données sans
re-choisir le seuil, parce qu'une partie de l'avantage initial était
la chance d'avoir été la meilleure. Que l'érosion commence **avant même
la sortie d'échantillon** est une information à garder en tête le
15 octobre : si le Δ hors échantillon ressort autour de +3, il ne
faudra pas le lire comme « proche du +4,65 annoncé ».

**La valeur de référence pour le 15/10 reste +4,65 et +3,69**, celles
du pré-enregistrement. On ne remplace pas une valeur pré-enregistrée
par une valeur plus récente : ce serait déplacer la cible.

**PROVENANCE — à vérifier.** Les chiffres du 17/08 18:56 ne viennent
pas d'une lecture directe du fichier : ils sont rapportés par le REPL
lisant `scalp_orderflow_<date>-<heure>.txt`. Le pré-enregistrement du
matin, lui, vient de la sortie `20260817-1025` lue directement. Tant
que la ligne de 18:56 n'est pas relue à la source, elle est notée ici
comme **rapportée, non vérifiée**.

**Coupure confirmée : tous les tickets clos à partir du 18/08/2026
00:00.** Le compteur repart de zéro à cet instant ; les 2 790 tickets
ci-dessus sont tous du côté in-sample.

---

## H32 — Le classement de force entre les trois indices dans une séance de baisse large

**Statut : PRÉ-ENREGISTRÉE le 18/08/2026. Non appliquée. Vérification
le 22/09/2026.**

**Écrite sur deux observations seulement, et parce qu'elles sont deux.**
Attendre d'en avoir cinq pour l'écrire, ce serait l'écrire après les
avoir vues — et une observation notée après coup ne contraint rien.

### Ce qui a été observé

Deux fois, à cinq jours d'intervalle, la même ordre de dégât relatif :

```
13/08   US100 tient au-dessus de sa cassure, US30 rend tout,
        US500 entre les deux              (releve par l utilisateur, note
                                           dans mistakes.md le 15/08)
18/08   US100 -0,48 %, US500 -0,73 %, US30 -0,88 %
        sous leur propre niveau de cassure
```

**Le 17/08 au soir et le 18/08 au matin sont UN SEUL épisode**, pas
deux : la même descente continue, sans reprise entre les deux. Compter
chaque capture d'un mouvement en cours comme une observation
supplémentaire fabriquerait de l'effectif à partir de la fréquence à
laquelle on regarde l'écran.

Deux épisodes, donc. Sur six ordres possibles entre trois actifs, deux
fois le même arrive avec une probabilité de **1 sur 6**. Ce n'est pas
un résultat.

### L'énoncé, sous une forme qui ne demande pas de définir « épisode »

Définir un épisode de cassure puis réintégration demanderait des choix
— combien de séances de range, quel tampon, quelle durée — et je les
ferais forcément coller aux deux cas connus. On mesure donc quelque
chose de mécanique :

**Sur une séance de baisse large** — les trois indices clôturant en
baisse par rapport à la clôture de la séance précédente — le classement
des rendements en pourcentage est :

```
US100 > US500 > US30     (du moins negatif au plus negatif)
```

### Les paramètres sont GELÉS

```
source      snapshots.csv (MT5), la seule qui porte les TROIS indices
            -- les .scid n ont pas de Nasdaq, sur aucune echeance
mesure      rendement de seance en %, cloture a cloture
selection   les trois indices en baisse le meme jour
unite       la seance, definie par sa densite de barres
exclues     13/08 et l episode 17-18/08, qui ont fait naitre
            l hypothese et ne peuvent pas la tester
```

Refaire la mesure sur les rendements en points au lieu du pourcentage,
ou sur une autre fenêtre que la séance, serait un balayage.

### La limite, écrite d'avance

`snapshots.csv` ne couvre que **21 journées**. C'est la contrainte
dure : aucune source ne porte les trois indices sur plus long. Le
Nasdaq est invisible à SierraChart, et `futures_<SYMBOLE>_M1.csv` est
une fenêtre glissante sans historique.

À raison d'environ une séance de baisse large sur trois, 21 journées en
contiennent peut-être sept — dont deux sont exclues. **L'échantillon de
départ est donc de l'ordre de cinq.** C'est peu, et c'est dit avant.

### Ce qui la réfute

Sur **au moins 8 séances de baisse large postérieures au 18/08/2026**,
l'ordre exact `US100 > US500 > US30` doit apparaître plus souvent que
le hasard ne le donne.

Sous H0, chaque séance a 1 chance sur 6. Sur 8 séances :

```
0 a 2 fois sur 8    compatible avec le hasard  -> H32 est FAUSSE
5 fois ou plus      p = 0,0035                 -> elle survit ce tour
```

**H32 est fausse si l'ordre exact apparaît 2 fois ou moins sur 8.**

Un ordre partiel — US100 devant US30 mais US500 mal placé — ne compte
pas comme une confirmation. C'est l'ordre complet qui a été observé,
c'est lui qu'on teste.

### Ce qui la rendrait vraie par construction

**Élargir la définition.** « Les trois en baisse » est mécanique.
Passer à « les trois en forte baisse », ou choisir un seuil, ferait
entrer le choix du seuil dans le résultat.

**Se rabattre sur l'ordre partiel** si l'ordre complet échoue. C'est
exclu d'avance, ici, par écrit.

**Confondre avec la volatilité.** Le US30 est le plus volatil en
points ; s'il descend le plus en pourcentage aussi, ce peut n'être que
sa volatilité, pas une faiblesse. **Contrôle obligatoire** : rapporter
chaque rendement à l'écart-type de séance de son propre actif. Si
l'ordre disparaît après normalisation, H32 ne décrit qu'une différence
de volatilité déjà connue — et c'est ce qu'il faudra écrire.

### Ce que H32 n'autorise pas

Aucune décision de trading, aucun changement de paramètre. Elle est
**observée**, pas appliquée. Un classement de force n'est ni un point
d'entrée, ni une direction, ni un euro.

### H29 — ANNOTATION DE COUPURE, chiffres VÉRIFIÉS le 18/08 à 08:09

L'annotation d'hier soir portait la mention « rapportés, non vérifiés » :
ses chiffres venaient du REPL lisant le panneau, pas d'une lecture
directe. Lecture faite dans `scalp_orderflow_20260818-0809.txt`.

```
                         tickets  apparies       base      dA      dB
17/08 10:25  pre-enreg     2 550   1 635 (64,1%)  -0,97   +4,65   +3,69
17/08 18:56  rapporte      2 790   1 764 (63,0%)      ?   +3,75   +3,31
18/08 08:09  VERIFIE       2 813   1 778 (63,2%)  -1,19   +3,88   +3,38
```

Les chiffres rapportés par le REPL étaient **proches mais pas exacts**
— +3,75 contre +3,88, +3,31 contre +3,38. L'écart s'explique par deux
exports différents (18:56 la veille, 08:09 ce matin) et non par une
erreur de lecture. La mention « non vérifié » est levée.

**Ce que la vérification confirme.** L'érosion est réelle : `A` passe de
+4,65 à +3,88, `B` de +3,69 à +3,38, sur 263 tickets supplémentaires et
**toujours in-sample**. La valeur de référence du 15/10 reste +4,65 et
+3,69, celles du pré-enregistrement.

**Ce que la vérification ajoute, et que le REPL n'avait pas dit.** La
base elle-même a bougé : **−0,97 € → −1,19 €** par signal. Une partie
de la baisse du Δ vient donc d'un `après` qui monte moins, pas
seulement d'un `avant` qui descend. À relire au 15/10 : comparer les Δ
sans comparer les bases serait comparer deux soustractions différentes.

**Et le cumul des règles est chiffré, il n'est plus une crainte.** Le
document lui-même écrit, sur la ligne `cumul des règles Δ>0` :

```
9 regles combinees -- sur-ajuste, a lire comme un plafond, pas un plan
retires 2 344 sur 2 813 (83 %)   reste 469   apres +9,42   D +10,62
```

83 % du flux retiré, 469 tickets restants. C'est exactement l'ordre de
grandeur estimé la veille (≈18 % de survivants) et ça confirme
qu'empiler les filtres ne construit pas une stratégie : ça isole le
sous-ensemble le plus sur-ajusté de l'échantillon. Le panneau le dit
lui-même, dans sa propre sortie.

---

## H33 — Ce n'est pas le SIGNE du flux qui annonce le refus, c'est son RENDEMENT

**Statut : PRÉ-ENREGISTRÉE le 18/08/2026, AVANT toute mesure. Non
appliquée. Première lecture attendue sous 48 h.**

### D'où elle vient : une bougie, pas un échantillon

`bougie_deux_actifs.py`, 14/08 à 16h30 Paris, MES-continu, minute par
minute :

```
heure    cloture    dprix    delta   x med    cvd     vol xm
16:04    7828.00    +1.75     +809    27.9    +902     19.5
16:05    7830.00    +3.75    +1047    36.1   +1949     25.7
16:06    7829.25    +3.00     +187     6.4   +2136     13.0
...
16:21    7818.75    -7.50    -1651    56.9   -4289     48.6
```

**+2 136 contrats nets à l'achat, en trois minutes, à 28 et 36 fois le
delta médian de la journée — pour +3,75 points.** Puis le flux se
retourne et le prix rend 22 points sur la fenêtre, avec un delta cumulé
de −9 554.

De l'achat massif qui n'achète presque rien, suivi d'un effondrement.
C'est la définition opérationnelle de l'absorption.

### Pourquoi `refus_continuation.py` ne peut pas la voir

Sa colonne APPROCHE est une **SOMME** de delta sur 60 minutes. Ici la
somme est trompeuse : l'achat de 16:04-16:06 et la vente qui suit se
compensent. Le signal n'est pas dans le total, il est dans le
**RAPPORT** entre ce que le flux pousse et ce que le prix rend.

C'est pour ça que `APPROCHE` sort à `p = 0,77` et `0,48` : elle mesure
une direction là où le phénomène est un rendement. **Une variable nulle
n'est pas une absence de phénomène, c'est parfois la mauvaise variable.**

### La mesure, GELÉE avant d'être faite

Dans la fenêtre d'approche `[t−60, t[`, on prend **la minute au plus
fort |delta|** — pas une somme, pas une moyenne : l'extrême, qui est
l'endroit où l'absorption se voit :

```
d = |delta| de cette minute      / mediane |delta| du jour
p = |dprix| de cette minute      / mediane |dprix| du jour
RENDEMENT = p / d
```

Sur 16:05 : `d = 36,1`, `p = 2,00 / 0,25 = 8,0`, donc **rendement
0,22**. Une minute ordinaire vaut environ 1.

Les deux médianes sont celles de la journée et de l'actif, déjà
calculées par les deux outils. Rien de nouveau n'est inventé.

### L'énoncé

**Les tentatives qui finissent en REFUS ont, dans leur fenêtre
d'approche, un RENDEMENT plus faible que celles qui finissent en
CONTINUATION.** Le flux pousse autant, le prix suit moins.

### Ce qui la réfute

Même dispositif que la colonne APPROCHE : écart des médianes entre
REFUS et CONTINUATION, `p` par permutation des issues à l'intérieur de
chaque journée, graine 20260817.

**H33 est fausse si `p > 0,05` sur MES-continu et sur YM-continu.**

### LA RÉSERVE QUI COMPTE : c'est un deuxième test sur le même échantillon

Les 827 événements ont déjà servi à tester APPROCHE et VOLUME. Ajouter
une troisième variable sur les mêmes données augmente mécaniquement la
chance qu'une d'elles sorte. Trois variables à 5 %, c'est ~14 % de
chance qu'au moins une passe sous H0.

Donc, écrit d'avance :

- un `p < 0,05` sur H33 **ne vaut pas** un `p < 0,05` obtenu du premier
  coup. Il vaut « à confirmer » ;
- **la confirmation exigée est une période disjointe** — les données de
  septembre à novembre, même outil, mêmes paramètres, sans rien
  rechoisir ;
- si H33 passe et que la confirmation échoue, on écrit qu'elle a
  échoué. On ne se rabat pas sur une quatrième variable.

### Ce qu'elle n'autorise pas

Aucune décision, aucun paramètre. Et même vraie, elle ne dirait qu'une
chose : que l'information est dans le rendement du flux et non dans son
sens. Le chemin vers l'euro passerait encore par des tickets, un
spread et `churn_trades.jsonl`.

### Ce que la bougie du 14/08 dit AUSSI, et qu'il faut noter

```
MES-continu  delta -9554   prix -0,281 %   volume 16,6 x median
YM-continu   delta   +198  prix -0,184 %   volume  7,5 x median
```

**Le Dow a baissé avec un carnet net ACHETEUR.** Les deux carnets sont
de signe opposé sur la fenêtre, 42 % des minutes en désaccord de signe.
C'est H31 — les prix ensemble, les flux non — rendue visible sur un
seul événement.

Et une caution pour **H32** : sur cette fenêtre, US500 baisse **plus**
que US30 en pourcentage (−0,281 contre −0,184), soit l'inverse du
classement pré-enregistré. Une fenêtre de 91 minutes ne teste pas une
hypothèse de séance — mais c'est un rappel que le classement n'est pas
un fait acquis.

### H32 — AMENDEMENT du 18/08, AVANT toute mesure

**Écrit avant que H32 ait tourné une seule fois.** C'est la condition
qui le sépare d'un sauvetage : on corrige une erreur de fait sur ce qui
existe, pas un résultat qui déplaît. Même forme que l'amendement de H27
du 17/08.

**L'erreur.** H32 gelait `source snapshots.csv, la seule qui porte les
TROIS indices`. C'est faux. Il existe un journal dédié, écrit par
`index_cohesion.py`, dont l'en-tête dit explicitement qu'il a été fait
parce que *« SierraChart n'a pas le NASDAQ »* :

```
docs/index_cohesion/cohesion_AAAA-MM-JJ.jsonl
{"ts": "2026-08-18 00:00:00",
 "z": {"US30": 1.495, "US500": 4.301, "US100": 1.629},
 "state": {"US30": "UP", "US500": "UP", "US100": "UP"},
 "regime": "ALIGNE_HAUSSE", "n_up": 3, "n_down": 0, "n_flat": 0,
 "cohesion": 1.0, "corr_sp_nas": 0.756, "corr_sp_nas_lag1": 0.192,
 "lead": "US500_MENE", "tz_offset_h": -3}
```

**Ce que ça change, et ce que ça ne change pas.**

La source devient ce journal, pour une raison de fond : il porte des
`z`, c'est-à-dire des mouvements **déjà normalisés par actif**. Or H32
impose un contrôle obligatoire — vérifier que le classement ne soit pas
une simple différence de volatilité. Le journal le fournit directement
au lieu de le faire recalculer.

**Mais la couverture est PIRE que ce que j'avais écrit.**

```
16 fichiers, du 2026-08-03 au 2026-08-18
```

Seize journées, contre les vingt et une de `snapshots.csv`. Et les deux
épisodes fondateurs — le 13/08 et le 17-18/08 — sont **à l'intérieur**
de cette fenêtre, donc exclus du test comme prévu. Il reste quatorze
journées, dont peut-être quatre ou cinq de baisse large.

**La conclusion de H32 est donc inchangée et son échéance aussi.** Le
22/09 elle aura peut-être huit séances neuves, pas davantage. Elle
reste mince, elle était annoncée mince, et corriger la source ne la
rend pas plus forte.

**Un cadeau au passage, qui ne concerne pas H32.** Le journal calcule à
chaque instant :

```
corr_sp_nas        0,756     correlation S&P / Nasdaq, simultanee
corr_sp_nas_lag1   0,192     la meme, decalee d un pas
```

C'est **H31 mesurée en direct par la stack depuis le 3 août** : les
indices bougent ensemble à 0,76 et le décalage d'un pas fait tomber ça
à 0,19. Rien ne précède. Une confirmation indépendante, sur une source
qu'on n'avait pas ouverte, du résultat de la section 9 du protocole.

---

## H34 — La VITESSE du flux, et non son volume

**Statut : PRÉ-ENREGISTRÉE le 18/08/2026, AVANT toute mesure. Mesurée
en EXPLORATION d'abord (§10 du protocole).**

### D'où elle vient

L'utilisateur, 18/08 : *« lorsque je regarde les bougies je vois le
rythme usuel de formation de la bougie via les échanges et parfois,
sans news ou autre, on a des bougies repères car on a vu le flux à
l'intra-bougie aller beaucoup plus vite »*.

**Tous mes outils agrègent à la minute et détruisent cette information
par construction.** Deux bougies de même volume et même delta, l'une
remplie en cinq secondes et l'autre étalée sur soixante, sont le même
point dans toutes mes mesures.

### Ce qui rend la mesure possible tout de suite

`of_*.csv` porte quatorze colonnes, mes outils en lisaient cinq :

```
ts open high low close trades volume bid_vol ask_vol delta cvd
spread_moy contrat roulement
```

`trades` = nombre de transactions dans la minute. Il était là depuis le
début, sur 183 314 barres.

### Les deux variables, GELÉES

```
VITESSE   trades de la minute        / mediane des trades du jour
TAILLE    (volume / trades)          / mediane du (volume/trades) du jour
```

Mille transactions d'un lot et cent transactions de dix lots font le
même volume. VITESSE et TAILLE les séparent ; le volume seul, non.

Mesurées sur **la minute au plus fort |delta| de la fenêtre
d'approche** — même point que H33, pour qu'elles soient comparables
entre elles et qu'aucune ne bénéficie d'un choix particulier.

### L'énoncé

**Les tentatives qui finissent en REFUS sont précédées d'une minute de
poussée plus RAPIDE et de plus PETITE taille moyenne que celles qui
finissent en CONTINUATION** — beaucoup de petits ordres pressés plutôt
que peu de gros ordres posés.

### Ce qui la réfute

`p > 0,05` sur les deux variables et les deux symboles, en
CONFIRMATION. Un résultat d'exploration ne réfute ni ne confirme rien :
il décide seulement de ce qui passe en confirmation.

### Ce qu'elle n'autorise pas

Aucune décision. Et une réserve de fond : une minute rapide peut être
la conséquence d'une nouvelle que le calendrier ne porte pas. La
vitesse ne dit pas la cause.

### H34 — ANNOTATION DESCRIPTIVE du 18/08, ÉCRITE AVANT TOUTE MESURE

`bougies_reperes.py`, sortie propre après `patch_bornes` : 107 séances
sur MES, 108 sur YM, 5,4 % et 3,7 % des minutes repérées.

**Le raisonnement de H34 est affaibli par un fait descriptif.** L'énoncé
dit que les refus sont précédés d'une poussée *« plus RAPIDE et de plus
PETITE taille moyenne »*. Or les deux ne coïncident presque jamais :

```
recouvrement VITESSE <-> TAILLE     MES  9 %     YM  2 %
```

Et la colonne TAILLE des vingt-cinq minutes les plus rapides de MES
vaut 1,3 · 1,2 · 1,2 · 1,0 · 0,9 · 1,1 · 1,2 · 1,3 · 1,4 · 1,1 —
**toutes autour de 1**, c'est-à-dire la taille ordinaire de la journée.

**Les bougies rapides ne sont pas faites de petits ordres. Elles sont
faites de beaucoup d'ordres de taille normale.**

**Ce que ça change, et ce que ça ne change pas.** H34 porte sur REFUS
contre CONTINUATION, pas sur la co-occurrence des deux variables : ce
constat ne la réfute pas. Mais l'image qui l'a fait naître — « beaucoup
de petits ordres pressés » — ne décrit pas ce que les données
contiennent. Les deux variables restent mesurées **séparément**, comme
prévu, et c'est justement parce qu'elles sont indépendantes que les
mesurer toutes deux garde un sens.

**Les paramètres ne bougent pas.** On ne réécrit pas un énoncé parce
qu'un fait descriptif dérange ; on écrit le fait à côté, daté, avant la
mesure. Si VITESSE sort et pas TAILLE, cette annotation dira qu'on
l'avait vu venir — et si TAILLE sort quand même, elle dira que
l'intuition valait mieux que le descriptif.

### L'HORLOGE, CHIFFRÉE — contrainte sur H34 et sur toute mesure future

```
YM-continu, part des reperes par heure UTC (uniforme = 4,3 %)
  13:00 UTC   18,2 %   ouverture du cash NYSE
  22:00 UTC   11,8 %   cloture CME
  les deux         30,0 % des reperes dans 2 heures sur 23

MES-continu, maximum 8,3 % a 13:00 -- a peine le double de l uniforme
```

Le Dow est un contrat mince dont l'ouverture écrase le reste ; le S&P
échange assez toute la journée pour que l'horloge ne domine pas.

**Toute mesure bâtie sur les repères de YM apparie ses témoins À LA
MÊME MINUTE DE SÉANCE**, faute de quoi elle mesurera « le cash ouvre à
13:30 » et sortira un `p` magnifique. Sur MES la contrainte est plus
légère mais elle reste.

### Une dépendance ALGÉBRIQUE entre deux des six dimensions

```
MES   PRESSION <-> RENDU   54 % / 50 %   -- le plus fort du tableau
```

`RENDU = AMPLEUR / PRESSION`. Une PRESSION forte pousse mécaniquement
le RENDU vers le bas : ce recouvrement est **construit, pas mesuré**.

Conséquence : compter « le nombre de dimensions franchies » traite six
grandeurs comme indépendantes alors que deux ne le sont pas. Le tri du
listing en est faussé, et une hypothèse qui utiliserait les deux
paierait deux tests pour une information et demie.

À corriger dans l'outil : RENDU doit être déclaré **dérivé** et sorti
du décompte. Le reste tient — TAILLE et SPREAD sont indépendants de
tout à 2-15 %.

---

## H35 — Un repère du S&P marque-t-il un niveau sur le Dow ?

**Statut : PRÉ-ENREGISTRÉE le 18/08/2026, AVANT toute mesure. NON
MESURÉE — reportée sur décision de l'utilisateur, « c'est à voir une
fois le reste bien ancré ». Écrite maintenant précisément pour que le
jour où on la mesure, l'énoncé et la règle de décision soient
antérieurs aux données.**

### D'où elle vient

L'utilisateur, 18/08 : *« lorsque j'ai mis le script us500 sur us30 on
a vu la correspondance en temps [...] il y a des rapprochements et on
pourrait avoir créé les momentums de supports et résistances »*.

L'indicateur généré pour MES a été collé sur un graphique du Dow. Les
instants de repère y tombent visiblement au même endroit.

### Ce que cette correspondance ne peut pas être

**Elle ne peut pas porter sur les prix.** MES cote 7 826 quand US500
cote 7 757 ; le Dow cote 46 000. Seuls les INSTANTS traversent d'un
symbole à l'autre — c'est déjà la raison pour laquelle
`pine_reperes.py` n'exporte que des `timestamp("UTC", ...)`.

**Et l'observation visuelle est, en l'état, la prédiction de
l'hypothèse nulle.** Deux contrats qui échangent la même séance ont
leurs minutes extrêmes aux mêmes heures :

```
YM-continu   13:00 UTC  18,2 %   22:00 UTC  11,8 %   (uniforme 4,3 %)
MES-continu  13:00 UTC   8,3 %
```

Trente pour cent des repères de YM tiennent dans deux heures sur
vingt-trois. Deux listes d'instants tirées de cette distribution se
« correspondent » sans qu'aucune information ne passe de l'une à
l'autre. **La coïncidence temporelle est ici le témoin, pas le
résultat.**

### Ce que H31 fait attendre — et pourquoi ça rend l'énoncé intéressant

H31, mesurée le 17/08 sur 2 565 blocs : `rho PRIX 0,800`,
`rho DELTA 0,209`. Les prix des deux indices bougent ensemble, leurs
flux beaucoup moins.

Un repère est un **événement de flux**. Si les flux sont dissociés, un
repère de MES ne devrait rien marquer de particulier sur YM au-delà de
l'horloge. **L'hypothèse contredit donc un résultat déjà mesuré** — ce
qui est exactement ce qu'on veut d'un énoncé pré-enregistré : il peut
perdre. S'il gagne, il dit que les événements extrêmes coïncident alors
que le flux ordinaire ne coïncide pas, ce qui n'est pas la même chose
que 0,209 et vaudrait cher.

### L'énoncé, GELÉ

**Un niveau tracé sur le Dow à l'instant d'un repère du S&P survit plus
longtemps qu'un niveau tracé sur le Dow à partir d'une bougie
ORDINAIRE prise à la même minute de séance un autre jour.**

Et sa réciproque, mesurée séparément : repère de YM, niveau sur MES.
Les deux sens comptent comme deux tests.

### Comment elle se mesure — l'outil existe déjà

`survie_niveaux.py` fait exactement ce calcul à un symbole près. Il
faut lui séparer deux rôles aujourd'hui confondus :

```
--reperes-de   symbole ou les repères sont détectés
--niveaux-sur  symbole ou le niveau est posé et sa survie mesurée
```

Le témoin reste apparié **à la même minute de séance**, sur le symbole
porteur du niveau. Aucun autre paramètre n'est ajouté ; le seuil de
détection et le centile ne bougent pas.

### La règle de décision, écrite avant les données

- `p >= 0,05` sur les deux sens : le regroupement n'ajoute rien, et on
  l'écrit sans essayer un troisième découpage.
- `p < 0,05` dans un seul sens : intéressant, mais **asymétrique** —
  à ne pas raconter comme une symétrie. Le sens gagnant est noté tel
  quel.
- `p < 0,05` dans les deux : passage obligatoire par la coupe du §10,
  exploration sur les 2/3 anciens, confirmation en une seule passe sur
  le tiers récent jamais regardé.

Et dans tous les cas, **la distance médiane au prix est lue avec le
résultat** : un niveau qui survit parce qu'il est loin n'est pas un
repère.

### Ce que ça ne dira pas, quoi qu'il arrive

Le mot « momentum » de la formulation d'origine décrit un mécanisme —
quelque chose qui pousse. Une survie en minutes ne contient aucun
mécanisme, aucun sens, aucun euro. Elle dit qu'un niveau n'a pas été
touché ; elle ne dit ni pourquoi, ni s'il fallait s'y opposer.

**Un support tenu parce que personne ne le regarde et un support
défendu donnent la même mesure.**

---

## MESURE — La survie des niveaux de repère (18/08/2026)

**Statut : MESURÉE sur l'échantillon complet. Résultat NÉGATIF, et il
se conclut — la première rédaction de cette entrée sur-couvrait le
résultat, elle a été corrigée après objection de l'utilisateur.**

### Les chiffres

```
MES-continu   distance au prix  0,75 / 0,75    ecart +0,0 min   p = 1,0000
YM-continu    978 reperes, 1956 niveaux
              survie mediane    3,0 / 2,0 min
              censures         11,3 % / 6,3 %
              distance au prix 19,00 / 6,00    ecart +1,0 min   p = 0,0370
```

### Ce qui se conclut

**Aucun soutien à l'idée qu'un niveau de bougie repère tient plus
longtemps qu'un niveau ordinaire.** Et les deux bras se répondent :

- Sur **MES**, les deux groupes sont à la **même distance du prix**
  (0,75 contre 0,75) : l'appariement est complet, et l'écart est
  **exactement nul**.
- Sur **YM**, le seul écart observé (+1 min) apparaît avec un écart de
  distance de **19 contre 6** — plus du triple. Un niveau trois fois
  plus loin est retouché plus tard pour une raison géométrique.

**Le seul endroit où une différence apparaît est le seul endroit où la
distance est déséquilibrée.** C'est un argument, pas une prudence.

### Ce que ces chiffres ne permettent PAS de dire

**1. Que l'effet est nul.** La survie est un nombre entier de minutes
et les médianes valent 2 et 3. Une différence de médianes sur de
petits entiers ne peut sortir que `+0`, `+1`, `+2`… : tout effet
inférieur à la minute est **invisible par construction**. On écarte un
gros effet, pas un petit.

**2. Que `p = 1,0000` soit une preuve forte.** Il est arithmétiquement
dégénéré : l'écart observé valant exactement 0, toute permutation
donne `|e| >= 0`. Le fait informatif est l'**égalité des médianes**,
pas le `p`.

**3. Que la question des supports soit tranchée.** La médiane décrit
les **deux ou trois premières minutes** — le prix reste près d'où il
vient de passer, et c'est ce que mesure la médiane. Un support au sens
courant vit dans la **queue censurée** : 11,3 % contre 6,3 %. C'est le
seul chiffre du tableau qui parle de la question posée, et il est
lui aussi porté par la distance.

**La mesure a répondu à « à quelle vitesse un niveau est-il
retouché », quand la question était « lesquels survivent
longtemps ».**

### Ce qui NE limite PAS ce résultat — rectification

J'avais opposé l'absence de coupe du §10. **C'était une mauvaise
application de la règle.** Le §10 protège contre le fait de croire un
résultat POSITIF trouvé en cherchant. Un résultat négatif ne se
fabrique pas par sur-ajustement : on ne cherche pas jusqu'à ne rien
trouver. La coupe redeviendra nécessaire le jour où un test sortira
positif.

### Ce qu'il faudrait pour reprendre la question

Deux corrections, à **déclarer avant** de relancer, sinon c'est
choisir le test après avoir vu échouer le premier :

1. **Apparier aussi sur la distance**, et pas seulement sur la minute
   de séance. Le témoin doit être à distance comparable du prix.
2. **Viser la queue, pas la médiane** : part de niveaux non touchés à
   30, 60, 120 minutes, qui est une proportion et non un entier
   quantifié.

Tant que ces deux points ne sont pas écrits et gelés, la question
reste ouverte **et l'outil ne se relance pas**.

---

## H36 — Un niveau de repère survit-il à la queue, à distance égale ?

**Statut : PRÉ-ENREGISTRÉE le 18/08/2026, AVANT toute exécution du
nouvel outil. Reprise déclarée de la mesure négative du même jour,
sur demande explicite de l'utilisateur : « geler les 2 corrections et
relancer sur l'intégralité ».**

**C'est un SECOND test après l'échec d'un premier.** Ce qui le rend
légitime et non un repêchage : les deux corrections sont écrites ici
*avant* de voir le moindre chiffre, et elles étaient déjà nommées dans
l'entrée du résultat négatif.

### Correction 1 — la distance n'est plus approchée, elle est ANNULÉE

Le premier tour comparait le plus haut d'une bougie repère au plus
haut d'une bougie ordinaire. Sur YM les repères sont de grandes
bougies : 19 points du prix contre 6. La survie mesurait
l'éloignement.

Apparier « au plus proche » laisserait un résidu — si aucune bougie
ordinaire de cette minute n'atteint 19, l'écart persiste. **On
supprime donc le degré de liberté au lieu de le réduire :**

```
d              = distance du niveau repère à la clôture de SA bougie
niveau repère  = cloture_repere + d      (et - d pour le bas)
niveau témoin  = cloture_temoin + d      (et - d pour le bas)
```

Le niveau témoin n'est plus un extrême de bougie : c'est **le même
écart géométrique, posé sur une bougie ordinaire**. Les deux niveaux
sont à distance identique par construction — la sortie l'imprime pour
le prouver.

Ce que ça isole exactement : *un niveau situé à d du prix est-il
particulier parce qu'une bougie repère l'a produit, ou seulement parce
qu'il est à d ?*

### Correction 2 — une PROPORTION, pas une médiane

La survie est un entier de minutes et les médianes valaient 2 et 3 :
l'écart de médianes ne pouvait sortir que `+0` ou `+1`. La médiane
décrivait en plus les trois premières minutes, c'est-à-dire le fait
banal que le prix reste près d'où il vient — pas un support.

```
NON TOUCHÉ À H = le niveau n est contenu par aucune barre de la
                 même séance dans les H minutes qui suivent
```

Une proportion est continue : elle n'a pas de pas d'une minute.

**HORIZON PRIMAIRE : 60 minutes.** Gelé. 30 et 120 sont imprimés en
robustesse et **ne portent aucun verdict** — c'est ce qui évite de
payer trois tests pour une question.

**Censure :** une paire ne compte que si les DEUX séances ont encore
au moins H minutes devant elles. Un niveau dont la séance s'arrête
avant l'horizon n'est pas « survivant », il est inconnu.

### L'énoncé, GELÉ

**À distance égale du prix, un niveau produit par une bougie repère
est moins souvent touché dans les 60 minutes qu'un niveau posé au même
écart sur une bougie ordinaire de la même minute de séance.**

### La règle de décision, écrite avant les chiffres

```
p par permutation de l etiquette repere/temoin A L INTERIEUR de chaque
journee, 2000 tirages, graine 20260818, bilaterale sur la difference
des proportions a 60 minutes.
```

- **MES et YM tous deux `p < 0,05`, même signe** → le repère ajoute
  quelque chose à géométrie égale.
- **Un seul des deux** → asymétrique. Noté tel quel, jamais raconté
  comme une symétrie.
- **Aucun des deux** → la question est CLOSE. On n'essaie ni un
  troisième horizon, ni un autre seuil de dimensions, ni un autre
  découpage.

### Le coût accepté, déclaré à l'avance

L'utilisateur demande l'intégralité. **Cela consomme le tiers récent
que le §10 réservait à la confirmation.** Conséquence acceptée en
connaissance de cause : un résultat positif ici ne pourra PAS être
confirmé hors échantillon sur ces données.

**Sa confirmation est donc fixée en avant, comme H30 :**

```
CONFIRMATION H36   le 20/10/2026, sur les seances posterieures au
                   18/08/2026, memes parametres, une seule passe.
```

Si le résultat est négatif, cette date tombe d'elle-même — un nul n'a
pas besoin d'être confirmé.

### Ce que ça ne dira pas, même positif

Ni euro, ni sens, ni mécanisme. « Non touché pendant 60 minutes » ne
dit pas qu'il fallait s'y opposer, ni que quelqu'un le défendait. Un
niveau que personne ne regarde et un niveau défendu donnent la même
proportion.
