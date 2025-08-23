from typing import Dict, Type
from .base import ProviderInterface

_registry: Dict[str, Type[ProviderInterface]] = {}

def register(provider_type: str, cls: Type[ProviderInterface]):
    _registry[provider_type] = cls

def get(provider_type: str) -> Type[ProviderInterface]:
    return _registry[provider_type]
