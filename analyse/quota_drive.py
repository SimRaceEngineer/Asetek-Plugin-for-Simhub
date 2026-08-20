# -*- coding: utf-8 -*-
"""
quota_drive.py -- ou passent les 199 Go du quota Google ?

Lecture seule stricte. Ce script :
  - localise la base de configuration de Google Drive for desktop,
  - la COPIE avant de l ouvrir (jamais l originale, elle est verrouillee),
  - liste les racines de synchronisation : quels dossiers LOCAUX
    sont sauvegardes vers le cloud (section "Ordinateurs" de Drive,
    qui consomme le quota sans apparaitre dans My Drive),
  - mesure le cache local de Drive, gros consommateur de C:.

Il n ecrit rien ailleurs que dans un fichier temporaire qu il efface.

Options :
  --tailles      mesure la taille de chaque racine locale (long)
  --base CHEMIN  force le chemin d une base sqlite
"""

import os
import sys
import shutil
import sqlite3
import tempfile

SEP = "=" * 92

# colonnes dont la valeur ne doit jamais etre imprimee en clair :
# la sortie de ce script est collee dans une conversation.
SENSIBLE = ("token", "secret", "password", "passwd", "credential",
            "auth", "cookie", "key")


def masque(nom_colonne, valeur):
    n = (nom_colonne or "").lower()
    if any(m in n for m in SENSIBLE):
        if valeur is None:
            return "(vide)"
        return "[masque, %d caracteres]" % len(str(valeur))
    return valeur


def humain(n):
    for unite, seuil in (("To", 1024 ** 4), ("Go", 1024 ** 3),
                         ("Mo", 1024 ** 2), ("ko", 1024)):
        if n >= seuil:
            return "%.1f %s" % (n / float(seuil), unite)
    return "%d o" % n


def racine_drivefs():
    """Le dossier %LOCALAPPDATA%\\Google\\DriveFS, ou None."""
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    d = os.path.join(local, "Google", "DriveFS")
    return d if os.path.isdir(d) else None


def bases(dossier):
    """Toutes les root_preference_sqlite.db trouvees sous DriveFS."""
    trouvees = []
    for courant, sous, fichiers in os.walk(dossier):
        for f in fichiers:
            if f.startswith("root_preference") and f.endswith(".db"):
                trouvees.append(os.path.join(courant, f))
        # ne pas descendre dans le cache : des millions de fichiers
        sous[:] = [s for s in sous if s not in ("content_cache", "Logs")]
    return trouvees


def lit_base(chemin):
    """Copie puis introspecte. Retourne (tables, lignes_par_table)."""
    tmp = tempfile.mkdtemp(prefix="qd_")
    copie = os.path.join(tmp, "copie.db")
    try:
        shutil.copy2(chemin, copie)
        for extra in ("-wal", "-shm"):
            if os.path.exists(chemin + extra):
                shutil.copy2(chemin + extra, copie + extra)
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return None, "copie impossible : %s" % e

    try:
        cx = sqlite3.connect(copie)
        cur = cx.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        dump = {}
        for t in tables:
            try:
                cur.execute("PRAGMA table_info(%s)" % t)
                cols = [r[1] for r in cur.fetchall()]
                cur.execute("SELECT COUNT(*) FROM %s" % t)
                n = cur.fetchone()[0]
                lignes = []
                if n <= 200:
                    cur.execute("SELECT * FROM %s" % t)
                    lignes = cur.fetchall()
                dump[t] = (cols, n, lignes)
            except Exception as e:
                dump[t] = ([], -1, [("erreur", str(e))])
        cx.close()
        return dump, None
    except Exception as e:
        return None, "lecture impossible : %s" % e
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ressemble_a_un_chemin(v):
    if not isinstance(v, str) or len(v) < 4:
        return False
    return (v[1:3] == ":\\") or v.startswith("\\\\")


def taille_dossier(chemin):
    """Somme des tailles, sortie en continu, sans suivre les jonctions."""
    total = 0
    nb = 0
    dernier = 0
    for courant, sous, fichiers in os.walk(chemin):
        # ne jamais suivre un point de reanalyse : boucles infinies
        gardes = []
        for s in sous:
            p = os.path.join(courant, s)
            try:
                if os.path.islink(p):
                    continue
                if os.stat(p).st_file_attributes & 0x400:  # REPARSE_POINT
                    continue
            except Exception:
                pass
            gardes.append(s)
        sous[:] = gardes
        for f in fichiers:
            try:
                total += os.path.getsize(os.path.join(courant, f))
                nb += 1
            except Exception:
                pass
        if nb - dernier >= 20000:
            dernier = nb
            sys.stdout.write("      ... %d fichiers, %s\n" % (nb, humain(total)))
            sys.stdout.flush()
    return total, nb


