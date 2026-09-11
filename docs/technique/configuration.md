# Configuration

## Variables d'environnement

Les paramètres sont lus depuis l'environnement ou un fichier `.env` placé dans le répertoire courant (modèle : [`.env.example`](../../.env.example)). Toutes les variables sont préfixées par `RENDEZ_VITE_`.

### Général et Temporal

| Variable | Défaut | Description |
|---|---|---|
| `RENDEZ_VITE_LOG_LEVEL` | `INFO` | Niveau de journalisation |
| `RENDEZ_VITE_TEMPORAL_ADDRESS` | `localhost:7233` | Adresse du serveur Temporal |
| `RENDEZ_VITE_TEMPORAL_NAMESPACE` | `default` | Namespace Temporal |
| `RENDEZ_VITE_TEMPORAL_TASK_QUEUE` | `rendez-vite` | File de tâches du worker et des surveillances |
| `RENDEZ_VITE_TEMPORAL_TLS` | `false` | Active TLS (Temporal Cloud) |
| `RENDEZ_VITE_TEMPORAL_API_KEY` | — | Clé d'API Temporal Cloud (secret) |
| `RENDEZ_VITE_DEFAULT_PROVIDER` | `fake` | Provider utilisé si `--provider` est omis |
| `RENDEZ_VITE_DEFAULT_NOTIFIER` | `console` | Notifier utilisé si `--notifier` est omis |

### Notifier `smtp`

| Variable | Défaut | Description |
|---|---|---|
| `RENDEZ_VITE_SMTP_HOST` | `localhost` | Serveur SMTP |
| `RENDEZ_VITE_SMTP_PORT` | `587` | Port de soumission |
| `RENDEZ_VITE_SMTP_USE_TLS` | `true` | Négocie STARTTLS avant l'envoi |
| `RENDEZ_VITE_SMTP_USERNAME` | — | Identifiant (authentification si identifiant et mot de passe sont renseignés) |
| `RENDEZ_VITE_SMTP_PASSWORD` | — | Mot de passe (secret) |
| `RENDEZ_VITE_SMTP_SENDER` | `rendez-vite@localhost` | Adresse d'expédition |
| `RENDEZ_VITE_SMTP_TIMEOUT_SECONDS` | `10` | Délai de connexion |

Seul STARTTLS est pris en charge (port 587 ou 25). Le TLS implicite du port 465 ne l'est pas.

### Provider `http`

| Variable | Défaut | Description |
|---|---|---|
| `RENDEZ_VITE_BOOKING_API_BASE_URL` | `https://example.invalid/api` | Racine de l'API |
| `RENDEZ_VITE_BOOKING_API_TOKEN` | — | Jeton envoyé en `Authorization: Bearer` (secret) |
| `RENDEZ_VITE_BOOKING_API_TIMEOUT_SECONDS` | `10` | Délai par requête |

Contrat attendu : `GET {base}/availabilities?practitioner_id=…&reason=…&from=<ISO 8601>&to=<ISO 8601>`, qui répond :

```json
{
  "slots": [
    {
      "id": "8421",
      "start": "2026-09-15T09:30:00+02:00",
      "end": "2026-09-15T10:00:00+02:00",
      "practitioner_id": "dr-martin-dermato",
      "reason": "consultation",
      "location": "Cabinet Martin",
      "booking_url": "https://booking.example.org/slots/8421"
    }
  ]
}
```

Seuls `start` et `end` sont obligatoires, et doivent porter un fuseau. Une liste nue, sans l'objet `slots`, est aussi acceptée. Les champs absents sont complétés à partir de la requête.

### Provider `fake`

| Variable | Défaut | Description |
|---|---|---|
| `RENDEZ_VITE_FAKE_SEED` | `rendez-vite` | Graine : même graine, même agenda |
| `RENDEZ_VITE_FAKE_RELEASE_RATE` | `0.05` | Part de l'agenda libre, entre 0 et 1 |
| `RENDEZ_VITE_FAKE_TIMEZONE` | `Europe/Paris` | Fuseau des heures d'ouverture (8 h – 18 h, créneaux de 30 min) |

Les secrets sont stockés en `SecretStr` et n'apparaissent jamais dans les journaux.

## Ligne de commande

```text
rendez-vite [--log-level LEVEL] {worker,watch,status,stop,components}
```

| Commande | Description |
|---|---|
| `worker` | Lance un worker Temporal (bloquant) |
| `watch` | Démarre une surveillance (voir [critères](../fonctionnel/criteres-et-regles.md#critères-de-recherche)) |
| `status <workflow-id>` | Affiche la progression d'une surveillance |
| `stop <workflow-id>` | Arrête une surveillance |
| `components` | Liste les providers et notifiers disponibles |

Options propres à `watch`, en plus des critères :

| Option | Description |
|---|---|
| `--provider`, `--notifier` | Adaptateurs à utiliser (défauts : variables ci-dessus) |
| `--workflow-id` | Remplace l'identifiant dérivé du praticien et du motif |
| `--wait` | Attend la fin de la surveillance et affiche son bilan |

`--log-level` se place **avant** la commande : `rendez-vite --log-level DEBUG worker`.

## Options avancées du workflow

Ces champs de `WatchOptions` ne sont pas exposés par la CLI. Ils restent accessibles en démarrant le workflow depuis le SDK :

| Champ | Défaut | Description |
|---|---|---|
| `checks_before_continue_as_new` | `200` | Vérifications par run avant renouvellement de l'historique |
