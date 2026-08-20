# -*- coding: utf-8 -*-
r"""
rotation_docs.py -- comprimer ce qui dort, ne supprimer que ce qui est deja reduit

  python rotation_docs.py                    rapport seul, rien n est touche
                                             (trouve la racine tout seul)
  python rotation_docs.py --comprimer        gzip les journees mures, verifie
  python rotation_docs.py --supprimer --oui  efface le brut DEJA reduit et gzip

PAR DEFAUT CE SCRIPT NE TOUCHE A RIEN. Il faut un drapeau explicite
pour comprimer, et deux pour supprimer.

LA REGLE, ET D OU ELLE VIENT

    Elle n est pas de moi. extraire_cycles.py porte en tete : "34 Go de
    cycles ramenes a quelques Mo". Il lit docs\buddha\<jour>\cycles.jsonl
    et ecrit cartes\cycles\cycles_<jour>.csv. extraire_snapshots.py fait
    de meme vers cartes\snapshots\snap_<jour>.csv.

    Donc la condition de SUPPRESSION n est pas l age, c est la
    REDUCTION :

        un jour brut ne peut disparaitre que si son extraction existe.

    Elle ne conditionne QUE la suppression. La premiere version liait
    aussi la compression a la reduction, et gelait ainsi deux Go de
    snapshots en clair pour rien : comprimer ne detruit pas, et se
    defait.

    La compression a sa propre condition, et elle est ailleurs :

        on ne comprime que si le LECTEUR sait ouvrir un .gz.

    extraire_cycles essaie cycles.jsonl puis cycles.jsonl.gz : sans
    danger. extraire_snapshots et audit_cadence cherchent le nom exact
    "snapshots.csv" : les gzipper ne provoquerait aucune erreur, ils
    trouveraient zero journee et rendraient un rapport vide. C est le
    piege que le propre en-tete d extraire_cycles decrit -- "un
    chercheur de fichiers qui ignore silencieusement la majorite de ses
    candidats rend un resultat plausible".

CE QUE LA MESURE DU 20/08 A MONTRE

    docs = 11,2 Go dont 4,8 Go ecrits en 7 jours, soit ~690 Mo par
    jour. A ce rythme, vingt Go liberes reviennent en un mois.

    Les cycles anciens sont deja en .gz -- quelqu un les comprime. Mais
    docs\lifecycle\<jour>\lifecycle.csv ne l est PAS : 309, 291, 284,
    268 Mo par journee, en clair. Un CSV se comprime tres bien, et
    aucun module Python du depot ne lit lifecycle. C est le gisement le
    plus simple, et il ne demande aucune suppression.

CE QUE LA COMPRESSION GARANTIT

    Ecrire le .gz, le RELIRE, comparer l empreinte SHA-256 du flux
    decompresse a celle de l original, et seulement alors effacer
    l original. Si quoi que ce soit cloche, le .gz partiel est retire
    et le fichier d origine reste intact.

    Rien n est touche pour la journee EN COURS ni pour un fichier
    modifie dans l heure : la stack est peut-etre en train d y ecrire.
"""
import argparse
import gzip
import hashlib
import os
import shutil
import sys
import time

RACINE = "docs"
CARTES = "cartes"

# (dossier, motif, dossier reduit, prefixe reduit, gz_ok, consommateurs)
#
# gz_ok = les modules qui lisent ce fichier savent-ils ouvrir un .gz ?
# La question n est pas theorique : gzipper un fichier que son lecteur
# cherche par son nom exact ne provoque aucune erreur. Le lecteur
# trouve zero journee et rend un rapport vide -- plausible, et faux.
FLUX = [
    # extraire_cycles.source() essaie cycles.jsonl PUIS cycles.jsonl.gz,
    # et ouvre() gere gzip. Compression sans danger.
    (os.path.join(RACINE, "buddha"), "cycles.jsonl",
     os.path.join(CARTES, "cycles"), "cycles_", True,
     "extraire_cycles"),
    # extraire_snapshots.journees() et audit_cadence cherchent le nom
    # EXACT "snapshots.csv". Les comprimer les rendrait aveugles.
    (os.path.join(RACINE, "buddha"), "snapshots.csv",
     os.path.join(CARTES, "snapshots"), "snap_", False,
     "extraire_snapshots, audit_cadence"),
    # Aucun module Python du depot ne lit lifecycle.
    (os.path.join(RACINE, "lifecycle"), "lifecycle.csv",
     None, None, True, "aucun"),
]

