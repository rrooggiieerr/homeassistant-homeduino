# pylint: disable=R0801
from __future__ import annotations

import logging

from homeassistant.components.number import (
    NumberEntityDescription,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeduino import Homeduino, HomeduinoPinMode

from . import HomeduinoCoordinator
from .const import (
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
    CONF_IO_DIGITAL_,
    CONF_IO_PWM_OUTPUT,
    CONF_SERIAL_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Homeduino number."""
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
            _LOGGER.debug("key: %s, value: %s", key, value)
            if value == CONF_IO_PWM_OUTPUT:
                entity_description = HomeduinoTransceiverNumberEntityDescription(
                    key=config_entry.entry_id,
                    translation_key=CONF_IO_PWM_OUTPUT,
                    translation_placeholders={"digital_io": digital_io},
                    native_min_value=0,
                    native_max_value=255,
                    native_step=1,
                    digital_io=digital_io,
                )
                entities.append(
                    HomeduinoTransceiverNumber(
                        coordinator, device_info, entity_description
                    )
                )

    async_add_entities(entities)


class HomeduinoTransceiverNumberEntityDescription(
    NumberEntityDescription, frozen_or_thawed=True
):
    digital_io: int


class HomeduinoTransceiverNumber(CoordinatorEntity, RestoreNumber):
    _attr_has_entity_name = True
    _attr_available = False

    _homeduino: Homeduino = None

    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: HomeduinoTransceiverNumberEntityDescription,
    ) -> None:
        """Initialize the switch."""
        # Pass coordinator to CoordinatorEntity.
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = device_info

        self._attr_unique_id = f"{entity_description.key}-{CONF_IO_PWM_OUTPUT}-{entity_description.digital_io}"

        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        self._homeduino = self.coordinator.get_transceiver(self.device_entry.id)

        if self._homeduino.connected():
            self._attr_available = True

            await self._homeduino.pin_mode(
                self.entity_description.digital_io, HomeduinoPinMode.OUTPUT
            )

            if (last_state := await self.async_get_last_state()) is not None:
                last_number_data = await self.async_get_last_number_data()
                native_value = last_number_data.native_value or 0
                if await self._homeduino.analog_write(
                    self.entity_description.digital_io, int(native_value)
                ):
                    self._attr_native_value = native_value

        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if await self._homeduino.analog_write(
            self.entity_description.digital_io, int(value)
        ):
            self._attr_native_value = value

        self.async_write_ha_state()
