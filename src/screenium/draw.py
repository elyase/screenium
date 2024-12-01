import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Union

import Cocoa
import objc
import Quartz
from colour import Color


def default_color() -> Color:
    """Default color factory function."""
    return Color("green")


@dataclass
class Shape:
    """Represents a drawable shape with position and dimensions."""

    shape_type: Literal["circle", "rectangle"]
    x: int
    y: int
    width: int
    height: int
    color: Color = field(default_factory=default_color)  # Default color is green
    line_width: float = 5.0  # Default line width


def parse_color(color: Union[str, tuple[float, float, float], Color]) -> Color:
    """Convert various color formats to Color object.

    Args:
        color: Can be:
            - Color name (e.g., 'red', 'blue', 'dark green')
            - Hex code (e.g., '#ff0000', '#0088ff')
            - RGB tuple (e.g., (1, 0, 0))
            - Color object

    Returns:
        Color object
    """
    if isinstance(color, Color):
        return color
    elif isinstance(color, tuple):
        return Color(rgb=color)
    else:
        return Color(color)


class OverlayView(Cocoa.NSView):
    def initWithFrame_(self, frame):
        self = objc.super(OverlayView, self).initWithFrame_(frame)
        if self:
            self.shapes: List[Shape] = []
            self.image_views = []
        return self

    def add_shape(self, shape: Shape):
        """Add a shape to be drawn on the overlay."""
        self.shapes.append(shape)
        self.setNeedsDisplay_(True)  # Trigger a redraw

    def add_image(
        self,
        x: int,
        y: int,
        width: Union[int, None] = None,
        height: Union[int, None] = None,
        percent: Union[int, float, None] = None,
        image_path: str = None,
    ):
        """Add an image to the view with flexible scaling options."""
        print(f"Attempting to load image from: {image_path}")
        image = Cocoa.NSImage.alloc().initWithContentsOfFile_(image_path)
        if not image:
            print(f"Failed to load image: {image_path}")
            return self

        # Get original image size
        original_size = image.size()
        original_width = original_size.width
        original_height = original_size.height
        aspect_ratio = original_width / original_height

        # Calculate new dimensions based on provided parameters
        if percent is not None:
            # Scale by percentage
            scale_factor = percent / 100.0
            new_width = original_width * scale_factor
            new_height = original_height * scale_factor
        elif width is None and height is None:
            # Use original size
            new_width = original_width
            new_height = original_height
        elif width is not None and height is None:
            # Scale based on width
            new_width = width
            new_height = width / aspect_ratio
        elif height is not None and width is None:
            # Scale based on height
            new_height = height
            new_width = height * aspect_ratio
        else:
            # Both width and height provided
            width_ratio = width / original_width
            height_ratio = height / original_height
            # Use the smaller ratio to fit within bounds
            scale_ratio = min(width_ratio, height_ratio)
            new_width = original_width * scale_ratio
            new_height = original_height * scale_ratio

        print(f"Original size: {original_width}x{original_height}")
        print(f"New size: {new_width}x{new_height}")

        # Create image view with calculated dimensions
        image_view = Cocoa.NSImageView.alloc().initWithFrame_(
            Cocoa.NSMakeRect(x, y, new_width, new_height)
        )

        # Enable animation for GIFs
        image_view.setAnimates_(True)
        image_view.setImage_(image)
        image_view.setImageScaling_(Cocoa.NSImageScaleProportionallyUpOrDown)

        # Check if image is animated
        if image.representations():
            first_rep = image.representations()[0]
            if hasattr(first_rep, "frameCount") and first_rep.frameCount() > 1:
                print(f"Animated GIF detected with {first_rep.frameCount()} frames")
                # Set animation properties
                image_view.setCanDrawConcurrently_(True)
                image_view.setEditable_(False)

        self.addSubview_(image_view)
        self.image_views.append(image_view)
        return self

    def drawRect_(self, rect):
        context = Cocoa.NSGraphicsContext.currentContext().CGContext()

        for shape in self.shapes:
            # Convert Color object to RGB values
            rgb = shape.color.rgb
            Quartz.CGContextSetRGBStrokeColor(context, *rgb, 1)  # Alpha is always 1
            Quartz.CGContextSetLineWidth(context, shape.line_width)

            rect = Quartz.CGRectMake(shape.x, shape.y, shape.width, shape.height)
            if shape.shape_type == "circle":
                Quartz.CGContextStrokeEllipseInRect(context, rect)
            else:
                Quartz.CGContextStrokeRect(context, rect)


class OverlayWindow(Cocoa.NSWindow):
    def canBecomeKeyWindow(self):
        return False

    def canBecomeMainWindow(self):
        return False


class TimerDelegate(Cocoa.NSObject):
    """Delegate class to handle timer callbacks."""

    def initWithWindow_(self, window):
        self = objc.super(TimerDelegate, self).init()
        if self is None:
            return None
        self.window = window
        self.did_hide = False
        return self

    def timerDidFire_(self, timer):
        self.window.orderOut_(None)
        self.did_hide = True


