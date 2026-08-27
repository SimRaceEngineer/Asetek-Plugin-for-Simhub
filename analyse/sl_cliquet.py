# -*- coding: utf-8 -*-
r"""sl_cliquet.py -- un stop deplace dans le sens du gain ne revient jamais

LA REGLE, ET ELLE EST UNIQUE
    Pour chaque position, on retient le MEILLEUR stop jamais vu. Toute
    ecriture qui proposerait moins bien est refusee. Pour un achat le
    meilleur est le plus haut, pour une vente le plus bas.

    Rien d autre n est arbitre : ni les ouvertures, ni les fermetures,
    ni les TP, ni les volumes.

POURQUOI PAS sl_arbitre
    sl_arbitre applique la meme regle, mais il relit le stop courant sur
    MT5 a chaque appel. Trois defauts en decoulent, tous constates :

    1. Sa reference est effacable. Un "sl = 0" supprime le stop, et
       comme la position n en a plus, la repose du stop d ORIGINE
       devient autorisee. Deux requetes anodines, un recul complet,
       aucune ligne de journal. Ici la memoire est A NOUS : effacer le
       stop chez le courtier ne l efface pas chez nous, et un
       effacement est lui-meme traite comme un recul a l infini.

    2. Il est pose UNE FOIS au demarrage. Cinquante et un fichiers
       reecrivent mt5.order_send au fil de la journee -- les gates a
       fenetre horaire le font a chaque ouverture et fermeture de leur
       fenetre -- et l un d eux finit par rendre la fonction d origine.
       Le 26/08, l arbitre avait produit UNE ligne de journal en seize
       heures, pour 301 entrees : il etait hors de la chaine. Ici un fil
       de veille verifie la pose toutes les VEILLE_SEC secondes et la
       refait au besoin.

    3. Il ne vit que dans le moteur. L envoyeur du pont ecrit des stops
       sur le compte dedie sans aucun controle. install() est donc fait
       pour etre appele dans CHAQUE processus qui ecrit des stops.

LA MEMOIRE SUR DISQUE
    Un redemarrage ne doit pas amnesier le cliquet : une position
    ouverte hier soir garde son meilleur stop ce matin. Le fichier est
    ecrit de facon atomique, et sa perte n est jamais fatale -- au pire
    on repart de ce que MT5 annonce.

FAIL-OPEN, PARTOUT
    Champ manquant, position introuvable, exception, premier stop d une
    position : la requete passe. Ce cliquet ne sait faire qu une chose,
    refuser un recul avere, et il ne doit JAMAIS empecher la pose d un
    premier stop ni bloquer sur une erreur transitoire. Un arbitre en
    panne laisse jouer.

CE QU IL JOURNALISE
    Chaque refus nomme le module appelant. C est ce qui dira enfin QUI
    ramene les stops en arriere -- une question ouverte depuis le 10/08.
"""
import io
import json
import os
import threading
import time

VERSION = "2.0"

# ---------------------------------------------------------------- reglages
BLOQUE = True           # False = observe et laisse passer
EXEMPTS = set()         # modules autorises a reculer un stop. Vide, et il
                        # faut un argument pour y toucher : un stop elargi
                        # augmente le risque de la position.
VEILLE_SEC = 20         # cadence du fil qui verifie la pose
SEUIL_RAPPORT = 200     # une synthese toutes les N ecritures de stop
MEMOIRE_FICHIER = os.path.join("docs", "sl_cliquet", "memoire.json")
OUBLI_SEC = 36 * 3600   # on oublie un ticket sans nouvelle depuis 36 h

# ------------------------------------------------------------------- etat
_verrou = threading.Lock()
_memoire = {}           # ticket -> {"sens": 1|-1, "meilleur": float,
                        #            "vu": ts, "par": module}
_stats = {}             # module -> {"ecrits", "refus", "points"}
_depuis = [0]
_mt5 = None
_origine = None
_log = None
_enveloppe = [None]     # l objet enveloppe courant, pour se reconnaitre
_pose = [False]
_fil = [None]
_sale = [False]


def _dire(niveau, msg, *a):
    if _log is not None:
        try:
            getattr(_log, niveau)(msg, *a)
            return
        except Exception:
            pass
    try:
        print(msg % a if a else msg, flush=True)
    except Exception:
        pass


