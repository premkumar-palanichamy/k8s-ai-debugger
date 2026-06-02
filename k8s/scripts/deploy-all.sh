#!/bin/bash
# Deploys all broken scenarios to your local minikube cluster
# Usage: ./scripts/deploy-all.sh

set -e

echo ""
echo "⎈  K8s AI Debugger — Test Scenarios"
echo "====================================="
echo ""

# Check minikube is running
if ! kubectl cluster-info &>/dev/null; then
  echo "❌ No cluster found. Starting minikube..."
  minikube start
  echo "✅ Minikube started"
fi

echo "✅ Cluster is running"
echo ""

# Deploy each scenario
MANIFESTS_DIR="$(dirname "$0")/../manifests"

echo "Deploying test scenarios..."
echo ""

for file in "$MANIFESTS_DIR"/*.yaml; do
  scenario=$(basename "$file" .yaml)
  echo "  → Deploying $scenario"
  kubectl apply -f "$file"
done

echo ""
echo "====================================="
echo "✅ All scenarios deployed!"
echo ""
echo "Wait 30 seconds then run:"
echo "  kubectl get pods -n default"
echo ""
echo "You should see pods in various broken states:"
echo "  test-crashloop   → CrashLoopBackOff"
echo "  test-imagepull   → ImagePullBackOff"
echo "  test-oom         → OOMKilled"
echo "  test-pending     → Pending"
echo "  test-configerror → CreateContainerConfigError"
echo "  test-app         → Running (but service has wrong selector)"
echo "  test-storage     → Pending (PVC unbound)"
echo ""
echo "Then open http://localhost:8000 and investigate!"
echo ""
