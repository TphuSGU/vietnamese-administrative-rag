#!/bin/bash
set +e  # Don't exit on error

echo "==================================================="
echo "Running All Tests - Will Continue on Errors"
echo "==================================================="

# Create results directory
mkdir -p test-results

# Track failures
FAILED=0

# Run unit tests
echo ""
echo ">>> Running Unit Tests..."
pytest tests/unit/ -v --tb=short --maxfail=999 \
  --junitxml=test-results/unit-tests.xml \
  2>&1 | tee test-results/unit-tests.log
[ $? -eq 0 ] || FAILED=$((FAILED+1))

# Run integration tests
echo ""
echo ">>> Running Integration Tests..."
pytest tests/integration/ -v --tb=short --maxfail=999 \
  --junitxml=test-results/integration-tests.xml \
  2>&1 | tee test-results/integration-tests.log
[ $? -eq 0 ] || FAILED=$((FAILED+1))

# Run property tests
echo ""
echo ">>> Running Property Tests..."
pytest tests/property/ -v --tb=short --maxfail=999 \
  --junitxml=test-results/property-tests.xml \
  2>&1 | tee test-results/property-tests.log
[ $? -eq 0 ] || FAILED=$((FAILED+1))

# Run coverage
echo ""
echo ">>> Generating Coverage Report..."
pytest tests/ --cov=app --cov-report=html --cov-report=term \
  --maxfail=999 \
  2>&1 | tee test-results/coverage.log
[ $? -eq 0 ] || FAILED=$((FAILED+1))

# Summary
echo ""
echo "==================================================="
echo "Test Summary"
echo "==================================================="
echo "Failed test suites: $FAILED"
echo ""
echo "Logs saved to test-results/"
echo "Coverage report: htmlcov/index.html"
echo ""

if [ $FAILED -gt 0 ]; then
    echo "⚠️  Some tests failed, but all suites were executed."
    exit 1
else
    echo "✅ All tests passed!"
    exit 0
fi
