.PHONY: build up down restart logs test shell clean

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart chatbot

logs:
	docker-compose logs -f chatbot

test:
	curl -s http://localhost:8000/api/health | python -m json.tool

shell:
	docker-compose exec chatbot bash

seed:
	docker-compose exec chatbot python scripts/seed_database.py

clean:
	docker-compose down -v
	docker system prune -f

rebuild: clean build up seed