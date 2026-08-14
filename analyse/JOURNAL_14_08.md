# MISE À JOUR DU 14/08/2026 — à lire avant de conseiller

Ce document corrige le `JOURNAL.md` principal, qui date du 13/08 et
décrit une stack qui a changé. **En cas de contradiction, c'est ce
document qui fait foi.**

---

## 1. Le fait le plus important, et il n'était pas chiffré hier

Sur `tickets_rails.jsonl`, 3 560 tickets réels du 21/07 au 14/08 :

| | séance 15h30-19h30 | hors séance | net |
|---|---|---|---|
| 29/07 → 04/08 | **+13 300 €** | −1 136 € | **+12 164 €** |
| 05/08 → 14/08 | **−2 524 €** | −12 343 € | **−14 867 €** |

**Depuis le 5 août, la stack perd tous les jours ou presque.** Onze
jours négatifs sur quatorze hors séance. Tout le gain du début a été
rendu, et davantage : net de −2 703 € sur la fenêtre.

La date du 5 août n'est pas choisie après coup — c'est celle que la
stack retient elle-même en nommant `panel_rails_post0508`.

**Ne jamais présenter un chiffre agrégé sur toute la fenêtre sans
préciser de quel côté du 5 août il tombe.** Presque tous les edges
mesurés existent avant et disparaissent après.

---

## 2. Ce qui tient, après correction du seuil

Douze découpes non annoncées ont été examinées le 14/08. À douze
comparaisons le seuil est **z ≈ 2,9**, pas 1,96. Après correction,
**deux résultats seulement survivent** :

**H9 — ne pas trader hors séance US.**
`−5,48 €/tk sur 2 461 tickets` contre `+9,80 sur 1 099`. Moyenne
élaguée à 1 % : **−5,71**, donc *pire* que la brute — ce n'est pas une
queue. Négatif 11 jours sur 14. Découpage sur l'heure d'entrée seule,
sans classifieur. C'est le seul edge démontrable du dossier.

**H14 — un bon départ est avare.**
Plus un « épisode » produit d'entrées, plus il est mauvais :
`1-4 entrées +25,04 · 5-9 +12,71 · 10+ −4,18`. À rang fixé, 54 € d'écart
entre un épisode à 3-4 entrées et un à 20+. Échantillon : 52 épisodes
contre 54 — enfin une unité correcte. **t ≈ 2,5, donc sous la barre.**
Et depuis le 05/08 sa moitié rentable a disparu : il ne reste qu'une
règle d'**évitement**, pas d'entrée.

**Tout le reste est non démontré.** Trois résultats présentés comme
acquis dans la journée passent sous la barre une fois le compteur tenu :
`x02 rangs 1-4` (t=2,86), `contre-sens` (t=2,82), `bande 0-15 min`
(t=2,57).

---

## 3. Ce qui a été RÉFUTÉ — ne pas le ressusciter

Trois hypothèses ont été écrites **avant** d'être testées, puis tuées
en une commande. Si un raisonnement y ramène, c'est une erreur :

- **« Un seul départ propre, le reste est du FOMO »** — faux. À délai
  égal, le rang 1 est le **plus mauvais** et la performance **monte**
  avec le rang, aux deux réglages d'épisode.
- **« Un fort débit précoce annonce un mauvais épisode »** — faux. Le
  pire camp est celui qui ne produit **rien** dans les dix premières
  minutes, et l'écart a un t de 0,82. Le débit ne porte aucune
  information.
- **« Un départ qui tarde est un faux départ »** — faux. Aucun ordre
  entre les tranches de latence, y compris restreint aux rangs 2-4.

---

## 4. Défauts de données connus — ne pas conclure dessus

**`age_s` du plateau est faux d'un jour entier.** Le champ `ouvert`
d'un membre de plateau ne porte que l'heure, sans la date. Toute
position ouverte la veille donne un âge **négatif**. Vérifié : `age_s
= −10 796` pour une position qui en avait **75 603** (21 h). Réparé
en lecture par `panel_quadruple.py`, pas dans le collecteur.

**Biais de survie dans les `CLOTURE`.** Le bras 206 tient jusqu'au
reverse ; le 207 prend son partiel et sort plus tôt. Lire les clôtures
en début de collecte sur-représente donc mécaniquement le 207. Au
14/08, **aucun x10/x20/x30 du bras 206 n'a encore de ligne CLOTURE** :
toute comparaison 206/207 sur ces setups est illisible.

**Deux classifieurs de régime se contredisent.** `regime_history.jsonl`
étiquette la matinée `INDETERMINATE / PRE_SESSION`, pas « range ».
Toute affirmation « le matin est en range » dépend du fichier ouvert.

**`elapsed_min` n'est pas l'âge du régime.** C'est le temps depuis
l'ouverture du cash US (15h30), et il vaut **0** avant. Vérifié trois
fois.

