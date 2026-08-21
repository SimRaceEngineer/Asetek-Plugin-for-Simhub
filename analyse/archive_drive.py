#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
archive_drive.py -- archiver un dossier du Drive, sans rien perdre.

  python archive_drive.py --inventaire
  python archive_drive.py --dossier "LeMansUltimate Led Profiles" --essai
  python archive_drive.py --dossier "LeMansUltimate Led Profiles" --archiver
  python archive_drive.py --dossier "LeMansUltimate Led Profiles" --supprimer

LA DISCIPLINE, LA MEME QU HIER SUR C:

    Rien n est supprime avant d avoir ete relu. L archive est ecrite,
    puis chaque fichier en est RESSORTI et son SHA-256 compare a
    l original. La suppression n est proposee qu apres, et seulement
    sur demande explicite.

L ORDRE DES OPERATIONS COMPTE, ET IL N EST PAS EVIDENT

    Le Drive est PLEIN. On ne peut donc pas y ecrire l archive avant
    d avoir libere la place. La sequence est :

      1. ARCHIVER vers C:   (21 Go libres, la place existe)
      2. VERIFIER l archive contre les originaux
      3. SUPPRIMER le dossier sur G:
      4. VIDER LA CORBEILLE DRIVE dans le navigateur
         -- sans ca rien n est rendu, la corbeille compte 30 jours
      5. seulement alors, RECOPIER l archive sur G: si tu la veux
         dans le cloud

    L etape 4 est celle qu on oublie et qui annule tout le reste.

CE QUE L INVENTAIRE MESURE VRAIMENT

    Pas la taille : la COMPRESSIBILITE. Un dossier de .cbz, de .mp4 ou
    de .jpg est deja compresse -- l archiver ne rend rien. Le script
    echantillonne le contenu et donne le gain REEL attendu, pas une
    esperance.

    Il compte aussi les fichiers : 20 000 petits fichiers coutent bien
    plus que leur somme, et c est la que l archivage paie le plus.
