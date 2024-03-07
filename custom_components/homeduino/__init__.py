"""The Homeduino 433 MHz RF transceiver integration."""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import serial
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeduino import (
    DEFAULT_BAUD_RATE,
    DEFAULT_RECEIVE_PIN,
    DEFAULT_SEND_PIN,
    Homeduino,
    HomeduinoError,
    ResponseTimeoutError,
)

from .const import (
    CONF_BAUD_RATE,
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_RF_DEVICE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
    CONF_RECEIVE_PIN,
    CONF_SEND_PIN,
    CONF_SERIAL_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONF_SERVICE_COMMAND = "command"

SERVICE_SEND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERVICE_COMMAND): cv.string,
    }
)

ALLOWED_FAILED_PINGS = 1


class HomeduinoCoordinator(DataUpdateCoordinator):
    """Homeduino Data Update Coordinator."""

    _instance = None

    serial_port = None
    transceiver: Homeduino = None

    binary_sensors = []
    analog_sensors = []
    dht_sensor = None

    failed_pings = 0

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
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=5),
        )

    def add_transceiver(self, transceiver: Homeduino):
        """Add a Homeduino transceiver."""

        self.transceiver = transceiver
        self.transceiver.add_rf_receive_callback(self.rf_receive_callback)

        self.async_set_updated_data(None)

    def has_transceiver(self):
        return self.transceiver is not None

    def connected(self):
        if not self.transceiver:
            return False

        return self.transceiver.connected()

    async def remove_transceiver(self, serial_port):
        _LOGGER.debug(self.transceiver)
        if self.transceiver and await self.transceiver.disconnect():
            self.transceiver = None

    async def _async_update_data(self):
        if not self.transceiver:
            raise UpdateFailed("No Homeduino configured")

        try:
            if (
                not self.transceiver.connected()
                and not await self.transceiver.connect()
            ):
                raise UpdateFailed("Homeduino not connected")
        except ResponseTimeoutError as ex:
            raise UpdateFailed(
                f"Unable to connect to Homeduino transceiver on {self.serial_port}"
            ) from ex

        try:
            if await self.transceiver.ping():
                self.failed_pings = 0
            else:
                self.failed_pings += 1

                if self.failed_pings > ALLOWED_FAILED_PINGS:
                    raise UpdateFailed("Unable to ping Homeduino")

                _LOGGER.warning("Unable to ping Homeduino")
        except HomeduinoError as ex:
            raise UpdateFailed("Unable to ping Homeduino") from ex

        return None

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

    async def rf_send(self, protocol: str, values):
        if not self.transceiver:
            return False

        if not self.transceiver.connected() and not await self.transceiver.connect():
            return False

        if await self.transceiver.rf_send(protocol, values):
            self.async_set_updated_data({"protocol": protocol, "values": values})

            return True

        return False

    async def send(self, command):
        if not self.transceiver:
            return False

        if not self.transceiver.connected() and not await self.transceiver.connect():
            return False

        return await self.transceiver.send(command)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up is called when Home Assistant is loading our component."""

    async def async_handle_send(call: ServiceCall):
        """Handle the service call."""
        command: str = call.data.get(CONF_SERVICE_COMMAND)

        return await HomeduinoCoordinator.instance(hass).send(command.strip())

    hass.services.async_register(
        DOMAIN, "send", async_handle_send, schema=SERVICE_SEND_SCHEMA
    )

    # Return boolean to indicate that initialization was successful.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homeduino from a config entry."""
    entry_type = entry.data.get(CONF_ENTRY_TYPE)

    homeduino_coordinator = HomeduinoCoordinator.instance(hass)

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        if homeduino_coordinator.has_transceiver():
            # We allow only one transceiver
            _LOGGER.error("Only one Homeduino Transceiver is currently allowed")
            return False

        # Set up Homeduino 433 MHz RF transceiver
        try:
            serial_port = entry.data.get(CONF_SERIAL_PORT, None)

            homeduino = Homeduino(
                serial_port,
                entry.options.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE),
                entry.options.get(CONF_RECEIVE_PIN, DEFAULT_RECEIVE_PIN),
                entry.options.get(CONF_SEND_PIN, DEFAULT_SEND_PIN),
            )

            if not await homeduino.connect():
                raise ConfigEntryNotReady(f"Unable to connect to device {serial_port}")

            homeduino_coordinator.add_transceiver(homeduino)

            # Create the device if not exists
            device_registry = dr.async_get(hass)
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, serial_port)},
                manufacturer="pimatic",
                name="Homeduino Transceiver",
            )

            _LOGGER.info("Homeduino transceiver on %s is available", serial_port)
        except serial.SerialException as ex:
            raise ConfigEntryNotReady(
                f"Unable to connect to Homeduino transceiver on {serial_port}"
            ) from ex
        except ResponseTimeoutError as ex:
            raise ConfigEntryNotReady(
                f"Unable to connect to Homeduino transceiver on {serial_port}"
            ) from ex

        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = homeduino_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_type = entry.data.get(CONF_ENTRY_TYPE)

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        serial_port = entry.data.get(CONF_SERIAL_PORT, None)
        await HomeduinoCoordinator.instance(hass).remove_transceiver(serial_port)
        if unload_ok := await hass.config_entries.async_unload_platforms(
            entry, PLATFORMS
        ):
            hass.data[DOMAIN].pop(entry.entry_id)
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Configuration options updated, reloading Homeduino integration")
    await hass.config_entries.async_reload(entry.entry_id)
