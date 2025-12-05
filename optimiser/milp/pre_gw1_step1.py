import pandas as pd
import pulp
import sys
from pathlib import Path

# Add parent directory to path for importing utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import get_pulp_solver


def optimize_pre_gw1_step1(players_df, solver='CBC'):
    """
    Optimize starting XI and captain for Pre-GW1 Step 1.
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, name, position, team, cost, expected_points, unavailable
        IMPORTANT: 
        - Each player_id must appear exactly ONCE. If using multi-gameweek data,
          filter to a single gameweek first (e.g., players_df[players_df['GW'] == 1]).
        - Must have 'expected_points' column pre-calculated by the caller.
    
    Returns:
    --------
    dict : Solution containing:
        - 'x': {player_id: value} - x_i* ∈ {0,1} for all players (1 if starter, 0 otherwise)
        - 'y': {player_id: value} - y_i* ∈ {0,1} for all players (1 if in squad, 0 otherwise)
        - 'c': {player_id: value} - c_i* ∈ {0,1} for all players (1 if captain, 0 otherwise)
    """
    
    # Validate: Ensure single gameweek data (no duplicate player_ids)
    if players_df['player_id'].duplicated().any():
        raise ValueError("More than 1 GW data detected. Each player_id must appear exactly once.")
    
    # Create nested dictionary for efficient lookups (auto-includes ALL columns)
    player_ids = players_df['player_id'].tolist()
    players = players_df.set_index('player_id').to_dict('index')
    
    # Create the optimization problem
    prob = pulp.LpProblem("FPL_PreGW1_Step1", pulp.LpMaximize)
    
    # y_i: 1 if player i is in squad
    y = pulp.LpVariable.dicts("squad", player_ids, cat='Binary')
    
    # x_i: 1 if player i is in starting XI
    x = pulp.LpVariable.dicts("starter", player_ids, cat='Binary')
    
    # c_i: 1 if player i is captain
    c = pulp.LpVariable.dicts("captain", player_ids, cat='Binary')
    
    # Objective: Maximize expected points from starters (x_i) and captain bonus (c_i)
    prob += pulp.lpSum([
        players[pid]['expected_points'] * (x[pid] + c[pid])
        for pid in player_ids
    ]), "Total_Expected_Points"
    
    # Constraint: Exactly 11 starters
    prob += pulp.lpSum([x[pid] for pid in player_ids]) == 11, "Lineup_Size"
    
    # Position constraints for starters
    gk_ids = players_df[players_df['position'] == 'GK']['player_id'].tolist()
    def_ids = players_df[players_df['position'] == 'DEF']['player_id'].tolist()
    mid_ids = players_df[players_df['position'] == 'MID']['player_id'].tolist()
    fwd_ids = players_df[players_df['position'] == 'FWD']['player_id'].tolist()
    
    # Exactly 1 starting GK
    prob += pulp.lpSum([x[pid] for pid in gk_ids]) == 1, "Starting_GK"
    
    # 3-5 starting DEF
    prob += pulp.lpSum([x[pid] for pid in def_ids]) >= 3, "Min_Starting_DEF"
    prob += pulp.lpSum([x[pid] for pid in def_ids]) <= 5, "Max_Starting_DEF"
    
    # 2-5 starting MID
    prob += pulp.lpSum([x[pid] for pid in mid_ids]) >= 2, "Min_Starting_MID"
    prob += pulp.lpSum([x[pid] for pid in mid_ids]) <= 5, "Max_Starting_MID"
    
    # 1-3 starting FWD
    prob += pulp.lpSum([x[pid] for pid in fwd_ids]) >= 1, "Min_Starting_FWD"
    prob += pulp.lpSum([x[pid] for pid in fwd_ids]) <= 3, "Max_Starting_FWD"
    
    # Constraint: Exactly 1 captain
    prob += pulp.lpSum([c[pid] for pid in player_ids]) == 1, "One_Captain"
    
    # Constraint: Captain must be a starter
    for pid in player_ids:
        prob += c[pid] <= x[pid], f"Captain_Must_Start_{pid}"
    
    # Constraint: Unavailable players cannot be starters
    # It is a more efficient way to express the constraint. i.e. for i with u_i = 1, x_i = 0
    unavailable_ids = players_df[players_df['unavailable'] == 1]['player_id'].tolist()
    for pid in unavailable_ids:
        prob += x[pid] == 0, f"Unavailable_Cannot_Start_{pid}"
    
    # Squad constraints
    # Total squad size: 15 players
    prob += pulp.lpSum([y[pid] for pid in player_ids]) == 15, "Squad_Size"
    
    # Position quotas for squad
    prob += pulp.lpSum([y[pid] for pid in gk_ids]) == 2, "Squad_GK"
    prob += pulp.lpSum([y[pid] for pid in def_ids]) == 5, "Squad_DEF"
    prob += pulp.lpSum([y[pid] for pid in mid_ids]) == 5, "Squad_MID"
    prob += pulp.lpSum([y[pid] for pid in fwd_ids]) == 3, "Squad_FWD"
    
    # Budget constraint (all values in tenths of millions, 1000 = £100m)
    prob += pulp.lpSum([
        players[pid]['cost'] * y[pid]
        for pid in player_ids
    ]) <= 1000, "Budget_Limit"
    
    # Club limits: max 3 players per club
    clubs = players_df['team'].unique()
    for club in clubs:
        club_players = players_df[players_df['team'] == club]['player_id'].tolist()
        prob += pulp.lpSum([y[pid] for pid in club_players]) <= 3, f"Club_Limit_{club}"
    
    # Constraint: Starters must be in squad
    for pid in player_ids:
        prob += x[pid] <= y[pid], f"Starter_In_Squad_{pid}"
    
    # Solve the problem with selected solver
    prob.solve(get_pulp_solver(solver))
    
    # Extract solution
    if prob.status != pulp.LpStatusOptimal:
        raise ValueError(f"Optimization failed with status: {pulp.LpStatus[prob.status]}")
    
    # Return complete solution in mathematical format (decision variables only)
    # Force binary variables to integers to handle floating-point precision issues
    solution = {
        'x': {pid: int(round(x[pid].varValue)) for pid in player_ids},  # x_i* ∈ {0,1} ∀ i ∈ P (starters)
        # 'y': {pid: y[pid].varValue for pid in player_ids},  # y_i* ∈ {0,1} ∀ i ∈ P (squad)
        'c': {pid: int(round(c[pid].varValue)) for pid in player_ids}   # c_i* ∈ {0,1} ∀ i ∈ P (captain)
    }
    
    return solution


if __name__ == "__main__":
    # Example usage
    print("This module should be imported and used with actual player data.")
