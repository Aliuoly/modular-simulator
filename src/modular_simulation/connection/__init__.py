from __future__ import annotations

from modular_simulation.connection.hydraulics.hydraulic_compile import (
    CompiledHydraulicGraph,
    HydraulicCompileLifecycle,
)
from modular_simulation.connection.hydraulics.hydraulic_element import (
    ElementOutputSpec,
    ElementParameterSpec,
    ElementUnknownSpec,
    HydraulicElement,
)
from modular_simulation.connection.runtime.connected_plant_orchestrator import (
    ConnectedPlantInitializationResult,
    ConnectedPlantOrchestrator,
    ConnectedPlantPhaseHooks,
    ConnectedPlantStepResult,
)
from modular_simulation.connection.kernel_adapter import (
    CandidateKernelAdapter,
    KernelAdapterTelemetry,
    KernelCandidateStepRequest,
    KernelCandidateStepResult,
    KernelDelaySemantics,
    KernelDelayStrategy,
    KernelInitializationRequest,
    KernelInitializationResult,
    KernelOptionalCapability,
    KernelWarmStartRequest,
    KernelWarmStartResult,
    SupportsBoundsAccess,
    SupportsJacobianAccess,
    SupportsResidualEvaluation,
    SupportsStateVectorExport,
)
from modular_simulation.connection.topology.network import (
    CompiledConnectionNetwork,
    ConnectionNetwork,
    NetworkBoundarySpec,
    NetworkLineHydraulicConfig,
    NetworkProcessSpec,
)
from modular_simulation.connection.domain.reconfiguration_api import (
    DynamicConnectionLineReconfigurationApi,
    DynamicUnitPortReconfigurationApi,
)
from modular_simulation.connection.runtime.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.runtime.process_stream_io import ProcessOutletConditionResolver
from modular_simulation.connection.topology.process_binding import (
    BindingError,
    OutletBinding,
    OutletRole,
    ProcessBinding,
)
from modular_simulation.connection.topology.subsystem_descriptor import (
    Subsystem,
    SubsystemRuntimeDescriptor,
)

__all__ = [
    "BindingError",
    "CompiledConnectionNetwork",
    "CompiledHydraulicGraph",
    "CandidateKernelAdapter",
    "ConnectionNetwork",
    "DynamicConnectionLineReconfigurationApi",
    "DynamicUnitPortReconfigurationApi",
    "ConnectedPlantInitializationResult",
    "ConnectedPlantOrchestrator",
    "ConnectedPlantPhaseHooks",
    "ConnectedPlantStepResult",
    "HydraulicCompileLifecycle",
    "KernelAdapterTelemetry",
    "KernelCandidateStepRequest",
    "KernelCandidateStepResult",
    "KernelDelaySemantics",
    "KernelDelayStrategy",
    "KernelInitializationRequest",
    "KernelInitializationResult",
    "KernelOptionalCapability",
    "KernelWarmStartRequest",
    "KernelWarmStartResult",
    "ConnectionRuntimeOrchestrator",
    "NetworkBoundarySpec",
    "NetworkLineHydraulicConfig",
    "NetworkProcessSpec",
    "OutletBinding",
    "ProcessOutletConditionResolver",
    "OutletRole",
    "ProcessBinding",
    "SupportsBoundsAccess",
    "SupportsJacobianAccess",
    "SupportsResidualEvaluation",
    "SupportsStateVectorExport",
    "Subsystem",
    "SubsystemRuntimeDescriptor",
    "ElementOutputSpec",
    "ElementParameterSpec",
    "ElementUnknownSpec",
    "HydraulicElement",
]
