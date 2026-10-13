"""Public contracts for external formatter and linter providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ProviderCapabilities:
    check: bool = True
    fix: bool = False
    format: bool = False
    range_format: bool = False
    batch: bool = False


@dataclass(frozen=True)
class ProviderCase:
    name: str
    source: str
    expectation: str
    fixed: Optional[str] = None


@dataclass(frozen=True)
class ProviderEdit:
    start: int
    end: int
    replacement: str
    applicability: str = "tool"


@dataclass(frozen=True)
class ProviderFinding:
    code: str
    message: str
    line: int
    column: int = 1
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    severity: str = "error"
    edits: Tuple[ProviderEdit, ...] = ()


@dataclass
class ProviderResult:
    content: str
    findings: List[ProviderFinding] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)
    changed: bool = False
    version: Optional[str] = None


@dataclass(frozen=True)
class ProviderContext:
    path: str
    language: str
    selected_lines: FrozenSet[int]
    restricted: bool
    fix: bool
    profile: Optional[str]
    disabled_lines: Dict[str, FrozenSet[int]]


class BaseProvider:
    """Validated extension point for tools implemented outside MIR rules."""

    provider_id = "base"
    description = "External tool provider"
    languages: Tuple[str, ...] = ()
    extensions: Tuple[str, ...] = ()
    capabilities = ProviderCapabilities()
    default_config: Dict[str, Any] = {}
    config_options: Dict[str, Dict[str, Any]] = {}
    cases: Sequence[ProviderCase] = ()
    documentation_url: Optional[str] = None

    def run(
        self,
        content: str,
        context: ProviderContext,
        provider_config: Dict[str, Any],
    ) -> ProviderResult:
        raise NotImplementedError

