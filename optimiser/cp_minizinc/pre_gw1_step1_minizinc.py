"""
MiniZinc CP solver for FPL Pre-GW1 Step 1.

This module provides a MiniZinc-based implementation of the CP subproblem
for optimizing FPL squad and lineup selection using set-based modeling
with symmetry breaking.
"""
import os
import pandas as pd
from minizinc import Instance, Model, Solver
from data_prep import prepare_minizinc_parameters, parse_minizinc_output


def optimize_pre_gw1_step1_minizinc(players_df, solver_name='cp-sat', timeout_seconds=300):
    """
    Optimize starting XI and captain for Pre-GW1 Step 1 using MiniZinc CP solver.
    
    This function uses the MiniZinc model with set-based formulation and 
    symmetry breaking to solve the FPL optimization problem.
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
        - 'y': {player_id: value} - y_i* ∈ {0,1} for all players (1 if in squad, 0 otherwise)
        - 'objective': float - Objective value (expected points)
    
    Raises:
    -------
    ValueError: If player_id is duplicated or solver fails
    """
    # Validate: Ensure single gameweek data (no duplicate player_ids)
    if players_df['player_id'].duplicated().any():
        raise ValueError("More than 1 GW data detected. Each player_id must appear exactly once.")
    
    # Load the MiniZinc model
    model_path = os.path.join(os.path.dirname(__file__), 'pre_gw1_step1.mzn')
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
    
    # Prepare MiniZinc parameters from DataFrame
    params = prepare_minizinc_parameters(players_df)
    
    # Assign parameters to instance
    instance['n_players'] = params['n_players']
    instance['UB'] = params['UB']
    instance['expected_points'] = params['expected_points']
    instance['cost'] = params['cost']
    instance['unavailable'] = params['unavailable']
    instance['PosPlayers'] = params['PosPlayers']
    instance['ClubPlayers'] = params['ClubPlayers']
    
    # Solve the model
    print(f"Solving with {solver.name} (timeout={timeout_seconds}s)...")
    result = instance.solve(timeout=pd.Timedelta(seconds=timeout_seconds))
    
    # Check solution status
    if not result.status.has_solution():
        raise ValueError(f"MiniZinc solver failed with status: {result.status}")
    
    print(f"Solution found! Status: {result.status}")
    print(f"Objective: {float(result['z']) / 10.0:.2f} expected points")
    
    # Parse output to binary dictionaries
    solution = parse_minizinc_output(result, players_df)
    
    return solution


def display_solution(players_df, solution):
    """
    Display the solution in a readable format.
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        Original player data
    solution : dict
        Solution from optimize_pre_gw1_step1_minizinc()
    """
    player_dict = players_df.set_index('player_id').to_dict('index')
    
    # Squad
    squad_ids = [pid for pid, val in solution['y'].items() if val == 1]
    print(f"\n{'='*60}")
    print(f"SQUAD ({len(squad_ids)} players):")
    print(f"{'='*60}")
    
    for pos in ['GK', 'DEF', 'MID', 'FWD']:
        pos_squad = [pid for pid in squad_ids if player_dict[pid]['position'] == pos]
        print(f"\n{pos} ({len(pos_squad)}):")
        for pid in sorted(pos_squad, key=lambda p: player_dict[p]['expected_points'], reverse=True):
            p = player_dict[pid]
            starter = "★" if solution['x'][pid] == 1 else " "
            captain = "(C)" if solution['c'][pid] == 1 else ""
            print(f"  {starter} {p['name']:30s} £{p['cost']:.1f}m  {p['expected_points']:.2f}pts {captain}")
    
    # Starters
    starter_ids = [pid for pid, val in solution['x'].items() if val == 1]
    captain_id = [pid for pid, val in solution['c'].items() if val == 1][0]
    
    total_cost = sum(player_dict[pid]['cost'] for pid in squad_ids)
    total_points = sum(player_dict[pid]['expected_points'] for pid in starter_ids)
    total_points += player_dict[captain_id]['expected_points']  # Captain bonus
    
    print(f"\n{'='*60}")
    print(f"SUMMARY:")
    print(f"{'='*60}")
    print(f"Squad Size: {len(squad_ids)}")
    print(f"Starters: {len(starter_ids)}")
    print(f"Total Cost: £{total_cost:.1f}m / £100.0m")
    print(f"Expected Points: {total_points:.2f}")
    print(f"Captain: {player_dict[captain_id]['name']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # Example usage
    print("This module should be imported and used with actual player data.")
    print("\nExample usage:")
    print("  from pre_gw1_step1_minizinc import optimize_pre_gw1_step1_minizinc, display_solution")
    print("  solution = optimize_pre_gw1_step1_minizinc(players_df)")
    print("  display_solution(players_df, solution)")
