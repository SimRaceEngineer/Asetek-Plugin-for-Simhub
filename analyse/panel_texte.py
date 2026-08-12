# -*- coding: utf-8 -*-
"""
panel_texte.py -- rendre une sortie console en panneau lisible

  python panel_texte.py panels\\panel_rails_trois.txt > essai.html
  python panel_texte.py panels\\panel_rails_trois.txt --verifier

CE QU IL FAIT

    Il prend le texte exporte -- de la sortie console a colonnes fixes --
    et le rend comme RAILS TRADES : titres en bandeau, vrais tableaux
    HTML, lignes alternees, chiffres colores par le signe, prose lisible.

    Les panneaux etaient corrects mais serres et gris : un <pre> brut.
    Ce module ne change AUCUN chiffre, il ne fait que les mettre en page.

COMMENT IL TROUVE LES COLONNES -- et pourquoi pas au jugé

    Decouper sur les espaces ne marche pas : une cellule vide ("-" seul
    dans sa periode) donnerait moins de cellules que les autres lignes,
    et tout le tableau glisserait d une colonne.

    On procede par MASQUE D ESPACES. On empile les lignes du bloc et on
    garde les positions ou TOUTES ont un espace. Deux positions vides
    consecutives ou plus = une separation ; entre deux separations, une
    colonne. C est la geometrie reelle du texte qui decide, pas une
    supposition sur son format.

    Consequence utile : une cellule vide reste dans SA colonne, et une
    colonne trop pleine pour laisser une gouttiere fusionne avec sa
    voisine -- moche, mais jamais faux.

CE QU IL NE JETTE PAS

    Toutes les lignes sortent, y compris les avertissements, les "?" des
    cellules trop petites et les notes de bas de bloc. Seules les barres
    ==== et ---- disparaissent, remplacees par la mise en page qu elles
    dessinaient en ASCII.

    --verifier le prouve : il recompte les lignes non-barre du texte
    source et celles rendues, et affiche les manquantes s il y en a. Un
    panneau qui perd un avertissement en devenant joli est une
    regression, pas une amelioration.

QUAND IL NE COMPREND PAS

    Un bloc qui n a pas la forme entete / ---- / lignes reste en
    monospace, colore mais non tabule. Il vaut mieux un bloc brut qu un
    tableau mal aligne : le premier se lit, le second trompe.
"""
import html as _html
import io
import re
import sys

# La palette de la page 8095, pas une nouvelle.
FOND = "#1b1b1d"
FOND2 = "#232326"
TEXTE = "#e8eaed"
GRIS = "#9aa0a6"
BLEU = "#8ab4f8"
VERT = "#81c995"
ROUGE = "#f28b82"
AMBRE = "#fbbc04"

RE_FORT = re.compile(r"^\s*={4,}\s*$")
RE_FIN = re.compile(r"^\s*-{4,}\s*$")
RE_NOMBRE = re.compile(r"^[+-]?\d+(?:[  ]\d{3})*(?:\.\d+)?$")
RE_ENTIER = re.compile(r"^\d+$")
RE_PCT = re.compile(r"^\d+%$")

# Les verdicts churn ont une couleur fixe dans toute la stack.
VERDICTS = {"CHURN": ROUGE, "MIXED": AMBRE, "CLEAN": VERT,
            "OK": VERT, "KO": ROUGE, "PERIME": ROUGE}


def _e(s):
    return _html.escape(s, quote=False)


# ---------------------------------------------------------------- colonnes

def _masque(lignes):
    """Positions ou toutes les lignes ont un espace."""
    larg = max(len(l) for l in lignes)
    plein = [l.ljust(larg) for l in lignes]
    return [all(p[i] == " " for p in plein) for i in range(larg)], larg


