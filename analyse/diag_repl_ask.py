# -*- coding: utf-8 -*-
"""
diag_repl_ask.py -- obtenir la trace que le serveur avale

  python diag_repl_ask.py

LE PROBLEME
    Le REPL rend "[erreur] repl ask error: I/O operation on closed file".
    Le handler, price_action.py ligne 18490, attrape l exception et n en
    garde que le texte :

        except Exception as _rwe:
            out = {"ok": False, "error": f"repl ask error: {_rwe}"}

    Pas de trace, donc pas de ligne coupable. On a deja elimine mon
    print de _ctx_repl (v2 le protege), et repl_web ne detourne pas
    sys.stdout. Il faut voir la pile.

CE QUE FAIT CE SCRIPT
    Il appelle repl_web.ask() exactement comme le serveur -- meme
    argv[0], donc meme cle DeepSeek -- avec sys.stdout FERME, ce qui est
    l etat ou l erreur se produit. Puis il imprime la trace complete sur
    la sortie d ERREUR, qui, elle, reste ouverte.

    Deux passes :
      1. sortie ouverte  -- la question doit reussir
      2. sortie fermee   -- si elle echoue, la trace nomme la ligne

    Si la passe 1 echoue aussi, ce n est pas une histoire de stdout du
    tout, et la trace le dira quand meme.

AUCUNE ECRITURE. Aucun ordre. Un appel API DeepSeek par passe.
"""
import io
import os
import sys
import traceback


def essai(nom, fermer):
    sys.stderr.write("\n=== %s ===\n" % nom)
    vrai = sys.stdout
    if fermer:
        # On ne ferme pas le vrai stdout : on le remplace par un flux
        # deja ferme. Meme symptome, sans casser la console apres coup.
        mort = io.StringIO()
        mort.close()
        sys.stdout = mort
    try:
        import repl_web as rw
        out = rw.ask("Reponds juste OK.")
        sys.stdout = vrai
        sys.stderr.write("REUSSI. type=%s\n" % type(out).__name__)
        sys.stderr.write("%s\n" % repr(out)[:400])
    except Exception:
        sys.stdout = vrai
        sys.stderr.write("ECHEC -- trace complete :\n")
        traceback.print_exc(file=sys.stderr)
    finally:
        sys.stdout = vrai


def main():
    # Meme identite que le serveur 8095 : sans ca, council_shadow ne
    # charge pas la cle et on diagnostiquerait autre chose.
    sys.argv[0] = "price_action.py"
    _cwd = os.getcwd()
    if _cwd not in sys.path:
        sys.path.insert(0, _cwd)

    sys.stderr.write("dossier : %s\n" % _cwd)
    essai("passe 1 : sortie OUVERTE", False)
    essai("passe 2 : sortie FERMEE (comme le serveur)", True)
    sys.stderr.write("\nColle tout ce qui precede.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
