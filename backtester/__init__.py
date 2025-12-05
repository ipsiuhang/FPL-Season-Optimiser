"""
FPL Backtester Package

A comprehensive backtesting tool for Fantasy Premier League season optimizer results.
"""

from .backtester import run_backtest, save_backtest_results
from .fpl_validator import (
    validate_team,
    validate_formation
)
from .fpl_point_calculator import calculate_gameweek_points, format_lineup_summary

__version__ = "1.0.0"
__all__ = [
    "run_backtest",
    "save_backtest_results",
    "validate_squad",
    "validate_starting_xi",
    "validate_bench",
    "validate_captaincy",
    "validate_formation",
    "calculate_gameweek_points",
    "format_lineup_summary"
]
