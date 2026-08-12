# Feuille de route du 13/08 -- ecrite le 12/08 a 16h40

## L observation du jour -- et sa correction, une heure plus tard

Premiere lecture : le 12/08, **US30 perd pendant que US100 et US500
gagnent**. Hypothese proposee : US30 serait le laggard de
l apres-midi, il lui faut une **etiquette**, et on ne le traderait pas
avant 16h30.

**Les graphiques M1 des trois indices ont refute cette lecture le jour
meme.** Montee reguliere jusqu a 15h28, une bougie de chute violente a
15h30 -- l ouverture du cash US -- puis une heure de hachoir. US100
entre 29 740 et 29 840, US30 entre 53 740 et 53 870, US500 entre 7 736
et 7 758. Trois amplitudes, **un seul comportement**, a la meme minute.

Ce n est donc pas une propriete d US30 : c est un REGIME, synchronise
sur les trois. Si US30 a perdu davantage, c est vraisemblablement parce
qu il est le plus large en points et qu un hachoir coute a proportion de
l amplitude.

### La question devient donc autre, et meilleure

**Cet apres-midi etait-il detectable en temps reel par quelque chose
qu on calcule deja ?** On dispose des verdicts churn (CHURN / MIXED /
CLEAN), du VIX, de `range_pos`, de l alignement HLC. Le panneau
annoncait d ailleurs « US30 reste en CHURN » vers 13h30 pendant que
US100 passait OK.

    Si les detecteurs ont dit CHURN entre 15h30 et 16h40
        -> l information existait et personne ne s en est servi.
           C est un correctif de BRANCHEMENT, pas de recherche.

    S ils ont dit CLEAN
        -> ils sont aveugles a ce motif. C est un vrai sujet.

A faire en premier demain, c est une lecture de journal, pas une etude :
relever ce que les verdicts churn et le regime ont dit sur les trois
actifs, minute par minute, entre 15h25 et 16h45 le 12/08.

### Si malgre tout on veut une regle horaire

### Le piege a eviter

Une journee est **une** observation. Le 12/08 peut etre la regle ou
l exception, et rien dans ce qu on a mesure aujourd hui ne permet de
trancher. Exactement comme le creneau 09h-11h ce matin : la moyenne par
ticket paraissait ecrasante, et il a fallu passer a la seance pour
savoir si elle tenait.

Le meme traitement s impose donc ici, et dans cet ordre :

1. **Le fait, d abord.** P&L par actif et par heure, sur les 12 seances
   du corpus. US30 est-il negatif le matin sur la plupart des seances,
   ou seulement aujourd hui ?
2. **La seance comme unite.** Sur combien de seances US30 finit-il la
   matinee dans le rouge quand US100 et US500 finissent dans le vert ?
   Test du signe. C est ca, la question.
3. **Le contrefactuel.** Ce que la stack aurait fait sans les entrees
   US30 avant 16h30 -- en sachant que c est un plafond, pas une
   prevision.
4. **Le cout.** Combien de tickets et combien d euros on ampute. US30
   pese 1069 tickets sur le corpus ; couper huit heures de sa journee
   n est pas un reglage mineur.

### L etiquette

Si le fait tient, il faudra le NOMMER avant de le coder. Et le nom
compte : « US30 est le laggard » et « l apres-midi post-ouverture est un
hachoir » ne donnent pas le meme correctif. Le premier coupe un actif,
le second coupe une fenetre pour tout le monde -- et seul le second
colle a ce que montrent les graphiques du 12/08.

Une regle sans mecanisme derriere ne survivra pas au premier mois ou
elle se trompe. On a vu aujourd hui ce que vaut une explication
plausible mais non testee -- trois fois, dont celle-ci.

## Ce qui reste a faire, par ordre

