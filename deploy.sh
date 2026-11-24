#!/usr/bin/env bash
# Déploie CWM Lab sur le Pi : pousse main vers GitHub, puis git pull sur le Pi,
# réinstalle le paquet (dépendances) et redémarre le service systemd.
# Caddy expose le service (gunicorn, 127.0.0.1:8010) sur
# https://pedago.desmontils.net/cwmlab/ — son bloc de configuration est déjà en place.
#
# Cibles (variable TARGETS, « hôte:dossier » séparés par des espaces ; défaut : le Pi) :
#   ed@192.168.1.200:programmation/cwm-lab   (service systemd cwm-lab ; réseau local)
#   SKIP_TESTS=1  déploie sans lancer les tests automatisés (make test)
#   SERVICE=cwm-lab  nom du service systemd à redémarrer
set -euo pipefail

TARGETS="${TARGETS:-ed@192.168.1.200:programmation/cwm-lab}"
SERVICE="${SERVICE:-cwm-lab}"
cd "$(dirname "$0")"

if [ -n "$(git status --porcelain)" ]; then
  echo "Des modifications ne sont pas commitées : commitez avant de déployer." >&2
  exit 1
fi

if [ "${SKIP_TESTS:-0}" != 1 ]; then
  echo "Tests automatisés…"
  make test >/dev/null 2>&1 || { echo "Les tests échouent : déploiement annulé (SKIP_TESTS=1 pour passer outre)." >&2; exit 1; }
fi

git push origin main

# Chaque cible : « hôte:dossier » ; une cible injoignable n'empêche pas de mettre à jour les autres (le code est déjà sur GitHub).
fail=0
for t in $TARGETS; do
  host="${t%%:*}"; dir="${t#*:}"
  echo "→ $host ($dir)"
  if ssh -o BatchMode=yes -o ConnectTimeout=10 "$host" "
      set -e
      git -C $dir pull --ff-only
      $dir/.venv/bin/pip install -q -e $dir -r $dir/requirements-deploy.txt
      sudo -n systemctl restart $SERVICE
      sleep 3
      systemctl is-active $SERVICE
      curl -fsS http://127.0.0.1:8010/api/version; echo
      git -C $dir log --oneline -1"; then :; else echo "  ÉCHEC : $host injoignable ou mise à jour refusée." >&2; fail=1; fi
done
if [ "$fail" = 0 ]; then echo "Déployé : https://pedago.desmontils.net/cwmlab/"; else echo "Déploiement incomplet : relancez ./deploy.sh depuis un réseau qui joint la cible en échec." >&2; exit 1; fi
