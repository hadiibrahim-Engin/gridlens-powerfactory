"""GridLens - preparation and presentation of pre-computed PowerFactory results.

GridLens starts *after* the network calculation. It reads existing QA results,
scenario metadata and simulation results, normalizes them, computes statistics
and comparisons, and hands a stable report data model to the Stimulsoft template.

GridLens deliberately does not judge results. It never emits verdicts such as
permissible, safe or critical; it prepares the data so an engineer can judge.
"""

__version__ = "2.0.0"

TEMPLATE_NAME = "MASTER_GRIDLENS"
TEMPLATE_VERSION = "2.0.0"
DATA_CONTRACT_VERSION = "2.0"
