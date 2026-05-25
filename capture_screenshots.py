"""
capture_screenshots.py — headless screenshot capture for each TUI screen.
Run: python3 capture_screenshots.py
Outputs SVGs to ./screenshots/ then converts to PNG via qlmanage.
"""

import asyncio
import os
import subprocess
import sys

SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

SCREENS = [
    ("01_dashboard",  []),
    ("02_habits",     ["1"]),
    ("03_tasks",      ["1", "q", "2"]),
    ("04_notes",      ["1", "q", "2", "q", "3"]),
    ("05_portfolio",  ["1", "q", "2", "q", "3", "q", "5"]),
    ("06_music",      ["1", "q", "2", "q", "3", "q", "5", "q", "6"]),
    ("07_game",       ["1", "q", "2", "q", "3", "q", "5", "q", "6", "q", "4"]),
]


async def capture() -> None:
    from tui import DarkHourApp

    app = DarkHourApp()
    async with app.run_test(size=(200, 50)) as pilot:
        # Wait for mount + initial data load
        await pilot.pause(1.5)
        app.save_screenshot(filename="01_dashboard.svg", path=SCREENSHOTS_DIR)
        print("  ✓  01_dashboard")

        await pilot.press("1")
        await pilot.pause(0.8)
        app.save_screenshot(filename="02_habits.svg", path=SCREENSHOTS_DIR)
        print("  ✓  02_habits")

        await pilot.press("q")
        await pilot.pause(0.4)
        await pilot.press("2")
        await pilot.pause(0.8)
        app.save_screenshot(filename="03_tasks.svg", path=SCREENSHOTS_DIR)
        print("  ✓  03_tasks")

        await pilot.press("q")
        await pilot.pause(0.4)
        await pilot.press("3")
        await pilot.pause(0.8)
        app.save_screenshot(filename="04_notes.svg", path=SCREENSHOTS_DIR)
        print("  ✓  04_notes")

        await pilot.press("q")
        await pilot.pause(0.4)
        await pilot.press("5")
        await pilot.pause(2.0)  # portfolio does a threaded fetch
        app.save_screenshot(filename="05_portfolio.svg", path=SCREENSHOTS_DIR)
        print("  ✓  05_portfolio")

        await pilot.press("q")
        await pilot.pause(0.4)
        await pilot.press("6")
        await pilot.pause(0.8)
        app.save_screenshot(filename="06_music.svg", path=SCREENSHOTS_DIR)
        print("  ✓  06_music")

        await pilot.press("q")
        await pilot.pause(0.4)
        await pilot.press("4")
        await pilot.pause(0.8)
        app.save_screenshot(filename="07_game.svg", path=SCREENSHOTS_DIR)
        print("  ✓  07_game")


def convert_to_png() -> None:
    """Convert SVGs to PNG thumbnails via macOS Quick Look."""
    svgs = sorted(
        os.path.join(SCREENSHOTS_DIR, f)
        for f in os.listdir(SCREENSHOTS_DIR)
        if f.endswith(".svg")
    )
    if not svgs:
        return
    result = subprocess.run(
        ["qlmanage", "-t", "-s", "1600", "-o", SCREENSHOTS_DIR] + svgs,
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"  qlmanage warning: {result.stderr.decode().strip()}")


if __name__ == "__main__":
    print("Capturing screenshots…")
    asyncio.run(capture())
    print("\nConverting SVG → PNG…")
    convert_to_png()
    print(f"\nDone. Files saved to:\n  {SCREENSHOTS_DIR}")
    subprocess.run(["open", SCREENSHOTS_DIR])
