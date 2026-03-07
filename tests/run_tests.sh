#!/bin/bash
# Run POI Dashboard backend tests locally
# Prerequisites: PostgreSQL running with database 'poi_test'
#
# Quick setup:
#   createdb poi_test
#   pip install -r backend/requirements.txt
#   pip install -r tests/requirements-test.txt
#   bash tests/run_tests.sh

set -e

export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/poi_test}"
export DATABASE_URL="$TEST_DATABASE_URL"

echo "=== POI Dashboard Test Suite ==="
echo "Database: $TEST_DATABASE_URL"
echo ""

# Run all tests
pytest tests/ -v --tb=short "$@"