### 1. Les deux onglets de la page 8095
`rails_range_panel.py` et `rails_trois_panel.py` sont ecrits, testes,
et rendent 11 768 et 16 980 caracteres. Il manque le branchement, qui
demande quatre pieces et non une :

    price_action.py:4260   l onglet         <div class="tab" onclick="showTab('railstr')">
    price_action.py:4540   le bloc          <div class="panel" id="p-railstr">
    price_action.py:4541   l iframe         <iframe id="railstr-iframe" src="about:blank">
    price_action.py:4911   la branche JS    if (t === 'railstr') { ... }

    plus la route HTTP qui sert le HTML a l iframe.

Quinze minutes a froid. Ne pas improviser en fin de journee.

### 2. Verifier la seance complete du 12/08
A faire apres la cloture si ce n est pas deja fait :

    python rails_join.py
    python bande_morte.py --depuis 2026-08-12

Les 60 % de capture du trail reposent sur **sept** tickets et une
demi-seance. La seance entiere dira s ils tiennent.

### 3. Deuxieme releve des threads
Le 12/08 a 15h49 : 350 threads, 1108 handles, 813 Mo sur le processus
principal. Un releve ne fait pas une tendance. Refaire exactement la
meme commande demain :

    Get-Process python,terminal64 | Sort-Object CPU -Descending |
      Select-Object -First 8 Id, ProcessName,
      @{n='RAM_Mo';e={[int]($_.WS/1MB)}},
      @{n='Threads';e={$_.Threads.Count}}, Handles,
      @{n='CPU_s';e={[int]$_.CPU}}

Si on passe a 500-600 threads, c est une fuite -- et changer de machine
ne la corrigera pas, ca la rendra seulement plus lente a se manifester.

### 4. La migration VPS -> MSI Trident 2
`inventaire.py` est ecrit et teste. Il reste a le lancer des deux cotes
et a comparer. Mais **la mesure du 12/08 ne montre aucun
sous-dimensionnement** : 16 Go dont 9,6 libres, 6 vCPU, deux coeurs
utilises sur six, handles normaux. Il faut mesurer PENDANT un episode
d irresponsivite, pas quand tout va bien.

A garder en tete : un VPS en centre de donnees a l onduleur, la
redondance reseau et la surveillance. Un Trident sous un bureau a une
prise, une box et Windows Update.

## Les gels en cours, et leurs dates

| gel | ce qu il mesure | verdict |
|---|---|---|
| V9 | reference in-sample, couverture famille X | 01/09 |
| trail/BE + US30 207 | part des tickets obtenant un stop, capture | 27/08 (10 seances) |
| SARKEEP M1 vs M5 | latent au signal contre realise final | 01/09 |
| creneau 09h-11h | a reprendre par famille 206 seule | non pose |

Le SARKEEP M5 (`sarkeep_m5.py`) et l observateur M1 (`sarkeep_gel.py`)
tournent en lecture seule depuis le 12/08. Verifier au demarrage que le
M5 annonce bien `sar_anchor._compute_sar -- MEME calcul que le M1` :
sinon la comparaison M1/M5 perd sa validite.

## Ce qu on a appris aujourd hui, en une ligne chacun

- Le cran BE du trail etait refuse 62 709 fois sur 62 732 par C14. Repare.
- US30 etait exclu du trail depuis 15 jours. Repare, 3 lignes le 12/08.
- Le creneau 09h-11h perd 10 180 EUR sur 11 seances, mais la perte est
  portee par la famille 207 hors trail, pas par l heure seule.
- 206 se gere jusqu au reverse, 207 est traille : la comparaison n avait
  aucun sens avant le 12/08, les deux bras etaient autonomes.
- Le SAR ancre attend des magics 1710-1712 qui ne tradent plus.
- Le mode autonomie EA dure depuis 112 jours au lieu de 2-3, mais il
  n a plus d effet reel : un seul fichier n est plus ecrit, et personne
  ne le lit.

## Trois sur-lectures, un seul remede

Le creneau du matin attribue au trailing. La famille 207 condamnee sur
un sous-ensemble biaise. Le watchdog accuse de tuer son propre
processus. Les trois fois, une inference de trop au-dela de ce que la
donnee portait -- et les trois fois, une commande a suffi a trancher.

Mesurer avant de conclure. C est moins rapide et c est la seule chose
qui a marche aujourd hui.
