# MiniZinc CP Solver for FPL Optimization

This folder contains the **Constraint Programming (CP)** implementation of the FPL optimization pipeline using **MiniZinc** with the **OR-Tools CP-SAT solver**.

## Overview

The MiniZinc implementation provides a CP-based alternative to the MILP solver, offering:
- **Extremely fast solve times** with OR-Tools CP-SAT
- **Oracle mode enabled by default** (uses actual points)
- **Set-based formulation** for transfers (no explicit transfer variables)
- **Declarative modeling** in MiniZinc language

## File Structure

```
cp_minizinc/
├── pre_gw1_step1_minizinc.py      # GW1: Starting XI + Captain
├── pre_gw1_step1.mzn              # MiniZinc model for pre-GW1 step 1
├── pre_gw1_step2_minizinc.py      # GW1: Full squad (bench)
├── pre_gw1_step2.mzn              # MiniZinc model for pre-GW1 step 2
├── post_gw1_step1_minizinc.py     # GW2+: Transfers + Selection
├── post_gw1_step1.mzn             # MiniZinc model for post-GW1
├── run_season_optimizer_minizinc.py  # Season-long optimizer (main entry point)
├── data_prep.py                   # Data preparation utilities
├── README.md                      # This file
├── tests/                         # Test scripts
│   ├── test_pre_gw1_pipeline.py
│   ├── test_post_gw1_quick.py
│   └── test_multi_gameweek_pipeline.py
└── docs/                          # Documentation
    ├── doc_minizinc_api.md
    └── docs-minizinc-dev-en-stable.pdf
```

## Installation

### 1. Install MiniZinc

Download and install MiniZinc from: https://www.minizinc.org/

```bash
# On macOS
brew install minizinc

# On Linux
sudo apt-get install minizinc

# On Windows
# Download installer from https://www.minizinc.org/
```

### 2. Install Python Package

```bash
pip install minizinc
```

### 3. Verify Installation

```python
from minizinc import Solver
print(Solver.lookup('cp-sat'))  # Should print solver info
```

## Usage

### Running the Season Optimizer

```bash
cd optimiser/cp_minizinc
python run_season_optimizer_minizinc.py
```

The script will:
1. Use **OR-Tools CP-SAT** solver (fastest option)
2. Ask if you want to keep **oracle mode enabled** (default: Y)
3. Ask for the ending gameweek (default: 38)
4. Save results to `../../optimised_result/cp_minizinc_season_optim_oracle.json`

### Module-Level Usage

#### Pre-GW1 (Initial Squad Selection)

```python
from pre_gw1_step1_minizinc import optimize_pre_gw1_step1_minizinc
from pre_gw1_step2_minizinc import optimize_pre_gw1_step2_minizinc

# Step 1: Optimize starting XI and captain
step1_solution = optimize_pre_gw1_step1_minizinc(
    players_df,  # DataFrame with 'expected_points' pre-calculated
    solver_name='cp-sat'
)

# Step 2: Optimize full squad (bench)
step2_solution = optimize_pre_gw1_step2_minizinc(
    players_df,
    step1_solution['x'],  # Fixed starters from step 1
    solver_name='cp-sat'
)
```

#### Post-GW1 (Transfers + Selection)

```python
from post_gw1_step1_minizinc import optimize_post_gw1_step1_minizinc

solution = optimize_post_gw1_step1_minizinc(
    players_df,   # DataFrame with 'expected_points' pre-calculated
    y0,           # Dict: current squad {player_id: 0/1}
    p0,           # Dict: purchase prices {player_id: price_scaled_x10}
    f,            # Int: free transfers available
    B_bank,       # Int: bank balance (scaled by 10)
    solver_name='cp-sat'
)
```

## Key Differences from MILP

### 1. Oracle Mode Default
- **CP:** Oracle mode enabled by default (uses actual points)
- **MILP:** Asks user whether to use oracle mode

### 2. Solver
- **CP:** OR-Tools CP-SAT (via MiniZinc)
- **MILP:** CBC, GLPK, or SCIP

### 3. Transfer Formulation
- **CP:** Set-based approach (no explicit transfer variables)
- **MILP:** Explicit transfer variables `t_i` and `s_i`

### 4. Performance
- **CP:** Extremely fast (seconds per gameweek)
- **MILP:** Slower (can take minutes per gameweek)

## Data Requirements

All Python modules expect a DataFrame with these columns:
- `player_id`: Unique player identifier
- `name`: Player name
- `position`: 'GK', 'DEF', 'MID', or 'FWD'
- `team`: Team number (1-20)
- `cost`: Player cost (INTEGER scaled by 10, e.g., 55 = £5.5m)
- `expected_points`: Expected points (pre-calculated by caller)
- `unavailable`: 0/1 (1 if player is injured/suspended)

**IMPORTANT:**
- Each `player_id` must appear exactly **once** (single gameweek data)
- `cost` and `expected_points` are automatically scaled by 10 for integer arithmetic
- The caller must set `expected_points = actual_points` for oracle mode

## Integer Scaling

All prices and points are scaled by 10 for integer arithmetic:
- **£5.5m** → stored as **55**
- **12.3 points** → stored as **123**

This ensures the CP solver works with integers only, improving performance and exactness.

## State Variables

The optimization maintains state between gameweeks:

- **y0**: Current squad membership `{player_id: 0/1}`
- **p0**: Purchase prices `{player_id: price}` (scaled by 10)
- **f**: Free transfers available (1 or 2)
- **B_bank**: Bank balance (scaled by 10)

## Testing

Run the test scripts to verify the implementation:

```bash
# Test Pre-GW1 pipeline
cd tests
python test_pre_gw1_pipeline.py

# Test Post-GW1 quick
python test_post_gw1_quick.py

# Test multi-gameweek pipeline (GW1→GW2→GW3)
python test_multi_gameweek_pipeline.py
```

## Troubleshooting

### Solver Not Found
```
Error: Solver 'cp-sat' not found
```
**Solution:** Install OR-Tools: `pip install ortools`

### MiniZinc Not Installed
```
Error: MiniZinc binary not found
```
**Solution:** Install MiniZinc from https://www.minizinc.org/

### Integer Overflow
```
Error: Integer overflow in cost calculation
```
**Solution:** Ensure all costs and points are properly scaled (÷10 before display, ×10 for computation)

## Performance Notes

- **OR-Tools CP-SAT** is the recommended solver (fastest)
- Typical solve time: **1-3 seconds per gameweek**
- Full season (38 GWs): **~2 minutes total**
- Memory usage: **~500MB** per solve

## References

- [MiniZinc Documentation](https://www.minizinc.org/doc-latest/en/index.html)
- [OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver)
- [Python MiniZinc Package](https://minizinc-python.readthedocs.io/)
