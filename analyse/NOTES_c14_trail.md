# C14 contre le trailing MFE — ce qui est établi, ce qui ne l'est pas

État au 11/08/2026, 19h30. À relire avant de toucher à `mfe_ticket_trail.py`
ou à `buddha_clause_gate.py`.

Cette note existe parce que le raisonnement de la soirée a changé de cible
trois fois. La version finale est la bonne, les deux premières étaient
fausses, et sans trace écrite ce sont elles qu'on se rappellerait.

---

## Le fait central

`mfe_ticket_trail` pose son premier stop (cran BE) à **0,004 %** du prix
d'entrée. `buddha_clause_gate.C14` refuse tout resserrement qui atterrit à
moins de **0,040 %** (US30, US500) ou **0,069 %** (NAS100) de l'entrée.

La fenêtre de veto est **dix à dix-sept fois plus large** que l'endroit où le
cran BE pose son stop. Ce n'est pas un réglage malheureux : aucun niveau de
MFE ne peut faire sortir le cran BE de la fenêtre, puisqu'il pose toujours le
stop au même endroit, à l'entrée.

**62 709 refus sur 62 732 tentatives** du 28/07 au 11/08. 23 succès, sans
doute les instants où Buddha était en `INIT` ou retourné.

Conséquence : **149 tickets sur 343 n'ont jamais obtenu un seul déplacement
de stop.** Leur sort dépend entièrement du closer Python.

---

## La bande morte

Entre le cran interdit (BE, à 0,08 % de MFE) et le premier cran qui franchit
la fenêtre (lock50, à 0,16 %), aucune protection n'est possible.

| actif | bande morte, en MFE |
|---|---|
| US30 | 40 → 80 pts |
| NAS100 | 23 → 47 pts |
| SPX500 | 6 → 12 pts |

**154 tickets, 45 % du corpus**, y vivent et y meurent. Pic moyen 20,7 points.

---

## Ce qui prouve que le stop est bien la cause

`discontinuite.py`, lecture par tranche de pic rapporté au seuil lock50 :

| pic / seuil | tickets | avec stop | capture |
|---|---|---|---|
| 0,5 – 0,7 | 86 | 3 | 23 % |
| 0,7 – 0,9 | 46 | 2 | 20 % |
| 0,9 – 1,0 | 14 | 0 | **−4 %** |
| **1,0 – 1,1** | 92 | 92 | **57 %** |
| 1,1 – 1,3 | 24 | 24 | 50 % |
| 2,0 et + | 55 | 53 | 71 % |

Deux arguments, et le second est le plus fort :

1. **La marche est à la frontière**, +55 points de capture sans que
   l'amplitude ait bougé de plus de quelques dixièmes de point.
2. **En dessous du seuil, plus d'amplitude donne MOINS de capture**
   (23 → 20 → −4). Si le confondant d'amplitude expliquait quoi que ce soit,
   ces trois lignes monteraient. Elles descendent.

Confirmation interne : la capture de chaque zone colle à son cran. Stop à
50 % du MFE → capture mesurée 57 %. Stop à 70 % → capture 71 %. C'est le
stop qui détermine la sortie, et ça se voit dans le chiffre.

Les deux actifs le montrent, avec des fenêtres C14 différentes :
NAS100 −19 % → +59 %, SPX500 +34 % → +66 %.

---

## Le réglage que les données désignent

`sweet_spot.py` : armement à **0,12 %** du prix, stop à **70 %** de
l'armement, soit un stop à **0,084 %** du prix.

- NAS100 : armer à 34,6 pts de MFE, stop à 24,2 pts (fenêtre 20, marge 4,2)
- SPX500 : armer à 9,1 pts, stop à 6,3 pts (fenêtre 3, marge 3,3)
- 230 éligibles, 102 sauvés, **zéro refusé par C14**
- gain plafond **2 149 €** sur onze séances, soit ~195 €/séance au mieux

