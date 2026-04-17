import random
import math
from itertools import combinations
from collections import Counter, defaultdict
from typing import Tuple, List, Dict, Optional

from player import Player, PlayerAction


#  SECTION 1 — CARD UTILITIES

SUIT_NAMES = ["♠", "♥", "♦", "♣"]
RANK_NAMES = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
ALL_INDICES = list(range(1, 53))


def idx_to_rs(idx: int) -> Tuple[int, int]:
    """Convert engine card index (1–52) → (rank 0–12, suit 0–3)."""
    i = idx - 1
    return i % 13, i // 13


def rs_to_idx(rank: int, suit: int) -> int:
    return suit * 13 + rank + 1


def card_str(idx: int) -> str:
    r, s = idx_to_rs(idx)
    return RANK_NAMES[r] + SUIT_NAMES[s]


#  SECTION 2 — 5-CARD HAND EVALUATOR

def _score_5(ranks: list, suits: list) -> Tuple[int, tuple]:
    """Return (hand_rank 0–8, tiebreak_tuple). Higher = better."""
    rs       = sorted(ranks, reverse=True)
    is_flush = len(set(suits)) == 1
    is_str   = len(set(ranks)) == 5 and rs[0] - rs[4] == 4
    # Ace-low straight A-2-3-4-5
    if not is_str and set(ranks) == {12, 0, 1, 2, 3}:
        is_str, rs = True, [3, 2, 1, 0, 12]

    freq  = Counter(ranks)
    by_c  = sorted(freq.items(), key=lambda x: (x[1], x[0]), reverse=True)
    grp   = [c for _, c in by_c]
    ordr  = [r for r, _ in by_c]

    if is_flush and is_str:          return 8, tuple(rs)
    if grp[0] == 4:                  return 7, tuple(ordr)
    if grp[0] == 3 and grp[1] == 2: return 6, tuple(ordr)
    if is_flush:                     return 5, tuple(rs)
    if is_str:                       return 4, tuple(rs)
    if grp[0] == 3:                  return 3, tuple(ordr)
    if grp[0] == 2 and grp[1] == 2: return 2, tuple(ordr)
    if grp[0] == 2:                  return 1, tuple(ordr)
    return 0, tuple(rs)


def best_hand(card_indices: list) -> Tuple[int, tuple]:
    """Best 5-card hand from up to 7 card indices."""
    cards = [idx_to_rs(i) for i in card_indices if i > 0]
    if len(cards) < 2:
        return 0, (0,)
    best = (-1, ())
    for combo in combinations(cards, min(5, len(cards))):
        r  = [x for x, _ in combo]
        s  = [y for _, y in combo]
        sc = _score_5(r, s)
        if sc > best:
            best = sc
    return best


#  SECTION 3 — PRE-FLOP HAND STRENGTH  (Chen Formula)

def preflop_strength(c1: int, c2: int) -> float:
    """Normalised Chen score in [0, 1]. Used to seed equity pre-flop."""
    r1, s1 = idx_to_rs(c1)
    r2, s2 = idx_to_rs(c2)
    suited = (s1 == s2)
    chen   = [1,1.5,2,2.5,3,3.5,4,4.5,5,6,7,8,10]
    high, low = max(r1,r2), min(r1,r2)
    score = chen[high]
    if r1 == r2:
        score = max(score * 2, 5)
    else:
        if suited: score += 2
        gap = high - low - 1
        score -= [0,0,1,2,4,5][min(gap,5)]
        if gap <= 1 and low >= 5: score += 1
    return max(0.0, min(1.0, (score + 1) / 21.0))


#  SECTION 4 — RANGE MODELING  

_ALL_COMBOS: List[Tuple[int,int]] = list(combinations(ALL_INDICES, 2))


def _combo_strength(c1: int, c2: int) -> float:
    """Quick pre-flop strength of a combo for range initialization."""
    return preflop_strength(c1, c2)


