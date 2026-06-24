PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: install serve test demo demo-docker demo-langchain smoke docker-up clean

install:        ## create venv and install backend, sdk, cli (editable) + test deps
	python3 -m venv .venv
	$(PIP) install --upgrade pip >/dev/null
	$(PIP) install --constraint backend/requirements.txt -e ./sdk -e ./cli -e './backend[dev]'

serve:          ## run the backend on http://127.0.0.1:8700
	cd backend && ../$(PY) -m app

test:           ## run the python test suite
	$(PY) -m pytest backend/tests -q

demo:           ## record a toy agent run via the SDK (backend must be up)
	$(PY) examples/toy_agent/toy_agent.py

demo-docker:    ## seed the checkout-agent-payment-timeout demo incident over HTTP
	python3 scripts/seed_demo_run.py --api-url http://127.0.0.1:8700

demo-langchain: ## record a run through the LangChain adapter (fake chain, no API keys)
	$(PY) examples/langchain_like_agent/agent.py

smoke:          ## end-to-end smoke test against a running backend
	python3 scripts/smoke.py

docker-up:      ## build + run backend-only AFR in docker (persistent volume)
	docker compose up --build

clean:
	rm -rf .venv ui/node_modules ui/dist afr.db afr.db-wal afr.db-shm
