import random
import timeout_decorator
from agent_baselines import Agent

# -----
# Tunable constants
# -----
PROXIMITY_DEPTH = 9 # how many provinces away the value still reaches!
DIFFUSION_DIVISOR = 5.0 # 1 + the average degree of the standard map

# Supply centres will only change hands in Fall, so the two seasons want different things: 
# - Fall wants to be on a valuable province
# - Spring wants to be next to one, ready to capture in Fall.
SPRING = {'attack': 700, 'defence': 300, 'proximity': [100, 1000, 30, 10, 6, 5, 4, 3, 2, 1]}
FALL = {'attack': 600, 'defence': 400, 'proximity': [1000, 100, 30, 10, 6, 5, 4, 3, 2, 1]}

STRENGTH_WEIGHT = 1000 # bonus points for friendly unit adjacent to a province
COMPETITION_WEIGHT = 1000 # reduce points per enemy units adjacent to a province
CONVOY_MIN_UTILITY = 0.0 # convoy benefit must exceed the fleet/support opportunity cost



def base(location):
    """ 'STP/SC' -> 'STP'. The coasts are addresses for fleets, not provinces."""
    return location.split('/')[0]


class StudentAgent(Agent):
    '''
   What is a DumbBot algorithm?

   A dumbbot is a reflexive agent meaning it doesn't think ahead.
   It instead:

   1. Score's every province on the map: based on how important it is 
   to have a unit standing there. A province with enemy's supply centre 
   scores high; Empty ocean scores nothing.

   2. Distribute those scores outward across the map: So a province near
   something valuable gets a bit of that value.

   3. For each of those units: choose the highest-scoring possible place
   it can reach.

   Note: After researching a bit of the literature on agent attempts on this game
   I thought that the dumbbot's simplicity not only would match the restrictions
   provided but be easy to analyse later as all choices are fully explainable.
    '''

    @timeout_decorator.timeout(1)
    def __init__(self, agent_name='DumbBot', use_diffusion=True, use_supports=True,
                 use_redirect=True, use_convoys=True):
        super().__init__(agent_name)
        self.use_diffusion = use_diffusion
        self.use_supports = use_supports
        self.use_redirect = use_redirect
        self.use_convoys = use_convoys

    @timeout_decorator.timeout(1)
    def new_game(self, game, power_name):
        self.game = game
        self.power_name = power_name
        self.build_adjacency()

    @timeout_decorator.timeout(1) # This is only for updating the game engine and other states if any. Do not implement heavy stratergy here.
    def update_game(self, all_power_orders):
        # do not make changes to the following codes
        for power_name in all_power_orders.keys():
            self.game.set_orders(power_name, all_power_orders[power_name])
        self.game.process()
    @timeout_decorator.timeout(1)
    def get_actions(self):
        """This function is called once per phase. We need to dispatch the right handler"""
        phase = self.game.phase_type
        if phase == 'M': # Movement
            return self.movement_orders()
        if phase == 'R': # Retreat
            return self.retreat_orders()
        if phase == 'A': # Adjustment (build / disbands)
            return self.adjustment_orders()        
        return [] 

    # -----
    # Static map info, we only need to build once a game
    # -----
    def build_adjacency(self):
        """ Since armies and fleets move on different graphs. We need to build both"""
        game_map = self.game.map
        nodes = [loc.upper() for loc in game_map.loc_type.keys()]

        self.army_adjacency = {n: [] for n in nodes}
        self.fleet_adjacency = {n: [] for n in nodes}
        for a in nodes:
            for b in nodes:
                if a == b:
                    continue
                if game_map.abuts('A', a, '-', b): # .abuts checks to see if two nodes share a border
                    self.army_adjacency[a].append(b)
                if game_map.abuts('F', a, '-', b):
                    self.fleet_adjacency[a].append(b)

        self.provinces = sorted({base(n) for n in nodes})
        self.neighbours = {p: set() for p in self.provinces}
        for a in nodes:
            for b in self.army_adjacency[a] + self.fleet_adjacency[a]:
                self.neighbours[base(a)].add(base(b))
 
        self.supply_centres = set(game_map.scs)

    # -----
    # Step 1 - score every province
    # -----
    def power_sizes(self):
        """A 17-centre power scores 373, a 1-centre power score 21. So attacking the leader matters far more"""
        return {p: len(self.game.get_centers(p)) ** 2 + 4 * len(self.game.get_centers(p)) + 16 for p in self.game.powers.keys()}
    
    def province_scores(self):
        """Two numbers per province: how badly we want it, and how badly we need to keep it."""
        sizes = self.power_sizes()
        my_centres = set(self.game.get_centers(self.power_name))
         # Who owns which centre, and who has a unit sitting where. We need both.
        centre_owner = {}
        for power in self.game.powers.keys():
            for centre in self.game.get_centers(power):
                centre_owner[centre] = power
        
        unit_owner = {}
        for power in self.game.powers.keys():
            for unit in self.game.get_units(power):
                unit_owner.setdefault(base(unit.split()[1]), power)
        
        attack, defence = {}, {}
        for province in self.provinces:
            attack_value = defence_value = 0
            # Worth taking. Meaning that a supply centre is being held by someone
            if province in self.supply_centres and province not in my_centres:
                holder = centre_owner.get(province)
                attack_value = sizes[holder] if holder else 16
            # Worth defending. our own centre but has a big enemy close.
            if province in my_centres:
                for neighbour in self.neighbours[province]:
                    other = unit_owner.get(neighbour)
                    if other and other != self.power_name:
                        defence_value = max(defence_value, sizes[other])
            attack[province] = attack_value
            defence[province] = defence_value
        
        # this is a local force ratio. Our units are summed. enemies are taken as a max over powers,
        # this is because two enemies attacking one province will bounce off one another rather than combining.
        friendly = {p: 0 for p in self.provinces}
        hostile = {p: {} for p in self.provinces}
        for province in self.provinces:
            for neighbour in self.neighbours[province]:
                owner = unit_owner.get(neighbour)
                if owner is None:
                    continue
                if owner == self.power_name:
                    friendly[province] += 1
                else: 
                    hostile[province][owner] = hostile[province].get(owner, 0) + 1
        competition = {p: (max(hostile[p].values()) if hostile[p] else 0) for p in self.provinces}

        return attack, defence, friendly, competition

    # -----
    # Step 2 - spread the values across the map
    # -----
    def destination_values(self):
        """ as mentioned the second step of the dumbbot agent"""
        season = SPRING if self.game.get_current_phase()[0] == 'S' else FALL
        attack, defence, friendly, competition = self.province_scores()
 
        tables = []
        for adjacency in (self.army_adjacency, self.fleet_adjacency):
            level = {n: season['attack'] * attack[base(n)] + season['defence'] * defence[base(n)] for n in adjacency}
            total = {n: season['proximity'][0] * level[n] for n in adjacency}
 
            if self.use_diffusion:
                # Each pass averages a province with its neighbours, so value bleeds tgt
                # one step further out. Nine passes, each weighted less than the last.
                for depth in range(1, PROXIMITY_DEPTH + 1):
                    level = {n: (level[n] + sum(level[m] for m in adjacency[n])) / DIFFUSION_DIVISOR for n in adjacency}
                    weight = season['proximity'][depth]
                    for n in adjacency:
                        total[n] += weight * level[n]
    # Finally the local force ratio: good to have mates nearby, pretty shit to have enemies.
            for n in adjacency:
                total[n] += (STRENGTH_WEIGHT * friendly[base(n)] - COMPETITION_WEIGHT * competition[base(n)])
            tables.append(total)
 
        self.army_values, self.fleet_values = tables
 
    def value_of(self, unit_type, location):
        """Look up a score. Falls back to the base province if the coast isn't in the table."""
        table = self.army_values if unit_type == 'A' else self.fleet_values
        return table.get(location, table.get(base(location), 0.0))
    
    
    # -----
    # Step 3 - tuning these values into orders
    # -----

    def my_options(self):
        """{location: [legal order strings]} for the units we control.
 
        Note: get_all_possible_orders() hands back orders for all seven powers, so we
        cut it down to ours. """        
        possible = self.game.get_all_possible_orders()
        locations = self.game.get_orderable_locations(self.power_name)
        return {loc: possible[loc] for loc in locations if possible.get(loc)}
 
    def enemy_occupied(self):
        """Provinces with someone else's unit standing on them. We need strength 2 to take these."""
        held = set()
        for power in self.game.powers.keys():
            if power == self.power_name:
                continue
            for unit in self.game.get_units(power):
                held.add(base(unit.split()[1]))
        return held
    def movement_orders(self):
        """Pick destinations, add coordinated convoys, then repair the plan twice."""
        self.destination_values()
        options = self.my_options()
        occupied = self.enemy_occupied()
        self._convoy_locations = set()

        # Every ordinary move and hold, scored by where it lands. A VIA order
        # cannot be treated as an ordinary move: it requires matching fleet
        # convoy orders in the same phase.
        candidates = []
        for location, orders in options.items():
            for order in orders:
                if ' S ' in order or ' C ' in order or order.endswith(' VIA'):
                    continue
                words = order.split()
                unit_type, origin = words[0], words[1]
                target = words[words.index('-') + 1] if '-' in words else origin
                candidates.append((self.value_of(unit_type, target), location, order, base(target)))

        candidates.sort(key=lambda c: -c[0])
        candidates = self.jitter(candidates)

        # Greedy assignment keeps friendly units from bouncing into each other.
        chosen, claimed = {}, set()
        if self.use_convoys:
            self.add_convoys(options, candidates, chosen, claimed, occupied)
        for value, location, order, target in candidates:
            if location in chosen or target in claimed:
                continue
            chosen[location] = [order, value, target]
            claimed.add(target)
        for location, orders in options.items():
            if location not in chosen:
                fallback = next((order for order in orders
                                 if ' S ' not in order and ' C ' not in order
                                 and not order.endswith(' VIA')), orders[0])
                chosen[location] = [fallback, 0.0, base(location)]

        if self.use_supports:
            self.add_supports(options, chosen, occupied)
        if self.use_redirect:
            self.redirect_hopeless_attacks(candidates, chosen, occupied)
        return [entry[0] for entry in chosen.values()]

    def add_convoys(self, options, candidates, chosen, claimed, occupied):
        """Commit only convoy plans whose army gain pays for fleet coordination."""
        regular_best = {}
        for value, location, _, _ in candidates:
            regular_best[location] = max(regular_best.get(location, float('-inf')), value)

        convoy_offers, support_offers = {}, {}
        for location, orders in options.items():
            for order in orders:
                if ' C A ' in order and ' - ' in order:
                    route = order.split(' C ', 1)[1]
                    convoy_offers.setdefault(route, {})[location] = order
                elif ' S ' in order:
                    route = order.split(' S ', 1)[1]
                    support_offers.setdefault(route, []).append((location, order))

        plans = []
        for army_location, orders in options.items():
            for army_order in orders:
                words = army_order.split()
                if (not words or words[0] != 'A' or not army_order.endswith(' VIA')
                        or ' - ' not in army_order):
                    continue
                origin = words[1]
                target = words[words.index('-') + 1]
                route = army_order.rsplit(' VIA', 1)[0]
                fleet_orders = self.shortest_convoy_chain(
                    origin, target, convoy_offers.get(route, {}))
                if not fleet_orders:
                    continue

                value = self.value_of('A', target)
                army_best = regular_best.get(
                    army_location, self.value_of('A', origin))
                fleet_locations = {location for location, _ in fleet_orders}
                fleet_cost = sum(
                    max(0.0, regular_best.get(location, self.value_of('F', location))
                        - self.value_of('F', location))
                    for location in fleet_locations)

                support_orders = []
                support_cost = 0.0
                if base(target) in occupied:
                    needed = 1
                    choices = []
                    for location, order in support_offers.get(route, []):
                        if location == army_location or location in fleet_locations:
                            continue
                        unit_type = order.split()[0]
                        hold_value = self.value_of(unit_type, location)
                        cost = max(0.0, regular_best.get(location, hold_value) - hold_value)
                        choices.append((cost, location, order))
                    if len(choices) < needed:
                        continue
                    choices.sort(key=lambda choice: choice[0])
                    support_orders = choices[:needed]
                    support_cost = sum(choice[0] for choice in support_orders)

                utility = value - army_best - fleet_cost - support_cost
                if utility <= CONVOY_MIN_UTILITY:
                    continue
                plans.append((utility, value, army_location, army_order,
                              base(target), fleet_orders, support_orders))

        random.shuffle(plans)
        plans.sort(key=lambda plan: -plan[0])
        for (_, value, army_location, army_order, target, fleet_orders,
             support_orders) in plans:
            fleet_locations = {location for location, _ in fleet_orders}
            reserved_locations = fleet_locations | {army_location}
            reserved_locations.update(location for _, location, _ in support_orders)
            reserved_positions = {base(location) for location in reserved_locations}
            if (any(location in chosen for location in reserved_locations)
                    or target in claimed or reserved_positions & claimed):
                continue

            chosen[army_location] = [army_order, value, target]
            for fleet_location, fleet_order in fleet_orders:
                chosen[fleet_location] = [fleet_order, value, base(fleet_location)]
            for _, support_location, support_order in support_orders:
                chosen[support_location] = [support_order, value, base(support_location)]
            claimed.add(target)
            claimed.update(reserved_positions - {base(army_location)})
            self._convoy_locations.update(reserved_locations)

    def shortest_convoy_chain(self, origin, target, fleet_orders):
        """Retun the fewest offered fleets that connect an army to its target."""
        starts = [location for location in fleet_orders
                  if self.fleet_near_province(location, origin)]
        goals = {location for location in fleet_orders
                 if self.fleet_near_province(location, target)}
        if not starts or not goals:
            return []

        pending = [(location, [location]) for location in starts]
        seen = set(starts)
        while pending:
            current, path = pending.pop(0)
            if current in goals:
                return [(location, fleet_orders[location]) for location in path]
            for neighbour in self.fleet_adjacency.get(current, []):
                if neighbour in fleet_orders and neighbour not in seen:
                    seen.add(neighbour)
                    pending.append((neighbour, path + [neighbour]))
        return []

    def fleet_near_province(self, fleet_location, province):
        """Whether a convoying fleet touches either coast of an army province."""
        return any(base(neighbour) == base(province)
                   for neighbour in self.fleet_adjacency.get(fleet_location, []))

    @staticmethod
    def order_signature(order):
        """A support names ``A X - Y``; a convoying army appends ``VIA``."""
        return order.rsplit(' VIA', 1)[0] if order.endswith(' VIA') else order

    def jitter(self, candidates):
        """Shuffle options that are basically tied. Everyone moves at the same instant in this game, so a bot that always picks
        the same order can be counter-ordered every single tun. Randomising between equally good moves is the cheapest fix for that. """
        result, i = [], 0
        while i < len(candidates):
            j, top = i, candidates[i][0]
            while j < len(candidates) and \
                    abs(candidates[j][0] - top) < max(1.0, abs(top) * 0.02):
                j += 1
            block = candidates[i:j]
            random.shuffle(block)
            result.extend(block)
            i = j
        return result
 
    def add_supports(self, options, chosen, occupied):
        """Every unit has strength 1, so an attack on a defended province needs a second unit supporting it or it simply bounces."""
        offers = {}
        for location, orders in options.items():
            for order in orders:
                if ' S ' not in order:
                    continue
                offers.setdefault(order.split(' S ', 1)[1], []).append(
                    (location, order))
 
        attacks = sorted((entry for entry in chosen.values()
                          if ' - ' in entry[0] and entry[2] in occupied),
                         key=lambda e: -e[1])
 
        converted = set()
        for order, value, target in attacks:
            for location, support_order in offers.get(self.order_signature(order), []):
                if (location in converted or location in self._convoy_locations
                        or chosen[location][0] == order):
                    continue
                if chosen[location][1] < value:
                    chosen[location] = [support_order, value, base(location)]
                    converted.add(location)
                    break
 
    def redirect_hopeless_attacks(self, candidates, chosen, occupied):
        """An unsupported attack on a defended province bounces every tun.
        Left alone, units lock into that loop for the whole game. Send them
        somewhere they can actually arrive."""
        supported = {self.order_signature(order.split(' S ', 1)[1])
                     for order, _, _ in chosen.values() if ' S ' in order}
        claimed = {entry[2] for entry in chosen.values()}
 
        for location, entry in chosen.items():
            order, value, target = entry
            if (' - ' not in order or ' VIA' in order or target not in occupied
                    or self.order_signature(order) in supported):
                continue
            for alt_value, alt_location, alt_order, alt_target in candidates:
                if alt_location != location or alt_order == order:
                    continue
                if alt_target in occupied or alt_target in claimed:
                    continue
                claimed.discard(target)
                claimed.add(alt_target)
                chosen[location] = [alt_order, alt_value, alt_target]
                break
    
    # -----
    # Retreat and adjustment phases
    # -----
    def retreat_orders(self):
        """Dislodged units pick the best square they can reach. Disband only if there's nothing."""
        self.destination_values()
        orders, claimed = [], set()
        for location, options in self.my_options().items():
            best = best_value = best_target = None
            for order in options:
                words = order.split()
                if 'R' in words:
                    target = words[words.index('R') + 1]
                    if base(target) in claimed: # two retreats to one
                        continue # province disband both
                    value = self.value_of(words[0], target)
                else:
                    target, value = None, -1e9 # disband: last resort
                if best_value is None or value > best_value:
                    best, best_value, best_target = order, value, target
            if best:
                orders.append(best)
                if best_target:
                    claimed.add(base(best_target))
        return orders
 
    def adjustment_orders(self):
        """Builds are optional and very easy to forfeit. Disbands aren't optional at all.
 
        Note: builds only work in a home centre we still own and nothing is standing on.
        Parking our own units at home silently costs us units all game.
        """
        allowed = self.game.get_state()['builds'][self.power_name]['count']
        if allowed == 0:
            return []
 
        options = self.my_options()
        self.destination_values()
 
        if allowed > 0:
            candidates = []
            for location, orders in options.items():
                for order in orders:
                    if order.endswith(' B'):
                        words = order.split()
                        candidates.append(
                            (self.value_of(words[0], words[1]), location, order))
            candidates.sort(key=lambda c: -c[0])
            chosen, used = [], set()
            for _, location, order in candidates:
                if location in used:
                    continue
                chosen.append(order)
                used.add(location)
                if len(chosen) == allowed:
                    break
            return chosen
 
        candidates = []
        for location, orders in options.items():
            for order in orders:
                if order.endswith(' D'):
                    words = order.split()
                    candidates.append(
                        (self.value_of(words[0], words[1]), location, order))
        candidates.sort(key=lambda c: c[0]) # cheapest units go first
        return [order for _, _, order in candidates[:abs(allowed)]]
 
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
   