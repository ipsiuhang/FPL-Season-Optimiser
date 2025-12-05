import pandas as pd
import pulp
import math
import sys
from pathlib import Path

# Add parent directory to path for importing utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import get_pulp_solver


def optimize_post_gw1_step1(players_df, y0, p0, f, B_bank, solver='CBC'):
    """
    Optimize starting XI, captain, and transfers for Post-GW1.
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, name, position, team, cost, expected_points, unavailable
        IMPORTANT: Must have 'expected_points' column pre-calculated by the caller.
    y0 : dict
        Current squad state - {player_id: value} where value is 1 if in squad, 0 otherwise (y_i^0)
        Dictionary for ALL players
    p0 : dict
        Purchase prices - {player_id: price} where price is in tenths of millions (p^0_buy,i)
        Dictionary for ALL players (0 for players not in current squad)
        Note: 55 = £5.5m
    f : int
        Number of free transfers available 
    B_bank : float
        Cash in bank in tenths of millions
        Note: 1000 = £100m budget

    dict : Solution containing:
        - 'x': {player_id: value} - x_i* ∈ {0,1} for all players (starters)
        - 'y': {player_id: value} - y_i* ∈ {0,1} for all players (squad)
        - 'c': {player_id: value} - c_i* ∈ {0,1} for all players (captain)
        - 't': {player_id: value} - t_i* ∈ {0,1} for all players (transfers in)
        - 's': {player_id: value} - s_i* ∈ {0,1} for all players (transfers out)
        - 'e': int - e* extra transfers beyond free transfers
        - 'y0': {player_id: value} - Updated squad state for next GW
        - 'p0': {player_id: value} - Updated purchase prices for next GW
        - 'f': int - Remaining free transfers for next GW
        - 'B_bank': float - Updated bank balance for next GW (in tenths of millions)
    """
    
    # Validate: Ensure single gameweek data (no duplicate player_ids)
    if players_df['player_id'].duplicated().any():
        raise ValueError("More than 1 GW data detected. Each player_id must appear exactly once.")
    
    # Create nested dictionary for efficient lookups (auto-includes ALL columns)
    player_ids = players_df['player_id'].tolist()
    players = players_df.set_index('player_id').to_dict('index')
    
    # Calculate selling prices with 50% profit lock (sp_i)
    # sp_i = p^0_buy,i + ceil(0.5 * max(0, p_i - p^0_buy,i))
    # Note: All prices in tenths of millions, FPL always rounds up
    selling_prices = {}
    for pid in player_ids:
        current_price = players[pid]['cost']
        purchase_price = p0[pid]
        
        if current_price > purchase_price:
            profit = current_price - purchase_price
            selling_prices[pid] = purchase_price + math.ceil(0.5 * profit)
        else:
            selling_prices[pid] = current_price
    
    # Create the optimization problem
    prob = pulp.LpProblem("FPL_PostGW1_Step1", pulp.LpMaximize)
    
    # Decision variables
    # y_i: 1 if player i is in new squad
    y = pulp.LpVariable.dicts("squad", player_ids, cat='Binary')
    
    # x_i: 1 if player i is in starting XI
    x = pulp.LpVariable.dicts("starter", player_ids, cat='Binary')
    
    # c_i: 1 if player i is captain
    c = pulp.LpVariable.dicts("captain", player_ids, cat='Binary')
    
    # t_i: 1 if buy player i (transfer in)
    t = pulp.LpVariable.dicts("transfer_in", player_ids, cat='Binary')
    
    # s_i: 1 if sell player i (transfer out)
    s = pulp.LpVariable.dicts("transfer_out", player_ids, cat='Binary')
    
    # e: number of extra transfers beyond free_transfers (penalty)
    e = pulp.LpVariable("extra_transfers", lowBound=0, upBound=15, cat='Integer')
    
    # Objective: Maximize expected points minus transfer penalty
    prob += pulp.lpSum([
        players[pid]['expected_points'] * (x[pid] + c[pid])
        for pid in player_ids
    ]) - 4 * e, "Total_Expected_Points_Minus_Penalty"
    
    # Lineup constraints
    prob += pulp.lpSum([x[pid] for pid in player_ids]) == 11, "Lineup_Size"
    
    # Position constraints for starters
    gk_ids = [pid for pid in player_ids if players[pid]['position'] == 'GK']
    def_ids = [pid for pid in player_ids if players[pid]['position'] == 'DEF']
    mid_ids = [pid for pid in player_ids if players[pid]['position'] == 'MID']
    fwd_ids = [pid for pid in player_ids if players[pid]['position'] == 'FWD']
    
    prob += pulp.lpSum([x[pid] for pid in gk_ids]) == 1, "Starting_GK"
    prob += pulp.lpSum([x[pid] for pid in def_ids]) >= 3, "Min_Starting_DEF"
    prob += pulp.lpSum([x[pid] for pid in def_ids]) <= 5, "Max_Starting_DEF"
    prob += pulp.lpSum([x[pid] for pid in mid_ids]) >= 2, "Min_Starting_MID"
    prob += pulp.lpSum([x[pid] for pid in mid_ids]) <= 5, "Max_Starting_MID"
    prob += pulp.lpSum([x[pid] for pid in fwd_ids]) >= 1, "Min_Starting_FWD"
    prob += pulp.lpSum([x[pid] for pid in fwd_ids]) <= 3, "Max_Starting_FWD"
    
    # Captain constraints
    prob += pulp.lpSum([c[pid] for pid in player_ids]) == 1, "One_Captain"
    for pid in player_ids:
        prob += c[pid] <= x[pid], f"Captain_Must_Start_{pid}"
    
    # Unavailable players cannot be starters
    unavailable_ids = [pid for pid in player_ids if players[pid].get('unavailable', 0) == 1]
    for pid in unavailable_ids:
        prob += x[pid] == 0, f"Unavailable_Cannot_Start_{pid}"
    
    # Squad constraints
    prob += pulp.lpSum([y[pid] for pid in player_ids]) == 15, "Squad_Size"
    prob += pulp.lpSum([y[pid] for pid in gk_ids]) == 2, "Squad_GK"
    prob += pulp.lpSum([y[pid] for pid in def_ids]) == 5, "Squad_DEF"
    prob += pulp.lpSum([y[pid] for pid in mid_ids]) == 5, "Squad_MID"
    prob += pulp.lpSum([y[pid] for pid in fwd_ids]) == 3, "Squad_FWD"
    
    # Dynamic budget constraint from mathematical model (Section 2.2):
    # Σ p_j t_j ≤ B_bank + Σ sp_i s_i
    # Cost of new purchases ≤ cash in bank + selling proceeds
    # Note: All values in tenths of millions 
    prob += pulp.lpSum([
        players[pid]['cost'] * t[pid]
        for pid in player_ids
    ]) <= B_bank + pulp.lpSum([
        selling_prices[pid] * s[pid]
        for pid in player_ids
    ]), "Budget_Limit"
    
    # Club limits: max 3 players per club
    clubs = players_df['team'].unique()
    for club in clubs:
        club_players = players_df[players_df['team'] == club]['player_id'].tolist()
        prob += pulp.lpSum([y[pid] for pid in club_players]) <= 3, f"Club_Limit_{club}"
    
    # Starters must be in squad
    for pid in player_ids:
        prob += x[pid] <= y[pid], f"Starter_In_Squad_{pid}"
    
    # Transfer logic
    # y_i = y_i^0 + t_i - s_i (squad update)
    for pid in player_ids:
        prob += y[pid] == y0[pid] + t[pid] - s[pid], f"Squad_Update_{pid}"
    
    # No simultaneous buy and sell of same player
    for pid in player_ids:
        prob += t[pid] + s[pid] <= 1, f"No_Simultaneous_Transfer_{pid}"
    
    # Can only buy players not in current squad
    for pid in player_ids:
        prob += t[pid] <= 1 - y0[pid], f"Buy_Only_Non_Squad_{pid}"
    
    # Can only sell players in current squad
    for pid in player_ids:
        prob += s[pid] <= y0[pid], f"Sell_Only_Current_Squad_{pid}"
    
    # Extra transfers calculation
    prob += e >= pulp.lpSum([t[pid] for pid in player_ids]) - f, "Extra_Transfers"
    
    # Logical upper bound on transfers
    prob += pulp.lpSum([t[pid] for pid in player_ids]) <= 15, "Max_Transfers"
    
    # Solve the problem with selected solver
    prob.solve(get_pulp_solver(solver))
    
    # Extract solution
    if prob.status != pulp.LpStatusOptimal:
        raise ValueError(f"Optimization failed with status: {pulp.LpStatus[prob.status]}")
    
    # Extract optimal decision variables (Section 2.2.5)
    # Force binary variables to integers to handle floating-point precision issues
    x_star = {pid: int(round(x[pid].varValue)) for pid in player_ids}
    y_star = {pid: int(round(y[pid].varValue)) for pid in player_ids}
    c_star = {pid: int(round(c[pid].varValue)) for pid in player_ids}
    t_star = {pid: int(round(t[pid].varValue)) for pid in player_ids}
    s_star = {pid: int(round(s[pid].varValue)) for pid in player_ids}
    e_star = int(round(e.varValue))
    
    # State updates for next GW (Section 2.2.5)
    # Calculate total transfers made
    total_transfers_made = int(sum(t_star.values()))
    
    # Update purchase prices: p^0_buy,i ← 0 if sold, p_i if bought, unchanged otherwise
    for pid in player_ids:
        if s_star[pid]:
            p0[pid] = 0
        elif t_star[pid]:
            p0[pid] = players[pid]['cost']
    
    # Calculate bank balance update: B_bank^new = B_bank + Σ sp_i*s_i* - Σ p_j*t_j*
    total_selling_proceeds = sum(selling_prices[pid] * s_star[pid] for pid in player_ids)
    total_purchase_costs = sum(players[pid]['cost'] * t_star[pid] for pid in player_ids)
    
    # Calculate remaining free transfers
    remaining_free_transfers = max(0, f - total_transfers_made)
    
    # Return decision variables and updated state
    solution = {
        # Decision variables (optimal solution)
        'x': x_star,  # x_i* ∈ {0,1} ∀ i (starters)
        'y': y_star,  # y_i* ∈ {0,1} ∀ i (squad)
        'c': c_star,  # c_i* ∈ {0,1} ∀ i (captain)
        # 't': t_star,  # t_i* ∈ {0,1} ∀ i (transfers in)
        # 's': s_star,  # s_i* ∈ {0,1} ∀ i (transfers out)
        # 'e': e_star,  # e* ∈ ℤ (extra transfers)
        
        # Updated state for next GW (Section 2.2.5)
        'y0': y_star,  # New squad becomes next GW's starting squad
        'p0': p0,  # Updated purchase prices
        'f': remaining_free_transfers,  # Remaining free transfers
        'B_bank': B_bank + total_selling_proceeds - total_purchase_costs  # B_bank^new = B_bank + Σ sp_i*s_i* - Σ p_j*t_j*
    }
    
    return solution


if __name__ == "__main__":
    # Example usage
    print("This module should be imported and used with actual player data.")
