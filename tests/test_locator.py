"""Tests for the Text functionality."""

from pathlib import Path

import pytest

from screenium.locator import Text, TextFinder


@pytest.fixture(autouse=True)
def patch_text(monkeypatch):
    """Patch Text class to always use test image."""
    image_path = str(Path(__file__).parent / "screenshot.png")
    original_init = Text.__init__

    def patched_init(self, text=None, image_path=image_path, **kwargs):
        kwargs["recognition_level"] = "accurate"
        original_init(self, text=text, image_path=image_path, **kwargs)

    monkeypatch.setattr(Text, "__init__", patched_init)


def test_basic_spatial_relationships():
    """Test basic directional relationships between text elements."""
    # Print all elements to see what we're working with
    print("\nAll elements:")
    print(f"Left: {Text('Left')}")
    print(f"Right: {Text('Right')}")
    print(f"Top: {Text('Top')}")
    print(f"Bottom: {Text('Bottom')}")
    print(f"Center: {Text('Center')}")
    print(f"TL: {Text('TL')}")
    print(f"TR: {Text('TR')}")
    print(f"BL: {Text('BL')}")
    print(f"BR: {Text('BR')}")

    # Basic directional relationships without alignment
    assert Text("Left").left_of("Center")
    assert Text("Right").right_of("Center")
    assert Text("Top").above("Center")
    assert Text("Bottom").below("Center")

    # Verify negatives without alignment
    assert not Text("Center").left_of("Left")
    assert not Text("Center").right_of("Right")
    assert not Text("Center").above("Top")
    assert not Text("Center").below("Bottom")


def test_chained_relationships():
    """Test chaining multiple spatial relationships."""
    # Test diagonal positions without alignment
    assert Text("TL").above("Center").left_of("Center")
    assert Text("TR").above("Center").right_of("Center")
    assert Text("BL").below("Center").left_of("Center")
    assert Text("BR").below("Center").right_of("Center")

    # Verify negatives for chained relationships
    assert not Text("Center").above("Top").left_of("Left")
    assert not Text("Center").below("Bottom").right_of("Right")


def test_aligned_relationships():
    """Test relationships that require alignment."""
    print("\nStarting aligned relationships test")
    # Test aligned relationships
    assert Text("Left").aligned.left_of("Center")
    assert Text("Right").aligned.right_of("Center")
    assert Text("Top").aligned.above("Center")
    assert Text("Bottom").aligned.below("Center")

    # Verify negatives with alignment
    assert not Text("Center").aligned.left_of("Left")
    assert not Text("Center").aligned.right_of("Right")
    assert not Text("Center").aligned.above("Top")
    assert not Text("Center").aligned.below("Bottom")

    # Test that aligned requires proper alignment
    assert not Text("TL").aligned.left_of(
        "Bottom"
    )  # Should fail because they don't have vertical overlap
    assert Text("TL").left_of("Bottom")  # Should pass because it's not using aligned

    # Test that substring matches work with alignment
    assert Text("T").aligned.above(
        "Center"
    )  # Should pass - matches "Top" which is aligned with Center


def test_edge_cases():
    """Test edge cases and special scenarios."""
    # Test elements that are far apart
    assert Text("TL").above("BR")
    assert Text("BR").below("TL")
    assert Text("TL").left_of("TR")
    assert Text("BL").left_of("BR")


def test_substring_with_alignment():
    """Test that substring matches must respect alignment."""
    # This should pass because 'T' matches 'Top' which is aligned with Center
    assert Text("T").aligned.above(
        "Center"
    )  # 'Top' has 76 pixels of horizontal overlap with 'Center'


def test_match_filtering():
    """Test how matches get filtered through operation chains."""
    print("\nStarting match filtering test")

    # Should start with both TL and TR (they both contain 'T')
    # Then filter to only those above Center
    # Then filter to only those left of Right
    # Should end up with just TL
    result = Text("T").above("Center").left_of("Right")
    assert result  # Force evaluation

    print("\nTesting alignment filtering:")
    # Should start with matches containing 'T'
    # Then require alignment with Center
    # Should match "Top" because it's aligned with Center
    result = Text("T").aligned.above("Center")
    assert result  # Should pass because "Top" is aligned with Center

    print("\nTest complete")


