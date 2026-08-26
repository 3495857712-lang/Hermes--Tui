"""Example: Creating a custom tool for Hermes TUI.

This module demonstrates how to create and register a custom tool
that the AI agent can call.

Usage:
    1. Import this module before launching the app (or add it to your
       startup script).
    2. The @tool decorator registers it on the global registry.
    3. The AI can then call it during conversation.
"""

from __future__ import annotations

import random

from hermes_tui.tools import tool


@tool
def roll_dice(sides: int = 6, count: int = 1) -> str:
    """Roll one or more dice.

    Args:
        sides: Number of sides per die (default 6).
        count: Number of dice to roll (default 1).
    """
    if sides < 2:
        return "Error: Dice must have at least 2 sides."
    if count < 1 or count > 100:
        return "Error: Count must be between 1 and 100."

    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls)

    if count == 1:
        return f"🎲 Rolled a d{sides}: **{rolls[0]}**"
    return f"🎲 Rolled {count}d{sides}: {rolls} = **{total}**"


@tool
def word_count(text: str) -> str:
    """Count words, characters, and lines in the given text.

    Args:
        text: The text to analyze.
    """
    words = len(text.split())
    chars = len(text)
    lines = text.count("\n") + 1
    return f"Words: {words}\nCharacters: {chars}\nLines: {lines}"


@tool(requires_confirmation=True)
def create_calculator_note(expression: str, result: str) -> str:
    """Save a calculation result to a notes file.

    This is a demonstration of a tool that requires confirmation.

    Args:
        expression: The math expression that was evaluated.
        result: The result of the calculation.
    """
    from pathlib import Path

    notes_path = Path.home() / ".hermes-tui" / "calculations.txt"
    notes_path.parent.mkdir(parents=True, exist_ok=True)

    with open(notes_path, "a", encoding="utf-8") as f:
        f.write(f"{expression} = {result}\n")

    return f"Saved to {notes_path}"


# If run directly, test the tools
if __name__ == "__main__":
    print(roll_dice(sides=20, count=2))
    print()
    print(word_count("Hello world. This is a test."))
