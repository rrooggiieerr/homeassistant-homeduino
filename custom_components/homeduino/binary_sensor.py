"""
Created on 12 Jan 2023

@author: Rogier van Staveren
"""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homeduino binary sensors."""
    entry_type = config_entry.data.get(CONF_ENTRY_TYPE)

    entities = []

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        coordinator: HomeduinoCoordinator = hass.data[DOMAIN][config_entry.entry_id]

        for binary_sensor in coordinator.binary_sensors:
            entities.append(
                HomeduinoTransceiverBinarySensor(coordinator, binary_sensor.get("pin"))
            )
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE and config_entry.data.get(
        CONF_RF_PROTOCOL
    ).startswith("pir"):
        coordinator = HomeduinoCoordinator.instance(hass)

        protocol = config_entry.data.get(CONF_RF_PROTOCOL)
        id = config_entry.data.get(CONF_RF_ID)
        unit = config_entry.data.get(CONF_RF_UNIT)

        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{protocol}-{id}")},
            name=config_entry.title,
            via_device=(DOMAIN, coordinator.serial_port),
        )

        entity_description = BinarySensorEntityDescription(
            key=(protocol, id, unit),
            name=f"Switch {unit}",
            device_class=BinarySensorDeviceClass.MOTION,
        )

        entities.append(
            HomeduinoRFBinarySensor(coordinator, device_info, entity_description)
        )

    async_add_entities(entities)


class HomeduinoTransceiverBinarySensor(CoordinatorEntity, BinarySensorEntity):
    entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_available = False

    _attr_is_on = None

    def __init__(self, coordinator: HomeduinoCoordinator, digital_pin: int):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.serial_port}-digital{digital_pin}"

        self._attr_name = f"Binary {digital_pin}"

        self._digital_pin = digital_pin


class HomeduinoRFBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    _attr_available = False

    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entity_description.key)

        self.protocol = entity_description.key[0]
        self.id = entity_description.key[1]
        self.unit = entity_description.key[2]

        self._attr_device_info = device_info

        self._attr_unique_id = f"{DOMAIN}-{self.protocol}-{self.id}-{self.unit}"

        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # if (last_state := await self.async_get_last_state()) is not None:
        #     self._attr_is_on = last_state.state == STATE_ON

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

            self._attr_is_on = self.coordinator.data.get("values", {}).get("state")

        self.async_write_ha_state()
