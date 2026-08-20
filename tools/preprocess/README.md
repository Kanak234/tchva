# C++ Preprocessor — fk-preprocess

## Build

```bash
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

## Usage

```bash
./fk-preprocess --in data/raw/ --grid data/districts.json --out api/rules/baselines.json --bench
```

Input: Directory of CSV files named `<grid_id>.csv` (e.g. `HZB-01.csv`)  
CSV format: `time,temperature_2m_max,temperature_2m_min,precipitation_sum,...`  
Output: `baselines.json` — loaded by the rules engine at startup

## Benchmark Results

_(To be recorded after running on the actual dataset — see Section 12.5 of BUILD_SPEC)_

**Protocol:**  
1. Same input: 35 years × 4 grid cells of daily data (~51,100 rows)  
2. Run A: `python tools/baseline_pandas.py` — median of 3 runs  
3. Run B: `./fk-preprocess --bench` — median of 3 runs  
4. Verify both produce identical `baselines.json`  
5. Record: rows, wall time A, wall time B, ratio, CPU model, RAM  

| Run | Rows | Wall Time | Tool |
|-----|------|-----------|------|
| A (pandas) | TBD | TBD | Python |
| B (C++) | TBD | TBD | fk-preprocess |

**Hardware:** TBD

## Why this is justified

This is a genuinely CPU-bound, single-pass, memory-bandwidth-limited workload over
tens of millions of rows. A fast iteration loop (40 seconds vs 12 minutes) matters
while tuning thresholds.

It is **NOT** in the request path. Do not say otherwise in the pitch.
