"""Entry point for `python -m chimeraforge`.

Without this the conventional module invocation exited 0 having printed
nothing -- the worst possible response, since it looks like the command ran.
"""

from chimeraforge.cli import app

if __name__ == "__main__":
    app()
