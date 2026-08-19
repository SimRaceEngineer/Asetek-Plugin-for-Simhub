# Les 35 cles de l export -- etat au 19/08, apres papers_coupure

## Ce qui est etabli, et ne sera plus rediscute

**La population n y est pour rien.** `rails` et `churn` rendent le
MEME compte sur les 35 cles, sans une exception (4696 vs 4704 lignes).
J avais lu `limite=20000` comme une taille alors que c est un plafond.
Hypothese morte, tuee par le decompte.

**L ordre des operations sur les signaux n y est pour rien non plus.**
Fusion-puis-coupe et coupe-puis-fusion : 2902 signaux dans les deux
cas, et le meme compte sur les huit cles signaux. Aucune paire de
jumeaux n est a cheval sur la coupure. Question fermee.

**La coupure est identifiee par 25 contraintes.**
Bande commune : `[2026-08-18 12:20:06, 2026-08-18 13:54:15)`, 94 min.
Chaque fenetre individuelle vaut quelques minutes sur un etalement de
douze jours ; qu un point au hasard en satisfasse une vaut de l ordre
du pour-cent. Vingt-cinq simultanement n est pas un ajustement.

Pour memoire, l historique du meme parametre :
- papers_repare, 4 contraintes + une lue a la main : 19:26:10 -> 20 cles
- papers_population, 4 contraintes, `return bas` : 19:00:04 -> 18 cles
- papers_coupure, 33 fenetres, balayage : 12:20:06 -> **26 cles**

## Ce qui tombe juste : cinq sections ENTIERES

| section | cles |
|---|---|
| ecartement (trades, session) | 4/4 |
| par TF (trades, session) | 6/6 |
| accords TF (trades, session) | 3/3 |
| hlc vue C (trades, ALL) | 3/3 |
| leader (trades, session) | 3/3 |

Une cle isolee peut tomber juste par hasard. Cinq sections completes,
non.

## Ce qui reste, en trois causes distinctes

### 1. Quatre fenetres DISJOINTES -- au plus une des quatre est juste

Les quatre maxima du balayage ne forment pas un plateau : ce sont
quatre intervalles separes, chacun debloquant UNE seule cle.

    12:20:06 -> 12:40:01   M15_WIDE_CL
    13:18:03 -> 13:18:06   M15_LEAD      (3 secondes de large)
    13:26:34 -> 13:32:02   M5_WIDE_CL
    13:51:27 -> 13:54:04   M5_DIVG

Elles ne se recouvrent nulle part : ces quatre cles NE PEUVENT PAS
etre justes ensemble. Ce n est donc pas une question de coupure --
trois au moins ont un predicat faux. A la coupure retenue :
M5_WIDE_CL -3, M15_LEAD -2, M5_DIVG -6.

### 2. Trois qui DEBORDENT, et le motif designe la cause

Famille nest : les deux cles dont le predicat precise la direction
sont EXACTES ; les deux qui la laissent a `None` debordent d un
facteur ~2.

| cle | dv | compte / annonce |
|---|---|---|
| M5_ET_YES | `WITH` | 43 / 43 exact |
| M5_ET_NO_A | `AGAINST` | 104 / 104 exact |
| M5_ET_NO_C | `None` | **665 / 290** |
| M15_NO_MX | `None` | **724 / 396** |

J avais ecrit `veut_dv = None` avec pour commentaire "sens non precise
dans le libelle". Le libelle ne le precise pas ; la SECTION, elle, le
fait. A verifier dans `_section_mtf_nest`.

C_M15_VENTE deborde aussi : 513 pour 358 (x1,43), section vs pack, ou
M5_AGA_CH est exact.

Leurs fenetres se ferment le 07/08, le 10/08, le 14/08 -- des jours
avant le consensus. Aucune coupure plus tardive ne les sauvera : elle
ne fait qu ajouter.

### 3. Un DEFICIT : M15_SCA_MX

43 lignes disponibles pour 73 annoncees. Le predicat rate 30 lignes
qu il devrait attraper, quelle que soit la periode. Les trois autres
cles de hlc vue A sont exactes.

### Hors panneau : RSI_M1_BU (171), RSI_M15_BU (186)

Aucune section du panneau ne les produit ; le mot rsi n y apparait que
dans des legendes. Leur source est ailleurs et reste a trouver.

## La suite, et c est une LECTURE, pas un essai

`_section_mtf_nest`, `_section_vs_pack`, `_section_hlc_churn`,
`_nest_for` -- sortis tels quels par papers_extrait. La reponse est
dans le panneau. Continuer a essayer des variantes serait refaire
exactement la faute que ce carnet enregistre depuis le 14/08 :
raisonner sur ma reconstruction alors que la definition est dans un
fichier que j ai deja.
