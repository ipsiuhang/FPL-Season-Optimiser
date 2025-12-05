% FPL Pre-GW1 Step 1: Optimized Set-of-Sets Model with Symmetry Breaking
% Models squad/lineup as partitioned sets to avoid symmetries.
% USES INTEGER ARITHMETIC: All costs and points scaled by 10 (e.g., £4.5m → 45, 5.5pts → 55)

include "globals.mzn";  % For disjoint, increasing, etc.

% High-Level Abstractions
enum Position = {GK, DEF, MID, FWD};  % Positions for partitioning
set of int: Players = 1..n_players;     % Base set P of all players
set of int: Clubs = 1..20;              % Club indices for limits

% Parameters (passed via .dzn or Python API)
% NOTE: expected_points and cost should be integers (scaled by 10 in data preparation)
int: n_players;                         % |P|
int: UB;                                % Tight upper bound on objective (scaled by 10)
array[Players] of int: expected_points;  % expected_points_i as integer (scaled by 10 in data)
array[Players] of int: cost;             % cost_i as integer (scaled by 10 in data, e.g., £4.5m → 45)
array[Players] of bool: unavailable;       % u_i (true if unavailable)
array[Position] of set of Players: PosPlayers;  % Pre-partitioned: PosPlayers[GK] = G subset P (available only)
array[Clubs] of set of Players: ClubPlayers;    % ClubPlayers[c] = P_c subset P

% Decision Variables: Sets and Set-of-Sets (Partitions)
var set of Players: Squad;                      % Q: Squad set, |Q|=15
var set of Players: Starters;                   % S subset Q: Starting XI, |S|=11
var set of Players: Captain;                    % Singleton set for captain

array[Position] of var set of Players: SquadPartitions;  % Partition of Q by position (set-of-sets)
array[Position] of var set of Players: StarterPartitions;  % Partition of S by position

% Subset Constraints 
constraint Starters subset Squad;
constraint Captain subset Starters;

% Objective: Maximize expected points from starters + captain (doubled)
% Using INTEGER arithmetic (values scaled by 10 in data preparation)
var 0..UB: z;
constraint z = sum(i in Starters) (expected_points[i]) + sum(i in Captain) (expected_points[i]);

% Constraints in Set Notation
% Cardinalities
constraint card(Squad) = 15;
constraint card(Starters) = 11;
constraint card(Captain) = 1;

% Position-Specific Cardinalities
constraint card(SquadPartitions[GK]) = 2 /\ card(StarterPartitions[GK]) = 1;
constraint card(SquadPartitions[DEF]) = 5 /\ 3 <= card(StarterPartitions[DEF]) /\ card(StarterPartitions[DEF]) <= 5;
constraint card(SquadPartitions[MID]) = 5 /\ 2 <= card(StarterPartitions[MID]) /\ card(StarterPartitions[MID]) <= 5;
constraint card(SquadPartitions[FWD]) = 3 /\ 1 <= card(StarterPartitions[FWD]) /\ card(StarterPartitions[FWD]) <= 3;

% Partition Constraints (disjoint union, subsets of available players)
constraint forall(p1, p2 in Position where p1 < p2) (disjoint(SquadPartitions[p1], SquadPartitions[p2]));
constraint Squad = array_union([SquadPartitions[p] | p in Position]);
constraint forall(p in Position) (SquadPartitions[p] subset PosPlayers[p]);

constraint forall(p1, p2 in Position where p1 < p2) (disjoint(StarterPartitions[p1], StarterPartitions[p2]));
constraint Starters = array_union([StarterPartitions[p] | p in Position]);
constraint forall(p in Position) (StarterPartitions[p] subset SquadPartitions[p]);

% Budget Constraint (sum over set) - Budget scaled: £100.0m → 1000
constraint sum(i in Squad) (cost[i]) <= 1000;

% Club Limits (intersection cardinalities)
constraint forall(c in Clubs) (card(Squad intersect ClubPlayers[c]) <= 3);

% Availability (exclude unavailable from starters)
constraint forall(i in Players where unavailable[i]) (not (i in Starters));

% Search Strategy: Focus on partitions with proper annotations
solve :: set_search([SquadPartitions[p] | p in Position] ++ [StarterPartitions[p] | p in Position],
                    input_order, indomain_min)
      maximize z;

% Output for Integration (e.g., parse in Python for decomposition)
output [
  "Objective z = ", show(z), " (scaled by 10, actual = ", show(int2float(z) / 10.0), " pts)\n",
  "Squad = ", show(Squad), "\n",
  "Starters = ", show(Starters), "\n",
  "Captain = ", show(Captain), "\n",
  "Squad Partitions = ", show([SquadPartitions[p] | p in Position]), "\n",
  "Starter Partitions = ", show([StarterPartitions[p] | p in Position]), "\n"
];
