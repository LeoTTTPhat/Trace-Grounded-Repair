.PHONY: reproduce smoketest test

reproduce:
	@if [ "$(BUG)" = "smoketest" ] || [ -z "$(BUG)" ]; then \
		python3 -m tgr.harness.smoketest; \
	else \
		echo "Unknown BUG=$(BUG). Currently supported: smoketest"; \
		exit 2; \
	fi

smoketest:
	python3 -m tgr.harness.smoketest

test:
	python3 -m unittest discover -s tests
