# pylint: disable=R0801
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomeduinoCoordinator
from .const import (
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_RF_DEVICE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
    CONF_IO_ANALOG_,
    CONF_IO_DHT11,
    CONF_IO_DHT22,
    CONF_IO_DIGITAL_,
    CONF_IO_DIGITAL_INPUT,
    CONF_RF_ID,
    CONF_RF_PROTOCOL,
    CONF_RF_UNIT,
    CONF_SERIAL_PORT,
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
        device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.data.get(CONF_SERIAL_PORT))},
            manufacturer="pimatic",
            name=config_entry.title,
        )

        for analog_input in range(0, 8):
            key = CONF_IO_ANALOG_ + str(analog_input)
            value = config_entry.options.get(key, False)
            if value:
                entity_description = SensorEntityDescription(
                    key=(config_entry.entry_id, analog_input),
                    translation_key="analog_input",
                    translation_placeholders={"analog_input": analog_input},
                )
                entities.append(
                    HomeduinoTransceiverAnalogSensor(
                        coordinator, device_info, entity_description
                    )
                )

        for digital_io in range(2, 15):
            key = CONF_IO_DIGITAL_ + str(digital_io)
            value = config_entry.options.get(key)
            if value in [CONF_IO_DHT11, CONF_IO_DHT22]:
                dht_type = int(value[3:5])
                entity_description = SensorEntityDescription(
                    key=(config_entry.entry_id, digital_io, dht_type),
                    translation_key=f"{value}_temperature",
                    translation_placeholders={"digital_io": digital_io},
                    device_class=SensorDeviceClass.TEMPERATURE,
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                )
                entities.append(
                    HomeduinoTransceiverDHTTemperatureSensor(
                        coordinator, device_info, entity_description
                    )
                )

                entity_description = SensorEntityDescription(
                    key=(config_entry.entry_id, digital_io),
                    translation_key=f"{value}_humidity",
                    translation_placeholders={"digital_io": digital_io},
                    device_class=SensorDeviceClass.HUMIDITY,
                    native_unit_of_measurement=PERCENTAGE,
                )
                entities.append(
                    HomeduinoTransceiverDHTHumiditySensor(
                        coordinator, device_info, entity_description
                    )
                )
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE and config_entry.data.get(
        CONF_RF_PROTOCOL
    ).startswith("weather"):
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

        if protocol in ("weather4", "weather7", "weather19"):
            entity_description = SensorEntityDescription(
                key=(protocol, id, unit, "temperature"),
                translation_key="temperature",
                translation_placeholders={"unit": unit},
                device_class=SensorDeviceClass.TEMPERATURE,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            )

            entities.append(
                HomeduinoRFSensor(coordinator, device_info, entity_description)
            )

        if protocol in ("weather4", "weather7"):
            entity_description = SensorEntityDescription(
                key=(protocol, id, unit, "humidity"),
                translation_key="humidity",
                translation_placeholders={"unit": unit},
                device_class=SensorDeviceClass.HUMIDITY,
                native_unit_of_measurement=PERCENTAGE,
            )

            entities.append(
                HomeduinoRFSensor(coordinator, device_info, entity_description)
            )

    async_add_entities(entities)


class HomeduinoTransceiverSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_available = False
    _attr_native_value = None

    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: SensorEntityDescription,
    ):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = device_info

        self.entity_description = entity_description


class HomeduinoTransceiverAnalogSensor(HomeduinoTransceiverSensor):
    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: SensorEntityDescription,
    ):
        """Pass coordinator to HomeduinoTransceiverSensor."""
        super().__init__(coordinator, device_info, entity_description)

        self._config_entry_id = entity_description.key[0]
        self._analog_input = entity_description.key[1]
        self._attr_unique_id = (
            f"{self._config_entry_id}-analog_input-{self._analog_input}"
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        homeduino = self.coordinator.get_transceiver(self._config_entry_id)
        homeduino.add_analog_read_callback(
            self._analog_input, self._handle_analog_read_update
        )

        if homeduino.connected():
            self._attr_available = True

        self.async_write_ha_state()

    @callback
    def _handle_analog_read_update(self, value) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()


class HomeduinoTransceiverDHTTemperatureSensor(HomeduinoTransceiverSensor):
    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: SensorEntityDescription,
    ):
        """Pass coordinator to HomeduinoTransceiverSensor."""
        super().__init__(coordinator, device_info, entity_description)

        self._config_entry_id = entity_description.key[0]
        self._digital_io = entity_description.key[1]
        self._dht_type = entity_description.key[1]
        self._attr_unique_id = f"{self._config_entry_id}-{CONF_IO_DIGITAL_INPUT}-{self._digital_io}-dhttemperature"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        homeduino = self.coordinator.get_transceiver(self._config_entry_id)
        await homeduino.add_dht_read_callback(
            self._dht_type, self._digital_io, self._handle_dht_read_update
        )

        if homeduino.connected():
            self._attr_available = True

        self.async_write_ha_state()

    @callback
    def _handle_dht_read_update(self, temperature, _) -> None:
        self._attr_native_value = temperature
        self.async_write_ha_state()


class HomeduinoTransceiverDHTHumiditySensor(HomeduinoTransceiverSensor):
    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: SensorEntityDescription,
    ):
        """Pass coordinator to HomeduinoTransceiverSensor."""
        super().__init__(coordinator, device_info, entity_description)

        self._config_entry_id = entity_description.key[0]
        self._digital_io = entity_description.key[1]
        self._dht_type = entity_description.key[1]
        self._attr_unique_id = f"{self._config_entry_id}-{CONF_IO_DIGITAL_INPUT}-{self._digital_io}-dhthumidity"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        homeduino = self.coordinator.get_transceiver(self._config_entry_id)
        await homeduino.add_dht_read_callback(
            self._dht_type, self._digital_io, self._handle_dht_read_update
        )

        if homeduino.connected():
            self._attr_available = True

        self.async_write_ha_state()

    @callback
    def _handle_dht_read_update(self, _, humidity) -> None:
        self._attr_native_value = humidity
        self.async_write_ha_state()


class HomeduinoRFSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: SensorEntityDescription,
    ):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, entity_description.key)

        self.protocol = entity_description.key[0]
        self.id = entity_description.key[1]
        self.unit = entity_description.key[2]
        self.field = entity_description.key[3]

        self._attr_device_info = device_info

        self._attr_unique_id = f"{self.protocol}-{self.id}-{self.unit}-{self.field}"

        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # ToDo

        if self.coordinator.connected():
            self._attr_available = True

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self._attr_available:
            return self._attr_available

        return self.coordinator.last_update_success

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

            values = self.coordinator.data.get("values", {})
            if values.get("id") != self.id:
                return

            if values.get("unit") != self.unit:
                return

            _LOGGER.debug(self.coordinator.data)
            try:
                self._attr_native_value = values.get(self.field)
                self._attr_available = True
            except ValueError as ex:
                _LOGGER.error(ex)
                self._attr_available = False

        self.async_write_ha_state()
