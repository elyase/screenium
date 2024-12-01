# 🎯 Screenium

Screenium is like Selenium after discovering there's a whole world outside the browser. Find and click any text on your screen using OCR. That "Accept Cookies" popup for the millionth time? Banish it. That stubborn system dialog that won't go away? Click it. That game that needs grinding? Automate it.

<img src="demo.gif" width="600px" alt="Demo">

## 🔍 Use Cases

- **Auto-Accept Cookies**: Run a background task that automatically clicks "Accept Cookies" popups
- **Meeting Assistant**: Auto-join video calls by detecting "Join Meeting" buttons and automatically enable/disable your camera/mic based on meeting names
- **Game Automation**: Automate repetitive game tasks by detecting and clicking on in-game text (e.g., "Collect Rewards", "Start Battle")
- **System Dialog Monitor**: Handling system or application dialogs, like "Are you sure?" or "Run command," in Cursor based on set rules.
- **Multi-Browser Testing**: Perform UI tests on browsers that lack automation APIs or web drivers with no separate web driver installations needed.

## 🔍 Finding Text

The most basic way to find text is:

```python
from screenium import Text

# Simple text matching
text = Text("Login")  # Finds "Login" anywhere on screen
text = Text("LOG")    # Matches "LOGIN", "LOGOUT", etc.

# Exact matching
text = Text("Login", exact_match=True)  # Only matches "Login" exactly
text = Text("login", case_sensitive=True)  # Case-sensitive matching
```

## 📍 Spatial Relationships

You can find text based on its position relative to other text:

```python
# Basic relationships
Text("Password").below("Username")  # Find "Password" below "Username"
Text("Cancel").left_of("Submit")    # Find "Cancel" left of "Submit"
Text("Help").right_of("Back")       # Find "Help" right of "Back"
Text("Title").above("Content")      # Find "Title" above "Content"

# Chain relationships
Text("Save").below("Options").right_of("Cancel")
```

### 📐 Aligned Elements

For more precise positioning, use `aligned` to require elements to line up:

```python
# Elements must be vertically aligned (same x-axis)
Text("Email").aligned.below("Username")

# Elements must be horizontally aligned (same y-axis)
Text("Back").aligned.left_of("Next")
```

## 🎨 Background Color Matching

Find text by its background color:

```python
# Match text with specific background colors
Text("Error", background_color="red")
Text("Success", background_color="green")
Text("Info", background_color="#0088ff")

# Adjust color matching tolerance (0-100)
Text("Warning", background_color="yellow", background_tolerance=50)
```

## 🖱️ Mouse Actions

Interact with matched text:

```python
# Basic mouse actions
Text("Submit").click()
Text("Options").right_click()
Text("Link").double_click()
Text("Button").mouse_move()  # Just move mouse without clicking

# Type text
Text("Username").click().typewrite("myuser")
Text("Password").click().typewrite("mypass")

# Special keys
Text("Terminal").click().typewrite(["command", "k"])  # Clear terminal
```

## ⏰ Waiting and Monitoring

Handle timing and background monitoring:

```python
# Wait for specific duration
Text("Loading").wait(2).click()  # Wait 2 seconds then click
```

## 🔍 Inspecting Matches

Get detailed information about matches:

```python
# Get all matches
matches = Text("Button").matches
for match in matches:
    print(f"Found at: ({match['x']}, {match['y']})")
    print(f"Size: {match['width']}x{match['height']}")
    print(f"Confidence: {match['confidence']}")
```

## 🎨 Visual Debugging

Draw boxes around matches to debug:

```python
# Draw green box for 3 seconds
Text("Username").draw(duration=3, color="green")

# Chain with other operations
Text("Password").below("Username").draw(duration=2, color="red").click()
```

## 🎯 Tips & Best Practices

1. Start with basic text matching before adding spatial relationships
2. Use `draw()` to visually verify matches
3. Adjust background color tolerance if color matching is too strict/loose
4. Use `aligned` when elements should line up precisely
5. Chain operations for more precise matching

## ⚠️ Limitations

- macOS only (uses Apple Vision framework)
- Requires macOS Monterey (12.x) or higher
- Screen resolution and scaling can affect matching

## 🔐 Required macOS Permissions

Screenium needs two key macOS permissions to function. The app running your Python script (e.g., Terminal, VS Code, PyCharm) will need:

1. **Screen Recording**
   - Open System Settings > Privacy & Security > Screen Recording
   - Toggle on your terminal app/IDE
   - Required for:
     - Finding text on screen using OCR
     - Background monitoring
     - Visual debugging with `draw()`

2. **Accessibility**
   - Open System Settings > Privacy & Security > Accessibility
   - Toggle on your terminal app/IDE
   - Required for:
     - Mouse actions (`click()`, `right_click()`, etc.)
     - Keyboard input (`typewrite()`, `hotkey()`)

> 💡 **Tip**: If running from different apps, each one needs separate permissions. For example, if you run scripts from both Terminal and VS Code, you'll need to grant permissions to both.

---
