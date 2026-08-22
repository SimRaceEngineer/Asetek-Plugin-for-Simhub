# Drive - ce qui reste a faire sur l ordinateur

Etat au 22/08/2026, apres l inventaire par API. L inventaire est arrete ici
a ta demande : la suite se fait sur la machine, ou tu vois les dossiers et
les tailles directement.

## 1. Etat mesure du compte

    Total          200,09 Go sur 200 Go   (sature)
    Drive          120,55 Go
    Photos          69,16 Go
    Gmail            7,02 Go
    WhatsApp         3,34 Go

Le poids du Drive est concentre dans de vieux dumps MySQL de tes sites,
ranges dans DEUX arborescences de sauvegarde qui se recouvrent en grande
partie. Les deux vivent sous un dossier parent sans parent visible
(section "Ordinateurs" du Drive), ce qui explique pourquoi un inventaire
lance depuis "Mon Drive" ne voyait que 9,4 Go sur 120,55.

## 2. Fait

27 doublons supprimes (3 par toi, 24 par moi), soit 7,39 Go.

Critere de preuve utilise pour chaque suppression, sans exception :
nom identique + nombre d octets identique + date de modification d origine
identique a la seconde. Aucun fichier supprime sur la seule ressemblance
du nom.

## 3. A FAIRE EN PREMIER : vider la corbeille

Tant que la corbeille n est pas videe, les 7,39 Go ne sont PAS rendus.
Google les garde 30 jours. C est le geste qui a le meilleur rapport
effort / gain de toute cette liste, et il prend dix secondes.

    drive.google.com/drive/trash   ->   Vider la corbeille

A verifier juste apres sur drive.google.com/drive/quota : le total doit
passer d environ 200,09 Go a environ 192,7 Go.

## 4. A FAIRE : comprimer les dumps .sql restants

C est le gros du gain, et de loin.

Mesure faite sur tes propres fichiers, pas une estimation theorique :
un dump deja zippe present sur ton Drive pese 35 945 732 octets, alors que
les dumps bruts de la meme generation pesent entre 300 Mo et 1 Go.
Facteur de compression constate : 8 a 12.

Si la branche 2024 contient de l ordre de 60 Go de .sql bruts, on descend
a 5 a 8 Go. Gain attendu : 50 a 55 Go.

Un .sql est du texte, il se comprime tres bien et le zip se relit tel quel
si un jour tu dois restaurer. Aucun risque a comprimer, a condition de
verifier l archive avant d effacer l original.

Ordre des gestes, par lot, jamais en une seule passe sur tout :
  1. comprimer un lot
  2. ouvrir l archive et verifier qu elle liste bien les fichiers attendus
  3. seulement ensuite supprimer les .sql d origine du lot
  4. vider la corbeille a la fin

## 5. A FAIRE : finir la verification des doublons

Deux endroits n ont pas ete parcourus jusqu au bout, l API ne rendant
qu une page de resultats a la fois.

Les deux arborescences, chemins complets :

  Branche A
    Abaure
      > Sauvegarde ABAURE
        > Sauvegarde disque dur externe
          > Fournisseurs
            > prestashop manager      (page 2 et suivantes non verifiees)

  Branche B
    Abaure
      > Sauvegarde ddur portable imac
        > ABAURE
          > Fournisseurs
            > prestashop manager      (page 2 et suivantes non verifiees)

Identifiants Drive, pour ouvrir directement :

    Abaure                          1--fWmmu9o3Z9hKOHNSeNEsW0J8tmMEn9
    Sauvegarde ABAURE               1-Sx54xdVkujcaxQYArKKOzm0mjzBmONX
    Sauvegarde disque dur externe   1-Z9qPSE9BcO0ftbqwCYjfYtJTzZ48P7n
    Fournisseurs (branche A)        1-uXLkkLuKS0luwQ5WxfzlKsAh5XTsUNt
    prestashop manager (branche A)  18vF7Rp2XzfSsvbgPkH-NWOwMamUgJDmz

    Sauvegarde ddur portable imac   1gMNgVutK6AEJr5riWk3Bbe3Zf5yuz9Fe
    ABAURE                          1EJ8Tt6aUsDk6HPQNT1Xrn4Ukc826_19d
    Fournisseurs (branche B)        1mU7az8vNIrhrSMgTcQNAS8KSbraL-H_1
    prestashop manager (branche B)  1ieAsbLpJZxSATQBoSctKBVte34xXajjW

Une URL se fabrique ainsi :
drive.google.com/drive/folders/ suivi de l identifiant.

Reste aussi a parcourir : le reste de la branche
"Sauvegarde ddur portable imac", qui n a ete ouverte que sur ses premiers
niveaux.

Sur l ordinateur, le tri par taille dans l explorateur remplace tres
avantageusement l API : tu vois immediatement les paires nom + taille
identiques.

## 6. NE PAS FAIRE

Environ 40 petits doublons .cfg et .ini, pour 650 Ko au total.
Le temps passe ne vaut pas le gain. A ignorer.

## 7. Ordre recommande

    1. vider la corbeille              gain immediat  7,39 Go
    2. comprimer les .sql restants     gain attendu   50 a 55 Go
    3. revider la corbeille
    4. finir la verification des doublons des deux "prestashop manager"

Apres les etapes 1 a 3 le compte devrait etre repasse largement sous la
limite, et l etape 4 devient du confort, plus une urgence.
