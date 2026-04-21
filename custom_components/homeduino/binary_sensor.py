# pylint: disable=R0801
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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomeduinoCoordinator
from .const import (
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_RF_DEVICE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Homeduino binary sensors."""
    entry_type = config_entry.data.get(CONF_ENTRY_TYPE)

    entities = []

    coordinator = HomeduinoCoordinator.instance(hass)

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.data.get(CONF_SERIAL_PORT))},
            manufacturer="pimatic",
            name=config_entry.title,
        )

        for digital_io in range(2, 14):
            key = CONF_IO_DIGITAL_ + str(digital_io)
            value = config_entry.options.get(key)
            if value == CONF_IO_DIGITAL_INPUT:
                entity_description = HomeduinoTransceiverBinarySensorEntityDescription(
                    key=config_entry.entry_id,
                    translation_key=CONF_IO_DIGITAL_INPUT,
                    translation_placeholders={"digital_io": digital_io},
                    digital_io=digital_io,
                )
                entities.append(
                    HomeduinoTransceiverBinarySensor(
                        coordinator, device_info, entity_description
                    )
                )
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE:
        protocol = config_entry.data.get(CONF_RF_PROTOCOL)
        if protocol.startswith(("contact", "pir")):
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

            # Determine device_class based on protocol
            device_class = None
            if protocol.startswith("contact"):
                device_class = BinarySensorDeviceClass.DOOR
            elif protocol.startswith("pir"):
                device_class = BinarySensorDeviceClass.MOTION

            entity_description = HomeduinoRFBinarySensorEntityDescription(
                key=protocol,
                device_class=device_class,
                id=id,
                unit=unit,
            )

            entities.append(
                HomeduinoRFBinarySensor(coordinator, device_info, entity_description)
            )

        if protocol in ["contact4", "weather4", "weather5", "weather7", "weather13"]:
            entity_description = HomeduinoRFBinarySensorEntityDescription(
                key=protocol,
                device_class=BinarySensorDeviceClass.BATTERY,
                id=id,
                unit=unit,
                field="lowBattery",
            )

            entities.append(
                HomeduinoRFBinarySensor(coordinator, device_info, entity_description)
            )

    async_add_entities(entities)


class HomeduinoTransceiverBinarySensorEntityDescription(
    BinarySensorEntityDescription, frozen_or_thawed=True
):
    digital_io: int


class HomeduinoRFBinarySensorEntityDescription(
    BinarySensorEntityDescription, frozen_or_thawed=True
):
    id: int
    unit: int | None
    field: str | None = None


class HomeduinoTransceiverBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_available = False

    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: HomeduinoTransceiverBinarySensorEntityDescription,
    ):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = device_info

        self._attr_unique_id = f"{entity_description.key}-{CONF_IO_DIGITAL_INPUT}-{entity_description.digital_io}"

        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        homeduino = self.coordinator.get_transceiver(self.device_entry.id)
        await homeduino.add_digital_read_callback(
            self.entity_description.digital_io, self._handle_digital_read_update
        )

        if homeduino.connected():
            self._attr_available = True

        self.async_write_ha_state()

    @callback
    def _handle_digital_read_update(self, value) -> None:
        self._attr_is_on = value
        self.async_write_ha_state()


class HomeduinoRFBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    _attr_available = False

    fiel = None

    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: HomeduinoRFBinarySensorEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = device_info

        unique_id = f"{DOMAIN}-{entity_description.protocol}-{entity_description.id}"
        if entity_description.unit is not None:
            unique_id += f"-{entity_description.unit}"
        if entity_description.field:
            unique_id += f"-{entity_description.field}"
        self._attr_unique_id = unique_id

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

            if self.coordinator.data.get("protocol") != self.entity_description.key:
                return

            if (
                self.coordinator.data.get("values", {}).get("id")
                != self.entity_description.id
            ):
                return

            if (
                self.coordinator.data.get("values", {}).get("unit")
                != self.entity_description.unit
            ):
                return

            _LOGGER.debug(self.coordinator.data)

            self._attr_is_on = self.coordinator.data.get("values", {}).get(
                self.entity_description.field
                if self.entity_description.field
                else "state"
            )

        self.async_write_ha_state()
