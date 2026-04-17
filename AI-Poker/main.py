# """
# main.py  —  Run this to play against MyBot
# """
# from pai import MyBot
# from baseplayers import InputPlayer
# from game import PokerGame, GamePhase
# from card import Rank, Suit

# SUIT_SYMBOLS = {Suit.SPADES: "♠", Suit.HEARTS: "♥", Suit.DIAMONDS: "♦", Suit.CLUBS: "♣"}
# RANK_SYMBOLS = {
#     Rank.TWO: "2", Rank.THREE: "3", Rank.FOUR: "4", Rank.FIVE: "5",
#     Rank.SIX: "6", Rank.SEVEN: "7", Rank.EIGHT: "8", Rank.NINE: "9",
#     Rank.TEN: "10", Rank.JACK: "J", Rank.QUEEN: "Q", Rank.KING: "K", Rank.ACE: "A"
# }

# def print_your_cards(player):
#     if not player.hole_cards:
#         return
#     cards = [f"{RANK_SYMBOLS[c.rank]}{SUIT_SYMBOLS[c.suit]}" for c in player.hole_cards]
#     print(f"\n  ╔═══════════════╗")
#     print(f"  ║  Your cards:  ║")
#     print(f"  ║   {cards[0]:>3}  {cards[1]:<3}    ║")
#     print(f"  ╚═══════════════╝")

# def is_hand_over(game):
#     if game.phase == GamePhase.SHOWDOWN:
#         return True
#     active = [p for p in game.players if p.status.value == "active"]
#     all_in = [p for p in game.players if p.status.value == "all-in"]
#     folded = [p for p in game.players if p.status.value == "folded"]
#     # Only one player hasn't folded
#     if len(folded) == len(game.players) - 1:
#         return True
#     return False

# # ── Setup ────────────────────────────────────────────────────────
# you   = InputPlayer("You", 1000)
# bot   = MyBot("MyBot", 1000)
# game  = PokerGame([you, bot], big_blind=20)

# hand_count = 0
# print("\n" + "="*50)
# print("   TEXAS HOLD'EM  —  You vs MyBot")
# print("="*50)

# # ── Main game loop ────────────────────────────────────────────────
# while True:
#     if not game.start_new_hand():
#         print("\nGame over — not enough chips to continue.")
#         break

#     hand_count += 1
#     print(f"\n{'─'*40}")
#     print(f"  Hand #{hand_count}  |  You: ${you.stack}  |  MyBot: ${bot.stack}")
#     print(f"{'─'*40}")

#     # Show your cards right after deal
#     print_your_cards(you)

#     # ── Betting loop ──────────────────────────────────────────────
#     while True:
#         if is_hand_over(game):
#             break

#         current_player = game.players[game.active_player_index]

#         # Show your cards before every decision
#         if current_player.name == "You":
#             print_your_cards(you)

#         try:
#             game.get_player_input()
#         except Exception as e:
#             print(f"[Error in game loop: {e}]")
#             break

#     # ── End of hand summary ───────────────────────────────────────
#     print(f"\n{'─'*40}")
#     print(f"  After hand #{hand_count}:")
#     print(f"  You:   ${you.stack}")
#     print(f"  MyBot: ${bot.stack}")
#     print(f"{'─'*40}")

#     # Check if anyone is bust
#     if you.stack <= 0:
#         print("\n  You are out of chips. MyBot wins the session!")
#         break
#     if bot.stack <= 0:
#         print("\n  MyBot is out of chips. You win the session!")
#         break

# print("\nThanks for playing!")

"""
main.py — Texas Hold'em  │  You vs MyBot
==========================================
Run: python main.py
"""

import os
import time
from pai import MyBot
from baseplayers import InputPlayer
from game import PokerGame, GamePhase
from player import PlayerAction
from card import Rank, Suit

# ══════════════════════════════════════════════════════════════════
#  CARD ART
# ══════════════════════════════════════════════════════════════════