FRAICHE = 3600          # une heure : en dessous, la stack ecrit peut-etre

# Ou chercher la racine du stack, dans l ordre. Un script qui depend du
# repertoire courant echoue le jour ou on le lance d ailleurs -- ou
# depuis une tache planifiee, qui demarre ou elle veut.
CANDIDATES = [
    os.getcwd(),
    os.path.dirname(os.path.abspath(__file__)) or ".",
    os.path.join(os.path.expanduser("~"), "Downloads",
                 "Scalp-EA-main", "Scalp-EA-main"),
]


def trouve_racine(dis):
    r"""Le premier endroit qui porte docs\buddha ou docs\lifecycle."""
    vus = []
    for c in CANDIDATES:
        if c in vus:
            continue
        vus.append(c)
        for sonde in (os.path.join("docs", "buddha"),
                      os.path.join("docs", "lifecycle")):
            if os.path.isdir(os.path.join(c, sonde)):
                return c
    dis("  Racine du stack introuvable. Cherche dans :")
    for c in vus:
        dis("    %s" % c)
    dis("  Relance depuis le dossier du stack, ou dis-le-moi.")
    return None


def humain(o):
    for u, s in (("Go", 1024 ** 3), ("Mo", 1024 ** 2), ("ko", 1024)):
        if o >= s:
            return "%.1f %s" % (o / float(s), u)
    return "%d o" % o


