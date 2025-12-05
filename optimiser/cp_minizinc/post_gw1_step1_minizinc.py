"""
MiniZinc CP solver for FPL Post-GW1 Step 1.

This module provides a MiniZinc-based implementation of the CP subproblem
for optimizing FPL transfers, starters, and captain selection for gameweeks after GW1
using set-based modeling with transfer mechanics.
"""
import os
import sys
import math
import pandas as pd
from minizinc import Instance, Model, Solver
from data_prep import prepare_minizinc_parameters

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import process_post_gw1_solution


def calculate_selling_prices(players_df, p0_array, player_id_to_idx):
    """
    Calculate selling prices with 50% profit lock.
    
    sp_i = p^0_buy,i + ceil(0.5 * max(0, p_i - p^0_buy,i))
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, cost
    p0_array : list
        Purchase prices as 1-indexed array (INTEGER, scaled by 10)
    player_id_to_idx : dict
        Mapping from player_id to 1-based index
        
    Returns:
    --------
    dict : {player_id: selling_price} for all players (INTEGER, scaled by 10)
    """
    selling_prices = {}
    
    for _, row in players_df.iterrows():
        pid = row['player_id']
        current_price = int(round(float(row['cost'])))  # Integer, scaled by 10
        
        # Get purchase price from array
        idx = player_id_to_idx[pid]
        purchase_price = p0_array[idx - 1]  # Convert to 0-indexed for list access
        
        if current_price > purchase_price and purchase_price > 0:
            profit = current_price - purchase_price
            selling_prices[pid] = purchase_price + math.ceil(0.5 * profit)
        else:
            # If no profit or not purchased, selling price = current price
            selling_prices[pid] = current_price if purchase_price > 0 else 0
    
    return selling_prices


def calculate_upper_bound_post_gw1(players_df):
    """
    Calculate upper bound for net objective (raw points - penalty).
    
    Returns:
    --------
    int : Upper bound for net points (scaled by 10)
    """
    # Best possible raw points (same as Pre-GW1)
    available_df = players_df[players_df['unavailable'] == 0].copy()
    
    # Best 11 starters (1 GK + best 10 outfield)
    best_11 = available_df.nlargest(11, 'expected_points')['expected_points'].sum()
    captain_bonus = available_df['expected_points'].max()
    
    ub_raw = best_11 + captain_bonus
    # No penalty in best case (0 extra transfers)
    # Scale by 10 for integer arithmetic
    return int(ub_raw * 10) + 10  # Add buffer


def prepare_post_gw1_parameters(players_df, y0, p0, f, B_bank):
    """
    Convert pandas DataFrame and state to MiniZinc parameter dictionary for Post-GW1.
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, name, position, team, cost, 
                                expected_points, unavailable
    y0 : list
        Current squad state as 1-indexed array (0/1 values)
    p0 : list
        Purchase prices as 1-indexed array (INTEGER, scaled by 10)
    f : int
        Number of free transfers available
    B_bank : int
        Cash in bank (INTEGER, scaled by 10: e.g., 45 = £4.5m)
    
    Returns:
    --------
    dict : MiniZinc parameters ready for Instance assignment
    """
    # You already force len(players_df) == 638 with stable sorting → safe
    assert len(players_df) == 638, "Data must have exactly 638 players"
    assert len(y0) == 638 and len(p0) == 638

    params = prepare_minizinc_parameters(players_df)   # gives 1..638 arrays

    # Convert y0 list to bool array (1-indexed: y0[1] to y0[638])
    y0_bool = [bool(y0[i]) for i in range(638)]
    
    params.update({
        'y0':     y0_bool,  # Bool array of current squad membership
        'sp':     p0,       # already length 638, scaled ×10
        'f':      f,
        'B_bank': B_bank,
    })

    return params


