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

from . import HomeduinoCoordinator
from .const import (
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_RF_DEVICE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
    CONF_RF_ID,
    CONF_RF_ID_IGNORE_ALL,
    CONF_RF_PROTOCOL,
    CONF_RF_SWITCH_AS_BUTTON,
    CONF_RF_UNIT,
    CONF_RF_UNIT_EXTRAPOLATE,
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

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        coordinator: HomeduinoCoordinator = hass.data[DOMAIN][config_entry.entry_id]

        # for binary_sensor in coordinator.binary_sensors:
        #     entities.append(HomeduinoTransceiverSwitch(coordinator, binary_sensor.get('pin')))
    elif (
        entry_type == CONF_ENTRY_TYPE_RF_DEVICE
        and config_entry.data.get(CONF_RF_PROTOCOL).startswith("switch")
        and not config_entry.options.get(CONF_RF_SWITCH_AS_BUTTON, False)
    ):
        coordinator = HomeduinoCoordinator.instance(hass)

        protocol = config_entry.data.get(CONF_RF_PROTOCOL)
        id = config_entry.data.get(CONF_RF_ID)
        unit = config_entry.data.get(CONF_RF_UNIT)
        id_ignore_all = config_entry.options.get(CONF_RF_ID_IGNORE_ALL)

        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{protocol}-{id}")},
            name=config_entry.title,
            via_device=(DOMAIN, coordinator.serial_port),
        )

        if config_entry.options.get(CONF_RF_UNIT_EXTRAPOLATE):
            for i in range(unit + 1):
                entity_description = SwitchEntityDescription(
                    key=(protocol, id, i),
                    name=f"Switch {i}",
                    device_class=SwitchDeviceClass.SWITCH,
                )
                entities.append(
                    HomeduinoRFSwitch(
                        coordinator, device_info, entity_description, id_ignore_all
                    )
                )
            if id_ignore_all:
                entity_description = SwitchEntityDescription(
                    key=(protocol, id, unit + 1), name=f"Switch {unit + 1}"
                )
                entities.append(
                    HomeduinoRFSwitchAll(coordinator, device_info, entity_description)
                )
        else:
            entity_description = SwitchEntityDescription(
                key=(protocol, id, unit), name=f"Switch {unit}"
            )
            entities.append(
                HomeduinoRFSwitch(
                    coordinator, device_info, entity_description, id_ignore_all
                )
            )

    async_add_entities(entities)


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
            self.protocol, {"id": self.id, "unit": self.unit, "state": True}
        ):
            self._attr_is_on = True
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to switch on %s", self.name)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        _LOGGER.debug("Turning off %s", self.name)
        if await self.coordinator.rf_send(
            self.protocol, {"id": self.id, "unit": self.unit, "state": False}
        ):
            self._attr_is_on = False
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to switch off %s", self.name)


class HomeduinoRFSwitchAll(HomeduinoRFSwitch):
    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_info, entity_description, True)

        self._attr_unique_id = f"{DOMAIN}-{self.protocol}-{self.id}-all"

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

            if self.coordinator.data.get("values", {}).get("all", False) is not True:
                return

            _LOGGER.debug(self.coordinator.data)

            self._attr_is_on = self.coordinator.data.get("values", {}).get("state")

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        _LOGGER.debug("Turning on %s", self.name)
        if await self.coordinator.rf_send(
            self.protocol,
            {"id": self.id, "unit": 0, "state": True, "all": True},
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
            {"id": self.id, "unit": 0, "state": False, "all": True},
        ):
            self._attr_is_on = False
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to switch off %s", self.name)
