# FPL Team Validator

A Python tool to validate Fantasy Premier League team selections against official FPL rules.

## Overview

This validator performs comprehensive sanity checks on a selected team of 15 players to ensure compliance with all FPL rules before calculating points.

## Features

The validator checks the following FPL rules:

**Squad Composition**: Exactly 2 GK, 5 DEF, 5 MID, 3 FWD (15 total)
**Players Per Club**: Maximum 3 players from any single club
**Starting Lineup (formation)**: 
- Exactly 11 starters such that
    - Exactly 1 starting goalkeeper
    - 3-5 starting defenders
    - 2-5 starting midfielders
    - 1-3 starting forwards
**Bench Configuration**:
- Exactly 4 benched players
- Bench positions 1-4 each have unique player
- Bench position 1 must be the goalkeeper
- Bench positions 2-4 must be outfield players
**Captaincy**:
- Exactly 1 captain
- Exactly 1 vice-captain
- Both must be starters
- Must be distinct players


budget is not checked, since you can earn money and it is complicated.