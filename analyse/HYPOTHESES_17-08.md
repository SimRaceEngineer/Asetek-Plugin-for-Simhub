<!-- A concatener a la fin de HYPOTHESES.md sur le VPS. -->
<!-- Tout ce que le 17/08 ajoute a ce document, en UN seul -->
<!-- morceau. Remplace les fragments separes, desormais -->
<!-- prefixes _PERIME_ sur le Drive. -->

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

---

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

---

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
