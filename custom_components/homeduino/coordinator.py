"""The Homeduino 433 MHz RF transceiver coordinator."""

import json
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeduino import (
    DEFAULT_REPEATS,
    Homeduino,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
