"""
Data preparation utilities for MiniZinc CP solver.
Converts pandas DataFrame to MiniZinc parameter format.
"""
import pandas as pd
import re
import sys
import os

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import process_pre_gw1_solution


def calculate_upper_bound(players_df):
    """
    Calculate tight upper bound for objective function.
    
    UB = sum(top expected_points per position) + max(expected_points for captain)
    
    This provides a tight bound for the CP solver to improve pruning.
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, position, expected_points, unavailable
    
    Returns:
    --------
    int : Upper bound scaled by 10 for integer arithmetic
    """
    # Get available players only
    available_df = players_df[players_df['unavailable'] == 0].copy()
    
    # Top expected_points per position for squad
    top_gk = available_df[available_df['position'] == 'GK'].nlargest(2, 'expected_points')['expected_points'].sum()
    top_def = available_df[available_df['position'] == 'DEF'].nlargest(5, 'expected_points')['expected_points'].sum()
    top_mid = available_df[available_df['position'] == 'MID'].nlargest(5, 'expected_points')['expected_points'].sum()
    top_fwd = available_df[available_df['position'] == 'FWD'].nlargest(3, 'expected_points')['expected_points'].sum()
    
    # Best 11 starters (1 GK + best 10 outfield from squad)
    squad_expected = top_gk + top_def + top_mid + top_fwd
    best_11 = available_df.nlargest(11, 'expected_points')['expected_points'].sum()
    
    # Captain bonus: max expected_points
    captain_bonus = available_df['expected_points'].max()
    
    # UB = best possible starters + captain bonus
    ub = best_11 + captain_bonus
    
    # Scale by 10 for integer arithmetic, round up
    return int(ub * 10) + 10  # Add buffer


def create_position_sets(players_df):
    """
    Create position-partitioned sets for MiniZinc.
    
    Returns sets of player indices (1-indexed) for each position.
    Includes ALL players (both available and unavailable).
    Unavailability is handled via separate constraints in the model.
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, position, unavailable
    
    Returns:
    --------
    dict : {Position: set of ints} where Position in {GK, DEF, MID, FWD}
    """
    # Create mapping from player_id to 1-indexed position
    player_id_to_idx = {pid: idx + 1 for idx, pid in enumerate(players_df['player_id'])}
    
    # DEBUG: Check player_id range and mapping
    print(f"\n[DEBUG create_position_sets]")
    print(f"  DataFrame shape: {players_df.shape}")
    print(f"  player_id range: {players_df['player_id'].min()} to {players_df['player_id'].max()}")
    print(f"  First 5 player_ids: {players_df['player_id'].head().tolist()}")
    print(f"  Mapping (first 5): {dict(list(player_id_to_idx.items())[:5])}")
    print(f"  Mapping (last 5): {dict(list(player_id_to_idx.items())[-5:])}")
    
    # Build sets per position (1-indexed) - INCLUDE ALL PLAYERS
    pos_sets = {}
    for pos in ['GK', 'DEF', 'MID', 'FWD']:
        player_ids = players_df[players_df['position'] == pos]['player_id'].tolist()
        pos_sets[pos] = set(player_id_to_idx[pid] for pid in player_ids)
        print(f"  {pos}: {len(pos_sets[pos])} players, index range: {min(pos_sets[pos])} to {max(pos_sets[pos])}")
    
    return pos_sets


def create_club_sets(players_df):
    """
    Create club-partitioned sets for MiniZinc.
    
    Returns sets of player indices (1-indexed) for each club.
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, team
    
    Returns:
    --------
    dict : {club_index: set of ints} for clubs 1..20
    """
    # Get unique clubs and assign indices 1..20
    unique_clubs = sorted(players_df['team'].unique())
    club_to_idx = {club: idx + 1 for idx, club in enumerate(unique_clubs)}
    
    # Create mapping from player_id to 1-indexed position
    player_id_to_idx = {pid: idx + 1 for idx, pid in enumerate(players_df['player_id'])}
    
    # Build sets per club (1-indexed)
    club_sets = {}
    for club in unique_clubs:
        player_ids = players_df[players_df['team'] == club]['player_id'].tolist()
        club_sets[club_to_idx[club]] = set(player_id_to_idx[pid] for pid in player_ids)
    
    # Fill in empty clubs for 1..20 if needed
    for i in range(1, 21):
        if i not in club_sets:
            club_sets[i] = set()
    
    return club_sets


