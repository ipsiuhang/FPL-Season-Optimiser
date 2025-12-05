# Optimizer Input/Output Reference

**Note:** All functions require `players_df` filtered to a single gameweek (no duplicate `player_id` entries).

## Main Orchestrator

### `run_season_optimizer.py`
**Input:** 
- `csv_path`: str - path to cleaned_data.csv (default: '../../cleaned_data.csv')
- `oracle`: bool - use actual points (True) or predicted points (False)

**Output:** 
- JSON file with complete solutions for all 38 gameweeks
- Each gameweek contains: x, y, c, v, b1, b2, b3, b4, y0, p0, B_bank, f

**Functionality:**
- Orchestrates optimization across all 38 gameweeks
- GW1: Pre-GW1 pipeline (step1 → step2 → post_hoc)
- GW2-38: Post-GW1 pipeline (step1 → post_hoc)
- Calculates expected_points once per gameweek based on oracle mode
- Manages state variables (y0, p0, B_bank, f) between gameweeks

## Pre-GW1

### `pre_gw1_step1.py`
**Input:** `players_df` (DataFrame)  
**Output:** 
- `x`: dict[player_id → {0,1}] - starters
- `c`: dict[player_id → {0,1}] - captain

### `pre_gw1_step2.py`
**Input:** `players_df` (DataFrame), `x_star` (dict)  
**Output:** 
- `y`: dict[player_id → {0,1}] - optimized squad
- `y0`: dict[player_id → {0,1}] - initial squad state
- `p0`: dict[player_id → float] - purchase prices (integer values in tenths of millions, e.g., 55.0 = £5.5m)
- `B_bank`: float - cash in bank (integer value in tenths of millions, e.g., 1000.0 = £100m)
- `f`: int - free transfers (0-5)

### `pre_gw1_post_hoc.py`
**Input:** `players_df` (DataFrame), `x_star`, `y2_star`, `c_star` (dicts)  
**Output:** 
- `v`: dict[player_id → {0,1}] - vice-captain
- `b1`: dict[player_id → {0,1}] - bench position 1
- `b2`: dict[player_id → {0,1}] - bench position 2
- `b3`: dict[player_id → {0,1}] - bench position 3
- `b4`: dict[player_id → {0,1}] - bench position 4

## Post-GW1

### `post_gw1_step1.py`
**Input:** `players_df` (DataFrame), `y0` (dict), `p0` (dict), `f` (int), `B_bank` (float)  
**Output:** 
- `x`: dict[player_id → {0,1}] - starters
- `y`: dict[player_id → {0,1}] - squad
- `c`: dict[player_id → {0,1}] - captain
- `y0`: dict[player_id → {0,1}] - updated squad state
- `p0`: dict[player_id → float] - updated purchase prices (integer values in tenths of millions)
- `f`: int - remaining free transfers (0-5)
- `B_bank`: float - updated cash in bank (integer value in tenths of millions)

### `post_gw1_post_hoc.py`
**Input:** `players_df` (DataFrame), `x_star`, `y_star`, `c_star` (dicts)  
**Output:** 
- `v`: dict[player_id → {0,1}] - vice-captain
- `b1`: dict[player_id → {0,1}] - bench position 1
- `b2`: dict[player_id → {0,1}] - bench position 2
- `b3`: dict[player_id → {0,1}] - bench position 3
- `b4`: dict[player_id → {0,1}] - bench position 4

## Variable Categories

**Solution variables** (for display): x, y, c, v, b1, b2, b3, b4 - all binary dicts  
**State variables** (carry between GWs): y0 (binary dict), p0 (float dict), B_bank (float), f (int)


# the output from season optimiser

{
  "gw1": {
    "x": {"1": 0, "2": 1, ..., "638": 0},    // All 638 players
    "y": {"1": 0, "2": 1, ..., "638": 0},    // All 638 players
    "c": {"1": 0, "2": 1, ..., "638": 0},    // All 638 players
    "v": {"1": 0, "2": 0, ..., "638": 0},    // All 638 players
    "b1": {"1": 0, "2": 0, ..., "638": 0},   // All 638 players
    "b2": {"1": 0, "2": 0, ..., "638": 0},   // All 638 players
    "b3": {"1": 0, "2": 0, ..., "638": 0},   // All 638 players
    "b4": {"1": 0, "2": 0, ..., "638": 0},   // All 638 players
    "y0": {"1": 0, "2": 1, ..., "638": 0},   // All 638 players
    "p0": {"1": 55, "2": 80, ..., "638": 65},  // All 638 players
    "B_bank": 5,
    "f": 1
  },
  "gw2": {
    // Same 12 keys, each with all 638 player IDs
  },
  ...
  "gw38": {
    // Same 12 keys, each with all 638 player IDs
  }
}


## JSON Key Definitions

### Binary Variables (all 638 players, values 0 or 1):

- **x**: Starting XI (11 players = 1)
- **y**: Full squad (15 players = 1)
- **c**: Captain (1 player = 1, gets double points)
- **v**: Vice-captain (1 player = 1)
- **b1**: 1st bench - backup GK
- **b2**: 2nd bench - best outfield sub
- **b3**: 3rd bench - middle outfield sub
- **b4**: 4th bench - worst outfield sub

### State Variables (for next GW):

- **y0**: Squad ownership (binary dict, 638 players)
- **p0**: Purchase prices (dict, in tenths of millions, e.g. 55 = £5.5m)
- **B_bank**: Cash in bank (scalar, tenths of millions)
- **f**: Free transfers available (scalar int)

Each gameweek has all 12 keys, with 10 dicts (638 players each) + 2 scalars.