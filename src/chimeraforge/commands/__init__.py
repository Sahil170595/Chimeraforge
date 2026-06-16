"""ChimeraForge CLI command implementations.

Each module defines one command function. They are registered on the Typer
``app`` in ``chimeraforge.cli``. Heavy dependencies are imported lazily inside
each function to keep ``chimeraforge --version`` fast.
"""
