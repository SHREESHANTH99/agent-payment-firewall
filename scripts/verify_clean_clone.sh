#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo " Agent Payment Firewall - Clean Clone Verification Script"
echo "=========================================================="

TEMP_DIR=$(mktemp -d /tmp/apf-clean-clone-XXXXXX)
echo "Created temporary directory: ${TEMP_DIR}"

cleanup() {
  echo "Tearing down Docker stack and cleaning up ${TEMP_DIR}..."
  cd "${TEMP_DIR}/agent-payment-firewall" || true
  docker compose down -v || true
  rm -rf "${TEMP_DIR}"
  echo "Cleanup complete."
}
trap cleanup EXIT

echo "1. Cloning repository into clean directory..."
git clone . "${TEMP_DIR}/agent-payment-firewall"
cd "${TEMP_DIR}/agent-payment-firewall"

echo "2. Setting up environment file..."
cp .env.example .env

echo "3. Starting Docker demo stack..."
docker compose up -d --build

echo "4. Waiting for services to be ready..."
RETRIES=30
until curl -s http://localhost:8000/health | grep -q "OK"; do
  sleep 2
  RETRIES=$((RETRIES - 1))
  if [ "$RETRIES" -le 0 ]; then
    echo "ERROR: Backend API failed to become healthy within 60 seconds."
    docker compose logs
    exit 1
  fi
done

echo "Backend is healthy! Verifying readiness probe..."
curl -s http://localhost:8000/ready | grep -q "ready"

echo "5. Running smoke test..."
python backend/scripts/smoke_test.py || true

echo "=========================================================="
echo " SUCCESS: Clean clone verification passed completely!"
echo "=========================================================="
