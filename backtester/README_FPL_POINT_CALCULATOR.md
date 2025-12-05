# FPL Point Calculator

A Python tool to calculate Fantasy Premier League gameweek points with automatic substitutions and captain doubling.

## Overview

This calculator processes a team selection and applies FPL rules to calculate the total points for a gameweek, including:
- Automatic substitutions for non-playing starters
- Captain/vice-captain point doubling
- Formation validation

## Features

### Captain Doubling
- If captain played (minutes > 0): double captain's points
- Else if vice-captain played: double vice-captain's points
- Else: no doubling applied

## Substitution Logic Details

### Algorithm

1. **Remove non-playing starters**: Filter starters to those with minutes > 0, if none , no substitution is needed
2. **Process bench in order** (positions 1→2→3→4):
    - If bench player didn't play (minutes = 0) → Skip
    - If bench player played:
     - Try adding to active team
     - Check if formation would be valid
     - If pass → Add player
     - If not → Skip and try next bench player 

3. **Stop when**: All bench tried OR 11 active players reached

### Formation Flexibility

The algorithm allows formation changes during substitution. For example:
- **Starting 4-4-2**, two defenders don't play → **2-4-2** (8 active)
- **Bench DEF** at position 2 played → Add → **3-4-2** (9 active)
- **Bench MID** at position 3 played → Add → **3-5-2** (10 active) ✓
- **Bench FWD** at position 4 played → Add → **3-5-3** (11 active) ✓

## Edge Cases 

1. **Fewer than 11 active players**: Valid if no valid substitutions available
2. **Captain didn't play**: Vice-captain points are doubled instead
3. **Both captain and vice-captain didn't play**: No doubling applied
4. **Bench GK when starting GK played**: Cannot substitute (would have 2 GKs)
5. **Multiple starters didn't play**: Processes substitutions in bench order

