# Rendez-vite

Surveille les créneaux disponibles d'un praticien et vous prévient par e-mail dès qu'un rendez-vous se libère.

> 🚧 Projet en cours de construction : aucun code n'est encore publié.

## Principe

Obtenir un rendez-vous chez un spécialiste peut prendre des mois, alors que des créneaux se libèrent régulièrement suite à des désistements. Rendez-vite vérifie à intervalle régulier les disponibilités d'un praticien pour un type de rendez-vous donné, et envoie un e-mail dès qu'un créneau correspondant à vos critères apparaît.

Critères envisagés :

- praticien et motif de consultation
- horizon de recherche (par exemple : dans les 30 prochains jours)
- plage horaire et jours de la semaine souhaités
- fréquence de vérification

## Stack prévue

- Python
- [Temporal](https://temporal.io) pour l'orchestration de la surveillance sur la durée
- Envoi des notifications par SMTP

## Avertissement

Rendez-vite est un projet personnel, sans aucun lien avec Doctolib. Il est destiné à un usage individuel et raisonnable : gardez un intervalle de vérification de plusieurs minutes pour ne pas surcharger le service.

## Licence

Distribué sous licence [0BSD](LICENSE) : vous pouvez utiliser, modifier et redistribuer ce projet librement, sans condition.
