import os
import sys

# Allow --data-root before package imports bind DATA_ROOT.
if "--data-root" in sys.argv:
    idx = sys.argv.index("--data-root")
    if idx + 1 < len(sys.argv):
        os.environ["EV_DATA_ROOT"] = sys.argv[idx + 1]

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
