#!/usr/bin/env python3
"""Demo script that shows and executes code examples from the README."""

import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from screenium import Text


def clear_terminal():
    """Clear terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def print_action(text: str):
    """Print action and ensure it's displayed immediately."""
    print(f">>> {text}")
    sys.stdout.flush()  # Force immediate display
    time.sleep(0.1)  # Small delay to ensure print is visible


def demo_basic_matching():
    """Show example of text matching with boxes."""
    clear_terminal()
    print("\n=== Basic Text Finding ===")

    print_action("from screenium import Text")
    from screenium import Text

    time.sleep(0.5)

    print_action("# Find text on screen")
    print_action('Text("Left").draw()')
    Text("Left").draw()


def demo_fun_interaction():
    """Show a fun, rapid clockwise mouse movement."""
    clear_terminal()
    print("\n=== Mouse Movement Demo ===")

    print_action("# Watch this spin!")

    # Define the clockwise movement pattern
    movements = [
        ("Top", "blue"),
        ("TR", "green"),
        ("Right", "yellow"),
        ("BR", "purple"),
        ("Bottom", "red"),
        ("BL", "cyan", True),  # True indicates needs aligned.left_of("Bottom")
        ("Left", "magenta"),
        ("TL", "orange"),
    ]

    for element, color, *aligned in movements:
        if aligned and aligned[0]:
            # Handle BL special case
            cmd = f'Text("{element}").aligned.left_of("Bottom")'
        else:
            cmd = f'Text("{element}")'

        # Move mouse
        print_action(f"{cmd}.mouse_move()")
        eval(f"{cmd}.mouse_move()")

        # Draw highlight
        print_action(f'{cmd}.draw(color="{color}")')
        eval(f'{cmd}.draw(color="{color}")')
        print("\n")

    time.sleep(1)
    Text("").typewrite("Your screen is my playground - let's have some fun!")


def main():
    """Run all demos in sequence."""
    time.sleep(1)

    demos = [
        demo_basic_matching,
        demo_fun_interaction,
    ]

    for demo in demos:
        demo()
        time.sleep(1)


if __name__ == "__main__":
    main()
