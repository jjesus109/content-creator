.PHONY: dev dev-down dev-logs run

# Start the local PostgreSQL + PostgREST containers
dev:
	@test -f .env.local || (cp .env.local.example .env.local && echo "Created .env.local — fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CREATOR_ID before running 'make run'")
	docker compose up -d
	@echo ""
	@echo "Local stack ready:"
	@echo "  PostgREST (supabase-py): http://localhost:3000"
	@echo "  PostgreSQL (direct):     localhost:5432"
	@echo ""
	@echo "Next: make run"

# Stop and remove containers (data volume is preserved)
dev-down:
	docker compose down

# Destroy containers AND wipe the database volume (full reset)
dev-reset:
	docker compose down -v

# Stream container logs
dev-logs:
	docker compose logs -f

# Run the app locally against the local stack
# Migrations run automatically on startup — no manual SQL needed.
run:
	@test -f .env.local || (echo "Run 'make dev' first to create .env.local" && exit 1)
	PYTHONPATH=src uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --env-file .env.local --reload
