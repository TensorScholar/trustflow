.PHONY: quality test demo build

quality:
	ruff format --check .
	ruff check .
	mypy src/trustflow

test:
	pytest --cov=trustflow --cov-branch --cov-report=term-missing

demo:
	trustflow demo

build:
	python setup.py sdist bdist_wheel
