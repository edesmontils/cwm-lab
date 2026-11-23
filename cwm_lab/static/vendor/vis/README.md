# vis-network — bundle local (P5, option « visualisation du graphe »)

Ce dossier contient le bundle **vis-network** (+ **vis-data**, sa
dépendance) utilisé par l'outil TP (`lab/lab_web/static/app.js`) pour
la visualisation du graphe des triples, **vendu en local** : pas de
CDN, aucune dépendance réseau au moment de l'exécution (même décision
que le bundle CodeMirror, voir `../codemirror/README.md`).

- `vis-data.min.js` — UMD (build `peer/umd` du paquet npm) ; expose
  `vis.DataSet` (et `vis.data`) ;
- `vis-network.min.js` — UMD (build `dist` du paquet npm) ; expose
  `vis.Network` (et `vis.network`) ;
- `LICENSE.md` — licence **MIT** (les deux paquets sont dual
  `Apache-2.0 OR MIT` ; la MIT est celle retenue ici).

Chargés par deux balises `<script>` classiques (UMD) : le premier
définit l'objet global `vis`, le second l'étend.

## Provenance

Fichiers **tels que distribués** par le registre npm (aucun build
local, contrairement à CodeMirror) :

| Paquet | Version | Fichier source |
|---|---|---|
| `vis-data` | 7.1.9 | `https://cdn.jsdelivr.net/npm/vis-data@7.1.9/peer/umd/vis-data.min.js` |
| `vis-network` | 10.1.5 | `https://cdn.jsdelivr.net/npm/vis-network@10.1.5/dist/vis-network.min.js` |

Téléchargés le 2026-11-22. Pour régénérer :

```sh
curl -sfL https://cdn.jsdelivr.net/npm/vis-data@7.1.9/peer/umd/vis-data.min.js -o vis-data.min.js
curl -sfL https://cdn.jsdelivr.net/npm/vis-network@10.1.5/dist/vis-network.min.js -o vis-network.min.js
```
