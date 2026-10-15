#!/bin/bash

echo "========================================"
echo "CI/CD Setup Verification"
echo "========================================"
echo ""

ERRORS=0

# Check GitHub workflows
echo "Checking GitHub workflows..."
if [ -f "../../.github/workflows/ci.yml" ]; then
    echo "✅ ci.yml found"
else
    echo "❌ ci.yml NOT found"
    ERRORS=$((ERRORS+1))
fi

if [ -f "../../.github/workflows/test-report.yml" ]; then
    echo "✅ test-report.yml found"
else
    echo "❌ test-report.yml NOT found"
    ERRORS=$((ERRORS+1))
fi

if [ -f "../../.github/workflows/nightly.yml" ]; then
    echo "✅ nightly.yml found"
else
    echo "❌ nightly.yml NOT found"
    ERRORS=$((ERRORS+1))
fi

echo ""

# Check backend configuration
echo "Checking backend configuration..."
if [ -f "pytest.ini" ]; then
    echo "✅ pytest.ini found"
else
    echo "❌ pytest.ini NOT found"
    ERRORS=$((ERRORS+1))
fi

if [ -f "scripts/run_all_tests.sh" ]; then
    echo "✅ run_all_tests.sh found"
    if [ -x "scripts/run_all_tests.sh" ]; then
        echo "✅ run_all_tests.sh is executable"
    else
        echo "⚠️  run_all_tests.sh is NOT executable (run: chmod +x scripts/run_all_tests.sh)"
    fi
else
    echo "❌ run_all_tests.sh NOT found"
    ERRORS=$((ERRORS+1))
fi

echo ""

# Check test directories
echo "Checking test directories..."
if [ -d "tests/unit" ]; then
    echo "✅ tests/unit/ directory exists"
    UNIT_COUNT=$(find tests/unit -name "test_*.py" | wc -l)
    echo "   Found $UNIT_COUNT unit test files"
else
    echo "❌ tests/unit/ directory NOT found"
    ERRORS=$((ERRORS+1))
fi

if [ -d "tests/integration" ]; then
    echo "✅ tests/integration/ directory exists"
    INTEGRATION_COUNT=$(find tests/integration -name "test_*.py" | wc -l)
    echo "   Found $INTEGRATION_COUNT integration test files"
else
    echo "❌ tests/integration/ directory NOT found"
    ERRORS=$((ERRORS+1))
fi

if [ -d "tests/property" ]; then
    echo "✅ tests/property/ directory exists"
    PROPERTY_COUNT=$(find tests/property -name "test_*.py" | wc -l)
    echo "   Found $PROPERTY_COUNT property test files"
else
    echo "❌ tests/property/ directory NOT found"
    ERRORS=$((ERRORS+1))
fi

echo ""

# Check Python and dependencies
echo "Checking Python environment..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✅ Python found: $PYTHON_VERSION"
else
    echo "❌ Python NOT found"
    ERRORS=$((ERRORS+1))
fi

if command -v pytest &> /dev/null; then
    PYTEST_VERSION=$(pytest --version)
    echo "✅ pytest found: $PYTEST_VERSION"
else
    echo "⚠️  pytest NOT found (install: pip install pytest)"
fi

echo ""

# Check documentation
echo "Checking documentation..."
if [ -f "../../.github/CI_SETUP.md" ]; then
    echo "✅ CI_SETUP.md found"
else
    echo "⚠️  CI_SETUP.md NOT found"
fi

if [ -f "../../.github/QUICK_START.md" ]; then
    echo "✅ QUICK_START.md found"
else
    echo "⚠️  QUICK_START.md NOT found"
fi

if [ -f "../../CI_IMPLEMENTATION_SUMMARY.md" ]; then
    echo "✅ CI_IMPLEMENTATION_SUMMARY.md found"
else
    echo "⚠️  CI_IMPLEMENTATION_SUMMARY.md NOT found"
fi

echo ""
echo "========================================"
echo "Summary"
echo "========================================"

if [ $ERRORS -eq 0 ]; then
    echo "✅ All critical files found!"
    echo ""
    echo "Next steps:"
    echo "1. Run local tests: ./scripts/run_all_tests.sh"
    echo "2. Commit and push to trigger CI"
    echo "3. Check Actions tab on GitHub"
    exit 0
else
    echo "❌ Found $ERRORS error(s)"
    echo ""
    echo "Please fix the issues above before proceeding."
    exit 1
fi
