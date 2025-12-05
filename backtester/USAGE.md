# FPL Backtester - Usage Guide

## Overview

The FPL Backtester evaluates your season optimizer results against actual gameweek data, providing comprehensive analysis of points, transfers, and team performance.

## Quick Start

### Command Line Usage

```bash
python -m backtester.backtester <optimizer_json_filename>
```

**Example:**
```bash
python -m backtester.backtester season_optimization_results.json
```

This will:
1. Read the optimizer JSON from `optimised_result/season_optimization_results.json`
2. Load player data from `cleaned_data.csv`
3. Process all 38 gameweeks
4. Generate results at `backtester/season_optimization_results_backtest_results.txt`

### Python API Usage

```python
from backtester import run_backtest, save_backtest_results

# Option 1: Run and get results
results_text, total_points, total_transfers = run_backtest(
    optimizer_json_path="optimised_result/season_optimization_results.json",
    cleaned_data_path="cleaned_data.csv"
)
print(f"Total Points: {total_points}")
print(f"Total Transfers: {total_transfers}")

# Option 2: Run and save directly to file
total_points, total_transfers = save_backtest_results(
    optimizer_json_path="optimised_result/season_optimization_results.json",
    output_path="backtester/my_results.txt",
    cleaned_data_path="cleaned_data.csv"
)
```

## Input Requirements

### 1. Optimizer JSON File
- Location: `optimised_result/` folder
- Format: JSON with structure described in `backtester/README.md`
- Contains team selections for each gameweek (gw1-gw38)

### 2. Cleaned Data CSV
- Location: Root directory
- Filename: `cleaned_data.csv`
- Contains player stats for all 638 players across 38 gameweeks

## Output Format

The backtester generates a TXT file with:

### Per-Gameweek Information
- **Points**: Points scored that gameweek
- **Cumulative Points**: Running total
- **Transfers**: Players transferred in/out with details (ID, name, position, team)
- **Captain Info**: Captain/vice-captain with bonus points applied
- **Substitutions**: Automatic substitutions made (if any)
- **Active Lineup**: Final playing XI with points and minutes
- **Bench**: Bench players with substitution status

### Final Summary
- Total points for the season
- Total number of transfers
- Average points per gameweek
- Number of gameweeks completed

## Features

### Automatic Validation
The backtester validates each gameweek's selection:
- ✓ Squad composition (2 GK, 5 DEF, 5 MID, 3 FWD)
- ✓ Max 3 players per club
- ✓ Starting XI formation (1 GK, 3-5 DEF, 2-5 MID, 1-3 FWD)
- ✓ Bench configuration (position 1 = GK, positions 2-4 = outfield)
- ✓ Captain/vice-captain selection

**If validation fails**, the backtester stops and reports the specific error.

### Automatic Substitutions
- Processes bench in order (positions 1→2→3→4)
- Only substitutes players who actually played (minutes > 0)
- Validates formation after each potential substitution
- Stops when 11 active players reached or all bench tried

### Captain Doubling
- If captain played: doubles captain's points
- Else if vice-captain played: doubles vice-captain's points
- Else: no doubling applied

### Transfer Tracking
- Compares current squad with previous gameweek
- Identifies specific players transferred in/out
- Shows player details (name, ID, position, team)

## Example Output Snippet

```
================================================================================
GAMEWEEK 10
================================================================================
Points: 77
Cumulative Points: 708

Transfers:
  IN (3):
    Dominic Solanke-Mitchell (ID: 158, FWD, Spurs)
    Curtis Jones (ID: 126, MID, Liverpool)
    Ola Aina (ID: 487, DEF, Nott'm Forest)
  OUT (3):
    Matthijs de Ligt (ID: 435, DEF, Man Utd)
    Facundo Buonanotte (ID: 188, MID, Leicester)
    Michail Antonio (ID: 443, FWD, West Ham)

Captain: Mohamed Salah (ID: 451)
Vice-Captain: Ola Aina (ID: 487)
Captain Bonus: +9 pts (captain)

Substitutions Made: None

Active Lineup (11 players):
  GK: Jordan Pickford - 2pts (90min)
  DEF: Joško Gvardiol - 7pts (90min)
  DEF: Michael Keane - 1pts (90min)
  DEF: Ola Aina (VC) - 15pts (88min)
  MID: Cole Palmer - 3pts (90min)
  MID: Curtis Jones - 4pts (24min)
  MID: Georginio Rutter - 2pts (90min)
  MID: Mohamed Salah (C) - 9pts (90min)
  FWD: Chris Wood - 7pts (78min)
  FWD: Dominic Solanke-Mitchell - 16pts (90min)
  FWD: Ollie Watkins - 2pts (90min)
```

## Error Handling

If validation fails, the backtester will:
1. Stop processing
2. Report the gameweek where the error occurred
3. Display the specific validation error
4. Show what type of validation failed (squad/starters/bench/captaincy)

Example error output:
```
GW5: VALIDATION FAILED - Starting XI
  Error: Starting XI must have 3-5 DEF, found 2
```

## Module Structure

- `fpl_validator.py` - Team validation logic
- `fpl_point_calculator.py` - Point calculation with substitutions
- `backtester.py` - Main orchestration module
- `__init__.py` - Package exports

## Requirements

- Python 3.7+
- pandas
- Standard library modules (json, pathlib, typing)

## Tips

1. **Place JSON files** in the `optimised_result/` folder before running
2. **Ensure cleaned_data.csv** is in the root directory
3. **Check validation errors** carefully - they indicate issues with optimizer output
4. **Results are saved** as TXT for easy reading and sharing
5. **API provides flexibility** for custom analysis workflows
