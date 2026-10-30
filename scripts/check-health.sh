#!/usr/bin/env bash
# Print both backend health endpoints.
set -uo pipefail
BASE_URL="${API_BASE_URL:-http://localhost:8000}"

echo "== GET $BASE_URL/api/v1/health"
curl -s -w "\nHTTP %{http_code}\n" "$BASE_URL/api/v1/health"
echo
echo "== GET $BASE_URL/api/v1/health/db"
curl -s -w "\nHTTP %{http_code}\n" "$BASE_URL/api/v1/health/db"

