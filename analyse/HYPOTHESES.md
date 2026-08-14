# HYPOTHÈSES — écrites le 14/08, avant la collecte

**Ce fichier est daté et ne doit plus être modifié.** Il liste ce qu'on
va tester pendant les quinze jours, avec pour chaque question la mesure
exacte, le seuil d'effectif, et la règle de décision. Écrites **avant**
d'avoir vu les données.

## Pourquoi ce fichier existe

En quinze jours, `papier_tf` produira de l'ordre de 200 à 350 entrées
x10 sur trois actifs, moins pour les autres durées. Découpé par durée ×
bras × séance × régime × HLC, ça fait **10 à 30 trades par case**.

À cet effectif, il existe **toujours** une combinaison flatteuse. Ce
n'est pas une opinion sur le marché, c'est de l'arithmétique : avec
quarante cases tirées d'un bruit centré, la meilleure sort à deux
écarts-types par construction. Le panneau `matrice_tf` en affichera
plusieurs dizaines.

Donc : un chiffre de la matrice ne devient un **résultat** que s'il
répond à une question posée ici. Tout le reste est de l'exploration —
utile pour écrire les hypothèses du mois prochain, jamais pour décider
maintenant.

## Le budget de tests

**Sept hypothèses principales.** Sept tests, décidés d'avance, sur un
échantillon qu'on ne regarde pas en route. Toute question née de la
lecture des données est notée dans la section EXPLORATION et ne compte
pas comme un test.

**Aucune décision de production avant le 29/08**, même si une case
paraît spectaculaire au bout de trois jours. Regarder un compteur en
train de monter et s'arrêter quand il est haut, c'est choisir son
résultat.

---

## H1 — le gradient x60 tient hors échantillon

**Prédiction.** Sur les quinze jours, le setup 60 (`familles.py`) reste
positif en EUR/ticket, et supérieur à chacun des setups 01, 02, 03, 05.

**Mesure.** `python familles.py --depuis 2026-08-14 --setup 60 --detail`

**Seuil.** 40 tickets x60 minimum sur la fenêtre. En dessous : non
testé, pas « non confirmé ».

**Décision.** Confirmé si positif ET premier de tous les setups.
Réfuté s'il passe négatif. Entre les deux — positif mais dépassé par un
setup court — l'hypothèse « le H1 est spécial » tombe, et il reste
« le H1 est un magic qui gagne parmi trente ».

*État au 13/08 : +30,47/ticket sur 186 (21/07→13/08), +15,52 sur 83
depuis le 05/08. L'avantage a déjà été divisé par deux en changeant de
régime.*

## H2 — le bras 206 bat le 207 sur les unités longues

**Prédiction.** À entrées identiques, le 206 fait au moins +5 EUR/ticket
de plus que le 207, sur H1 et sur M30.

**Mesure.** Même sortie, colonnes 206 et 207 par actif.

**Seuil.** 30 tickets par bras et par durée.

**Décision.** Confirmé si l'écart est positif **sur les trois actifs**
et supérieur à 5 en agrégé. Un écart positif sur deux actifs sur trois
ne confirme rien : c'est ce qu'on observait déjà, et ça peut tenir au
hasard sur trois comparaisons.

*État au 13/08 : +16,76/ticket en agrégé, positif sur les trois actifs
sur l'historique complet, mais inversé sur US100 depuis le 05/08. C'est
la piste la plus actionnable et elle a besoin d'un échantillon frais.*

## H3 — le déplacement de stop coûte de l'argent

**Prédiction.** Les positions dont le stop a été remonté finissent, en
moyenne, **moins bien** que celles qui ne l'ont pas été, à MFE
comparable.

**Mesure.** Non disponible aujourd'hui. Elle exige un log du
déclenchement : ticket, magic, instant, profit au moment du
déplacement, MFE atteint, résultat final. **À instrumenter avant de
pouvoir tester.** Sans ce log, H3 reste ouverte et ne se rattrape pas
rétroactivement — l'historique ne garde que le SL final.

**Raison de la prédiction.** La MFE médiane d'une perdante vaut 9 à
15 € ; le déplacement se déclenche entre +10 et +39. Il ne peut donc
quasiment jamais protéger une perdante, et n'agit que sur des
gagnantes — pour les raccourcir. Trois mesures indépendantes disent
déjà qu'il ne faut pas tronquer les gagnantes.

## H4 — le M10 perd en séance

**Prédiction.** Sur les entrées M10 ouvertes entre 08:00 et 19:30, le
résultat par trade est négatif.

