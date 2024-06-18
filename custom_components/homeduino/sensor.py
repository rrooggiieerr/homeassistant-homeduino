from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
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
    """Set up the Homeduino sensors."""
    entry_type = config_entry.data.get(CONF_ENTRY_TYPE)

    entities = []

    coordinator = HomeduinoCoordinator.instance(hass)

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        for analog_sensor in coordinator.analog_sensors:
            entities.append(
                HomeduinoTransceiverAnalogSensor(coordinator, analog_sensor.get("pin"))
            )

        if coordinator.dht_sensor:
            entities.append(HomeduinoTransceiverDHTTemperatureSensor(coordinator))
            entities.append(HomeduinoTransceiverDHTHumiditySensor(coordinator))
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE:
        entities.append(HomeduinoRFSensor(coordinator))

    async_add_entities(entities)


class HomeduinoTransceiverSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_available = False
    _attr_native_value = None

    def __init__(self, coordinator: HomeduinoCoordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self._attr_device_info = coordinator.device_info


class HomeduinoTransceiverAnalogSensor(HomeduinoTransceiverSensor):
    def __init__(self, coordinator: HomeduinoCoordinator, analog_pin: int):
        """Pass coordinator to HomeduinoTransceiverSensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.serial_port}-analog{analog_pin}"

        self._attr_name = f"Analog {analog_pin}"

        self._analog_pin = analog_pin


class HomeduinoTransceiverDHTTemperatureSensor(HomeduinoTransceiverSensor):
    def __init__(self, coordinator: HomeduinoCoordinator):
        """Pass coordinator to HomeduinoTransceiverSensor."""
        super().__init__(coordinator)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.serial_port}-dhttemperature"

        self._attr_name = "Temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS


class HomeduinoTransceiverDHTHumiditySensor(HomeduinoTransceiverSensor):
    def __init__(self, coordinator: HomeduinoCoordinator):
        """Pass coordinator to HomeduinoTransceiverSensor."""
        super().__init__(coordinator)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.serial_port}-dhthumidity"

        self._attr_name = "Humidity"
        self._attr_device_class = SensorDeviceClass.HUMIDITY
        self._attr_native_unit_of_measurement = PERCENTAGE


class HomeduinoRFSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: HomeduinoCoordinator):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.serial_port}-rf"
