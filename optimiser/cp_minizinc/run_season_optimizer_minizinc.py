"""
Main Runner: Season Optimizer for GW1-38 using MiniZinc CP-SAT solver

Orchestrates the CP optimization across all gameweeks using the documented module interfaces.
Oracle mode is enabled by default (uses actual points instead of predictions).

Usage:
    python run_season_optimizer_minizinc.py
"""

import pandas as pd
import json
import sys
import time
from pathlib import Path

# Add parent directory to path for importing utils
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the MiniZinc CP optimization modules
from pre_gw1_step1_minizinc import optimize_pre_gw1_step1_minizinc
from pre_gw1_step2_minizinc import optimize_pre_gw1_step2_minizinc
from post_gw1_step1_minizinc import optimize_post_gw1_step1_minizinc
from utils import convert_solution_for_json


def load_data(csv_path='../../cleaned_data.csv'):
    """Load and validate player data from CSV."""
    df = pd.read_csv(csv_path)
    
    required_cols = ['player_id', 'gw', 'name', 'position', 'team', 'cost', 'eP', 'points', 'prob_showup', 'unavailable']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    return df


def optimize_gw1(players_df, oracle=True, solver='cp-sat', timeout=60):
    """
    Optimize GW1 using the Pre-GW1 approach with MiniZinc.
    
    Parameters:
    -----------
    players_df : DataFrame
        Player data for GW1
    oracle : bool
        If True, use actual points instead of predicted points (default: True)
    solver : str
        Solver to use: 'cp-sat', 'gecode', 'chuffed' (default: 'cp-sat')
    timeout : int
        Timeout in seconds (default: 60)
    
    Returns:
    --------
    dict : Complete solution for GW1 with state updates
    """
    # Calculate expected points based on oracle mode
    players_df = players_df.copy()
    if oracle:
        players_df['expected_points'] = players_df['points']
    else:
        players_df['expected_points'] = players_df['eP']
    
    # Step 1: Optimize starters and captain
    step1 = optimize_pre_gw1_step1_minizinc(players_df, solver_name=solver, timeout_seconds=timeout)
    
    # Step 2: Optimize squad (bench)
    step2 = optimize_pre_gw1_step2_minizinc(players_df, step1['x'], step1['c'], solver_name=solver, timeout_seconds=timeout)
    
    # Combine outputs - step2 now contains all vectors including v, b1-b4
    solution = {
        'x': step2['x'],      # From step1 (included in step2)
        'y': step2['y'],      # Final squad from step2
        'c': step2['c'],      # From step1 (included in step2)
        'v': step2['v'],      # Vice-captain (post-hoc)
        'b1': step2['b1'],    # Bench position 1 (post-hoc)
        'b2': step2['b2'],    # Bench position 2 (post-hoc)
        'b3': step2['b3'],    # Bench position 3 (post-hoc)
        'b4': step2['b4'],    # Bench position 4 (post-hoc)
        'y0': step2['y0'],
        'p0': step2['p0'],
        'B_bank': step2['B_bank'],
        'f': step2['f']
    }
    
    return solution


def optimize_gw_post1(players_df, y0, p0, f, B_bank, oracle=True, solver='cp-sat', timeout=60):
    """
    Optimize gameweeks 2-38 using the Post-GW1 approach with MiniZinc.
    
    Parameters:
    -----------
    players_df : DataFrame
        Player data for the gameweek
    y0, p0, f, B_bank : Previous state
    oracle : bool
        If True, use actual points instead of predicted points (default: True)
    solver : str
        Solver to use: 'cp-sat', 'gecode', 'chuffed' (default: 'cp-sat')
    timeout : int
        Timeout in seconds (default: 60)
    
    Returns:
    --------
    dict : Complete solution for the gameweek with state updates
    """
    # Calculate expected points based on oracle mode
    players_df = players_df.copy()
    if oracle:
        players_df['expected_points'] = players_df['points']
    else:
        players_df['expected_points'] = players_df['eP']
    
    # Optimize starters, captain, and transfers (all in one step)
    solution = optimize_post_gw1_step1_minizinc(
        players_df, y0, p0, f, B_bank, solver_name=solver, timeout_seconds=timeout
    )
    
    return solution


