.PHONY: build up down logs logs-b lint fmt test test-b

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down -v

logs:
        docker compose logs -f server-a

logs-b:
        docker compose logs -f server-b

lint:
	docker compose run --rm server-a ruff check .

fmt:
	docker compose run --rm server-a ruff check --fix . && docker compose run --rm server-a black .

test:
        docker compose run --rm server-a pytest

test-b:
        docker compose run --rm server-b pytest
