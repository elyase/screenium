#!/usr/bin/env python3
"""Screen OCR and text interaction tool using Apple's VisionKit framework."""

import io
import logging
import platform
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import objc
import pynput.keyboard
import pynput.mouse
import Vision
from AppKit import NSEvent, NSScreen, NSWorkspace
from colour import Color
from mss import mss
from mss.tools import to_png
from PIL import Image
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGNullWindowID,
    kCGWindowListOptionOnScreenOnly,
)

from screenium.draw import ShapeDrawer, parse_color

logger = logging.getLogger(__name__)


# Check for macOS Monterey or higher
def _get_macos_version() -> str:
    """Get the macOS version number."""
    return platform.mac_ver()[0]


def _check_monterey_compatibility():
    """Check if running on macOS Monterey or higher."""
    macos_version = _get_macos_version()
    major_version = int(macos_version.split(".")[0])
    if major_version < 12:
        raise RuntimeError(
            f"Screen Locator requires macOS Monterey (12.x) or higher but found version {macos_version}. "
            "This module uses VisionKit framework features that are only available in Monterey and later versions."
        )


_check_monterey_compatibility()


# OCR Module
class TextRecognizer:
    """Handles OCR using Apple's Vision framework."""

    def __init__(self):
        """Initialize the text recognizer."""
        # Create reusable Vision objects
        self.request = Vision.VNRecognizeTextRequest.alloc().init()

    def image_to_text(
        self, image_data: bytes, recognition_level: str = "fast"
    ) -> List[Dict[str, Union[str, float]]]:
        """Convert image data to text using Vision framework OCR."""
        with objc.autorelease_pool():
            # Set recognition level
            level = 1 if recognition_level == "fast" else 0
            self.request.setRecognitionLevel_(level)

            # Create image handler directly from bytes
            handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(
                image_data, None
            )

            # Perform recognition
            handler.performRequests_error_([self.request], None)

            # Extract results
            results = []
            if self.request.results():
                for observation in self.request.results():
                    bbox = observation.boundingBox()
                    results.append(
                        {
                            "text": observation.text(),
                            "confidence": observation.confidence(),
                            "x": bbox.origin.x,
                            "y": bbox.origin.y,
                            "width": bbox.size.width,
                            "height": bbox.size.height,
                        }
                    )

            return results


# Screen Capture Module
class ScreenCapture:
    """Handles screen capture functionality."""

    def __init__(self):
        """Initialize screen capture."""
        self.sct = mss()

    def get_current_monitor(self) -> Dict[str, int]:
        """Get the geometry of the current monitor (where the mouse cursor is).

        Returns:
            Dictionary containing monitor geometry:
            - left: X coordinate of the left edge
            - top: Y coordinate of the top edge
            - width: Width of the monitor
            - height: Height of the monitor
        """
        # Get all real monitors (skip index 0 which is the "all monitors" dummy)
        monitors = self.sct.monitors[1:]

        # Get current mouse position
        mouse_pos = NSEvent.mouseLocation()
        mouse_x = int(mouse_pos.x)
        mouse_y = int(NSScreen.mainScreen().frame().size.height - mouse_pos.y)

        # Find the monitor containing the mouse cursor
        current_monitor = None
        for monitor in monitors:
            if (
                monitor["left"] <= mouse_x <= monitor["left"] + monitor["width"]
                and monitor["top"] <= mouse_y <= monitor["top"] + monitor["height"]
            ):
                current_monitor = monitor
                break

        # If no monitor found, use the primary monitor
        if not current_monitor:
            current_monitor = monitors[0]

        return {
            "left": current_monitor["left"],
            "top": current_monitor["top"],
            "width": current_monitor["width"],
            "height": current_monitor["height"],
        }

    def capture_region(self, top: int, left: int, width: int, height: int) -> bytes:
        """Capture a specific region of the screen and return as PNG bytes."""
        monitor = {"top": top, "left": left, "width": width, "height": height}
        screenshot = self.sct.grab(monitor)
        return to_png(screenshot.rgb, screenshot.size)

    def capture_screen(self) -> bytes:
        """Capture the current monitor and return as PNG bytes."""
        monitor = self.get_current_monitor()
        screenshot = self.sct.grab(monitor)
        return to_png(screenshot.rgb, screenshot.size)


