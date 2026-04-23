### AI Poker Bot
**Overview**

This project is a command line Texas Hold’em poker game where you play against an AI opponent called MyBot. The gameplay flow, interface, and outputs are based on the terminal session shown, where both players start with 1000 chips and compete through multiple hands with clearly displayed phases, actions, and results.

**Features**

The game supports 1v1 Texas Hold’em gameplay between a human player and MyBot through an interactive command line interface. It displays the full game state in real time including player stacks, pot size, current phase, and community cards as they are revealed. The interface shows your hole cards in a structured format while keeping the bot’s cards hidden until showdown, and provides numbered input options for actions such as fold, call, and raise. The system maintains a continuous action log and updates the pot and stacks dynamically after every move, as seen in the gameplay output.

**Algorithms Used**

The bot combines Monte Carlo simulation with an incomplete information decision model. At each decision point it samples many possible opponent hands and future community cards to estimate win probability, using this equity to guide actions like calling, raising, or folding. Since poker is a hidden information game, the bot does not know the opponent’s exact cards and instead operates over a distribution of possible hands inferred from the current state and action history. This allows it to make probabilistic decisions under uncertainty, balancing aggression and caution based on estimated outcomes rather than fixed rules.

**Rules**

The implementation follows a simplified version of Texas Hold’em as reflected in the output. Both players begin with equal stacks of 1000 chips and a blind value of 20 which rotates between players each hand. The game progresses through the standard phases of pre flop, flop, turn, river, and showdown, with community cards revealed step by step. A standard 52 card deck is used and aces can act as either high or low depending on the best hand. There is no side pot handling, so all chips go into a single pot regardless of betting situations, and the game is strictly limited to two players.

**Run**
```bash
git clone https://github.com/arsh-ngui/Monte-carlo-based-AI-poker
```
**Gameplay**

When the game starts, the terminal displays the match setup and begins a new hand. For example:
```bash
TEXAS HOLD EM  You vs MyBot

NEW HAND
You posts big blind 20

Phase pre-flop
Pot 20
```
Your cards are shown clearly:
```bash
Your cards
3♣ 6♠
```
You choose actions by entering numbers:
```bash
1 Fold
2 Call 21
3 Raise
Example Hand
```
A sample flow from the output shows how actions progress:
```bash
Phase flop
Community cards ['6♥', 'A♣', 'A♠']

You bets 100
MyBot raises to 121
You calls 21
```
The game continues through turn and river, updating pot and stacks in real time.

Showdown

At the end of the hand, both hands are revealed and evaluated:
```bash
You ['3♣', '6♠'] TWO_PAIR
MyBot ['Q♥', 'Q♠'] TWO_PAIR

MyBot wins 768 chips
```
After this, updated stacks are displayed and the next hand begins automatically:
```bash
After hand #1
You 616
MyBot 1384
```
**MyBot**

MyBot uses custom decision logic that determines when to bet, raise, call, or check based on the current game state, which can be observed through its actions across different phases in the output.

**Notes**

The implementation runs entirely in the terminal and focuses on clarity of gameplay and state transitions. It does not include side pot logic or advanced opponent modeling, but provides a clean and functional base for further AI improvements.

## Contributers

-Anubhav Suri https://github.com/Surianubhav
-Vedant Agarwal https://github.com/Vedant0527
-Abhinav Saini https://github.com/AbhinavSaini18
