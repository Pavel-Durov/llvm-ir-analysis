from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List

from .model import Function


class BaseParser(ABC):
    """Base class for all parsers (IR, MIR, ASM)."""

    @abstractmethod
    def parse(self, filename: str, skip_patterns: List[str] | None = None,
              skip_prefixes: List[str] | None = None) -> Dict[str, Function]:
        """Parse the file and return a dictionary of functions.

        Args:
            filename: Path to the file to parse
            skip_patterns: Skip functions whose name contains any of these substrings
            skip_prefixes: Skip functions whose name starts with any of these prefixes

        Returns:
            Dict mapping function names to Function objects
        """
        pass

