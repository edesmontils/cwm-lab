"""cache — cache à deux niveaux (mémoire + disque) des traitements (P8).

En TP, le même traitement (parse, raisonnement, requête, preuve,
vérification de preuve, graphe, sérialisation) est très
probablement demandé plusieurs fois : le cache évite de le
refaire — la seconde occurrence est quasi instantanée et le
processeur est déchargé.

Deux niveaux :

- **mémoire** (processus) : hot path, LRU borné en nombre
  d'entrées, TTL court ;
- **disque** (persisté) : un fichier JSON par clé, survit aux
  redémarrages du serveur — le gain se cumule sur plusieurs
  séances de TP. Borné en taille totale (évacuation du plus
  ancien), TTL long.

Le cache est une **optimisation, pas un état** : le serveur
reste stateless (chaque requête reconstruit son store) ; seule
la réponse JSON déjà calculée est mémorisée. Clé = SHA-256 de
l'endpoint + du payload complet : la moindre variation du texte
force le recalcul. Seuls les résultats **complets et réussis**
sont cachés (jamais un timeout partiel, jamais une erreur).
Thread-safe (le serveur est ``ThreadingHTTPServer``) : un
``threading.Lock`` unique, écritures disque atomiques
(``tmp`` + ``os.replace``).

Configuration (tous les fichiers **facultatifs** — absents, les
valeurs par défaut s'appliquent, l'appli démarre sans config) :

- ``config.yaml`` (chmod 600) — paramètres non sensibles :
  ``ttl_disk``, ``ttl_memory``, ``max_disk_mb``,
  ``memory_entries``. Format YAML plat (``cle: valeur``, un
  niveau), parseable en stdlib ;
- ``.env`` (ignoré par git, chmod 600) — données sensibles /
  locales : ``CACHE_DIR`` (défaut ``~/.cache/lab_tp``) et, pour
  la P9, ``IA_URL`` / ``IA_MODEL`` / ``IA_API_KEY`` ;
- ``config.yaml``, pour la P9 — plafonds de quota de séance de
  l'IA : ``ia_max_requests``, ``ia_max_tokens``,
  ``ia_max_attempts``, ``ia_timeout``, ``ia_max_tokens_response``.
"""

# Copyright 2026 CWM 2.0 maintainers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import hashlib
import json
import os
import threading
import time

#: Valeurs par défaut (appliquées si les fichiers de config sont
#: absents — l'appli démarre sans config).
DEFAULTS = {
    "cache_dir": os.path.join(os.path.expanduser("~"), ".cache", "lab_tp"),
    "ttl_memory": 300.0,        # 5 min
    "ttl_disk": 7 * 86400.0,    # 7 jours
    "max_disk_bytes": 200 * 1024 * 1024,  # 200 Mo
    "memory_entries": 64,
    # P9 — IA générative (voir ia.py)
    "ia_provider": "",              # ex. "proxyiag" (URL par défaut)
    "ia_url": "https://pedago.desmontils.net/proxyiag/v1",
    "ia_model": "",
    "ia_api_key": "",
    "ia_max_requests": 30,          # requêtes par jour (séance)
    "ia_max_tokens": 100000,        # tokens par jour (séance)
    "ia_max_attempts": 3,           # régénération bornée
    "ia_timeout": 120.0,            # appel proxy (secondes)
    "ia_max_tokens_response": 4000,  # max_tokens demandé au modèle
}

#: URL par défaut par provider (API compatible OpenAI) — ``IA_URL``
#: dans ``.env`` prime toujours.
_PROVIDER_DEFAULT_URLS = {
    "proxyiag": "https://pedago.desmontils.net/proxyiag/v1",
    "openai": "https://api.openai.com/v1",
}


# ----------------------------------------------------------------------
# parseurs de config (stdlib, un niveau)
# ----------------------------------------------------------------------

def parse_flat_yaml(text):
    """Parse un YAML **plat** (``cle: valeur``, un niveau).

    Lignes vides et commentaires (``#``) ignorés. Renvoie un
    dictionnaire de chaînes (la conversion de type est faite par
    :func:`load_config`).
    """
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def parse_flat_env(text):
    """Parse un ``.env`` (``CLE=value``, un niveau).

    Lignes vides et commentaires (``#``) ignorés.
    """
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _parse_duration(value, default):
    """``"7d"`` / ``"12h"`` / ``"30m"`` / ``"45"`` → secondes."""
    if value is None:
        return default
    s = str(value).strip().lower()
    if not s:
        return default
    units = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}
    try:
        if s[-1] in units:
            return float(s[:-1]) * units[s[-1]]
        return float(s)
    except ValueError:
        return default


