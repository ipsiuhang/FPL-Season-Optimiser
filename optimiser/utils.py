import pandas as pd


def process_pre_gw1_solution(players_df, x_star, y2_star, c_star):
    """
    Process Pre-GW1 optimization results to compute post-hoc assignments.
    
    This function performs post-hoc computations:
    - Select vice-captain (highest expected points among starters, excluding captain)
    - Assign bench positions (GK in pos 1, outfield sorted by expected points)
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, name, position, team, cost, expected_points
        IMPORTANT: Must have 'expected_points' column pre-calculated by the caller.
    x_star : dict
        x_i* from Step 1 - {player_id: value} where value is 1 if starter, 0 otherwise
    y2_star : dict
        y_i** from Step 2 - {player_id: value} where value is 1 if in final squad, 0 otherwise
    c_star : dict
        c_i* from Step 1 - {player_id: value} where value is 1 if captain, 0 otherwise
    
    Returns:
    --------
    dict : Solution containing complete binary vectors:
        - 'v': {player_id: value} - v_i ∈ {0,1} for all players (1 if vice-captain)
        - 'b1': {player_id: value} - b1_i ∈ {0,1} for all players (1 if bench position 1 - GK)
        - 'b2': {player_id: value} - b2_i ∈ {0,1} for all players (1 if bench position 2)
        - 'b3': {player_id: value} - b3_i ∈ {0,1} for all players (1 if bench position 3)
        - 'b4': {player_id: value} - b4_i ∈ {0,1} for all players (1 if bench position 4)
    """
    
    player_ids = list(x_star.keys())
    
    # Validate: Ensure single gameweek data (no duplicate player_ids)
    if players_df['player_id'].duplicated().any():
        raise ValueError("More than 1 GW data detected. Each player_id must appear exactly once.")
    
    # Create nested dictionary for efficient O(1) lookups (auto-includes ALL columns)
    players = players_df.set_index('player_id').to_dict('index')
    
    # Extract filtered lists for computation
    squad_ids = [pid for pid, val in y2_star.items() if val == 1]
    starter_ids = [pid for pid, val in x_star.items() if val == 1]
    captain_id = [pid for pid, val in c_star.items() if val == 1][0]
    bench_ids = [pid for pid in squad_ids if pid not in starter_ids]
    
    # Select vice-captain: highest expected points among starters (excluding captain)
    vice_captain_id = max(
        (pid for pid in player_ids if x_star[pid] == 1 and c_star[pid] == 0),
        key=lambda pid: players[pid]['expected_points']
    )
    
    # Assign bench positions (returns ordered list of 4 player_ids)
    bench_order = assign_bench_positions(players, bench_ids)
    
    # Create complete binary vectors for post-hoc assignments
    v = {pid: (1 if pid == vice_captain_id else 0) for pid in player_ids}
    b1 = {pid: (1 if pid == bench_order[0] else 0) for pid in player_ids}
    b2 = {pid: (1 if pid == bench_order[1] else 0) for pid in player_ids}
    b3 = {pid: (1 if pid == bench_order[2] else 0) for pid in player_ids}
    b4 = {pid: (1 if pid == bench_order[3] else 0) for pid in player_ids}
    
    solution = {
        # Post-hoc assignments
        'v': v,
        'b1': b1,
        'b2': b2,
        'b3': b3,
        'b4': b4
    }
    
    return solution


