# -*- coding: utf-8 -*-
r"""
disque_grossit.py -- qu est-ce qui remplit le disque, et depuis quand

  python disque_grossit.py
  python disque_grossit.py --racine "D:\ailleurs" --jours 14

LECTEUR SEUL. N EFFACE RIEN, NE DEPLACE RIEN, N ECRIT AUCUN FICHIER.

LE CONSTAT QUI L A DECLENCHE

    Vingt Go liberes il y a une semaine, quatre Go restants aujourd hui.
    Et AUCUNE note dans le depot sur ce qui avait ete efface -- j ai
    cherche dans les 25 .md de analyse\, rien. Une operation faite et
    non consignee est une operation qu on refait, indefiniment.

    Ce script ne libere rien. Il DESIGNE, pour qu on puisse decider une
    regle au lieu de refaire un menage.

CE QU IL MESURE, ET POURQUOI CES ENDROITS-LA

    L espace libre de chaque volume, d abord : sans lui, tout le reste
    est une opinion.

    Puis les suspects habituels quand "le disque local ET le Drive" se
    remplissent ensemble :

      DriveFS        Google Drive pour ordinateur garde un CACHE LOCAL
                     qui peut peser des dizaines de Go sans que rien
                     n apparaisse dans le Drive. Suspect numero un.
      MetaQuotes     l historique et les journaux du terminal MT5
                     grossissent sans limite par defaut.
      Temp           ce que personne ne vide.
      Chrome         le cache du navigateur.
      le stack       docs\ et logs\, mesures a 11,2 Go et 2,4 Go, tous
                     deux ecrits aujourd hui.

    Pour chacun : la taille, et surtout ce qui a ete ECRIT dans les N
    derniers jours. Un dossier de 30 Go fige depuis un an n est pas le
    probleme ; un dossier de 3 Go entierement reecrit cette semaine
    l est, parce qu il recommencera la semaine prochaine.

CE QU IL PROPOSE, SANS LE FAIRE

    Pour chaque endroit, il dit s il est ROTATIF -- c est-a-dire s il
    peut etre tronque periodiquement sans rien perdre d irremplacable.
    Un cache se reconstruit. Un journal ancien ne sert plus. Un ticket
    de trade, jamais : il ne sera pas propose a la troncature.
"""
import argparse
import os
import shutil
import stat as statmod
import sys
import time

