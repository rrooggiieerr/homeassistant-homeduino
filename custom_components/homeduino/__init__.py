"""The Homeduino 433 MHz RF transceiver integration."""
from __future__ import annotations

import json
import logging
import os

import serial
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeduino import Homeduino

from .const import (
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
    Platform.SWITCH,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


class HomeduinoCoordinator(DataUpdateCoordinator):
    """Homeduino Data Update Coordinator."""

    _instance = None

    serial_port = None
    homeduino = None

    binary_sensors = []
    analog_sensors = []
    dht_sensor = None

    @staticmethod
    def instance(hass=None):
        if not HomeduinoCoordinator._instance:
            HomeduinoCoordinator._instance = HomeduinoCoordinator(hass)

        return HomeduinoCoordinator._instance

    @staticmethod
    def has_instance():
        return HomeduinoCoordinator._instance is not None

    @staticmethod
    async def remove_instance():
        await HomeduinoCoordinator._instance.disconnect()
        HomeduinoCoordinator._instance = None

    def __init__(self, hass):
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=__name__,
        )

    def init(
        self, serial_port: str, receive_pin: int, send_pin: int, hdt_pin: int = None
    ):
        """Initialize Homeduino Data Update Coordinator."""

        self.serial_port = serial_port
        self.homeduino = Homeduino(
            self.serial_port, receive_pin, send_pin, hdt_pin, self.hass.loop
        )

        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.serial_port)},
            name="Homeduino Transceiver",
            manufacturer="pimatic",
        )

    @callback
    def rf_receive_callback(self, decoded) -> None:
        """Handle received messages."""
        _LOGGER.info(
            f"RF Protocol: %s Values: %s",
            decoded["protocol"],
            json.dumps(decoded["values"]),
        )
        self.async_set_updated_data(decoded)

    async def connect(self):
        if not await self.homeduino.connect():
            raise ConfigEntryNotReady(f"Unable to connect to device {self.serial_port}")

        self.homeduino.add_rf_receive_callback(self.rf_receive_callback)

    def disconnect(self):
        self.homeduino.disconnect()

    def rf_send(self, protocol, values):
        if self.homeduino:
            return self.homeduino.rf_send(protocol, values)

        return False

    def send(self, command):
        if self.homeduino:
            return self.homeduino.send_command(command)

        return False


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    def handle_send(call):
        """Handle the service call."""
        command: str = call.data.get("command")

        return HomeduinoCoordinator.instance().send(command.strip())

    hass.services.register(DOMAIN, "send", handle_send)

    # Return boolean to indicate that initialization was successful.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homeduino from a config entry."""
    entry_type = entry.data.get(CONF_ENTRY_TYPE)

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        if HomeduinoCoordinator.has_instance():
            # We allow only one transceiver
            _LOGGER.error("Only one Homeduino Transceiver is currently allowed")
            return False

        # Set up Homeduino 433 MHz RF transceiver
        try:
            serial_port = entry.data.get(CONF_SERIAL_PORT, None)

            homeduino_coordinator = HomeduinoCoordinator.instance(hass)
            homeduino_coordinator.init(
                serial_port,
                entry.options.get(CONF_RECEIVE_PIN),
                entry.options.get(CONF_SEND_PIN),
            )

            # Create the device if not exists
            device_registry = dr.async_get(hass)
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id, **homeduino_coordinator.device_info
            )

            # Open the connection.
            await homeduino_coordinator.connect()

            _LOGGER.info("Homeduino transceiver on %s is available", serial_port)
        except serial.SerialException as ex:
            raise ConfigEntryNotReady(
                f"Unable to connect to Homeduino transceiver on {serial_port}: {ex}"
            ) from ex

        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = homeduino_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_type = entry.data.get(CONF_ENTRY_TYPE)

    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        HomeduinoCoordinator.remove_instance()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
