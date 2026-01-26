up:
	docker compose up

up-all:
	docker compose --profile web --profile telegram up

up-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up

down:
	docker compose down