def _colonnes(lignes, entete=None):
    """[(debut, fin)] des colonnes, deduites du masque d espaces.

    Une gouttiere = au moins DEUX espaces a la meme position sur toutes
    les lignes. Un seul espace ne suffit pas : entre '%10.2f' et '%5d' il
    y en a un, et couper la donnerait deux colonnes pour un nombre.

    Ce seuil manque parfois une vraie separation -- avec '%4s %4s', une
    valeur qui remplit sa case ne laisse qu un espace. D ou _affiner :
    l ENTETE dit combien il y a de colonnes, la DONNEE dit ou couper."""
    vide, larg = _masque(lignes)
    cols, debut = [], None
    i = 0
    while i < larg:
        if vide[i]:
            j = i
            while j < larg and vide[j]:
                j += 1
            if j - i >= 2:                 # vraie gouttiere
                if debut is not None:
                    cols.append((debut, i))
                    debut = None
            elif debut is None:
                debut = i                  # espace isole : dans la colonne
            i = j
        else:
            if debut is None:
                debut = i
            i += 1
    if debut is not None:
        cols.append((debut, larg))
    return _affiner(cols, entete, vide) if entete is not None else cols


def _affiner(cols, entete, vide):
    """Couper les colonnes ou l entete en annonce visiblement deux.

    Si le texte d entete d une colonne contient lui-meme un blanc de deux
    espaces ou plus -- 'N   WR' --, c est que deux colonnes ont fusionne.
    On cherche alors, DANS ce blanc, une position ou toutes les lignes
    ont un espace, et on coupe la. S il n y en a aucune, on laisse
    fusionne : une colonne trop large se lit, une coupure au mauvais
    endroit tronque un nombre."""
    out = []
    for d, f in cols:
        seg = entete[d:f] if d < len(entete) else ""
        coupes = []
        for m in re.finditer(r"(?<=\S)\s{2,}(?=\S)", seg):
            zone = [d + k for k in range(m.start(), m.end())]
            libre = [p for p in zone if p < len(vide) and vide[p]]
            if libre:
                coupes.append(libre[0])
        bornes = [d] + coupes + [f]
        for k in range(len(bornes) - 1):
            if bornes[k + 1] > bornes[k]:
                out.append((bornes[k], bornes[k + 1]))
    return out


def _cellules(ligne, cols):
    return [ligne[d:f].strip() if d < len(ligne) else "" for d, f in cols]


