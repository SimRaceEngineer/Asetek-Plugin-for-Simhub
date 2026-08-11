# -*- coding: utf-8 -*-
"""
sl_arbitre.py -- un seul point de passage pour toutes les ecritures de stop

LE PROBLEME QU IL REGLE
    trading_engine.py demarre environ deux cents modules en threads dans un
    seul processus. Une trentaine d entre eux ecrivent des stops sur les
    memes positions : be_supergate, auto_be_after_mfe, universal_zone_protect,
    fbt_asset_protect, vix_phase_trail, capitulation_lock_half,
    mfe_ticket_trail, us30_trail, candle_trail, zone_touch_observe,
    structural_sl_enforcer, ms_trailing, dev_close_protection, daily_watchdog,
    preopen_protect, losing_magic_zone_tp, sar_anchor_m5,
    deep_position_protector...

    Aucun ne consulte les autres. Dernier ecrivain gagne. Le 10/08 a 15:27,
    trois stops deja verrouilles en profit ont ete ramenes au prix d entree :
    61,0 / 22,6 / 22,1 points rendus.

    On peut poser une garde dans chacun -- on l a fait pour preopen_protect.
    Mais a trente ecrivains, et avec ceux qu on n a pas encore identifies,
    cela ne tient pas. Il faut un point de passage unique.

COMMENT
    Tous ces modules font "import MetaTrader5 as mt5" puis "mt5.order_send(req)".
    Python met le module en cache : ils partagent donc TOUS le meme objet. On
    remplace mt5.order_send une seule fois, au demarrage du moteur, et les
    trente passent par la garde sans qu on touche a un seul de leurs fichiers.

    Les alias -- import MetaTrader5 as _mt5raw, as _mt5raw251, etc. -- sont
    le meme objet, donc couverts aussi. Un module qui ferait "from MetaTrader5
    import order_send" y echapperait ; aucun ne le fait dans ce depot, mais
    c est la limite a connaitre.

LA REGLE, ET ELLE EST UNIQUE
    Un stop ne recule jamais. Pour un achat il ne descend pas, pour une vente
    il ne monte pas. Rien d autre n est arbitre : ni les ouvertures, ni les
    fermetures, ni les TP, ni les volumes.

FAIL-OPEN, PARTOUT
    Action autre que SLTP, champ manquant, position introuvable, exception,
    stop pas encore pose : la requete passe. Cette garde ne sait faire qu une
    chose, refuser un recul avere, et elle ne doit JAMAIS empecher la pose
    d un premier stop ni bloquer sur une erreur transitoire. Un arbitre qui
    tombe en panne doit laisser jouer.

MODE OBSERVATION PAR DEFAUT
    BLOQUE = False : on journalise et on laisse passer. Une journee de mesure
    dira qui recule, combien de fois, de combien de points. On ne bloque
    qu ensuite. Meme discipline que les gels : mesurer avant de trancher.

EXEMPTIONS
    EXEMPTS accepte des noms de modules autorises a reculer un stop. Vide par
    defaut, et il faut une bonne raison pour y toucher : un module qui
    ELARGIT un stop augmente le risque de la position, ce qui demande un
    argument, pas une habitude.
"""
import threading

VERSION = "1.0"

# ---------------------------------------------------------------- reglages
BLOQUE = False          # False = observe et laisse passer. True = refuse.
EXEMPTS = set()         # noms de modules autorises a reculer un stop
SEUIL_RAPPORT = 200     # une synthese toutes les N ecritures de stop

# ------------------------------------------------------------------- etat
_verrou = threading.Lock()
_stats = {}             # module -> {"ecrits", "reculs", "points"}
_depuis = [0]
_mt5 = None
_origine = None
_log = None
_pose = [False]


def _dire(niveau, msg, *a):
    if _log is not None:
        getattr(_log, niveau)(msg, *a)
    else:
        try:
            print(msg % a if a else msg, flush=True)
        except Exception:
            pass


def _appelant():
    """(module, fonction) du code qui a demande l ecriture.

    Le nom du MODULE compte plus que celui de la fonction : c est lui qui
    identifie l ecrivain parmi la trentaine. On remonte les cadres jusqu au
    premier qui ne soit pas ce fichier-ci.
    """
    try:
        import sys as _s
        n = 1
        while n < 12:
            f = _s._getframe(n)
            mod = f.f_globals.get("__name__", "?")
            if mod != __name__:
                return mod, f.f_code.co_name
            n += 1
    except Exception:
        pass
    return "?", "?"


