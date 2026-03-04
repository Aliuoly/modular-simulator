## Design of the `Sensors`

`AbstractSensor` is the base class for sensor components. A sensor reads a process or registry tag, publishes a measured point, and can apply sampling, delay, noise, and fault behavior.

By design, a sensor is coupled to a `System` at install time.

It extends `AbstractComponent` and follows the component lifecycle:
1. `install(system)`: commissions the sensor and resolves its measurement getter.
2. `update(t)`: performs measurement updates through `_update`.
3. `should_update(t)`: controls whether an update runs at a given time.
4. `save()`: serializes configuration and runtime state.
5. `load(payload)`: restores a sensor from serialized payload.

Runtime rewiring is supported through `bind_runtime_signal(...)` and `unbind_runtime_signal(...)`, with rollback-safe state restoration on bind failures.
