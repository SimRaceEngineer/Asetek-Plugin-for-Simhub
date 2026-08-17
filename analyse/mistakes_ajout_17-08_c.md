<!-- A concatener a la fin de mistakes.md sur le VPS -->

---

## 17/08/2026 — un résultat significatif qui n'était qu'un changement d'échéance

**Le chiffre.** Après avoir corrigé le décompte des doublons, mesuré le
TICK en points, et ajouté une permutation par journée stratifiée par
jour de semaine, un seul nombre survivait sur trente-six tests :

```
MES-continu   15min delta   -1330 contrats   p = 0,0015
```

Trois symboles, douze tests chacun. Un seul sortait. C'était, au sens
strict, le premier résultat mesuré de la journée.

**Pourquoi je ne l'ai pas rapporté.** Trois faits ne collaient pas :

```
YMU26-CBOT   un seul contrat sur sa plage    rien sur 12 tests
TICK-NYSE    pas de contrat du tout          rien sur 12 tests
MES-continu  le seul qui bascule d echeance  le seul qui sort
```

Le raccord passe de `MESM26` à `MESU26` le 16 juin. Le calendrier
commence le 1er juin. Les journées témoins étaient donc prises pour
l'essentiel **avant** juin — c'est-à-dire sur l'autre échéance, avec un
autre niveau de volume. Un delta cumulé ne se compare pas d'un contrat
à l'autre.

**Ce que la correction a donné.** En bornant le témoin à la plage que
le calendrier couvre réellement : **−1330 → −267**, et plus aucune
p-value, parce que plus rien n'est testable.

**La faute de fond, et elle n'est pas dans le code.** Une journée était
déclarée « sans publication » dès qu'elle n'apparaissait pas dans le
fichier d'événements. Or le fichier commençait en juin. De janvier à
mai il n'y avait aucun événement **dans le fichier** — il y en a eu des
dizaines dans le marché. **L'absence de donnée était lue comme une
donnée d'absence.**

155 des 235 journées témoins tombaient hors calendrier. Le groupe
témoin était à ~85 % constitué de journées dont on ne savait rien, et
la comparaison n'était pas « avec surprise contre sans surprise » mais
**juin-août contre janvier-mai**, avec un changement de contrat au
milieu.

**Ce qui l'a attrapé.** Pas un contrôle automatique : la table de
composition par jour de semaine. Elle affichait 22 mercredis témoins et
21 jeudis témoins, alors que EIA tombe tous les mercredis et les
inscriptions au chômage tous les jeudis. Ces témoins-là ne pouvaient
pas exister à l'intérieur du calendrier — donc ils venaient d'ailleurs.
C'est en cherchant d'où qu'on trouve le reste.

**Les règles.** Absence de donnée n'est pas donnée d'absence : un
témoin doit être une journée **vérifiée** sans événement, dans une
plage **couverte**, et la plage se lit dans le fichier. Et quand un
seul symbole sur trois sort un résultat, chercher d'abord ce que ce
symbole a de particulier — ici, il était le seul à changer de contrat.

**Le contre-poids, pour être juste.** La chaîne a fonctionné : chacun
des quatre correctifs de la journée a été prédit, benché sur données
synthétiques, puis vérifié sur les vraies. Le seul résultat
significatif de la journée est mort d'une objection formulée **avant**
de le tester. C'est le fonctionnement normal, pas un échec — mais s'il
n'y avait pas eu de table de composition, il serait dans un panel, et
on construirait dessus la semaine prochaine.
