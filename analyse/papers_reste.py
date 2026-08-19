# -*- coding: utf-8 -*-
r"""
papers_reste.py -- les trois cles qui restent, et deux erreurs a moi

  python papers_reste.py

LECTEUR SEUL. N ECRIT RIEN, NE PREND AUCUN TRADE.

CE QUE LE RUN PRECEDENT A ETABLI

    Vingt-neuf cles sont exactes au MEME INSTANT : 2026-08-18
    13:51:27. Pas une bande -- un point. Trois autres viennent de plus
    tot dans la meme seance : M5_WIDE_CL 24 min avant, M15_LEAD 33 min
    avant, M15_WIDE_CL 1 h 31 avant. L export est un instantane, pas
    une periode.

DEUX ERREURS A MOI, CORRIGEES ICI

 1. LE VERDICT AUTOMATIQUE DU SCRIPT PRECEDENT ETAIT FAUX.
    Il cherchait un facteur x8 entre deux K successifs. La suite fait
    0 s -> 24 min -> 33 min -> 1 h 31 -> impossible : aucun rapport x8,
    mais une discontinuite absolue a la fin. Mauvais test, pas
    mauvaises donnees.

 2. J AI ECRIT QUE INSIDE ET ABOVE ETAIENT DES MOTS INVENTES.
    C est faux. Ils sont dans les tickets : M1 INSIDE=1506,
    ABOVE=1499, BELOW=1556. Ils ne figuraient pas dans le CODE des
    autres modules, qui emploient d autres vocabulaires. J ai confondu
    "absent du code" et "inexistant".

    Alors pourquoi RSI_M1_BU et RSI_M15_BU n avaient-elles aucun
    instant ? Parce que JE NE LES AI JAMAIS MESUREES : je les avais
    marquees "hors panneau" dans SECTIONS, et le script a obei --
    fen[cle] = (None, None) par construction. Ce n etait pas un
    resultat, c etait mon etiquetage qui me revenait.

 3. UNE FENETRE DE "0 s" N EST PAS ETROITE, ELLE EST VIDE.
    C_M15_VENTE affichait [08:00:05, 08:00:05). Deux signaux partagent
    l horodatage du 358e rang : toute coupure qui prend le 358e prend
    aussi le 359e. Aucune coupure ne donne 358. L affichage aurait du
    ecrire JAMAIS.

CE QUE FAIT CE SCRIPT

    A. Il MESURE les deux cles RSI, avec le predicat tel qu il est
       ecrit dans papers_encode, sur les six combinaisons declarees
       d avance : {trades, signaux} x {US, EUR, ALL}. Six essais poses
       avant de regarder, pas une recherche.

    B. Il va chercher le mot CONFLIT et les effectifs 358 / 171 / 186
       dans les FICHIERS TEXTE du depot -- l export lui-meme y est.
       L en-tete au-dessus de la ligne dira de quelle section elle
       vient, au lieu que je le devine une fois de plus.

    Si une combinaison rend 171 (ou 186) avec une fenetre qui contient
    13:51:27, la cle est identifiee par le meme critere que les 29
    autres. Si aucune ne le fait, le script le dit et la cle reste
    ouverte -- elle ne sera pas rangee de force.
"""
import argparse
import io
import os
import sys

INSTANT_DEFAUT = "2026-08-18 13:51:27"
MOTS = ("CONFLIT", "conflit")
NOMBRES = ("358", "171", "186")


def fichiers_texte(racines, taille_max=4 * 1024 * 1024):
    """Les .txt et .md de ces racines, chacun UNE fois.

    Les racines se recouvrent (docs, panels et le point les contient
    toutes) : sans dedoublonnage on relirait les memes fichiers et le
    plafond de resultats tomberait sur des doublons."""
    vus = set()
    for racine in racines:
        if not os.path.isdir(racine):
            continue
        for dossier, _sd, fichiers in os.walk(racine):
            for f in sorted(fichiers):
                if not f.lower().endswith((".txt", ".md")):
                    continue
                chemin = os.path.join(dossier, f)
                cle = os.path.normcase(os.path.abspath(chemin))
                if cle in vus:
                    continue
                vus.add(cle)
                try:
                    if os.path.getsize(chemin) > taille_max:
                        continue
                    yield chemin, io.open(
                        chemin, encoding="utf-8",
                        errors="replace").read().split("\n")
                except Exception:
                    continue


def cherche_texte(add, racines, max_hits=30):
    add("=" * 96)
    add("D OU VIENT 'CONFLIT' -- recherche dans les fichiers texte")
    add("=" * 96)
    add("  L export a ete recopie d un panneau. Le panneau ecrit aussi")
    add("  des .txt. L en-tete au-dessus de la ligne dira la section.")
    add("")
    vus = 0
    for chemin, lignes in fichiers_texte(racines):
        for i, l in enumerate(lignes):
            if not any(m in l for m in MOTS):
                continue
            add("  %s:%d" % (chemin, i + 1))
            for j in range(max(0, i - 3), min(len(lignes), i + 2)):
                add("      %s%s" % ("> " if j == i else "  ",
                                    lignes[j][:86]))
            add("")
            vus += 1
            if vus >= max_hits:
                add("  ... (arrete a %d)" % max_hits)
                return
    if not vus:
        add("  Le mot CONFLIT n apparait dans aucun .txt ni .md lisible.")
        add("  L export ne vient donc pas d un fichier de ce depot : il a")
        add("  ete copie depuis le HTML du panneau, dans le navigateur.")
        add("  Son libelle est alors celui d une legende, pas d une")
        add("  colonne -- et il faudra le retrouver dans le HTML.")