**Ce n'est pas une règle nouvelle.** Le cran lock50 actuel pose déjà le stop
à 0,080 % du prix. Le candidat le pose à 0,084 %. Le même endroit. La seule
chose qui change est le moment de l'armement, un quart plus tôt. On
déclencherait plus tôt une règle qui capture déjà 57 % en production.

Cohérence : à 0,16 % et au-delà le gain tombe à zéro, parce que la règle
s'applique déjà là. Tout le gain se concentre dans la bande morte. Le
tableau retrouve seul la zone identifiée par un autre chemin.

---

## Ce qui manque, et qui interdit de conclure

**Le taux d'aller-retour.** Le journal porte le pic de MFE, jamais les creux.
On peut donc chiffrer ce qu'un stop rapporte en sauvant des trades finis en
dessous de lui ; on ne peut pas chiffrer ce qu'il coûte en sortant des trades
qui seraient remontés — la pathologie M94/M95 pour laquelle C14 a été écrit.

Le gain de 2 149 € est un **plafond**. Le taux de bascule (gain / exposition)
vaut 39 % : la règle reste gagnante tant que moins de 39 % des gagnants
au-dessus du stop y seraient repassés.

Et cette métrique a son propre défaut : elle **monte mécaniquement quand le
stop se resserre**, alors que c'est précisément là que le coût non modélisé
est le plus grand. Ne pas comparer deux lignes de la grille sur ce seul
chiffre.

**Le taux réel est mesurable sans rien risquer.** `c14_set_live(False)` met
la clause en observation : elle journalise `[C14 OBSERVE] would-block` et
laisse passer. Deux ou trois séances suffisent. C'est la seule chose à faire
avant de changer une constante.

---

## Ce que C14 n'est pas

Ce n'est pas une erreur. Le fichier porte sa justification, datée du
06/05/2026 :

> M94/M95 enter +6 MFE, SL moves to BE+6, pullback hits SL = exit at +0.3
> while trend continues. Buddha HOLD says "no flip → don't pinch yet".

Le gate distingue correctement un resserrement d'un desserrement, exempte les
magics autonomes, les fermetures forcées et les actifs hors indices, et
laisse passer tout stop posé au-delà de sa fenêtre. C'est une règle étroite,
délibérée et argumentée.

Le problème n'est pas le veto. C'est qu'entre un stop à 1,2 point de l'entrée
et le stop d'origine à mille points, **aucun module ne propose de cran
intermédiaire**.

---

## Trois erreurs de la soirée, gardées exprès

1. **`dow_cap_gate` accusé le premier.** Six lignes de log lues pendant
   l'initialisation du moteur. Il compte pour 212 refus sur 3 922 ce jour-là,
   et 3 930 sur 63 915 au total. Réel mais mineur — sauf aux crans 2 et 3,
   où il est en revanche le blocage dominant (1 206 refus).
2. **« SPX500 est neutralisé de bout en bout ».** Faux, son cran lock50
   franchit C14 sans problème.
3. **« Le taux d'échec est de 99 % ».** Le log du moteur ne journalise pas
   les succès : 3 922 était un numérateur sans dénominateur. C'est le CSV
   `mfe_trail_events.csv`, qui porte `retcode`, qui a donné le vrai taux.

Le point commun des trois : conclure depuis le log du moteur plutôt que
depuis le journal du module. Le CSV existait depuis le début.

---

## Non résolu

**Aucune ligne US30 dans `mfe_trail_events.csv`**, du 28/07 au 11/08. Zéro
tentative, alors que le module annonce au démarrage `managing
US30/NAS100/SPX500`. Piste la plus probable : les magics autonomes, que
`_is_autonomous_magic` fait sortir de C14 *et* du trail — le log du 11/08
disait `[R6] TRAIL: 0 positions (excl XAUUSD + autonomous) / 19 total`.

À trancher avant tout réglage : si US30 est hors du dispositif, la moitié du
volume l'est aussi.
