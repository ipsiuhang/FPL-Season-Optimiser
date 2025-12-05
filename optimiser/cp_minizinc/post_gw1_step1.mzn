% CP-Optimized Post-GW1 Step 1: Explicit Binary Transfers (Robust Alternative)
% Maximizes net points with penalty: sum(expected_points[i] for i in Starters) + sum(expected_points[i] for i in Captain) - 4*e
% Uses explicit bool variables for buys/sells to avoid propagation issues with set diff
% Equivalent to proposal formulation with t_i, s_i binaries
include "globals.mzn";

% Enums and Base Sets
enum Position = {GK, DEF, MID, FWD};
int: n_players;                         % Number of players
set of int: Players = 1..n_players;
set of int: Clubs = 1..20;

% Parameters (INTEGER arithmetic, scaled by 10)
int: UB;  % Tight upper bound on objective
array[Players] of int: expected_points;  % Scaled by 10
array[Players] of int: cost;  % Scaled by 10
array[Players] of bool: unavailable;
array[Position] of set of Players: PosPlayers;
array[Clubs] of set of Players: ClubPlayers;

% State from Previous GW
array[Players] of int: sp;  % Selling prices, scaled by 10
array[Players] of bool: y0;  % Current squad (renamed from y0_bool for simplicity)
int: B_bank;  % Scaled by 10
int: f;  % Free transfers

% Decision Variables
array[Players] of var 0..1: y;  % New squad membership (y_i)
var set of Players: Squad;  % Squad as set (channeled with y)
var set of Players: Starters;  % Starting XI (subset of squad)
var set of Players: Captain;  % Captain (singleton subset of Starters)
array[Position] of var set of Players: SquadPartitions;
array[Position] of var set of Players: StarterPartitions;
var 0..15: e;  % Extra transfers

% NEW: Explicit Transfer Variables and Constraints (replaces set diff)
array[Players] of var bool: t;  % t[i] = 1 if buy i (transfer in)
array[Players] of var bool: s;  % s[i] = 1 if sell i (transfer out)

% Squad update: y_i = y^0_i + t_i - s_i
constraint forall(i in Players) (
    y[i] = bool2int(y0[i]) + bool2int(t[i]) - bool2int(s[i])
);

% Channeling: link int array y with set variable Squad
constraint forall(i in Players) (
    (y[i] = 1) <-> (i in Squad)
);

% Cannot buy and sell the same player
constraint forall(i in Players) (
    not (t[i] /\ s[i])
);

% Can only buy players not in current squad
constraint forall(i in Players) (
    y0[i] -> not t[i]
);

% Can only sell players in current squad
constraint forall(i in Players) (
    not y0[i] -> not s[i]
);

% Extra transfers penalty: e >= number of buys - f
constraint e >= sum(i in Players) (bool2int(t[i])) - f;
constraint sum(i in Players) (bool2int(t[i])) <= 15;  % Logical bound

% Budget: cost of buys <= bank + proceeds from sells
constraint sum(i in Players) (cost[i] * bool2int(t[i])) <= 
           B_bank + sum(i in Players) (sp[i] * bool2int(s[i]));

% Subset Relationships
constraint Starters subset Squad;
constraint Captain subset Starters;

% Objective: Net points (scaled by 10)
var -1000..UB: z;
constraint z = sum(i in Starters) (expected_points[i]) 
             + sum(i in Captain) (expected_points[i]) 
             - 40 * e;

% Squad Size Constraints
constraint sum(i in Players) (y[i]) = 15;
constraint card(Starters) = 11;
constraint card(Captain) = 1;

% Position Requirements for Squad
constraint card(SquadPartitions[GK]) = 2;
constraint card(SquadPartitions[DEF]) = 5;
constraint card(SquadPartitions[MID]) = 5;
constraint card(SquadPartitions[FWD]) = 3;

% Position Requirements for Starters
constraint card(StarterPartitions[GK]) = 1;
constraint 3 <= card(StarterPartitions[DEF]) /\ card(StarterPartitions[DEF]) <= 5;
constraint 2 <= card(StarterPartitions[MID]) /\ card(StarterPartitions[MID]) <= 5;
constraint 1 <= card(StarterPartitions[FWD]) /\ card(StarterPartitions[FWD]) <= 3;

% Squad Partition Constraints
constraint forall(p1, p2 in Position where p1 < p2) (
    disjoint(SquadPartitions[p1], SquadPartitions[p2])
);
constraint Squad = array_union([SquadPartitions[p] | p in Position]);
constraint forall(p in Position) (
    SquadPartitions[p] subset PosPlayers[p]
);

% Starter Partition Constraints
constraint forall(p1, p2 in Position where p1 < p2) (
    disjoint(StarterPartitions[p1], StarterPartitions[p2])
);
constraint Starters = array_union([StarterPartitions[p] | p in Position]);
constraint forall(p in Position) (
    StarterPartitions[p] subset SquadPartitions[p]
);

% Club Limits
constraint forall(c in Clubs) (
    card(Squad intersect ClubPlayers[c]) <= 3
);

% Availability Constraint
constraint forall(i in Players where unavailable[i]) (
    not (i in Starters)
);

% Search Strategy
solve :: seq_search([
    set_search([SquadPartitions[p] | p in Position], first_fail, indomain_min),
    int_search([e], first_fail, indomain_min)
]) maximize z;

% Output
output [
    "Net z = ", show(z), " (scaled by 10, actual = ", show(int2float(z) / 10.0), " pts)\n",
    "e = ", show(e), "\n",
    "Squad = ", show({i | i in Players where y[i] = 1}), "\n",
    "Starters = ", show(Starters), "\n",
    "Captain = ", show(Captain), "\n"
];
