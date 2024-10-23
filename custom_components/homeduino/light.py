# pylint: disable=R0801
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeduino import DEFAULT_REPEATS

from . import HomeduinoCoordinator
from .const import (
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_RF_DEVICE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
    CONF_RF_ID,
    CONF_RF_ID_IGNORE_ALL,
    CONF_RF_PROTOCOL,
    CONF_RF_REPEATS,
    CONF_RF_UNIT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Homeduino light."""
    entry_type = config_entry.data.get(CONF_ENTRY_TYPE)

    entities = []

    coordinator = HomeduinoCoordinator.instance(hass)

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        # for binary_sensor in coordinator.binary_sensors:
        #     entities.append(HomeduinoTransceiverPWMDimmer(coordinator, binary_sensor.get('pin')))

        pass
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE and config_entry.data.get(
        CONF_RF_PROTOCOL
    ).startswith("dimmer"):

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

        entity_description = LightEntityDescription(
            key=(protocol, id, unit),
            translation_key="rf_light",
            translation_placeholders={"unit": unit},
        )

        if config_entry.data.get(CONF_RF_PROTOCOL) == "dimmer1":
            entities.append(
                HomeduinoRFDimmer1(
                    coordinator, device_info, entity_description, id_ignore_all, repeats
                )
            )
        else:
            entities.append(
                HomeduinoRFDimmer(
                    coordinator, device_info, entity_description, id_ignore_all, repeats
                )
            )

    async_add_entities(entities)


class HomeduinoRFDimmer(CoordinatorEntity, LightEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_available = False

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    _attr_is_on = None
    _attr_brightness = None
    _off_brightness = None

    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: LightEntityDescription,
        ignore_all: bool = False,
        repeats: int = DEFAULT_REPEATS,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entity_description.key)

        self.protocol = entity_description.key[0]
        self.protocols = [entity_description.key[0]]
        self.id = entity_description.key[1]
        self.unit = entity_description.key[2]

        self._attr_device_info = device_info

        self._attr_unique_id = f"{DOMAIN}-{self.protocol}-{self.id}-{self.unit}"

        self.entity_description = entity_description
        self.ignore_all = ignore_all
        self.repeats = repeats

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return state attributes."""
        return {
            "off_brightness": self._off_brightness,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == STATE_ON
            self._attr_brightness = last_state.attributes.get(ATTR_BRIGHTNESS, 255)
            self._off_brightness = last_state.attributes.get("off_brightness")

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

            if self.coordinator.data.get("protocol") not in self.protocols:
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

            new_brightness = self.coordinator.data.get("values", {}).get("dimlevel")
            if new_brightness:
                self._attr_brightness = new_brightness * 17

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        _LOGGER.debug("Turning on %s", self.name)
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        state = None
        if not brightness:
            brightness = self._attr_brightness
            state = True

        if not brightness:
            brightness = self._off_brightness
            state = True

        if not brightness:
            brightness = 255

        brightness = int(brightness / 17)

        if await self.coordinator.rf_send(
            self.protocol,
            {"id": self.id, "unit": self.unit, "state": state, "dimlevel": brightness},
            self.repeats,
        ):
            self._attr_is_on = True
            self._attr_brightness = brightness * 17
            self._off_brightness = None
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to switch on %s", self.name)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        _LOGGER.debug("Turning off %s", self.name)
        if await self.coordinator.rf_send(
            self.protocol,
            {"id": self.id, "unit": self.unit, "state": False, "dimlevel": 0},
            self.repeats,
        ):
            self._attr_is_on = False

            # Store current brightness so that the next turn_on uses it
            # when using "enhanced turn on".
            self._off_brightness = self._attr_brightness

            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to switch off %s", self.name)


class HomeduinoRFDimmer1(HomeduinoRFDimmer):
    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: LightEntityDescription,
        ignore_all: bool = False,
        repeats: int = DEFAULT_REPEATS,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            coordinator, device_info, entity_description, ignore_all, repeats
        )

        self.protocols.append("switch1")
