# CI/CD Pipeline Setup

## Overview

This repository includes a comprehensive GitHub Actions CI/CD pipeline that:
- ✅ Runs **all** tests (unit, integration, property-based)
- ✅ Logs **ALL** errors (doesn't stop on first failure)
- ✅ Generates detailed reports and artifacts
- ✅ Supports both backend and frontend testing
- ✅ Includes security scanning
- ✅ Provides coverage reports

---

## Files Created

### 1. **`.github/workflows/ci.yml`** - Main CI Pipeline
Comprehensive pipeline with:
- Backend testing (unit, integration, property tests)
- Frontend validation (HTML, JavaScript)
- Security scanning (Bandit, Safety)
- Coverage reporting
- Full error logging with artifacts

### 2. **`.github/workflows/test-report.yml`** - Test Report Publisher
Automatically publishes test results to PR comments and checks.

### 3. **`.github/workflows/nightly.yml`** - Nightly Testing
Runs full test suite nightly at 2 AM UTC.

### 4. **`backend/pytest.ini`** - Pytest Configuration
Optimized pytest settings for:
- Detailed logging
- Continuing on errors (`--maxfail=999`)
- Test markers (unit, integration, property, slow)
- Coverage configuration

### 5. **`backend/scripts/run_all_tests.sh`** - Local Test Runner
Shell script to run all tests locally with the same error-logging behavior as CI.

---

## Key Features

### 1. **Continue on Error**
The pipeline continues executing even when tests fail:

```yaml
continue-on-error: true      # Jobs don't stop pipeline
fail-fast: false             # Matrix runs all combinations
--maxfail=999                # Pytest continues through failures
|| true                      # Shell commands don't stop workflow
```

### 2. **Full Error Logging**
Every test suite logs all errors:

```yaml
--tb=short                   # Short traceback format
-o log_cli=true              # Real-time logging
--junitxml=test-results/     # JUnit XML reports
2>&1 | tee test-results.log  # Capture all output
```

### 3. **Artifact Upload**
All logs and reports are saved as artifacts:

```yaml
if: always()                 # Upload even on failure
retention-days: 30           # Keep for 30 days
```

### 4. **Parallel Testing**
Multiple test suites run in parallel:
- Unit tests
- Integration tests
- Property-based tests
- Frontend validation
- Security scanning

---

## Usage

### Local Testing

Run all tests locally with full error logging:

```bash
cd local-government-ai-assistant/backend
./scripts/run_all_tests.sh
```

This will:
1. Run unit tests (logs to `test-results/unit-tests.log`)
2. Run integration tests (logs to `test-results/integration-tests.log`)
3. Run property tests (logs to `test-results/property-tests.log`)
4. Generate coverage report (logs to `test-results/coverage.log`)
5. Continue even if tests fail
6. Display summary at the end

### GitHub Actions

#### Automatic Triggers
The CI runs automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`

#### Manual Trigger
1. Go to **Actions** tab on GitHub
2. Select **CI Pipeline** workflow
3. Click **Run workflow**
4. Select branch and run

#### Nightly Tests
Full test suite runs automatically at 2 AM UTC daily.

---

## Viewing Results

### 1. In GitHub Actions UI

1. Navigate to **Actions** tab
2. Click on a workflow run
3. View job summaries and step outputs
4. Check the **Summary** for quick overview

### 2. Download Artifacts

1. Scroll to bottom of workflow run
2. Download artifacts:
   - `backend-test-results-py3.12` - All backend test logs
   - `frontend-test-results` - Frontend validation logs
   - `security-scan-results` - Security reports
   - `ci-summary` - Overall summary

3. Extract and review:
   - `test-results/unit-tests.log` - Unit test output
   - `test-results/integration-tests.log` - Integration test output
   - `test-results/property-tests.log` - Property test output
   - `htmlcov/index.html` - Coverage report

### 3. Test Reports

Test results are automatically published as:
- PR comments (via `test-report.yml`)
- GitHub Checks (visible in PR)
- Step summaries (in workflow run)

---

## Configuration

### Pytest Settings

Edit `backend/pytest.ini` to customize:

```ini
[pytest]
addopts = 
    -v                              # Verbose
    --maxfail=999                   # Continue on errors
    --continue-on-collection-errors # Don't stop on import errors
    --tb=short                      # Short tracebacks

log_cli_level = INFO                # Console log level
log_file_level = DEBUG              # File log level
```

### CI Workflow Settings

Edit `.github/workflows/ci.yml`:

```yaml
strategy:
  matrix:
    python-version: ['3.12']  # Add more Python versions
  fail-fast: false            # Keep false to test all versions
```

### Test Markers

Use markers to categorize tests:

```python
@pytest.mark.unit
def test_example():
    pass

@pytest.mark.integration
def test_integration():
    pass

@pytest.mark.property
def test_property():
    pass

@pytest.mark.slow
def test_slow_operation():
    pass
```

Run specific markers:
```bash
pytest -m unit          # Run only unit tests
pytest -m "not slow"    # Skip slow tests
```

---

## Security Scanning

### Bandit (Code Security)
Scans Python code for security issues:
- Hardcoded passwords
- SQL injection risks
- Shell injection
- Insecure functions

### Safety (Dependency Check)
Checks dependencies for known vulnerabilities.

### Results
Security scan results are uploaded as artifacts:
- `bandit-report.json` - Detailed security issues
- `safety-report.json` - Vulnerable dependencies

---

## Coverage Reports

Coverage is generated automatically:

### In CI:
- Uploaded to Codecov (if configured)
- HTML report in artifacts (`htmlcov/`)
- Summary in workflow output

### Locally:
```bash
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html
```

---

## Troubleshooting

### Issue: Tests are failing but CI shows success
**Cause**: Jobs have `continue-on-error: true`

**Solution**: Check:
1. Job summaries for individual results
2. Download artifacts for detailed logs
3. The "Summary" job shows overall status

### Issue: Can't find test logs
**Cause**: Artifacts may not be uploaded

**Solution**:
1. Check if job completed (even with errors)
2. Look for "Upload test results" step
3. Download artifacts from workflow run page

### Issue: Want CI to fail on test failures
**Cause**: By design, pipeline continues on errors

**Solution**: Modify `.github/workflows/ci.yml`:
```yaml
# Remove these lines:
continue-on-error: true
fail-fast: false

# Change:
|| true
# To:
# (nothing - let it fail)
```

---

## Best Practices

### 1. Review Artifacts Regularly
- Download and review test logs
- Check coverage reports
- Monitor security scan results

### 2. Fix Tests Incrementally
- Don't let failing tests accumulate
- Use artifacts to identify patterns
- Focus on high-impact failures first

### 3. Use Test Markers
- Mark slow tests with `@pytest.mark.slow`
- Mark integration tests appropriately
- Run fast tests locally, full suite in CI

### 4. Monitor Coverage
- Aim for >80% coverage
- Review uncovered code
- Add tests for critical paths

---

## Examples

### Run Specific Test Suite Locally

```bash
cd local-government-ai-assistant/backend

# Run only unit tests
pytest tests/unit/ -v --tb=short

# Run only integration tests  
pytest tests/integration/ -v --tb=short

# Run only property tests
pytest tests/property/ -v --tb=short

# Run with coverage
pytest tests/unit/ --cov=app --cov-report=term
```

### Debug Failing Test

```bash
# Run with full traceback
pytest tests/unit/test_example.py -v --tb=long

# Run with pdb debugger
pytest tests/unit/test_example.py -v --pdb

# Run single test function
pytest tests/unit/test_example.py::test_specific_function -v
```

### Generate Local Reports

```bash
cd local-government-ai-assistant/backend

# Run all tests with reports
pytest tests/ \
  --junitxml=test-results/junit.xml \
  --cov=app \
  --cov-report=html \
  --cov-report=term \
  --maxfail=999

# View coverage
open htmlcov/index.html
```

---

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [Codecov documentation](https://docs.codecov.com/)
- [Bandit documentation](https://bandit.readthedocs.io/)

---

## Summary

✅ **Created Files:**
- `.github/workflows/ci.yml` - Main CI pipeline
- `.github/workflows/test-report.yml` - Test result publisher
- `.github/workflows/nightly.yml` - Nightly full test
- `backend/pytest.ini` - Pytest configuration
- `backend/scripts/run_all_tests.sh` - Local test runner

✅ **Features:**
- Continues on all errors
- Logs everything to artifacts
- Runs all test suites in parallel
- Generates coverage reports
- Includes security scanning
- 30-day artifact retention

✅ **Usage:**
- Automatic: Push to main/develop
- Manual: Actions tab → Run workflow
- Local: `./scripts/run_all_tests.sh`
