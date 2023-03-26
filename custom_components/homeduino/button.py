from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
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
    CONF_RF_DEVICE_NAME,
    CONF_RF_ID,
    CONF_RF_ID_IGNORE_ALL,
    CONF_RF_PROTOCOL,
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
    """Set up the Homeduino button."""
    entry_type = config_entry.data.get(CONF_ENTRY_TYPE)

    entities = []

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        coordinator: HomeduinoCoordinator = hass.data[DOMAIN][config_entry.entry_id]

        # for binary_sensor in coordinator.binary_sensors:
        #     entities.append(HomeduinoTransceiverButton(coordinator, binary_sensor.get('pin')))
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE and config_entry.data.get(
        CONF_RF_PROTOCOL
    ).startswith("button"):
        device_name = config_entry.data.get(CONF_RF_DEVICE_NAME)
        protocol = config_entry.data.get(CONF_RF_PROTOCOL)
        id = config_entry.data.get(CONF_RF_ID)
        unit = config_entry.data.get(CONF_RF_UNIT)
        id_ignore_all = config_entry.options.get(CONF_RF_ID_IGNORE_ALL)
        if config_entry.options.get(CONF_RF_UNIT_EXTRAPOLATE):
            for i in range(unit + 1):
                entities.append(
                    HomeduinoRFButton(
                        device_name, protocol, id, i, True, id_ignore_all
                    )
                )
                entities.append(
                    HomeduinoRFButton(
                        device_name, protocol, id, i, False, id_ignore_all
                    )
                )
            if id_ignore_all:
                entities.append(HomeduinoRFButtonAll(device_name, protocol, id, unit + 1, True))
                entities.append(HomeduinoRFButtonAll(device_name, protocol, id, unit + 1, False))
        else:
            entities.append(
                HomeduinoRFButton(
                    device_name, protocol, id, unit, True, id_ignore_all
                )
            )
            entities.append(
                HomeduinoRFButton(
                    device_name, protocol, id, unit, False, id_ignore_all
                )
            )

    async_add_entities(entities)


class HomeduinoRFButton(CoordinatorEntity, ButtonEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_assumed_state = True

    _attr_available = False
    _attr_is_on = None

    def __init__(
        self,
        device_name: str,
        protocol: str,
        id: int,
        unit: int,
        state: bool,
        ignore_all: bool = False,
    ) -> None:
        """Initialize the button."""
        super().__init__(HomeduinoCoordinator.instance())

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{protocol}-{id}")},
            name=device_name,
            via_device=(DOMAIN, self.coordinator.serial_port),
        )

        self._attr_unique_id = f"{DOMAIN}-{protocol}-{id}-{unit}-{state}"

        self._attr_name = f"Button {unit} {state}"
        self.protocol = protocol.replace("button", "switch")
        self.id = id
        self.unit = unit
        self._unit_state = state
        self.ignore_all = ignore_all

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _LOGGER.debug("async_added_to_hass")
        
        if self.coordinator.has_transceiver():
            self._attr_available = True
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.has_transceiver() and not self._attr_available:
            self._attr_available = True
            self.async_write_ha_state()
        elif not self.coordinator.has_transceiver() and self._attr_available:
            self._attr_available = False
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self._attr_available:
            return self._attr_available

        return self.coordinator.last_update_success

    async def async_press(self, **kwargs) -> None:
        """Turn the entity on."""
        _LOGGER.debug("Switching %s", self._attr_name)
        await self.coordinator.rf_send(
            self.protocol, {"id": self.id, "unit": self.unit, "state": self._unit_state}
        )


class HomeduinoRFButtonAll(HomeduinoRFButton):
    def __init__(
        self,
        device_name: str,
        protocol: str,
        id: int,
        unit: int,
        state: bool
    ) -> None:
        """Initialize the button."""
        super().__init__(device_name, protocol, id, unit, state, True)

        self._attr_unique_id = f"{DOMAIN}-{protocol}-{id}-all-{state}"

    async def async_press(self, **kwargs) -> None:
        """Turn the entity on."""
        _LOGGER.debug("Switching %s", self._attr_name)
        await self.coordinator.rf_send(
            self.protocol, {"id": self.id, "unit": 0, "state": self._unit_state, "all": True},
        )
