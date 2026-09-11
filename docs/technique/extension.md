# Extension

Chaque point d'extension s'ajoute sans modifier le code existant, hormis l'enregistrement du nouveau composant.

## Ajouter un service de réservation

1. Implémentez le port `SlotProvider` : une coroutine `fetch_slots(query) -> list[AppointmentSlot]`. Elle lève `SlotProviderError` en cas d'échec.

   ```python
   class MyClinicProvider:
       """Read availabilities from My Clinic's API."""

       def __init__(self, api_key: str) -> None: ...

       async def fetch_slots(self, query: SlotQuery) -> list[AppointmentSlot]:
           """Return the slots offered in the query window. ..."""
           ...
   ```

2. Enregistrez une fabrique dans `build_provider_registry()` (`infrastructure/providers/__init__.py`), ou dans un registre dédié passé à `AppointmentActivities` depuis `worker.py` :

   ```python
   registry.register("my-clinic", lambda settings: MyClinicProvider(settings.my_clinic_api_key))
   ```

3. Ajoutez les paramètres nécessaires à `Settings`, puis sélectionnez le provider avec `--provider my-clinic`.

Si l'API est proche du contrat JSON par défaut, sous-classez `HttpSlotProvider` et redéfinissez seulement `parse_slot`.

## Ajouter un canal de notification

1. Implémentez `NotificationSender` : `async send(message: EmailMessage) -> None`, qui lève `NotificationError` en cas d'échec.
2. Enregistrez-le dans `build_notifier_registry()`.
3. Pour un format différent (HTML, message court pour SMS), fournissez un autre `AlertRenderer` à `AppointmentActivities`.

## Ajouter un critère de recherche

1. Ajoutez le champ à `SearchCriteria`, avec une valeur par défaut qui préserve le comportement actuel et une validation dans `__post_init__`.
2. Créez un `SlotFilter` dédié dans `domain/filters.py`.
3. Ajoutez sa fabrique à `FILTER_FACTORIES`.
4. Exposez-le dans la CLI (`build_parser` et `build_watch_request`).

Les filtres s'exécutent **dans le workflow** : ils doivent rester purs, sans I/O, sans aléatoire et sans lecture de l'horloge (l'instant de référence leur est fourni). Voir aussi les [contraintes de déterminisme](workflow-temporal.md#contraintes-de-déterminisme).

## Tester une extension

Les adaptateurs se testent isolément, avec des doublures injectées : `client_factory` pour HTTP, `transport_factory` pour SMTP. Les activités se testent avec `temporalio.testing.ActivityEnvironment`, sans serveur. Des exemples se trouvent dans `tests/unit/`.
