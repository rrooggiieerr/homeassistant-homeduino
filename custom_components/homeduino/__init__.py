"""The Homeduino 433 MHz RF transceiver integration."""

from __future__ import annotations

import json
import logging
import os

import homeassistant.helpers.config_validation as cv
import serial
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeduino import (
    DEFAULT_BAUD_RATE,
    DEFAULT_RECEIVE_PIN,
    DEFAULT_REPEATS,
    DEFAULT_SEND_PIN,
    Homeduino,
    HomeduinoError,
    HomeduinoResponseTimeoutError,
)

from .const import (
    CONF_BAUD_RATE,
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_RF_DEVICE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
    CONF_IO_ANALOG_,
    CONF_IO_DIGITAL_,
    CONF_IO_RF_RECEIVE,
    CONF_IO_RF_SEND,
    CONF_RECEIVE_PIN,
    CONF_RF_ID_IGNORE_ALL,
    CONF_SEND_PIN,
    CONF_SERIAL_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONF_SERVICE_DEVICE_ID = "device_id"
CONF_SERVICE_COMMAND = "command"
CONF_SERVICE_PROTOCOL = "protocol"
CONF_SERVICE_ID = "id"
CONF_SERVICE_UNIT = "unit"
CONF_SERVICE_STATE = "state"
CONF_SERVICE_ALL = "all"
CONF_SERVICE_REPEATS = "repeats"

SERVICE_SEND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERVICE_DEVICE_ID): cv.string,
        vol.Required(CONF_SERVICE_COMMAND): cv.string,
    }
)
SERVICE_RAW_RF_SEND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERVICE_COMMAND): cv.string,
        vol.Optional(CONF_SERVICE_REPEATS, default=DEFAULT_REPEATS): NumberSelector(
            NumberSelectorConfig(min=1, mode=NumberSelectorMode.BOX)
        ),
    }
)

ALLOWED_FAILED_PINGS = 1

_service_rf_send_schema: vol.Schema


