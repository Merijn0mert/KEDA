# Kubernetes + KEDA Deployment Guide

## Vereisten
- `kubectl` geconfigureerd op je cluster (minikube, kind, of cloud)
- KEDA geïnstalleerd (zie stap 1)
- Docker images gebuild (zie stap 2)

---

## Stap 1 – KEDA installeren

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda --namespace keda --create-namespace
```

Controleer of KEDA draait:
```bash
kubectl get pods -n keda
```

---

## Stap 2 – Docker images bouwen

### Minikube
```bash
eval $(minikube docker-env)   # gebruik de Docker daemon van minikube
docker build -t keda-poc-producer:latest ./producer
docker build -t keda-poc-worker:latest ./worker
docker build -t keda-poc-frontend:latest ./frontend
```

### Kind
```bash
docker build -t keda-poc-producer:latest ./producer
docker build -t keda-poc-worker:latest ./worker
docker build -t keda-poc-frontend:latest ./frontend

kind load docker-image keda-poc-producer:latest
kind load docker-image keda-poc-worker:latest
kind load docker-image keda-poc-frontend:latest
```

### Cloud (bijv. Docker Hub)
```bash
docker build -t jouwusername/keda-poc-producer:latest ./producer && docker push jouwusername/keda-poc-producer:latest
docker build -t jouwusername/keda-poc-worker:latest ./worker   && docker push jouwusername/keda-poc-worker:latest
docker build -t jouwusername/keda-poc-frontend:latest ./frontend && docker push jouwusername/keda-poc-frontend:latest
```
Pas dan de `image:` velden aan in de YAML-bestanden.

---

## Stap 3 – Alles deployen

```bash
# Pas de volgorde aan: eerst RabbitMQ (Secret + Deployment), dan de rest
kubectl apply -f k8s/rabbitmq.yaml
kubectl apply -f k8s/producer.yaml
kubectl apply -f k8s/worker.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/scaledobject.yaml
```

Wacht tot alles draait:
```bash
kubectl get pods -w
```

---

## Stap 4 – Frontend bereiken

### Minikube
```bash
minikube service frontend
```

### Kind / andere clusters
```bash
kubectl port-forward svc/frontend 5173:5173
# Open http://localhost:5173
```

### Producer API direct
```bash
kubectl port-forward svc/producer 8000:8000
# Open http://localhost:8000/docs
```

---

## Stap 5 – KEDA testen

Gooi een paar jobs in de queue via de UI op http://localhost:5173, of via de API:

```bash
curl -X POST http://localhost:8000/add-job \
  -H "Content-Type: application/json" \
  -d '{"count": 50}'
```

Kijk hoe de workers automatisch omhoog en omlaag schalen:
```bash
kubectl get pods -l app=worker -w
```

Of via de ScaledObject status:
```bash
kubectl describe scaledobject worker-scaler
```

---

## Configuratie aanpassen

| Variabele in scaledobject.yaml | Standaard | Beschrijving |
|---|---|---|
| `pollingInterval` | 5s | Hoe vaak KEDA de queue controleert |
| `cooldownPeriod` | 10s | Wachttijd voor scale-to-zero na inactiviteit |
| `value` | 5 | Berichten per worker (bijv. 5 = 10 workers bij 50 jobs) |
| `maxReplicaCount` | 10 | Maximum aantal workers |

---

## Opruimen

```bash
kubectl delete -f k8s/
helm uninstall keda -n keda
```
## Pods opstarten en leeghalen
```bash
#opstarten
kubectl scale deployment --all --replicas=1
#leeghalen
kubectl scale deployment --all --replicas=0

#Bekijke running pods
while ($true) { kubectl get pods; Start-Sleep 2; Clear-Host }
```