**Mesure.** `matrice_tf`, section 1, colonnes EUROPE et US.

**Seuil.** 40 entrées M10 en séance.

**Décision.** Confirmé si négatif avec N ≥ 40 → on retire le M10 du
live. Réfuté si positif. Le papier hors séance ne compte pas : la
production est bornée, cette colonne n'est pas capturable.

*État au 13/08 : −14,52/trade sur 16 en séance, +35,34 sur 14 hors
séance — mais la colonne séance est passée de +8,06 à −14,52 en trois
heures. Elle ne soutient rien, dans un sens ni dans l'autre.*

## H5 — le x10 nocturne est un artefact de traversée

**Prédiction.** Parmi les entrées x10 ouvertes entre 22:00 et 09:00, le
gain se concentre sur celles qui ont **franchi une ouverture de
séance**. Les autres — nées et mortes dans la nuit — sont à peu près
nulles.

**Mesure.** `matrice_tf`, section 3, ligne M10, colonnes « n'a rien
franchi » contre « a franchi 1+ ».

**Seuil.** 25 entrées dans chacune des deux colonnes.

**Décision.** Confirmé si l'écart dépasse 10 EUR/trade en faveur des
traversantes → l'heure d'entrée nocturne est une étiquette trompeuse et
il ne faut pas en faire un créneau. Réfuté si les deux colonnes se
tiennent → la nuit paie vraiment.

**C'est l'hypothèse la plus importante des sept**, parce qu'elle
décide si « le x10 donne de bons moments la nuit » est une observation
ou un mirage. Hors séance rien ne remet à plat : une nuit calme est une
nuit sans reverse, donc la position de 02h vit jusqu'au matin.

## H6 — l'alignement sur un x60 se mesure à sa SORTIE

**Prédiction.** À l'instant où un x60 sort, les positions courtes du
**même actif** alignées sur son sens font mieux que celles à
contre-sens.

**Mesure.** `x60_onset`, section plateau, au moment `X60_SORTIE`.

**Seuil.** 25 présences dans chaque camp.

**Décision.** Confirmé si l'écart dépasse 8 EUR/présence. Réfuté sinon.

**Pourquoi à la sortie et pas à l'entrée.** À l'instant de l'entrée
d'un x60, il n'existe **aucune** position alignée sur le même actif —
zéro sur zéro — parce qu'on photographie au moment précis où il vient
de basculer. Le camp « AVEC » est vide *par définition de l'instant
choisi*, pas par rareté. Mesuré à l'entrée, ce test n'a pas de groupe
témoin et ne peut rien conclure.

## H7 — le filtre horaire 09h-11h survit

**Prédiction.** Le créneau 09h-11h reste le découpage horaire au plus
gros Δ, devant toutes les cellules orderflow.

**Mesure.** Panneau orderflow, contrefactuel Δ par signal.

**Seuil.** 100 signaux dans le créneau.

**Décision.** Confirmé s'il reste premier. Réfuté s'il passe sous
+2,00 par signal.

*État : Δ +5,43, confirmé sur deux slicings, contre +0,08 pour le
CARNAGE seul et −0,15 pour l'anti-contre-flux. C'est la seule règle
orderflow qui ait survécu au gel V9.*

---

## Ce qui compte comme EXPLORATION

Tout le reste, et notamment :

- les croisements contexte × durée de la section 4 de `matrice_tf` ;
- les combinaisons du type « MIXED + HLC widening + Asie » ;
- toute case repérée parce qu'elle est belle dans le tableau.

Ces lectures servent à **écrire les hypothèses de septembre**, pas à
décider en août. Une case explorée qui devient une hypothèse doit être
retestée sur des données qu'elle n'a pas servi à choisir — sans quoi
elle est positive par construction, comme les quatre artefacts du
13/08.

## La discipline de lecture, en trois lignes

1. **Un chiffre sans sa couverture ne vaut rien.** Zéro trade et
   observateur arrêté produisent le même fichier vide — le 13/08 au
   soir, les deux observateurs sont restés morts douze heures sans que
   rien ne le signale.
2. **Sous le seuil, on décrit, on ne conclut pas.** `matrice_tf` marque
   ces cases d'un `?`.
3. **Un cumul de règles choisies parce que leur Δ était positif sur le
   même échantillon est positif par construction.** C'est un plafond,
   jamais un plan.

---

*Ouvert le 14/08/2026. Relecture prévue le 29/08. Aucune décision de
production d'ici là.*
