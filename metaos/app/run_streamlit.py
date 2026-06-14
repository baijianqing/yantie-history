"""Run Streamlit with MetaOS-specific process setup."""

from __future__ import annotations

import asyncio
import sys


def configure_windows_event_loop() -> None:
    """Avoid noisy Proactor transport resets from Streamlit/Tornado on Windows."""
    if sys.platform != "win32":
        return
    selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if selector_policy is not None:
        asyncio.set_event_loop_policy(selector_policy())


def main() -> None:
    configure_windows_event_loop()
    from streamlit.web.cli import main as streamlit_main

    streamlit_main(prog_name="streamlit", args=sys.argv[1:])


if __name__ == "__main__":
    main()
