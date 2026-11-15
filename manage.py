#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main():
    """Run administrative tasks."""
    # src layout：只装 requirements.txt 时也要能 import blog / imagehost。
    src = str(Path(__file__).resolve().parent / 'src')
    if src not in sys.path:
        sys.path.insert(0, src)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_blog.settings')
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