def cherche_nombres(add, racines, max_hits=24):
    add("")
    add("=" * 96)
    add("LES EFFECTIFS 358 / 171 / 186 DANS LES MEMES FICHIERS")
    add("=" * 96)
    add("  Un effectif isole ne prouve rien ; trois sur la meme ligne,")
    add("  si. On cherche les lignes qui en portent au moins DEUX.")
    add("")
    vus = 0
    for chemin, lignes in fichiers_texte(racines):
        for i, l in enumerate(lignes):
            if sum(1 for n in NOMBRES if n in l) < 2:
                continue
            add("  %s:%d  %s" % (chemin, i + 1, l.strip()[:76]))
            vus += 1
            if vus >= max_hits:
                add("  ... (arrete a %d)" % max_hits)
                return
    if not vus:
        add("  Aucune ligne ne porte deux de ces trois nombres.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--instant", default=INSTANT_DEFAUT)
    p.add_argument("--rails", default=None)
    a = p.parse_args()

    try:
        import papers_encode as PE
        import papers_population as PP
        import papers_coupure as PC
    except ImportError as e:
        print("KO : papers_encode, papers_population et papers_coupure")
        print("     doivent etre dans ce dossier. (%s)" % e)
        return 1

    chemin = a.rails or PP.RAILS
    trades, ko = PP.lire(chemin)
    sigs, _ec = PP.signaux(trades)

    L = []
    add = L.append
    add("=" * 96)
    add("LES TROIS CLES QUI RESTENT")
    add("=" * 96)
    add("")
    add("  Lecteur seul. Rien n est ecrit, aucun trade n est pris.")
    add("")
    add("  %s : %d lignes (%d illisibles)" % (chemin, len(trades), ko))
    add("  instant de reference : %s  (29 cles y sont exactes)" % a.instant)
    add("")

    # ---- A. les deux cles RSI, enfin mesurees -----------------------
    add("=" * 96)
    add("RSI_M1_BU ET RSI_M15_BU -- mesurees, cette fois")
    add("=" * 96)
    add("  Le predicat est celui de papers_encode, inchange. Les six")
    add("  combinaisons sont posees d avance : deux populations, trois")
    add("  colonnes. Rien n est essaye au-dela.")
    add("")
    cibles = [(c, n, pr) for c, _lib, n, pr, _no in PE.CLES
              if c in ("RSI_M1_BU", "RSI_M15_BU") and pr is not None]
    if not cibles:
        add("  Les deux cles n ont pas de predicat dans papers_encode.")
    for cle, n, pred in cibles:
        add("  %s -- annonce %d" % (cle, n))
        trouve = False
        for nom, pop in (("trades", trades), ("signaux", sigs)):
            for col in ("US", "EUR", "ALL"):
                ts = PC.horodates(pop, pred, col, PE)
                v = sum(1 for e in ts if e <= a.instant)
                lo, hi = PC.fenetre(ts, n)
                if lo is not None and lo == hi:
                    etat = "JAMAIS (deux lignes au meme horodatage)"
                elif lo is None:
                    etat = "n atteint jamais %d (total %d)" % (n, len(ts))
                elif lo <= a.instant < hi:
                    etat = "EXACTE A L INSTANT DE REFERENCE"
                    trouve = True
                else:
                    etat = "exacte ailleurs : [%s, %s)" % (lo, hi)
                add("    %-8s %-4s  total %5d   a l instant %5d  %+5d   %s"
                    % (nom, col, len(ts), v, v - n, etat))
        if not trouve:
            add("    -> aucune des six ne tombe a l instant de reference.")
            add("       La cle reste OUVERTE. Elle ne sera pas rangee de")
            add("       force dans une section qui ne la produit pas.")
        add("")

    # ---- B. C_M15_VENTE : la fenetre vide, dite comme telle ---------
    add("=" * 96)
    add("C_M15_VENTE -- pourquoi aucune coupure ne peut donner 358")
    add("=" * 96)
    for cle, _lib, n, pred, _no in PE.CLES:
        if cle != "C_M15_VENTE":
            continue
        ts = PC.horodates(sigs, pred, "ALL", PE)
        add("  predicat papers_encode, signaux, ALL : %d au total" % len(ts))
        if len(ts) > n:
            add("  rang %d : %s" % (n, ts[n - 1]))
            add("  rang %d : %s" % (n + 1, ts[n]))
            if ts[n - 1] == ts[n]:
                add("")
                add("  Les deux memes. Toute coupure qui prend le %de prend"
                    % n)
                add("  aussi le %de : 358 est INATTEIGNABLE avec ce" % (n + 1))
                add("  predicat. Ce n est pas une fenetre etroite, c est une")
                add("  fenetre vide, et mon affichage disait '0 s'.")
    add("")

    # ---- C. d ou vient le mot CONFLIT -------------------------------
    cherche_texte(add, [os.path.join("docs"), "panels", "."])
    cherche_nombres(add, [os.path.join("docs"), "panels", "."])

    add("")
    add("=" * 96)
    add("  Ce script n a rien ecrit et n a pris aucun trade.")
    add("=" * 96)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
