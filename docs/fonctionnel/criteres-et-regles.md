# Critères et règles de gestion

## Critères de recherche

| Critère | Option `watch` | Défaut | Contrôle à la saisie |
|---|---|---|---|
| Praticien | `--practitioner` | obligatoire | non vide |
| Motif de consultation | `--reason` | obligatoire | non vide |
| Adresse d'alerte | `--email` | obligatoire | format `x@y.z` |
| Horizon de recherche | `--horizon-days` | 30 jours | ≥ 1 |
| Délai minimum avant le rendez-vous | `--min-lead-time-hours` | 0 heure | ≥ 0 |
| Jours de la semaine | `--weekdays` | `mon,tue,wed,thu,fri` | au moins un jour ; abréviations anglaises ou françaises (`lun,mar`) |
| Plage horaire | `--from-time` / `--to-time` | `00:00` – `23:59` | format `HH:MM`, début ≤ fin |
| Fuseau horaire | `--timezone` | `Europe/Paris` | identifiant IANA connu |
| Fréquence de vérification | `--interval` | `15m` | ≥ 60 s ; suffixes `s`, `m`, `h` |
| Nombre maximal de vérifications | `--max-checks` | illimité | ≥ 1 |
| Continuer après une alerte | `--keep-watching` | non | — |

Une saisie invalide est refusée avant le démarrage de la surveillance, avec un message explicite.

## Règles de gestion

| Réf. | Règle |
|---|---|
| RG-01 | Un créneau est retenu seulement s'il satisfait **tous** les critères. |
| RG-02 | Le jour et l'heure d'un créneau sont évalués dans le fuseau de l'utilisateur, changements d'heure compris. |
| RG-03 | La plage horaire porte sur l'heure de **début** du créneau ; ses bornes sont incluses. |
| RG-04 | Horizon : le créneau commence au plus tard *maintenant + N jours*. Délai minimum : il commence au plus tôt *maintenant + H heures*. |
| RG-05 | Le motif est comparé sans tenir compte de la casse ni des espaces multiples. Les accents restent significatifs. |
| RG-06 | Un même créneau n'est annoncé qu'une seule fois. Les 500 derniers créneaux annoncés sont mémorisés. |
| RG-07 | Un créneau n'est considéré comme annoncé qu'une fois l'e-mail envoyé. Si l'envoi échoue, il sera de nouveau proposé à la vérification suivante. |
| RG-08 | Un e-mail regroupe tous les nouveaux créneaux d'une vérification, triés par ordre chronologique. |
| RG-09 | Par défaut, la surveillance s'arrête après la première alerte. Avec `--keep-watching`, elle continue et n'annonce que les nouveaux créneaux. |
| RG-10 | La surveillance s'arrête aussi lorsque le nombre maximal de vérifications est atteint, ou sur demande d'arrêt. |
| RG-11 | Une vérification est comptée même si le service de réservation est indisponible. La surveillance continue à l'intervalle suivant. |
| RG-12 | Une erreur de configuration (provider ou notifier inconnu) arrête la surveillance en échec : elle ne se corrigera pas seule. |
| RG-13 | Modifier les critères en cours de route efface la mémoire des créneaux annoncés, pour les réévaluer selon les nouvelles règles. |
| RG-14 | En pause, aucune vérification n'a lieu. Après la reprise, la vérification suivante a lieu dès la fin de l'intervalle en cours. |
| RG-15 | Deux surveillances ayant le même praticien et le même motif partagent un identifiant. Une seconde ne peut pas démarrer tant que la première tourne. |

## Cas limites

| Situation | Comportement |
|---|---|
| Un créneau disparaît puis réapparaît | Il n'est pas annoncé de nouveau tant qu'il figure parmi les 500 derniers annoncés. |
| Le service de réservation renvoie un créneau mal formé | La vérification échoue, puis est retentée automatiquement (RG-11). |
| Changement d'heure pendant la surveillance | Aucun impact : les calculs utilisent des instants absolus, convertis dans le fuseau de l'utilisateur. |
| Le worker est arrêté plusieurs heures | La surveillance reprend là où elle en était au redémarrage, sans perdre sa mémoire. |
| Surveillance de plusieurs mois | L'historique Temporal est renouvelé régulièrement, en conservant la progression (voir [Workflow Temporal](../technique/workflow-temporal.md)). |
