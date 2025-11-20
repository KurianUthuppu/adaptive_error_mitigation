# adaptive_error_mitigation/utils/color_log.py


# ANSI Color Codes
class ANSI:
    """Class containing standard ANSI escape codes for coloring terminal output."""

    # Text Styles
    BOLD = "\033[1m"
    RESET = "\033[0m"

    # Standard Colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"

    # Bright Colors (often used for metrics/values)
    B_YELLOW = "\033[93m"
    B_GREEN = "\033[92m"
    B_CYAN = "\033[96m"
    B_RED = "\033[91m"


# Utility function for quick coloring (optional but handy)
def colorize(text: str, color_code: str) -> str:
    """Wraps text in ANSI color codes."""
    return f"{color_code}{text}{ANSI.RESET}"