def sha_flux(ouvre):
    h = hashlib.sha256()
    with ouvre() as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def comprime(chemin, dis):
    """Ecrit .gz, VERIFIE, puis efface l original. Rend les octets gagnes.

    La verification n est pas une precaution de style : un gzip
    tronque par un disque plein produit un fichier qui s ouvre et se
    lit jusqu au trou. Sans relecture complete, on effacerait
    l original en croyant l avoir sauve."""
    gz = chemin + ".gz"
    if os.path.exists(gz):
        dis("      %s existe deja, on ne touche pas." % os.path.basename(gz))
        return 0
    avant = os.path.getsize(chemin)
    try:
        with open(chemin, "rb") as src, gzip.open(gz, "wb", 6) as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)
    except (OSError, EOFError) as e:
        dis("      ECHEC ecriture : %s" % e)
        if os.path.exists(gz):
            os.remove(gz)
        return 0
    try:
        a = sha_flux(lambda: open(chemin, "rb"))
        b = sha_flux(lambda: gzip.open(gz, "rb"))
    except (OSError, EOFError) as e:
        dis("      ECHEC relecture : %s -- original conserve." % e)
        if os.path.exists(gz):
            os.remove(gz)
        return 0
    if a != b:
        dis("      EMPREINTES DIFFERENTES -- original conserve, .gz retire.")
        os.remove(gz)
        return 0
    apres = os.path.getsize(gz)
    os.remove(chemin)
    dis("      comprime et verifie : %s -> %s" % (humain(avant),
                                                  humain(apres)))
    return avant - apres


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--comprimer", action="store_true")
    p.add_argument("--supprimer", action="store_true")
    p.add_argument("--oui", action="store_true",
                   help="confirme --supprimer")
    p.add_argument("--garde-clair", type=int, default=2, dest="clair",
                   help="journees laissees en clair (defaut 2)")
    p.add_argument("--garde", type=int, default=60,
                   help="journees avant qu un brut REDUIT soit effacable")
    a = p.parse_args()

    def dis(x):
        print(x)
        sys.stdout.flush()

    dis("=" * 94)
    dis("ROTATION DES DONNEES QUOTIDIENNES")
    dis("=" * 94)
    dis("")
    if a.supprimer and not a.oui:
        dis("  --supprimer sans --oui : je n efface rien.")
        dis("  Relance avec les deux si c est bien voulu.")
        dis("")
        a.supprimer = False
    mode = ("SUPPRESSION" if a.supprimer
            else ("COMPRESSION" if a.comprimer else "RAPPORT SEUL"))
    dis("  mode : %s" % mode)
    dis("  %d journee(s) laissee(s) en clair, suppression au-dela de %d j."
        % (a.clair, a.garde))
    dis("")

    racine = trouve_racine(dis)
    if racine is None:
        return 1
    if os.path.abspath(racine) != os.path.abspath(os.getcwd()):
        dis("  racine trouvee : %s" % racine)
        os.chdir(racine)
    dis("")

    aujourd = time.strftime("%Y-%m-%d")
    gagne = 0
    bloques = []
    for dossier, motif, red_dir, red_pre, gz_ok, lecteurs in FLUX:
        dis("-" * 94)
        dis("%s   (%s)" % (dossier, motif))
        dis("   lu par : %s%s" % (lecteurs,
                                  "" if gz_ok else "  -- NE LIT PAS le .gz"))
        dis("-" * 94)
        if not os.path.isdir(dossier):
            dis("  absent.")
            dis("")
            continue
        jours = sorted(d for d in os.listdir(dossier)
                       if os.path.isdir(os.path.join(dossier, d)))
        if not jours:
            dis("  aucune journee.")
            dis("")
            continue
        dis("  %-12s %10s %6s %-12s %s"
            % ("jour", "taille", "age", "reduit", "etat"))
        dis("  " + "-" * 88)
        rangs = {}
        for i, j in enumerate(reversed(jours)):
            rangs[j] = i          # 0 = la plus recente
        bloc_o = bloc_n = 0
        for j in jours:
            clair = os.path.join(dossier, j, motif)
            gzp = clair + ".gz"
            ici = clair if os.path.isfile(clair) else (
                gzp if os.path.isfile(gzp) else None)
            if ici is None:
                continue
            taille = os.path.getsize(ici)
            rang = rangs[j]
            reduit = "-"
            a_reduit = True
            if red_dir:
                rc = os.path.join(red_dir, "%s%s.csv" % (red_pre, j))
                a_reduit = os.path.isfile(rc)
                reduit = "oui" if a_reduit else "NON"
            frais = (time.time() - os.path.getmtime(ici)) < FRAICHE
            # L ordre des tests EST la politique. La reduction ne
            # conditionne QUE la suppression : comprimer ne detruit
            # rien et reste reversible. Les lier, comme le faisait la
            # premiere version, gelait 2 Go de snapshots en clair.
            if j == aujourd or frais:
                etat = "en cours -- intouchable"
            elif ici.endswith(".gz"):
                if not a_reduit:
                    etat = "comprime, non reduit -- garde"
                else:
                    etat = ("effacable (reduit, %d j)" % rang
                            if rang >= a.garde else "comprime, garde")
            elif rang < a.clair:
                etat = "en clair, recent -- garde"
            elif not gz_ok:
                etat = "EN CLAIR -- son lecteur ignore le .gz"
            else:
                etat = "A COMPRIMER"
            dis("  %-12s %10s %6d %-12s %s"
                % (j, humain(taille), rang, reduit, etat))

            if a.comprimer and etat == "A COMPRIMER":
                gagne += comprime(ici, dis)
            if a.supprimer and etat.startswith("effacable"):
                try:
                    o = os.path.getsize(ici)
                    os.remove(ici)
                    gagne += o
                    dis("      efface : %s (extraction conservee)" % humain(o))
                except OSError as e:
                    dis("      echec suppression : %s" % e)
            if etat.startswith("EN CLAIR"):
                bloc_o += taille
                bloc_n += 1
        if bloc_n:
            bloques.append((motif, lecteurs, bloc_o, bloc_n))
        dis("")

    dis("=" * 94)
    if bloques:
        dis("BLOQUE PAR LE LECTEUR, ET NON PAR LA PRUDENCE")
        dis("=" * 94)
        for motif, lecteurs, o, n in bloques:
            dis("  %-16s %10s en clair sur %d journee(s)"
                % (motif, humain(o), n))
            dis("      %s cherche(nt) le nom exact, sans variante .gz."
                % lecteurs)
        dis("")
        dis("  Ce n est pas une donnee a proteger, c est un lecteur a")
        dis("  corriger. extraire_cycles le fait deja en six lignes :")
        dis("  essayer le nom, puis le nom + .gz, et ouvrir via gzip si")
        dis("  besoin. Tant que ce n est pas fait, je ne comprime pas.")
        dis("=" * 94)
    if mode == "RAPPORT SEUL":
        dis("  Rien n a ete touche.")
        dis("")
        dis("  Etape suivante raisonnable, et sans aucune suppression :")
        dis("      python rotation_docs.py --comprimer")
        dis("  Elle ne fait que gzip + verification par empreinte. Un")
        dis("  fichier n est efface qu apres relecture complete de son")
        dis("  .gz et comparaison SHA-256.")
    else:
        dis("  Recupere : %s" % humain(gagne))
    dis("=" * 94)
    return 0


if __name__ == "__main__":
    sys.exit(main())
