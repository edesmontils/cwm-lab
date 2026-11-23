# Makefile — CWM Lab (cwm-lab) — outil de TP Web sémantique sur CWM 2.0

.PHONY: test serve

# Tests unitaires (110) — CWM 2.0 doit être installé (pip install cwm,
# ou voir README.md « Lancement » avant la première publication PyPI).
test:
	@python3 -m unittest discover -s tests -t . -v

# Serveur local → http://127.0.0.1:8000
serve:
	python3 -m cwm_lab.server
