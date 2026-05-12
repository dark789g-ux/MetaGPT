#!/usr/bin/env python
"""Django's command-line utility for administrative tasks.

MetaGPT vendor patch: the GA frontend reads/writes via relative paths
``storage/``, ``temp_storage/``, ``compressed_storage/``. We chdir to
the parent directory (``examples/stanford_town/``) so those relative
paths resolve to the shared directories that the MetaGPT backend
(``run_st_game.py``) writes into.
"""
import os
import sys
from pathlib import Path

# Resolve frontend project root and its parent (examples/stanford_town/)
FRONTEND_DIR = Path(__file__).resolve().parent
ST_ROOT = FRONTEND_DIR.parent
# Make Django find frontend_server package regardless of cwd
sys.path.insert(0, str(FRONTEND_DIR))


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'frontend_server.settings')
    # Switch cwd so views.py relative-path lookups (storage/, temp_storage/, ...)
    # land in the shared MetaGPT directories one level up.
    os.chdir(ST_ROOT)
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
