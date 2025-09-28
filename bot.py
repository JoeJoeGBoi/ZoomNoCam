"""Automation bot for enforcing Zoom participant camera usage."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np
import pyautogui
import pytesseract

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Path to your icons (from the pack provided with the project)
ICON_CAMERA_OFF = "cam_off_dark.png"
ICON_CAMERA_OFF_LIGHT = "cam_off_light.png"
ICON_MULTI_PIN = "multi_pin.png"
ICON_CO_HOST = "co_host.png"

WARNING_SECONDS = 30
CHECK_INTERVAL = 3
MENU_TYPING_DELAY = 0.25

# Dictionary to store timers for each guest (keyed by a stable identifier)
guest_timers: Dict[str, float] = {}

# Configure logging so that the script can be debugged from the terminal.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


@dataclass(frozen=True)
class Guest:
    """Represents a Zoom guest entry on the participants panel."""

    name: str
    position: Tuple[int, int]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def locate_icon(image_path: str, confidence: float = 0.8) -> Optional[pyautogui.Box]:
    """Locate a single icon on screen using :mod:`pyautogui`.

    ``pyautogui.locateOnScreen`` occasionally throws exceptions if the screen
    capture fails. We catch them here so the main loop does not crash.
    """

    try:
        return pyautogui.locateOnScreen(image_path, confidence=confidence)
    except Exception:  # pragma: no cover - defensive guard for GUI failures
        logging.debug("Failed to locate icon %s", image_path)
        return None


def locate_all_icons(image_path: str, confidence: float = 0.8) -> List[pyautogui.Box]:
    """Locate all instances of an icon on screen."""

    try:
        return list(pyautogui.locateAllOnScreen(image_path, confidence=confidence))
    except Exception:  # pragma: no cover - defensive guard for GUI failures
        logging.debug("Failed to locate icons %s", image_path)
        return []


def click_icon(image_path: str, confidence: float = 0.8) -> bool:
    """Click an icon if it is visible on screen."""

    location = locate_icon(image_path, confidence)
    if location:
        pyautogui.click(pyautogui.center(location))
        return True
    return False


def normalize_name(image: np.ndarray) -> str:
    """Extract the participant name from a screenshot of the entry."""

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(thresh)
    return text.strip() or "Unknown"


# ---------------------------------------------------------------------------
# Actions on participants
# ---------------------------------------------------------------------------

def right_click_menu_action(position: Tuple[int, int], search_text: str) -> None:
    """Open the context menu for a participant and trigger an action.

    The function uses the type-to-search behaviour of Zoom menus to focus the
    requested entry before pressing Enter.
    """

    pyautogui.rightClick(position)
    time.sleep(MENU_TYPING_DELAY)
    pyautogui.typewrite(search_text)
    time.sleep(MENU_TYPING_DELAY)
    pyautogui.press("enter")


def ask_to_start_video(position: Tuple[int, int]) -> None:
    """Ask the guest to start their video via the context menu."""

    logging.info("Issuing video start request at %s", position)
    right_click_menu_action(position, "Ask to Start Video")


def remove_guest(position: Tuple[int, int]) -> None:
    """Remove a guest from the meeting via the context menu."""

    logging.info("Removing guest at %s", position)
    right_click_menu_action(position, "Remove")
    # Zoom shows a confirmation dialog. We give it a moment and confirm.
    time.sleep(MENU_TYPING_DELAY)
    pyautogui.press("enter")


def remove_pin(position: Tuple[int, int]) -> None:
    """Remove multi-pin for a guest via the context menu."""

    logging.info("Removing multi-pin at %s", position)
    right_click_menu_action(position, "Remove Pin")


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def capture_region(box: pyautogui.Box) -> np.ndarray:
    """Capture a screenshot of the given region."""

    screenshot = pyautogui.screenshot(region=box)
    return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)


def guest_identifier(position: Tuple[int, int]) -> str:
    """Create a stable identifier for a guest based on screen position."""

    return f"{position[0]}x{position[1]}"


def guests_with_camera_off() -> Iterable[Guest]:
    """Yield guests that currently display the "camera off" icon."""

    icons = []
    for icon_path in (ICON_CAMERA_OFF, ICON_CAMERA_OFF_LIGHT):
        icons.extend(locate_all_icons(icon_path))

    for icon_box in icons:
        # Assume the participant entry stretches to the left of the icon.
        name_region = pyautogui.Box(
            icon_box.left - int(icon_box.width * 6),
            icon_box.top,
            int(icon_box.width * 5.5),
            icon_box.height,
        )
        screenshot = capture_region(name_region)
        name = normalize_name(screenshot)
        center = pyautogui.center(icon_box)
        yield Guest(name=name, position=(center.x, center.y))


def guests_with_multi_pin() -> Iterable[Tuple[int, int]]:
    """Return positions for guests who are multi-pinned."""

    for box in locate_all_icons(ICON_MULTI_PIN, confidence=0.85):
        center = pyautogui.center(box)
        yield (center.x, center.y)


def is_co_host(position: Tuple[int, int]) -> bool:
    """Heuristic check to skip co-hosts based on the co-host icon."""

    co_host_box = locate_icon(ICON_CO_HOST, confidence=0.85)
    if not co_host_box:
        return False
    center = pyautogui.center(co_host_box)
    return abs(center.x - position[0]) < 10 and abs(center.y - position[1]) < 10


# ---------------------------------------------------------------------------
# Core loop
# ---------------------------------------------------------------------------

def enforce_camera_rules(now: float) -> None:
    """Issue warnings or kick guests based on camera status."""

    active_guests = {}
    for guest in guests_with_camera_off():
        if is_co_host(guest.position):
            logging.debug("Skipping co-host %s", guest.name)
            continue

        identifier = guest_identifier(guest.position)
        active_guests[identifier] = guest

        if identifier not in guest_timers:
            logging.info("Camera off detected for %s", guest.name)
            guest_timers[identifier] = now
            ask_to_start_video(guest.position)
            continue

        elapsed = now - guest_timers[identifier]
        if elapsed >= WARNING_SECONDS:
            logging.info(
                "Guest %s still has camera off after %.0fs; removing.",
                guest.name,
                elapsed,
            )
            remove_guest(guest.position)
            guest_timers.pop(identifier, None)

    # Remove timers for guests no longer detected
    for identifier in list(guest_timers):
        if identifier not in active_guests:
            logging.debug("Guest %s resolved camera issue", identifier)
            guest_timers.pop(identifier, None)


def enforce_multi_pin_rules() -> None:
    """Remove multi-pin settings for guests."""

    for position in guests_with_multi_pin():
        logging.info("Multi-pin detected at %s", position)
        remove_pin(position)


def keep_last_page_active() -> None:
    """Scroll the participants panel to keep the last page visible."""

    pyautogui.press("end")


def main_loop() -> None:
    """Run the automation loop indefinitely."""

    logging.info("Starting Zoom automation bot.")
    while True:
        start = time.time()
        keep_last_page_active()
        enforce_camera_rules(start)
        enforce_multi_pin_rules()
        duration = time.time() - start
        sleep_for = max(0.0, CHECK_INTERVAL - duration)
        if sleep_for:
            time.sleep(sleep_for)


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logging.info("Zoom automation bot stopped at %s", datetime.now())
