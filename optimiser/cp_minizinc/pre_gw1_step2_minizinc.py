"""
MiniZinc CP solver for FPL Pre-GW1 Step 2.

This module provides a MiniZinc-based implementation of the CP subproblem
for optimizing FPL bench composition with fixed starters from Step 1.
"""
import os
import sys
import pandas as pd
from minizinc import Instance, Model, Solver
from data_prep import prepare_minizinc_parameters

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import process_pre_gw1_solution


def optimize_pre_gw1_step2_minizinc(players_df, x_star, c_star, solver_name='cp-sat', timeout_seconds=300):
    """
    Optimize bench composition for Pre-GW1 Step 2 with fixed starters from Step 1.
    
    This function uses the MiniZinc model with set-based formulation to solve
    the bench optimization problem, keeping starters from Step 1 fixed.
    NOTE: The model uses integer arithmetic (values scaled by 10 in data_prep.py)
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, name, position, team, cost, 
                                expected_points, unavailable
        IMPORTANT: 
        - Each player_id must appear exactly ONCE. If using multi-gameweek data,
          filter to a single gameweek first (e.g., players_df[players_df['GW'] == 1]).
        - Must have 'expected_points' column pre-calculated by the caller.
        - cost and expected_points will be scaled by 10 automatically
    x_star : dict
        x_i* from Step 1 - {player_id: value} where value is 1 if starter, 0 otherwise
    c_star : dict
        c_i* from Step 1 - {player_id: value} where value is 1 if captain, 0 otherwise
    solver_name : str
        MiniZinc solver to use. Options: 'cp-sat', 'gecode', 'chuffed'
        Default: 'cp-sat' (recommended - extremely fast)
    timeout_seconds : int
        Maximum solve time in seconds. Default: 300 (5 minutes)
    
    Returns:
    --------
    dict : Solution containing:
        - 'x': {player_id: value} - x_i* from Step 1 (starters)
        - 'c': {player_id: value} - c_i* from Step 1 (captain)
        - 'y': {player_id: value} - y_i** ∈ {0,1} for all players (1 if in squad, 0 otherwise)
        - 'v': {player_id: value} - v_i ∈ {0,1} for all players (1 if vice-captain)
        - 'b1': {player_id: value} - b1_i ∈ {0,1} for all players (1 if bench position 1)
        - 'b2': {player_id: value} - b2_i ∈ {0,1} for all players (1 if bench position 2)
        - 'b3': {player_id: value} - b3_i ∈ {0,1} for all players (1 if bench position 3)
        - 'b4': {player_id: value} - b4_i ∈ {0,1} for all players (1 if bench position 4)
        - 'objective': float - Objective value (total squad expected points)
        - 'y0': {player_id: value} - Initial state for GW2 (same as 'y')
        - 'p0': {player_id: value} - Purchase prices for GW2 state
        - 'B_bank': float - Cash in bank for GW2
        - 'f': int - Free transfers for GW2 (initially 2)
    
    Raises:
    -------
    ValueError: If player_id is duplicated or solver fails
    """
    # Validate: Ensure single gameweek data (no duplicate player_ids)
    if players_df['player_id'].duplicated().any():
        raise ValueError("More than 1 GW data detected. Each player_id must appear exactly once.")
    
    # Extract fixed starters from Step 1's output
    fixed_starter_ids = [pid for pid, val in x_star.items() if val == 1]
    
    if len(fixed_starter_ids) != 11:
        raise ValueError(f"Expected 11 fixed starters from Step 1, got {len(fixed_starter_ids)}")
    
    # Create mapping from player_id to 1-indexed position
    player_id_to_idx = {pid: idx + 1 for idx, pid in enumerate(players_df['player_id'])}
    
    # Create FixedStarters set (1-indexed)
    fixed_starters_set = set(player_id_to_idx[pid] for pid in fixed_starter_ids)
    
    # Create FixedStarterPartitions (per-position breakdown, 1-indexed)
    player_dict = players_df.set_index('player_id').to_dict('index')
    
    fixed_starter_partitions = {
        'GK': set(),
        'DEF': set(),
        'MID': set(),
        'FWD': set()
    }
    
    for pid in fixed_starter_ids:
        pos = player_dict[pid]['position']
        idx = player_id_to_idx[pid]
        fixed_starter_partitions[pos].add(idx)
    
    # Convert to array matching Position enum order: {GK, DEF, MID, FWD}
    fixed_starter_partitions_array = [
        fixed_starter_partitions['GK'],
        fixed_starter_partitions['DEF'],
        fixed_starter_partitions['MID'],
        fixed_starter_partitions['FWD']
    ]
    
    # Validate starter position counts
    if len(fixed_starter_partitions['GK']) != 1:
        raise ValueError(f"Expected 1 GK starter, got {len(fixed_starter_partitions['GK'])}")
    if not (3 <= len(fixed_starter_partitions['DEF']) <= 5):
        raise ValueError(f"Expected 3-5 DEF starters, got {len(fixed_starter_partitions['DEF'])}")
    if not (2 <= len(fixed_starter_partitions['MID']) <= 5):
        raise ValueError(f"Expected 2-5 MID starters, got {len(fixed_starter_partitions['MID'])}")
    if not (1 <= len(fixed_starter_partitions['FWD']) <= 3):
        raise ValueError(f"Expected 1-3 FWD starters, got {len(fixed_starter_partitions['FWD'])}")
    
    # Load the MiniZinc model
    model_path = os.path.join(os.path.dirname(__file__), 'pre_gw1_step2.mzn')
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
    
    # Prepare MiniZinc parameters from DataFrame (reuses Step 1's function)
    params = prepare_minizinc_parameters(players_df)
    
    # Assign base parameters to instance (same as Step 1)
    instance['n_players'] = params['n_players']
    instance['UB'] = params['UB']
    instance['expected_points'] = params['expected_points']
    instance['cost'] = params['cost']
    instance['unavailable'] = params['unavailable']
    instance['PosPlayers'] = params['PosPlayers']
    instance['ClubPlayers'] = params['ClubPlayers']
    
    # NEW: Assign Step 2-specific parameters (fixed starters from Step 1)
    instance['FixedStarters'] = fixed_starters_set
    instance['FixedStarterPartitions'] = fixed_starter_partitions_array
    
    # Solve the model
    print(f"Solving Step 2 with {solver.name} (timeout={timeout_seconds}s)...")
    print(f"Fixed starters: {len(fixed_starter_ids)} players")
    result = instance.solve(timeout=pd.Timedelta(seconds=timeout_seconds))
    
    # Check solution status
    if not result.status.has_solution():
        raise ValueError(f"MiniZinc solver failed with status: {result.status}")
    
    print(f"Solution found! Status: {result.status}")
    print(f"Objective: {float(result['z']) / 10.0:.2f} total squad expected points")
    
    # Parse output to binary dictionaries
    squad_set = result['Squad']
    player_ids = players_df['player_id'].tolist()
    
    # Create mapping from 1-indexed position to player_id
    idx_to_player_id = {idx + 1: pid for idx, pid in enumerate(player_ids)}
    
    # Convert squad set to binary dictionary
    y_star = {pid: (1 if (idx + 1) in squad_set else 0) for idx, pid in enumerate(player_ids)}
    
    # Verify all fixed starters are in final squad
    for pid in fixed_starter_ids:
        if y_star[pid] != 1:
            raise ValueError(f"Fixed starter {pid} not in final squad!")
    
    # Initialize state for GW2 (Post-GW1) - matching MILP implementation
    player_dict_full = players_df.set_index('player_id').to_dict('index')
    
    # p0_buy: purchase price for each player (cost if in squad, 0 otherwise)
    # Note: cost is already scaled by 10 in players_df (e.g., 55 = £5.5m)
    p0_buy = {
        pid: (int(round(player_dict_full[pid]['cost'])) if y_star[pid] == 1 else 0)
        for pid in player_ids
    }
    
    # B_bank: cash in bank (1000 - total squad cost)
    # Note: All values in tenths of millions (1000 = £100m budget)
    total_cost = sum(int(round(player_dict_full[pid]['cost'])) * y_star[pid] for pid in player_ids)
    B_bank = 1000 - total_cost
    
    # f: free transfers for GW2 (1 per week + 1 banked)
    f = 2
    
    # Calculate objective (expected_points are NOT scaled, so no division needed)
    objective = float(result['z'])
    
    # Compute post-hoc assignments (vice-captain & bench positions)
    # Note: y_star is y2_star (final squad), x_star is from step1, c_star is from step1
    post_hoc = process_pre_gw1_solution(players_df, x_star, y_star, c_star)
    
    # Return complete solution with initial state for GW2
    solution = {
        # Decision variables from Step 1 and Step 2
        'x': x_star,  # x_i* from Step 1 (starters)
        'c': c_star,  # c_i* from Step 1 (captain)
        'y': y_star,  # y_i** ∈ {0,1} ∀ i ∈ P (final squad from Step 2)
        'objective': objective,  # Total squad expected points
        
        # Initial state for GW2
        'y0': y_star,
        'p0': p0_buy,
        'B_bank': B_bank,
        'f': f
    }
    
    # Merge post-hoc assignments (v, b1, b2, b3, b4)
    solution.update(post_hoc)
    
    return solution


