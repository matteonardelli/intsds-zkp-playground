PYTHON ?= python3
RUN_DIR ?=
RQ3_RUN ?=$(RUN_DIR)
OUTPUT_DIR ?=$(RUN_DIR)

.PHONY: test validate-paper run-paper reproduce-paper paper-artifacts

test:
	$(PYTHON) -m unittest discover -s tests

validate-paper:
	$(PYTHON) scripts/validate_circuits.py --scope all

run-paper:
	$(PYTHON) scripts/run_bench.py --scope all

reproduce-paper:
	$(PYTHON) scripts/reproduce_paper.py

paper-artifacts:
	@test -n "$(RUN_DIR)" || (echo "Set RUN_DIR=results/<run-id>" && exit 2)
	$(PYTHON) scripts/build_paper_artifacts.py \
		$(RUN_DIR) \
		--rq3-run $(RQ3_RUN) \
		--output-dir $(OUTPUT_DIR)
