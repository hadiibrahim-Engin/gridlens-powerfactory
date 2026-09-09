"""PowerFactory 2026 IntReport extension for MASTER_GRIDLENS.mrt.

The script reads existing ElmRes snapshots in the active study case, prepares
report variables in memory and publishes native IntReport tables. It does not
read a mock payload, write SQLite directly or need third-party packages.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# PowerFactory keeps sys.modules across script runs. Without this purge an edit
# to a submodule would not take effect while the entry file still reports the
# new publisher version -- exactly the failure the version banner should catch.
for _name in [n for n in sys.modules
              if n == "gridlens_pf" or n.startswith("gridlens_pf.")]:
    del sys.modules[_name]

from gridlens_pf.entry import main

if __name__ == "__main__":
    main()
