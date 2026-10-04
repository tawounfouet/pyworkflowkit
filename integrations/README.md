# PyWorkflowKit Integrations & Conformance Suites

Ce répertoire regroupe les suites de test, bancs d'essai de plugins et gabarits de développement de l'écosystème PyWorkflowKit.

Ces paquets sont des **fixtures de qualification indépendantes** (chacune possédant son propre fichier `pyproject.toml`) isolées du code source du package central `pyworkflowkit` :

- **`ecosystem-template/`** : Gabarit de référence officiel démontrant l'implémentation d'un plugin tiers autonome utilisant exclusivement la façade publique `pyworkflowkit.ecosystem`.
- **`qualification-integrations/`** : Paquets de test transversaux vérifiant la tolérance aux pannes (`broken-optional`) et l'extension d'exécuteur tiers (`reference-executor`).
- **`reference-integrations/`** : Distributions de référence (`reference-workload`, `reference-event-sink`, `reference-metadata`, `reference-pyingestkit`) vérifiant la découverte dynamique par points d'entrée Python (`importlib.metadata`).
- **`typing-fixtures/`** : Fixtures de vérification statique stricte par Mypy validant la signature des consommateurs publics.

> **Note de distribution** : L'ensemble de ce répertoire `integrations/` est formellement exclu des archives distribuables sur PyPI (`wheel` et `sdist`).
