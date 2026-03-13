# Testing — Ghost Backend

## pytest Configuration

### Markers
```bash
pytest tests/ -m "unit"         # Unit tests only
pytest tests/ -m "integration"  # Integration tests (require DB/Redis)
pytest tests/ -m "not slow"     # Skip slow tests
```

### Coverage
```bash
pytest tests/ --cov=src/ghost --cov-report=html --cov-fail-under=50
```

- CI gate: 50% minimum (`--cov-fail-under=50` in `.github/workflows/ci.yml`)
- Production target: 85%
- Reports: `htmlcov/` directory

## Mocking Patterns

### Database
```python
@pytest.fixture
def mock_db_session():
    """Mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session
```

### Redis
```python
@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis
```

### External APIs
```python
@pytest.fixture
def mock_httpx():
    """Mock external HTTP calls."""
    with patch("httpx.AsyncClient") as mock:
        client = AsyncMock()
        mock.return_value.__aenter__ = AsyncMock(return_value=client)
        mock.return_value.__aexit__ = AsyncMock(return_value=False)
        yield client
```

## CI Pipeline Test Job

The `test` job in `.github/workflows/ci.yml`:
1. Sets up Python 3.12
2. Caches pip dependencies
3. Installs `requirements-dev.txt` + editable package
4. Runs flake8 linting (fatal errors + style warnings)
5. Runs mypy type checking
6. Runs pytest with coverage (50% gate)
7. Uploads coverage to Codecov

Security scanning is handled separately by `security.yml` (bandit + safety + semgrep).

## Running Tests Locally

```bash
# Full suite
pytest

# Verbose with output
pytest -v -s

# Single file
pytest tests/test_framework.py

# Single test
pytest tests/test_framework.py::TestGhostFramework::test_config_loading

# With coverage HTML report
pytest --cov=src/ghost --cov-report=html && open htmlcov/index.html
```
