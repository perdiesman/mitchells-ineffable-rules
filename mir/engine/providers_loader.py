"""Validated discovery for built-in and third-party providers."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import inspect
import sys
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Type

from mir.engine.provider_interface import BaseProvider, ProviderCapabilities


class ProviderValidationError(Exception):
    pass


def validate_provider_class(provider_class: Type[BaseProvider]) -> None:
    provider_id = getattr(provider_class, "provider_id", None)
    if not isinstance(provider_id, str) or not provider_id or provider_id == "base":
        raise ProviderValidationError("Providers must declare a non-empty provider_id")
    if not isinstance(getattr(provider_class, "description", None), str):
        raise ProviderValidationError(f"Provider '{provider_id}' must declare a description")
    if not isinstance(getattr(provider_class, "capabilities", None), ProviderCapabilities):
        raise ProviderValidationError(f"Provider '{provider_id}' has invalid capabilities")
    for name in ("languages", "extensions"):
        values = getattr(provider_class, name, None)
        if not isinstance(values, tuple) or not all(isinstance(value, str) and value for value in values):
            raise ProviderValidationError(f"Provider '{provider_id}' has invalid {name}")
    if provider_class.run is BaseProvider.run:
        raise ProviderValidationError(f"Provider '{provider_id}' must implement run()")


def _classes_from_module(module: object) -> Iterable[Type[BaseProvider]]:
    for _, candidate in inspect.getmembers(module, inspect.isclass):
        if candidate is not BaseProvider and issubclass(candidate, BaseProvider):
            yield candidate


def _load_local(directory: str) -> Iterable[Type[BaseProvider]]:
    root = Path(directory)
    if not root.is_dir():
        return
    for path in sorted(root.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_name = f"mir_external_provider_{abs(hash(path.resolve()))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        yield from _classes_from_module(module)


@lru_cache(maxsize=16)
def _load_providers_cached(provider_dirs: tuple[str, ...]) -> tuple[BaseProvider, ...]:
    from mir.providers.eslint import EslintProvider
    from mir.providers.prettier import PrettierProvider
    from mir.providers.ruff import RuffProvider

    classes: list[Type[BaseProvider]] = [RuffProvider, EslintProvider, PrettierProvider]
    for entry_point in importlib.metadata.entry_points().select(group="mir.providers"):
        loaded = entry_point.load()
        classes.extend(_classes_from_module(loaded) if inspect.ismodule(loaded) else [loaded])
    for directory in provider_dirs:
        classes.extend(_load_local(directory))

    providers: list[BaseProvider] = []
    seen: set[str] = set()
    for provider_class in classes:
        validate_provider_class(provider_class)
        if provider_class.provider_id in seen:
            raise ProviderValidationError(f"Duplicate provider_id '{provider_class.provider_id}'")
        seen.add(provider_class.provider_id)
        providers.append(provider_class())
    return tuple(providers)


def load_providers(provider_dirs: Iterable[str] = ()) -> List[BaseProvider]:
    return list(_load_providers_cached(tuple(str(path) for path in provider_dirs)))

