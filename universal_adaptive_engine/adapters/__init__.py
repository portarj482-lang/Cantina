"""Adapter package for Universal Adaptive Intelligence Architecture."""
from universal_adaptive_engine.adapters.protocol import (
    ArchitectureAdapter,
    BaseArchitectureAdapter,
    AdapterResult,
)
from universal_adaptive_engine.adapters.host_adapter import HostEnvironmentAdapter
from universal_adaptive_engine.adapters.cantina_adapter import CantinaBountyAdapter
from universal_adaptive_engine.adapters.discovery import TargetDiscoveryAdapter
from universal_adaptive_engine.adapters.evm_adapter import EVMArchitectureAdapter
from universal_adaptive_engine.adapters.solana_adapter import SolanaArchitectureAdapter

__all__ = [
    "ArchitectureAdapter",
    "BaseArchitectureAdapter",
    "AdapterResult",
    "HostEnvironmentAdapter",
    "CantinaBountyAdapter",
    "TargetDiscoveryAdapter",
    "EVMArchitectureAdapter",
    "SolanaArchitectureAdapter",
]