REPARSE = getattr(statmod, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
UTIL = os.path.expanduser("~")

# (chemin, libelle, rotatif). rotatif = tronquable sans perte definitive.
SUSPECTS = [
    (os.path.join(UTIL, "AppData", "Local", "Google", "DriveFS"),
     "cache Google Drive", True),
    (os.path.join(UTIL, "AppData", "Roaming", "MetaQuotes"),
     "MT5 : historique et journaux", True),
    (os.path.join(UTIL, "AppData", "Local", "Temp"),
     "Temp utilisateur", True),
    (os.path.join("C:\\", "Windows", "Temp"),
     "Temp Windows", True),
    (os.path.join(UTIL, "AppData", "Local", "Google", "Chrome",
                  "User Data", "Default", "Cache"),
     "cache Chrome", True),
    (os.path.join(UTIL, "Downloads", "Scalp-EA-main", "Scalp-EA-main",
                  "logs"),
     "stack : journaux", True),
    (os.path.join(UTIL, "Downloads", "Scalp-EA-main", "Scalp-EA-main",
                  "docs"),
     "stack : donnees -- NE PAS tronquer a l aveugle", False),
    (os.path.join(UTIL, "Downloads", "Scalp-EA-main", "Scalp-EA-main",
                  "cartes"),
     "stack : panneaux HTML", True),
]


def humain(o):
    for unite, seuil in (("To", 1024 ** 4), ("Go", 1024 ** 3),
                         ("Mo", 1024 ** 2), ("ko", 1024)):
        if o >= seuil:
            return "%.1f %s" % (o / float(seuil), unite)
    return "%d o" % o


def est_reparse(chemin):
    try:
        if os.path.islink(chemin):
            return True
        st = os.stat(chemin, follow_symlinks=False)
        return bool(getattr(st, "st_file_attributes", 0) & REPARSE)
    except OSError:
        return False


def pese(chemin, jours, gros, dire=None):
    """(total, recents, n, n_recents). Recents = ecrits depuis N jours."""
    limite = time.time() - jours * 86400
    total = recents = n = nr = 0
    dernier = time.time()
    for dossier, sous, fichiers in os.walk(chemin, onerror=lambda e: None):
        sous[:] = [d for d in sous
                   if not est_reparse(os.path.join(dossier, d))]
        for f in fichiers:
            c = os.path.join(dossier, f)
            try:
                st = os.stat(c)
            except OSError:
                continue
            total += st.st_size
            n += 1
            if st.st_mtime >= limite:
                recents += st.st_size
                nr += 1
            if st.st_size > 100 * 1024 * 1024:
                gros.append((st.st_size, st.st_mtime, c))
            # Le battement se declenche AUSSI dans la boucle de
            # fichiers : un dossier unique de 300 000 fichiers ne rend
            # la main qu une fois, et le script paraitrait mort.
            if dire and (n % 5000 == 0) and time.time() - dernier > 5:
                dire("      ... %d fichiers, %s" % (n, humain(total)))
                dernier = time.time()
    return total, recents, n, nr


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--jours", type=int, default=7)
    p.add_argument("--racine", action="append", default=None,
                   help="ajouter un endroit a examiner")
    a = p.parse_args()

    def dis(x):
        print(x)
        sys.stdout.flush()

    dis("=" * 94)
    dis("QU EST-CE QUI REMPLIT LE DISQUE")
    dis("=" * 94)
    dis("")
    dis("  Lecteur seul. Rien n est efface, rien n est deplace.")
    dis("  Fenetre 'recent' : %d jours." % a.jours)
    dis("")

    dis("-" * 94)
    dis("ESPACE LIBRE PAR VOLUME")
    dis("-" * 94)
    for lettre in "CDEFG":
        v = lettre + ":\\"
        if not os.path.isdir(v):
            continue
        try:
            u = shutil.disk_usage(v)
        except OSError as e:
            dis("  %-4s illisible : %s" % (v, e))
            continue
        pc = 100.0 * u.free / u.total if u.total else 0
        dis("  %-4s total %10s   utilise %10s   LIBRE %10s  (%.1f %%)"
            % (v, humain(u.total), humain(u.used), humain(u.free), pc))
    dis("")

    endroits = list(SUSPECTS)
    for r in (a.racine or []):
        endroits.append((r, "ajoute en ligne de commande", False))

    gros = []
    dis("-" * 94)
    dis("LES ENDROITS QUI GROSSISSENT")
    dis("-" * 94)
    dis("  %-38s %10s %10s %8s  %s"
        % ("endroit", "taille", "ecrit<%dj" % a.jours, "fichiers", "rotatif"))
    dis("  " + "-" * 90)
    lignes = []
    for chemin, libelle, rotatif in endroits:
        if not os.path.isdir(chemin):
            dis("  %-38s %10s   absent" % (libelle[:38], "-"))
            continue
        t, rec, n, nr = pese(chemin, a.jours, gros, dire=dis)
        lignes.append((t, rec, n, nr, libelle, rotatif, chemin))
        dis("  %-38s %10s %10s %8d  %s"
            % (libelle[:38], humain(t), humain(rec), n,
               "oui" if rotatif else "NON -- donnees"))
    dis("")

    dis("-" * 94)
    dis("CE QU ON POURRAIT RECUPERER, ET CE QU ON NE DOIT PAS TOUCHER")
    dis("-" * 94)
    recup = sum(t for t, _r, _n, _nr, _l, rot, _c in lignes if rot)
    garde = sum(t for t, _r, _n, _nr, _l, rot, _c in lignes if not rot)
    dis("  rotatif, tronquable      %10s" % humain(recup))
    dis("  donnees, a conserver     %10s" % humain(garde))
    dis("")
    for t, rec, n, nr, libelle, rotatif, chemin in sorted(lignes,
                                                          reverse=True):
        if not rotatif or t < 100 * 1024 * 1024:
            continue
        part = (100.0 * rec / t) if t else 0
        dis("  %-38s %10s dont %s ecrit(s) en %d j (%.0f %%)"
            % (libelle[:38], humain(t), humain(rec), a.jours, part))
        dis("      %s" % chemin)
    dis("")
    dis("  Une part elevee = le dossier se REECRIT. Le tronquer libere")
    dis("  de la place qui reviendra : c est un candidat a la rotation")
    dis("  periodique, pas a un menage manuel de plus.")
    dis("")

    dis("-" * 94)
    dis("LES FICHIERS DE PLUS DE 100 Mo")
    dis("-" * 94)
    gros.sort(reverse=True)
    if not gros:
        dis("  Aucun.")
    for o, mt, c in gros[:20]:
        dis("  %10s  %s  %s"
            % (humain(o), time.strftime("%Y-%m-%d", time.localtime(mt)),
               c[-64:]))
    dis("")
    dis("=" * 94)
    dis("  Ce script n a rien efface, rien deplace, rien ecrit.")
    dis("=" * 94)
    return 0


if __name__ == "__main__":
    sys.exit(main())
