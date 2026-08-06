.PHONY: quality security test demo build release-check

quality:
	ruff format --check .
	ruff check .
	mypy src/trustflow

security:
	python scripts/check_architecture.py
	python scripts/security_scan.py
	python scripts/secret_scan.py

test:
	pytest --cov=trustflow --cov-branch --cov-report=term-missing

demo:
	trustflow demo

build:
	python -m build

release-check: quality security test demo build
