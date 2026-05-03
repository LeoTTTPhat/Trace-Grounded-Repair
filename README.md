# Trace-Grounded-Repair

Prototype research artifact for the NIER paper "Trace-Grounded Repair:
Letting Large Language Models See Execution."

## Smoke Test

```bash
make smoketest
```

The smoke test traces the paper's `rolling_max` toy bug and writes a compact
run record to `runs/smoketest/`:

- `config.json`
- `trace.json`
- `digest.txt`
- `result.json`

Run the local test suite with:

```bash
make test
```

For the reproducibility entry point described in `PLAN.md`, run:

```bash
make reproduce BUG=smoketest
```

Both targets use `python3`; the prototype expects Python 3.11 or newer.
