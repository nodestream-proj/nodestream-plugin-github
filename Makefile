.PHONY: clean
clean: clean-pyc 
	find . \( -name "coverage.xml" -or -name ".coverage" \) -delete
	find . -name htmlcov -exec rm -rf {} +

.PHONY: clean-pyc
clean-pyc:
	find . -name '*.pyc' -exec rm -rf {} +
	find . -name '*.pyo' -exec rm -rf {} +
	find . -name '*~' -exec rm -rf {} +
	find . -name '__pycache__' -exec rm -rf {} +

.PHONY: run
run: 
	poetry install
	poetry run python main.py

.PHONY: fmt
fmt:
	poetry run isort nodestream_github tests
	poetry run black nodestream_github tests

.PHONY: lint
lint: fmt
	poetry run ruff check nodestream_github tests --fix
	
.PHONY: test
test:
	poetry run pytest

