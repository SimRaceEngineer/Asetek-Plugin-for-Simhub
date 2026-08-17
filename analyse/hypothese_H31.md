<!-- A concatener a la fin de HYPOTHESES.md sur le VPS -->

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
