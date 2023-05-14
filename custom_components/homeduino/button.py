from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
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
    """Set up the Homeduino button."""
    entry_type = config_entry.data.get(CONF_ENTRY_TYPE)

    entities = []

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        coordinator: HomeduinoCoordinator = hass.data[DOMAIN][config_entry.entry_id]

        # for binary_sensor in coordinator.binary_sensors:
        #     entities.append(HomeduinoTransceiverButton(coordinator, binary_sensor.get('pin')))
    elif (
        entry_type == CONF_ENTRY_TYPE_RF_DEVICE
        and config_entry.data.get(CONF_RF_PROTOCOL).startswith("switch")
        and config_entry.options.get(CONF_RF_SWITCH_AS_BUTTON, False)
    ):
        coordinator = HomeduinoCoordinator.instance()

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
                entity_description = ButtonEntityDescription(
                    key=(protocol, id, i), name=f"Button {i} On"
                )
                entities.append(
                    HomeduinoRFButton(
                        coordinator,
                        device_info,
                        entity_description,
                        True,
                        id_ignore_all,
                    )
                )
                entity_description = ButtonEntityDescription(
                    key=(protocol, id, i), name=f"Button {i} Off"
                )
                entities.append(
                    HomeduinoRFButton(
                        coordinator,
                        device_info,
                        entity_description,
                        False,
                        id_ignore_all,
                    )
                )
            if id_ignore_all:
                entity_description = ButtonEntityDescription(
                    key=(protocol, id, unit + 1), name=f"Button {unit + 1} On"
                )
                entities.append(
                    HomeduinoRFButtonAll(
                        coordinator, device_info, entity_description, True
                    )
                )
                entity_description = ButtonEntityDescription(
                    key=(protocol, id, unit + 1), name=f"Button {unit + 1} Off"
                )
                entities.append(
                    HomeduinoRFButtonAll(
                        coordinator, device_info, entity_description, False
                    )
                )
        else:
            entity_description = ButtonEntityDescription(
                key=(protocol, id, unit), name=f"Button {unit} On"
            )
            entities.append(
                HomeduinoRFButton(
                    coordinator, device_info, entity_description, True, id_ignore_all
                )
            )
            entity_description = ButtonEntityDescription(
                key=(protocol, id, unit), name=f"Button {unit} Off"
            )
            entities.append(
                HomeduinoRFButton(
                    coordinator, device_info, entity_description, False, id_ignore_all
                )
            )

    async_add_entities(entities)


class HomeduinoRFButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True

    _attr_available = False

    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: ButtonEntityDescription,
        state: bool,
        ignore_all: bool = False,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entity_description.key)

        self.protocol = entity_description.key[0]
        self.id = entity_description.key[1]
        self.unit = entity_description.key[2]

        self._attr_device_info = device_info

        self._attr_unique_id = f"{DOMAIN}-{self.protocol}-{self.id}-{self.unit}-{state}"

        self._unit_state = state
        self.entity_description = entity_description
        self.ignore_all = ignore_all

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _LOGGER.debug("async_added_to_hass")

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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self._attr_available:
            return self._attr_available

        return self.coordinator.last_update_success

    async def async_press(self, **kwargs) -> None:
        """Turn the entity on."""
        _LOGGER.debug("Switching %s", self.name)
        await self.coordinator.rf_send(
            self.protocol, {"id": self.id, "unit": self.unit, "state": self._unit_state}
        )


class HomeduinoRFButtonAll(HomeduinoRFButton):
    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: ButtonEntityDescription,
        state: bool,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_info, entity_description, state, True)

        self._attr_unique_id = f"{DOMAIN}-{self.protocol}-{self.id}-all-{state}"

    async def async_press(self, **kwargs) -> None:
        """Turn the entity on."""
        _LOGGER.debug("Switching %s", self.name)
        await self.coordinator.rf_send(
            self.protocol,
            {"id": self.id, "unit": 0, "state": self._unit_state, "all": True},
        )
