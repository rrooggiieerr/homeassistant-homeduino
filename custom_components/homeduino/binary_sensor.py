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
from homeassistant.helpers import entity_registry as er
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
                entity_description = BinarySensorEntityDescription(
                    key=(config_entry.entry_id, digital_io),
                    translation_key=CONF_IO_DIGITAL_INPUT,
                    translation_placeholders={"digital_io": digital_io},
                )
                entities.append(
                    HomeduinoTransceiverBinarySensor(
                        coordinator, device_info, entity_description
                    )
                )
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE and config_entry.data.get(
        CONF_RF_PROTOCOL
    ).startswith(("pir", "contact")):
        protocol = config_entry.data.get(CONF_RF_PROTOCOL)
        id = int(config_entry.data.get(CONF_RF_ID))
        unit = config_entry.data.get(CONF_RF_UNIT)
        if unit is not None:
            unit = int(unit)

        # --- Migration: alte unique_id -> neue unique_id ---
        registry = er.async_get(hass)
        old_base = f"{DOMAIN}-{protocol}-{id}-{unit}"

        # New field naming: use "state" for both PIR and contact sensor state.
        if protocol.startswith("pir"):
            fields = ["state"]
        elif protocol.startswith("contact"):
            # map old single-field unique (no field suffix) -> new unique ids
            # New field name is "state" (replaces old "contact") and keep "lowBattery"
            fields = ["state", "lowBattery"]
        else:
            fields = []

        for field in fields:
            old_unique = old_base  # alte Form: DOMAIN-protocol-id-unit
            new_unique = f"{DOMAIN}-{protocol}-{id}-{unit}-{field}"
            entity_id = registry.async_get_entity_id("binary_sensor", DOMAIN, old_unique)
            if entity_id:
                registry.async_update_entity(entity_id, new_unique_id=new_unique)


        identifier = f"{protocol}-{id}"
        if unit is not None:
            identifier += f"-{unit}"

        device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=config_entry.title,
        )

        # Determine device_class based on protocol
        device_class = None
        if protocol.startswith("pir"):
            device_class = BinarySensorDeviceClass.MOTION
        elif protocol.startswith("contact"):
            device_class = BinarySensorDeviceClass.DOOR

        # Main state entity: use field name "state" for both PIR and contact protocols
        entity_description = BinarySensorEntityDescription(
            key=(protocol, id, unit, "state"),
            translation_key="rf_motion" if protocol.startswith("pir") else "rf_contact",
            translation_placeholders={"unit": unit},
            device_class=device_class,
        )

        entities.append(
            HomeduinoRFBinarySensor(coordinator, device_info, entity_description)
        )

        # For contact devices also expose low battery as separate entity
        if protocol.startswith("contact"):
            entity_description = BinarySensorEntityDescription(
                key=(protocol, id, unit, "lowBattery"),
                translation_key="rf_low_battery",
                translation_placeholders={"unit": unit},
                device_class=BinarySensorDeviceClass.BATTERY,
            )

            entities.append(
                HomeduinoRFBinarySensor(coordinator, device_info, entity_description)
            )

    async_add_entities(entities)


class HomeduinoTransceiverBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_available = False

    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: BinarySensorEntityDescription,
    ):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = device_info

        self._config_entry_id = entity_description.key[0]
        self._digital_io = entity_description.key[1]
        self._attr_unique_id = (
            f"{self._config_entry_id}-{CONF_IO_DIGITAL_INPUT}-{self._digital_io}"
        )

        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        homeduino = self.coordinator.get_transceiver(self.device_entry.id)
        await homeduino.add_digital_read_callback(
            self._digital_io, self._handle_digital_read_update
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

    def __init__(
        self,
        coordinator: HomeduinoCoordinator,
        device_info: DeviceInfo,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entity_description.key)

        self.protocol = entity_description.key[0]
        self.id = entity_description.key[1]
        self.unit = entity_description.key[2]
        self.field = entity_description.key[3]

        self._attr_device_info = device_info

        self._attr_unique_id = f"{DOMAIN}-{self.protocol}-{self.id}-{self.unit}-{self.field}"

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

            if self.coordinator.data.get("protocol") != self.protocol:
                return

            if self.coordinator.data.get("values", {}).get("id") != self.id:
                return

            if self.coordinator.data.get("values", {}).get("unit") != self.unit:
                return

            _LOGGER.debug(self.coordinator.data)

            self._attr_is_on = self.coordinator.data.get("values", {}).get(self.field)

        self.async_write_ha_state()