def load_config(base_dir=None):
    """Charge la configuration (``config.yaml`` + ``.env``) et applique
    les valeurs par défaut (:data:`DEFAULTS`).

    ``base_dir`` est le dossier contenant les fichiers de config
    (défaut : le dossier du paquet ``cwm_lab``). Un fichier
    absent, illisible ou mal formé ne bloque pas le démarrage :
    les valeurs par défaut (ou les autres fichiers) s'appliquent.
    """
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg = dict(DEFAULTS)
    # config.yaml — paramètres non sensibles
    try:
        with open(os.path.join(base_dir, "config.yaml"), encoding="utf-8") as f:
            flat = parse_flat_yaml(f.read())
    except OSError:
        flat = {}
    if "ttl_disk" in flat:
        cfg["ttl_disk"] = _parse_duration(flat["ttl_disk"], cfg["ttl_disk"])
    if "ttl_memory" in flat:
        cfg["ttl_memory"] = _parse_duration(flat["ttl_memory"], cfg["ttl_memory"])
    try:
        if "max_disk_mb" in flat:
            cfg["max_disk_bytes"] = int(float(flat["max_disk_mb"])) * 1024 * 1024
        if "memory_entries" in flat:
            cfg["memory_entries"] = int(flat["memory_entries"])
        # P9 — plafonds de quota de séance de l'IA
        if "ia_max_requests" in flat:
            cfg["ia_max_requests"] = max(1, int(flat["ia_max_requests"]))
        if "ia_max_tokens" in flat:
            cfg["ia_max_tokens"] = max(1, int(flat["ia_max_tokens"]))
        if "ia_max_attempts" in flat:
            cfg["ia_max_attempts"] = max(1, int(flat["ia_max_attempts"]))
        if "ia_timeout" in flat:
            cfg["ia_timeout"] = max(1.0, float(flat["ia_timeout"]))
        if "ia_max_tokens_response" in flat:
            cfg["ia_max_tokens_response"] = max(
                200, int(flat["ia_max_tokens_response"]))
    except ValueError:
        pass
    # .env — données sensibles / locales
    try:
        with open(os.path.join(base_dir, ".env"), encoding="utf-8") as f:
            env = parse_flat_env(f.read())
    except OSError:
        env = {}
    if env.get("CACHE_DIR"):
        cfg["cache_dir"] = os.path.expanduser(env["CACHE_DIR"])
    for key in ("ia_provider", "ia_model", "ia_api_key"):
        env_key = "IA_" + key.split("_", 1)[1].upper()
        if env.get(env_key):
            cfg[key] = env[env_key]
    # P9 — URL du proxy : IA_URL prime ; sinon l'URL par défaut du
    # provider (IA_PROVIDER) ; sinon la valeur par défaut (proxyiag).
    if env.get("IA_URL"):
        cfg["ia_url"] = env["IA_URL"].rstrip("/")
    elif cfg["ia_provider"] in _PROVIDER_DEFAULT_URLS:
        cfg["ia_url"] = _PROVIDER_DEFAULT_URLS[cfg["ia_provider"]]
    return cfg


# ----------------------------------------------------------------------
# cache
# ----------------------------------------------------------------------

def cachable(result):
    """Un résultat n'est mis en cache que s'il est **complet et réussi** :
    dictionnaire avec ``ok: true`` et sans ``timeout`` (jamais un
    timeout partiel, jamais une erreur).
    """
    return (isinstance(result, dict)
            and result.get("ok") is True
            and not result.get("timeout"))