**Décalage d'une heure entre `ts` et `iso`** dans le même
enregistrement de `regime_history`. Joindre sur `iso`, jamais sur `ts`.

---

## 5. Ce qui a changé dans la stack aujourd'hui

- `x60_onset` écrit désormais `X_ENTREE` / `X_SORTIE` avec plateau pour
  **x10, x20, x30** — pas seulement x60. Depuis 10:35.
- `papier_tf` enregistre le contexte d'entrée **et de sortie**, plus la
  séance.
- **Gardien-Stack** garde 8 services et tourne toutes les 5 minutes.
  161 `VEILLE` au 14/08 : ~27 h d'observation sans décrochage.
- **Nouveau panneau** `panels/panel_quadruple.txt`, régénéré toutes les
  5 minutes : dix sections à quatre entrées x10/x20/x30/x60 — résultat
  par actif et par bras, séance, mfe/mae, le **plateau** (qui
  accompagne qui, avec le résultat final de l'accompagnant), l'âge
  réparé, les épisodes, le porteur, la richesse.
- Plafond de complétion du REPL porté à 60 000 jetons.

---

## 6. La règle de comptage — à appliquer avant d'affirmer

Pour distinguer un edge *e* du bruit avec σ par ticket :
`n > (z · σ / e)²`. Avec σ ≈ 60 € (**estimation, pas mesure**) et
e = 16 € : **~54 tickets** pour une comparaison annoncée d'avance,
**~118** pour vingt, **~172** pour cent.

**Une cellule sous 54 tickets ne conclut rien**, quelle que soit sa
moyenne. Les panneaux la marquent `?`. Une moyenne sans son n est un
chiffre sans unité.

Et l'unité qui compte n'est pas toujours le ticket : 300 tickets
répartis sur 25 épisodes valent **25 observations**, pas 300.

---

## 7. Ce qu'il ne faut pas dire

- Que le setup 60 est rentable. `+15,52 €/tk sur 83 tickets` a été
  **choisi** comme le meilleur d'une dizaine de candidats ; après
  correction il ne passe plus. Depuis le 05/08 il est le seul setup
  non perdant — ce qui n'est pas la même chose qu'être bon : +952 €
  sur 90 tickets, **t ≈ 1,67**.
- Que le papier hors séance dit quelque chose. Il est optimiste **par
  construction** — ni spread ni slippage, précisément aux heures où le
  spread est le plus large.
- Qu'un chiffre sur x10/x20/x30 est mesuré. Ces setups tournent depuis
  le **13/08 13:10**. 41 allumages au total. Tout ce qui les concerne
  est descriptif.
- Que « l'US100 se swingue et l'US30 se scalpe ». Sur le plus gros
  échantillon disponible (setup 60 depuis le 05/08), **l'US100 est le
  membre le plus faible** — US30 206 +26,90, US500 206 +33,09,
  US100 206 −0,15.

---

## 8. La question ouverte que le gel doit trancher

**H10 — le porteur doit être en avance, pas le plus grand.** Depuis le
05/08, un M2 ou M5 couvert par un **M10-M30** fait `+13,89 €/tk` contre
`−15,09` sous porteur **H1** — 29 € d'écart, t ≈ 4,1, signe cohérent
sur huit cellules.

Mécanisme : quand un H1 s'allume, le mouvement est engagé. Le H1 tient
jusqu'au reverse et encaisse ce qui reste ; un M5 entrant au même
instant n'a plus que la queue. **Le même trade est bon pour qui tient
et mauvais pour qui scalpe.**

**Réserve décisive : ces 107 tickets viennent de 43 allumages, tous
postérieurs au 13/08 13:10.** Une séance et demie. Le t suppose des
tickets indépendants ; ceux d'une même séance ne le sont pas. C'est la
cible nommée du gel — quinze jours donneront ~200 allumages au lieu
de 43.

---

## 9. Fichiers lisibles

```
panels/panel_quadruple.txt      les quatre unites, dix sections
docs/x60_onset/events.jsonl     VEILLE X60_ENTREE X_ENTREE
                                X60_SORTIE X_SORTIE CLOTURE
docs/rails_trades/tickets_rails.jsonl   depuis le 21/07
logs/regime_history.jsonl       type, phase, elapsed_min,
                                session_high/low, current_bid
logs/frg_transitions.jsonl      bascules -- BEGAIE autour du seuil
                                chop 50, sans hysteresis : ne pas
                                s en servir comme source des bascules
```

`HYPOTHESES.md` contient les dix-huit hypothèses avec, pour chacune,
son critère de réfutation et **ce qui la rendrait vraie par
construction**. Toute conclusion qui ne correspond à aucune de ses
lignes est une trouvaille de fouille : à re-tester sur données neuves,
jamais à mettre en production.
