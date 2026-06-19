# KEDA PoC – Lokale setup

## Starten

```bash
docker compose up --build
```

Wacht tot alles opgestart is (~30 seconden), dan:

| URL | Wat |
|-----|-----|
| http://localhost:5173  | Vue dashboard |
| http://localhost:8000  | Producer API |
| http://localhost:15672 | RabbitMQ UI (guest / guest) |

## Dashboard

- **Jobs toevoegen** — typ een aantal of gebruik de snelknoppen (1 / 10 / 50 / 100 / 500)
- **Queue & Workers grafiek** — live queue lengte vs actieve workers (laatste 2 minuten)
- **CPU & Geheugen grafiek** — resource gebruik van de producer

## Workers handmatig schalen

```bash
# 3 workers starten
docker compose up --scale worker=3 -d

# terugzetten naar 1
docker compose up --scale worker=1 -d
```

## Configuratie aanpassen

In `docker-compose.yml`:

| Variabele | Standaard | Beschrijving |
|-----------|-----------|--------------|
| `PROCESSING_TIME_SECONDS` | 5 | Verwerktijd per job |
| `QUEUE_NAME` | jobs | Naam van de RabbitMQ queue |

## Later: richting Kubernetes + KEDA

De producer API (`/add-job`, `/metrics/current`, `/metrics/history`) werkt
hetzelfde als de app in Kubernetes draait. De Vue frontend hoeft dan alleen
het API adres aangepast te krijgen — de grafieken en meetdata zijn herbruikbaar.