def parse_post_gw1_output(result, players_df, y0, p0, f, B_bank):
    """
    Parse MiniZinc solution and convert to binary dictionaries with state updates.
    
    Parameters:
    -----------
    result : minizinc.Result
        Solution from MiniZinc solver
    players_df : pd.DataFrame
        Original DataFrame to map indices back to player_ids
    y0 : list
        Current squad state as 1-indexed array (0/1 values)
    p0 : list
        Current purchase prices as 1-indexed array (INTEGER, scaled by 10)
    f : int
        Current free transfers
    B_bank : int
        Current bank balance - INTEGER, scaled by 10
    
    Returns:
    --------
    dict : Solution containing:
        - 'x': {player_id: 0/1} - starters
        - 'c': {player_id: 0/1} - captain
        - 'y': {player_id: 0/1} - new squad
        - 'v': {player_id: 0/1} - vice-captain
        - 'b1': {player_id: 0/1} - bench position 1 (GK)
        - 'b2': {player_id: 0/1} - bench position 2
        - 'b3': {player_id: 0/1} - bench position 3
        - 'b4': {player_id: 0/1} - bench position 4
        - 't': {player_id: 0/1} - transfers in (computed from set diff)
        - 's': {player_id: 0/1} - transfers out (computed from set diff)
        - 'e': int - extra transfers
        - 'objective': float - objective value (scaled back to float)
        - 'y0': {player_id: 0/1} - updated squad state for next GW
        - 'p0': {player_id: price} - updated purchase prices for next GW
        - 'f': int - remaining free transfers for next GW
        - 'B_bank': int - updated bank balance for next GW (scaled by 10)
    """
    if not result.status.has_solution():
        raise ValueError(f"MiniZinc solver failed with status: {result.status}")
    
    # Get arrays and sets from MiniZinc output
    y_array = result['y']  # Bool array of new squad membership
    t_array = result['t']  # Bool array of transfers in
    s_array = result['s']  # Bool array of transfers out
    starters_set = result['Starters']
    captain_set = result['Captain']
    e_value = int(result['e'])
    objective = float(result['z']) / 10.0  # Scale back from integer
    
    # Create mappings
    player_ids = players_df['player_id'].tolist()
    player_id_to_idx = {pid: idx + 1 for idx, pid in enumerate(player_ids)}
    
    # Convert bool arrays to binary dictionaries (MiniZinc arrays are 1-indexed)
    y = {pid: (1 if y_array[player_id_to_idx[pid] - 1] else 0) for pid in player_ids}
    t = {pid: (1 if t_array[player_id_to_idx[pid] - 1] else 0) for pid in player_ids}
    s = {pid: (1 if s_array[player_id_to_idx[pid] - 1] else 0) for pid in player_ids}
    
    # Convert sets to binary dictionaries
    x = {pid: (1 if player_id_to_idx[pid] in starters_set else 0) for pid in player_ids}
    c = {pid: (1 if player_id_to_idx[pid] in captain_set else 0) for pid in player_ids}
    
    # Update purchase prices (p0) for next GW - INTEGER, scaled by 10
    # - If sold (s_i = 1): p0_new[i] = 0
    # - If bought (t_i = 1): p0_new[i] = current_price[i]
    # - Otherwise: p0_new[i] = p0[i] (unchanged)
    p0_new = {}
    player_dict = players_df.set_index('player_id').to_dict('index')
    
    for pid in player_ids:
        idx = player_id_to_idx[pid]
        if s[pid] == 1:
            p0_new[pid] = 0  # Sold
        elif t[pid] == 1:
            p0_new[pid] = int(round(player_dict[pid]['cost']))  # Bought at current price
        else:
            p0_new[pid] = p0[idx - 1]  # Unchanged (access list with 0-indexed)
    
    # Calculate selling prices for state update
    selling_prices = calculate_selling_prices(players_df, p0, player_id_to_idx)
    
    # Calculate total selling proceeds and purchase costs - INTEGER, scaled by 10
    total_selling_proceeds = sum(selling_prices[pid] * s[pid] for pid in player_ids)
    total_purchase_costs = sum(int(round(player_dict[pid]['cost'])) * t[pid] for pid in player_ids)
    
    # Update bank balance
    # B_bank_new = B_bank + selling_proceeds - purchase_costs
    B_bank_new = B_bank + total_selling_proceeds - total_purchase_costs
    
    # Calculate total transfers made
    total_transfers_made = sum(t.values())
    
    # Update free transfers for next GW
    # If used free transfers: f_new = 0
    # If didn't use all free transfers: f_new = min(2, 1 + (f - total_transfers_made))
    # Simplified: f_new = max(0, f - total_transfers_made)
    # But FPL rule: If you don't use free transfer, you get 2 max (carries over 1)
    if total_transfers_made <= f:
        # Used free transfers only (or less)
        remaining_free = f - total_transfers_made
        if remaining_free > 0:
            # Carry over 1 free transfer, base 1 for next week → min(2, 1 + 1) = 2
            f_new = min(2, 1 + remaining_free)
        else:
            # Used all free transfers → get 1 for next week
            f_new = 1
    else:
        # Used extra transfers (penalties applied) → get 1 for next week
        f_new = 1
    
    # Compute post-hoc assignments (vice-captain & bench positions)
    post_hoc = process_post_gw1_solution(players_df, x, y, c)
    
    solution = {
        # Decision variables (optimal solution)
        'x': x,  # Starters
        'c': c,  # Captain
        'y': y,  # New squad
        't': t,  # Transfers in
        's': s,  # Transfers out
        'e': e_value,  # Extra transfers
        'objective': objective,  # Objective value
        
        # Updated state for next GW
        'y0': y,  # New squad becomes next GW's starting squad
        'p0': p0_new,  # Updated purchase prices
        'f': f_new,  # Remaining/reset free transfers
        'B_bank': B_bank_new  # Updated bank balance
    }
    
    # Merge post-hoc assignments (v, b1, b2, b3, b4)
    solution.update(post_hoc)
    
    return solution


