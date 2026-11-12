class Colors:
    def __init__(self):
        """ANSI escape sequences for terminal colours and styles, plus semantic aliases (ERROR, SUCCESS, ...)."""

        self.BLACK = "\033[30m"
        self.RED = "\033[31m"
        self.DIM = "\033[2m"
        self.GREEN = "\033[32m"
        self.YELLOW = "\033[33m"
        self.BLUE = "\033[34m"
        self.MAGENTA = "\033[35m"
        self.CYAN = "\033[36m"
        self.WHITE = "\033[37m"

        # High-Intensity Colors
        self.BRIGHT_RED = "\033[91m"
        self.BRIGHT_GREEN = "\033[92m"
        self.BRIGHT_YELLOW = "\033[93m"
        self.BRIGHT_BLUE = "\033[94m"
        self.BRIGHT_MAGENTA = "\033[95m"
        self.BRIGHT_CYAN = "\033[96m"
        self.BRIGHT_WHITE = "\033[97m"

        self.ERROR = self.BRIGHT_RED
        self.SUCCESS = self.BRIGHT_GREEN
        self.WARNING = self.BRIGHT_YELLOW
        self.INFO = self.BRIGHT_BLUE

        self.BOLD = "\033[1m"
        self.RESET = "\033[0m"