"""Vestaboard character encoding.

The Vestaboard uses a 6-row by 22-column display.
Each character is represented by a numeric code.
"""

import re

# Character code mapping
CHAR_CODES = {
    " ": 0,
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8, "I": 9,
    "J": 10, "K": 11, "L": 12, "M": 13, "N": 14, "O": 15, "P": 16, "Q": 17,
    "R": 18, "S": 19, "T": 20, "U": 21, "V": 22, "W": 23, "X": 24, "Y": 25,
    "Z": 26,
    "1": 27, "2": 28, "3": 29, "4": 30, "5": 31, "6": 32, "7": 33, "8": 34,
    "9": 35, "0": 36,
    "!": 37, "@": 38, "#": 39, "$": 40, "(": 41, ")": 42,
    "-": 44, "+": 46, "&": 47, "=": 48, ";": 49, ":": 50,
    "'": 52, '"': 53, "%": 54, ",": 55, ".": 56,
    "/": 59, "?": 60, "°": 62,
    # Poppet character (filled square)
    "█": 71,
}

# Special codes that can be used in text with {CODE} syntax
SPECIAL_CODES = {
    "RED": 63,
    "ORANGE": 64,
    "YELLOW": 65,
    "GREEN": 66,
    "BLUE": 67,
    "VIOLET": 68,
    "WHITE": 69,
    "BLACK": 70,
    "BLOCK": 71,
}

# Pattern to match special codes like {RED}, {BLUE}, etc.
SPECIAL_CODE_PATTERN = re.compile(r'\{(' + '|'.join(SPECIAL_CODES.keys()) + r')\}', re.IGNORECASE)

# Reverse lookup
CODE_TO_CHAR = {v: k for k, v in CHAR_CODES.items()}

# Display dimensions
ROWS = 6
COLS = 22


def text_to_codes(text: str) -> list[int]:
    """Convert text string to list of character codes.

    Supports special codes like {RED}, {BLUE}, {BLOCK}, etc.

    Args:
        text: Text to convert (will be uppercased).

    Returns:
        List of character codes.
    """
    codes = []
    text = text.upper()
    i = 0

    while i < len(text):
        # Check for special code pattern like {RED}
        if text[i] == '{':
            match = SPECIAL_CODE_PATTERN.match(text, i)
            if match:
                code_name = match.group(1).upper()
                codes.append(SPECIAL_CODES[code_name])
                i = match.end()
                continue

        # Regular character
        char = text[i]
        if char in CHAR_CODES:
            codes.append(CHAR_CODES[char])
        else:
            # Unknown character becomes space
            codes.append(0)
        i += 1

    return codes


def get_display_length(text: str) -> int:
    """Get the display length of text (accounting for special codes).

    Special codes like {RED} take up 1 cell on the board.

    Args:
        text: Text to measure.

    Returns:
        Number of cells the text will occupy.
    """
    # Remove special codes and count their occurrences
    special_count = len(SPECIAL_CODE_PATTERN.findall(text))
    # Remove special codes from text to get regular chars
    text_without_special = SPECIAL_CODE_PATTERN.sub('', text)
    return len(text_without_special) + special_count


def create_board(lines: list[str], center: bool = True) -> list[list[int]]:
    """Create a 6x22 board from lines of text.

    Args:
        lines: List of up to 6 lines of text.
        center: If True, center each line horizontally.

    Returns:
        6x22 matrix of character codes.
    """
    board = [[0] * COLS for _ in range(ROWS)]

    for row_idx, line in enumerate(lines[:ROWS]):
        codes = text_to_codes(line)
        # Truncate to fit display
        codes = codes[:COLS]

        if center:
            # Center the text based on actual display length
            padding = (COLS - len(codes)) // 2
            start_col = padding
        else:
            start_col = 0

        for col_idx, code in enumerate(codes):
            if start_col + col_idx < COLS:
                board[row_idx][start_col + col_idx] = code

    return board


def wrap_text(text: str, width: int = COLS) -> list[str]:
    """Wrap text to fit within specified width.

    Accounts for special codes like {RED} which take 1 cell on the board.

    Args:
        text: Text to wrap.
        width: Maximum characters per line.

    Returns:
        List of lines.
    """
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        # Use display length for special codes
        word_length = get_display_length(word)

        if current_length + word_length + (1 if current_line else 0) <= width:
            current_line.append(word)
            current_length += word_length + (1 if len(current_line) > 1 else 0)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = word_length

    if current_line:
        lines.append(" ".join(current_line))

    return lines


def format_message(text: str, center: bool = True) -> list[list[int]]:
    """Format a text message for the Vestaboard.

    Automatically wraps text and creates a centered display.

    Args:
        text: Message to display.
        center: If True, center text horizontally and vertically.

    Returns:
        6x22 matrix of character codes.
    """
    lines = wrap_text(text)

    # Limit to 6 lines
    lines = lines[:ROWS]

    # Vertical centering
    if center and len(lines) < ROWS:
        padding = (ROWS - len(lines)) // 2
        lines = [""] * padding + lines

    return create_board(lines, center=center)
