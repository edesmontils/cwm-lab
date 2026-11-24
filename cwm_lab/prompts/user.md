Génère une base de connaissances N3 (Turtle) d'environ ${n_facts} faits et d'environ ${n_entities} entités — PAS PLUS.

## CONTRAINTES STRICTES

1. **DONNÉES SEULES** : aucun énoncé de règle — pas de `log:implies`, pas de `@forAll`, pas de variables `?x`.
2. **Syntaxe N3/Turtle valide** : chaque triple se termine par un point ; les préfixes sont déclarés en tête de document.
3. Chaque entité (ressource) porte au moins un `rdf:type` (« a :Classe »).
4. **Valeurs réalistes** : prénoms d'usage, âges et dates plausibles, quantités numériques cohérentes avec le domaine.
5. **Taille STRICTE** : au plus ${max_facts} faits et au plus ${max_entities} entités — un document plus volumineux est automatiquement rejeté ; arrête-toi dès la limite atteinte, sans résumé ni commentaire superflu.
${rules_constraint}
${json_constraint}
${domaine_block}
${regles_block}
${generic_domain}
${feedback_block}