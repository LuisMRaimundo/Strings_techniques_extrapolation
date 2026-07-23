"""GUI entry point — numerical narrow extrapolator (no audio)."""

from __future__ import annotations

from string_technique_model.gui_metadata.extrapolator_app import (
    NarrowExtrapolatorApp,
    launch_extrapolator_gui,
)


def launch_gui() -> None:
    launch_extrapolator_gui()


def main() -> None:
    launch_gui()


__all__ = ["NarrowExtrapolatorApp", "launch_gui", "main"]


if __name__ == "__main__":
    main()
