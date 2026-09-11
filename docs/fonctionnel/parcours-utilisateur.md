# Parcours utilisateur

Exemple : Camille cherche une consultation chez sa dermatologue, un lundi ou un mardi matin, dans les trois prochaines semaines, avec au moins 24 heures pour s'organiser.

## 1. Démarrer le worker

Le worker exécute les surveillances. Il doit tourner en permanence, voir [Installation et déploiement](../technique/installation-et-deploiement.md).

```bash
uv run rendez-vite worker
```

## 2. Lancer une surveillance

```bash
uv run rendez-vite watch \
  --practitioner dr-martin-dermato \
  --reason "consultation" \
  --email camille@example.org \
  --horizon-days 21 \
  --min-lead-time-hours 24 \
  --weekdays lun,mar \
  --from-time 08:00 --to-time 12:00 \
  --interval 15m \
  --provider http --notifier smtp
```

La commande affiche l'identifiant de la surveillance, par exemple `rendez-vite-dr-martin-dermato-consultation`. Ajoutez `--wait` pour attendre la fin de la surveillance dans le terminal.

## 3. Recevoir l'alerte

```text
Objet : Rendez-vite : 1 créneau disponible (consultation)

Bonne nouvelle : 1 créneau disponible correspond à vos critères.

Praticien : dr-martin-dermato
Motif : consultation

- mardi 15 septembre 2026 à 09:30 (Cabinet Martin)
  Réserver : https://booking.example.org/slots/8421

Pensez à réserver rapidement, ces créneaux partent vite.
-- Rendez-vite
```

## 4. Suivre la surveillance

```bash
uv run rendez-vite status rendez-vite-dr-martin-dermato-consultation
# rendez-vite-dr-martin-dermato-consultation: running, 12 check(s), 0 alert(s), last check 2026-09-11 08:45:00+00:00
```

L'interface web de Temporal (<http://localhost:8233> avec le serveur de développement) montre aussi chaque vérification.

## 5. Mettre en pause, reprendre ou modifier

Ces actions passent par la CLI Temporal :

```bash
ID=rendez-vite-dr-martin-dermato-consultation

temporal workflow signal --workflow-id $ID --name pause
temporal workflow signal --workflow-id $ID --name resume

# Élargir la recherche au mercredi et à 30 jours
temporal workflow signal --workflow-id $ID --name update_criteria --input '{
  "practitioner_id": "dr-martin-dermato", "reason": "consultation",
  "timezone": "Europe/Paris", "horizon_days": 30, "min_lead_time_hours": 24,
  "weekdays": [0, 1, 2], "time_range": {"start": "08:00", "end": "12:00"}
}'
```

Les jours sont numérotés de 0 (lundi) à 6 (dimanche).

## 6. Arrêter

```bash
uv run rendez-vite stop rendez-vite-dr-martin-dermato-consultation
```

La surveillance se termine immédiatement, même au milieu d'un intervalle d'attente.
