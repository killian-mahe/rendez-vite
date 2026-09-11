# Présentation fonctionnelle

## Contexte

Obtenir un rendez-vous chez un spécialiste peut prendre des mois. Pourtant, des créneaux se libèrent régulièrement suite à des désistements, et ils partent vite. Surveiller soi-même l'agenda d'un praticien plusieurs fois par jour est fastidieux.

## Objectif

Rendez-vite surveille l'agenda d'un praticien pour un motif de consultation donné. Dès qu'un créneau compatible avec vos contraintes apparaît, il vous envoie un e-mail. La réservation reste entre vos mains.

## Périmètre

| Inclus | Exclu |
|---|---|
| Vérification périodique des disponibilités d'un praticien pour un motif | Réservation automatique du créneau |
| Filtrage selon l'horizon, les jours, la plage horaire et un délai minimum | Plusieurs praticiens dans une même surveillance (lancer une surveillance par praticien) |
| Alerte par e-mail, ou dans les journaux pour un essai | SMS, notifications push (ajoutables, voir [Extension](../technique/extension.md)) |
| Pause, reprise, modification des critères et arrêt d'une surveillance en cours | Interface web dédiée (l'interface de Temporal sert au suivi) |
| Surveillance sur plusieurs semaines, résistante aux pannes et redémarrages | Connecteur vers un service de réservation propriétaire |

## Acteurs

- **Patient** : définit ses critères, reçoit les alertes et réserve lui-même.
- **Service de réservation** : expose les créneaux disponibles, via un connecteur (*provider*).
- **Serveur SMTP** : achemine les e-mails.
- **Temporal** : garantit que la surveillance continue malgré les pannes et les redémarrages.

## Glossaire

| Terme | Définition |
|---|---|
| Surveillance (*watch*) | Exécution durable du workflow pour un praticien et un motif. |
| Vérification (*check*) | Interrogation du service de réservation, suivie du filtrage des créneaux. |
| Créneau (*slot*) | Rendez-vous réservable, identifié de façon unique, avec un début et une fin. |
| Horizon | Nombre de jours pendant lesquels un créneau vous intéresse. |
| Délai minimum | Temps minimal entre maintenant et le rendez-vous, pour pouvoir s'organiser. |
| Provider | Connecteur vers un service de réservation (`fake` pour la démonstration, `http` pour une API JSON). |
| Notifier | Canal d'envoi des alertes (`console` ou `smtp`). |

## Usage raisonnable

Rendez-vite est un projet personnel, sans lien avec Doctolib ni avec aucun autre service de réservation. Il est destiné à un usage individuel :

- l'intervalle entre deux vérifications ne peut pas descendre sous 60 secondes. Il vaut 15 minutes par défaut ;
- respectez les conditions d'utilisation du service interrogé.
