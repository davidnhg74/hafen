# Oracle demo schemas (Tier 2)

| Schema | What it adds | Status |
|---|---|---|
| HR | Already in the dev container; covered by `test_migrate_runner_oracle_live.py` | loaded |
| SH | Already in the dev container; sales-history star schema | loaded |
| CO | Already in the dev container; BLOB columns covered by `test_blob_round_trips_via_co_products` | loaded |
| **OE** (Order Entry) | Object types, nested tables, XMLType, varrays | **not yet loaded** |
| **PM** (Product Media) | BLOB + BFILE + XMLType + multimedia | **not yet loaded** |
| IX (Information Exchange) | Oracle Streams / AQ messaging — out of scope | flag as unsupported |

Same operational pattern as `oracle_benchmarks/` — drop the install
scripts here, extend the matrix runner, optionally bake into
`docker/oracle-init/`. OE and PM specifically would close the
"object types" and "multimedia" coverage gaps.