def process_post_gw1_solution(players_df, x_star, y_star, c_star):
    """
    Process Post-GW1 optimization results to compute post-hoc assignments.
    
    This function performs post-hoc computations:
    - Select vice-captain (highest expected points among starters, excluding captain)
    - Assign bench positions (GK in pos 1, outfield sorted by expected points)
    
    Parameters:
    -----------
    players_df : pd.DataFrame
        DataFrame with columns: player_id, name, position, team, cost, expected_points
        IMPORTANT: Must have 'expected_points' column pre-calculated by the caller.
    x_star : dict
        x_i* from Step 1 - {player_id: value} where value is 1 if starter, 0 otherwise
    y_star : dict
        y_i* from Step 1 - {player_id: value} where value is 1 if in squad, 0 otherwise
    c_star : dict
        c_i* from Step 1 - {player_id: value} where value is 1 if captain, 0 otherwise
    
    Returns:
    --------
    dict : Solution containing complete binary vectors:
        - 'v': {player_id: value} - v_i ∈ {0,1} for all players (1 if vice-captain)
        - 'b1': {player_id: value} - b1_i ∈ {0,1} for all players (1 if bench position 1 - GK)
        - 'b2': {player_id: value} - b2_i ∈ {0,1} for all players (1 if bench position 2)
        - 'b3': {player_id: value} - b3_i ∈ {0,1} for all players (1 if bench position 3)
        - 'b4': {player_id: value} - b4_i ∈ {0,1} for all players (1 if bench position 4)
    """

    # Validate: Ensure single gameweek data 
    if players_df['player_id'].duplicated().any():
        raise ValueError("More than 1 GW data detected. Each player_id must appear exactly once.")
    
    # Create nested dictionary for efficient 
    players = players_df.set_index('player_id').to_dict('index')
    player_ids = players_df['player_id'].tolist()

    # Extract filtered lists for computation
    squad_ids = [pid for pid, val in y_star.items() if val == 1]
    starter_ids = [pid for pid, val in x_star.items() if val == 1]
    captain_id = [pid for pid, val in c_star.items() if val == 1][0]
    bench_ids = [pid for pid in squad_ids if pid not in starter_ids]
    
    # Select vice-captain: highest expected points among starters (excluding captain)
    vice_captain_id = max(
        (pid for pid in player_ids if x_star[pid] == 1 and c_star[pid] == 0),
        key=lambda pid: players[pid]['expected_points']
    )
    
    # Assign bench positions (returns ordered list of 4 player_ids)
    bench_order = assign_bench_positions(players, bench_ids)
    
    # Create complete binary vectors for post-hoc assignments
    v = {pid: (1 if pid == vice_captain_id else 0) for pid in player_ids}
    b1 = {pid: (1 if pid == bench_order[0] else 0) for pid in player_ids}
    b2 = {pid: (1 if pid == bench_order[1] else 0) for pid in player_ids}
    b3 = {pid: (1 if pid == bench_order[2] else 0) for pid in player_ids}
    b4 = {pid: (1 if pid == bench_order[3] else 0) for pid in player_ids}
    
    solution = {
        # Post-hoc assignments
        'v': v,
        'b1': b1,
        'b2': b2,
        'b3': b3,
        'b4': b4
    }
    
    return solution


def assign_bench_positions(players, bench_ids):
    """
    Assign bench positions according to FPL rules.
    
    Rules:
    - Position 1: Backup goalkeeper (must be GK)
    - Positions 2-4: Outfield players sorted by expected points (descending)
    
    Parameters:
    -----------
    players : dict
        Nested dictionary with player attributes: {pid: {'expected_points': float, 'cost': float, 'position': str}}
    bench_ids : list
        List of player_ids on the bench (should be 4 players)
    
    Returns:
    --------
    list : 4 player_ids in bench order [pos1_GK, pos2_best, pos3_mid, pos4_worst]
    """
    # Position 1: Backup GK - use dictionary lookup instead of DataFrame filtering
    bench_gks = [pid for pid in bench_ids if players[pid]['position'] == 'GK']
    if len(bench_gks) != 1:
        raise ValueError(f"Expected exactly 1 bench GK, found {len(bench_gks)}")
    gk_id = bench_gks[0]
    
    # Positions 2-4: Outfield players sorted by expected points (descending)
    # Use dictionary lookup and sorted() instead of DataFrame operations
    outfield_ids = [pid for pid in bench_ids if players[pid]['position'] != 'GK']
    
    if len(outfield_ids) != 3:
        raise ValueError(f"Expected exactly 3 bench outfield players, found {len(outfield_ids)}")
    
    # Sort by expected points (descending)
    outfield_ids_sorted = sorted(outfield_ids, key=lambda pid: players[pid]['expected_points'], reverse=True)
    
    # Bench order: [pos1_GK, pos2_best, pos3_mid, pos4_worst]
    bench_order = [gk_id] + outfield_ids_sorted
    
    return bench_order

def convert_solution_for_json(solution):
    """
    Convert solution dictionaries from int keys to string keys for JSON serialization.
    
    JSON doesn't support integer keys, so we convert player_id keys to strings.
    """
    converted = {}
    
    for key, value in solution.items():
        if isinstance(value, dict):
            # Convert player_id keys to strings
            converted[key] = {str(pid): val for pid, val in value.items()}
        else:
            # Keep scalars as-is (B_bank, f)
            converted[key] = value
    
    return converted


def get_pulp_solver(solver_name='CBC', msg=0):
    """Get PuLP solver object based on solver name."""
    import pulp
    
    # Map solver names to PuLP solver objects
    solvers = {
        # 'CPLEX': pulp.CPLEX_CMD(msg=msg),
        'CBC': pulp.PULP_CBC_CMD(msg=msg),
        'GLPK': pulp.GLPK_CMD(msg=msg),
        # 'GUROBI': pulp.GUROBI_CMD(msg=msg),
        'SCIP': pulp.SCIP_PY(msg=msg)
    }
    
    # Handle case-insensitive input
    solver_upper = solver_name.upper()
    
    # Return requested solver or default to CBC with warning
    if solver_upper not in solvers:
        print(f"Warning: Unknown solver '{solver_name}', defaulting to CBC")
        return pulp.PULP_CBC_CMD(msg=msg)
    
    return solvers[solver_upper]


if __name__ == "__main__":
    # Example usage
    print("This module should be imported and used with optimization results.")