SUIT_SYM = {
    Suit.SPADES:   "♠",
    Suit.HEARTS:   "♥",
    Suit.DIAMONDS: "♦",
    Suit.CLUBS:    "♣",
}
RANK_SYM = {
    Rank.TWO:"2", Rank.THREE:"3", Rank.FOUR:"4",  Rank.FIVE:"5",
    Rank.SIX:"6", Rank.SEVEN:"7", Rank.EIGHT:"8", Rank.NINE:"9",
    Rank.TEN:"10",Rank.JACK:"J",  Rank.QUEEN:"Q", Rank.KING:"K",
    Rank.ACE:"A",
}
RED_SUITS = {Suit.HEARTS, Suit.DIAMONDS}

def _card_lines(card, hidden=False):
    """Return 7 lines of ASCII art for one card."""
    if hidden:
        return [
            "╔═════╗",
            "║░░░░░║",
            "║░░░░░║",
            "║░░░░░║",
            "║░░░░░║",
            "║░░░░░║",
            "╚═════╝",
        ]
    r = RANK_SYM[card.rank]
    s = SUIT_SYM[card.suit]
    top = f"{r:<2}   "   # rank top-left
    bot = f"   {r:>2}"   # rank bottom-right
    return [
        "╔═════╗",
        f"║{top}║",
        "║     ║",
        f"║  {s}  ║",
        "║     ║",
        f"║{bot}║",
        "╚═════╝",
    ]

def _empty_card_lines():
    return [
        "╔═════╗",
        "║     ║",
        "║     ║",
        "║  ?  ║",
        "║     ║",
        "║     ║",
        "╚═════╝",
    ]

def render_cards(cards, hidden=False, empty_slots=0) -> str:
    """Render a row of cards side by side. Pads with empty_slots grey slots."""
    all_cols = []
    for c in cards:
        all_cols.append(_card_lines(c, hidden))
    for _ in range(empty_slots):
        all_cols.append(_empty_card_lines())
    if not all_cols:
        return "    (no cards)"
    lines = ["  ".join(col[row] for col in all_cols) for row in range(7)]
    return "\n".join("    " + ln for ln in lines)

def card_label(card) -> str:
    return RANK_SYM[card.rank] + SUIT_SYM[card.suit]


# ══════════════════════════════════════════════════════════════════
#  LAYOUT PRIMITIVES
# ══════════════════════════════════════════════════════════════════

W = 66   # display width

def clr():
    os.system("cls" if os.name == "nt" else "clear")

def div(ch="─"):
    print(ch * W)

