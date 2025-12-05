# the input from season optimiser

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

# the input from the cleaned data

## cleaned_data.csv Structure

### Columns (11 total):
```
player_id, gw, name, position, team, cost, points, eP, prob_showup, minutes, unavailable
```

### Column Details:

**player_id**: Integer 1-638 (player identifier)

**gw**: Game week 1-38

**name**: Player name (string)

**position**: GK, DEF, MID, FWD

**team**: Team name

**cost**: Player price in tenths (e.g., 55 = £5.5m)
- Reconciled from two sources via max()

**points**: Actual points scored that GW

**eP**: Expected points (predicted)
- Reconciled via closest to actual points

**prob_showup**: Probability of playing (0-1)
- Derived via sigmoid transformation of minutes

**minutes**: Minutes played (0-90)

**unavailable**: Binary flag
- 0 = real data
- 1 = imputed (player missing that GW)

### Dataset Properties:

- **~638 unique players** (appeared in ≥36 GWs)
- **~24,244 rows** (638 × 38 GWs)
- **Same player count in every GW** (standardized)
- Sorted by: gw, then player_id
- Missing GWs imputed with cost interpolation, stats=0, unavailable=1

### Key Processing:
- Filtered to consistent players only (≥36 GW appearances)
- Cost/eP reconciled from multiple conflicting sources
- Missing data imputed to ensure uniform player set across all 38 GWs


