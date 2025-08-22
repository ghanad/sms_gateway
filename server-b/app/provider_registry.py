from typing import Dict, Type
from .providers.base import BaseProvider


class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}
        self._enabled: Dict[str, bool] = {}

    def register(self, name: str, provider: BaseProvider, enabled: bool = True) -> None:
        self._providers[name] = provider
        self._enabled[name] = enabled

    def get(self, name: str) -> BaseProvider:
        return self._providers[name]

    def is_enabled(self, name: str) -> bool:
        return self._enabled.get(name, False)

    def names(self) -> list[str]:
        return list(self._providers.keys())
