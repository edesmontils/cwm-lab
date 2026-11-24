"""P6 — worker de raisonnement (subprocess tuable).

Ce module n'est **pas** du code du TP : il est exécuté en
subprocess par :func:`cwm_lab.engine._run_closure` (``python -m
cwm_lab._reason_worker``) pour calculer la clôture (ou la preuve)
dans un processus qu'on peut **tuer** au timeout. Avant P6, la
clôture tournait dans un thread démon abandonné qui continuait de
consommer CPU/mémoire après le timeout (vecteur de DoS sur un
serveur partagé — risque #8 ROADMAP).

Protocole : paramètres en JSON sur **stdin**, résultat en JSON sur
la dernière ligne de **stdout** marquée ``CWM_TP_RESULT: `` (le
moteur CWM peut imprimer d'autres choses — « loaded from file »
& co). Code de sortie : 0 = résultat présent ; 1 = erreur interne
(message sur stderr).
"""

import json
import sys


def main():
    try:
        params = json.loads(sys.stdin.read())
    except ValueError:
        params = None
    if not isinstance(params, dict):
        sys.stderr.write("worker : paramètres JSON invalides\n")
        return 1
    # import différé : le moteur CWM est lourd (le worker n'existe
    # que pour lui)
    from cwm_lab import engine
    try:
        result = engine._closure_result(
            params.get("op", "closure"),
            params.get("kb", ""), params.get("rules", ""),
            base_uri=params.get("base_uri") or engine.DEFAULT_BASE_URI,
            mode=params.get("mode", "think"),
            store_rules=bool(params.get("store_rules", False)),
            lang=params.get("lang", "fr"),
        )
    except Exception as e:  # le worker doit toujours terminer proprement
        sys.stderr.write("worker : %s: %s\n" % (type(e).__name__, e))
        return 1
    sys.stdout.write("CWM_TP_RESULT: "
                     + json.dumps(result, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
