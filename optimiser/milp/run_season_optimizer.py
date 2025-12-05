"""
Main Runner: Season Optimizer for GW1-38
Orchestrates the MILP optimization across all gameweeks using the documented module interfaces.

Usage:
    python run_season_optimizer.py
"""

import pandas as pd
import json
import sys
import time
from pathlib import Path

# Add parent directory to path for importing post_hoc_utils
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the MILP optimization modules
from pre_gw1_step1 import optimize_pre_gw1_step1
from pre_gw1_step2 import optimize_pre_gw1_step2
from post_gw1_step1 import optimize_post_gw1_step1
from utils import process_pre_gw1_solution, process_post_gw1_solution, convert_solution_for_json


def load_data(csv_path='../../cleaned_data.csv'):
    """Load and validate player data from CSV."""
    df = pd.read_csv(csv_path)
    
    required_cols = ['player_id', 'gw', 'name', 'position', 'team', 'cost', 'eP', 'prob_showup', 'unavailable']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    return df


def optimize_gw1(players_df, oracle=False, solver='CBC'):
    """
    Optimize GW1 using the three-step Pre-GW1 approach.
    
    Parameters:
    -----------
    players_df : DataFrame
        Player data for GW1
    oracle : bool
        If True, use actual points instead of predicted points
    solver : str
        Solver to use: 'CPLEX', 'CBC', 'GLPK', or 'GUROBI'
    
    Returns:
    --------
    dict : Complete solution for GW1
    """
    # Calculate expected points once based on oracle mode
    players_df = players_df.copy()
    if oracle:
        players_df['expected_points'] = players_df['points']
    else:
        players_df['expected_points'] = players_df['eP'] # * (1 - players_df['prob_showup']) dated 
    
    # Step 1: Optimize starters and captain
    step1 = optimize_pre_gw1_step1(players_df, solver=solver)
    
    # Step 2: Optimize squad (bench)
    step2 = optimize_pre_gw1_step2(players_df, step1['x'], solver=solver)
    
    # Step 3: Post-hoc processing (vice-captain, bench order)
    post_hoc = process_pre_gw1_solution(players_df, step1['x'], step2['y'], step1['c'])
    
    # Combine all outputs
    solution = {
        'x': step1['x'],
        'y': step2['y'],
        'c': step1['c'],
        'v': post_hoc['v'],
        'b1': post_hoc['b1'],
        'b2': post_hoc['b2'],
        'b3': post_hoc['b3'],
        'b4': post_hoc['b4'],
        'y0': step2['y0'],
        'p0': step2['p0'],
        'B_bank': step2['B_bank'],
        'f': step2['f']
    }
    
    return solution


def optimize_gw_post1(players_df, y0, p0, f, B_bank, oracle=False, solver='CBC'):
    """
    Optimize gameweeks 2-38 using the two-step Post-GW1 approach.
    
    Parameters:
    -----------
    players_df : DataFrame
        Player data for the gameweek
    y0, p0, f, B_bank : Previous state
    oracle : bool
        If True, use actual points instead of predicted points
    solver : str
        Solver to use: 'CPLEX', 'CBC', 'GLPK', or 'GUROBI'
    
    Returns:
    --------
    dict : Complete solution for the gameweek
    """
    # Calculate expected points once based on oracle mode
    players_df = players_df.copy()
    if oracle:
        players_df['expected_points'] = players_df['points']
    else:
        players_df['expected_points'] = players_df['eP'] # * (1 - players_df['prob_showup']) dated
    
    # Step 1: Optimize starters, captain, and transfers
    step1 = optimize_post_gw1_step1(players_df, y0, p0, f, B_bank, solver=solver)
    
    # Step 2: Post-hoc processing (vice-captain, bench order)
    post_hoc = process_post_gw1_solution(players_df, step1['x'], step1['y'], step1['c'])
    
    # Combine all outputs
    solution = {
        'x': step1['x'],
        'y': step1['y'],
        'c': step1['c'],
        'v': post_hoc['v'],
        'b1': post_hoc['b1'],
        'b2': post_hoc['b2'],
        'b3': post_hoc['b3'],
        'b4': post_hoc['b4'],
        'y0': step1['y0'],
        'p0': step1['p0'],
        'B_bank': step1['B_bank'],
        'f': step1['f']
    }
    
    return solution