class ShapeDrawer:
    """Main class for drawing shapes on screen."""

    def __init__(self, duration: int = 5):
        self.duration = duration
        self.app = Cocoa.NSApplication.sharedApplication()
        self.window = None
        self.view = None
        self._setup_window()
        self.screen_height = Cocoa.NSScreen.mainScreen().frame().size.height

    def _convert_y_coordinate(self, y: int, height: int) -> int:
        """Convert Y coordinate from top-left to bottom-left origin.

        Args:
            y: Y coordinate in top-left coordinate system
            height: Height of the shape being drawn

        Returns:
            Y coordinate in bottom-left coordinate system
        """
        # The y coordinate is already in screen coordinates (top-left origin)
        # For Cocoa's bottom-left coordinate system, we need to flip it
        return self.screen_height - (y + height)

    def _setup_window(self):
        """Set up the overlay window."""
        screen = Cocoa.NSScreen.mainScreen()
        self.window = (
            OverlayWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                screen.frame(),
                Cocoa.NSBorderlessWindowMask,
                Cocoa.NSBackingStoreBuffered,
                False,
            )
        )
        self.window.setLevel_(Quartz.kCGFloatingWindowLevel)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(Cocoa.NSColor.clearColor())
        self.window.setIgnoresMouseEvents_(True)

        self.view = OverlayView.alloc().initWithFrame_(self.window.frame())
        self.window.setContentView_(self.view)

    def add_circle(
        self,
        x: int,
        y: int,
        diameter: int,
        color: Union[str, tuple[float, float, float], Color] = "red",
        line_width: float = 5.0,
    ):
        """Add a circle to be drawn.

        Args:
            x: X coordinate of the circle's top-left corner (from top-left origin)
            y: Y coordinate of the circle's top-left corner (from top-left origin)
            diameter: Diameter of the circle
            color: Color specification, can be:
                - Color name (e.g., 'red', 'blue', 'dark green')
                - Hex code (e.g., '#ff0000', '#0088ff')
                - RGB tuple (e.g., (1, 0, 0))
                - Color object
            line_width: Width of the circle's outline (default: 5.0)
        """
        converted_y = self._convert_y_coordinate(y, diameter)
        shape = Shape(
            "circle",
            x,
            converted_y,
            diameter,
            diameter,
            parse_color(color),
            line_width,
        )
        self.view.add_shape(shape)
        return self

    def add_rectangle(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: Union[str, tuple[float, float, float], Color] = "red",
        line_width: float = 5.0,
    ):
        """Add a rectangle to be drawn.

        Args:
            x: X coordinate of the rectangle's top-left corner (from top-left origin)
            y: Y coordinate of the rectangle's top-left corner (from top-left origin)
            width: Width of the rectangle
            height: Height of the rectangle
            color: Color specification, can be:
                - Color name (e.g., 'red', 'blue', 'dark green')
                - Hex code (e.g., '#ff0000', '#0088ff')
                - RGB tuple (e.g., (1, 0, 0))
                - Color object
            line_width: Width of the rectangle's outline (default: 5.0)
        """
        converted_y = self._convert_y_coordinate(y, height)
        shape = Shape(
            "rectangle",
            x,
            converted_y,
            width,
            height,
            parse_color(color),
            line_width,
        )
        self.view.add_shape(shape)
        return self

    def add_image(
        self,
        x: int,
        y: int,
        width: Union[int, None] = None,
        height: Union[int, None] = None,
        percent: Union[int, float, None] = None,
        image_path: str = None,
    ):
        """Add an image to be drawn.

        Args:
            x: X coordinate of the image's top-left corner (from top-left origin)
            y: Y coordinate of the image's top-left corner (from top-left origin)
            width: Target width (maintains aspect ratio if height is None)
            height: Target height (maintains aspect ratio if width is None)
            percent: Scale image by percentage (e.g., 50 for 50%)
            image_path: Path to the image file
        """

        # Let the view handle the image display
        self.view.add_image(
            x,
            self._convert_y_coordinate(y, height or 0),
            width,
            height,
            percent,
            image_path,
        )
        return self

    def show(self, duration: int = None):
        """Show all added shapes for the specified duration."""
        if duration is not None:
            self.duration = duration

        self.window.makeKeyAndOrderFront_(None)

        # Create timer to hide window
        delegate = TimerDelegate.alloc().initWithWindow_(self.window)
        Cocoa.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            self.duration, delegate, "timerDidFire:", None, False
        )

        # Run loop until window is hidden
        run_loop = Cocoa.NSRunLoop.currentRunLoop()
        while not delegate.did_hide:
            run_loop.runMode_beforeDate_(
                Cocoa.NSDefaultRunLoopMode,
                Cocoa.NSDate.dateWithTimeIntervalSinceNow_(0.1),
            )


def example_usage():
    """Example of how to use the ShapeDrawer with different shapes and images."""
    drawer = ShapeDrawer(duration=5)
    (
        drawer.add_rectangle(0, 0, 150, 100, "blue")
        .add_circle(400, 50, 80, "#ff00ff")
        .add_image(500, 500, image_path="animation.gif", percent=10)
        .show()
    )


if __name__ == "__main__":
    example_usage()
