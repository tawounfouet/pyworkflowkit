# Plan d'Implémentation : LOT-32 — Ergonomie d'Authoring & Validation Statique

- **Statut** : Plan d'implémentation opérationnel
- **Milestone** : LOT-32
- **Phase** : Phase 2 (Ergonomie & Moteur Runtime V2)
- **Dépendance amont** : Phase 1 (LOT-31)
- **Branche de travail cible** : `feat/v2-lot32-authoring-ergonomics`

---

## 1. Objectifs & Périmètre du Lot

Le but de **LOT-32** est de transformer l'ergonomie d'écriture des workflows dans `pyworkflowkit.authoring` :
1. **Opérateurs de flux déclaratifs (`>>`)** : Permettre d'enchaîner des tâches avec l'opérateur naturel de décalage à droite (`task_a >> task_b >> [task_c, task_d]`).
2. **Détection de Cycle Immédiate** : Vérifier l'acyclicité du graphe dès l'invocation de l'opérateur ou de `.add_task()`, en levant une `CircularDependencyError` explicite avant toute compilation ou exécution.
3. **Typage Statique Générique** : Supporter `TaskDefinition[T_Input, T_Output]` pour garantir la cohérence des types d'entrées/sorties via `mypy`.
4. **Composition de Sous-Graphes** : Permettre d'intégrer une `WorkflowDefinition` comme sous-tâche composite au sein d'un workflow parent.

---

## 2. Fichiers à Modifier et Créer

```text
src/pyworkflowkit/authoring/
├── definitions.py              # Ajout de __rshift__ et __rrshift__ sur TaskDefinition
├── builders.py                 # Support du chaînage fluide dans WorkflowBuilder
└── validation.py               # Algorithme de détection de cycles incrémental (DFS/Tarjan)

tests/unit/authoring/
├── test_v2_flow_operators.py           # Tests du chaînage individuel et en listes
├── test_v2_instant_cycle_detection.py  # Tests de levée immédiate de CircularDependencyError
└── test_v2_generic_task_typing.py      # Validation du typage strict mypy

tests/property/
└── test_v2_authoring_properties.py     # Tests Hypothesis sur graphes aléatoires
```

---

## 3. Détail des Spécifications Techniques

### 3.1 Opérateur `>>` sur `TaskDefinition`
```python
def __rshift__(
    self,
    other: TaskDefinition | Sequence[TaskDefinition],
) -> TaskDefinition | Sequence[TaskDefinition]:
    """Déclare que 'other' dépend de 'self' (self >> other)."""
    ...
```
* Supporte :
  - `task_a >> task_b`
  - `task_a >> [task_b, task_c]` (fan-out)
  - `[task_a, task_b] >> task_c` (fan-in)
  - `task_a >> task_b >> task_c` (chaînage continu)

### 3.2 Détection de Cycles Incrémentale
* Chaque ajout de dépendance $A \rightarrow B$ vérifie s'il existe déjà un chemin orienté de $B$ vers $A$.
* Si un chemin existe, une `CircularDependencyError` est immédiatement levée avec le détail du chemin de cycle :
  `CircularDependencyError: Cycle detected: task_c -> task_a -> task_b -> task_c`.

---

## 4. Stratégie de Test

* **Tests Unitaires** : Couvrir toutes les combinaisons d'opérateurs (unitaire vers unitaire, unitaire vers liste, liste vers unitaire, liste vers liste).
* **Tests de Propriétés (Hypothesis)** : Générer des DAGs aléatoires avec jusqu'à 50 nœuds pour prouver mathématiquement qu'aucun faux positif ou cycle non détecté n'est possible.
* **Test de Non-Régression** : Vérifier que l'ancienne syntaxe explicite `.add_task(..., depends_on=...)` fonctionne toujours à 100% à l'identique.

---

## 5. Critères d'Acceptation (Definition of Done)

- [ ] L'opérateur `>>` fonctionne sur tâches uniques et séquences de tâches.
- [ ] La détection de cycle est immédiate à la construction du graphe.
- [ ] Les tests de propriétés Hypothesis passent avec 1 000 exemples aléatoires.
- [ ] L'invariance de la racine 2.0 est préservée.
- [ ] `ruff` et `mypy --strict` sont à 0 défaut.