def run_full_season(end_gw, oracle, solver, output_file, timeout=60, csv_path='../../cleaned_data.csv'):
    """
    Run optimization for gameweeks 1 through end_gw and save results to JSON.
    
    Parameters:
    -----------
    end_gw : int
        Final gameweek to optimize (1-38)
    oracle : bool
        If True, use actual points; if False, use predicted points
    solver : str
        Solver to use: 'cp-sat', 'gecode', 'chuffed'
    output_file : str
        Path to save optimization results (JSON format)
    timeout : int
        Timeout in seconds per gameweek (default: 60)
    csv_path : str
        Path to cleaned_data.csv
    """
    print("\n" + "="*80)
    print("FPL SEASON OPTIMIZER - MiniZinc CP Implementation")
    print("="*80)
    print(f"Solver: {solver}")
    print(f"Oracle mode: {'ENABLED' if oracle else 'DISABLED'}")
    
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
    
    # Get sorted player IDs for consistent ordering (needed for list conversion)
    player_ids_sorted = None
    
    print(f"\nOptimizing gameweeks 1-{end_gw}...")
    
    # Optimize each gameweek
    for gw in range(1, end_gw + 1):
        # Get players for this gameweek
        players_gw = all_data[all_data['gw'] == gw].copy()
        
        # Initialize sorted player IDs on first gameweek
        if player_ids_sorted is None:
            player_ids_sorted = sorted(players_gw['player_id'].tolist())
        
        try:
            print(f"  GW{gw:2d}...", end=' ', flush=True)
            
            # Start timing
            start_time = time.time()
            
            if gw == 1:
                # GW1: Initial squad selection
                solution = optimize_gw1(players_gw, oracle, solver, timeout)
                
                # Convert dict state to lists for next GW
                y0 = [solution['y0'][pid] for pid in player_ids_sorted]
                p0 = [solution['p0'][pid] for pid in player_ids_sorted]
                B_bank = solution['B_bank']
                f = solution['f']
            else:
                # GW2+: Optimize with transfers (y0, p0 are now lists)
                solution = optimize_gw_post1(players_gw, y0, p0, f, B_bank, oracle, solver, timeout)
                
                # Convert dict state to lists for next GW
                y0 = [solution['y0'][pid] for pid in player_ids_sorted]
                p0 = [solution['p0'][pid] for pid in player_ids_sorted]
                B_bank = solution['B_bank']
                f = solution['f']
            
            # End timing and store
            elapsed_time = time.time() - start_time
            if gw == 1:
                gw1_time = elapsed_time
            else:
                gw2_38_times.append(elapsed_time)
            
            # Store solution (convert player_id keys to strings for JSON)
            results[f"gw{gw}"] = convert_solution_for_json(solution)
            
            print("✓")
            
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
    print("\nAvailable CP solvers:")
    print("  1. cp-sat (Recommended, OR-Tools CP-SAT solver)")
    print("  2. gecode (Gecode constraint solver)")
    print("  3. chuffed (Lazy clause generation solver)")
    
    while True:
        solver_input = input("\nSelect solver (1-3) [default: 1]: ").strip()
        
        solver_map = {'1': 'cp-sat', '2': 'gecode', '3': 'chuffed', '': 'cp-sat'}
        
        if solver_input in solver_map:
            solver = solver_map[solver_input]
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")
    
    print(f"Selected solver: {solver}")
    
    # Ask user for time limit per gameweek
    while True:
        timeout_input = input("\nEnter time limit per gameweek in seconds [default: 60]: ").strip()
        if timeout_input == '':
            timeout = 60
            break
        try:
            timeout = int(timeout_input)
            if timeout > 0:
                break
            else:
                print("Invalid timeout. Please enter a positive integer.")
        except ValueError:
            print("Invalid input. Please enter a valid positive integer.")
    
    print(f"Time limit: {timeout} seconds per gameweek")
    
    # Oracle mode is enabled by default for CP
    print("\n⚠️  Oracle mode is ENABLED by default for CP optimization")
    print("    (Using actual points instead of predictions)")
    
    while True:
        oracle_input = input("\nKeep oracle mode enabled? (Y/n) [default: Y]: ").strip()
        if oracle_input in ['Y', 'y', '', 'yes', 'Yes']:
            oracle = True
            break
        elif oracle_input in ['N', 'n', 'no', 'No']:
            oracle = False
            print("\n⚠️  Oracle mode DISABLED - will use predicted points (eP)")
            break
        else:
            print("Invalid input. Please enter 'Y' or 'n'.")
    
    # Ask user for end gameweek with validation
    while True:
        end_gw_input = input("Optimize from GW1 to GW ? [default: 38]: ").strip()
        if end_gw_input == '':
            end_gw = 38
            break
        try:
            end_gw = int(end_gw_input)
            if 1 <= end_gw <= 38:
                break
            else:
                print("Invalid gameweek. Please enter a number between 1 and 38.")
        except ValueError:
            print("Invalid input. Please enter a valid integer between 1 and 38.")

    # Set output filename based on solver, timeout, and oracle mode
    if oracle:
        output_file = f'../../optimised_result/cp_minizinc_{solver}_{timeout}sec_season_optim_oracle.json'
        print(f"\nOracle mode enabled - using actual points for optimization")
    else:
        output_file = f'../../optimised_result/cp_minizinc_{solver}_{timeout}sec_season_optim.json'
        print(f"\nNormal mode - using predicted points for optimization")
    
    print(f"Output file: {output_file}")
    
    run_full_season(end_gw, oracle, solver, output_file, timeout)
