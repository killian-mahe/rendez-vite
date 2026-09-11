# Installation et déploiement

## Prérequis

- Python 3.11, 3.12 ou 3.13
- [uv](https://docs.astral.sh/uv/) pour la gestion des dépendances
- Un serveur Temporal : la [CLI Temporal](https://docs.temporal.io/cli) (`temporal server start-dev`) en local, Temporal Cloud ou un cluster auto-hébergé en production
- Docker, optionnel

## Exécution native

```bash
# 1. Dépendances (environnement virtuel .venv créé par uv)
uv sync

# 2. Serveur Temporal de développement (interface web : http://localhost:8233)
temporal server start-dev

# 3. Worker, dans un autre terminal
uv run rendez-vite worker
#    ou, sans le script installé :
uv run python -m rendez_vite worker

# 4. Surveillance de démonstration : provider fictif, alerte dans les journaux du worker
uv run rendez-vite watch --practitioner dr-demo --reason consultation \
  --email moi@example.org --interval 1m --wait
```

Pour recevoir de vrais e-mails, copiez `.env.example` vers `.env`, renseignez la section SMTP, puis passez `--notifier smtp`.

## Docker

L'image est construite en deux étapes : les dépendances sont installées par uv dans l'étape de build, et l'image finale ne contient que l'environnement virtuel. Elle s'exécute avec un utilisateur non root.

```bash
docker build -t rendez-vite .

# Worker connecté à un Temporal accessible depuis le conteneur
docker run -d --name rendez-vite-worker --env-file .env \
  -e RENDEZ_VITE_TEMPORAL_ADDRESS=temporal.example.org:7233 \
  rendez-vite

# Les autres commandes utilisent la même image
docker run --rm --env-file .env rendez-vite components
```

## Docker Compose

`compose.yaml` démarre un serveur Temporal de développement et le worker :

```bash
docker compose up -d --build
docker compose run --rm worker watch --practitioner dr-demo --reason consultation \
  --email moi@example.org --interval 1m
docker compose logs -f worker
```

Le serveur de développement garde ses données **en mémoire**, et les surveillances sont perdues à son redémarrage. Pour une surveillance longue en auto-hébergement, persistez-le (`temporal server start-dev --db-filename /chemin/temporal.db`, avec un volume inscriptible) ou utilisez un vrai cluster.

## Production

- **Temporal Cloud** : `RENDEZ_VITE_TEMPORAL_ADDRESS=<namespace>.<compte>.tmprl.cloud:7233`, `RENDEZ_VITE_TEMPORAL_NAMESPACE=<namespace>.<compte>`, `RENDEZ_VITE_TEMPORAL_TLS=true` et `RENDEZ_VITE_TEMPORAL_API_KEY`.
- **Disponibilité** : lancez au moins un worker en permanence, avec redémarrage automatique. Plusieurs workers sur la même file se répartissent la charge.
- **Secrets** : injectez `SMTP_PASSWORD`, `BOOKING_API_TOKEN` et `TEMPORAL_API_KEY` via le gestionnaire de secrets de la plateforme, jamais dans l'image.
- **Supervision** : l'interface Temporal liste les surveillances, leurs vérifications et les échecs d'activités. La requête `status` expose la dernière erreur rencontrée.
- **Déploiement d'une nouvelle version** : voir les [contraintes de déterminisme](workflow-temporal.md#contraintes-de-déterminisme) avant de modifier les règles de filtrage.
