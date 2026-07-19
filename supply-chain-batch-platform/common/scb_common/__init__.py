"""scb_common — shared library for the Supply Chain Batch Data Platform.

Import the pieces you need:

    from scb_common import get_logger, BatchContext
    from scb_common.config import load_config
    from scb_common.schema import ColumnSpec, TableSchema
    from scb_common.dq import NotNull, Unique, InRange, evaluate
    from scb_common.metadata import JsonlMetadataStore, BatchAudit

The core has one runtime dependency (PyYAML). Spark helpers are an optional
extra so this package stays fast to import and test.
"""

from scb_common.context import BatchContext
from scb_common.errors import ConfigError, DataQualityError, SchemaValidationError
from scb_common.logging import get_logger
from scb_common.retry import retry

__all__ = [
    "BatchContext",
    "ConfigError",
    "DataQualityError",
    "SchemaValidationError",
    "get_logger",
    "retry",
]

__version__ = "0.1.0"