def main():
    args = sys.argv[1:]
    veut_tailles = "--tailles" in args
    force = None
    if "--base" in args:
        i = args.index("--base")
        if i + 1 < len(args):
            force = args[i + 1]

    print(SEP)
    print("OU PASSE LE QUOTA GOOGLE")
    print(SEP)
    print()
    print("  Lecture seule. La base est copiee avant d etre ouverte.")
    print("  Rien n est ecrit, rien n est efface, rien n est envoye.")
    print()

    dossier = racine_drivefs()
    if not dossier:
        print("  Google Drive for desktop introuvable")
        print("  (%LOCALAPPDATA%\\Google\\DriveFS n existe pas).")
        print("  Alors le quota n est pas consomme par une sauvegarde")
        print("  de dossiers locaux depuis CETTE machine.")
        print()
        print(SEP)
        return

    print("  DriveFS : %s" % dossier)
    print()

    # --- le cache local, consommateur de C: -------------------------------
    print(SEP)
    print("CACHE LOCAL DE DRIVE (consomme C:, pas le quota)")
    print(SEP)
    caches = []
    for courant, sous, _f in os.walk(dossier):
        for s in sous:
            if s == "content_cache":
                caches.append(os.path.join(courant, s))
        if courant.count(os.sep) - dossier.count(os.sep) > 2:
            sous[:] = []
    if not caches:
        print("  aucun content_cache trouve")
    for c in caches:
        t, n = taille_dossier(c)
        print("  %-60s %10s  %8d fichiers" % (c[-60:], humain(t), n))
        print()
        print("  Ce cache se vide depuis Drive : Preferences > (roue)")
        print("  > Parametres > 'Vider le cache local'. Il se reconstruit.")
    print()

    # --- les racines de synchronisation -----------------------------------
    print(SEP)
    print("RACINES DE SYNCHRONISATION")
    print(SEP)

    chemins = force and [force] or bases(dossier)
    if not chemins:
        print("  aucune base root_preference trouvee.")
        print()
        print(SEP)
        return

    locaux = []
    for b in chemins:
        print()
        print("  base : %s" % b)
        dump, err = lit_base(b)
        if err:
            print("    %s" % err)
            continue
        for t in sorted(dump):
            cols, n, lignes = dump[t]
            print("    table %-24s %4d ligne(s)" % (t, n))
            if not lignes:
                continue
            for ligne in lignes:
                paires = []
                for i, v in enumerate(ligne):
                    nom = cols[i] if i < len(cols) else "col%d" % i
                    v = masque(nom, v)
                    if v in (None, "", 0):
                        continue
                    paires.append("%s=%s" % (nom, v))
                    if ressemble_a_un_chemin(v) and os.path.isdir(v):
                        if v not in locaux:
                            locaux.append(v)
                if paires:
                    print("        " + " | ".join(str(p) for p in paires))

    print()
    print(SEP)
    print("DOSSIERS LOCAUX SAUVEGARDES VERS LE CLOUD")
    print(SEP)
    if not locaux:
        print()
        print("  Aucun chemin local existant dans la configuration.")
        print("  Cette machine ne pousse donc pas de dossier local vers")
        print("  Drive. Les 173 Go manquants sont ailleurs : corbeille,")
        print("  Google Photos, Gmail, ou une autre machine.")
    else:
        print()
        for p in locaux:
            print("  %s" % p)
        if not veut_tailles:
            print()
            print("  Relance avec --tailles pour les mesurer.")
        else:
            print()
            total = 0
            for p in locaux:
                print("  mesure : %s" % p)
                t, n = taille_dossier(p)
                total += t
                print("     -> %10s  %8d fichiers" % (humain(t), n))
            print()
            print("  TOTAL POUSSE VERS LE CLOUD : %s" % humain(total))
            print()
            print("  A comparer aux 22.2 Go de My Drive et aux ~195 Go")
            print("  de quota consomme. Si ce total comble l ecart, la")
            print("  cause est trouvee : ce sont des dossiers locaux")
            print("  qui remontent, et le menage sur C: les fait")
            print("  redescendre -- mais seulement apres la corbeille.")

    print()
    print(SEP)
    print("  Ce script n a rien copie, rien efface, rien envoye.")
    print(SEP)


if __name__ == "__main__":
    main()
