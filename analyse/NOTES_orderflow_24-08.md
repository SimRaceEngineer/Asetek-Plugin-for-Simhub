# Orderflow : dossier clos le 24/08/2026

Verdict : **l abonnement a un flux orderflow live ne se justifie pas.**
Quatre mesures independantes convergent. Ce document existe pour que la
question ne soit pas rejouee dans trois semaines sans element nouveau.

## 1. Le gel V9 le disait deja

Contrefactuel du panneau, PnL par signal apres moins avant :

    creneau 09h-11h      +5,43
    PLAT ou DIVERGENT    +2,58
    churn a l entree     +1,30
    flux ER < 0,40       +0,50
    flux CARNAGE seul    +0,08
    CONTRE-FLUX          -0,15

L orderflow entier vaut moins d un dixieme du simple filtre horaire, et
la regle anti-contre-flux DEGRADE le resultat.

## 2. Les .scid n ont aucun pouvoir predictif, a aucune echelle

`scid_echelle.py`, 1 a 1000 ticks, US30 et US500, temoin par
permutation des seuls deltas :

  - la correlation delta / variation de la MEME barre est forte (0,21 a
    0,71) mais tautologique : un trade execute a l ask EST un tick
    haussier ;
  - decalee d une barre -- la seule version qui se traduise en ordres --
    elle est NEGATIVE partout : -0,028 sur US30, -0,105 sur US500. Le
    flux annonce l inverse du mouvement suivant, signature du rebond
    bid-ask ;
  - aucun niveau d absorption ne se detache une fois corrigee la part
    des barres que les seuils laissent reellement passer, et une fois
    le temps de sejour a chaque prix pris en compte.

## 3. La fraicheur du flux n achete rien

`croise_flux.py`, accord entre la bande ER d il y a N secondes et celle
de l instant de l entree :

    retard        US500 (hasard 44,2 %)   US30 (hasard 27,1 %)
       60 s              49,4 %                  35,1 %
      300 s              48,3 %                  35,2 %
      600 s              51,8 %                  35,8 %
     1800 s              52,5 %                  34,6 %

Plat. La bande d il y a une demi-heure vaut celle de maintenant. Le
faible exces sur le hasard est la tendance generale de chaque actif,
pas un etat local qui se degrade. Un flux a la seconde donnerait donc
la meme chose qu un flux vieux de trente minutes.

## 4. Rien ne survit hors echantillon -- douze tests, douze echecs

Regle apprise sur une moitie de la periode, appliquee telle quelle sur
l autre, dans les deux sens, pour les parents comme pour les miroirs
220/230/240, en lecture live comme en barre M1 precedente.

Le cas decisif est celui qui paraissait le meilleur. US30 parents,
barre M1 precedente, 18,22 d ecart et 0 fois sur 400 au hasard --
le seul tableau significatif de tout le dossier :

        applique a l autre moitie (377 trades) :
          sans regle        +2275.50
          avec la regle      +804.21   (330 ecartes, 88 %)
          gain              -1471.29

La regle detruit 1471 sur une demi-periode qui gagnait 2275 sans elle.

## LE MECANISME, ET C EST LUI QU IL FAUT RETENIR

La premiere moitie (14 -> 18/08) perd sur TOUTES les bandes, sur les
deux actifs. La seconde (18 -> 21/08) gagne. Toute bande presente dans
la premiere moitie paraıt donc perdante, et l ecarter dans la seconde
revient a jeter la bonne periode.

**Les bandes ER captent QUAND le trade a eu lieu, pas dans quel flux il
a ete pris.** La variation entre periodes ecrase la variation entre
bandes. C est pourquoi les tableaux in-sample sont spectaculaires et
les regles s effondrent dehors.

## RESERVE, ET POURQUOI ELLE NE CHANGE PAS LA CONCLUSION

L ER recalcule depuis les ticks n a PAS pu etre verifie : les 5811
tickets de docs/rails_trades/tickets_rails.jsonl ne portent aucun champ
_er. Ce n est ni un chemin ni un nom d actif -- le champ est absent. La
demo Sierra etant terminee, il n y aura pas d occasion de le caler.

Les bandes ci-dessus sont donc une RECONSTRUCTION. Mais l effet de
periode qui fait tomber toutes les regles ne depend pas des bornes :
meme decalees d un cran, elles resteraient dominees par le calendrier.

## MISE EN GARDE QUI DEPASSE L ORDERFLOW

Le gradient gele de V9 -- US30 CARNAGE +1,57 (59), MOU -14,59 (47),
CORRECT +11,97 (48), PROPRE +20,43 (24) -- n a jamais ete passe hors
echantillon. Il a exactement la forme de ce qui vient de s effondrer.
Cela ne le rend pas faux : cela veut dire qu on ne sait pas, et qu on
dispose desormais de l outil pour le savoir.

Tout tableau construit en cherchant la meilleure decoupe DANS les
donnees puis juge SUR les memes donnees est expose au meme piege. Le
test de permutation limite les degats ; seul le hors echantillon
tranche.

## CE QUI A SURVECU

La coupure de 13h : 19 seances, 16 rouges avant, binomiale 0,0022,
tenue en retirant les trois pires jours, repliquee dans les deux
regimes. Le temps domine le flux -- ce qui est exactement ce que la
section precedente vient de montrer par un autre chemin.
