import pandas as pd
import pulp
import sys
from pathlib import Path

# Add parent directory to path for importing utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import get_pulp_solver


def optimize_pre_gw1_step2(players_df, x_star, solver='CBC'):
    """
    Optimize bench composition for Pre-GW1 Step 2 with fixed starters from Step 1.
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, name, position, team, cost, expected_points
        IMPORTANT: 
        - Each player_id must appear exactly ONCE. If using multi-gameweek data,
          filter to a single gameweek first (e.g., players_df[players_df['GW'] == 1]).
        - Must have 'expected_points' column pre-calculated by the caller.
    x_star : dict
        x_i* from Step 1 - {player_id: value} where value is 1 if starter, 0 otherwise
    
    Returns:
    --------
    dict : Solution containing:
        - 'y': {player_id: value} - y_i** ∈ {0,1} for all players (1 if in squad, 0 otherwise)
    """
    
    # Extract fixed starters from Step 1's output
    fixed_starter_ids = [pid for pid, val in x_star.items() if val == 1]
    
    # Validate: Ensure single gameweek data (no duplicate player_ids)
    if players_df['player_id'].duplicated().any():
        raise ValueError("More than 1 GW data detected. Each player_id must appear exactly once.")
    
    # Create nested dictionary for efficient lookups (auto-includes ALL columns)
    player_ids = players_df['player_id'].tolist()
    players = players_df.set_index('player_id').to_dict('index')
    
    # Create the optimization problem
    prob = pulp.LpProblem("FPL_PreGW1_Step2", pulp.LpMaximize)
    
    # y_i: 1 if player i is in squad
    y = pulp.LpVariable.dicts("squad", player_ids, cat='Binary')
    
    # Objective: Maximize total expected points of squad
    prob += pulp.lpSum([
        players[pid]['expected_points'] * y[pid]
        for pid in player_ids
    ]), "Total_Squad_Expected_Points"
    
    # Squad constraints
    # Total squad size: 15 players
    prob += pulp.lpSum([y[pid] for pid in player_ids]) == 15, "Squad_Size"
    
    # Position quotas for squad
    gk_ids = players_df[players_df['position'] == 'GK']['player_id'].tolist()
    def_ids = players_df[players_df['position'] == 'DEF']['player_id'].tolist()
    mid_ids = players_df[players_df['position'] == 'MID']['player_id'].tolist()
    fwd_ids = players_df[players_df['position'] == 'FWD']['player_id'].tolist()
    
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
    
    # Fix starters from Step 1
    for pid in fixed_starter_ids:
        prob += y[pid] == 1, f"Fix_Starter_{pid}"
    
    # Solve the problem with selected solver
    prob.solve(get_pulp_solver(solver))
    
    # Extract solution
    if prob.status != pulp.LpStatusOptimal:
        raise ValueError(f"Optimization failed with status: {pulp.LpStatus[prob.status]}")
    
    # Extract squad composition
    # Force binary variables to integers to handle floating-point precision issues
    y_star = {pid: int(round(y[pid].varValue)) for pid in player_ids}
    
    # Initialize state for GW2 (Post-GW1)
    
    # p0_buy: purchase price for each player (cost if in squad, 0 otherwise)
    # Note: cost is in tenths of millions (e.g., 55 = £5.5m)
    p0_buy = {
        pid: (players[pid]['cost'] if y_star[pid] == 1 else 0)
        for pid in player_ids
    }
    
    # B_bank: cash in bank (1000 - total squad cost)
    # Note: All values in tenths of millions (1000 = £100m budget)
    total_cost = sum(players[pid]['cost'] * y_star[pid] for pid in player_ids)
    B_bank = 1000 - total_cost
    
    # f: free transfers for GW2 (1 per week + 1 banked)
    f = 2
    
    # Return complete solution with initial state for GW2
    solution = {
        # Decision variable
        'y': y_star,  # y_i** ∈ {0,1} ∀ i ∈ P (final squad)
        
        # Initial state for GW2
        'y0': y_star,
        'p0': p0_buy,
        'B_bank': B_bank,
        'f': f
    }
    
    return solution


if __name__ == "__main__":
    # Example usage
    print("This module should be imported and used with actual player data.")