def _groupes(ligne, cols):
    """Entete de groupe (« 1 TENDANCE » au-dessus de trois colonnes).

    Rend [(texte, colspan)]. Ces libelles sont cadres a DROITE de leur
    groupe ('%24s') : ils ne surplombent donc que les dernieres colonnes
    de celui-ci. Les prendre au pied de la lettre donnerait « 2 RANGE »
    au-dessus de la seule colonne WR, avec deux cases vides a sa gauche.

    On rattache donc chaque libelle a TOUT ce qui separe la fin du
    precedent de la sienne. Le premier n a pas de precedent : on lui
    donne la longueur mediane des autres. S il est seul, on le laisse ou
    la geometrie le met -- inventer une largeur sans point de comparaison
    serait deviner."""
    if not ligne.strip():
        return None
    reperes = []
    for m in re.finditer(r"\S(?:.*?\S)?(?=\s{2,}|$)", ligne):
        d, f = m.start(), m.end()
        prem = next((k for k in range(len(cols)) if cols[k][1] > d), None)
        if prem is None:
            break
        der = prem
        while der + 1 < len(cols) and cols[der + 1][0] < f:
            der += 1
        reperes.append([m.group(0).strip(), prem, der])
    if not reperes:
        return None

    for k in range(1, len(reperes)):
        reperes[k][1] = reperes[k - 1][2] + 1
    if len(reperes) > 1:
        autres = sorted(r[2] - r[1] + 1 for r in reperes[1:])
        larg = autres[len(autres) // 2]
        reperes[0][1] = max(0, min(reperes[0][1], reperes[0][2] - larg + 1))

    out, i = [], 0
    for txt, prem, der in reperes:
        if prem > i:
            out.append(("", prem - i))
        out.append((txt, der - prem + 1))
        i = der + 1
    if i < len(cols):
        out.append(("", len(cols) - i))
    return out


# ---------------------------------------------------------------- couleurs

def _couleur(txt, premiere):
    """La couleur d une cellule. Le signe d abord, le mot ensuite."""
    t = txt.strip()
    if not t or t == "-":
        return GRIS, False
    if premiere:
        return BLEU, True
    hd = t.upper().split()[0].rstrip(":")
    if hd in VERDICTS:
        return VERDICTS[hd], True
    base = t[:-1].strip() if t.endswith("?") else t
    if RE_ENTIER.match(base) or RE_PCT.match(base):
        return TEXTE, False
    if RE_NOMBRE.match(base.replace(" ", "")):
        try:
            v = float(base.replace(" ", "").replace(" ", ""))
        except ValueError:
            return TEXTE, False
        if v > 0:
            return VERT, False
        if v < 0:
            return ROUGE, False
    return TEXTE, False


def _cellule_html(txt, premiere, pid):
    """Une cellule. Le '?' des effectifs trop faibles reste visible et
    passe en ambre : c est un avertissement, pas une decoration."""
    t = txt.strip()
    marque = ""
    # Le '?' d effectif suit un CHIFFRE. Un libelle qui vaut « ? / ? »
    # -- un rail dont on ignore le sens -- n est pas un avertissement de
    # taille, et lui en mettre un raconterait le contraire du vrai.
    if not premiere and t.endswith("?") and len(t) > 1:
        tete = t[:-1].strip()
        if RE_PCT.match(tete) or RE_NOMBRE.match(tete.replace(" ", "")):
            t, marque = tete, (
                '<span style="color:%s" title="effectif trop faible">'
                ' ?</span>' % AMBRE)
    coul, gras = _couleur(t + ("?" if marque else ""), premiere)
    st = "color:%s" % coul
    if gras:
        st += ";font-weight:600"
    return '<td style="%s">%s%s</td>' % (st, _e(t), marque)


# ------------------------------------------------------------------ blocs

def _table_html(entetes, corps, pid):
    cols = (_colonnes([entetes[-1]] + corps, entetes[-1]) if entetes
            else _colonnes(corps))
    if len(cols) < 2:
        return None
    h = ['<table>']
    if len(entetes) > 1:
        for g in entetes[:-1]:
            gr = _groupes(g, cols)
            if not gr:
                continue
            h.append('<tr class="grp">')
            for txt, span in gr:
                h.append('<th colspan="%d">%s</th>' % (span, _e(txt)))
            h.append('</tr>')
    if entetes:
        h.append('<tr>')
        for c in _cellules(entetes[-1], cols):
            h.append('<th>%s</th>' % _e(c))
        h.append('</tr>')
    for k, ligne in enumerate(corps):
        h.append('<tr%s>' % (' class="alt"' if k % 2 else ''))
        for i, c in enumerate(_cellules(ligne, cols)):
            h.append(_cellule_html(c, i == 0, pid))
        h.append('</tr>')
    h.append('</table>')
    return "".join(h)


def _prose_html(lignes):
    """Prose. Les lignes tout en majuscules sont des avertissements --
    l auteur les a ecrites ainsi, on ne les eteint pas."""
    out = ['<div class="pr">']
    for l in lignes:
        s = l.rstrip()
        if not s.strip():
            out.append('<div class="sp"></div>')
            continue
        ind = len(s) - len(s.lstrip())
        c = s.strip()
        lettres = [x for x in c if x.isalpha()]
        fort = bool(lettres) and all(x.isupper() for x in lettres)
        st = "margin-left:%dpx" % (ind * 7)
        if fort:
            st += ";color:%s;font-weight:600" % AMBRE
        out.append('<div style="%s">%s</div>' % (st, _e(c)))
    out.append('</div>')
    return "".join(out)


def _brut_html(lignes):
    """Repli : monospace, mais espace et lisible."""
    return ('<pre class="br">%s</pre>'
            % _e("\n".join(l.rstrip() for l in lignes)))


def _decouper(txt):
    """[(genre, charge)] -- 'titre', 'table', 'prose'.

    Deux regles, et rien d autre :
      une ligne encadree de ==== est un titre ;
      une barre ---- separe l entete du corps d un tableau."""
    lignes = txt.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocs, tampon, i = [], [], 0

    def vider():
        while tampon and not tampon[-1].strip():
            tampon.pop()
        if tampon:
            blocs.append(("prose", list(tampon)))
        del tampon[:]

    while i < len(lignes):
        l = lignes[i]
        if (RE_FORT.match(l) and i + 2 < len(lignes)
                and RE_FORT.match(lignes[i + 2]) and lignes[i + 1].strip()):
            vider()
            blocs.append(("titre", lignes[i + 1].strip()))
            i += 3
            continue
        if RE_FIN.match(l):
            # entete = jusqu a 2 lignes pleines juste au-dessus
            ent = []
            while tampon and len(ent) < 2 and tampon[-1].strip():
                ent.insert(0, tampon.pop())
            corps, j = [], i + 1
            while j < len(lignes):
                if RE_FIN.match(lignes[j]) or RE_FORT.match(lignes[j]):
                    break
                if not lignes[j].strip():
                    break
                corps.append(lignes[j])
                j += 1
            if corps and ent:
                vider()
                blocs.append(("table", (ent, corps)))
                i = j + 1 if j < len(lignes) and RE_FIN.match(lignes[j]) else j
                continue
            tampon.extend(ent)          # forme inattendue : on ne force pas
            i += 1
            continue
        tampon.append(l)
        i += 1
    vider()
    return blocs


# ------------------------------------------------------------------ rendu

def _css(pid):
    return (
        '<style>'
        '#%(p)s{padding:12px 18px 22px 18px;color:%(t)s;'
        'font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif}'
        '#%(p)s h2{margin:0 0 2px 0;font-size:19px;letter-spacing:.4px}'
        '#%(p)s .age{color:%(g)s;font-size:11.5px;margin-bottom:16px}'
        '#%(p)s h3{margin:26px 0 10px 0;font-size:13px;font-weight:600;'
        'letter-spacing:1.6px;color:%(b)s;text-transform:uppercase;'
        'border-left:3px solid %(b)s;padding:5px 0 5px 10px;'
        'background:linear-gradient(90deg,rgba(138,180,248,.10),'
        'rgba(138,180,248,0))}'
        '#%(p)s table{border-collapse:collapse;margin:6px 0 14px 0;'
        'font-size:12.5px;font-variant-numeric:tabular-nums;'
        'background:%(f2)s;border-radius:6px;overflow:hidden}'
        '#%(p)s th{color:%(g)s;font-weight:600;font-size:11px;'
        'letter-spacing:.8px;text-transform:uppercase;text-align:right;'
        'padding:8px 14px;border-bottom:1px solid rgba(255,255,255,.14);'
        'white-space:nowrap}'
        '#%(p)s tr.grp th{color:%(t)s;text-align:center;font-size:11.5px;'
        'border-bottom:1px solid rgba(255,255,255,.07);padding-bottom:5px}'
        '#%(p)s th:first-child{text-align:left}'
        '#%(p)s td{padding:6px 14px;text-align:right;white-space:nowrap;'
        'font-variant-numeric:tabular-nums}'
        '#%(p)s td:first-child{text-align:left;padding-right:26px}'
        '#%(p)s tr.alt td{background:rgba(255,255,255,.028)}'
        '#%(p)s tbody tr:hover td,#%(p)s tr:hover td'
        '{background:rgba(138,180,248,.09)}'
        '#%(p)s .pr{font-size:12.5px;line-height:1.62;color:%(g)s;'
        'margin:8px 0 14px 0;max-width:118ch}'
        '#%(p)s .pr .sp{height:9px}'
        '#%(p)s .br{white-space:pre;overflow-x:auto;font-size:12px;'
        'line-height:1.5;color:%(t)s;background:%(f2)s;padding:12px 14px;'
        'border-radius:6px;margin:6px 0 14px 0}'
        '#%(p)s .tete{display:flex;align-items:baseline;'
        'justify-content:space-between;gap:14px}'
        '#%(p)s .cp{background:%(f2)s;color:%(t)s;'
        'border:1px solid rgba(255,255,255,.16);border-radius:6px;'
        'padding:4px 13px;font-size:11.5px;cursor:pointer;'
        'font-family:inherit;white-space:nowrap;flex:none}'
        '#%(p)s .cp:hover{border-color:%(b)s;color:%(b)s}'
        # La source brute, hors ecran : c est ELLE qu on copie. Copier le
        # rendu HTML rendrait des colonnes collees et des lignes cassees,
        # donc du texte inutilisable dans un REPL ou un prompt.
        '#%(p)s .src{position:absolute;left:-9999px;top:0;'
        'width:1px;height:1px;opacity:0}'
        '</style>'
        % {"p": pid, "t": TEXTE, "g": GRIS, "b": BLEU, "f2": FOND2})


def _bouton(pid):
    """Copie le TEXTE BRUT, pas le rendu. navigator.clipboard d abord ;
    si le navigateur le refuse -- il l interdit hors HTTPS sur certaines
    configurations -- on retombe sur la selection + execCommand, qui
    marche encore partout. Le bouton dit ce qui s est passe : muet, on
    ne saurait pas si la copie a eu lieu."""
    return (
        '<button class="cp" onclick="(function(b){'
        "var t=document.getElementById('%(p)s_src');"
        "var ok=function(){b.textContent='copie';"
        "setTimeout(function(){b.textContent='Copy'},1400)};"
        "var vieux=function(){t.select();"
        "try{document.execCommand('copy');ok()}"
        "catch(e){b.textContent='echec'}};"
        "if(navigator.clipboard&&navigator.clipboard.writeText)"
        "{navigator.clipboard.writeText(t.value).then(ok,vieux)}"
        "else{vieux()}"
        '})(this)">Copy</button>' % {"p": pid})


def rendre(txt, titre, fichier, age, pid=None):
    """Le panneau complet, CSS comprise. pid isole le style du reste."""
    pid = pid or ("pnl_" + re.sub(r"\W+", "", titre).lower())
    if age is None:
        entete, coul = "fichier absent", ROUGE
    elif age > 3600:
        entete, coul = "exporte il y a %d min -- PERIME" % (age // 60), ROUGE
    elif age > 1200:
        entete, coul = "exporte il y a %d min" % (age // 60), AMBRE
    else:
        entete, coul = "exporte il y a %d min" % (age // 60), BLEU

    corps = [_css(pid), '<div id="%s">' % pid,
             '<div class="tete">',
             '<h2 style="color:%s">%s</h2>' % (coul, _e(titre)),
             _bouton(pid),
             '</div>',
             '<div class="age">%s &middot; %s</div>'
             % (_e(entete), _e(str(fichier))),
             '<textarea id="%s_src" class="src" readonly>%s</textarea>'
             % (pid, _e(txt))]
    for genre, charge in _decouper(txt):
        if genre == "titre":
            corps.append("<h3>%s</h3>" % _e(charge))
        elif genre == "table":
            ent, lot = charge
            t = _table_html(ent, lot, pid)
            corps.append(t if t else _brut_html(ent + lot))
        else:
            corps.append(_prose_html(charge))
    corps.append("</div>")
    return "".join(corps)


# ------------------------------------------------------------- verification

def verifier(txt, html):
    """Aucune ligne perdue ? Rend (manquantes, total).

    Une ligne de tableau devient plusieurs <td> : on recolle donc par
    ligne de rendu -- </tr> et les balises de bloc redeviennent des
    retours a la ligne, le reste des espaces. Comparer cellule par
    cellule laisserait passer une colonne perdue."""
    # La zone source cachee du bouton Copy contient le texte ENTIER. La
    # laisser ici ferait passer le controle a tous les coups, meme si le
    # rendu perdait une colonne : le verificateur trouverait chaque ligne
    # dans la copie, pas dans le tableau. On la retire d abord.
    html = re.sub(r"<textarea\b[^>]*>.*?</textarea>", " ", html,
                  flags=re.S)
    nu = re.sub(r"</(tr|div|pre|h2|h3|style)>", "\n", html)
    nu = re.sub(r"<[^>]+>", " ", nu)
    nu = _html.unescape(nu)
    vus = set(" ".join(l.split()) for l in nu.split("\n") if l.strip())
    manque, total = [], 0
    for l in txt.split("\n"):
        s = " ".join(l.split())
        if not s or RE_FORT.match(l) or RE_FIN.match(l):
            continue
        total += 1
        if s not in vus:
            manque.append(s)
    return manque, total


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().split("\n\n")[0])
        return 1
    txt = io.open(argv[1], encoding="utf-8", errors="replace").read()
    h = rendre(txt.strip(), "ESSAI", argv[1], 0)
    if "--verifier" in argv:
        manque, total = verifier(txt, h)
        print("%d lignes de contenu, %d rendues, %d manquantes"
              % (total, total - len(manque), len(manque)))
        for m in manque[:20]:
            print("  MANQUE : %s" % m[:100])
        return 1 if manque else 0
    sys.stdout.write(h)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
