"""
FPL Backtester

Functional module to backtest FPL season optimizer results against actual gameweek data.
"""

import json
import pandas as pd
from typing import Dict, List, Tuple
from pathlib import Path

from .fpl_validator import validate_team
from .fpl_point_calculator import calculate_gameweek_points, format_lineup_summary


# Helper functions

def extract_player_ids(binary_dict: Dict[str, int]) -> List[int]:
    """Extract player IDs where value is 1 from binary dictionary."""
    return [int(pid) for pid, val in binary_dict.items() if val == 1]


def get_gameweek_data(cleaned_df: pd.DataFrame, gw: int, player_ids: List[int]) -> pd.DataFrame:
    """
    Get player data for specific gameweek and player IDs.
    
    Args:
        cleaned_df: Full cleaned data DataFrame
        gw: Gameweek number (1-38)
        player_ids: List of player IDs
        
    Returns:
        DataFrame with player data for specified GW and players
    """
    gw_data = cleaned_df[cleaned_df['gw'] == gw]
    return gw_data[gw_data['player_id'].isin(player_ids)].copy()


def detect_transfers(current_squad: List[int], previous_squad: List[int]) -> Tuple[List, List]:
    """
    Detect transfers by comparing current squad with previous squad.
    
    Args:
        current_squad: List of current player IDs (15 players)
        previous_squad: List of previous player IDs (15 players)
        
    Returns:
        (transfers_in, transfers_out): Lists of player IDs
    """
    current_set = set(current_squad)
    previous_set = set(previous_squad)
    
    transfers_in = list(current_set - previous_set)
    transfers_out = list(previous_set - current_set)
    
    return transfers_in, transfers_out


def format_transfer_section(transfers_in: List[int], transfers_out: List[int], 
                            cleaned_df: pd.DataFrame, gw: int) -> List[str]:
    """Format transfer section for output."""
    lines = []
    
    if transfers_in:  # If there are transfers (in and out are always equal)
        lines.append("\nTransfers:")
        
        # Get all transfer player data in one lookup
        all_transfer_ids = transfers_in + transfers_out
        transfer_data = get_gameweek_data(cleaned_df, gw, all_transfer_ids)
        
        # Format transfers in
        lines.append(f"  IN ({len(transfers_in)}):")
        for pid in transfers_in:
            player = transfer_data[transfer_data['player_id'] == pid].iloc[0]
            lines.append(f"    {player['name']} (ID: {pid}, {player['position']}, {player['team']})")
        
        # Format transfers out
        lines.append(f"  OUT ({len(transfers_out)}):")
        for pid in transfers_out:
            player = transfer_data[transfer_data['player_id'] == pid].iloc[0]
            lines.append(f"    {player['name']} (ID: {pid}, {player['position']}, {player['team']})")
    else:
        lines.append("\nTransfers: None")
    
    return lines


# Main backtesting function

