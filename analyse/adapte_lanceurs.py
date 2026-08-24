# -*- coding: utf-8 -*-
"""
adapte_lanceurs.py -- reecrit les chemins VPS des .bat et .cmd pour la
machine locale.

PAR DEFAUT IL NE MODIFIE RIEN. Il montre chaque ligne qu il changerait,
avant et apres, et s arrete. Il faut --appliquer pour qu il ecrive, et
il garde alors une copie .bak_local de chaque fichier touche.

CE QU IL REMPLACE, ET RIEN D AUTRE

    C:\\Users\\Administrator\\Downloads\\Scalp-EA-main\\Scalp-EA-main
        -> la racine ou ce script est lance

    ...\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe
    ...\\AppData\\Local\\Programs\\Python\\Python312\\python.exe
        -> l interpreteur qui execute ce script (sys.executable)

    Prendre sys.executable plutot qu un chemin ecrit a la main garantit
    que les lanceurs appelleront exactement le Python ou les paquets
    ont ete installes. Un second Python sur la machine, et la stack
    demarrerait sans MetaTrader5 sans que rien ne le dise.

CE QU IL NE TOUCHE PAS

    Les chemins vers Desktop\\Indicateurs\\Trading\\Bridge : c est un
    autre depot, absent d ici. Les reecrire ferait pointer des scripts
    vers un dossier qui n existe pas, ce qui est pire que de les
    laisser casses de facon visible. Ils sont listes a part.

    Les .py. Ceux-la utilisent des chemins relatifs ; ce sont les
    lanceurs qui posent le repertoire de travail.

GARDE-FOU

    Il refuse d ecrire si le dossier VPS d origine existe sur la
    machine -- signe qu on est sur le VPS et non sur la copie.

Usage :
    python "G:\\Mon Drive\\ScalpEA\\adapte_lanceurs.py" C:\\SVPS\\Scalp-EA-main
    python "G:\\Mon Drive\\ScalpEA\\adapte_lanceurs.py" C:\\SVPS\\Scalp-EA-main --appliquer
"""

import os
import sys

VPS_STACK = r"C:\Users\Administrator\Downloads\Scalp-EA-main\Scalp-EA-main"
VPS_PY = (
    r"C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\python.exe",
    r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe",
)
BRIDGE = r"C:\Users\Administrator\Desktop\Indicateurs\Trading\Bridge"

SUFFIXE = ".bak_local"


def octets(s):
    return s.encode("utf-8")


def montre(b):
    return b.decode("utf-8", "replace").rstrip("\r\n")


def main():
    args = [a for a in sys.argv[1:]]
    appliquer = "--appliquer" in args
    args = [a for a in args if not a.startswith("--")]
    racine = os.path.abspath(args[0]) if args else os.getcwd()

    if not os.path.isdir(racine):
        print("Ce chemin n est pas un dossier : %s" % racine)
        return 1

    py = os.path.abspath(sys.executable)

    print("=" * 72)
    print("racine       : %s" % racine)
    print("interpreteur : %s" % py)
    print("=" * 72)
    print("")

    # Le garde-fou. Sur le VPS ce dossier existe ; ici il ne doit pas.
    sur_le_vps = os.path.isdir(VPS_STACK)
    if sur_le_vps:
        print("REFUS : %s existe sur cette machine." % VPS_STACK)
        print("C est le dossier du VPS. Ce script est fait pour la COPIE,")
        print("pas pour l original. Rien n a ete lu ni ecrit.")
        return 1

    if os.path.normcase(racine) == os.path.normcase(VPS_STACK):
        print("REFUS : la racine donnee est celle du VPS.")
        return 1

    # (motif, remplacement) -- le plus long d abord, sinon un motif court
    # mangerait le prefixe d un plus long et le second ne matcherait plus.
    regles = [(octets(VPS_STACK), octets(racine))]
    for v in VPS_PY:
        regles.append((octets(v), octets(py)))
    regles.sort(key=lambda r: -len(r[0]))

    fichiers = []
    for f in sorted(os.listdir(racine)):
        if f.lower().endswith((".bat", ".cmd")) and not f.endswith(SUFFIXE):
            fichiers.append(os.path.join(racine, f))

    if not fichiers:
        print("Aucun .bat ni .cmd a la racine. Mauvais chemin ?")
        return 1

    a_changer = []
    bridge = []
    illisibles = []

    for chemin in fichiers:
        try:
            with open(chemin, "rb") as fh:
                brut = fh.read()
        except OSError as e:
            illisibles.append((os.path.basename(chemin), str(e)))
            continue

        lignes = brut.splitlines(True)
        modifs = []
        for i, l in enumerate(lignes, 1):
            neuf = l
            for motif, rempl in regles:
                if motif in neuf:
                    neuf = neuf.replace(motif, rempl)
            if neuf != l:
                modifs.append((i, l, neuf))
        if modifs:
            a_changer.append((chemin, lignes, modifs))
        if octets(BRIDGE) in brut:
            bridge.append(os.path.basename(chemin))

    print("-" * 72)
    print("A REECRIRE  (%d fichier(s))" % len(a_changer))
    print("-" * 72)
    if not a_changer:
        print("Rien. Soit c est deja fait, soit la racine n est pas la bonne.")
    for chemin, _lignes, modifs in a_changer:
        print("")
        print("%s  (%d ligne(s))" % (os.path.basename(chemin), len(modifs)))
        for no, avant, apres in modifs:
            print("  %4d  -  %s" % (no, montre(avant)))
            print("        +  %s" % montre(apres))
    print("")

    if bridge:
        print("-" * 72)
        print("LAISSES TELS QUELS -- ils pointent vers le depot Bridge")
        print("-" * 72)
        for n in bridge:
            print("   %s" % n)
        print("")
        print("Ce dossier n existe pas ici. Les reecrire les ferait pointer")
        print("vers un chemin inexistant, ce qui est pire qu une panne")
        print("visible. Ils ne servent pas au lancement de la stack.")
        print("")

    if illisibles:
        print("-" * 72)
        print("ILLISIBLES (%d)" % len(illisibles))
        print("-" * 72)
        for n, e in illisibles:
            print("   %s : %s" % (n, e))
        print("")

    if not appliquer:
        print("=" * 72)
        print("RIEN N A ETE ECRIT. C etait la simulation.")
        print("Relancez avec --appliquer pour reecrire pour de vrai.")
        print("=" * 72)
        return 0

    print("=" * 72)
    print("ECRITURE")
    print("=" * 72)
    faits = 0
    echecs = []
    for chemin, lignes, modifs in a_changer:
        neuves = list(lignes)
        for no, _avant, apres in modifs:
            neuves[no - 1] = apres
        bak = chemin + SUFFIXE
        try:
            if not os.path.exists(bak):
                with open(chemin, "rb") as fh:
                    orig = fh.read()
                with open(bak, "wb") as fh:
                    fh.write(orig)
            with open(chemin, "wb") as fh:
                fh.write(b"".join(neuves))
            faits += 1
            print("  %s  (copie gardee : %s)"
                  % (os.path.basename(chemin), os.path.basename(bak)))
        except OSError as e:
            echecs.append((os.path.basename(chemin), str(e)))

    print("")
    if echecs:
        print("%d ECHEC(S) :" % len(echecs))
        for n, e in echecs:
            print("   %s : %s" % (n, e))
    else:
        print("%d fichier(s) reecrit(s), aucun echec." % faits)
    print("")
    print("Pour revenir en arriere : renommer chaque %s en .bat ou .cmd."
          % SUFFIXE)
    print("=" * 72)
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