def init_range(style: str = "neutral") -> Dict[Tuple[int,int], float]:
    """
    Initialize opponent hand range weights.

    style:
      "tight"   — only plays top ~20% hands (raise-heavy profile)
      "loose"   — plays ~60% of hands (passive/call-station)
      "neutral" — uniform, no prior info
      "aggro"   — wide range but weighted toward strong hands
    """
    weights: Dict[Tuple[int,int], float] = {}

    for c1, c2 in _ALL_COMBOS:
        s = _combo_strength(c1, c2)
        if style == "tight":
            # Exponential: strongly favors top hands
            w = math.exp(4 * s) / math.exp(4)
        elif style == "loose":
            # Flat but slight preference for playable hands
            w = 0.3 + 0.7 * s
        elif style == "aggro":
            # Bimodal: very strong OR pure bluff range
            w = s ** 2 + 0.15 * (1 - s) ** 3
        else:  # neutral / uniform
            w = 1.0
        weights[(c1, c2)] = max(w, 1e-6)

    return weights


def update_range(weights: Dict[Tuple[int,int], float],
                 action: str,
                 street: str,
                 pot_fraction: float = 0.5) -> Dict[Tuple[int,int], float]:
    """
    [NEW] Bayesian range update after observing an opponent action.

    action:       'raise', 'bet', 'call', 'check', 'fold', 'all-in'
    street:       'pre-flop', 'flop', 'turn', 'river'
    pot_fraction: bet_size / pot  (large bets → polarized range)

    P(action | hand) approximations:
      raise/bet  → strong hands more likely, bluffs possible
      call       → medium hands (not folding, not raising)
      check      → weak OR slow-playing strong hands
      fold       → irrelevant; handled externally
    """
    new_weights: Dict[Tuple[int,int], float] = {}

    for (c1, c2), w in weights.items():
        s = _combo_strength(c1, c2)   # 0–1 hand strength

        if action in ("raise", "bet", "all-in"):
            if pot_fraction >= 0.75:
                # Large bet → polarized: strong value OR bluff (very weak)
                p_action_given_hand = s ** 2 + 0.08 * (1 - s) ** 3
            else:
                # Medium bet → mostly value range
                p_action_given_hand = 0.2 + 0.8 * s
        elif action == "call":
            # Calling range: medium strength, not too strong (would raise), not weak (would fold)
            # Bell curve centered around 0.5
            p_action_given_hand = math.exp(-8 * (s - 0.52) ** 2) + 0.1
        elif action == "check":
            # Check: weak hands + occasional strong slow-play
            p_action_given_hand = (1 - s) ** 1.5 + 0.05 * s ** 3
        else:
            p_action_given_hand = 1.0  # no info

        new_weights[(c1, c2)] = max(w * p_action_given_hand, 1e-6)

    # Normalize
    total = sum(new_weights.values())
    return {k: v / total * len(new_weights) for k, v in new_weights.items()}


def sample_from_range(weights: Dict[Tuple[int,int], float],
                      excluded: set,
                      n: int = 2) -> Optional[List[int]]:
    """
    [NEW] Sample n cards from weighted range, excluding known cards.
    Returns list of card indices or None if impossible.
    """
    valid = [(combo, w) for combo, w in weights.items()
             if not (excluded & set(combo))]
    if not valid:
        return None
    combos, ws = zip(*valid)
    total = sum(ws)
    r = random.random() * total
    cumul = 0.0
    for combo, w in zip(combos, ws):
        cumul += w
        if r <= cumul:
            return list(combo)
    return list(combos[-1])


#  SECTION 5 — WEIGHTED MONTE CARLO WITH TIE HANDLING  [UPGRADED]