def banner(text, ch="═"):
    inner = f"  {text}  "
    side  = ch * ((W - len(inner)) // 2)
    print(side + inner + side)

def sec(label):
    """Section header — looks like a labelled divider."""
    tag = f"[ {label} ]"
    pad = (W - len(tag)) // 2
    print("─" * pad + tag + "─" * (W - pad - len(tag)))

def blank():
    print()


# ══════════════════════════════════════════════════════════════════
#  TABLE RENDERER
# ══════════════════════════════════════════════════════════════════

def _phase_label(game) -> str:
    return {
        GamePhase.PRE_FLOP: "PRE-FLOP",
        GamePhase.FLOP:     "FLOP",
        GamePhase.TURN:     "TURN",
        GamePhase.RIVER:    "RIVER",
        GamePhase.SHOWDOWN: "SHOWDOWN",
        GamePhase.SETUP:    "SETUP",
    }.get(game.phase, "?")

def _stack_bar(you_stack, bot_stack, pot, width=38):
    total    = max(1, you_stack + bot_stack + pot)
    you_w    = round(you_stack / total * width)
    pot_w    = round(pot       / total * width)
    bot_w    = width - you_w - pot_w
    return "█" * you_w + "▒" * pot_w + "░" * bot_w

def draw_table(game, you, bot, *, reveal_bot=False, hand_num=0, blind=20):
    """Redraw the entire terminal with the current game state."""
    clr()

    # ── Top banner ────────────────────────────────────────────────
    banner("TEXAS HOLD'EM  ─  You vs MyBot")
    div()
    phase = _phase_label(game)
    print(f"  Hand #{hand_num:<4}  Phase: {phase:<10}  Blind: ${blind}")
    div()

    # ── Stack bar ─────────────────────────────────────────────────
    bar = _stack_bar(you.stack, bot.stack, game.pot)
    print(f"  You ${you.stack:<6}  [{bar}]  Bot ${bot.stack}")
    print(f"  {'':30}  Pot: ${game.pot}")
    div()

    # ── BOT HAND ──────────────────────────────────────────────────
    blank()
    sec("BOT'S HAND")
    blank()
    if bot.hole_cards:
        print(render_cards(bot.hole_cards, hidden=not reveal_bot))
        if reveal_bot:
            labels = "  ".join(f"  {card_label(c)}" for c in bot.hole_cards)
            print(f"    {labels}")
    else:
        print("    (no cards yet)")
    blank()

    # ── COMMUNITY CARDS ───────────────────────────────────────────
    sec("COMMUNITY CARDS")
    blank()
    n = len(game.community_cards)
    print(render_cards(game.community_cards, empty_slots=5 - n))
    if game.community_cards:
        labels = "  ".join(f"  {card_label(c)}" for c in game.community_cards)
        print(f"    {labels}")
    blank()

    # ── YOUR HAND ─────────────────────────────────────────────────
    sec("YOUR HAND")
    blank()
    if you.hole_cards:
        print(render_cards(you.hole_cards))
        labels = "  ".join(f"  {card_label(c)}" for c in you.hole_cards)
        print(f"    {labels}")
    else:
        print("    (no cards yet)")
    blank()


def draw_action_log(history, n=10):
    """Print the last n actions in a clean table."""
    if not history:
        return
    sec("ACTION LOG  (this hand)")
    blank()
    recent = history[-n:]
    for street, name, act, amount in recent:
        street_tag = f"[{street[:3].upper()}]"
        name_col   = f"{name[:9]:<10}"
        act_col    = f"{act.upper():<8}"
        amt_col    = f"+${amount}" if amount > 0 else "     "
        print(f"    {street_tag}  {name_col}  {act_col}  {amt_col}")
    blank()


def draw_showdown(game, you, bot, *, you_gained, bot_gained, you_wins, bot_wins, hand_num, blind):
    """Full showdown screen — reveals bot cards + result banner."""
    draw_table(game, you, bot, reveal_bot=True, hand_num=hand_num, blind=blind)
    draw_action_log(game.action_history)

    # ── Result ────────────────────────────────────────────────────
    div("═")
    if you_gained > 0:
        print(f"  >>> YOU WIN  +${you_gained}   (your stack: ${you.stack})")
    elif bot_gained > 0:
        print(f"  >>> BOT WINS +${bot_gained}   (your stack: ${you.stack})")
    else:
        print(f"  >>> SPLIT POT  (stacks unchanged)")

    total_h = you_wins + bot_wins
    if total_h > 0:
        pct = 100 * you_wins / total_h
        print(f"  Record: You {you_wins}W  Bot {bot_wins}W  "
              f"({pct:.0f}% over {total_h} hands)")
    div("═")


# ══════════════════════════════════════════════════════════════════
#  GAME SETUP
# ══════════════════════════════════════════════════════════════════

STARTING_STACK = 1000
BLIND          = 20

you  = InputPlayer("You",   STARTING_STACK)
bot  = MyBot("MyBot",       STARTING_STACK)
game = PokerGame([you, bot], big_blind=BLIND)

hand_count = 0
you_wins   = 0
bot_wins   = 0

# ── Welcome ────────────────────────────────────────────────────────
clr()
banner("TEXAS HOLD'EM  ─  You vs MyBot")
div()
blank()
print(f"  Starting stacks : ${STARTING_STACK} each")
print(f"  Blind           : ${BLIND}  (rotates each hand)")
print(f"  Rules           : Standard Hold'em, one blind, no side pots")
blank()
print("  HOW TO PLAY:")
print("  • Type the NUMBER shown next to each action (1, 2, 3...)")
print("  • Bot hands are face-down during play, revealed after each round")
print("  • Action log shows every action taken this hand")
blank()
div()
input("  Press Enter to start...")


# ══════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════════

while True:
    # ── Start hand ────────────────────────────────────────────────
    if not game.start_new_hand():
        clr()
        banner("GAME OVER")
        print("\n  Not enough chips to continue.")
        break

    hand_count += 1
    prev_you  = you.stack
    prev_bot  = bot.stack
    num_tries = 0

    # ── Betting loop ──────────────────────────────────────────────
    while game.phase != GamePhase.SHOWDOWN:

        # Safety valve — mirrors engine's own main.py
        if num_tries == 3:
            game.player_action(PlayerAction.FOLD, 0)
            num_tries = 0
            continue

        current_player = game.players[game.active_player_index]

        # Engine pattern: 1 active player, bets settled → advance street
        if (game.num_active_players() == 1
                and current_player.bet_amount == game.current_bet):
            game.advance_game_phase()
            continue

        # ── Redraw ────────────────────────────────────────────────
        draw_table(game, you, bot,
                   reveal_bot=False,
                   hand_num=hand_count,
                   blind=BLIND)
        draw_action_log(game.action_history)

        # ── Turn indicator ────────────────────────────────────────
        if current_player.name == "You":
            call_amt = max(0, game.current_bet - you.bet_amount)
            div()
            print(f"  YOUR TURN")
            print(f"  Stack: ${you.stack:<7}  To call: ${call_amt:<7}  Pot: ${game.pot}")
            div()
        else:
            div()
            print(f"  Bot is thinking...")
            div()

        # ── Get action ────────────────────────────────────────────
        try:
            game.get_player_input()
            num_tries = 0
        except Exception as e:
            print(f"  [Error: {e}]")
            num_tries += 1

        time.sleep(0.15)

    # ── End of hand — show showdown screen ────────────────────────
    you_gained = you.stack - prev_you
    bot_gained = bot.stack - prev_bot

    if you_gained > 0:
        you_wins += 1
    elif bot_gained > 0:
        bot_wins += 1

    draw_showdown(
        game, you, bot,
        you_gained=you_gained,
        bot_gained=bot_gained,
        you_wins=you_wins,
        bot_wins=bot_wins,
        hand_num=hand_count,
        blind=BLIND,
    )

    # ── Bust check ────────────────────────────────────────────────
    blank()
    if you.stack <= 0:
        print("  You are out of chips. MyBot wins the session!")
        blank()
        break
    if bot.stack <= 0:
        print("  Bot is out of chips. You win the session!")
        blank()
        break

    # ── Continue prompt ───────────────────────────────────────────
    try:
        ans = input("  Next hand? [Enter = yes  /  q = quit]: ").strip().lower()
        if ans == "q":
            break
    except (EOFError, KeyboardInterrupt):
        break


# ══════════════════════════════════════════════════════════════════
#  SESSION SUMMARY
# ══════════════════════════════════════════════════════════════════

clr()
banner("SESSION SUMMARY")
div()
blank()
print(f"  Hands played   : {hand_count}")
print(f"  You won        : {you_wins}")
print(f"  Bot won        : {bot_wins}")
print(f"  Final stacks   : You ${you.stack}  │  Bot ${bot.stack}")
net = you.stack - STARTING_STACK
sign = "+" if net >= 0 else ""
print(f"  Net profit     : {sign}{net}")
blank()
div("═")
blank()