# Mouse Control Module
class MouseController:
    """Mouse controller using pynput."""

    def __init__(self):
        """Initialize the mouse controller."""
        self.mouse = pynput.mouse.Controller()
        self.keyboard = pynput.keyboard.Controller()

    def moveTo(self, x: int, y: int, **kwargs):
        """Move mouse to absolute coordinates."""
        self.mouse.position = (x, y)

    def click(self, x: int = None, y: int = None, **kwargs):
        """Click at the specified position."""
        # Always move to position first if coordinates are provided
        if x is not None and y is not None:
            self.moveTo(x, y)
            time.sleep(0.1)  # Small delay to ensure mouse has moved
        self.mouse.click(pynput.mouse.Button.left)

    def rightClick(self, x: int = None, y: int = None, **kwargs):
        """Right click at the specified position."""
        # Always move to position first if coordinates are provided
        if x is not None and y is not None:
            self.moveTo(x, y)
            time.sleep(0.1)  # Small delay to ensure mouse has moved
        self.mouse.click(pynput.mouse.Button.right)

    def doubleClick(self, x: int = None, y: int = None, **kwargs):
        """Double click at the specified position."""
        # Always move to position first if coordinates are provided
        if x is not None and y is not None:
            self.moveTo(x, y)
            time.sleep(0.1)  # Small delay to ensure mouse has moved
        self.mouse.click(pynput.mouse.Button.left, 2)

    def typewrite(self, text: Union[str, List[str]], interval: float = 0.0):
        """Type text using keyboard."""
        if isinstance(text, str):
            self.keyboard.type(text)
        else:
            # Handle special keys
            for key in text:
                try:
                    special_key = getattr(pynput.keyboard.Key, key.lower())
                    self.keyboard.press(special_key)
                    self.keyboard.release(special_key)
                except AttributeError:
                    # If not a special key, type it as a regular character
                    self.keyboard.type(key)
                if interval > 0:
                    time.sleep(interval)

    def hotkey(self, *keys: str):
        """Press a keyboard hotkey combination."""
        key_objects = []
        for key in keys:
            try:
                key_objects.append(getattr(pynput.keyboard.Key, key.lower()))
            except AttributeError:
                key_objects.append(key)

        for key in key_objects:
            self.keyboard.press(key)
        for key in reversed(key_objects):
            self.keyboard.release(key)


class LocatorManager:
    """Singleton manager for monitoring locators."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.monitored_locators = {}  # {locator: interval}
        self.last_check_times = {}  # {locator: last_check_time}
        self._monitor_thread = None
        self._stop_event = threading.Event()

    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance."""
        return cls()

    def start_monitoring(self):
        """Start the monitoring loop if not already running."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self):
        """Stop the monitoring loop."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._stop_event.set()
            self._monitor_thread.join()
            self._monitor_thread = None

    def _monitor_loop(self):
        """Check each registered locator at its specified interval."""
        while not self._stop_event.is_set():
            current_time = time.time()

            # Make a copy to avoid modification during iteration
            locators = list(self.monitored_locators.items())

            for locator, interval in locators:
                if current_time - self.last_check_times.get(locator, 0) >= interval:
                    try:
                        # Execute all operations in the chain
                        match = locator._execute_operations()

                        if match:
                            # Process any actions in the chain
                            for op in locator._operations:
                                if op["type"] == "action":
                                    if op["action"] == "click":
                                        x, y = locator._get_middle_point(match)
                                        locator._finder.mouse.click(
                                            x=x, y=y, duration=op["duration"]
                                        )
                                        logger.info(f"Clicked at ({x}, {y})")
                                    elif op["action"] == "mouse_move":
                                        x, y = locator._get_middle_point(match)
                                        locator._finder.mouse.moveTo(x=x, y=y)
                                        logger.info(f"Moved mouse to ({x}, {y})")
                                    elif op["action"] == "typewrite":
                                        locator._finder.mouse.typewrite(
                                            op["text"], interval=op.get("interval", 0.0)
                                        )
                                        logger.info(f"Typewrote '{op['text']}'")
                                    elif op["action"] == "hotkey":
                                        locator._finder.mouse.hotkey(*op["keys"])
                                        logger.info(
                                            f"Pressed hotkey {' + '.join(op['keys'])}"
                                        )
                                    elif op["action"] == "wait":
                                        time.sleep(op["seconds"])
                                        logger.info(
                                            f"Waited for {op['seconds']} seconds"
                                        )
                                    elif op["action"] == "draw":
                                        x, y = locator._get_middle_point(match)
                                        locator._finder.mouse.moveTo(x=x, y=y)
                                        logger.info(
                                            f"Drew rectangle around text '{locator.text}'"
                                        )

                        self.last_check_times[locator] = current_time
                    except Exception as e:
                        logger.error(f"Error monitoring locator '{locator.text}': {e}")

            # Sleep a small amount to prevent high CPU usage
            time.sleep(0.1)