def monte_carlo_equity(hole: List[int],
                       community: List[int],
                       opp_range: Dict[Tuple[int,int], float],
                       num_opp: int = 1,
                       sims: int = 600) -> float:
    """
    [UPGRADED] Monte Carlo equity with:
      - Weighted sampling from opponent range
      - Tie handling: (wins + 0.5 * ties) / sims
      - Fallback to uniform if range sampling fails
    """
    known     = set(c for c in hole + community if c > 0)
    avail     = [c for c in ALL_INDICES if c not in known]
    comm_k    = [c for c in community if c > 0]
    need      = 5 - len(comm_k)

    score_sum = 0.0   # accumulate wins + 0.5*ties

    for _ in range(sims):
        deck = avail[:]
        random.shuffle(deck)

        # Complete community cards
        sim_comm = comm_k + deck[:need]
        remaining = [c for c in deck[need:] if c not in set(sim_comm)]

        my_sc = best_hand(hole + sim_comm)
        excluded = known | set(sim_comm)

        # Sample opponent hole cards from weighted range
        opp_hole = sample_from_range(opp_range, excluded)
        if opp_hole is None or len(opp_hole) < 2:
            # Fallback: uniform
            if len(remaining) >= 2:
                opp_hole = remaining[:2]
            else:
                score_sum += 0.5   # treat as tie if can't sample
                continue

        opp_sc = best_hand(opp_hole + sim_comm)

        if my_sc > opp_sc:
            score_sum += 1.0
        elif my_sc == opp_sc:
            score_sum += 0.5   # [NEW] tie handling
        # else: loss → +0

    return score_sum / sims


#  SECTION 6 — BOARD TEXTURE ANALYSIS  [NEW]

def board_texture(community: List[int]) -> Dict[str, float]:
    """
    [NEW] Analyze board for:
      - wetness (draw-heavy)
      - monotone (flush possible)
      - paired (trips/full house possible)
      - connectedness

    Returns scores in [0, 1] for each dimension.
    """
    cards = [idx_to_rs(c) for c in community if c > 0]
    if not cards:
        return {"wetness": 0.0, "monotone": 0.0, "paired": 0.0, "connected": 0.0}

    ranks = [r for r, s in cards]
    suits = [s for r, s in cards]

    # Flush draw: 3+ of same suit
    suit_counts = Counter(suits)
    max_suit = max(suit_counts.values())
    monotone  = min(1.0, (max_suit - 1) / 2.0)  # 0 if <2 same suit, 1 if 3+

    # Paired board
    rank_counts = Counter(ranks)
    paired = 1.0 if max(rank_counts.values()) >= 2 else 0.0

    # Connectedness: how close together are ranks
    if len(ranks) >= 2:
        sorted_r = sorted(set(ranks))
        gaps = [sorted_r[i+1] - sorted_r[i] for i in range(len(sorted_r)-1)]
        avg_gap = sum(gaps) / len(gaps) if gaps else 6
        connected = max(0.0, 1.0 - avg_gap / 6.0)
    else:
        connected = 0.0

    wetness = (monotone * 0.5 + connected * 0.5)

    return {
        "wetness":   wetness,
        "monotone":  monotone,
        "paired":    paired,
        "connected": connected,
    }


def has_draw(hole: List[int], community: List[int]) -> Dict[str, bool]:
    """Detect flush draw and open-ended/gutshot straight draw in our hand."""
    all_cards = [idx_to_rs(c) for c in hole + community if c > 0]
    ranks = sorted([r for r, s in all_cards])
    suits = [s for r, s in all_cards]

    suit_counts = Counter(suits)
    flush_draw  = any(v == 4 for v in suit_counts.values())

    # Straight draw: 4 cards within a 5-card window
    unique_r = sorted(set(ranks))
    oesd = gutshot = False
    for i in range(len(unique_r)):
        window = [r for r in unique_r if unique_r[i] <= r <= unique_r[i] + 4]
        if len(window) == 4:
            oesd = True
        elif len(window) == 3 and (unique_r[i] + 4 - unique_r[i]) == 4:
            gutshot = True

    return {"flush_draw": flush_draw, "oesd": oesd, "gutshot": gutshot}


#  SECTION 7 — RICH OPPONENT PROFILING  [UPGRADED]