def prepare_minizinc_parameters(players_df):
    """
    Convert pandas DataFrame to MiniZinc parameter dictionary.
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, name, position, team, cost, 
                                expected_points, unavailable
    
    Returns:
    --------
    dict : MiniZinc parameters ready for Instance assignment
        NOTE: expected_points are scaled by 10; cost already scaled in data
    """
    # Data is already sorted
    player_ids = players_df['player_id'].tolist()
    n_players = len(player_ids)
    
    # Create sequential 1-based mapping: player_id -> 1..n_players
    player_id_to_idx = {pid: idx + 1 for idx, pid in enumerate(player_ids)}
    
    # Build arrays with sequential 1-based indices
    expected_points = [0] * (n_players + 1)  # Index 0 unused
    cost = [0] * (n_players + 1)
    unavailable = [False] * (n_players + 1)
    
    for pid in player_ids:
        idx = player_id_to_idx[pid]
        row = players_df[players_df['player_id'] == pid].iloc[0]
        # Expected points: NOT scaled in data → multiply by 10
        expected_points[idx] = int(round(float(row['expected_points']) * 10))
        # Cost: ALREADY scaled in data → just convert to int
        cost[idx] = int(round(float(row['cost'])))
        unavailable[idx] = bool(row['unavailable'])
    
    # Build position sets with sequential indices
    pos_players_dict = {}
    for pos in ['GK', 'DEF', 'MID', 'FWD']:
        pos_ids = players_df[players_df['position'] == pos]['player_id'].tolist()
        pos_players_dict[pos] = {player_id_to_idx[pid] for pid in pos_ids}
    
    pos_players = [
        pos_players_dict['GK'],
        pos_players_dict['DEF'],
        pos_players_dict['MID'],
        pos_players_dict['FWD']
    ]
    
    # Build club sets with sequential indices
    unique_clubs = sorted(players_df['team'].unique())
    club_to_idx = {club: idx + 1 for idx, club in enumerate(unique_clubs)}
    club_players_dict = {club_to_idx[club]: set() for club in unique_clubs}
    
    for pid in player_ids:
        club = players_df[players_df['player_id'] == pid]['team'].values[0]
        idx = player_id_to_idx[pid]
        club_players_dict[club_to_idx[club]].add(idx)
    
    # Fill empty clubs up to 20
    club_players = [club_players_dict.get(i, set()) for i in range(1, 21)]
    
    # Calculate upper bound (already returns scaled int)
    ub = calculate_upper_bound(players_df)
    
    # DEBUG
    print(f"\n[DEBUG prepare_minizinc_parameters]")
    print(f"  n_players: {n_players}")
    print(f"  player_ids range: {min(player_ids)} to {max(player_ids)}")
    print(f"  expected_points array length: {len(expected_points[1:])}")
    print(f"  cost array length: {len(cost[1:])}")
    print(f"  PosPlayers sets:")
    for i, pos_set in enumerate(pos_players):
        if pos_set:
            print(f"    Position {i}: {len(pos_set)} players, range {min(pos_set)} to {max(pos_set)}")
    print(f"  ClubPlayers sets:")
    for i, club_set in enumerate(club_players):
        if club_set:
            print(f"    Club {i+1}: {len(club_set)} players, range {min(club_set)} to {max(club_set)}")
    
    # Return parameter dictionary
    params = {
        'n_players': n_players,
        'UB': ub,  # Already scaled by calculate_upper_bound()
        'expected_points': expected_points[1:],  # 1..n_players, SCALED
        'cost': cost[1:],  # 1..n_players, ALREADY SCALED
        'unavailable': unavailable[1:],
        'PosPlayers': pos_players,  # Array indexed by Position enum
        'ClubPlayers': club_players  # Array indexed 1..20
    }
    
    return params


def parse_minizinc_output(result, players_df):
    """
    Parse MiniZinc solution and convert to binary dictionaries.
    
    Parameters:
    -----------
    result : minizinc.Result
        Solution from MiniZinc solver
    players_df : pd.DataFrame
        Original DataFrame to map indices back to player_ids
    
    Returns:
    --------
    dict : Solution containing:
        - 'x': {player_id: 0/1} - starters
        - 'c': {player_id: 0/1} - captain
        - 'y': {player_id: 0/1} - squad (for compatibility)
        - 'v': {player_id: 0/1} - vice-captain
        - 'b1': {player_id: 0/1} - bench position 1 (GK)
        - 'b2': {player_id: 0/1} - bench position 2
        - 'b3': {player_id: 0/1} - bench position 3
        - 'b4': {player_id: 0/1} - bench position 4
        - 'objective': float - objective value
    """
    if result.status.has_solution():
        # Get sets from MiniZinc output
        squad_set = result['Squad']
        starters_set = result['Starters']
        captain_set = result['Captain']
        objective = float(result['z']) / 10.0  # Scale back from integer
        
        # Create mapping from 1-indexed position to player_id
        idx_to_player_id = {idx + 1: pid for idx, pid in enumerate(players_df['player_id'])}
        player_ids = players_df['player_id'].tolist()
        
        # Convert sets to binary dictionaries
        y = {pid: (1 if (idx + 1) in squad_set else 0) for idx, pid in enumerate(player_ids)}
        x = {pid: (1 if (idx + 1) in starters_set else 0) for idx, pid in enumerate(player_ids)}
        c = {pid: (1 if (idx + 1) in captain_set else 0) for idx, pid in enumerate(player_ids)}
        
        # Compute post-hoc assignments (vice-captain & bench positions)
        post_hoc = process_pre_gw1_solution(players_df, x, y, c)
        
        solution = {
            'x': x,
            'c': c,
            'y': y,  # Include squad for compatibility
            'objective': objective
        }
        
        # Merge post-hoc assignments
        solution.update(post_hoc)
        
        return solution
    else:
        raise ValueError(f"MiniZinc solver failed with status: {result.status}")


if __name__ == "__main__":
    print("This module provides data preparation utilities for MiniZinc CP solver.")
    print("Use: from data_prep import prepare_minizinc_parameters, parse_minizinc_output")