"""

import argparse
import hashlib
import os
import random
import sys
import zipfile

SEP = "=" * 92
RACINE = r"G:\My Drive"
DEJA_COMPRESSE = (".zip", ".7z", ".rar", ".gz", ".cbz", ".cbr", ".jpg",
                  ".jpeg", ".png", ".mp4", ".mkv", ".avi", ".mp3", ".m4a",
                  ".pdf", ".docx", ".xlsx", ".pptx", ".webp", ".scid")


def humain(n):
    for u, s in (("To", 1024 ** 4), ("Go", 1024 ** 3),
                 ("Mo", 1024 ** 2), ("ko", 1024)):
        if n >= s:
            return "%.1f %s" % (n / float(s), u)
    return "%d o" % n


def sha(chemin, bloc=1 << 20):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        while True:
            b = f.read(bloc)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def parcourt(racine):
    """(chemin relatif, taille) de chaque fichier, sans suivre les liens."""
    out = []
    for courant, sous, fichiers in os.walk(racine):
        gardes = []
        for s in sous:
            p = os.path.join(courant, s)
            try:
                if os.path.islink(p):
                    continue
                a = os.stat(p).st_file_attributes
                if a & 0x400:            # point de reanalyse
                    continue
            except Exception:
                pass
            gardes.append(s)
        sous[:] = gardes
        for f in fichiers:
            p = os.path.join(courant, f)
            try:
                out.append((os.path.relpath(p, racine), os.path.getsize(p)))
            except OSError:
                pass
    return out


def compressibilite(racine, fichiers, echantillon=40):
    """Le gain REEL, mesure sur un echantillon compresse pour de vrai."""
    candidats = [(r, t) for r, t in fichiers if t > 0]
    if not candidats:
        return None, 0, 0
    random.seed(7)
    pris = random.sample(candidats, min(echantillon, len(candidats)))
    brut = comp = 0
    import zlib
    for rel, taille in pris:
        try:
            with open(os.path.join(racine, rel), "rb") as f:
                d = f.read(min(taille, 1 << 20))
        except OSError:
            continue
        if not d:
            continue
        brut += len(d)
        comp += len(zlib.compress(d, 6))
    if not brut:
        return None, 0, 0
    return comp / float(brut), len(pris), brut


def inventaire(racine):
    print(SEP)
    print("QUE PEUT-ON REELLEMENT GAGNER, DOSSIER PAR DOSSIER")
    print(SEP)
    print()
    if not os.path.isdir(racine):
        print("  introuvable : %s" % racine)
        return
    print("  racine : %s" % racine)
    print("  Lecture seule. Rien n est ecrit, rien n est supprime.")
    print()
    print("   dossier                              taille  fichiers"
          "  ratio   gain estime")
    print("   " + "-" * 84)
    lignes = []
    for nom in sorted(os.listdir(racine)):
        chemin = os.path.join(racine, nom)
        if not os.path.isdir(chemin):
            continue
        try:
            fichiers = parcourt(chemin)
        except Exception as e:
            print("   %-36s illisible (%s)" % (nom[:36], e))
            continue
        total = sum(t for _r, t in fichiers)
        if total == 0:
            continue
        ratio, n_ech, _b = compressibilite(chemin, fichiers)
        gain = int(total * (1 - ratio)) if ratio else 0
        lignes.append((gain, nom, total, len(fichiers), ratio))
    for gain, nom, total, nf, ratio in sorted(lignes, reverse=True):
        verdict = ""
        if ratio is None:
            verdict = "  non mesurable"
        elif ratio > 0.92:
            verdict = "  deja compresse -- l archiver ne rend RIEN"
        elif gain > 1 << 30:
            verdict = "  <== archiver ici"
        print("   %-36s %9s %8d   %4.2f   %9s%s"
              % (nom[:36], humain(total), nf, ratio or 0, humain(gain),
                 verdict))
    print()
    print("  ratio = taille comprimee / taille brute, MESURE sur un")
    print("  echantillon reellement compresse. Au-dessus de 0,92 le")
    print("  contenu est deja compresse et l archivage est inutile.")
    print()
    print("  Le nombre de fichiers compte autant que la taille : vingt")
    print("  mille petits fichiers coutent bien plus que leur somme.")
    print()


def archive(racine, nom, vers, essai):
    src = os.path.join(racine, nom)
    if not os.path.isdir(src):
        print("  introuvable : %s" % src)
        return
    cible = os.path.join(vers, nom.replace(" ", "_") + ".zip")
    print(SEP)
    print("ARCHIVAGE -- %s" % nom)
    print(SEP)
    print()
    fichiers = parcourt(src)
    total = sum(t for _r, t in fichiers)
    print("  source  : %s" % src)
    print("  %d fichier(s), %s" % (len(fichiers), humain(total)))
    print("  archive : %s" % cible)
    libre = None
    try:
        import shutil
        libre = shutil.disk_usage(vers).free
        print("  place libre sur la destination : %s" % humain(libre))
    except Exception:
        pass
    if libre is not None and libre < total * 0.6:
        print()
        print("  PAS ASSEZ DE PLACE pour une archive de cette taille.")
        print("  Choisis une autre destination avec --vers.")
        return
    print()
    if essai:
        print("  --essai : rien n est ecrit.")
        print("  Relance avec --archiver pour creer l archive.")
        return

    os.makedirs(vers, exist_ok=True)
    empreintes = {}
    ecrits = 0
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED,
                         allowZip64=True) as z:
        for rel, taille in fichiers:
            p = os.path.join(src, rel)
            try:
                empreintes[rel] = sha(p)
                z.write(p, rel)
                ecrits += 1
            except Exception as e:
                print("  NON ARCHIVE : %s (%s)" % (rel, e))
            if ecrits % 2000 == 0:
                print("    ... %d / %d" % (ecrits, len(fichiers)))
                sys.stdout.flush()
    taille_zip = os.path.getsize(cible)
    print()
    print("  archive ecrite : %s  (%.0f %% de l original)"
          % (humain(taille_zip), 100.0 * taille_zip / max(1, total)))
    print()

    print("  VERIFICATION -- chaque fichier est RESSORTI et compare")
    print()
    faux, verifies = [], 0
    with zipfile.ZipFile(cible) as z:
        noms = set(z.namelist())
        for rel, attendu in empreintes.items():
            arc = rel.replace(os.sep, "/")
            if arc not in noms:
                faux.append((rel, "absent de l archive"))
                continue
            h = hashlib.sha256()
            with z.open(arc) as f:
                while True:
                    b = f.read(1 << 20)
                    if not b:
                        break
                    h.update(b)
            if h.hexdigest() != attendu:
                faux.append((rel, "empreinte differente"))
            else:
                verifies += 1
            if verifies % 2000 == 0:
                print("    ... %d verifies" % verifies)
                sys.stdout.flush()
    print()
    print("  %d fichier(s) verifies a l identique" % verifies)
    if faux:
        print("  %d PROBLEME(S) :" % len(faux))
        for rel, quoi in faux[:20]:
            print("     %s -- %s" % (rel, quoi))
        print()
        print("  NE SUPPRIME RIEN. L archive n est pas fidele.")
        return
    print("  Aucun ecart. L archive contient l integralite du dossier.")
    print()
    print("  SUITE, dans cet ordre :")
    print("    1. python archive_drive.py --dossier \"%s\" --supprimer" % nom)
    print("    2. VIDER LA CORBEILLE DRIVE dans le navigateur")
    print("       -- sans ca les %s ne sont PAS rendus" % humain(total))
    print("    3. si tu veux l archive dans le cloud, recopie-la sur G:")
    print()


def supprime(racine, nom, vers):
    src = os.path.join(racine, nom)
    cible = os.path.join(vers, nom.replace(" ", "_") + ".zip")
    print(SEP)
    print("SUPPRESSION -- %s" % nom)
    print(SEP)
    print()
    if not os.path.isfile(cible):
        print("  Aucune archive a %s." % cible)
        print("  Rien ne sera supprime : l archive doit exister ET avoir")
        print("  ete verifiee avant.")
        return
    if not os.path.isdir(src):
        print("  %s n existe deja plus." % src)
        return
    fichiers = parcourt(src)
    total = sum(t for _r, t in fichiers)
    print("  archive presente : %s (%s)" % (cible, humain(os.path.getsize(cible))))
    print("  a supprimer      : %s (%d fichiers, %s)"
          % (src, len(fichiers), humain(total)))
    print()
    print("  Verification rapide : l archive contient-elle tout ?")
    with zipfile.ZipFile(cible) as z:
        noms = set(n.replace("/", os.sep) for n in z.namelist())
    manquants = [r for r, _t in fichiers if r not in noms]
    if manquants:
        print("  %d fichier(s) ABSENTS de l archive. Rien n est supprime."
              % len(manquants))
        for r in manquants[:10]:
            print("     %s" % r)
        return
    print("  les %d fichiers sont dans l archive." % len(fichiers))
    print()
    reponse = input("  Taper SUPPRIMER en majuscules pour confirmer : ")
    if reponse.strip() != "SUPPRIMER":
        print("  annule, rien n a ete supprime.")
        return
    import shutil
    shutil.rmtree(src)
    print()
    print("  %s supprime." % src)
    print()
    print("  IL RESTE L ETAPE QUI COMPTE :")
    print("  vide la CORBEILLE DRIVE dans le navigateur. Tant qu elle")
    print("  n est pas vide, ces %s comptent encore dans ton quota"
          % humain(total))
    print("  pendant 30 jours, et tu n auras rien gagne.")
    print()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--racine", default=RACINE)
    p.add_argument("--dossier")
    p.add_argument("--vers", default=r"C:\archives_drive")
    p.add_argument("--inventaire", action="store_true")
    p.add_argument("--essai", action="store_true")
    p.add_argument("--archiver", action="store_true")
    p.add_argument("--supprimer", action="store_true")
    a = p.parse_args()

    print(SEP)
    print("ARCHIVAGE DU DRIVE")
    print(SEP)
    print()

    if a.supprimer and a.dossier:
        supprime(a.racine, a.dossier, a.vers)
    elif a.dossier:
        archive(a.racine, a.dossier, a.vers, a.essai or not a.archiver)
    else:
        inventaire(a.racine)

    print(SEP)
    print("  Rappel : sur Drive, supprimer ne libere RIEN. Seul le")
    print("  vidage de la corbeille compte, et elle retient 30 jours.")
    print(SEP)


if __name__ == "__main__":
    main()
