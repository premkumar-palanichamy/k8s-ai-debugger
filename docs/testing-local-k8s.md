# Local Kubernetes Testing (Minikube)

Use the bundled broken manifests to validate all major detection paths.

## Start cluster

```bash
minikube start
kubectl get nodes
```

## Deploy all scenarios

```bash
cd k8s
chmod +x scripts/*.sh
./scripts/deploy-all.sh
./scripts/status.sh
```

## Scenario manifest map

- `manifests/crashloop.yaml`
- `manifests/imagepull.yaml`
- `manifests/oom.yaml`
- `manifests/pending.yaml`
- `manifests/configerror.yaml`
- `manifests/no-endpoints.yaml`
- `manifests/failedjob.yaml`
- `manifests/pvc-unbound.yaml`

## Investigate examples

```bash
# Full namespace scan
curl -X POST http://localhost:8000/api/v1/investigate/sync \
  -H "Content-Type: application/json" \
  -d '{"namespace":"default","scan_mode":"full"}'

# Target a pod
curl -X POST http://localhost:8000/api/v1/investigate/sync \
  -H "Content-Type: application/json" \
  -d '{"namespace":"default","pod_name":"test-crashloop"}'
```

## Cleanup

```bash
cd k8s
./scripts/cleanup.sh
```
