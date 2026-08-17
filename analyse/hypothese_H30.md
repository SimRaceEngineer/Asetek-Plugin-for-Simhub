<!-- A concatener a la fin de HYPOTHESES.md sur le VPS -->

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
