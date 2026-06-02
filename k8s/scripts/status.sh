#!/bin/bash
# Shows current state of all test pods
# Usage: ./scripts/status.sh

echo ""
echo "⎈  Test Scenarios Status"
echo "========================="
echo ""

echo "--- PODS ---"
kubectl get pods -n default --show-labels | grep -E "test-|NAME"

echo ""
echo "--- JOBS ---"
kubectl get jobs -n default | grep -E "test-|NAME"

echo ""
echo "--- PVCs ---"
kubectl get pvc -n default | grep -E "test-|NAME"

echo ""
echo "--- SERVICES ---"
kubectl get svc -n default | grep -E "test-|NAME"

echo ""
echo "--- ENDPOINTS ---"
kubectl get endpoints -n default | grep -E "test-|NAME"
echo ""
