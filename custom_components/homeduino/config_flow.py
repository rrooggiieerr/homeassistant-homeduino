"""Config flow for Homeduino 433 MHz RF transceiver integration."""

from __future__ import annotations

import logging
import os
from typing import Any

import serial.tools.list_ports
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_TYPE
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeduino import (
    BAUD_RATES,
    DEFAULT_BAUD_RATE,
    DEFAULT_RECEIVE_PIN,
    DEFAULT_SEND_PIN,
    Homeduino,
    HomeduinoNotReadyError,
    HomeduinoResponseTimeoutError,
)
from serial.serialutil import SerialException

from . import HomeduinoCoordinator
from .const import *

_LOGGER = logging.getLogger(__name__)

_DIGITAL_IO = [
    CONF_IO_RF_SEND,
    CONF_IO_DIGITAL_INPUT,
    CONF_IO_DIGITAL_OUTPUT,
]
_DIGITAL_IO_DEVICES = [
    CONF_IO_DHT11,
    CONF_IO_DHT22,
    CONF_IO_1_WIRE,
]


class HomeduinoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homeduino 433 MHz RF transceiver."""

    VERSION = 2

    _step_setup_serial_schema: vol.Schema
    _step_setup_rf_device_schema: vol.Schema

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Test if we already have a Homeduino transceiver configured
        if not HomeduinoCoordinator.instance(self.hass).has_transceiver():
            return await self.async_step_setup_transceiver(user_input)

        if user_input is not None:
            user_selection = user_input[CONF_TYPE]
            if user_selection == "transceiver":
                return await self.async_step_setup_transceiver()
            if user_selection == "rf_device":
                return await self.async_step_setup_rf_device()

        device_types = ["transceiver", "rf_device"]

        schema = vol.Schema(
            {
                vol.Required(CONF_TYPE): SelectSelector(
                    SelectSelectorConfig(
                        options=device_types,
                        mode=SelectSelectorMode.LIST,
                        translation_key="device_types",
                    )
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_setup_transceiver(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the setup transceiver step."""
        return await self.async_step_setup_serial(user_input)

    async def async_step_setup_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the setup transceiver serial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            title, data, options = await self.validate_input_setup_serial(
                user_input, errors
            )

            if not errors:
                return self.async_create_entry(title=title, data=data, options=options)

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = {}
        for port in ports:
            list_of_ports[port.device] = (
                f"{port}, s/n: {port.serial_number or 'n/a'}"
                + (f" - {port.manufacturer}" if port.manufacturer else "")
            )

        self._step_setup_serial_schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL_PORT, default=""): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=k, label=v)
                            for k, v in list_of_ports.items()
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                        sort=True,
                    )
                ),
                vol.Required(
                    CONF_BAUD_RATE, default=str(DEFAULT_BAUD_RATE)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=str(baud_rate), label=f"{baud_rate:n} Bd"
                            )
                            for baud_rate in BAUD_RATES
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        for digital_io in range(2, 13):
            options = [
                CONF_IO_NONE,
            ]
            if digital_io in (2, 3):
                options += [
                    CONF_IO_RF_RECEIVE,
                ]

            options += _DIGITAL_IO

            if digital_io in (3, 5, 6, 9, 10, 11):
                options += [
                    CONF_IO_PWM_OUTPUT,
                ]

            # options += _DIGITAL_IO_DEVICES

            default = CONF_IO_NONE
            if digital_io == DEFAULT_RECEIVE_PIN:
                default = CONF_IO_RF_RECEIVE
            if digital_io == DEFAULT_SEND_PIN:
                default = CONF_IO_RF_SEND

            self._step_setup_serial_schema = self._step_setup_serial_schema.extend(
                {
                    vol.Optional(
                        CONF_IO_DIGITAL_ + str(digital_io), default=default
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="digital_io",
                        )
                    ),
                }
            )

        self._step_setup_serial_schema = self._step_setup_serial_schema.extend(
            {
                vol.Optional(
                    CONF_IO_DIGITAL_ + "13", default=CONF_IO_NONE
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[CONF_IO_NONE, CONF_IO_RF_SEND, CONF_IO_DIGITAL_OUTPUT],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="digital_io",
                    )
                ),
            }
        )

        for analog_input in range(0, 8):
            self._step_setup_serial_schema = self._step_setup_serial_schema.extend(
                {vol.Optional(CONF_IO_ANALOG_ + str(analog_input)): BooleanSelector()}
            )

        if user_input is not None:
            data_schema = self.add_suggested_values_to_schema(
                self._step_setup_serial_schema, user_input
            )
        else:
            data_schema = self._step_setup_serial_schema

        return self.async_show_form(
            step_id="setup_serial",
            data_schema=data_schema,
            errors=errors,
        )

    async def validate_input_setup_serial(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> (str, dict[str, Any], dict[str, Any]):
        """Validate the user input and create data.

        Data has the keys from _step_setup_serial_schema with values provided by the user.
        """
        # Validate the data can be used to set up a connection.
        self._step_setup_serial_schema(data)

        serial_port = data.get(CONF_SERIAL_PORT)

        if serial_port is None:
            raise vol.error.RequiredFieldInvalid("No serial port configured")

        serial_port = await self.hass.async_add_executor_job(
            get_serial_by_id, serial_port
        )

        # Test if the device exists
        if not os.path.exists(serial_port):
            errors[CONF_SERIAL_PORT] = "nonexisting_serial_port"

        await self.async_set_unique_id(f"{DOMAIN}-{serial_port}")
        self._abort_if_unique_id_configured()

        baud_rate = int(data[CONF_BAUD_RATE])

        if errors.get(CONF_SERIAL_PORT) is None:
            # Test if we can connect to the device
            try:
                homeduino = Homeduino(
                    serial_port,
                    baud_rate,
                    None,
                    None,
                )

                try:
                    if not await homeduino.connect(ping_interval=0):
                        errors["base"] = f"Unable to connect to device {serial_port}"
                except SerialException as ex:
                    errors["base"] = ex.strerror
                except HomeduinoNotReadyError as ex:
                    errors["base"] = ex.strerror
                finally:
                    await homeduino.disconnect()

                _LOGGER.info("Device %s available", serial_port)
            except HomeduinoResponseTimeoutError as ex:
                _LOGGER.error("Unable to connect to the device %s", serial_port, ex)
                errors["base"] = "cannot_connect"
            except serial.SerialException as ex:
                _LOGGER.exception("Unable to connect to the device %s", serial_port)
                errors["base"] = "cannot_connect"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception("Unable to connect to the device %s", serial_port)
                errors["base"] = "cannot_connect"

        options = {}

        for digital_io in range(2, 14):
            key = CONF_IO_DIGITAL_ + str(digital_io)
            value = data.get(key)
            if value == CONF_IO_NONE:
                value = None
            options[key] = value

        for analog_input in range(0, 8):
            key = CONF_IO_ANALOG_ + str(analog_input)
            options[key] = data.get(key)

        # Return title, data, options.
        return (
            f"Homeduino Transceiver {serial_port}",
            {
                CONF_ENTRY_TYPE: CONF_ENTRY_TYPE_TRANSCEIVER,
                CONF_SERIAL_PORT: serial_port,
                CONF_BAUD_RATE: baud_rate,
            },
            options,
        )

    async def async_step_setup_rf_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the setup rf switch step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("user_input: %s", user_input)

            title, data, options = await self.validate_input_setup_rf_device(
                user_input, errors
            )
            _LOGGER.debug(
                "title: %s, data: %s, options: %s, errors: %s",
                title,
                data,
                options,
                errors,
            )

            if not errors:
                return self.async_create_entry(title=title, data=data, options=options)

        protocol_names = Homeduino.get_protocols()
        protocol_names = [
            protocol_name
            for protocol_name in protocol_names
            if protocol_name.startswith(("switch", "dimmer", "pir"))
        ]

        self._step_setup_rf_device_schema = vol.Schema(
            {
                vol.Required(CONF_RF_PROTOCOL, default=""): SelectSelector(
                    SelectSelectorConfig(
                        options=protocol_names,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_RF_ID): NumberSelector(
                    NumberSelectorConfig(min=0, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_RF_UNIT): NumberSelector(
                    NumberSelectorConfig(min=0, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(
                    CONF_RF_ID_IGNORE_ALL,
                    default=False,
                ): BooleanSelector(),
            }
        )

        if user_input is not None:
            data_schema = self.add_suggested_values_to_schema(
                self._step_setup_rf_device_schema, user_input
            )
        else:
            data_schema = self._step_setup_rf_device_schema

        return self.async_show_form(
            step_id="setup_rf_device",
            data_schema=data_schema,
            errors=errors,
        )

    async def validate_input_setup_rf_device(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> (str, dict[str, Any], dict[str, Any]):
        """Validate the user input and create data.

        Data has the keys from _step_setup_rf_device_schema with values provided by the user.
        """
        # Validate the data.
        self._step_setup_rf_device_schema(data)

        _LOGGER.debug(data)
        rf_protocol: str = data.get(CONF_RF_PROTOCOL).strip()
        rf_id: int = int(data.get(CONF_RF_ID))
        rf_unit: int = data.get(CONF_RF_UNIT, None)
        if rf_unit is not None:
            rf_unit = int(rf_unit) 
        rf_id_ignore_all: bool = data.get(CONF_RF_ID_IGNORE_ALL, False)

        unique_id = f"{DOMAIN}-{rf_protocol}-{rf_id}"
        if rf_unit is not None:
            unique_id += f"-{rf_unit}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        title = f"{rf_protocol} {rf_id}"
        if rf_unit is not None:
            title += f" {rf_unit}"
        data = {
            CONF_ENTRY_TYPE: CONF_ENTRY_TYPE_RF_DEVICE,
            CONF_RF_PROTOCOL: rf_protocol,
            CONF_RF_ID: rf_id,
        }
        if rf_unit is not None:
            data[CONF_RF_UNIT] = rf_unit

        options = {}

        if rf_protocol.startswith("switch") or rf_protocol.startswith("dimmer"):
            options[CONF_RF_ID_IGNORE_ALL] = rf_id_ignore_all

        # Return title, data, options.
        return (
            title,
            data,
            options,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return HomeduinoOptionsFlowHandler(config_entry)


class HomeduinoOptionsFlowHandler(config_entries.OptionsFlow):
    TRANSCEIVER_OPTIONS_SCHEMA = vol.Schema({})
    RF_DEVICE_OPTIONS_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_RF_ID_IGNORE_ALL): BooleanSelector(),
        }
    )

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        _LOGGER.debug(config_entry.data)
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        entry_type = self.config_entry.data.get(CONF_ENTRY_TYPE)

        if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
            data_schema = self.TRANSCEIVER_OPTIONS_SCHEMA

            for digital_io in range(2, 13):
                options = [
                    CONF_IO_NONE,
                ]
                if digital_io in (2, 3):
                    options += [
                        CONF_IO_RF_RECEIVE,
                    ]

                options += _DIGITAL_IO

                if digital_io in (3, 5, 6, 9, 10, 11):
                    options += [
                        CONF_IO_PWM_OUTPUT,
                    ]

                # options += _DIGITAL_IO_DEVICES

                data_schema = data_schema.extend(
                    {
                        vol.Optional(
                            CONF_IO_DIGITAL_ + str(digital_io), default=CONF_IO_NONE
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=options,
                                mode=SelectSelectorMode.DROPDOWN,
                                translation_key="digital_io",
                            )
                        ),
                    }
                )

            data_schema = data_schema.extend(
                {
                    vol.Optional(
                        CONF_IO_DIGITAL_ + "13", default=CONF_IO_NONE
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                CONF_IO_NONE,
                                CONF_IO_RF_SEND,
                                CONF_IO_DIGITAL_OUTPUT,
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="digital_io",
                        )
                    ),
                }
            )

            for analog_input in range(0, 8):
                data_schema = data_schema.extend(
                    {
                        vol.Optional(
                            CONF_IO_ANALOG_ + str(analog_input)
                        ): BooleanSelector()
                    }
                )
        elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE:
            data_schema = self.RF_DEVICE_OPTIONS_SCHEMA

        if user_input is not None:
            data_schema(user_input)
            return self.async_create_entry(title="", data=user_input)

        if user_input is not None:
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)
        else:
            data_schema = self.add_suggested_values_to_schema(
                data_schema, self.config_entry.options
            )

        return self.async_show_form(
            step_id=entry_type, data_schema=data_schema, errors=errors
        )

    async def async_step_transceiver(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_init(user_input)

    async def async_step_rf_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_init(user_input)


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path