class HomeduinoCoordinator(DataUpdateCoordinator):
    """Homeduino Data Update Coordinator."""

    _instance = None

    @staticmethod
    def instance(hass: HomeAssistant):
        if not HomeduinoCoordinator._instance:
            HomeduinoCoordinator._instance = HomeduinoCoordinator(hass)

        return HomeduinoCoordinator._instance

    def __init__(self, hass: HomeAssistant):
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=__name__,
        )
        self._transceivers = {}

    def add_transceiver(self, device_id, transceiver: Homeduino):
        """Add a Homeduino transceiver."""

        self._transceivers[device_id] = transceiver
        transceiver.add_rf_receive_callback(self.rf_receive_callback)

        self.async_set_updated_data(None)

    def has_transceiver(self):
        return len(self._transceivers) > 0

    def get_transceiver(self, device_id):
        return self._transceivers.get(device_id)

    def connected(self):
        if not self.has_transceiver():
            return False

        for transceiver in self._transceivers.values():
            return transceiver.connected()

    async def remove_transceiver(self, device_id):
        transceiver = self._transceivers.get(device_id)
        if transceiver is not None and await transceiver.disconnect():
            self._transceivers.pop(device_id)

    @callback
    def rf_receive_callback(self, decoded) -> None:
        """Handle received messages."""
        _LOGGER.info(
            "RF Protocol: %s Values: %s",
            decoded["protocol"],
            json.dumps(decoded["values"]),
        )
        self.async_set_updated_data(decoded)

        event_data = {**{"protocol": decoded["protocol"]}, **decoded["values"]}
        self.hass.bus.async_fire(f"{DOMAIN}_event", event_data)

    async def rf_send(self, protocol: str, values, repeats=DEFAULT_REPEATS):
        if not self.has_transceiver():
            return False

        success = False
        for transceiver in self._transceivers.values():
            if not transceiver.supports_rf_send():
                continue

            if not transceiver.connected() and not await transceiver.connect():
                continue

            if await transceiver.rf_send(protocol, values, repeats):
                self.async_set_updated_data({"protocol": protocol, "values": values})

                success = True

        return success

    async def raw_rf_send(self, command: str, repeats=DEFAULT_REPEATS):
        if not self.has_transceiver():
            return False

        success = False
        for transceiver in self._transceivers.values():
            if not transceiver.supports_rf_send():
                continue

            if not transceiver.connected() and not await transceiver.connect():
                continue

            if await transceiver.raw_rf_send(command, repeats) == "ACK":
                success = True

        return success

    async def send(self, config_entry_id, command):
        if not self.has_transceiver():
            return False

        transceiver = self._transceivers.get(config_entry_id)
        if transceiver is None:
            return False

        if not transceiver.connected() and not await transceiver.connect():
            return False

        return await transceiver.send(command)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homeduino from a config entry."""
    homeduino_coordinator = HomeduinoCoordinator.instance(hass)

    entry_type = entry.data.get(CONF_ENTRY_TYPE)
    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        # Set up Homeduino 433 MHz RF transceiver
        try:
            serial_port = entry.data.get(CONF_SERIAL_PORT)
            receive_pin = None
            send_pin = None
            for digital_io in range(2, 14):
                value = entry.options.get(CONF_IO_DIGITAL_ + str(digital_io))
                if value == CONF_IO_RF_RECEIVE:
                    receive_pin = digital_io
                elif value == CONF_IO_RF_SEND:
                    send_pin = digital_io

            homeduino = Homeduino(
                serial_port,
                entry.options.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE),
                receive_pin,
                send_pin,
            )

            if not await homeduino.connect():
                raise ConfigEntryNotReady(f"Unable to connect to device {serial_port}")

            # Create the device if not exists
            device_registry = dr.async_get(hass)
            device = device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, serial_port)},
                manufacturer="pimatic",
                name=entry.title,
                model="transceiver",
            )

            homeduino_coordinator.add_transceiver(device.id, homeduino)

            hass.data.setdefault(DOMAIN, {})
            hass.data[DOMAIN][entry.entry_id] = device.id

            _LOGGER.info("Homeduino transceiver on %s is available", serial_port)
        except serial.SerialException as ex:
            raise ConfigEntryNotReady(
                f"Unable to connect to Homeduino transceiver on {serial_port}"
            ) from ex
        except HomeduinoResponseTimeoutError as ex:
            raise ConfigEntryNotReady(
                f"Unable to connect to Homeduino transceiver on {serial_port}"
            ) from ex

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    async def async_handle_send(call: ServiceCall):
        """Handle the service call."""
        device_id: str = call.data.get(CONF_SERVICE_DEVICE_ID)
        command: str = call.data.get(CONF_SERVICE_COMMAND)

        return await HomeduinoCoordinator.instance(hass).send(
            device_id, command.strip()
        )

    async def async_handle_rf_send(call: ServiceCall):
        """Handle the service call."""
        protocol: str = call.data.get(CONF_SERVICE_PROTOCOL)
        id_: int = int(call.data.get(CONF_SERVICE_ID))
        unit: int = int(call.data.get(CONF_SERVICE_UNIT))
        state: bool = bool(call.data.get(CONF_SERVICE_STATE))
        all_: bool = bool(call.data.get(CONF_SERVICE_ALL))
        repeats: int = int(call.data.get(CONF_SERVICE_REPEATS, DEFAULT_REPEATS))

        return await HomeduinoCoordinator.instance(hass).rf_send(
            protocol, {"id": id_, "unit": unit, "state": state, "all": all_}, repeats
        )

    async def async_handle_raw_rf_send(call: ServiceCall):
        """Handle the service call."""
        command: str = call.data.get(CONF_SERVICE_COMMAND)
        repeats: int = int(call.data.get(CONF_SERVICE_REPEATS, DEFAULT_REPEATS))

        return await HomeduinoCoordinator.instance(hass).raw_rf_send(command, repeats)

    hass.services.async_register(
        DOMAIN, "send", async_handle_send, schema=SERVICE_SEND_SCHEMA
    )

    protocol_names = Homeduino.get_protocols()
    protocol_names = [
        protocol_name
        for protocol_name in protocol_names
        if protocol_name.startswith(("switch", "dimmer", "pir", "weather"))
    ]

    _service_rf_send_schema = vol.Schema(
        {
            vol.Required(CONF_SERVICE_PROTOCOL, default=""): SelectSelector(
                SelectSelectorConfig(
                    options=protocol_names,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_SERVICE_ID): NumberSelector(
                NumberSelectorConfig(min=0, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_SERVICE_UNIT): NumberSelector(
                NumberSelectorConfig(min=0, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_SERVICE_STATE): cv.boolean,
            vol.Optional(CONF_SERVICE_ALL): BooleanSelector(),
            vol.Optional(CONF_SERVICE_REPEATS, default=DEFAULT_REPEATS): NumberSelector(
                NumberSelectorConfig(min=1, mode=NumberSelectorMode.BOX)
            ),
        }
    )

    hass.services.async_register(
        DOMAIN, "rf_send", async_handle_rf_send, schema=_service_rf_send_schema
    )

    hass.services.async_register(
        DOMAIN,
        "raw_rf_send",
        async_handle_raw_rf_send,
        schema=SERVICE_RAW_RF_SEND_SCHEMA,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_type = entry.data.get(CONF_ENTRY_TYPE)

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        device_id = hass.data[DOMAIN][entry.entry_id]
        await HomeduinoCoordinator.instance(hass).remove_transceiver(device_id)
        if unload_ok := await hass.config_entries.async_unload_platforms(
            entry, PLATFORMS
        ):
            hass.data[DOMAIN].pop(entry.entry_id)
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Configuration options updated, reloading Homeduino integration")
    entry_type = entry.data.get(CONF_ENTRY_TYPE)
    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        device_id = hass.data[DOMAIN][entry.entry_id]
        await HomeduinoCoordinator.instance(hass).remove_transceiver(device_id)
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if config_entry.version == 1:
        _LOGGER.debug("Migrating config entry from 1 to 2")

        entry_type = config_entry.data.get(CONF_ENTRY_TYPE)

        if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
            receive_pin = int(config_entry.options.get(CONF_RECEIVE_PIN))
            send_pin = int(config_entry.options.get(CONF_SEND_PIN))

            data = {
                CONF_ENTRY_TYPE: CONF_ENTRY_TYPE_TRANSCEIVER,
                CONF_SERIAL_PORT: config_entry.data.get(CONF_SERIAL_PORT),
                CONF_BAUD_RATE: config_entry.data.get(
                    CONF_BAUD_RATE, DEFAULT_BAUD_RATE
                ),
            }

            options = {}

            for digital_io in range(2, 14):
                if digital_io == receive_pin:
                    options[CONF_IO_DIGITAL_ + str(digital_io)] = CONF_IO_RF_RECEIVE
                elif digital_io == send_pin:
                    options[CONF_IO_DIGITAL_ + str(digital_io)] = CONF_IO_RF_SEND
                else:
                    options[CONF_IO_DIGITAL_ + str(digital_io)] = None

            for analog_input in range(0, 8):
                options[CONF_IO_ANALOG_ + str(analog_input)] = False

        if entry_type == CONF_ENTRY_TYPE_RF_DEVICE:
            data = config_entry.data
            options = {
                CONF_RF_ID_IGNORE_ALL: config_entry.options.get(
                    CONF_RF_ID_IGNORE_ALL, False
                )
            }

        hass.config_entries.async_update_entry(
            config_entry, data=data, options=options, version=2
        )

        return True

    return False
