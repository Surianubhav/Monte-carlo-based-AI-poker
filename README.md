### AI Poker Bot 
An AI-powered poker bot for Texas Hold’em built using Monte Carlo simulations, range-based opponent modeling, and CFR-inspired strategies. This project is based on and extended from the IEEE AI Poker framework, with significant custom modifications for improved decision-making and exploitability.

**Project Overview -** 
Poker is an imperfect information game, making it a strong benchmark for AI systems dealing with uncertainty, probability, and strategic reasoning.

**This bot is designed to -** 
Estimate hand strength using simulation
Model opponent behavior dynamically
Make decisions using game-theoretic principles
Adapt strategies to exploit weaknesses

**Core Concepts Used:**
1. Monte Carlo Equity Estimation
Simulates thousands of random game outcomes
Estimates probability of winning against opponent ranges
Helps in decision-making (fold / call / raise)
2. Range-Based Opponent Modeling
Opponents are modeled as ranges of possible hands, not fixed cards
Ranges are updated based on betting behavior
Enables adaptive and exploitative play
3. CFR-Inspired Strategy (Counterfactual Regret Minimization)
Uses regret-based logic to approximate optimal strategies
Balances between aggressive and defensive actions
Avoids being easily exploitable
4. Exploitative Adjustments
Identifies opponent tendencies (e.g., over-folding, over-calling)
Deviates from equilibrium strategy to maximize expected value

**Tech Stack** 
1. Language: Python
2. Libraries: NumPy
3. Base Framework: IEEE AI Poker repo (modified)

**How It Works -**
Cards are dealt and game state is initialized
Bot estimates equity using Monte Carlo simulation
Opponent range is updated based on actions
Strategy module decides action between Fold, Call or Raise.
Process repeats for each betting round

**Example Logic Flow**
Preflop: Assign initial opponent range
Flop: Narrow range based on betting
Turn/River: Recalculate equity with updated ranges
Final Decision: Based on EV (Expected Value)

**Key Highlights -**
Uses probabilistic simulation instead of static rules.
Makes decisions based on ranges, not single hands.
Combines GTO principles with exploitative play.
Modular and extensible design.
