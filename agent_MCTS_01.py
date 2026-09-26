"""Basic time-bounded MCTS for the CITS3011 Diplomacy agent interface.

Root children hold complete order lists. Opponent orders are resampled for
each rollout because powers act simultaneously. Search restarts each phase.
"""
from collections import deque
import math
import random
import time

from diplomacy import Game
from agent_baselines import Agent


class _Node:
    def __init__(self, orders=()):
        self.orders = tuple(orders)
        self.visits = 0
        self.total = 0.0


class StudentAgent(Agent):
    THINK_SECONDS = 0.72
    MAX_ROLLOUTS = 24
    MAX_ACTIONS = 8
    EXPLORATION = 0.65

    def __init__(self, agent_name="Basic MCTS"):
        super().__init__(agent_name)

    def new_game(self, game, power_name):
        super().new_game(game, power_name)
        # Precompute legal movement adjacency for the positional heuristic.
        self.graph = {"A": {}, "F": {}}
        for source, neighbours in game.map.loc_abut.items():
            for kind in ("A", "F"):
                a = source.split("/")[0] if kind == "A" else source
                for neighbour in neighbours:
                    b = neighbour.split("/")[0] if kind == "A" else neighbour
                    if game.map.abuts(kind, source, "-", neighbour):
                        self.graph[kind].setdefault(a, set()).add(b)
                        self.graph[kind].setdefault(b, set()).add(a)

    def _distances(self, targets, kind):
        graph = self.graph[kind]
        distance = {}
        queue = deque()
        for loc in graph:
            if loc.split("/")[0] in targets:
                distance[loc] = 0
                queue.append(loc)
        while queue:
            loc = queue.popleft()
            for adjacent in graph[loc]:
                if adjacent not in distance:
                    distance[adjacent] = distance[loc] + 1
                    queue.append(adjacent)
        return distance

    @staticmethod
    def _base(unit):
        return unit.split()[1].split("/")[0]

    def _move_score(self, order, distances, targets, occupied):
        words = order.split()
        kind, source = words[:2]
        before = distances[kind].get(source if kind == "F" else source.split("/")[0], 8)
        if len(words) == 4 and words[2] == "-":
            dest = words[3]
            base = dest.split("/")[0]
            after = distances[kind].get(dest if kind == "F" else base, 8)
            score = 1.5 * (before - after)
            if base in targets:
                score += 3.0
            if base in occupied:
                score -= 1.0
            return score
        return 1.5 if source.split("/")[0] in targets else 0.0

    def _orders(self, game, power, possible, distances, targets, stochastic):
        locations = game.get_orderable_locations(power)
        if game.phase_type == "A":
            needed = len(game.powers[power].centers) - len(game.powers[power].units)
            if needed == 0:
                return []
            suffix = " B" if needed > 0 else " D"
            orders = []
            for loc in locations:
                choices = [o for o in possible.get(loc, ()) if o.endswith(suffix)]
                if choices:
                    orders.append(random.choice(choices) if stochastic else choices[0])
            if stochastic:
                random.shuffle(orders)
            return orders[:abs(needed)]

        if game.phase_type == "R":
            orders = []
            for loc in locations:
                choices = list(possible.get(loc, ()))
                retreat = [o for o in choices if " R " in o]
                if retreat:
                    orders.append(random.choice(retreat) if stochastic else retreat[0])
                elif choices:
                    orders.append(choices[0])
            return orders

        occupied = {self._base(u) for p in game.powers.values() for u in p.units}
        chosen = {}
        claimed = set()
        for loc in sorted(locations):
            choices = [o for o in possible.get(loc, ())
                       if (len(o.split()) == 4 and o.split()[2] == "-")
                       or (len(o.split()) == 3 and o.endswith(" H"))]
            if not choices:
                continue
            rated = []
            for order in choices:
                score = self._move_score(order, distances, targets, occupied)
                if order.split()[2] == "-" and order.split()[3].split("/")[0] in claimed:
                    score -= 4.0
                rated.append((score, order))
            rated.sort(reverse=True)
            if stochastic:
                pool = rated[:3]
                weights = [math.exp(score - pool[0][0]) for score, _ in pool]
                order = random.choices([o for _, o in pool], weights)[0]
            else:
                order = rated[0][1]
            chosen[loc] = order
            if order.split()[2] == "-":
                claimed.add(order.split()[3].split("/")[0])

        # Replace a unit's order only when its support order exists in the legal list.
        if stochastic and len(chosen) > 1 and random.random() < 0.7:
            moves = [o for o in chosen.values()
                     if len(o.split()) == 4 and o.split()[2] == "-"]
            random.shuffle(moves)
            for move in moves:
                for loc in sorted(chosen):
                    if loc == move.split()[1]:
                        continue
                    supporter = " ".join(chosen[loc].split()[:2])
                    support = supporter + " S " + move
                    if support in possible.get(loc, ()):
                        chosen[loc] = support
                        break
        return list(chosen.values())

    @staticmethod
    def _opponent_orders(game, power, possible):
        orders = []
        for loc in game.get_orderable_locations(power):
            choices = possible.get(loc, ())
            moves = [o for o in choices if len(o.split()) == 4 and o.split()[2] == "-"]
            holds = [o for o in choices if o.endswith(" H")]
            if moves and random.random() < 0.75:
                orders.append(random.choice(moves))
            elif holds:
                orders.append(holds[0])
        return orders

    def _value(self, game, distances, targets):
        power = game.powers[self.power_name]
        if len(power.centers) >= 18:
            return 100.0
        value = 8.0 * len(power.centers) + 2.0 * len(power.units)
        for unit in power.units:
            kind, loc = unit.split()[:2]
            base = loc.split("/")[0]
            if base in targets:
                value += 3.0  # Occupying a center before the fall capture.
            distance = distances[kind].get(loc if kind == "F" else base, 8)
            value += 2.0 / (1.0 + distance)
        return value

    def get_actions(self):
        started = time.monotonic()
        possible = self.game.get_all_possible_orders()
        targets = set(self.game.map.scs) - set(self.game.powers[self.power_name].centers)
        distances = {kind: self._distances(targets, kind) for kind in ("A", "F")}
        fallback = self._orders(self.game, self.power_name, possible,
                                distances, targets, stochastic=False)
        if self.game.phase_type != "M" or not fallback:
            return fallback

        candidates = [tuple(fallback)]
        seen = set(candidates)
        for _ in range(28):
            if len(candidates) >= self.MAX_ACTIONS or time.monotonic() - started > 0.18:
                break
            action = tuple(self._orders(self.game, self.power_name, possible,
                                         distances, targets, stochastic=True))
            if action not in seen:
                candidates.append(action)
                seen.add(action)
        if len(candidates) == 1:
            return fallback

        root = _Node()
        children = []
        untried = deque(candidates)
        baseline = self._value(self.game, distances, targets)
        snapshot = self.game.get_state()
        rules = list(self.game.rules)
        deadline = started + self.THINK_SECONDS
        last_cost = 0.04
        while root.visits < self.MAX_ROLLOUTS:
            if time.monotonic() + max(0.04, last_cost * 1.6) >= deadline:
                break
            if untried:
                node = _Node(untried.popleft())  # Expansion.
                children.append(node)
            else:
                log_n = math.log(root.visits + 1)
                node = max(children, key=lambda c: c.total / c.visits +
                           self.EXPLORATION * math.sqrt(log_n / c.visits))

            rollout_start = time.monotonic()
            simulation = Game(map_name=self.game.map_name, rules=rules)
            simulation.set_state(snapshot)
            simulation.set_orders(self.power_name, list(node.orders))
            static_scenario = random.random() < 0.35
            if not static_scenario:
                for opponent in simulation.powers:
                    if opponent != self.power_name:
                        orders = self._opponent_orders(simulation, opponent, possible)
                        simulation.set_orders(opponent, orders)
            simulation.process()  # One phase of actual game adjudication.
            reward = max(-1.0, min(1.0, (self._value(simulation, distances, targets)
                                         - baseline) / 10.0))
            node.visits += 1
            node.total += reward
            root.visits += 1  # Backpropagation.
            last_cost = time.monotonic() - rollout_start

        if not children:
            return fallback
        # Choose the most visited child and return its original current-phase orders.
        return list(max(children, key=lambda c: (c.visits, c.total / c.visits)).orders)
