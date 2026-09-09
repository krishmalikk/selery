"""Create a consistent SQLite research backup; restore is an explicit operator action."""
import argparse
import sqlite3
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
parser.add_argument('destination', type=Path)
args = parser.parse_args()
if not args.source.is_file() or args.destination.exists():
    parser.error('Source must exist and destination must be new.')
args.destination.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(args.source.resolve().as_uri() + '?mode=ro', uri=True) as source:
    with sqlite3.connect(args.destination) as destination:
        source.backup(destination)
        if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise SystemExit('Backup integrity check failed')
args.destination.chmod(0o600)
print('Consistent backup created and integrity checked; database contents were not printed.')
