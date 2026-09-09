"""PowerFactory reporting bridge.

The native bridge follows the user's IntReport example. A portable standalone
deployment entry point is also provided in the repository's powerfactory folder.
"""

from gridlens.powerfactory_reporting.bridge import IntReportBridge
from gridlens.powerfactory_reporting.powerfactory_bridge import PowerFactoryIntReportBridge
from gridlens.powerfactory_reporting.in_memory_bridge import (
    InMemoryIntReportBridge,
    RecordedTable,
)

__all__ = ["InMemoryIntReportBridge", "IntReportBridge", "PowerFactoryIntReportBridge", "RecordedTable"]
