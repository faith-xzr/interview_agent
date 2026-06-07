.PHONY: install backend frontend dev demo status stop restart test

BACKEND_HOST ?= 127.0.0.1
BACKEND_PORT ?= 8000
FRONTEND_HOST ?= 127.0.0.1
FRONTEND_PORT ?= 5173

install:
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

backend:
	PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --host $(BACKEND_HOST) --port $(BACKEND_PORT)

frontend:
	cd frontend && npm run dev -- --host $(FRONTEND_HOST) --port $(FRONTEND_PORT)

dev:
	$(MAKE) -j2 backend frontend

demo: dev

status:
	@echo "Backend: http://$(BACKEND_HOST):$(BACKEND_PORT)"
	@if lsof -nP -iTCP:$(BACKEND_PORT) -sTCP:LISTEN >/dev/null 2>&1; then \
		echo "  [ok] port $(BACKEND_PORT) is listening"; \
		if health=$$(curl --fail --silent --max-time 2 http://$(BACKEND_HOST):$(BACKEND_PORT)/api/health); then \
			printf "  [ok] health %s\n" "$$health"; \
		else \
			echo "  [warn] /api/health is not responding"; \
		fi; \
	else \
		echo "  [down] port $(BACKEND_PORT) is not listening"; \
	fi
	@echo "Frontend: http://$(FRONTEND_HOST):$(FRONTEND_PORT)"
	@if lsof -nP -iTCP:$(FRONTEND_PORT) -sTCP:LISTEN >/dev/null 2>&1; then \
		echo "  [ok] port $(FRONTEND_PORT) is listening"; \
		if curl --fail --silent --head --max-time 2 http://$(FRONTEND_HOST):$(FRONTEND_PORT)/ >/dev/null; then \
			echo "  [ok] page responds"; \
		else \
			echo "  [warn] page is not responding"; \
		fi; \
	else \
		echo "  [down] port $(FRONTEND_PORT) is not listening"; \
	fi

stop:
	@echo "Stopping backend/frontend listeners..."
	@for port in $(BACKEND_PORT) $(FRONTEND_PORT); do \
		pids=$$(lsof -tiTCP:$$port -sTCP:LISTEN 2>/dev/null || true); \
		if [ -n "$$pids" ]; then \
			echo "  stopping port $$port: $$pids"; \
			kill $$pids 2>/dev/null || true; \
			sleep 1; \
			remaining=$$(lsof -tiTCP:$$port -sTCP:LISTEN 2>/dev/null || true); \
			if [ -n "$$remaining" ]; then \
				echo "  force stopping port $$port: $$remaining"; \
				kill -9 $$remaining 2>/dev/null || true; \
			fi; \
		else \
			echo "  port $$port is free"; \
		fi; \
	done

restart: stop
	$(MAKE) dev

test:
	PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
	cd frontend && npm test
