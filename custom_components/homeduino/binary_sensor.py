"""
Created on 12 Jan 2023

@author: Rogier van Staveren
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomeduinoCoordinator
from .const import (
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_RF_DEVICE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
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
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE:
        pass

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