class Cache:
    """Cache à deux niveaux (mémoire LRU + disque persisté), thread-safe.

    ``config`` est le dictionnaire de :func:`load_config` (ou équivalent
    manuel pour les tests). ``clock`` est injectable (tests de TTL).
    Si le répertoire disque n'est pas créable, le cache dégenère en
    mémoire uniquement (le TP ne bloque jamais).
    """

    def __init__(self, config, clock=time.time):
        self._lock = threading.Lock()
        self._clock = clock
        self._mem = {}          # clé → (expiration, données) ; insertion = LRU
        self._mem_order = []    # ordre d'insertion (défaut Python : dict)
        self._ttl_memory = float(config["ttl_memory"])
        self._ttl_disk = float(config["ttl_disk"])
        self._max_disk_bytes = int(config["max_disk_bytes"])
        self._memory_entries = max(1, int(config["memory_entries"]))
        self._disk_dir = None
        try:
            self._disk_dir = os.path.expanduser(config["cache_dir"])
            os.makedirs(self._disk_dir, exist_ok=True)
        except OSError:
            self._disk_dir = None

    @property
    def disk_dir(self):
        """Répertoire disque effectif (``None`` si mémoire uniquement)."""
        return self._disk_dir

    # ------------------------------------------------------------------
    # clé
    # ------------------------------------------------------------------
    @staticmethod
    def make_key(api, payload):
        """Clé = ``<api>/<sha256>`` où sha256 porte sur l'endpoint et le
        **payload complet** (JSON canonique, clés triées) : toute
        variation d'un caractère force le recalcul."""
        canon = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
        digest = hashlib.sha256((api + "\x00" + canon).encode("utf-8"))
        # plat (pas de « / ») : un fichier par clé dans le répertoire
        # du cache — l'évacuation par taille scanne un seul niveau
        return api + "-" + digest.hexdigest()

    # ------------------------------------------------------------------
    # mémoire
    # ------------------------------------------------------------------
    def _mem_get(self, key, now):
        item = self._mem.get(key)
        if item is None:
            return None
        expiry, data = item
        if expiry <= now:
            del self._mem[key]
            return None
        return data

    def _mem_put(self, key, data, now):
        if key not in self._mem:
            while len(self._mem) >= self._memory_entries:
                oldest = next(iter(self._mem))
                del self._mem[oldest]
        self._mem[key] = (now + self._ttl_memory, data)

    # ------------------------------------------------------------------
    # disque
    # ------------------------------------------------------------------
    def _disk_path(self, key):
        return os.path.join(self._disk_dir, key + ".json")

    def _disk_get(self, key, now):
        try:
            with open(self._disk_path(key), "rb") as f:
                obj = json.loads(f.read().decode("utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(obj, dict) or "data" not in obj:
            return None
        try:
            if now - float(obj.get("ts", 0)) > self._ttl_disk:
                os.unlink(self._disk_path(key))
                return None
        except OSError:
            return None
        return obj["data"]

    def _disk_put(self, key, data, now):
        body = json.dumps({"ts": now, "data": data},
                          ensure_ascii=False).encode("utf-8")
        path = self._disk_path(key)
        tmp = "%s.tmp%d" % (path, os.getpid())
        with open(tmp, "wb") as f:
            f.write(body)
        os.replace(tmp, path)  # atomique : pas de fichier à moitié écrit

    def _disk_evict(self):
        """Garde le disque sous ``max_disk_bytes`` : fichiers JSON du
        cache, du plus ancien au plus récent (mtime), tant que la
        taille totale dépasse la borne."""
        try:
            entries = []
            for name in os.listdir(self._disk_dir):
                if name.endswith(".json"):
                    p = os.path.join(self._disk_dir, name)
                    try:
                        st = os.stat(p)
                    except OSError:
                        continue
                    entries.append((st.st_mtime, st.st_size, p))
            total = sum(size for _, size, _ in entries)
            if total <= self._max_disk_bytes:
                return
            for _, size, path in sorted(entries):  # mtime croissant
                os.unlink(path)
                total -= size
                if total <= self._max_disk_bytes:
                    return
        except OSError:
            pass  # l'évacuation ne doit jamais bloquer le TP

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def get(self, key):
        """Renvoie les données cachées sous ``key`` (mémoire d'abord,
        puis disque — un hit disque est promu en mémoire) ou ``None``."""
        with self._lock:
            now = self._clock()
            data = self._mem_get(key, now)
            if data is not None:
                return data
            if self._disk_dir is None:
                return None
            data = self._disk_get(key, now)
            if data is not None:
                self._mem_put(key, data, now)
            return data

    def put(self, key, data):
        """Mémorise ``data`` sous ``key`` (mémoire + disque persisté)."""
        with self._lock:
            now = self._clock()
            self._mem_put(key, data, now)
            if self._disk_dir is not None:
                self._disk_put(key, data, now)
                self._disk_evict()
