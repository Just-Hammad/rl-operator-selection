# One command regenerates every table and figure; one re-runs the experiment.
PY := ./.venv/bin/python
export PYTHONPATH := src

.PHONY: all experiment report test clean setup

## all: regenerate every table and figure from existing raw results
all: report

## setup: create the venv and install pinned dependencies
setup:
	python3 -m venv .venv
	./.venv/bin/pip install -r requirements.lock
	./.venv/bin/pip install -e .

## experiment: re-run exp01 from scratch (~90 min on 9 cores)
experiment:
	$(PY) -m aos.cli run experiments/exp01.yaml

## report: rebuild tables and figures from results/exp01
report:
	$(PY) -m aos.cli report results/exp01 --out paper

## test: run the test suite
test:
	$(PY) -m pytest tests/ -q

## smoke: tiny end-to-end pipeline check (~10s)
smoke:
	$(PY) -m aos.cli run experiments/smoke.yaml
	$(PY) -m aos.cli report results/smoke --out /tmp/aos_smoke_report

clean:
	rm -rf paper/*.png paper/*.csv paper/RESULTS.md
