<!-- A concatener a la suite de H30 dans HYPOTHESES.md -->

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