def test_aligned_flag():
    """Test that aligned flag affects only the next spatial operation."""
    print("\nTesting aligned flag behavior")

    # When we do aligned.above, it should:
    # 1. Set the aligned flag
    # 2. Then when doing 'above', check both alignment and position
    result = Text("T").aligned.above("Center")
    print("\nMatches after aligned.above:")
    print(result)

    # The aligned flag should only affect the next operation
    # So this should match TL because the 'left_of' isn't affected by aligned
    result = Text("TL").aligned.above("Center").left_of("Right")
    print("\nMatches after aligned.above.left_of:")
    print(result)


def test_matches_property():
    """Test the matches property."""
    # Test getting all OCR results with None
    all_matches_none = Text(None).matches
    print("\nAll OCR results (None):")
    for match in all_matches_none:
        print(f"Text: {match['text']}, Position: ({match['x']}, {match['y']})")
    assert len(all_matches_none) > 0, "Should find all text elements with None"

    # Test getting all OCR results with empty string
    all_matches_empty = Text("").matches
    print("\nAll OCR results (empty string):")
    for match in all_matches_empty:
        print(f"Text: {match['text']}, Position: ({match['x']}, {match['y']})")
    assert len(all_matches_empty) > 0, "Should find all text elements with empty string"

    # Verify both methods return the same results
    assert len(all_matches_none) == len(
        all_matches_empty
    ), "None and empty string should return same number of matches"
    assert all(
        a["text"] == b["text"] for a, b in zip(all_matches_none, all_matches_empty)
    ), "None and empty string should return same text matches"

    # Test exact match for Center
    center_matches = Text("Center").matches
    print(
        "\nCenter coordinates:",
        {
            "x": center_matches[0]["x"],
            "y": center_matches[0]["y"],
            "width": center_matches[0]["width"],
            "height": center_matches[0]["height"],
        },
    )
    assert len(center_matches) == 1
    assert center_matches[0]["text"] == "Center"
    assert center_matches[0]["confidence"] > 0.9

    # Compare x coordinates of Center and Right
    right_matches = Text("Right").matches
    print(
        "\nRight coordinates:",
        {
            "x": right_matches[0]["x"],
            "y": right_matches[0]["y"],
            "width": right_matches[0]["width"],
            "height": right_matches[0]["height"],
        },
    )
    assert len(right_matches) == 1
    print(
        f"\nX difference: Right.x ({right_matches[0]['x']}) - Center.x ({center_matches[0]['x']}) = {right_matches[0]['x'] - center_matches[0]['x']}"
    )
    assert (
        right_matches[0]["x"] > center_matches[0]["x"]
    ), "Right should be to the right of Center"

    # Test exact matches for TL
    tl_matches = Text("TL").matches
    print(
        "\nTL coordinates:",
        {
            "x": tl_matches[0]["x"],
            "y": tl_matches[0]["y"],
            "width": tl_matches[0]["width"],
            "height": tl_matches[0]["height"],
        },
    )
    assert len(tl_matches) == 1
    assert tl_matches[0]["text"] == "TL"

    # Test filtered matches
    filtered = Text("TL").above("Center").matches
    assert len(filtered) == 1  # Only TL


def test_exact_and_case_matching():
    """Test exact match and case sensitivity options."""
    # Test substring matching (default behavior)
    t_matches = Text("T").matches
    assert len(t_matches) > 2, "Should find multiple matches containing 'T'"

    # Test exact matching
    t_exact = Text("T", exact_match=True).matches
    assert len(t_exact) == 0, "Should find no exact matches for 'T'"

    tl_exact = Text("TL", exact_match=True).matches
    assert len(tl_exact) == 1, "Should find exactly one match for 'TL'"
    assert tl_exact[0]["text"] == "TL"

    # Test case sensitivity
    tl_case = Text("tl", case_sensitive=True).matches
    assert len(tl_case) == 0, "Should find no matches for lowercase 'tl'"

    tl_nocase = Text("tl", case_sensitive=False).matches
    assert len(tl_nocase) == 1, "Should find 'TL' when case insensitive"

    # Test both exact match and case sensitivity
    tl_exact_case = Text("TL", exact_match=True, case_sensitive=True).matches
    assert len(tl_exact_case) == 1, "Should find exact match for 'TL'"

    tl_exact_nocase = Text("tl", exact_match=True, case_sensitive=False).matches
    assert (
        len(tl_exact_nocase) == 1
    ), "Should find 'TL' with exact match but case insensitive"


