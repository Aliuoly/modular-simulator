from collections.abc import Mapping, Callable, Iterator
from typing import override
from .point import Point, DataValue
from astropy.units import UnitBase, UnitsError
from modular_simulation.validation.exceptions import MeasurableConfigurationError


class PointRegistry(Mapping[str, Point]):
    """
    Provides centralized storage and convenient functions for accessing & updating points.
    Behaves like a dictionary mapping tag names to Point objects.
    """

    def __init__(self, points: dict[str, Point] | None = None):
        self._points: dict[str, Point] = points if points else {}
        self._published_point_owner_by_tag: dict[str, str] = {}

        # Internal caches for filtered views
        self._measured_points: dict[str, Point] | None = None
        self._calculated_points: dict[str, Point] | None = None
        self._reference_points: dict[str, Point] | None = None

    @override
    def __getitem__(self, key: str) -> Point:
        return self._points[key]

    @override
    def __iter__(self) -> Iterator[str]:
        return iter(self._points)

    @override
    def __len__(self) -> int:
        return len(self._points)

    @override
    def __repr__(self) -> str:
        return f"PointRegistry({self._points})"

    @property
    def measured_points(self) -> dict[str, Point]:
        """Returns a dictionary of all measured points."""
        if self._measured_points is None:
            self._measured_points = {k: v for k, v in self._points.items() if v.type == "measured"}
        return self._measured_points

    @property
    def calculated_points(self) -> dict[str, Point]:
        """Returns a dictionary of all calculated points."""
        if self._calculated_points is None:
            self._calculated_points = {
                k: v for k, v in self._points.items() if v.type == "calculated"
            }
        return self._calculated_points

    @property
    def reference_points(self) -> dict[str, Point]:
        if self._reference_points is None:
            self._reference_points = {
                k: v for k, v in self._points.items() if v.type == "reference"
            }
        return self._reference_points

    def add(
        self,
        point: Point | dict[str, Point],
        *,
        subsystem_namespace: str | None = None,
        published_tag: str | None = None,
    ) -> None:
        """
        Adds a Point object to the registry.
        Updates cached views if they have been accessed.
        """
        if isinstance(point, dict):
            if published_tag is not None:
                raise ValueError("published_tag cannot be provided when adding a point dictionary.")
            for p in point.values():
                self.add(p, subsystem_namespace=subsystem_namespace)
            return

        registration_tag = self._resolve_registration_tag(
            point=point,
            subsystem_namespace=subsystem_namespace,
            published_tag=published_tag,
        )

        if registration_tag in self._points:
            raise ValueError(f"Point '{registration_tag}' already exists in registry.")

        self._points[registration_tag] = point

        # Update caches if they exist (incremental update)
        if self._measured_points is not None and point.type == "measured":
            self._measured_points[registration_tag] = point
        elif self._calculated_points is not None and point.type == "calculated":
            self._calculated_points[registration_tag] = point
        elif self._reference_points is not None and point.type == "reference":
            self._reference_points[registration_tag] = point

    def _resolve_registration_tag(
        self,
        *,
        point: Point,
        subsystem_namespace: str | None,
        published_tag: str | None,
    ) -> str:
        if subsystem_namespace is None:
            if published_tag is not None:
                raise ValueError("published_tag requires subsystem_namespace.")
            return point.tag

        normalized_namespace = self._normalize_subsystem_namespace(subsystem_namespace)
        source_tag = point.tag if published_tag is None else published_tag
        normalized_published_tag = self._normalize_published_tag(source_tag)
        self._validate_published_tag_collision(
            subsystem_namespace=normalized_namespace,
            published_tag=normalized_published_tag,
        )
        return f"{normalized_namespace}/{normalized_published_tag}"

    def _normalize_subsystem_namespace(self, subsystem_namespace: str) -> str:
        normalized_namespace = subsystem_namespace.strip()
        if not normalized_namespace:
            raise MeasurableConfigurationError(
                "Subsystem namespace for published measurement registration must be non-empty."
            )
        if "/" in normalized_namespace:
            raise MeasurableConfigurationError(
                "Subsystem namespace for published measurement registration must not contain '/'."
            )
        return normalized_namespace

    def _normalize_published_tag(self, published_tag: str) -> str:
        normalized_tag = published_tag.strip()
        if not normalized_tag:
            raise MeasurableConfigurationError(
                "Published measurement tag must be non-empty for subsystem registration."
            )
        if "/" in normalized_tag:
            raise MeasurableConfigurationError(
                f"Published measurement tag '{normalized_tag}' must not contain '/'."
            )
        return normalized_tag

    def _validate_published_tag_collision(
        self, *, subsystem_namespace: str, published_tag: str
    ) -> None:
        existing_owner = self._published_point_owner_by_tag.get(published_tag)
        if existing_owner is None:
            self._published_point_owner_by_tag[published_tag] = subsystem_namespace
            return
        if existing_owner != subsystem_namespace:
            raise MeasurableConfigurationError(
                f"Published measurement tag collision for '{published_tag}': "
                + f"already registered by subsystem '{existing_owner}', "
                + f"cannot register for subsystem '{subsystem_namespace}'."
            )

    def make_converted_data_getter(
        self, tag: str, target_unit: UnitBase | None = None
    ) -> Callable[[], DataValue]:
        """
        Convenient method equivalent to Point.make_converted_data_getter.
        Creates a getter for a point that converts data to the target unit.
        """
        if tag not in self._points:
            raise KeyError(f"Point '{tag}' not found in registry.")
        try:
            if target_unit is None:
                target_unit = self._points[tag].unit
            return self._points[tag].make_converted_data_getter(target_unit)
        except UnitsError as e:
            raise UnitsError(
                f"Failed to create converter for point '{tag}' from {self._points[tag].unit} to {target_unit}: {e}"
            )

    def make_converted_data_setter(
        self, tag: str, source_unit: UnitBase | None = None
    ) -> Callable[[DataValue], None]:
        """
        Convenient method equivalent to Point.make_converted_data_setter.
        Creates a setter for a point that converts data from the source unit.
        """
        if tag not in self._points:
            raise KeyError(f"Point '{tag}' not found in registry.")
        try:
            if source_unit is None:
                source_unit = self._points[tag].unit
            return self._points[tag].make_converted_data_setter(source_unit)
        except UnitsError as e:
            raise UnitsError(
                f"Failed to create converter for point '{tag}' from {source_unit} to {self._points[tag].unit}: {e}"
            )

    def make_data_updater(self, tag: str) -> Callable[[DataValue], None]:
        """Creates a callback to update the data of a specific point."""
        if tag not in self._points:
            raise KeyError(f"Point '{tag}' not found in registry.")

        point = self._points[tag]

        def data_updater(data_value: DataValue) -> None:
            point.data = data_value

        return data_updater

    @property
    def history(self) -> dict[str, list[DataValue]]:
        return {k: v.history for k, v in self._points.items()}
