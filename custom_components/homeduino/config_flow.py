"""Config flow for Homeduino 433 MHz RF transceiver integration."""
from __future__ import annotations

import logging
import os
import re
from typing import Any

import homeassistant.helpers.config_validation as cv
import serial
import serial.tools.list_ports
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeduino.homeduino import (
    BAUD_RATES,
    DEFAULT_BAUD_RATE,
    DEFAULT_RECEIVE_PIN,
    DEFAULT_SEND_PIN,
    Homeduino,
    NotReadyError,
    controller,
)
from serial.serialutil import SerialException

from . import HomeduinoCoordinator
from .const import (
    CONF_BAUD_RATE,
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_RF_DEVICE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
    CONF_MANUAL_PATH,
    CONF_RECEIVE_PIN,
    CONF_RF_ID,
    CONF_RF_ID_IGNORE_ALL,
    CONF_RF_PROTOCOL,
    CONF_RF_UNIT,
    CONF_RF_UNIT_EXTRAPOLATE,
    CONF_SEND_PIN,
    CONF_SERIAL_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class HomeduinoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homeduino 433 MHz RF transceiver."""

    VERSION = 1

    STEP_SETUP_SCHEMA = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = {}
    ) -> FlowResult:
        """Handle the initial step."""
        # Test if we already have a Homeduino transceiver configured
        if not HomeduinoCoordinator.instance().has_transceiver():
            return await self.async_step_setup_transceiver(user_input)

        return await self.async_step_setup_rf_device(user_input)

    async def async_step_setup_transceiver(
        self, user_input: dict[str, Any] | None = {}
    ) -> FlowResult:
        """Handle the setup transceiver step."""
        return await self.async_step_setup_serial(user_input)

    async def async_step_setup_serial(
        self, user_input: dict[str, Any] | None = {}
    ) -> FlowResult:
        """Handle the setup transceiver serial step."""
        errors: dict[str, str] = {}

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = {}
        for port in ports:
            list_of_ports[
                port.device
            ] = f"{port}, s/n: {port.serial_number or 'n/a'}" + (
                f" - {port.manufacturer}" if port.manufacturer else ""
            )

        self.STEP_SETUP_SCHEMA = vol.Schema(
            {
                vol.Exclusive(CONF_SERIAL_PORT, CONF_SERIAL_PORT): vol.In(
                    list_of_ports
                ),
                vol.Exclusive(
                    CONF_MANUAL_PATH, CONF_SERIAL_PORT, CONF_MANUAL_PATH
                ): cv.string,
                vol.Required(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE): vol.In(
                    BAUD_RATES
                ),
                vol.Optional(CONF_RECEIVE_PIN, default=DEFAULT_RECEIVE_PIN): vol.In(
                    range(2, 4)
                ),
                vol.Optional(CONF_SEND_PIN, default=DEFAULT_SEND_PIN): vol.In(
                    range(4, 14)
                ),
            }
        )

        if user_input is not None and len(user_input) > 0:
            try:
                title, data, options = await self.validate_input_setup_serial(
                    user_input, errors
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=title, data=data, options=options)

        return self.async_show_form(
            step_id="setup_serial",
            data_schema=self.STEP_SETUP_SCHEMA,
            errors=errors,
        )

    async def validate_input_setup_serial(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> (str, dict[str, Any], dict[str, Any]):
        """Validate the user input allows us to connect.

        Data has the keys from STEP_SETUP_SCHEMA with values provided by the user.
        """
        # Validate the data can be used to set up a connection.
        self.STEP_SETUP_SCHEMA(data)

        serial_port = None
        if CONF_MANUAL_PATH in data:
            serial_port = data[CONF_MANUAL_PATH]
        elif CONF_SERIAL_PORT in data:
            serial_port = data[CONF_SERIAL_PORT]

        if serial_port is None:
            raise vol.error.RequiredFieldInvalid("No serial port configured")

        serial_port = await self.hass.async_add_executor_job(
            get_serial_by_id, serial_port
        )

        await self.async_set_unique_id(f"{DOMAIN}-{serial_port}")
        self._abort_if_unique_id_configured()

        # Test if the device exists
        if not os.path.exists(serial_port):
            _LOGGER.error("Unable to connect to the device %s: not exists", serial_port)
            raise vol.error.PathInvalid(
                f"Unable to connect to the device {serial_port}: not exists"
            )

        # Test if we can connect to the device
        try:
            homeduino = Homeduino(
                serial_port,
                data[CONF_BAUD_RATE],
                data[CONF_RECEIVE_PIN],
                data[CONF_SEND_PIN],
            )

            try:
                if not await homeduino.connect():
                    errors["base"] = f"Unable to connect to device {serial_port}"
            except SerialException as ex:
                errors["base"] = ex.strerror
            except NotReadyError as ex:
                errors["base"] = ex.strerror
            finally:
                homeduino.disconnect()

            _LOGGER.info("Device %s available", serial_port)
        except serial.SerialException as ex:
            _LOGGER.exception("Unable to connect to the device %s: %s", serial_port, ex)
            raise CannotConnect("Unable to connect", ex) from ex
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Unable to connect to the device %s: %s", serial_port, ex)
            raise CannotConnect("Unable to connect", ex) from ex

        # Return title, data, options.
        return (
            f"Homeduino Tranceiver {serial_port}",
            {
                CONF_ENTRY_TYPE: CONF_ENTRY_TYPE_TRANSCEIVER,
                CONF_SERIAL_PORT: serial_port,
                CONF_RECEIVE_PIN: data[CONF_BAUD_RATE],
            },
            {
                CONF_RECEIVE_PIN: data[CONF_RECEIVE_PIN],
                CONF_SEND_PIN: data[CONF_SEND_PIN],
            },
        )

    async def async_step_setup_rf_device(
        self, user_input: dict[str, Any] | None = {}
    ) -> FlowResult:
        """Handle the setup rf switch step."""
        errors: dict[str, str] = {}
        if not user_input:
            user_input = {}

        def natural_sort(l):
            convert = lambda text: int(text) if text.isdigit() else text.lower()
            alphanum_key = lambda key: [convert(c) for c in re.split("([0-9]+)", key)]
            return sorted(l, key=alphanum_key)

        protocol_names = [protocol.name for protocol in controller.get_all_protocols()]
        protocol_names = natural_sort(protocol_names)

        self.STEP_SETUP_SCHEMA = vol.Schema(
            {
                vol.Required(
                    CONF_RF_PROTOCOL, default=user_input.get(CONF_RF_PROTOCOL)
                ): vol.In(protocol_names),
                vol.Required(
                    CONF_RF_ID, default=user_input.get(CONF_RF_ID)
                ): cv.positive_int,
                vol.Optional(
                    CONF_RF_UNIT, default=user_input.get(CONF_RF_UNIT)
                ): cv.positive_int,
                vol.Optional(
                    CONF_RF_ID_IGNORE_ALL,
                    default=user_input.get(CONF_RF_ID_IGNORE_ALL, False),
                ): bool,
                vol.Optional(
                    CONF_RF_UNIT_EXTRAPOLATE,
                    default=user_input.get(CONF_RF_UNIT_EXTRAPOLATE, False),
                ): bool,
            }
        )

        if user_input is not None and len(user_input) > 0:
            try:
                title, data, options = await self.validate_input_setup_rf_device(
                    user_input, errors
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=title, data=data, options=options)

        return self.async_show_form(
            step_id="setup_rf_device",
            data_schema=self.STEP_SETUP_SCHEMA,
            errors=errors,
        )

    async def validate_input_setup_rf_device(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> (str, dict[str, Any], dict[str, Any]):
        """Validate the user input allows us to connect.

        Data has the keys from STEP_SETUP_SCHEMA with values provided by the user.
        """
        # Validate the data can be used to set up a connection.
        self.STEP_SETUP_SCHEMA(data)

        rf_protocol: str = data.get(CONF_RF_PROTOCOL).strip()
        rf_id: int = data.get(CONF_RF_ID)
        rf_unit: int = data.get(CONF_RF_UNIT)
        rf_id_ignore_all: bool = data.get(CONF_RF_ID_IGNORE_ALL)
        rf_unit_extrapolate: bool = data.get(CONF_RF_UNIT_EXTRAPOLATE)

        unique_id = f"{DOMAIN}-{rf_protocol}-{rf_id}"
        if not rf_unit_extrapolate:
            unique_id += f"-{rf_unit}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # Return title, data, options.
        return (
            f"{rf_protocol} {rf_id}",
            {
                CONF_ENTRY_TYPE: CONF_ENTRY_TYPE_RF_DEVICE,
                CONF_RF_PROTOCOL: rf_protocol,
                CONF_RF_ID: rf_id,
                CONF_RF_UNIT: rf_unit,
            },
            {
                CONF_RF_ID_IGNORE_ALL: rf_id_ignore_all,
                CONF_RF_UNIT_EXTRAPOLATE: rf_unit_extrapolate,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        entry_type = config_entry.data.get(CONF_ENTRY_TYPE)

        if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
            return HomeduinoOptionsFlowHandler(config_entry)

        return None


class HomeduinoOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        _LOGGER.debug(config_entry.data)
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = {}
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_RECEIVE_PIN,
                    default=self.config_entry.options.get(CONF_RECEIVE_PIN, 2),
                ): vol.All(cv.positive_int, vol.Range(min=2, max=3)),
                vol.Optional(
                    CONF_SEND_PIN,
                    default=self.config_entry.options.get(CONF_SEND_PIN, 4),
                ): vol.All(cv.positive_int, vol.Range(min=4, max=13)),
            }
        )

        if user_input is not None and len(user_input) > 0:
            # schema(user_input)
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