def _appelant():
    """(module, fonction) du code qui a demande l ecriture."""
    try:
        import sys as _s
        n = 1
        while n < 14:
            f = _s._getframe(n)
            mod = f.f_globals.get("__name__", "?")
            if mod != __name__:
                return mod, f.f_code.co_name
            n += 1
    except Exception:
        pass
    return "?", "?"


def _champ(req, nom, defaut=None):
    """Un champ de requete, que ce soit un dict ou un objet."""
    try:
        if isinstance(req, dict):
            return req.get(nom, defaut)
        return getattr(req, nom, defaut)
    except Exception:
        return defaut


# ------------------------------------------------------------- la memoire

def _charge():
    try:
        with io.open(MEMOIRE_FICHIER, encoding="utf-8") as f:
            d = json.load(f)
        n = 0
        for k, v in (d.get("tickets") or {}).items():
            try:
                _memoire[int(k)] = {"sens": int(v["sens"]),
                                    "meilleur": float(v["meilleur"]),
                                    "vu": float(v.get("vu", 0)),
                                    "par": str(v.get("par", "?"))}
                n += 1
            except Exception:
                continue
        return n
    except Exception:
        return 0


def _ecrit():
    """Ecriture atomique. Sa perte n est jamais fatale."""
    try:
        d = os.path.dirname(MEMOIRE_FICHIER)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        tmp = MEMOIRE_FICHIER + ".tmp"
        with _verrou:
            paquet = {"version": VERSION, "ts": time.time(),
                      "tickets": dict((str(k), v) for k, v in _memoire.items())}
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(paquet, f)
        os.replace(tmp, MEMOIRE_FICHIER)
    except Exception:
        pass


def _oublie_les_vieux():
    limite = time.time() - OUBLI_SEC
    with _verrou:
        morts = [k for k, v in _memoire.items() if v.get("vu", 0) < limite]
        for k in morts:
            del _memoire[k]
    return len(morts)


def memoire():
    """Copie de la memoire, pour un panneau ou un rapport."""
    with _verrou:
        return dict((k, dict(v)) for k, v in _memoire.items())


# ------------------------------------------------------------- la decision

def _sens_de(tk):
    """1 achat, -1 vente, 0 inconnu. Lu sur MT5, une seule fois par ticket."""
    try:
        pos = _mt5.positions_get(ticket=tk)
        if pos:
            return 1 if pos[0].type == _mt5.POSITION_TYPE_BUY else -1
    except Exception:
        pass
    return 0


def _amorce(tk, sens):
    """Premiere rencontre : on prend le stop courant comme point de depart."""
    try:
        pos = _mt5.positions_get(ticket=tk)
        if pos and pos[0].sl:
            with _verrou:
                _memoire[tk] = {"sens": sens, "meilleur": float(pos[0].sl),
                                "vu": time.time(), "par": "amorce"}
            return float(pos[0].sl)
    except Exception:
        pass
    return None


def _juge(req):
    """(refuse, points_rendus, ticket, neuf, ancien) -- toute incertitude passe."""
    try:
        if _champ(req, "sl", None) is None and not isinstance(req, dict):
            return False, 0.0, None, None, None
        tk = _champ(req, "position", 0) or 0
        if not tk:
            return False, 0.0, None, None, None
        tk = int(tk)
        brut = _champ(req, "sl", None)
        if brut is None:
            return False, 0.0, None, None, None    # requete sans stop
        neuf = float(brut)

        with _verrou:
            m = _memoire.get(tk)
        if m is None:
            sens = _sens_de(tk)
            if sens == 0:
                return False, 0.0, tk, neuf, None  # position inconnue : on passe
            anc = _amorce(tk, sens)
            with _verrou:
                m = _memoire.get(tk)
            if m is None:
                # aucun stop encore pose : c est une premiere pose, on laisse
                if neuf:
                    with _verrou:
                        _memoire[tk] = {"sens": sens, "meilleur": neuf,
                                        "vu": time.time(), "par": "pose"}
                return False, 0.0, tk, neuf, anc

        sens, best = m["sens"], m["meilleur"]

        # Un effacement est un recul a l infini, pas une absence de stop.
        if not neuf:
            return True, float("inf"), tk, 0.0, best

        recule = (neuf < best) if sens > 0 else (neuf > best)
        if recule:
            return True, abs(best - neuf), tk, neuf, best

        with _verrou:
            e = _memoire.get(tk)
            if e is not None:
                e["meilleur"] = neuf
                e["vu"] = time.time()
        return False, 0.0, tk, neuf, best
    except Exception:
        return False, 0.0, None, None, None


