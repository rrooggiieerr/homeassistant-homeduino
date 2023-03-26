"""The Homeduino 433 MHz RF transceiver integration."""
from __future__ import annotations

import json
import logging
import os
from datetime import timedelta

import serial
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator,\
    UpdateFailed
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
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]


class HomeduinoCoordinator(DataUpdateCoordinator):
    """Homeduino Data Update Coordinator."""

    _instance = None

    serial_port = None
    transceiver = None

    binary_sensors = []
    analog_sensors = []
    dht_sensor = None

    @staticmethod
    def instance(hass=None):
        if not HomeduinoCoordinator._instance:
            HomeduinoCoordinator._instance = HomeduinoCoordinator(hass)

        return HomeduinoCoordinator._instance

    def __init__(self, hass):
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=__name__,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=5),
        )

    def add_transceiver(
        self, transceiver: Homeduino
    ):
        """Add a Homeduino transceiver."""

        self.transceiver = transceiver
        self.transceiver.add_rf_receive_callback(self.rf_receive_callback)
        
        self.async_set_updated_data(None)

    def has_transceiver(self):
        return self.transceiver is not None

    def remove_transceiver(self, serial_port):
        _LOGGER.debug(self.transceiver)
        if self.transceiver:
            self.transceiver.disconnect()
        self.transceiver = None

    async def _async_update_data(self):
        if not self.transceiver:
            raise UpdateFailed(f"No Homeduino configured")

        if not await self.transceiver.ping():
            # self.transceiver.disconnect()
            # self.transceiver = None
            raise UpdateFailed(f"Unable to ping Homeduino")
        
        return None

    @callback
    def rf_receive_callback(self, decoded) -> None:
        """Handle received messages."""
        _LOGGER.info(
            f"RF Protocol: %s Values: %s",
            decoded["protocol"],
            json.dumps(decoded["values"]),
        )
        self.async_set_updated_data(decoded)

    def rf_send(self, protocol: str, values):
        if self.transceiver:
            return self.transceiver.rf_send(protocol, values)

        return False

    def send(self, command):
        if self.transceiver:
            return self.transceiver.send_command(command)

        return False


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    async def async_handle_send(call: ServiceCall):
        """Handle the service call."""
        command: str = call.data.get("command")

        return HomeduinoCoordinator.instance().send(command.strip())

    hass.services.async_register(DOMAIN, "send", async_handle_send)

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
            
            homeduino = Homeduino(serial_port, entry.options.get(CONF_RECEIVE_PIN), entry.options.get(CONF_SEND_PIN))

            if not await homeduino.connect():
                raise ConfigEntryNotReady(f"Unable to connect to device {serial_port}")
    
            homeduino_coordinator.add_transceiver(homeduino)

            # Create the device if not exists
            device_registry = dr.async_get(hass)
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id, identifiers={(DOMAIN, serial_port)}, manufacturer="pimatic", name="Homeduino Transceiver"
            )

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
        serial_port = entry.data.get(CONF_SERIAL_PORT, None)
        HomeduinoCoordinator.instance(hass).remove_transceiver(serial_port)
        if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
            hass.data[DOMAIN].pop(entry.entry_id)
    elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok
