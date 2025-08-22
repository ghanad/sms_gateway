.PHONY: build up down logs lint fmt test

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down -v

logs:
	docker compose logs -f server-a

lint:
	docker compose run --rm server-a ruff check .

fmt:
	docker compose run --rm server-a ruff check --fix . && docker compose run --rm server-a black .

test:
	docker compose run --rm server-a pytest