import time
import timeout_decorator
from agent_baselines import Agent
import networkx as nx
import random

# Change to 1 once done
MAX_TIMEOUT = 1


class StudentAgent(Agent):
    @timeout_decorator.timeout(MAX_TIMEOUT)
    def __init__(self, agent_name="DunceBot"):
        super().__init__(agent_name)
        self.map_graph_army = None
        self.map_graph_navy = None

    @timeout_decorator.timeout(MAX_TIMEOUT)
    def new_game(self, game, power_name):
        self.game = game
        self.power_name = power_name
        """Implement your agent here."""
        self.build_map_graphs()
        self.current_enemies = [p for p in self.game.powers if p != self.power_name]
        self.centers = self.game.get_centers()

        self.north_powers = ["ENGLAND", "FRANCE", "GERMANY"]
        self.south_powers = ["TURKEY", "ITALY", "AUSTRIA", "RUSSIA"]

    @timeout_decorator.timeout(MAX_TIMEOUT)
    def update_game(self, all_power_orders):
        # do not make changes to the following codes
        for power_name in all_power_orders.keys():  # noqa: SIM118
            self.game.set_orders(power_name, all_power_orders[power_name])
        self.game.process()

    @timeout_decorator.timeout(MAX_TIMEOUT)
    def build_map_graphs(self):  # You can re-use this function if needed
        self.map_graph_army = nx.Graph()
        self.map_graph_navy = nx.Graph()

        locations = list(
            self.game.map.loc_type.keys()
        )  # locations with '/' are not real provinces

        for i in locations:
            if self.game.map.loc_type[i] in ["LAND", "COAST"]:
                self.map_graph_army.add_node(i.upper())
            if self.game.map.loc_type[i] in ["WATER", "COAST"]:
                self.map_graph_navy.add_node(i.upper())

        locations = [i.upper() for i in locations]

        for i in locations:
            for j in locations:
                if self.game.map.abuts("A", i, "-", j):
                    self.map_graph_army.add_edge(i, j)
                if self.game.map.abuts("F", i, "-", j):
                    self.map_graph_navy.add_edge(i, j)

    @timeout_decorator.timeout(MAX_TIMEOUT)
    def get_actions(self):
        """Implement your agent here."""

        return self._plans()

        """
        Return a list of orders. Each order is a string, with specific format. For the format, read the game rule and game engine documentation.
        
        Expected format:
        A LON H                  # Army at LON holds
        F IRI - MAO              # Fleet at IRI moves to MAO (and attack)
        A WAL S F LON            # Army at WAL supports Fleet at LON (and hold)
        F NTH S A EDI - YOR      # Fleet at NTH supports Army at EDI to move to YOR
        F NWG C A NWY - EDI      # Fleet at NWG convoys Army at NWY to EDI
        A NWY - EDI VIA          # Army at NWY moves to EDI via convoy
        A WAL R LON              # Army at WAL retreats to LON
        A LON D                  # Disband Army at LON
        A LON B                  # Build Army at LON
        F EDI B                  # Build Fleet at EDI

        Note: If an invalid order is sent to the engine, it will be accepted but with a result of 'void' (no effect).
        Note: For a 'support' action, two orders are needed, one for the supporter and one for the supportee. (Same for 'convoy')
        Note: For each unit, if no order is given, it will 'hold' by default.

        Useful Functions:
        
        # This is a dict of all the possible orders for each unit at each location (for all powers).
        possible_orders = self.game.get_all_possible_orders()

        # This is a list of all orderable locations for the power you control.
        orderable_locations = self.game.get_orderable_locations(self.power_name)
    
        # Combining these two, you can have the full action space for the power you control.

        # You can re-use the build_map_graphs function in the GreedyAgent to build the connection graph of the map if needed.
        
        """

    # def _plans(self, power_name):
    #     SCS = {
    #         # Austria
    #         "BUDAPEST": "BUD",
    #         "TRIESTE": "TRI",
    #         "VIENNA": "VIE",
    #         # England
    #         "EDINBURGH": "EDI",
    #         "LONDON": "LON",
    #         "LIVERPOOL": "LVP",
    #         # France
    #         "BREST": "BRE",
    #         "MARSEILLES": "MAR",
    #         "PARIS": "PAR",
    #         # Germany
    #         "BERLIN": "BER",
    #         "KIEL": "KIE",
    #         "MUNICH": "MUN",
    #         # Italy
    #         "NAPLES": "NAP",
    #         "ROME": "ROM",
    #         "VENICE": "VEN",
    #         # Russia
    #         "MOSCOW": "MOS",
    #         "SEVASTOPOL": "SEV",
    #         "ST. PETERSBURG": "STP",
    #         "WARSAW": "WAR",
    #         # Turkey
    #         "ANKARA": "ANK",
    #         "CONSTANTINOPLE": "CON",
    #         "SMYRNA": "SMY",
    #         # Neutral
    #         "BELGIUM": "BEL",
    #         "BULGARIA": "BUL",
    #         "DENMARK": "DEN",
    #         "GREECE": "GRE",
    #         "HOLLAND": "HOL",
    #         "NORWAY": "NWY",
    #         "PORTUGAL": "POR",
    #         "RUMANIA": "RUM",
    #         "SERBIA": "SER",
    #         "SPAIN": "SPA",
    #         "SWEDEN": "SWE",
    #         "TUNIS": "TUN",
    #     }

    #     all_possible_orders = self.game.get_all_possible_orders()
    #     all_orderable_locations = {
    #         p: self.game.get_orderable_locations(p) for p in self.game.powers
    #     }
    #     # scs = self.game.map.scs
    #     priority = []

    #     if self.power_name == "ENGLAND":
    #         priority = [
    #             SCS["EDINBURGH"],
    #             SCS["LONDON"],
    #             SCS["LIVERPOOL"],
    #             SCS["NORWAY"],
    #             SCS["SWEDEN"],
    #             SCS["ST. PETERSBURG"],
    #             SCS["DENMARK"],
    #             SCS["BELGIUM"],
    #             SCS["HOLLAND"],
    #             SCS["KIEL"],
    #             SCS["BERLIN"],
    #             SCS["MUNICH"],
    #             SCS["PARIS"],
    #             SCS["BREST"],
    #             SCS["MARSEILLES"],
    #             SCS["SPAIN"],
    #             SCS["PORTUGAL"],
    #             SCS["TUNIS"],
    #         ]
    #     # else:
    #     #     priority = [
    #     #         SCS["MOSCOW"],
    #     #         SCS["WARSAW"],
    #     #         SCS["SEVASTOPOL"],
    #     #         SCS["MUNICH"],
    #     #         SCS["VIENNA"],
    #     #         SCS["BUDAPEST"],
    #     #         SCS["RUMANIA"],
    #     #         SCS["BULGARIA"],
    #     #         SCS["SERBIA"],
    #     #         SCS["TRIESTE"],
    #     #         SCS["VENICE"],
    #     #         SCS["RUMANIA"],
    #     #         SCS["NAPLES"],
    #     #         SCS["GREECE"],
    #     #         SCS["CONSTANTINOPLE"],
    #     #         SCS["ANKARA"],
    #     #         SCS["SMYRNA"],
    #     #         SCS["TUNIS"],
    #     #     ]

    #     priority = [
    #         loc
    #         for loc in priority
    #         if loc not in all_orderable_locations[power_name]
    #     ]

    #     paths = []
    #     army_paths = []
    #     navy_paths = []
    #     for start in all_orderable_locations[power_name]:
    #         for loc in priority:
    #             path_army, path_navy = [], []
    #             if (
    #                 start in self.map_graph_army
    #                 and loc in self.map_graph_army
    #                 and nx.has_path(self.map_graph_army, start, loc)
    #             ):
    #                 path_army = nx.shortest_path(
    #                     self.map_graph_army, source=start, target=loc
    #                 )

    #             if (
    #                 start in self.map_graph_navy
    #                 and loc in self.map_graph_navy
    #                 and nx.has_path(self.map_graph_navy, start, loc)
    #             ):
    #                 path_navy = nx.shortest_path(
    #                     self.map_graph_navy, source=start, target=loc
    #                 )

    #             if path_army and path_navy:
    #                 paths.append(min(path_army, path_navy))
    #             elif path_army:
    #                 army_paths.append(path_army)
    #             elif path_navy:
    #                 navy_paths.append(path_navy)

    #     acts = []

    #     if navy_paths:
    #         shortest_path = min(navy_paths, key=len)
    #         for act in all_possible_orders[shortest_path[0]]:
    #             if shortest_path[1] in act:
    #                 acts.append(act)

    #     if army_paths:
    #         shortest_path = min(army_paths, key=len)
    #         for act in all_possible_orders[shortest_path[0]]:
    #             if shortest_path[1] in act:
    #                 acts.append(act)

    #     if paths:
    #         shortest_path = min(paths, key=len)
    #         for act in all_possible_orders[shortest_path[0]]:
    #             if shortest_path[1] in act:
    #                 acts.append(act)

    #     return acts
    #         # print(acts)

    def _plans(self):
        TARGETS = []
        if self.power_name in self.north_powers:
            TARGETS = [
                "NWY",
                "BEL",
                "HOL",
                "DEN",
                "SWE",
                "BRE",
                "PAR",
                "KIE",
                "BER",
                "MUN",
                "SPA",
                "POR",
                "MAR",
                "STP",
                "TUN",
            ]
        else:
            TARGETS = [
                "MOS",
                "WAR",
                "SEV",
                "MUN",
                "VIE",
                "BUD",
                "RUM",
                "BUL",
                "SER",
                "TRI",
                "VEN",
                "NAP",
                "GRE",
                "CON",
                "ANK",
                "SMY",
                "TUN",
            ]
        all_possible_orders = self.game.get_all_possible_orders()
        all_orderable_locations = {
            p: self.game.get_orderable_locations(p) for p in self.game.powers
        }
        phase = self.game.get_current_phase()[-1]
        orders = []

        # Builds / disbands
        if phase == "A":
            power = self.game.get_power(self.power_name)
            count = abs(len(power.centers) - len(power.units))
            preferred = "F" if self.north_powers else "A"

            for loc in all_orderable_locations[self.power_name]:
                opts = all_possible_orders[loc]
                preferred_builds = [
                    o for o in opts if o.startswith(preferred) and o.endswith(" B")
                ]
                other = [o for o in opts if o.endswith((" B", " D"))]
                if preferred_builds or other:
                    orders.append((preferred_builds or other)[0])
            return orders[:count]

        # Retreats
        if phase == "R":
            for loc in all_orderable_locations[self.power_name]:
                opts = all_possible_orders[loc]
                retreats = [o for o in opts if " R " in o]
                orders.append(retreats[0] if retreats else opts[0])
            return orders

        # Movement
        owned = set(self.game.get_centers(self.power_name))
        targets = [t for t in TARGETS if t not in owned]
        claimed = set()
        unit_orders = {}  # unit -> order
        unit_locs = {}  # unit -> key into all_possible_orders

        # Where enemies are, and which provinces they could move into this turn
        enemy_locs, threatened = set(), set()
        for p, locs in all_orderable_locations.items():
            if p == self.power_name:
                continue
            for l in locs:
                enemy_locs.add(l)
                for o in all_possible_orders[l]:
                    w = o.split()
                    if len(w) >= 4 and w[2] == "-":
                        threatened.add(w[3][:3])

        # Pass 1: moves
        for loc in all_orderable_locations[self.power_name]:
            opts = all_possible_orders[loc]
            unit = " ".join(opts[0].split()[:2])  # e.g. 'F EDI' or 'F SPA/SC'
            unit_locs[unit] = loc
            graph = self.map_graph_army if unit[0] == "A" else self.map_graph_navy

            best = None
            if unit[2:] in graph:
                paths = nx.single_source_shortest_path(graph, unit[2:])
                reachable = [paths[t] for t in targets if t in paths]
                best = min(reachable, key=len, default=None)

            if not best or len(best) == 1:
                unit_orders[unit] = f"{unit} H"
                continue

            step = best[1][:3]
            move = next(
                (
                    o
                    for o in opts
                    if o.split()[2:3] == ["-"]
                    and o.split()[3][:3] == step
                    and not o.endswith("VIA")
                ),
                None,
            )
            if move and step not in claimed:
                unit_orders[unit] = move
                claimed.add(step)
            else:
                unit_orders[unit] = f"{unit} H"

        # Pass 2: turn holding units into supports
        def same_unit(a, b):
            return a[0] == b[0] and a[2:5] == b[2:5]

        moves = {}  # destination -> our unit moving there
        for unit, o in unit_orders.items():
            w = o.split()
            if len(w) == 4 and w[2] == "-":
                moves[w[3][:3]] = unit
        staying = {u for u, o in unit_orders.items() if " - " not in o}

        for unit, o in unit_orders.items():
            if not o.endswith(" H"):
                continue
            best_opt, best_score = None, 0
            for opt in all_possible_orders[unit_locs[unit]]:
                w = opt.split()
                if len(w) < 5 or w[2] != "S" or not same_unit(" ".join(w[:2]), unit):
                    continue
                supported = " ".join(w[3:5])

                if len(w) == 7:  # support a move: 'F EDI S F LON - NTH'
                    dest = w[6][:3]
                    if dest in moves and same_unit(moves[dest], supported):
                        score = (
                            3 if dest in enemy_locs else 2 if dest in threatened else 0
                        )
                    else:
                        score = 0
                else:  # support a hold: 'F EDI S F LON'
                    ours = any(same_unit(s, supported) for s in staying if s != unit)
                    loc3 = supported[2:5]
                    score = 1 if ours and loc3 in owned and loc3 in threatened else 0

                if score > best_score:
                    best_opt, best_score = opt, score
            if best_opt:
                unit_orders[unit] = best_opt

        return list(unit_orders.values())
