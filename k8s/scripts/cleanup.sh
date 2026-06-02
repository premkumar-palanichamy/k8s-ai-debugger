#!/bin/bash
# Removes all test scenarios from the cluster
# Usage: ./scripts/cleanup.sh

echo ""
echo "🧹 Cleaning up test scenarios..."
echo ""

MANIFESTS_DIR="$(dirname "$0")/../manifests"

for file in "$MANIFESTS_DIR"/*.yaml; do
  scenario=$(basename "$file" .yaml)
  echo "  → Removing $scenario"
  kubectl delete -f "$file" --ignore-not-found=true
done

echo ""
echo "✅ All test scenarios removed"
echo ""