def run_backtest(optimizer_json_path: str, cleaned_data_path: str) -> Tuple[str, int, int]:
    """
    Run complete backtest for all 38 gameweeks.
    
    Args:
        optimizer_json_path: Path to optimizer output JSON file
        cleaned_data_path: Path to cleaned_data.csv
        
    Returns:
        (results_text, total_points, total_transfers): Results string and summary stats
    """
    # Load data
    print(f"Loading optimizer results from: {optimizer_json_path}")
    with open(optimizer_json_path, 'r') as f:
        optimizer_data = json.load(f)
    
    print(f"Loading cleaned data from: {cleaned_data_path}")
    cleaned_df = pd.read_csv(cleaned_data_path)
    
    # Initialize output and tracking
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("FPL BACKTESTER RESULTS")
    output_lines.append("=" * 80)
    output_lines.append(f"Season: 2024-25")
    output_lines.append(f"Optimizer: {Path(optimizer_json_path).name}")
    output_lines.append("=" * 80)
    output_lines.append("")
    
    cumulative_points = 0
    total_transfers = 0
    previous_squad = []
    
    # Process each gameweek
    for gw_num in range(1, 39):
        gw_key = f"gw{gw_num}"
        
        if gw_key not in optimizer_data:
            output_lines.append(f"WARNING: {gw_key} not found in optimizer data")
            continue
        
        gw_data = optimizer_data[gw_key]
        
        try:
            # Extract team selection
            squad_ids = extract_player_ids(gw_data['y'])
            starter_ids = extract_player_ids(gw_data['x'])
            captain_id = extract_player_ids(gw_data['c'])[0]
            vice_id = extract_player_ids(gw_data['v'])[0]
            
            bench_ids = {
                1: extract_player_ids(gw_data['b1'])[0],
                2: extract_player_ids(gw_data['b2'])[0],
                3: extract_player_ids(gw_data['b3'])[0],
                4: extract_player_ids(gw_data['b4'])[0]
            }
            
            # Get all players for this gameweek (filter once)
            gw_df = cleaned_df[cleaned_df['gw'] == gw_num].copy()
            
            # Validate team (comprehensive check)
            is_valid, error_msg = validate_team(gw_df, squad_ids, starter_ids, bench_ids, captain_id, vice_id)
            if not is_valid:
                output_lines.append(f"\nGW{gw_num}: VALIDATION FAILED")
                output_lines.append(f"  Error: {error_msg}")
                raise ValueError(f"GW{gw_num} validation failed: {error_msg}")
            
            # Calculate points
            gw_points, active_lineup, details = calculate_gameweek_points(gw_df, starter_ids, bench_ids, captain_id, vice_id)
            
            cumulative_points += gw_points
            
            # Detect transfers
            transfers_in = []
            transfers_out = []
            if gw_num > 1 and previous_squad:
                transfers_in, transfers_out = detect_transfers(squad_ids, previous_squad)
                total_transfers += len(transfers_in)
            
            # Format gameweek header
            output_lines.append(f"\n{'=' * 80}")
            output_lines.append(f"GAMEWEEK {gw_num}")
            output_lines.append(f"{'=' * 80}")
            output_lines.append(f"Points: {gw_points}")
            output_lines.append(f"Cumulative Points: {cumulative_points}")
            
            # Transfers
            output_lines.extend(format_transfer_section(
                transfers_in, transfers_out, cleaned_df, gw_num
            ))
            
            # Captain info
            captain_name = gw_df[gw_df['player_id'] == captain_id].iloc[0]['name']
            vice_name = gw_df[gw_df['player_id'] == vice_id].iloc[0]['name']
            output_lines.append(f"\nCaptain: {captain_name} (ID: {captain_id})")
            output_lines.append(f"Vice-Captain: {vice_name} (ID: {vice_id})")
            if details['captain_used']:
                output_lines.append(f"Captain Bonus: +{details['captain_bonus']} pts ({details['captain_used']})")
            
            # Substitutions
            if len(details['substitutions']) > 0:
                output_lines.append(f"\nSubstitutions Made ({len(details['substitutions'])}):")
                for sub in details['substitutions']:
                    output_lines.append(
                        f"  Bench {sub['bench_pos']}: {sub['name']} "
                        f"({sub['position']}) - {sub['points']}pts"
                    )
            else:
                output_lines.append(f"\nSubstitutions Made: None")
            
            # Active lineup
            output_lines.append(f"\nActive Lineup ({len(active_lineup)} players):")
            lineup_str = format_lineup_summary(active_lineup, captain_id, vice_id)
            output_lines.append(lineup_str)
            
            # Bench
            output_lines.append(f"\nBench:")
            for pos in [1, 2, 3, 4]:
                bench_player_id = bench_ids[pos]
                bench_player = gw_df[gw_df['player_id'] == bench_player_id].iloc[0]
                played = "✓" if bench_player_id in [s['player_id'] for s in details['substitutions']] else "✗"
                output_lines.append(
                    f"  {pos}. {bench_player['name']} ({bench_player['position']}) - "
                    f"{bench_player['points']}pts ({bench_player['minutes']}min) [{played}]"
                )
            
            # Update previous squad for next iteration
            previous_squad = squad_ids
            
        except Exception as e:
            output_lines.append(f"\nERROR in GW{gw_num}: {str(e)}")
            raise
    
    # Final summary
    output_lines.append(f"\n\n{'=' * 80}")
    output_lines.append("FINAL SUMMARY")
    output_lines.append(f"{'=' * 80}")
    output_lines.append(f"Total Points: {cumulative_points}")
    output_lines.append(f"Total Transfers: {total_transfers}")
    avg_points = cumulative_points / 38 if cumulative_points > 0 else 0
    output_lines.append(f"Average GW Points: {avg_points:.2f}")
    output_lines.append(f"Gameweeks Completed: 38")
    output_lines.append(f"{'=' * 80}")
    
    results_text = '\n'.join(output_lines)
    return results_text, cumulative_points, total_transfers


def save_backtest_results(optimizer_json_path: str, output_path: str, 
                          cleaned_data_path: str = "cleaned_data.csv") -> Tuple[int, int]:
    """
    Run backtest and save results to file.
    
    Args:
        optimizer_json_path: Path to optimizer output JSON file
        output_path: Path to save output TXT file
        cleaned_data_path: Path to cleaned_data.csv
        
    Returns:
        (total_points, total_transfers): Summary statistics
    """
    results_text, total_points, total_transfers = run_backtest(
        optimizer_json_path, cleaned_data_path
    )
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(results_text)
    
    print(f"\nResults saved to: {output_path}")
    return total_points, total_transfers


def main():
    """Main entry point for running backtester from command line."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m backtester.backtester <optimizer_json_filename>")
        print("Example: python -m backtester.backtester season_optim.json")
        sys.exit(1)
    
    # python -m backtester.backtester cp_minizinc_chuffed_10sec_season_optim_oracle.json
    # python -m backtester.backtester cp_minizinc_cp-sat_10sec_season_optim_oracle.json
    # python -m backtester.backtester cp_minizinc_gecode_10sec_season_optim_oracle.json
    # python -m backtester.backtester milp_cbc_season_optim.json
    # python -m backtester.backtester milp_cbc_season_optim_oracle.json
    # python -m backtester.backtester milp_glpk_season_optim.json
    # python -m backtester.backtester milp_glpk_season_optim_oracle.json
    # python -m backtester.backtester milp_scip_season_optim.json
    # python -m backtester.backtester milp_scip_season_optim_oracle.json
    

    json_filename = sys.argv[1]
    json_path = f"optimised_result/{json_filename}"
    
    # Generate output filename
    output_filename = json_filename.replace('.json', '_backtest_results.txt')
    output_path = f"backtester/{output_filename}"
    
    # Run and save
    print("\nRunning backtest...")
    total_points, total_transfers = save_backtest_results(json_path, output_path)
    print(f"Final Points: {total_points}")
    print(f"Total Transfers: {total_transfers}")


if __name__ == "__main__":
    main()