def run_full_season(end_gw, oracle, solver, output_file, csv_path='../../cleaned_data.csv'):
    """
    Run optimization for all 38 gameweeks and save results to JSON.
    
    Parameters:
    -----------
    end_gw : int
        Final gameweek to optimize (1-38)
    oracle : bool
        If True, use actual points; if False, use predicted points
    solver : str
        Solver to use: 'CPLEX', 'CBC', 'GLPK', or 'GUROBI'
    output_file : str
        Path to save optimization results (JSON format)
    csv_path : str
        Path to cleaned_data.csv
    """
    print("\n" + "="*80)
    print("FPL SEASON OPTIMIZER - MILP Implementation")
    print("="*80)
    print(f"Solver: {solver}")
    
    # Load data
    print(f"\nLoading data from {csv_path}...")
    all_data = load_data(csv_path)
    print(f"Loaded {len(all_data)} player-gameweek records")
    
    # State variables (will be updated after each GW)
    y0 = None
    p0 = None
    B_bank = None
    f = None
    
    # Results storage
    results = {}
    
    # Timing tracking
    gw1_time = None
    gw2_38_times = []
    
    print(f"\nOptimizing gameweeks 1-{end_gw}...")
    
    # Optimize each gameweek
    for gw in range(1, end_gw + 1):
        # Get players for this gameweek
        players_gw = all_data[all_data['gw'] == gw].copy()
        
        try:
            print(f"  GW{gw:2d}...", end=' ', flush=True)
            
            # Start timing
            start_time = time.time()
            
            if gw == 1:
                # GW1: Initial squad selection
                solution = optimize_gw1(players_gw, oracle, solver)
            else:
                # GW2+: Optimize with transfers
                solution = optimize_gw_post1(players_gw, y0, p0, f, B_bank, oracle, solver)
            
            # End timing and store
            elapsed_time = time.time() - start_time
            if gw == 1:
                gw1_time = elapsed_time
            else:
                gw2_38_times.append(elapsed_time)
            
            # Update state variables for next GW
            y0 = solution['y0']
            p0 = solution['p0']
            B_bank = solution['B_bank']
            f = solution['f']
            
            # Store solution (convert player_id keys to strings for JSON)
            results[f"gw{gw}"] = convert_solution_for_json(solution)
            
        except Exception as e:
            print(f"ERROR")
            print(f"\nERROR in GW{gw}: {str(e)}")
            import traceback
            traceback.print_exc()
            break
    
    # Save results to JSON
    print(f"\nSaving results to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nSeason optimization complete!")
    print(f"Results saved to: {output_file}")
    print(f"Optimized {len(results)} gameweeks (GW1-GW{max([int(k[2:]) for k in results.keys()])})")
    
    # Display timing information
    if gw1_time is not None:
        print("\n" + "="*80)
        print("OPTIMIZATION TIMING")
        print("="*80)
        print(f"GW1 time: {gw1_time:.2f} seconds")
        if gw2_38_times:
            avg_time = sum(gw2_38_times) / len(gw2_38_times)
            print(f"GW2-38 average time: {avg_time:.2f} seconds")
        print("="*80)

if __name__ == "__main__":
    # Ask user for solver selection
    print("\nAvailable MILP solvers:")
    print("  1. CBC (Recommended, reliable open-source solver)")
    print("  2. GLPK (Alternative open-source solver)")
    print("  3. SCIP (High-performance open-source solver)")
    
    while True:
        solver_input = input("\nSelect solver (1-3) [default: 1]: ").strip()
        
        solver_map = {'1': 'CBC', '2': 'GLPK', '3': 'SCIP', '': 'CBC'}
        
        if solver_input in solver_map:
            solver = solver_map[solver_input]
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")
    
    print(f"Selected solver: {solver}")
    
    # Ask user for oracle mode with validation
    while True:
        oracle_input = input("\nUse oracle mode? (y/n): ").strip()
        if oracle_input in ['Y', 'y', 'N', 'n']:
            oracle = (oracle_input in ['Y', 'y'])
            break
        else:
            print("Invalid input. Please enter 'y' or 'n'.")
    
    # Ask user for end gameweek with validation
    while True:
        end_gw_input = input("Optimize from GW1 to GW ?: ").strip()
        try:
            end_gw = int(end_gw_input)
            if 1 <= end_gw <= 38:
                break
            else:
                print("Invalid gameweek. Please enter a number between 1 and 38.")
        except ValueError:
            print("Invalid input. Please enter a valid integer between 1 and 38.")

    # Set output filename based on solver and oracle mode
    solver_lower = solver.lower()
    if oracle:
        output_file = f'../../optimised_result/milp_{solver_lower}_season_optim_oracle.json'
        print(f"\nOracle mode enabled - using actual points for optimization")
    else:
        output_file = f'../../optimised_result/milp_{solver_lower}_season_optim.json'
        print(f"\nNormal mode - using predicted points for optimization")
    
    print(f"Output file: {output_file}")
    
    run_full_season(end_gw, oracle, solver, output_file)