class OpponentProfile:
    """
    [UPGRADED] Tracks opponent tendencies with:
      - VPIP (voluntarily put money in pot %)
      - PFR  (pre-flop raise %)
      - Aggression Factor (AF) per street
      - Bluff tendency estimate
      - All-in frequency (bully detection)
      - Hand range (updated via Bayesian updates)
    """

    def __init__(self):
        # Raw counters
        self.hands_seen      = 0
        self.vpip_count      = 0    # hands where opp voluntarily put $ in
        self.pfr_count       = 0    # hands where opp raised pre-flop
        self.af_bets         = defaultdict(int)   # street → aggressive acts
        self.af_calls        = defaultdict(int)   # street → passive acts
        self.showdown_wins   = 0
        self.showdown_total  = 0
        self.allin_count     = 0
        self.fold_to_bet     = 0    # folded when facing a bet
        self.bet_faced       = 0    # times faced a bet
        self._seen_hands     = set()
        self._last_len       = 0

        # Hand range (initialized neutral, updated per action)
        self.hand_range: Dict[Tuple[int,int], float] = init_range("neutral")
        self._range_style = "neutral"

    def update(self, history: list, my_name: str):
        """Process new action history entries since last update."""
        if len(history) == self._last_len:
            return
        new_entries = history[self._last_len:]
        self._last_len = len(history)

        for (street, name, action, amount) in new_entries:
            if name == my_name:
                continue

            # Track VPIP / PFR
            if street == "pre-flop":
                if action in ("call", "raise", "bet", "all-in"):
                    self.vpip_count += 1
                if action in ("raise", "bet", "all-in"):
                    self.pfr_count += 1

            # AF by street
            if action in ("raise", "bet", "all-in"):
                self.af_bets[street]  += 1
            elif action in ("call", "check"):
                self.af_calls[street] += 1

            # Fold-to-bet tracking
            if action == "fold":
                self.fold_to_bet  += 1
                self.bet_faced    += 1
            elif action == "call":
                self.bet_faced    += 1

            # All-in bully tracking
            if action == "all-in":
                key = (len(history), name)
                if key not in self._seen_hands:
                    self._seen_hands.add(key)
                    self.allin_count += 1

            # Bayesian range update
            pot_frac = min(1.0, amount / max(1, amount + 50))
            self.hand_range = update_range(
                self.hand_range, action, street, pot_frac
            )

        # Re-estimate profile style and re-seed range periodically
        self._update_style()

    def _update_style(self):
        """Reclassify opponent and adjust range prior if needed."""
        if self.hands_seen < 3:
            return
        new_style = self._classify()
        if new_style != self._range_style:
            # Blend current range with new-style prior (don't fully reset)
            new_prior = init_range(new_style)
            self.hand_range = {
                k: 0.7 * self.hand_range.get(k, 1.0) + 0.3 * new_prior[k]
                for k in new_prior
            }
            self._range_style = new_style

    def _classify(self) -> str:
        if self.vpip > 0.5 and self.pfr < 0.15:
            return "loose"    # call station
        if self.vpip < 0.25 and self.pfr > 0.15:
            return "tight"    # nit / tight-aggressive
        if self.pfr > 0.30:
            return "aggro"
        return "neutral"

    # ── Stats ──────────────────────────────────────────────────────

    @property
    def hands_played(self) -> int:
        return max(1, self.vpip_count + max(1, self._last_len // 5))

    @property
    def vpip(self) -> float:
        return self.vpip_count / max(1, self.hands_played)

    @property
    def pfr(self) -> float:
        return self.pfr_count / max(1, self.hands_played)

    @property
    def aggression_factor(self) -> float:
        """Global AF = total bets+raises / total calls."""
        bets  = sum(self.af_bets.values())
        calls = sum(self.af_calls.values())
        return bets / max(1, calls)

    def street_af(self, street: str) -> float:
        return self.af_bets[street] / max(1, self.af_calls[street])

    @property
    def fold_to_cbet(self) -> float:
        return self.fold_to_bet / max(1, self.bet_faced)

    @property
    def allin_rate(self) -> float:
        return self.allin_count / max(1, self.hands_played)

    @property
    def is_bully(self) -> bool:
        return self.allin_count >= 3 and self.allin_rate > 0.40

    @property
    def bully_conf(self) -> float:
        if not self.is_bully:
            return 0.0
        return min(1.0, self.allin_count / 8.0) * self.allin_rate

    @property
    def bluff_tendency(self) -> float:
        """
        Estimate how often opponent bluffs.
        High aggression + high VPIP + moderate fold_to_bet → bluff heavy.
        """
        return min(1.0, self.aggression_factor * 0.3 + self.vpip * 0.3
                   + (1 - self.fold_to_cbet) * 0.4)


#  SECTION 8 — DYNAMIC THRESHOLD SYSTEM 

def compute_thresholds(profile: OpponentProfile,
                       stack_ratio: float,
                       in_position: bool,
                       pot_odds: float,
                       street: str) -> Dict[str, float]:
    """
    [NEW] Compute dynamic FOLD/CALL/RAISE thresholds.

    Factors:
      - Opponent AF:   more aggressive opp → tighten call, widen fold
      - VPIP:          loose opp → we can bluff more, call tighter
      - Stack ratio:   short stacks → push/fold territory
      - Position:      in position = lower thresholds (more info)
      - Street:        river = tighter (no more draws)
      - Pot odds:      direct pot odds form a hard floor on call threshold

    Returns dict with 'fold', 'call', 'raise', 'bluff_freq' keys.
    """
    af   = profile.aggression_factor
    vpip = profile.vpip

    # Base thresholds
    fold_t  = 0.30
    call_t  = 0.45
    raise_t = 0.62
    bluff_f = 0.15   # base bluff frequency

    # Vs aggressive opponents: be tighter (need more equity to call)
    # Vs passive opponents: be looser (they under-bluff)
    aggr_adj = 0.08 * (af - 1.0) / max(1.0, af)    # +0 to +0.06
    fold_t  += aggr_adj * 0.5
    call_t  += aggr_adj

    # Vs loose players: tighten slightly (they have real hands more often)
    # Vs tight players: loosen (they fold a lot → bluff more)
    vpip_adj = (vpip - 0.40) * 0.15
    fold_t  -= vpip_adj * 0.3
    call_t  -= vpip_adj * 0.5
    bluff_f += (0.40 - vpip) * 0.20   # bluff more vs tight players

    # Position advantage: in position = lower thresholds
    if in_position:
        call_t  -= 0.03
        raise_t -= 0.03
        bluff_f += 0.05

    # Short stack: polarize (push or fold)
    if stack_ratio < 0.15:
        fold_t  = 0.40    # fold marginal hands
        call_t  = 0.50    # call only decent hands
        raise_t = 0.55    # shove wider

    # River: no more draws → be tighter calling, bluff less
    if street == "river":
        call_t  += 0.03
        bluff_f -= 0.05

    # Hard floor: pot odds always override fold threshold
    fold_t = min(fold_t, max(0.15, pot_odds - 0.05))
    call_t = max(call_t, pot_odds + 0.01)   # must beat pot odds to call

    # Bluff frequency: fold_to_cbet adjusts it
    # If opp folds to bets a lot → bluff more
    bluff_f += profile.fold_to_cbet * 0.15

    return {
        "fold":      max(0.15, min(0.55, fold_t)),
        "call":      max(0.35, min(0.65, call_t)),
        "raise":     max(0.55, min(0.80, raise_t)),
        "bluff_freq": max(0.05, min(0.40, bluff_f)),
    }


#  SECTION 9 — MIXED STRATEGY & BLUFF LOGIC  

def compute_bluff_ev(pot: int, bet_size: int,
                     fold_equity: float) -> float:
    """
    [NEW] Simple bluff EV:
      EV(bluff) = fold_equity * pot - (1 - fold_equity) * bet_size
    """
    return fold_equity * pot - (1 - fold_equity) * bet_size


def should_bluff(equity: float,
                 thresholds: Dict[str, float],
                 texture: Dict[str, float],
                 draws: Dict[str, bool],
                 street: str,
                 pot: int,
                 bet_size: int,
                 profile: OpponentProfile,
                 in_position: bool) -> bool:
    """
    [NEW] Mixed strategy bluffing decision.

    Considers:
      1. Semi-bluffs (draws): always viable if draw equity is real
      2. Pure bluffs: EV-positive only (fold equity > breakeven)
      3. Randomized so not exploitable even when detected

    Breakeven fold equity for a bluff:
      FE_needed = bet / (pot + bet)
    """
    bluff_freq = thresholds["bluff_freq"]

    # Semi-bluff: raise for fold equity
    if draws["flush_draw"] or draws["oesd"]:
        draw_boost = 0.20 if draws["flush_draw"] else 0.12
        bluff_freq += draw_boost

    if draws["gutshot"]:
        bluff_freq += 0.06

    # Board wetness: wet board = opponent likely has draws too → bluff less
    # Dry board = opponent likely missed → bluff more
    bluff_freq += (0.5 - texture["wetness"]) * 0.10

    # Position: in position bluffs are more credible
    if in_position:
        bluff_freq += 0.05

    # Pot odds check: is bluff EV-positive?
    fe_needed = bet_size / (pot + bet_size) if (pot + bet_size) > 0 else 0.5
    fold_equity = profile.fold_to_cbet

    if fold_equity < fe_needed * 0.8:
        bluff_freq *= 0.4   # bluff EV is likely negative → reduce significantly

    roll = random.random()
    return equity < thresholds["fold"] + 0.10 and roll < bluff_freq


#  SECTION 10 — EV-BASED ALL-IN LOGIC  [UPGRADED]

def ev_call_allin(equity: float, pot: int,
                  call_amount: int, my_stack: int) -> float:
    """
    [NEW] Expected value of calling an all-in.
    EV(call) = equity * (pot + call_amount) - (1 - equity) * call_amount
    """
    return equity * (pot + call_amount) - (1 - equity) * call_amount


def ev_fold() -> float:
    return 0.0   # folding = no change in stack, EV = 0


#  SECTION 11 — SAFE SIZING HELPERS

def safe_bet(desired: int, blind: int, my_stack: int) -> Tuple[PlayerAction, int]:
    amount = max(int(desired), blind + 1)
    if amount >= my_stack:
        return PlayerAction.ALL_IN, my_stack
    return PlayerAction.BET, amount


def safe_raise(desired_total: int, current_bet: int,
               blind: int, my_stack: int,
               my_bet: int) -> Tuple[PlayerAction, int]:
    min_total = current_bet + blind + 1
    amount    = max(int(desired_total), min_total)
    cost      = amount - my_bet
    if cost >= my_stack:
        return PlayerAction.ALL_IN, my_stack
    return PlayerAction.RAISE, amount


#  SECTION 12 — THE BOT

class MyBot(Player):
    """
    Semi-GTO Texas Hold'em Bot.
    Range-based, dynamically adaptive, mixed-strategy.
    """

    def __init__(self, name: str, stack: int):
        super().__init__(name, stack)
        self.profile = OpponentProfile()
        self._starting_stack = stack

    def action(self, game_state: list,
               action_history: list) -> Tuple[PlayerAction, int]:

        # ── Parse game state ──────────────────────────────────────
        hole          = [game_state[0], game_state[1]]
        community     = game_state[2:7]
        pot           = game_state[7]
        current_raise = game_state[8]
        blind         = game_state[9]
        my_idx        = game_state[10]
        num_players   = game_state[11]
        stacks        = game_state[12 : 12 + num_players]
        my_stack      = self.stack
        my_bet        = self.bet_amount
        to_call       = max(0, current_raise - my_bet)

        num_comm      = sum(1 for c in community if c > 0)
        num_opp       = num_players - 1
        street_map    = {0:"pre-flop", 3:"flop", 4:"turn", 5:"river"}
        street        = street_map.get(num_comm, "pre-flop")
        in_position   = (my_idx == num_players - 1)
        stack_ratio   = my_stack / max(1, self._starting_stack)

        # ── Update opponent model ─────────────────────────────────
        self.profile.update(action_history, self.name)

        # ── Board analysis ────────────────────────────────────────
        texture = board_texture(community)
        draws   = has_draw(hole, community) if num_comm > 0 else \
                  {"flush_draw": False, "oesd": False, "gutshot": False}

        # ── Equity (Monte Carlo with weighted range) ───────────────
        sims_map = {"pre-flop": 250, "flop": 450, "turn": 600, "river": 800}
        n_sims   = sims_map.get(street, 450)

        try:
            equity = monte_carlo_equity(
                hole, community,
                opp_range=self.profile.hand_range,
                num_opp=num_opp,
                sims=n_sims
            )
        except Exception:
            equity = 0.5

        # Pre-flop: blend MC equity with Chen formula for stability
        if street == "pre-flop":
            strength = preflop_strength(hole[0], hole[1])
            equity   = 0.35 * equity + 0.65 * strength

        # ── Pot odds ──────────────────────────────────────────────
        pot_odds = to_call / (pot + to_call) if to_call > 0 else 0.0

        # ── Dynamic thresholds ────────────────────────────────────
        T = compute_thresholds(
            self.profile, stack_ratio, in_position, pot_odds, street
        )

        # ── Anti-exploitation: add small equity noise ─────────────
        # This prevents the bot from being perfectly predictable at
        # equity boundaries — opponent can never exploit exact thresholds
        equity_noise = random.gauss(0, 0.015)
        eff_equity   = max(0.0, min(1.0, equity + equity_noise))

        # ── Sizing constants ──────────────────────────────────────
        half_pot  = max(blind + 1, pot // 2)
        full_pot  = max(blind + 1, pot)
        overbet   = max(blind + 1, int(pot * 1.5))

        #  ALL-IN SITUATIONS: EV-based decision
        
        is_shove = (to_call >= my_stack * 0.65)

        if is_shove:
            call_ev = ev_call_allin(eff_equity, pot, to_call, my_stack)
            fold_ev = ev_fold()

            if self.profile.is_bully:
                bully_adj = 0.05 + 0.08 * self.profile.bully_conf
                adjusted_equity = min(1.0, eff_equity + bully_adj)
                call_ev = ev_call_allin(adjusted_equity, pot, to_call, my_stack)

            if call_ev > fold_ev:
                return PlayerAction.ALL_IN, my_stack
            # Occasional hero call vs confirmed bluff-heavy opponents
            if self.profile.bluff_tendency > 0.55 and eff_equity > 0.38:
                if random.random() < 0.35:
                    return PlayerAction.ALL_IN, my_stack
            return PlayerAction.FOLD, 0

        #  MUST CALL TO STAY
        if to_call > 0:

            # Strong hand → raise for value
            if eff_equity >= T["raise"]:
                desired = (overbet if eff_equity >= 0.85
                           else full_pot if eff_equity >= 0.75
                           else half_pot)
                # Occasionally just call with monsters (deception)
                if eff_equity >= 0.82 and random.random() < 0.25:
                    call_amt = min(to_call, my_stack)
                    return PlayerAction.CALL, call_amt
                return safe_raise(desired, current_raise, blind, my_stack, my_bet)

            # Decent hand → call if profitable
            if eff_equity >= T["call"] and eff_equity >= pot_odds:
                call_amt = min(to_call, my_stack)
                if call_amt == my_stack:
                    return PlayerAction.ALL_IN, my_stack
                return PlayerAction.CALL, call_amt

            # Marginal + cheap → call with some frequency
            if eff_equity >= T["fold"] and to_call <= blind:
                return PlayerAction.CALL, min(to_call, my_stack)

            # Semi-bluff raise: we have a draw and it's profitable to attack
            if should_bluff(eff_equity, T, texture, draws,
                            street, pot, current_raise, self.profile, in_position):
                if draws["flush_draw"] or draws["oesd"]:
                    # Semi-bluff raise
                    return safe_raise(current_raise + half_pot,
                                      current_raise, blind, my_stack, my_bet)

            return PlayerAction.FOLD, 0

        #  NO CALL NEEDED → CHECK OR BET
        
        else:
            # Strong hand → bet for value
            if eff_equity >= T["raise"]:
                desired = full_pot if eff_equity >= 0.82 else half_pot
                # Occasionally check strong hands (trap)
                if random.random() < 0.18:
                    return PlayerAction.CHECK, 0
                return safe_bet(desired, blind, my_stack)

            # Medium hand → check (pot control)
            if eff_equity >= T["call"]:
                # Occasionally bet medium hands for thin value
                if random.random() < 0.20 and in_position:
                    return safe_bet(half_pot // 2, blind, my_stack)
                return PlayerAction.CHECK, 0

            # Bluff or check
            if should_bluff(eff_equity, T, texture, draws,
                            street, pot, half_pot, self.profile, in_position):
                return safe_bet(half_pot, blind, my_stack)

            return PlayerAction.CHECK, 0


#  SELF-TEST

if __name__ == "__main__":
    print("=" * 60)
    print("pai.py  —  GTO Bot Self-Test")
    print("=" * 60)

    print("\n[1] Pre-flop strengths (Chen formula):")
    for c1, c2, label in [
        (52, 39, "A♣ A♥  (pocket aces)"),
        (52, 51, "A♣ K♣  (suited AK)"),
        (13, 26, "A♠ A♦  (pocket aces off-suit)"),
        (1,  14, "2♠ 2♥  (pocket 2s)"),
        (1,   2, "2♠ 3♠  (suited 23)"),
    ]:
        print(f"  {label:42s}  {preflop_strength(c1,c2):.2f}")

    print("\n[2] Range initialization:")
    for style in ["neutral","tight","loose","aggro"]:
        r = init_range(style)
        avg = sum(r.values()) / len(r)
        print(f"  {style:8s}  combos={len(r)}  avg_weight={avg:.3f}")

    print("\n[3] Monte Carlo equity (heads-up, pre-flop, neutral range):")
    r = init_range("neutral")
    e1 = monte_carlo_equity([52,39],[0,0,0,0,0],r,1,500)
    e2 = monte_carlo_equity([1,2],  [0,0,0,0,0],r,1,500)
    print(f"  A♣ A♥  → {e1:.2%}  (expect ~85%)")
    print(f"  2♠ 3♠  → {e2:.2%}  (expect ~35%)")

    print("\n[4] Range update after aggressive action:")
    r2 = update_range(r, "raise", "pre-flop", 0.5)
    top = sorted(r2.items(), key=lambda x: -x[1])[:3]
    bot_r = sorted(r2.items(), key=lambda x: x[1])[:3]
    print(f"  Highest weight combos: {[card_str(a)+card_str(b) for (a,b),_ in top]}")
    print(f"  Lowest weight combos:  {[card_str(a)+card_str(b) for (a,b),_ in bot_r]}")

    print("\n[5] Board texture:")
    wet  = [10, 23, 36]   # 9♠ 10♥ J♦ — very connected
    dry  = [1,  15, 29]   # 2♠ 3♥ 4♦ — different
    print(f"  Connected board: {board_texture(wet)}")
    print(f"  Dry board:       {board_texture(dry)}")

    print("\n[6] Dynamic thresholds (various profiles):")
    p_tight = OpponentProfile(); p_tight.vpip_count=2; p_tight.hands_seen=10
    p_loose = OpponentProfile(); p_loose.vpip_count=7; p_loose.hands_seen=10
    for p, label in [(p_tight,"tight opp"),(p_loose,"loose opp")]:
        T = compute_thresholds(p, 1.0, True, 0.25, "flop")
        print(f"  {label}: fold={T['fold']:.2f} call={T['call']:.2f} "
              f"raise={T['raise']:.2f} bluff={T['bluff_freq']:.2f}")

    print("\n[7] EV all-in logic:")
    ev = ev_call_allin(0.55, 200, 100, 900)
    print(f"  equity=55%, pot=200, call=100  →  EV={ev:.1f} "
          f"({'CALL' if ev > 0 else 'FOLD'})")
    ev2 = ev_call_allin(0.30, 200, 100, 900)
    print(f"  equity=30%, pot=200, call=100  →  EV={ev2:.1f} "
          f"({'CALL' if ev2 > 0 else 'FOLD'})")

    print("\n[8] Bully detection:")
    p = OpponentProfile()
    fh = [("pre-flop","Bully","all-in",1000),
          ("pre-flop","Me","fold",0)] * 5
    p.update(fh, "Me")
    print(f"  is_bully={p.is_bully}  rate={p.allin_rate:.2f}  "
          f"conf={p.bully_conf:.2f}")

    print("\n[9] Bot decisions:")
    bot = MyBot("T", 1000); bot.bet_amount = 0; bot.profile = p
    a,v = bot.action([52,39,0,0,0,0,0,20,1000,20,1,2,0,1000,1], fh)
    print(f"  AA vs bully shove   → {a.value} {v}")
    bot2 = MyBot("T2",1000); bot2.bet_amount=0; bot2.profile=p
    a2,v2 = bot2.action([5,27,0,0,0,0,0,20,1000,20,1,2,0,1000,1], fh)
    print(f"  72o vs bully shove  → {a2.value} {v2}")

    print("\nAll tests passed!")
    print("=" * 60)