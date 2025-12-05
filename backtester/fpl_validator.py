"""
FPL Team Validator

Validates Fantasy Premier League team selections against official FPL rules.
"""

from typing import Dict, List, Tuple
import pandas as pd


def validate_team(
    gw_df: pd.DataFrame,
    squad_ids: List[int],
    starter_ids: List[int],
    bench_ids: Dict[int, int],
    captain_id: int,
    vice_id: int
) -> Tuple[bool, str]:
    """
    Validate complete team selection in one comprehensive check.
    
    Args:
        gw_df: DataFrame with all players for this gameweek
        squad_ids: List of 15 player IDs in the squad
        starter_ids: List of 11 player IDs in starting XI
        bench_ids: Dict mapping bench position (1-4) to player ID
        captain_id: Player ID of captain
        vice_id: Player ID of vice-captain
        
    Returns:
        (is_valid, error_message): True if all valid, False with first error found
    """
    # 1. Validate squad size
    if len(squad_ids) != 15:
        return False, f"Squad must have exactly 15 players, found {len(squad_ids)}"
    
    # Get squad data
    squad_df = gw_df[gw_df['player_id'].isin(squad_ids)]
    
    # 2. Validate squad composition (2-5-5-3)
    position_counts = squad_df['position'].value_counts().to_dict()
    expected = {'GK': 2, 'DEF': 5, 'MID': 5, 'FWD': 3}
    
    for pos, count in expected.items():
        actual = position_counts.get(pos, 0)
        if actual != count:
            return False, f"Squad must have {count} {pos}, found {actual}"
    
    # 3. Validate max 3 players per club
    team_counts = squad_df['team'].value_counts()
    over_limit = team_counts[team_counts > 3]
    if len(over_limit) > 0:
        violations = ', '.join([f"{team}: {count}" for team, count in over_limit.items()])
        return False, f"Maximum 3 players per club. Violations: {violations}"
    
    # 4. Validate starting XI size
    if len(starter_ids) != 11:
        return False, f"Starting XI must have exactly 11 players, found {len(starter_ids)}"
    
    # Get starters data
    starters_df = gw_df[gw_df['player_id'].isin(starter_ids)]
    
    # 5. Validate starting XI formation
    starter_position_counts = starters_df['position'].value_counts().to_dict()
    
    gk = starter_position_counts.get('GK', 0)
    defn = starter_position_counts.get('DEF', 0)
    mid = starter_position_counts.get('MID', 0)
    fwd = starter_position_counts.get('FWD', 0)
    
    if gk != 1:
        return False, f"Starting XI must have exactly 1 GK, found {gk}"
    if defn < 3 or defn > 5:
        return False, f"Starting XI must have 3-5 DEF, found {defn}"
    if mid < 2 or mid > 5:
        return False, f"Starting XI must have 2-5 MID, found {mid}"
    if fwd < 1 or fwd > 3:
        return False, f"Starting XI must have 1-3 FWD, found {fwd}"
    
    # 6. Validate bench configuration
    if len(bench_ids) != 4:
        return False, f"Bench must have exactly 4 players, found {len(bench_ids)}"
    
    if sorted(bench_ids.keys()) != [1, 2, 3, 4]:
        return False, f"Bench positions must be [1,2,3,4], found {sorted(bench_ids.keys())}"
    
    # Position 1 must be GK
    pos1_id = bench_ids[1]
    pos1_player = gw_df[gw_df['player_id'] == pos1_id]
    if len(pos1_player) == 0:
        return False, f"Bench position 1 player (ID: {pos1_id}) not found"
    if pos1_player.iloc[0]['position'] != 'GK':
        return False, f"Bench position 1 must be GK, found {pos1_player.iloc[0]['position']}"
    
    # Positions 2-4 must be outfield
    for pos in [2, 3, 4]:
        player_id = bench_ids[pos]
        player = gw_df[gw_df['player_id'] == player_id]
        if len(player) == 0:
            return False, f"Bench position {pos} player (ID: {player_id}) not found"
        if player.iloc[0]['position'] == 'GK':
            return False, f"Bench position {pos} must be outfield player, found GK"
    
    # 7. Validate captaincy
    if captain_id == vice_id:
        return False, "Captain and vice-captain must be different players"
    if captain_id not in starter_ids:
        return False, f"Captain (ID: {captain_id}) must be in starting XI"
    if vice_id not in starter_ids:
        return False, f"Vice-captain (ID: {vice_id}) must be in starting XI"
    
    return True, ""

def validate_formation(players_df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Validate that a set of players forms a valid FPL formation.
    Used during substitution to check if adding a bench player is valid.
    
    Args:
        players_df: DataFrame of players (can be < 11 after non-playing starters removed)
        
    Returns:
        (is_valid, error_message): True if valid formation, False otherwise
    """
    position_counts = players_df['position'].value_counts().to_dict()
    
    gk = position_counts.get('GK', 0)
    defn = position_counts.get('DEF', 0)
    mid = position_counts.get('MID', 0)
    fwd = position_counts.get('FWD', 0)
    
    total = gk + defn + mid + fwd
    
    # Must have exactly 1 GK
    if gk != 1:
        return False, f"Formation must have exactly 1 GK, found {gk}"
    
    # Defenders: 3-5
    if defn < 3 or defn > 5:
        return False, f"Formation must have 3-5 DEF, found {defn}"
    
    # Midfielders: 2-5 (but only need to check if we have players)
    if total >= 4 and (mid < 2 or mid > 5):
        return False, f"Formation must have 2-5 MID, found {mid}"
    
    # Forwards: 1-3
    if total >= 5 and (fwd < 1 or fwd > 3):
        return False, f"Formation must have 1-3 FWD, found {fwd}"
    
    return True, ""
