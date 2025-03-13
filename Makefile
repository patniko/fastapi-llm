.EXPORT_ALL_VARIABLES:

FASTAPI_ENV ?= dev

init:
	poetry install

app-run:
	make docker-up
	poetry run fastapi dev server.py

app-run-prod:
	echo "Starting sql migration"
	poetry run alembic upgrade head
	echo "Starting server"
	poetry run python server.py

app-test:
	make docker-up
	poetry run pytest --capture=no

app-test-ci:
	make migration-run
	poetry run pytest --capture=no

app-test-smoke:
	poetry run pytest --capture=no

docker-up:
	docker-compose up -d
	make migration-run

docker-down:
	docker-compose down

migration-run:
	poetry run alembic upgrade head

migration-new:
	poetry run alembic revision --autogenerate -m $(m)

lint:
	poetry run ruff format
	poetry run ruff check --fix

lint-ci:
	poetry run ruff check
