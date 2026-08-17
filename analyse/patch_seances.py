# -*- coding: utf-8 -*-
r"""
patch_seances.py -- une seance n est pas une date

  python patch_seances.py            applique
  python patch_seances.py            relance : detecte et ne refait rien

CE QU IL CORRIGE

    `reaction_evenements.py` comptait les horizons en jours en avancant
    dans la liste des DATES presentes dans les barres. Les futures CME
    rouvrent le DIMANCHE SOIR : une poignee de barres suffit a faire
    apparaitre le dimanche dans cette liste. Avancer de trois crans
    depuis un mercredi tombait alors sur ce dimanche, qui n a aucune
    barre a 12:30 UTC -- l heure des publications americaines.

    Symptome : la colonne `3j` sortait a 10 points quand `1j` en avait
    22 et `5j` 20. Un effectif NON MONOTONE, qui ne s explique par
    aucune donnee manquante et signale qu on compte mal.

    Apres correction, une seance est une date portant au moins la
    MOITIE du nombre median de barres par jour. Le seuil est mesure sur
    la serie, pas invente, et il est affiche.

MARCHE ARRIERE

    Une copie `.bak-<horodatage>` est ecrite avant modification. Le
    patch ne s applique qu une fois : relance, il le dit et ne touche a
    rien.
"""
import io
import os
import sys
import datetime as dt

CIBLE = "reaction_evenements.py"
ANCRE = "        jours_b = sorted(set(x[0].date() for x in serie))"
MARQUE = "med_j = cpt[len(cpt) // 2]"

NOUVEAU = '''        # Les SEANCES, pas les dates presentes. Les futures CME
        # rouvrent le DIMANCHE SOIR : une poignee de barres suffit a
        # faire apparaitre le dimanche dans la liste des dates, et
        # avancer de trois crans depuis un mercredi tombait alors sur
        # ce dimanche fantome, qui n a aucune barre a 12:30 UTC. La
        # colonne 3j sortait a 10 points quand 1j en avait 22 et 5j 20
        # -- un effectif non monotone, signe qu on compte mal.
        #
        # On ne garde donc que les dates portant au moins la moitie du
        # nombre median de barres par jour. Le seuil est MESURE sur la
        # serie, pas invente.
        par_date = {}
        for x in serie:
            d = x[0].date()
            par_date[d] = par_date.get(d, 0) + 1
        cpt = sorted(par_date.values())
        med_j = cpt[len(cpt) // 2] if cpt else 0
        jours_b = sorted(d for d, n in par_date.items()
                         if n >= max(1, med_j // 2))
        dis("  %d date(s) dans les barres, %d retenues comme SEANCES"
            % (len(par_date), len(jours_b)))
        dis("  (au moins %d barres, soit la moitie de la mediane"
            % max(1, med_j // 2))
        dis("  journaliere de %d). Les reouvertures du dimanche soir en"
            % med_j)
        dis("  sont exclues : elles n ont pas de barre a l heure des")
        dis("  publications.")'''


def main():
    if not os.path.isfile(CIBLE):
        print("KO : %s introuvable. Lancer depuis le dossier de la stack."
              % CIBLE)
        return 1
    src = io.open(CIBLE, encoding="utf-8").read()

    if MARQUE in src:
        print("Deja applique : le calcul des seances est en place.")
        print("Rien n a ete modifie.")
        return 0
    if ANCRE not in src:
        print("KO : l ancre n a pas ete trouvee.")
        print("     Attendu la ligne :")
        print("       %s" % ANCRE.strip())
        print("     Le fichier n est pas la version attendue -- reprendre")
        print("     reaction_evenements_v2.py sur le Drive.")
        return 1
    if src.count(ANCRE) != 1:
        print("KO : l ancre apparait %d fois, une seule attendue."
              % src.count(ANCRE))
        return 1

    bak = "%s.bak-%s" % (CIBLE, dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    io.open(bak, "w", encoding="utf-8").write(src)

    out = src.replace(ANCRE, NOUVEAU)
    # Controle avant ecriture : le fichier doit rester compilable.
    try:
        compile(out, CIBLE, "exec")
    except SyntaxError as e:
        print("KO : le resultat ne compile pas (%s ligne %s)."
              % (e.msg, e.lineno))
        print("     Rien n a ete ecrit. La sauvegarde %s reste." % bak)
        return 1
    io.open(CIBLE, "w", encoding="utf-8").write(out)

    print("Applique.")
    print("  sauvegarde : %s" % bak)
    print("  %d lignes -> %d lignes"
          % (len(src.splitlines()), len(out.splitlines())))
    print()
    print("Marche arriere : Copy-Item %s %s -Force" % (bak, CIBLE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