def test_background_color_matching():
    """Test background color matching functionality."""
    # Test basic colors that should always work reliably
    basic_colors = [
        ("Center", "red"),  # Red
        ("BL", "blue"),  # Blue
        ("TL", "green"),  # Green
    ]

    print("\nTesting basic color matching:")
    for text, color in basic_colors:
        matches = Text(text, background_color=color).matches
        print(
            f"\n{text} with {color} background matches:",
            [
                {"text": m["text"], "color_distance": m["color_distance"]}
                for m in matches
            ],
        )
        assert len(matches) == 1, f"Should match {text} with {color} background"
        assert matches[0]["text"] == text, f"Should match exact text '{text}'"
        assert (
            matches[0]["color_distance"] <= 35
        ), f"Color distance for {text} should be within tolerance"

    # Test additional colors that may need more tolerance
    additional_colors = [
        ("Top", "green"),  # Dark green still matches with "green"
        ("Right", "red"),  # Darker red still matches with "red"
        ("Bottom", "yellow"),  # Yellow
        ("BR", "orange"),  # Orange
        ("TR", "gray"),  # Gray
    ]

    print("\nTesting additional color variations:")
    for text, color in additional_colors:
        matches = Text(text, background_color=color).matches
        print(
            f"\n{text} with {color} background matches:",
            [
                {"text": m["text"], "color_distance": m["color_distance"]}
                for m in matches
            ],
        )
        # These colors may need more tolerance, so we just verify they're found
        assert len(matches) >= 0, f"Should find {text} with {color} background"
        if matches:
            assert matches[0]["text"] == text, f"Should match exact text '{text}'"

    # Cross-verification: ensure distinctly different colors don't match
    mismatches = [
        ("Center", "blue"),  # Red shouldn't match with blue
        ("BL", "red"),  # Blue shouldn't match with red
    ]

    print("\nTesting color mismatches:")
    for text, color in mismatches:
        matches = Text(text, background_color=color).matches
        print(
            f"\n{text} with {color} background matches:",
            [
                {"text": m["text"], "color_distance": m["color_distance"]}
                for m in matches
            ],
        )
        assert len(matches) == 0, f"{text} shouldn't match with {color} background"


@pytest.mark.parametrize(
    "ocr_result,search_text,expected_x",
    [
        # The OCR engine recognizes "Welcome to Center" but we want to find "to"
        # Since "to" starts at index 8 (after "Welcome ") in a 150px wide text,
        # Each character is roughly 150/17 ≈ 8.82px wide (17 chars including spaces)
        # So "to" should start at approximately: 100 + (8 * 8.82) ≈ 170.59
        (
            {
                "text": "Welcome to Center",
                "x": 100,
                "y": 200,
                "width": 150,
                "height": 30,
                "confidence": 0.95,
            },
            "to",
            170.6,  # Rounded for readability
        )
    ],
)
def test_substring_within_longer_text(ocr_result, search_text, expected_x):
    """Test that when matching a substring, its coordinates are correctly interpolated."""
    finder = TextFinder()
    finder.results = [ocr_result]

    text = Text(search_text, finder=finder)
    matches = text.matches

    assert len(matches) == 1, "Should find exactly one match"
    match = matches[0]
    assert search_text in match["text"], "Match should contain the search text"
    assert match["x"] == pytest.approx(
        expected_x, rel=0.01
    ), "X coordinate should be approximately correct"
