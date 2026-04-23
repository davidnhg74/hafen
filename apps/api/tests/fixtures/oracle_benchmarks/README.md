# Oracle benchmark fixtures (Tier 1)

This directory holds the install scripts for the industry-standard
benchmark schemas the matrix runner exercises:

| Benchmark | Purpose | Status |
|---|---|---|
| TPC-H | Analytical workload, 8 tables. Breadth + classic FK star. | not yet loaded |
| TPC-C | OLTP workload, 9 tables, composite PKs. | not yet loaded |
| Swingbench Order Entry (SOE) | Real-world Oracle-idiomatic OLTP, includes the `ORDERENTRY` PL/SQL package, triggers, sequences. Pulls double duty as Strand 3b material. | not yet loaded |

Each benchmark is large enough that we don't vendor it into the
repo. The matrix runner skips Tier-1 fixtures cleanly when the
expected schema isn't present in the dev Oracle container.

## Adding a benchmark

1. Get the install scripts from upstream (HammerDB for TPC-C/H,
   Dominic Giles' Swingbench for SOE).
2. Drop the install SQL here as `load_<name>.sql`.
3. Extend `apps/api/tests/test_migration_benchmark_live.py` with a
   parameterized entry pointing at the fixture's schema name +
   tables of interest.
4. Optionally extend `docker/oracle-init/` so a fresh container
   auto-loads the benchmark on first boot.

## Why we ship empty for now

The Tier-3 stress schemas (`tests/fixtures/oracle_stress/`) cover
every code path our recent audit fixed. Tier-1 benchmarks add
breadth and realism but are operationally costlier (multi-GB
datasets) and don't exercise any failure mode we're not already
testing. We add them when we want to make performance / scale claims
in marketing — not as a launch blocker.