def _note(module, recule, points):
    with _verrou:
        s = _stats.setdefault(module, {"ecrits": 0, "reculs": 0, "points": 0.0})
        s["ecrits"] += 1
        if recule:
            s["reculs"] += 1
            s["points"] += points
        _depuis[0] += 1
        rapport = _depuis[0] >= SEUIL_RAPPORT
        if rapport:
            _depuis[0] = 0
            copie = dict((k, dict(v)) for k, v in _stats.items())
    if rapport:
        _dire("warning", "  [SL-ARBITRE] %s", synthese(copie))


def synthese(stats=None):
    """Une ligne lisible : qui ecrit, qui recule, combien de points."""
    s = stats if stats is not None else _stats
    if not s:
        return "aucune ecriture de stop"
    bouts = []
    for m in sorted(s, key=lambda k: -s[k]["ecrits"]):
        v = s[m]
        if v["reculs"]:
            bouts.append("%s=%d(%d reculs, %.1f pts)"
                         % (m, v["ecrits"], v["reculs"], v["points"]))
        else:
            bouts.append("%s=%d" % (m, v["ecrits"]))
    return " · ".join(bouts)


def stats():
    """Copie des compteurs, pour un panel ou un rapport."""
    with _verrou:
        return dict((k, dict(v)) for k, v in _stats.items())


def _recule(req):
    """(recule, points, position) -- (False, 0, None) si on ne sait pas.

    Toute incertitude renvoie False : on ne refuse que ce qui est avere.
    """
    try:
        if not isinstance(req, dict):
            return False, 0.0, None
        if req.get("action") != _mt5.TRADE_ACTION_SLTP:
            return False, 0.0, None
        tk = req.get("position")
        neuf = req.get("sl")
        if tk is None or not neuf:
            return False, 0.0, None
        pos = _mt5.positions_get(ticket=tk)
        if not pos:
            return False, 0.0, None
        p = pos[0]
        if not p.sl:                       # pas encore de stop : on pose
            return False, 0.0, p
        neuf = float(neuf)
        if p.type == _mt5.POSITION_TYPE_BUY:
            return (neuf < p.sl), (p.sl - neuf), p
        return (neuf > p.sl), (neuf - p.sl), p
    except Exception:
        return False, 0.0, None


def _enveloppe(req, *a, **k):
    try:
        recule, points, p = _recule(req)
        mod, fn = _appelant()
        _note(mod, recule, points)
        if recule:
            _dire("warning",
                  "  [SL-ARBITRE] %s.%s ticket %s %s %.2f -> %.2f RECUL %.1f pts%s",
                  mod, fn, req.get("position"),
                  "BUY" if p.type == _mt5.POSITION_TYPE_BUY else "SELL",
                  p.sl, float(req.get("sl")), points,
                  " REFUSE" if (BLOQUE and mod not in EXEMPTS) else " (observe)")
            if BLOQUE and mod not in EXEMPTS:
                return None
    except Exception:
        pass                                # un arbitre en panne laisse jouer
    return _origine(req, *a, **k)


def install(mt5_module, log=None):
    """Remplace mt5.order_send. A appeler UNE fois, avant tout module.

    Idempotent : un second appel ne fait rien, ce qui evite d empiler des
    enveloppes si le moteur redemarre un sous-ensemble de ses modules.
    """
    global _mt5, _origine, _log
    if _pose[0]:
        return False
    _mt5, _log = mt5_module, log
    _origine = mt5_module.order_send
    mt5_module.order_send = _enveloppe
    _pose[0] = True
    _dire("warning",
          "  [SL-ARBITRE] v%s pose sur mt5.order_send -- mode %s",
          VERSION, "BLOQUE" if BLOQUE else "OBSERVATION")
    return True


def retirer():
    """Remet mt5.order_send d origine. Pour les tests, ou en cas de doute."""
    global _pose
    if _pose[0] and _mt5 is not None and _origine is not None:
        _mt5.order_send = _origine
        _pose[0] = False
        return True
    return False