class Text:
    """Represents a chainable locator for finding and interacting with text on screen."""

    def __init__(
        self,
        text: str = None,
        image_path: str = None,
        app_name: Optional[str] = None,
        case_sensitive: bool = False,
        exact_match: bool = False,
        background_color: Optional[
            Union[str, Tuple[float, float, float], Color]
        ] = None,
        background_tolerance: float = 35.0,  # Default tolerance for basic colors
        recognition_level: str = "fast",
        finder: Optional["TextFinder"] = None,
        operations: Optional[List[Dict]] = None,
    ):
        """
        Initialize a text locator.

        Args:
            text: Text to search for
            image_path: Path to an image file to search in. If None, will capture screen.
            app_name: Restrict search to this application's windows
            case_sensitive: Whether to perform case-sensitive search
            exact_match: Whether to require exact text match (no substrings)
            background_color: Color to match against the text background. Can be:
                - Color name (e.g., 'red', 'blue', 'green')
                - Hex code (e.g., '#ff0000', '#0088ff')
                - RGB tuple (e.g., (1, 0, 0))
                - Color object
            background_tolerance: How much the color can differ (0-100):
                - 0: Exact match only
                - 35: Best for basic colors (default)
                - 50: Very different colors
            recognition_level: OCR recognition level ("fast" or "accurate")
            finder: Optional TextFinder instance to reuse OCR results
            operations: List of operations to perform (for internal use in chaining)
        """
        self.text = text
        self.image_path = image_path
        self.case_sensitive = case_sensitive
        self.exact_match = exact_match
        self.background_color = (
            parse_color(background_color) if background_color else None
        )
        self.background_tolerance = background_tolerance
        self._finder = (
            finder
            if finder
            else TextFinder(
                app_name=app_name,
                image_path=image_path,
                recognition_level=recognition_level,
            )
        )
        if finder is None:
            # Only run OCR if this is a new TextFinder instance
            self._finder.run_ocr()
        self._matches = None
        self._operations = operations or []  # List of operations to perform

    def _clone_with_operation(self, operation: Dict) -> "Text":
        """Create a new Text instance with an additional operation."""
        new_operations = self._operations.copy()

        # If this is a spatial operation, convert the target to text if needed
        if operation.get("type") == "spatial" and "target" in operation:
            other = operation["target"]
            operation["target"] = other if isinstance(other, str) else other.text

        new_operations.append(operation)
        return Text(
            self.text,
            finder=self._finder,
            operations=new_operations,
            case_sensitive=self.case_sensitive,
            exact_match=self.exact_match,
            background_color=self.background_color,
            background_tolerance=self.background_tolerance,
        )

    def left_of(self, other: Union[str, "Text"]) -> "Text":
        """Find this element left of another element."""
        return self._clone_with_operation(
            {"type": "spatial", "relation": "left_of", "target": other}
        )

    def right_of(self, other: Union[str, "Text"]) -> "Text":
        """Find this element right of another element."""
        return self._clone_with_operation(
            {"type": "spatial", "relation": "right_of", "target": other}
        )

    def above(self, other: Union[str, "Text"]) -> "Text":
        """Find this element above another element."""
        return self._clone_with_operation(
            {"type": "spatial", "relation": "above", "target": other}
        )

    def below(self, other: Union[str, "Text"]) -> "Text":
        """Find this element below another element."""
        return self._clone_with_operation(
            {"type": "spatial", "relation": "below", "target": other}
        )

    @property
    def aligned(self) -> "Text":
        """Indicate that the next spatial operation should require alignment."""
        return self._clone_with_operation({"type": "aligned"})

    def _add_action(self, action: str, **kwargs) -> "Text":
        """Add an action to the operation chain and execute if not in background mode."""
        # Add operation to chain
        operation = {"type": "action", "action": action, **kwargs}
        result = self._clone_with_operation(operation)

        # If not in background mode, execute immediately
        if not any(op["type"] == "background" for op in result._operations):
            # Handle non-mouse actions separately
            if action == "wait":
                time.sleep(kwargs["seconds"])
                return result
            elif action == "typewrite":
                self._finder.mouse.typewrite(
                    kwargs["text"], interval=kwargs.get("interval", 0.0)
                )
                return result

            # For mouse actions, we need coordinates
            match = result._execute_operations()
            if match:
                x, y = self._get_middle_point(match)
                if action == "mouse_move":
                    self._finder.mouse.moveTo(x=x, y=y)
                elif action == "double_click":
                    # Move to position first
                    self._finder.mouse.moveTo(x=x, y=y)
                    # Use pynput for double click
                    pynput.mouse.Controller().click(
                        button=pynput.mouse.Button.left, count=2
                    )
                else:
                    # For other click actions
                    getattr(self._finder.mouse, action)(x=x, y=y, **kwargs)

        return result

    def mouse_move(self) -> "Text":
        """Move the mouse to the matched text location."""
        return self._add_action("moveTo")

    def click(self, duration: float = 0.5) -> "Text":
        """Click on the matched text location."""
        return self._add_action("click", duration=duration)

    def right_click(self, duration: float = 0.5) -> "Text":
        """Right click on the matched text location."""
        return self._add_action("rightClick", duration=duration)

    def double_click(self, duration: float = 0.5) -> "Text":
        """Double click on the matched text location."""
        return self._add_action("doubleClick", duration=duration)

    def draw(
        self,
        duration: int = 0.5,
        color: str = "green",
        line_width: float = 5.0,
        padding: int = 5,
    ) -> "Text":
        """Draw rectangles around all matches.

        Args:
            duration: How long the shapes should stay on screen (in seconds)
            color: Color of the rectangles (name, hex code, or RGB tuple)
            line_width: Width of the rectangle's outline (default: 5.0)
            padding: Extra space around the text in pixels (default: 5)

        Returns:
            self for method chaining
        """
        # Add operation to chain
        result = self._clone_with_operation(
            {
                "type": "action",
                "action": "draw",
                "duration": duration,
                "color": color,
                "line_width": line_width,
                "padding": padding,
            }
        )

        # If not in background mode, execute immediately
        if not any(op["type"] == "background" for op in result._operations):
            match = result._execute_operations()
            if match:
                drawer = ShapeDrawer(duration=duration)
                drawer.add_rectangle(
                    x=match["x"] - padding,
                    y=match["y"] - padding,
                    width=match["width"] + (padding * 2),
                    height=match["height"] + (padding * 2),
                    color=color,
                    line_width=line_width,
                )
                drawer.show()

        return result

    def typewrite(self, text: Union[str, List[str]], interval: float = 0.1) -> "Text":
        """Type text at the current cursor position.

        Args:
            text: String to type or list of key names (e.g. ['a', 'b', 'enter', 'f1'])
            interval: Seconds between each key. If 0, typing is at maximum speed.

        Returns:
            self for method chaining
        """
        return self._add_action("typewrite", text=text, interval=interval)

    def hotkey(self, *keys: str) -> "Text":
        """Press a keyboard hotkey combination (e.g. ctrl+c, ctrl+v).

        Args:
            *keys: Variable number of key names (e.g. 'ctrl', 'c' for Ctrl+C)

        Returns:
            self for method chaining
        """
        return self._add_action("hotkey", keys=keys)

    def wait(self, seconds: float) -> "Text":
        """Wait for the specified number of seconds before continuing the chain.

        Args:
            seconds: Number of seconds to wait

        Returns:
            self for method chaining
        """
        return self._add_action("wait", seconds=seconds)

    def background(self, every: float = 1.0) -> "Text":
        """
        Monitor text presence using the LocatorManager.

        Args:
            every: Time interval in seconds between checks

        Returns:
            self for method chaining
        """
        result = self._clone_with_operation({"type": "background", "interval": every})

        manager = LocatorManager.get_instance()
        manager.monitored_locators[result] = every
        manager.last_check_times[result] = 0  # Force immediate first check
        manager.start_monitoring()
        return result

    def stop_background(self) -> "Text":
        """
        Stop background monitoring if active.

        Returns:
            self for method chaining
        """
        manager = LocatorManager.get_instance()
        if self in manager.monitored_locators:
            del manager.monitored_locators[self]
            if self in manager.last_check_times:
                del manager.last_check_times[self]
        return self

    def _execute_operations(self) -> Optional[Dict]:
        """Execute all operations in the chain and return the final match."""
        try:
            # Find all matches for the initial text
            current_matches = self._find_matches()

            if not current_matches:
                return None

            # Process each operation in sequence
            for i, op in enumerate(self._operations):
                if op["type"] == "spatial":
                    # Check if previous operation was 'aligned'
                    require_alignment = (
                        i > 0 and self._operations[i - 1]["type"] == "aligned"
                    )
                    relation = op["relation"]

                    # Find matches for the target text
                    target = op["target"]
                    if isinstance(target, Text):
                        target_matches = target._find_matches()
                    else:
                        target_matches = self._finder.find_text(target)

                    if not target_matches:
                        return None

                    # Apply spatial relationship check
                    new_matches = []
                    for match in current_matches:
                        for target_match in target_matches:
                            passes_spatial = False

                            # Check spatial relationship first
                            match relation:
                                case "above":
                                    passes_spatial = (
                                        match["y"] + match["height"]
                                        <= target_match["y"]
                                    )
                                case "below":
                                    passes_spatial = (
                                        match["y"]
                                        >= target_match["y"] + target_match["height"]
                                    )
                                case "left_of":
                                    passes_spatial = (
                                        match["x"] + match["width"] <= target_match["x"]
                                    )
                                case "right_of":
                                    passes_spatial = (
                                        match["x"]
                                        >= target_match["x"] + target_match["width"]
                                    )
                                case _:
                                    passes_spatial = False

                            # If spatial check passes and alignment is required, check alignment
                            if passes_spatial:
                                if require_alignment:
                                    # For vertical operations (above/below), check horizontal alignment
                                    # For horizontal operations (left/right), check vertical alignment
                                    if relation in ["above", "below"]:
                                        passes_alignment = self._has_horizontal_overlap(
                                            match, target_match
                                        )
                                    else:
                                        passes_alignment = self._has_vertical_overlap(
                                            match, target_match
                                        )

                                    if passes_alignment:
                                        new_matches.append(match)
                                else:
                                    new_matches.append(match)

                    # Update current matches for next operation
                    current_matches = new_matches

            # Return the first match that satisfies all operations
            return current_matches[0] if current_matches else None

        except Exception as e:
            logger.error(f"Error executing operations: {str(e)}")
            return None

    def _find_matches(self) -> List[Dict[str, Any]]:
        """Find all matches for this text on screen."""
        matches = self._finder.extract_matches(
            self.text, case_sensitive=self.case_sensitive, exact_match=self.exact_match
        )

        # If background color matching is enabled, filter matches by color
        if self.background_color is not None and matches:
            matches = self._filter_by_background_color(matches)

        return matches

    def _filter_by_background_color(
        self, matches: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter matches based on background color.

        Uses color range analysis to find similar colors in the region and group them
        together for more robust background color detection. Color distances are normalized
        to a 0-100 scale where 0 is an exact match and 100 is the maximum possible difference.
        """
        filtered_matches = []

        # Get the image data
        if self.image_path:
            with Image.open(self.image_path) as img:
                image = img.convert("RGB")
        else:
            # Convert the screenshot bytes to PIL Image
            image_bytes = self._finder.screen.capture_screen()
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Convert Color object to RGB values (0-255 range)
        target_color = np.array([int(c * 255) for c in self.background_color.rgb])

        # Maximum possible RGB distance is sqrt(255²+255²+255²)
        MAX_RGB_DISTANCE = np.sqrt(3 * 255 * 255)

        for match in matches:
            # Extract the region of the match
            x, y = int(match["x"]), int(match["y"])
            width, height = int(match["width"]), int(match["height"])
            region = image.crop((x, y, x + width, y + height))

            # Convert to numpy array and reshape to 2D array of pixels
            pixels = np.array(region)
            pixels_2d = pixels.reshape(-1, 3)

            # Calculate color distances in a vectorized way
            color_distances = np.sqrt(np.sum((pixels_2d - target_color) ** 2, axis=1))
            normalized_distances = (color_distances / MAX_RGB_DISTANCE) * 100

            # Create mask for similar colors
            similar_colors_mask = normalized_distances <= self.background_tolerance
            similar_pixels = pixels_2d[similar_colors_mask]

            if len(similar_pixels) > 0:
                # Calculate average color of similar pixels
                avg_color = np.mean(similar_pixels, axis=0)
                color_frequency = len(similar_pixels) / len(pixels_2d)

                # Calculate final color distance using the average color
                avg_distance = np.sqrt(np.sum((avg_color - target_color) ** 2))
                normalized_distance = (avg_distance / MAX_RGB_DISTANCE) * 100

                # If we have enough similar pixels
                if color_frequency >= 0.15:
                    match["background_color"] = tuple(map(int, avg_color))
                    match["color_distance"] = float(normalized_distance)
                    match["color_frequency"] = float(color_frequency)
                    filtered_matches.append(match)

        return filtered_matches

    @staticmethod
    def _ensure_locator(other: Union[str, "Text"]) -> "Text":
        """Convert string to Text if needed."""
        if isinstance(other, str):
            return Text(other)
        return other

    def _get_match(self) -> Optional[Dict[str, Any]]:
        """Get the best match for this text."""
        if self._matches is None:
            self._matches = self._find_matches()
        return self._matches[0] if self._matches else None

    def _get_middle_point(self, match: Dict[str, Any]) -> Tuple[int, int]:
        """Calculate the middle point of a match."""
        x = match["x"] + match["width"] / 2
        y = match["y"] + match["height"] / 2
        return int(x), int(y)

    def _check_spatial_relationship(
        self,
        a: Dict[str, Any],
        b: Dict[str, Any],
        position_check: bool,
        is_vertical: bool,
    ) -> bool:
        """Check if elements satisfy a spatial relationship with optional alignment.

        Args:
            a: First element
            b: Second element
            position_check: Whether the basic position requirement is met
            is_vertical: Whether to check vertical (True) or horizontal (False) overlap
        """
        if not position_check:
            return False

        if self._is_aligned_operation():
            overlap_check = (
                self._has_vertical_overlap
                if is_vertical
                else self._has_horizontal_overlap
            )
            return position_check and overlap_check(a, b)

        return True

    def _is_left_of(self, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        """Check if element a is left of element b."""
        is_left = (a["x"] + a["width"]) <= b["x"]  # Non-strict to allow touching
        return self._check_spatial_relationship(a, b, is_left, True)

    def _is_right_of(self, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        """Check if element a is right of element b."""
        is_right = a["x"] >= (b["x"] + b["width"])  # Non-strict to allow touching
        return self._check_spatial_relationship(a, b, is_right, True)

    def _is_above(self, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        """Check if element a is above element b."""
        is_above = (a["y"] + a["height"]) <= b["y"]  # Non-strict to allow touching
        return self._check_spatial_relationship(a, b, is_above, False)

    def _is_below(self, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        """Check if element a is below element b."""
        is_below = a["y"] >= (b["y"] + b["height"])  # Non-strict to allow touching
        return self._check_spatial_relationship(a, b, is_below, False)

    def _is_aligned_operation(self) -> bool:
        """Check if the current operation should require alignment."""
        # Look for an 'aligned' operation that comes immediately before
        # the current spatial operation
        for i, op in enumerate(self._operations):
            if op["type"] == "spatial":
                # Check if the previous operation was 'aligned'
                if i > 0 and self._operations[i - 1]["type"] == "aligned":
                    return True
                return False
        return False

    def _has_vertical_overlap(self, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        """Check if two elements have vertical overlap."""
        # Note: y-coordinates are from top-down, so larger y means lower on screen
        y1_top = a["y"]
        y1_bottom = a["y"] + a["height"]
        y2_top = b["y"]
        y2_bottom = b["y"] + b["height"]

        # Calculate actual overlap amount
        overlap_top = max(y1_top, y2_top)
        overlap_bottom = min(y1_bottom, y2_bottom)
        overlap_amount = overlap_bottom - overlap_top

        # Require at least 1 pixel of overlap for alignment
        return overlap_amount >= 1

    def _has_horizontal_overlap(self, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        """Check if two elements have horizontal overlap."""
        box1_left = a["x"]
        box1_right = a["x"] + a["width"]
        box2_left = b["x"]
        box2_right = b["x"] + b["width"]

        return not (box1_right <= box2_left or box1_left >= box2_right)

    def __bool__(self) -> bool:
        """Return True if text is found on screen with all operations in chain."""
        match = self._execute_operations()
        return bool(match)

    def __str__(self) -> str:
        """Return string representation of the text locator."""
        match = self._get_match()
        text_repr = "''" if self.text is None else f"'{self.text}'"
        if match:
            return f"<Text text={text_repr} x={match['x']} y={match['y']} width={match['width']} height={match['height']}>"
        return f"<Text text={text_repr} not found>"

    def __repr__(self) -> str:
        """Return detailed string representation of the text locator."""
        base = f'Text("{self.text}")'

        # Add relationship chain if any
        if hasattr(self, "_relationship_chain"):
            base += "".join(self._relationship_chain)

        # Add location if found
        match = self._get_match()
        if match:
            x, y = self._get_middle_point(match)
            return f"{base} @ ({x}, {y}) [{match['width']}x{match['height']}]"

        return f"{base} [not found]"

    @property
    def matches(self) -> List[Dict[str, Any]]:
        """Return all matches at the current point in the execution chain."""
        try:
            # Find all matches for the initial text
            current_matches = self._find_matches()

            if not current_matches:
                return []

            # Process each operation in sequence
            for i, op in enumerate(self._operations):
                if op["type"] == "spatial":
                    # Check if previous operation was 'aligned'
                    require_alignment = (
                        i > 0 and self._operations[i - 1]["type"] == "aligned"
                    )
                    relation = op["relation"]

                    # Find matches for the target text
                    target = op["target"]
                    if isinstance(target, Text):
                        target_matches = target._find_matches()
                    else:
                        target_matches = self._finder.find_text(target)

                    if not target_matches:
                        return []

                    # Apply spatial relationship check
                    new_matches = []
                    for match in current_matches:
                        for target_match in target_matches:
                            passes_spatial = False

                            # Check spatial relationship first
                            if (
                                relation == "above"
                                and match["y"] + match["height"] <= target_match["y"]
                            ):
                                passes_spatial = True
                            elif (
                                relation == "below"
                                and match["y"]
                                >= target_match["y"] + target_match["height"]
                            ):
                                passes_spatial = True
                            elif (
                                relation == "left_of"
                                and match["x"] + match["width"] <= target_match["x"]
                            ):
                                passes_spatial = True
                            elif (
                                relation == "right_of"
                                and match["x"]
                                >= target_match["x"] + target_match["width"]
                            ):
                                passes_spatial = True

                            # If spatial check passes and alignment is required, check alignment
                            if passes_spatial:
                                if require_alignment:
                                    # For vertical operations (above/below), check horizontal alignment
                                    # For horizontal operations (left/right), check vertical alignment
                                    if relation in ["above", "below"]:
                                        passes_alignment = self._has_horizontal_overlap(
                                            match, target_match
                                        )
                                    else:
                                        passes_alignment = self._has_vertical_overlap(
                                            match, target_match
                                        )

                                    if passes_alignment:
                                        new_matches.append(match)
                                else:
                                    new_matches.append(match)

                    # Update current matches for next operation
                    current_matches = new_matches

            return current_matches

        except Exception as e:
            logger.error(f"Error getting matches: {str(e)}")
            return []

    @property
    def region(self) -> Dict[str, int]:
        """Get the geometry of the region being used for OCR.

        Returns:
            Dictionary containing:
            - left: X coordinate of the left edge
            - top: Y coordinate of the top edge
            - width: Width of the region
            - height: Height of the region
        """
        return self._finder.screen.get_current_monitor()


@dataclass
class WindowGeometry:
    """Window position and size information."""

    top: float
    left: float
    width: float
    height: float


def get_active_window_geometry() -> Optional[WindowGeometry]:
    """
    Get the geometry of the currently active window.

    Returns:
        WindowGeometry: Window position and size
        None: If no active window is found
    """
    workspace = NSWorkspace.sharedWorkspace()
    curr_pid = workspace.activeApplication()["NSApplicationProcessIdentifier"]

    options = kCGWindowListOptionOnScreenOnly
    window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)

    for window in window_list:
        if curr_pid == window["kCGWindowOwnerPID"]:
            geometry = window["kCGWindowBounds"]
            # Ensure we have positive coordinates for screen capture
            return WindowGeometry(
                top=max(0, geometry["Y"]),  # Ensure non-negative
                left=max(0, geometry["X"]),  # Ensure non-negative
                width=geometry["Width"],
                height=geometry["Height"]
                + (
                    geometry["Y"] if geometry["Y"] < 0 else 0
                ),  # Adjust height if Y was negative
            )

    return None


def get_window_geometry_by_app(app_name: str) -> Optional[WindowGeometry]:
    """
    Get the geometry of a window belonging to the specified app.

    Args:
        app_name: Name of the application to find

    Returns:
        WindowGeometry: Window position and size
        None: If no matching window is found
    """
    options = kCGWindowListOptionOnScreenOnly
    window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)

    for window in window_list:
        owner_name = window.get("kCGWindowOwnerName", "")
        if owner_name.lower() == app_name.lower():
            geometry = window["kCGWindowBounds"]
            # Ensure we have positive coordinates for screen capture
            return WindowGeometry(
                top=max(0, geometry["Y"]),  # Ensure non-negative
                left=max(0, geometry["X"]),  # Ensure non-negative
                width=geometry["Width"],
                height=geometry["Height"]
                + (
                    geometry["Y"] if geometry["Y"] < 0 else 0
                ),  # Adjust height if Y was negative
            )

    return None


class TextFinder:
    """Finds and validates text elements and their relationships."""

    def __init__(
        self,
        app_name: Optional[str] = None,
        image_path: Optional[str] = None,
        recognition_level: str = "fast",
    ):
        """
        Initialize TextFinder.

        Args:
            app_name: Restrict search to windows of this application
            image_path: Path to an image file to search in. If None, will capture screen.
            recognition_level: OCR recognition level ("fast" or "accurate")
        """
        self.app_name = app_name
        self.image_path = image_path
        self.recognition_level = recognition_level
        self.screen = ScreenCapture()
        self.recognizer = TextRecognizer()
        self.mouse = MouseController()
        self.results = None
        self._match_cache = {}  # Cache for text matches
        # Get dimensions based on whether we're using a file or screen capture
        self.width, self.height = self._get_dimensions()

    def _get_dimensions(self) -> tuple[int, int]:
        """
        Get dimensions based on whether we're using a file or screen capture.

        Returns:
            tuple[int, int]: Width and height as integers
        """
        if self.image_path:
            # For image files, use PIL to get dimensions
            from PIL import Image

            with Image.open(self.image_path) as img:
                return img.size
        else:
            # For screen capture, use screen dimensions
            try:
                main_screen = NSScreen.mainScreen()
                frame = main_screen.frame()
                return int(frame.size.width), int(frame.size.height)
            except Exception as e:
                logging.debug(f"Failed to get screen dimensions using NSScreen: {e}")
                return pynput.mouse.Controller().position

    def run_ocr(self):
        """Run OCR on the current screen and update results."""
        self._match_cache.clear()  # Clear the cache

        if self.image_path:
            # Read image from file
            with open(self.image_path, "rb") as f:
                image_data = f.read()
        else:
            # Capture the full screen instead of just the active window
            image_data = self.screen.capture_screen()

        # Get raw OCR results (normalized coordinates)
        raw_results = self.recognizer.image_to_text(
            image_data, recognition_level=self.recognition_level
        )

        # Convert normalized coordinates to screen/image coordinates
        self.results = []
        for result in raw_results:
            # Convert coordinates (0-1) to actual coordinates
            x = int(result["x"] * self.width)
            y = int((1.0 - result["y"] - result["height"]) * self.height)
            width = int(result["width"] * self.width)
            height = int(result["height"] * self.height)

            self.results.append(
                {
                    "text": result["text"],
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "confidence": result["confidence"],
                }
            )

    def extract_matches(
        self, text: str, case_sensitive: bool = False, exact_match: bool = False
    ) -> List[Dict[str, Any]]:
        """Extract matches for text from OCR results.

        Args:
            text: Text to search for. If None or empty string, returns all OCR results.
            case_sensitive: Whether to perform case-sensitive search
            exact_match: Whether to require exact text match (no substrings)
        """
        if not self.results:
            return []

        # If text is None or empty, return all results
        if text is None or text == "":
            return [
                {**result, "full_text": result["text"], "is_exact_match": True}
                for result in self.results
            ]

        matches = []
        search_text = text if case_sensitive else text.lower()

        for result in self.results:
            current_text = result["text"] if case_sensitive else result["text"].lower()

            # Check for match based on exact_match parameter
            is_match = False
            if exact_match:
                is_match = current_text == search_text
            else:
                is_match = search_text in current_text

            if is_match:
                result = result.copy()  # Create a copy to avoid modifying original
                result["full_text"] = result["text"]
                result["is_exact_match"] = current_text == search_text

                # If this is a substring match, interpolate its coordinates
                if not exact_match and len(search_text) < len(current_text):
                    # Find where the substring starts in the original text
                    start_idx = current_text.index(search_text)
                    # Calculate width per character
                    char_width = result["width"] / len(current_text)
                    # Adjust x coordinate and width based on substring position
                    result["x"] = result["x"] + (start_idx * char_width)
                    result["width"] = len(search_text) * char_width

                matches.append(result)

        return matches

    def find_text(self, text: str) -> List[Dict[str, Any]]:
        """Find matches for text, using cache if available."""
        return self.extract_matches(text)


def get_active_window_name() -> str:
    """
    Get the name of the currently active (frontmost) window.

    Returns:
        str: Name of the active window, or "Unknown" if not found
    """
    workspace = NSWorkspace.sharedWorkspace()
    curr_pid = workspace.activeApplication()["NSApplicationProcessIdentifier"]

    options = kCGWindowListOptionOnScreenOnly
    window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)

    for window in window_list:
        if curr_pid == window["kCGWindowOwnerPID"]:
            return window.get("kCGWindowName", "Unknown")

    return "Unknown"


if __name__ == "__main__":
    # Configure logging to see what's happening
    from screenium import Text

    matches = Text().matches
    print(matches)
