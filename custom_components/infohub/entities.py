"""Default entity-group configuration for InfoHub.

Mirrors the entities configured today in the standalone service's
config.yaml (root of the repo). This is a hardcoded default for this
step - a follow-up options-flow will make these editable via the HA UI
(see the implementation plan's "Nicht enthalten" section) instead of
requiring a code change to add/remove a sensor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .const import GROUP_ABFALL, GROUP_RAUMKLIMA, GROUP_STROM, GROUP_WETTER


@dataclass(frozen=True)
class EntityConfig:
    """One tracked entity: its display label, unit and optional type."""

    entity_id: str
    label: str
    unit: str | None = None
    # Meaning depends on the entity's group: "weather" (GROUP_WETTER) marks
    # the one entity that gets extended attributes/forecast; for
    # GROUP_AKTOREN this instead picks the actuator widget's per-row
    # control - "cover" (Auf/Stop/Zu) or "slider" (drag to set a value,
    # see min_value/max_value), None/anything else means the default
    # on/off toggle. See coordinator.py's _async_transform_state().
    type: str | None = None
    # Slider range override - only meaningful when type == "slider". When
    # unset, coordinator.py falls back to the entity's own min/max state
    # attribute (number/input_number) or a 0-100 default (light/cover).
    min_value: float | None = None
    max_value: float | None = None


DEFAULT_ENTITY_GROUPS: dict[str, tuple[EntityConfig, ...]] = {
    GROUP_WETTER: (
        EntityConfig("weather.forecast_home", "Wetter", type="weather"),
        EntityConfig("sun.sun", "Sonne"),
    ),
    GROUP_STROM: (
        EntityConfig(
            "sensor.tibber_pulse_home_leistung",
            "Aktueller Verbrauch",
            unit="W",
        ),
        EntityConfig(
            "sensor.tibber_pulse_home_kumulierter_verbrauch",
            "Verbrauch heute",
            unit="kWh",
        ),
        EntityConfig(
            "sensor.home_strompreis", "Strompreis", unit="ct/kWh"
        ),
        EntityConfig(
            "sensor.home_monatliche_kosten",
            "Monatliche Kosten",
            unit="€",
        ),
    ),
    GROUP_RAUMKLIMA: (
        EntityConfig(
            "sensor.thermo_wohnzimmer_temperature", "Innentemperatur", unit="°C"
        ),
        EntityConfig(
            "sensor.thermo_wohnzimmer_humidity", "Innenfeuchtigkeit", unit="%"
        ),
    ),
    GROUP_ABFALL: (
        EntityConfig("sensor.abfall_restmuell", "Restmüll"),
        EntityConfig("sensor.abfall_bioabfall", "Bioabfall"),
        EntityConfig("sensor.abfall_altpapier", "Altpapier"),
        EntityConfig("sensor.abfall_gelber_sack", "Gelber Sack"),
    ),
}


def all_entity_ids(
    groups: dict[str, tuple[EntityConfig, ...]] = DEFAULT_ENTITY_GROUPS,
) -> list[str]:
    """Flat list of every entity_id across all groups."""
    return [ec.entity_id for group_entities in groups.values() for ec in group_entities]


def find_entity_config(
    entity_id: str,
    groups: dict[str, tuple[EntityConfig, ...]] = DEFAULT_ENTITY_GROUPS,
) -> tuple[str, EntityConfig] | None:
    """Finds the group name and config for an entity_id, or None."""
    for group_name, group_entities in groups.items():
        for ec in group_entities:
            if ec.entity_id == entity_id:
                return group_name, ec
    return None


def entity_groups_as_list(
    groups: dict[str, tuple[EntityConfig, ...]],
) -> list[dict[str, Any]]:
    """Flattens entity groups into the list-of-dicts shape the options flow stores.

    Inverse of build_entity_groups().
    """
    return [
        {
            "entity_id": ec.entity_id,
            "label": ec.label,
            "group": group_name,
            "unit": ec.unit,
            "type": ec.type,
            "min_value": ec.min_value,
            "max_value": ec.max_value,
        }
        for group_name, group_entities in groups.items()
        for ec in group_entities
    ]


def build_entity_groups(
    entity_dicts: Iterable[dict[str, Any]] | None,
) -> dict[str, tuple[EntityConfig, ...]]:
    """Builds entity groups from the options flow's stored entity list.

    Falls back to DEFAULT_ENTITY_GROUPS when nothing has been configured
    yet (e.g. a freshly created config entry before the options flow was
    opened once). Inverse of entity_groups_as_list().
    """
    if not entity_dicts:
        return DEFAULT_ENTITY_GROUPS

    groups: dict[str, list[EntityConfig]] = {}
    for item in entity_dicts:
        groups.setdefault(item["group"], []).append(
            EntityConfig(
                entity_id=item["entity_id"],
                label=item["label"],
                unit=item.get("unit") or None,
                type=item.get("type") or None,
                min_value=item.get("min_value"),
                max_value=item.get("max_value"),
            )
        )
    return {group_name: tuple(cfgs) for group_name, cfgs in groups.items()}
