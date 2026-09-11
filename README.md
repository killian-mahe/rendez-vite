# Rendez-vite

[![CI](https://github.com/killian-mahe/rendez-vite/actions/workflows/ci.yml/badge.svg)](https://github.com/killian-mahe/rendez-vite/actions/workflows/ci.yml)

Surveille les créneaux disponibles d'un praticien et vous prévient par e-mail dès qu'un rendez-vous se libère.

## Principe

Obtenir un rendez-vous chez un spécialiste peut prendre des mois, alors que des créneaux se libèrent régulièrement suite à des désistements. Rendez-vite vérifie à intervalle régulier les disponibilités d'un praticien pour un type de rendez-vous donné, et envoie un e-mail dès qu'un créneau correspondant à vos critères apparaît.

Critères :

- praticien et motif de consultation
- horizon de recherche (30 prochains jours par défaut)
- jours de la semaine et plage horaire souhaités, dans votre fuseau
- délai minimum avant le rendez-vous, pour avoir le temps de s'organiser
- fréquence de vérification (15 minutes par défaut)

La surveillance est un workflow [Temporal](https://temporal.io) : elle tient des semaines, survit aux redémarrages et aux pannes passagères du service interrogé, et se met en pause, se modifie ou s'arrête à la demande.

## Démarrage rapide

Prérequis : Python 3.11 à 3.13, [uv](https://docs.astral.sh/uv/) et la [CLI Temporal](https://docs.temporal.io/cli).

```bash
uv sync

temporal server start-dev          # serveur local, interface web sur http://localhost:8233
uv run rendez-vite worker          # dans un second terminal

uv run rendez-vite watch \
  --practitioner dr-demo --reason consultation \
  --email moi@example.org \
  --weekdays lun,mar --from-time 08:00 --to-time 12:00 \
  --horizon-days 21 --interval 15m
```

Par défaut, le provider `fake` simule un agenda et les alertes sont écrites dans les journaux du worker : de quoi essayer sans rien configurer. Pour de vrais e-mails, copiez `.env.example` vers `.env`, renseignez la section SMTP, puis ajoutez `--provider http --notifier smtp`.

Le point d'entrée fonctionne aussi sans le script installé : `uv run python -m rendez_vite worker`.

## Commandes

| Commande | Description |
|---|---|
| `rendez-vite worker` | Lance un worker Temporal |
| `rendez-vite watch …` | Démarre une surveillance |
| `rendez-vite status <id>` | Affiche la progression d'une surveillance |
| `rendez-vite stop <id>` | Arrête une surveillance |
| `rendez-vite components` | Liste les providers et notifiers disponibles |

Pause, reprise et modification des critères à chaud passent par les signaux Temporal, voir le [parcours utilisateur](docs/fonctionnel/parcours-utilisateur.md).

## Docker

```bash
docker build -t rendez-vite .
docker compose up -d --build      # serveur Temporal de développement + worker
```

## Documentation

- **Fonctionnelle** : [présentation](docs/fonctionnel/presentation.md), [critères et règles de gestion](docs/fonctionnel/criteres-et-regles.md), [parcours utilisateur](docs/fonctionnel/parcours-utilisateur.md)
- **Technique** : [architecture](docs/technique/architecture.md), [workflow Temporal](docs/technique/workflow-temporal.md), [configuration](docs/technique/configuration.md), [installation et déploiement](docs/technique/installation-et-deploiement.md), [extension](docs/technique/extension.md), [qualité et CI](docs/technique/qualite-et-ci.md)

## Développement

```bash
uv sync --all-groups
uv run ruff format && uv run ruff check
uv run mypy
uv run pytest --cov                  # couverture minimale de 80 %
uv run pytest -m "not integration"   # sans serveur Temporal
```

## Avertissement

Rendez-vite est un projet personnel, sans aucun lien avec Doctolib. Il est destiné à un usage individuel et raisonnable : l'intervalle de vérification ne peut pas descendre sous 60 secondes, et gardez plutôt plusieurs minutes pour ne pas surcharger le service.

## Licence

Distribué sous licence [0BSD](LICENSE) : vous pouvez utiliser, modifier et redistribuer ce projet librement, sans condition.
