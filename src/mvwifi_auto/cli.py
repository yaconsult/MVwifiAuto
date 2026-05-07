"""CLI entry point for mvwifi-auto."""

import sys

from mvwifi_auto.controller import main

if __name__ == "__main__":
    sys.exit(main())
