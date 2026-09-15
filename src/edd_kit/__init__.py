"""Native suite authoring interface. Importing EDD does not import DeepEval."""

from .suite import Case, Control, Suite

__version__ = "0.1.0"
__all__ = ["Case", "Control", "Suite", "__version__"]
