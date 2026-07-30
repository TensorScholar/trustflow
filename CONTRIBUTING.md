# Contributing

Run:

```bash
ruff format --check .
ruff check .
mypy src/trustflow
pytest --cov=trustflow --cov-branch
```

Document-format changes require round-trip fixtures and security tests.
