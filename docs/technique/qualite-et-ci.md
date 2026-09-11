# Qualité et intégration continue

## Commandes locales

```bash
uv sync --all-groups                      # dépendances de développement comprises

uv run ruff format                        # formatage
uv run ruff check                         # lint, docstrings numpy, règles de sécurité
uv run mypy                               # typage strict (src et tests)

uv run pytest --cov                       # tests + couverture (échec sous 80 %)
uv run pytest -m "not integration"        # tests unitaires seuls, sans serveur Temporal

uv export --all-groups --no-emit-project -o requirements-audit.txt
uv run pip-audit --disable-pip -r requirements-audit.txt   # dépendances vulnérables
uv run bandit -c pyproject.toml -r src    # analyse statique de sécurité
```

## Organisation des tests

| Dossier | Portée | Dépendances |
|---|---|---|
| `tests/unit/` | Domaine, adaptateurs (HTTP et SMTP simulés), activités (`ActivityEnvironment`), CLI, configuration, état du workflow | Aucune |
| `tests/integration/` | Workflow complet : arrêt au premier créneau, budget de vérifications, mode continu, `continue-as-new`, panne transitoire, erreur de configuration, signaux et requête | Serveur de test Temporal |

Par défaut, les tests d'intégration utilisent le serveur de test Temporal à **saut de temps**, téléchargé au premier lancement : les intervalles d'attente s'écoulent instantanément. S'il n'est pas disponible sur la plateforme, pointez-les vers un serveur existant, les attentes durant alors réellement (quelques minutes au total) :

```bash
RENDEZ_VITE_TEST_TEMPORAL_ADDRESS=localhost:7233 uv run pytest -m integration
```

Hors CI, ces tests sont ignorés si aucun serveur n'est joignable. En CI (`CI=true`), cette situation fait échouer le job.

## Conventions

- **Docstrings** au format numpy, en anglais, pour toutes les fonctions. Le format est vérifié par les règles `D` de ruff (`convention = "numpy"`).
- **Typage** strict avec mypy.
- **Couverture** minimale de 80 % en branches, configurée dans `pyproject.toml` (`fail_under`).
- **Formatage** ruff, lignes de 100 caractères.

## Pipeline GitHub Actions

Workflow [`ci.yml`](../../.github/workflows/ci.yml), déclenché sur push vers `main`, sur pull request, chaque lundi et à la demande :

| Job | Vérifications |
|---|---|
| `quality` | `uv.lock` à jour (`uv sync --locked`), formatage, lint et docstrings, typage |
| `tests` | Tests unitaires et d'intégration sur Python 3.11, 3.12 et 3.13, seuil de couverture à 80 %, résumé de couverture dans le récapitulatif du job, rapports `coverage.xml` et `junit.xml` en artefacts |
| `security` | Vulnérabilités connues des dépendances verrouillées (pip-audit), analyse statique (bandit) |
| `docker` | Lint du Dockerfile (hadolint), build de l'image, test de fumée, scan des vulnérabilités de l'image (Trivy, `CRITICAL`/`HIGH` corrigibles) |

S'y ajoutent :

- [`codeql.yml`](../../.github/workflows/codeql.yml) : analyse CodeQL (`security-and-quality`). Pour un dépôt privé, GitHub Advanced Security est nécessaire.
- [`dependabot.yml`](../../.github/dependabot.yml) : mises à jour hebdomadaires des dépendances Python (uv), des actions GitHub et de l'image de base Docker.

L'exécution hebdomadaire détecte les vulnérabilités publiées depuis le dernier push.