def optimize_post_gw1_step1_minizinc(players_df, y0, p0, f, B_bank, 
                                      solver_name='cp-sat', timeout_seconds=300):
    """
    Optimize transfers, starting XI, and captain for Post-GW1 using MiniZinc CP solver.
    
    This function uses the MiniZinc model with set-based formulation (no explicit transfer vars).
    Uses INTEGER arithmetic (scaled by 10).
    Penalty (4*e) included in objective during search (NOT post-hoc).
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, name, position, team, cost, 
                                expected_points, unavailable
        IMPORTANT: 
        - Each player_id must appear exactly ONCE.
        - Must have 'expected_points' column pre-calculated by the caller.
        - cost and expected_points will be scaled by 10 automatically
    y0 : dict
        Current squad state - {player_id: value} where value is 1 if in squad, 0 otherwise
        Dictionary for ALL players
    p0 : dict
        Purchase prices - {player_id: price} INTEGER scaled by 10 (e.g., 55 = £5.5m)
        Dictionary for ALL players (0 for players not in current squad)
    f : int
        Number of free transfers available
    B_bank : int
        Cash in bank INTEGER scaled by 10 (e.g., 45 = £4.5m)
    solver_name : str
        MiniZinc solver to use. Options: 'cp-sat', 'gecode', 'chuffed'
        Default: 'cp-sat' (recommended - extremely fast)
    timeout_seconds : int
        Maximum solve time in seconds. Default: 300 (5 minutes)
    
    Returns:
    --------
    dict : Solution containing:
        - 'x': {player_id: value} - x_i* ∈ {0,1} for all players (1 if starter, 0 otherwise)
        - 'c': {player_id: value} - c_i* ∈ {0,1} for all players (1 if captain, 0 otherwise)
        - 'y': {player_id: value} - y_i* ∈ {0,1} for all players (1 if in new squad, 0 otherwise)
        - 't': {player_id: value} - t_i* ∈ {0,1} for all players (1 if transfer in, 0 otherwise)
        - 's': {player_id: value} - s_i* ∈ {0,1} for all players (1 if transfer out, 0 otherwise)
        - 'e': int - e* extra transfers
        - 'objective': float - Objective value (expected points - penalty)
        - 'y0': {player_id: value} - Updated squad state for next GW
        - 'p0': {player_id: value} - Updated purchase prices for next GW
        - 'f': int - Remaining free transfers for next GW
        - 'B_bank': float - Updated bank balance for next GW
    
    Raises:
    -------
    ValueError: If player_id is duplicated or solver fails
    """
    # Validate: Ensure single gameweek data (no duplicate player_ids)
    if players_df['player_id'].duplicated().any():
        raise ValueError("More than 1 GW data detected. Each player_id must appear exactly once.")
    
    # Load the MiniZinc model
    model_path = os.path.join(os.path.dirname(__file__), 'post_gw1_step1.mzn')
    model = Model(model_path)
    
    # Get solver
    try:
        solver = Solver.lookup(solver_name)
    except LookupError:
        print(f"Warning: Solver '{solver_name}' not found. Trying 'cp-sat'...")
        try:
            solver = Solver.lookup('cp-sat')
        except LookupError:
            print("Warning: 'cp-sat' not found. Trying 'gecode'...")
            solver = Solver.lookup('gecode')
    
    # Create instance
    instance = Instance(solver, model)
    
    # Prepare MiniZinc parameters from DataFrame and state
    params = prepare_post_gw1_parameters(players_df, y0, p0, f, B_bank)
    
    # Assign parameters to instance
    instance['n_players'] = params['n_players']
    instance['UB'] = params['UB']
    instance['expected_points'] = params['expected_points']
    instance['cost'] = params['cost']
    instance['unavailable'] = params['unavailable']
    instance['PosPlayers'] = params['PosPlayers']
    instance['ClubPlayers'] = params['ClubPlayers']
    instance['y0'] = params['y0']
    instance['sp'] = params['sp']
    instance['B_bank'] = params['B_bank']
    instance['f'] = params['f']
    
    # Solve the model
    print(f"Solving Post-GW1 Step 1 with {solver.name} (timeout={timeout_seconds}s)...")
    try:
        result = instance.solve(timeout=pd.Timedelta(seconds=timeout_seconds))
    except Exception as e:
        print(f"ERROR during solve: {e}")
        raise
    
    # Check solution status
    if not result.status.has_solution():
        print(f"Solver status: {result.status}")
        if hasattr(result, 'statistics'):
            print(f"Statistics: {result.statistics}")
        raise ValueError(f"MiniZinc solver failed with status: {result.status}")
    
    print(f"Solution found! Status: {result.status}")
    print(f"Net Objective (after penalty): {float(result['z']) / 10.0:.2f} pts")
    print(f"Extra transfers penalty (e): {int(result['e'])}")
    
    # Parse output to binary dictionaries with state updates
    solution = parse_post_gw1_output(result, players_df, y0, p0, f, B_bank)
    
    # Print transfer info (computed from set diffs)
    num_transfers_in = sum(solution['t'].values())
    num_transfers_out = sum(solution['s'].values())
    print(f"Transfers: {num_transfers_in} in, {num_transfers_out} out")
    
    return solution


