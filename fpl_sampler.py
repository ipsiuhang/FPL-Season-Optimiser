import requests
import time
import pandas as pd
import numpy as np
import random

# Base URL for FPL API
BASE_URL = 'https://fantasy.premierleague.com/api/'

def get_bootstrap():
    """Fetch total number of managers from the bootstrap endpoint."""
    response = requests.get(f'{BASE_URL}bootstrap-static/')
    if response.status_code == 200:
        data = response.json()
        return data['total_players']
    else:
        raise ValueError(f"Failed to fetch bootstrap data: {response.status_code}")

def get_manager_summary(entry_id):
    """Fetch summary data for a specific manager, including total points and overall rank."""
    response = requests.get(f'{BASE_URL}entry/{entry_id}/')
    if response.status_code == 200:
        data = response.json()
        return {
            'entry_id': entry_id,
            'total_points': data.get('summary_total', 0),
            'overall_rank': data.get('summary_overall_rank', None),
            'team_name': data.get('name', 'Unknown')
        }
    else:
        return {'entry_id': entry_id, 'total_points': 0, 'overall_rank': None, 'team_name': 'Error'}

def sample_managers(num_samples=1000, delay=0.1):
    """
    Randomly sample managers without replacement and fetch their data.
    
    Args:
        num_samples (int): Number of managers to sample (default: 1000).
        delay (float): Seconds to wait between API calls (default: 0.1).
    
    Returns:
        pd.DataFrame: DataFrame containing sampled manager data.
    """
    total_players = get_bootstrap()
    print(f"Total managers in 2024/25 season: {total_players:,}")
    
    # Generate random sample of unique entry IDs (1 to total_players) without replacement
    entry_ids = random.sample(range(1, total_players + 1), min(num_samples, total_players))
    print(f"Sampling {len(entry_ids)} unique random managers...")
    
    results = []
    for i, entry_id in enumerate(entry_ids, 1):
        result = get_manager_summary(entry_id)
        results.append(result)
        if i % 100 == 0:
            print(f"Processed {i}/{len(entry_ids)} samples...")
        time.sleep(delay)  # Rate limit compliance
    
    # Convert to DataFrame
    df = pd.DataFrame(results)
    df = df.dropna(subset=['total_points'])  # Filter out invalid entries
    
    # Compute summary statistics
    valid_samples = len(df)
    print(f"\nValid samples collected: {valid_samples}")
    print(f"Mean total points: {df['total_points'].mean():.0f}")
    print(f"Median total points: {df['total_points'].median():.0f}")
    print(f"Standard deviation: {df['total_points'].std():.0f}")
    
    # Sample quantiles (e.g., top 10%, 1% thresholds based on sample)
    quantiles = df['total_points'].quantile([0.9, 0.99])
    print("\nSample-based quantile thresholds (points for top %):")
    print(f"Top 10%: {quantiles[0.9]:.0f}")
    print(f"Top 1%: {quantiles[0.99]:.0f}")
    
    # Save to CSV
    output_file = 'fpl_random_sample_2024_25.csv'
    df.to_csv(output_file, index=False)
    print(f"\nData saved to {output_file}")
    
    return df

# Example usage: Sample 1000 managers
if __name__ == "__main__":
    sample_df = sample_managers(num_samples=1000, delay=0.01)
