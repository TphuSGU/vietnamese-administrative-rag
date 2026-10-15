# CI/CD Quick Start Guide

## 🚀 Quick Commands

### Run All Tests Locally
```bash
cd local-government-ai-assistant/backend
./scripts/run_all_tests.sh
```

### Run Specific Test Suite
```bash
cd local-government-ai-assistant/backend

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Property tests only
pytest tests/property/ -v
```

### Check Test Results in CI
1. Go to **GitHub Actions** tab
2. Click latest workflow run
3. Scroll to **Artifacts** section
4. Download `backend-test-results-py3.12`
5. Extract and open logs in `test-results/` folder

---

## 📊 Understanding the Output

### Local Test Runner Output
```
===================================================
Running All Tests - Will Continue on Errors
===================================================

>>> Running Unit Tests...
[Test output here...]

>>> Running Integration Tests...
[Test output here...]

>>> Running Property Tests...
[Test output here...]

>>> Generating Coverage Report...
[Coverage report here...]

===================================================
Test Summary
===================================================
Failed test suites: 2
Logs saved to test-results/
Coverage report: htmlcov/index.html

⚠️  Some tests failed, but all suites were executed.
```

### What Each Log Contains

- **`test-results/unit-tests.log`** - All unit test output
- **`test-results/integration-tests.log`** - All integration test output
- **`test-results/property-tests.log`** - All property test output
- **`test-results/coverage.log`** - Coverage generation output
- **`htmlcov/index.html`** - Visual coverage report

---

## 🔍 Finding Errors

### 1. In Local Logs
```bash
cd local-government-ai-assistant/backend

# View unit test failures
cat test-results/unit-tests.log | grep -A 10 "FAILED"

# View integration test failures  
cat test-results/integration-tests.log | grep -A 10 "FAILED"

# View property test failures
cat test-results/property-tests.log | grep -A 10 "FAILED"

# Count total failures
grep -c "FAILED" test-results/*.log
```

### 2. In CI Artifacts
1. Download artifacts
2. Extract zip file
3. Open `test-results/*.log` files
4. Search for "FAILED" or "ERROR"

---

## 🎯 Common Tasks

### See Coverage Report
```bash
cd local-government-ai-assistant/backend
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html  # or xdg-open on Linux
```

### Run Tests with Verbose Output
```bash
pytest tests/unit/ -vv --tb=long
```

### Run Single Test File
```bash
pytest tests/unit/test_specific_file.py -v
```

### Run Single Test Function
```bash
pytest tests/unit/test_file.py::test_function_name -v
```

### Stop on First Failure (opposite of CI behavior)
```bash
pytest tests/unit/ -x  # Stop on first failure
```

---

## 🔧 Configuration Files

| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` | Main CI pipeline |
| `.github/workflows/test-report.yml` | Test result publisher |
| `.github/workflows/nightly.yml` | Nightly testing |
| `backend/pytest.ini` | Pytest configuration |
| `backend/scripts/run_all_tests.sh` | Local test runner |

---

## ✅ Checklist for New Tests

When adding new tests:

- [ ] Place in correct directory (`tests/unit/`, `tests/integration/`, `tests/property/`)
- [ ] Name file with `test_` prefix (e.g., `test_new_feature.py`)
- [ ] Name functions with `test_` prefix (e.g., `def test_function_name():`)
- [ ] Add appropriate marker:
  ```python
  @pytest.mark.unit
  @pytest.mark.integration
  @pytest.mark.property
  @pytest.mark.slow  # if test is slow
  ```
- [ ] Run locally before committing:
  ```bash
  pytest tests/path/to/test_file.py -v
  ```
- [ ] Check CI passes after push

---

## 🚨 Troubleshooting

### "No tests ran"
**Check:**
- File starts with `test_`
- Function starts with `test_`
- File is in `tests/` directory

### "Import errors"
**Fix:**
```bash
# Set PYTHONPATH
export PYTHONPATH=/path/to/backend:$PYTHONPATH
pytest tests/
```

### "Can't find coverage report"
**Run:**
```bash
pytest tests/ --cov=app --cov-report=html
# Then open htmlcov/index.html
```

### "Tests pass locally but fail in CI"
**Common causes:**
- Environment variables not set in CI
- Dependencies not in requirements.txt
- Database/external services not available

**Debug:**
1. Check CI logs in artifacts
2. Compare environment variables
3. Review `.github/workflows/ci.yml`

---

## 📈 Best Practices

### 1. Run Fast Tests Locally
```bash
pytest tests/unit/ -m "not slow"
```

### 2. Run Full Suite Before PR
```bash
./scripts/run_all_tests.sh
```

### 3. Check Coverage for New Code
```bash
pytest tests/ --cov=app --cov-report=term-missing
# Look for your new files in the output
```

### 4. Fix Failing Tests ASAP
- Don't let failures accumulate
- Review CI artifacts regularly
- Address failures before adding new features

---

## 📚 More Information

See [CI_SETUP.md](CI_SETUP.md) for complete documentation.
