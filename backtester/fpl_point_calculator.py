"""
FPL Point Calculator

Calculates Fantasy Premier League gameweek points with automatic substitutions
and captain doubling.
"""

from typing import Dict, List, Tuple
import pandas as pd
from .fpl_validator import validate_formation


def calculate_gameweek_points(
    gw_df: pd.DataFrame,
    starter_ids: List[int],
    bench_ids: Dict[int, int],
    captain_id: int,
    vice_id: int
) -> Tuple[int, pd.DataFrame, Dict]:
    """
    Calculate total points for a gameweek with automatic substitutions.
    
    Args:
        gw_df: DataFrame with all players for this gameweek
        starter_ids: List of 11 player IDs in starting XI
        bench_ids: Dict mapping bench position (1-4) to player ID
        captain_id: Player ID of captain
        vice_id: Player ID of vice-captain
        
    Returns:
        (total_points, final_active_df, details): 
            - total_points: Total points including captain bonus
            - final_active_df: Final active lineup after substitutions
            - details: Dict with breakdown (captain_points, subs_made, etc.)
    """
    # Get starters and bench data
    starters_df = gw_df[gw_df['player_id'].isin(starter_ids)].copy()
    
    # Step 1: Remove non-playing starters (minutes = 0)
    active_players = starters_df[starters_df['minutes'] > 0].copy()
    
    # If no one played, return 0 points
    if len(active_players) == 0:
        return 0, active_players, {
            'substitutions': [],
            'captain_played': False,
            'vice_played': False,
            'captain_points': 0
        }
    
    # Track substitutions made
    substitutions = []
    
    # Step 2: Process bench in order (positions 1 -> 2 -> 3 -> 4)
    for bench_pos in [1, 2, 3, 4]:
        # Stop if we have 11 active players
        if len(active_players) >= 11:
            break
        
        # Get the bench player at this position
        player_id = bench_ids[bench_pos]
        bench_player_row = gw_df[gw_df['player_id'] == player_id]
        
        # Skip if player didn't play
        if bench_player_row.iloc[0]['minutes'] == 0:
            continue
        
        bench_player = bench_player_row.iloc[0]
        
        # Try adding this bench player
        test_lineup = pd.concat([active_players, bench_player.to_frame().T], ignore_index=True)
        
        # Check if formation would be valid
        is_valid, _ = validate_formation(test_lineup)
        
        if is_valid:
            # Add the player
            active_players = test_lineup
            substitutions.append({
                'player_id': bench_player['player_id'],
                'name': bench_player['name'],
                'position': bench_player['position'],
                'bench_pos': bench_pos,
                'points': bench_player['points']
            })
    
    # Step 3: Calculate base points
    base_points = active_players['points'].sum()
    
    # Step 4: Apply captain doubling
    captain_played = captain_id in active_players['player_id'].values
    vice_played = vice_id in active_players['player_id'].values
    
    captain_bonus = 0
    captain_used = None
    
    if captain_played:
        captain_points = active_players[active_players['player_id'] == captain_id]['points'].iloc[0]
        captain_bonus = captain_points  # Double means add points once more
        captain_used = 'captain'
    elif vice_played:
        vice_points = active_players[active_players['player_id'] == vice_id]['points'].iloc[0]
        captain_bonus = vice_points
        captain_used = 'vice'
    
    total_points = base_points + captain_bonus
    
    # Return details
    details = {
        'substitutions': substitutions,
        'captain_played': captain_played,
        'vice_played': vice_played,
        'captain_used': captain_used,
        'captain_bonus': captain_bonus,
        'base_points': base_points,
        'num_active_players': len(active_players)
    }
    
    return int(total_points), active_players, details


def format_lineup_summary(active_df: pd.DataFrame, captain_id: int, vice_id: int) -> str:
    """
    Format the active lineup into a readable string.
    
    Args:
        active_df: DataFrame of active players
        captain_id: Captain player ID
        vice_id: Vice-captain player ID
        
    Returns:
        Formatted string of lineup
    """
    lines = []
    
    # Group by position
    for position in ['GK', 'DEF', 'MID', 'FWD']:
        pos_players = active_df[active_df['position'] == position].sort_values('name')
        if len(pos_players) > 0:
            for _, player in pos_players.iterrows():
                marker = ''
                if player['player_id'] == captain_id:
                    marker = ' (C)'
                elif player['player_id'] == vice_id:
                    marker = ' (VC)'
                
                lines.append(
                    f"  {player['position']}: {player['name']}{marker} - "
                    f"{player['points']}pts ({player['minutes']}min)"
                )
    
    return '\n'.join(lines)
