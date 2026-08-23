PY := .venv/bin/python
PIP := .venv/bin/pip
NPM := npm

.PHONY: install build-ui serve run test demo demo-docker demo-langchain smoke docker-up start stop logs package clean

install:        ## create venv and install backend, SDK, CLI, and test deps
	python3 -m venv .venv
	$(PIP) install --upgrade pip >/dev/null
	$(PIP) install --constraint backend/requirements.txt -e ./sdk -e ./cli -e './backend[dev]'
	$(PIP) check

build-ui:       ## install locked UI dependencies and build static assets
	cd ui && $(NPM) ci && $(NPM) run build

serve:          ## run the backend and any existing ui/dist bundle on http://127.0.0.1:8700
	cd backend && ../$(PY) -m app

run: build-ui serve  ## build the UI and run the complete local web app

test:           ## run the Python test suite
	$(PY) -m pytest backend/tests -q

demo:           ## record a toy agent run via the SDK (backend must be up)
	$(PY) examples/toy_agent/toy_agent.py

demo-docker:    ## seed the checkout-agent-payment-timeout demo incident over HTTP
	python3 scripts/seed_demo_run.py --api-url http://127.0.0.1:8700

demo-langchain: ## record a run through the LangChain adapter (fake chain, no API keys)
	$(PY) examples/langchain_like_agent/agent.py

smoke:          ## end-to-end smoke test against a running backend
	python3 scripts/smoke.py

docker-up:      ## build and run the complete AFR web app with persistent local data
	docker compose up --build

start:          ## build in the background, wait for health, and open the UI
	sh start.sh

stop:           ## stop AFR while preserving the named data volume
	docker compose down

logs:           ## follow AFR container logs
	docker compose logs -f afr

package: build-ui  ## create a portable source bundle with prebuilt UI assets
	rm -rf dist/agent-flight-recorder-portable dist/agent-flight-recorder-portable.zip
	mkdir -p dist/agent-flight-recorder-portable
	git archive --format=tar HEAD | tar -xf - -C dist/agent-flight-recorder-portable
	mkdir -p dist/agent-flight-recorder-portable/ui/dist
	cp -R ui/dist/. dist/agent-flight-recorder-portable/ui/dist/
	cd dist && zip -qr agent-flight-recorder-portable.zip agent-flight-recorder-portable

clean:
	rm -rf .venv ui/node_modules ui/dist dist afr.db afr.db-wal afr.db-shm
