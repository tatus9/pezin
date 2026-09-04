"""Support ``python -m pezin``.

Delegates to the same entry point as the ``pezin`` console script.
"""

from pezin.cli.main import run

if __name__ == "__main__":
    run()