def display_solution(players_df, solution):
    """
    Display the Post-GW1 solution in a readable format.
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        Original player data
    solution : dict
        Solution from optimize_post_gw1_step1_minizinc()
    """
    player_dict = players_df.set_index('player_id').to_dict('index')
    
    # Extract sets
    squad_ids = [pid for pid, val in solution['y'].items() if val == 1]
    transfers_in_ids = [pid for pid, val in solution['t'].items() if val == 1]
    transfers_out_ids = [pid for pid, val in solution['s'].items() if val == 1]
    starter_ids = [pid for pid, val in solution['x'].items() if val == 1]
    captain_id = [pid for pid, val in solution['c'].items() if val == 1][0]
    
    # Display transfers
    print(f"\n{'='*70}")
    print(f"TRANSFERS ({len(transfers_in_ids)} in, {len(transfers_out_ids)} out):")
    print(f"{'='*70}")
    
    if transfers_out_ids:
        print(f"\nOUT ({len(transfers_out_ids)}):")
        for pid in transfers_out_ids:
            p = player_dict[pid]
            print(f"  ❌ {p['name']:30s} {p['position']:4s} £{p['cost']/10.0:.1f}m")
    else:
        print("\nOUT: None")
    
    if transfers_in_ids:
        print(f"\nIN ({len(transfers_in_ids)}):")
        for pid in transfers_in_ids:
            p = player_dict[pid]
            print(f"  ✅ {p['name']:30s} {p['position']:4s} £{p['cost']/10.0:.1f}m  {p['expected_points']:.2f}pts")
    else:
        print("\nIN: None")
    
    # Display squad
    print(f"\n{'='*70}")
    print(f"SQUAD ({len(squad_ids)} players):")
    print(f"{'='*70}")
    
    for pos in ['GK', 'DEF', 'MID', 'FWD']:
        pos_squad = [pid for pid in squad_ids if player_dict[pid]['position'] == pos]
        print(f"\n{pos} ({len(pos_squad)}):")
        for pid in sorted(pos_squad, key=lambda p: player_dict[p]['expected_points'], reverse=True):
            p = player_dict[pid]
            starter = "★" if solution['x'][pid] == 1 else " "
            captain = "(C)" if solution['c'][pid] == 1 else ""
            transfer = "NEW" if solution['t'].get(pid, 0) == 1 else ""
            print(f"  {starter} {p['name']:30s} £{p['cost']/10.0:.1f}m  {p['expected_points']:.2f}pts {captain} {transfer}")
    
    # Summary
    total_cost = sum(player_dict[pid]['cost'] for pid in squad_ids)
    total_points = sum(player_dict[pid]['expected_points'] for pid in starter_ids)
    total_points += player_dict[captain_id]['expected_points']  # Captain bonus
    
    print(f"\n{'='*70}")
    print(f"SUMMARY:")
    print(f"{'='*70}")
    print(f"Net Objective: {solution['objective']:.2f} pts (after penalty)")
    print(f"Raw Points (Starters + Captain): {total_points:.2f} pts")
    print(f"Extra Transfers Penalty: -{solution['e'] * 4} pts ({solution['e']} extra transfers)")
    print(f"Squad Size: {len(squad_ids)}")
    print(f"Starters: {len(starter_ids)}")
    print(f"Total Cost: £{total_cost/10.0:.1f}m / £100.0m")
    print(f"Captain: {player_dict[captain_id]['name']}")
    print(f"\nNext GW State:")
    print(f"  Bank: £{solution['B_bank']/10.0:.1f}m")
    print(f"  Free Transfers: {solution['f']}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    # Example usage
    print("This module should be imported and used with actual player data.")
    print("\nExample usage:")
    print("  from post_gw1_step1_minizinc import optimize_post_gw1_step1_minizinc, display_solution")
    print("  solution = optimize_post_gw1_step1_minizinc(players_df, y0, p0, f, B_bank)")
    print("  display_solution(players_df, solution)")