def display_solution_step2(players_df, solution, x_star):
    """
    Display the Step 2 solution in a readable format.
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        Original player data
    solution : dict
        Solution from optimize_pre_gw1_step2_minizinc()
    x_star : dict
        Starters from Step 1 (for comparison)
    """
    player_dict = players_df.set_index('player_id').to_dict('index')
    
    # Squad
    squad_ids = [pid for pid, val in solution['y'].items() if val == 1]
    starter_ids = [pid for pid, val in x_star.items() if val == 1]
    bench_ids = [pid for pid in squad_ids if pid not in starter_ids]
    
    print(f"\n{'='*60}")
    print(f"SQUAD OPTIMIZATION RESULT - STEP 2")
    print(f"{'='*60}")
    
    print(f"\nSTARTERS (Fixed from Step 1): {len(starter_ids)}")
    print("-" * 60)
    for pos in ['GK', 'DEF', 'MID', 'FWD']:
        pos_starters = [pid for pid in starter_ids if player_dict[pid]['position'] == pos]
        if pos_starters:
            print(f"\n{pos}:")
            for pid in sorted(pos_starters, key=lambda p: player_dict[p]['expected_points'], reverse=True):
                p = player_dict[pid]
                print(f"  ★ {p['name']:30s} £{p['cost']:.1f}m  {p['expected_points']:.2f}pts")
    
    print(f"\n{'='*60}")
    print(f"BENCH (Optimized in Step 2): {len(bench_ids)}")
    print("-" * 60)
    for pos in ['GK', 'DEF', 'MID', 'FWD']:
        pos_bench = [pid for pid in bench_ids if player_dict[pid]['position'] == pos]
        if pos_bench:
            print(f"\n{pos}:")
            for pid in sorted(pos_bench, key=lambda p: player_dict[p]['expected_points'], reverse=True):
                p = player_dict[pid]
                print(f"    {p['name']:30s} £{p['cost']:.1f}m  {p['expected_points']:.2f}pts")
    
    # Summary
    total_cost = sum(player_dict[pid]['cost'] for pid in squad_ids)
    total_squad_points = sum(player_dict[pid]['expected_points'] for pid in squad_ids)
    total_bench_points = sum(player_dict[pid]['expected_points'] for pid in bench_ids)
    
    print(f"\n{'='*60}")
    print(f"SUMMARY:")
    print(f"{'='*60}")
    print(f"Squad Size: {len(squad_ids)} (11 starters + {len(bench_ids)} bench)")
    print(f"Total Cost: £{total_cost:.1f}m / £100.0m")
    print(f"Remaining Budget: £{solution['B_bank']/10.0:.1f}m")
    print(f"Total Squad Points: {total_squad_points:.2f}")
    print(f"Bench Points: {total_bench_points:.2f}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # Example usage
    print("This module should be imported and used with actual player data.")
    print("\nExample usage:")
    print("  from pre_gw1_step2_minizinc import optimize_pre_gw1_step2_minizinc, display_solution_step2")
    print("  # First run Step 1 to get x_star")
    print("  solution_step2 = optimize_pre_gw1_step2_minizinc(players_df, x_star)")
    print("  display_solution_step2(players_df, solution_step2, x_star)")
