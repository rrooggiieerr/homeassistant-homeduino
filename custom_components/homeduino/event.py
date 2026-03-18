from __future__ import annotations

import logging

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomeduinoCoordinator
from .const import (
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_RF_DEVICE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
    CONF_RF_ID,
    CONF_RF_PROTOCOL,
    CONF_RF_UNIT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Homeduino events."""
    entry_type = config_entry.data.get(CONF_ENTRY_TYPE)

    entities = []

    coordinator = HomeduinoCoordinator.instance(hass)

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        pass
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE and config_entry.data.get(
        CONF_RF_PROTOCOL
    ).startswith(("doorbell")):
        protocol = config_entry.data.get(CONF_RF_PROTOCOL)
        id = int(config_entry.data.get(CONF_RF_ID))
        unit = config_entry.data.get(CONF_RF_UNIT)
        if unit is not None:
            unit = int(unit)

        identifier = f"{protocol}-{id}"
        if unit is not None:
            identifier += f"-{unit}"

        device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=config_entry.title,
        )

        entity_description = EventEntityDescription(
            key=(protocol, id, unit),
            translation_key="rf_doorbell",
            translation_placeholders={"unit": unit},
            device_class=EventDeviceClass.DOORBELL,
        )

        entities.append(HomeduinoRFEvent(coordinator, device_info, entity_description))

    async_add_entities(entities)


class HomeduinoRFEvent(CoordinatorEntity, EventEntity):
    _attr_event_types = ["single_press"]

    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: EventEntityDescription,
    ) -> None:
        """Initialize the event."""
        super().__init__(coordinator, entity_description.key)

        self.protocol = entity_description.key[0]
        self.id = entity_description.key[1]
        self.unit = entity_description.key[2]

        self._attr_device_info = device_info

        self._attr_unique_id = f"{DOMAIN}-{self.protocol}-{self.id}-{self.unit}"

        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        """Register callbacks with your device API/library."""
        # my_device_api.listen(self._async_handle_event)
        await super().async_added_to_hass()

        if self.coordinator.connected():
            self._attr_available = True

        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.connected():
            self._attr_available = False
        else:
            self._attr_available = True
            self.async_write_ha_state()

            if not self.coordinator.data:
                return

            if self.coordinator.data.get("protocol") != self.protocol:
                return

            if self.coordinator.data.get("values", {}).get("id") != self.id:
                return

            if self.coordinator.data.get("values", {}).get("unit") != self.unit:
                return

            _LOGGER.debug(self.coordinator.data)

            self._trigger_event("single_press")

        self.async_write_ha_state()