def _note(module, refus, points):
    with _verrou:
        s = _stats.setdefault(module, {"ecrits": 0, "refus": 0, "points": 0.0})
        s["ecrits"] += 1
        if refus:
            s["refus"] += 1
            if points != float("inf"):
                s["points"] += points
        _depuis[0] += 1
        rapport = _depuis[0] >= SEUIL_RAPPORT
        if rapport:
            _depuis[0] = 0
            copie = dict((k, dict(v)) for k, v in _stats.items())
    if rapport:
        _dire("warning", "  [SL-CLIQUET] %s", synthese(copie))


def synthese(stats=None):
    s = stats if stats is not None else _stats
    if not s:
        return "aucune ecriture de stop"
    bouts = []
    for m in sorted(s, key=lambda k: -s[k]["ecrits"]):
        v = s[m]
        if v["refus"]:
            bouts.append("%s=%d(%d refus, %.1f pts)"
                         % (m, v["ecrits"], v["refus"], v["points"]))
        else:
            bouts.append("%s=%d" % (m, v["ecrits"]))
    return " | ".join(bouts) + (" | %d tickets en memoire" % len(_memoire))


def stats():
    with _verrou:
        return dict((k, dict(v)) for k, v in _stats.items())


# ------------------------------------------------------------ l enveloppe

def _fabrique(origine):
    """Une NOUVELLE enveloppe a chaque pose.

    Indispensable : si on reutilisait le meme objet, une enveloppe posee
    par-dessus la notre et capturee comme nouvelle origine nous ferait
    nous appeler nous-memes, donc boucler. Chaque pose cree un objet
    distinct, marque, et la chaine reste finie.
    """
    def envelope(req, *a, **k):
        try:
            refus, points, tk, neuf, best = _juge(req)
            mod, fn = _appelant()
            _note(mod, refus, points)
            if refus:
                bloque = BLOQUE and mod not in EXEMPTS
                _dire("warning",
                      "  [SL-CLIQUET] %s.%s ticket %s  %.2f -> %s  RECUL %s%s",
                      mod, fn, tk, best,
                      ("EFFACEMENT" if not neuf else "%.2f" % neuf),
                      ("infini" if points == float("inf")
                       else "%.1f pts" % points),
                      " REFUSE" if bloque else " (observe)")
                if bloque:
                    _sale[0] = True
                    return None
        except Exception:
            pass                        # un arbitre en panne laisse jouer
        return origine(req, *a, **k)
    envelope._sl_cliquet = VERSION
    return envelope


def _arme(pourquoi):
    """Pose l enveloppe au-dessus de ce qui est en place. Renvoie True si pose."""
    global _origine
    courant = getattr(_mt5, "order_send", None)
    if courant is None:
        return False
    if getattr(courant, "_sl_cliquet", None) == VERSION:
        return False                    # deja en tete, rien a faire
    _origine = courant
    neuve = _fabrique(courant)
    _mt5.order_send = neuve
    _enveloppe[0] = neuve
    _dire("warning", "  [SL-CLIQUET] v%s pose sur mt5.order_send -- %s -- mode %s",
          VERSION, pourquoi, "BLOQUE" if BLOQUE else "OBSERVATION")
    return True


def _veille():
    dernier_ecrit = 0.0
    while True:
        try:
            time.sleep(VEILLE_SEC)
            _arme("repose apres decrochage")
            maintenant = time.time()
            if _sale[0] or maintenant - dernier_ecrit > 60:
                _oublie_les_vieux()
                _ecrit()
                _sale[0] = False
                dernier_ecrit = maintenant
        except Exception:
            continue                    # la veille ne meurt jamais


def install(mt5_module, log=None):
    """A appeler dans CHAQUE processus qui ecrit des stops. Idempotent."""
    global _mt5, _log
    if _pose[0]:
        return False
    _mt5, _log = mt5_module, log
    n = _charge()
    _arme("pose initiale")
    _pose[0] = True
    if _fil[0] is None:
        f = threading.Thread(target=_veille, name="sl_cliquet", daemon=True)
        f.start()
        _fil[0] = f
    _dire("warning", "  [SL-CLIQUET] memoire : %d ticket(s) relus, veille %d s",
          n, VEILLE_SEC)
    return True
