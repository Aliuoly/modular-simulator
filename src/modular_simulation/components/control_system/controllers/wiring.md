```mermaid
classDiagram
    direction TB
    class PointRegistryView {
        controlled_state_1
        controlled_state_2
        ...
        index_map
        +get_converted_setter(unit, tag)
        +get_converted_getter(unit, tag)
    }
    class ControlElement {
        mv_tag
        mv_range
        mv_trajectory
        controller
        mode
        +install(System)
        +update(t)
        +change_control_mode(mode)
    }
    class Controller {
        <<ControllerBase>>
        cv_tag
        cv_range
        sp_trajectory
        cascade_controller
        mode
        +install(System)
        +wire_to_element(system, mv_getter, mv_range, mv_tag, mv_unit)
        +update(t)
        +change_control_mode(mode)
    }
    class CascadeController{
        <<ControllerBase>>
    }
    ControlElement -->  Controller
    Controller --> CascadeController
```
