# pylint: disable=R0801
from __future__ import annotations

import logging

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeduino import DEFAULT_REPEATS, Homeduino, HomeduinoPinMode

from . import HomeduinoCoordinator
from .const import (
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_RF_DEVICE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
    CONF_IO_DIGITAL_,
    CONF_IO_DIGITAL_OUTPUT,
    CONF_RF_ID,
    CONF_RF_ID_IGNORE_ALL,
    CONF_RF_PROTOCOL,
    CONF_RF_REPEATS,
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
    """Set up the Homeduino switch."""
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
            if value == CONF_IO_DIGITAL_OUTPUT:
                entity_description = SwitchEntityDescription(
                    key=(config_entry.entry_id, digital_io),
                    translation_key=CONF_IO_DIGITAL_OUTPUT,
                    translation_placeholders={"digital_io": digital_io},
                )
                entities.append(
                    HomeduinoTransceiverSwitch(
                        coordinator, device_info, entity_description
                    )
                )
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE and config_entry.data.get(
        CONF_RF_PROTOCOL
    ).startswith("switch"):
        protocol = config_entry.data.get(CONF_RF_PROTOCOL)
        id = int(config_entry.data.get(CONF_RF_ID))
        unit = config_entry.data.get(CONF_RF_UNIT)
        if unit is not None:
            unit = int(unit)
        id_ignore_all = config_entry.options.get(CONF_RF_ID_IGNORE_ALL)
        repeats = config_entry.options.get(CONF_RF_REPEATS, DEFAULT_REPEATS)

        identifier = f"{protocol}-{id}"
        if unit is not None:
            identifier += f"-{unit}"

        device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=config_entry.title,
        )

        entity_description = SwitchEntityDescription(
            key=(protocol, id, unit),
            translation_key="rf_switch",
            translation_placeholders={"unit": unit},
        )
        entities.append(
            HomeduinoRFSwitch(
                coordinator, device_info, entity_description, id_ignore_all, repeats
            )
        )

    async_add_entities(entities)


class HomeduinoTransceiverSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_available = False
    _attr_is_on = None

    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        # Pass coordinator to CoordinatorEntity.
        super().__init__(coordinator, entity_description.key)

        config_entry_id = entity_description.key[0]
        self._digital_io = entity_description.key[1]

        self._attr_device_info = device_info

        self._attr_unique_id = (
            f"{config_entry_id}-{CONF_IO_DIGITAL_OUTPUT}-{self._digital_io}"
        )

        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        self.homeduino = self.coordinator.get_transceiver(self.device_entry.id)

        if self.homeduino.connected():
            self._attr_available = True

            await self.homeduino.pin_mode(self._digital_io, HomeduinoPinMode.OUTPUT)

            if (last_state := await self.async_get_last_state()) is not None:
                is_on = last_state.state == STATE_ON
                if await self.homeduino.digital_write(self._digital_io, is_on):
                    self._attr_is_on = is_on

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        _LOGGER.debug("Turning on %s", self.name)
        if await self.homeduino.digital_write(self._digital_io, True):
            self._attr_is_on = True
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to switch on %s", self.name)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        _LOGGER.debug("Turning off %s", self.name)
        if await self.homeduino.digital_write(self._digital_io, False):
            self._attr_is_on = False
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to switch off %s", self.name)


class HomeduinoRFSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True

    _attr_available = False
    _attr_is_on = None

    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: SwitchEntityDescription,
        ignore_all: bool = False,
        repeats: int = DEFAULT_REPEATS,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entity_description.key)

        self.protocol = entity_description.key[0]
        self.id = entity_description.key[1]
        self.unit = entity_description.key[2]

        self._attr_device_info = device_info

        self._attr_unique_id = f"{DOMAIN}-{self.protocol}-{self.id}-{self.unit}"

        self.entity_description = entity_description
        self.ignore_all = ignore_all
        self.repeats = repeats

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == STATE_ON

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

            if self.coordinator.data.get("values", {}).get("id") != self.id:
                return

            if (
                self.coordinator.data.get("values", {}).get("unit") != self.unit
                and self.coordinator.data.get("values", {}).get("all", False) is False
            ):
                return

            if (
                self.coordinator.data.get("values", {}).get("all", False) is True
                and self.ignore_all
            ):
                return

            _LOGGER.debug(self.coordinator.data)

            self._attr_is_on = self.coordinator.data.get("values", {}).get("state")

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        _LOGGER.debug("Turning on %s", self.name)
        if await self.coordinator.rf_send(
            self.protocol,
            {"id": self.id, "unit": self.unit, "state": True},
            self.repeats,
        ):
            self._attr_is_on = True
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to switch on %s", self.name)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        _LOGGER.debug("Turning off %s", self.name)
        if await self.coordinator.rf_send(
            self.protocol,
            {"id": self.id, "unit": self.unit, "state": False},
            self.repeats,
        ):
            self._attr_is_on = False
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to switch off %s", self.name)
