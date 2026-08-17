<!-- A concatener a la fin de PROTOCOLE.md sur le VPS. -->
<!-- Tout ce que le 17/08 ajoute a ce document, en UN seul -->
<!-- morceau. Remplace les fragments separes, desormais -->
<!-- prefixes _PERIME_ sur le Drive. -->

---

## 6 bis. La branche macro est CLOSE en l'état (17/08)

`reaction_evenements.py` sort, sur les trois symboles, **`AUCUN
horizon n'est testable`**. Ce n'est pas un manque de puissance, c'est
une impossibilité de construction :

- le seuil de 4 occurrences ne garde que **deux séries hebdomadaires**
  (EIA le mercredi, inscriptions au chômage le jeudi) ; CPI, NFP, Fed,
  ISM, PMI sont tous à 3 occurrences et tombent ;
- ces deux séries tombent **toujours le même jour de la semaine**,
  tandis que les témoins sont pris sur les journées sans publication,
  donc **jamais** un mercredi ni un jeudi à l'intérieur du calendrier ;
- il n'existe donc aucun mercredi ni jeudi témoin à mettre en face.
  Rien à permuter.

**Ce qui débloque, et rien d'autre : étendre le calendrier vers le
passé.** Les barres remontent au 28/12 ; le calendrier commence au
01/06. Les 28 événements écartés sont précisément les poids lourds, et
ils ne tombent pas tous le même jour de semaine — ce qui rouvre la
stratification du même coup.

**Ne pas** baisser `--mini-occurrences` : ça normaliserait des
surprises sur deux points.

Chiffre à retenir : le seul résultat significatif de la journée
(`-1330` contrats à 15 min, p = 0,0015) est tombé à `-267` sans
p-value une fois le témoin borné au calendrier. C'était le changement
d'échéance du 16 juin, pas une réaction macro.

---

## 8. Ce que SierraChart donne, mesuré le 17/08

```
of_MES-continu.csv   183 314 barres   28/12 -> 17/08   mediane 1260 b/j
of_YM-continu.csv    160 257 barres   29/12 -> 17/08   mediane 1250 b/j
of_TICK-NYSE.csv     124 279 barres   27/01 -> 04/08   mediane  961 b/j
```

**Deux actifs au même grain, enfin.** Avant le 17/08, `YMU26` seul
donnait **131 barres par jour** — deux heures d'activité par séance,
inutilisable pour regarder une minute précise. Avec `YMM26`, le Dow est
mesurable comme le S&P, et la divergence US30/US500 devient une mesure
au lieu d'une impression.

Roulements mesurés (par volume dominant, persistance de 3 séances) :
**MES le 16/06**, **YM le 15/06**. Un jour d'écart, cohérent.

`TICK-NYSE` s'arrête au **4 août** : le `.scid` n'a pas été
retéléchargé. Toute fenêtre postérieure l'écartera d'elle-même par
contrôle de couverture — ce n'est pas un bug de nos outils.

### Deux pièges de chaîne, tous deux trouvés le 17/08

1. **Un raccord relu comme une échéance.** `of_MES-continu.csv`
   commence par `MES` : un `--racine MES` naïf le recharge, il domine
   le volume tous les jours puisqu'il contient tout, et le nouveau
   raccord n'est qu'une copie de l'ancien. *La version du VPS ne fait
   pas cette faute* — vérifié : elle trouve bien 2 échéances avec le
   continu présent dans le dossier.

2. **Les mêmes barres comptées trois fois.** Le continu et ses deux
   échéances cohabitent dans `cartes\scid\`. La règle : un fichier qui
   porte une colonne `contrat` déclare lui-même les échéances qu'il
   absorbe. On lit ce que les données déclarent, jamais un motif de nom
   de fichier.

### La règle qui manquait, et qui vaut au-delà de l'orderflow

**Absence de donnée n'est pas donnée d'absence.** Une journée hors de
la plage couverte par une source n'est pas une journée « sans
événement » : c'est une journée dont on ne sait rien. Tout groupe
témoin doit être borné à la plage réellement couverte, et cette plage
se lit dans le fichier.

---

## Outils ajoutes le 17/08

| outil | ce qu'il fait |
|---|---|
| `contrat_continu.py` | raboute deux échéances par le volume mesuré, colonne `contrat` |
| `patch_base.py` | écarte les fenêtres à cheval sur un roulement |
| `patch_doublons.py` | écarte les échéances déjà contenues dans un raccord ; mesure en points les séries qui traversent zéro |
| `patch_permutation.py` | composition des groupes par jour de semaine + p par permutation stratifiée |
| `patch_temoin.py` | borne le témoin à la plage réellement couverte par le calendrier |
| `bougie_deux_actifs.py` | une bougie décrite sur deux carnets, minute par minute, étalon = la séance |
