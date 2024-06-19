"""Config flow for Homeduino 433 MHz RF transceiver integration."""

from __future__ import annotations

import logging
import os
from typing import Any

import homeassistant.helpers.config_validation as cv
import serial.tools.list_ports
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_TYPE
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
from homeduino import (
    BAUD_RATES,
    DEFAULT_BAUD_RATE,
    DEFAULT_RECEIVE_PIN,
    DEFAULT_SEND_PIN,
    Homeduino,
    NotReadyError,
)
from serial.serialutil import SerialException

from . import HomeduinoCoordinator
from .const import (
    CONF_BAUD_RATE,
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_RF_DEVICE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
    CONF_LOCAL_DEVICE_GPIO,
    CONF_LOCAL_DEVICE_INTERVAL,
    CONF_LOCAL_DEVICE_TYPE,
    CONF_LOCAL_DEVICE_TYPE_ANALOG_INPUT,
    CONF_LOCAL_DEVICE_TYPE_DHT11,
    CONF_LOCAL_DEVICE_TYPE_DHT22,
    CONF_LOCAL_DEVICE_TYPE_DIGITAL_INPUT,
    CONF_LOCAL_DEVICE_TYPE_DIGITAL_OUTPUT,
    CONF_LOCAL_DEVICE_TYPE_DS18B20,
    CONF_LOCAL_DEVICE_TYPE_PWM_OUTPUT,
    CONF_RECEIVE_PIN,
    CONF_RF_ID,
    CONF_RF_ID_IGNORE_ALL,
    CONF_RF_PROTOCOL,
    CONF_RF_UNIT,
    CONF_SEND_PIN,
    CONF_SERIAL_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class HomeduinoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homeduino 433 MHz RF transceiver."""

    VERSION = 1

    _step_setup_serial_schema: vol.Schema
    _step_setup_rf_device_schema: vol.Schema
    _STEP_SETUP_LOCAL_DEVICE_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_LOCAL_DEVICE_GPIO, default=""): NumberSelector(
                NumberSelectorConfig(min=4, max=13, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_LOCAL_DEVICE_TYPE, default=""): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(
                            value=CONF_LOCAL_DEVICE_TYPE_DHT11, label="DHT11"
                        ),
                        SelectOptionDict(
                            value=CONF_LOCAL_DEVICE_TYPE_DHT22, label="DHT22"
                        ),
                        SelectOptionDict(
                            value=CONF_LOCAL_DEVICE_TYPE_DS18B20, label="Dallas DS18B20"
                        ),
                        SelectOptionDict(
                            value=CONF_LOCAL_DEVICE_TYPE_ANALOG_INPUT,
                            label="Analog Input",
                        ),
                        SelectOptionDict(
                            value=CONF_LOCAL_DEVICE_TYPE_DIGITAL_INPUT,
                            label="Digital Input",
                        ),
                        SelectOptionDict(
                            value=CONF_LOCAL_DEVICE_TYPE_DIGITAL_OUTPUT,
                            label="Digital Output",
                        ),
                        SelectOptionDict(
                            value=CONF_LOCAL_DEVICE_TYPE_PWM_OUTPUT, label="PWM Output"
                        ),
                    ],
                    custom_value=True,
                    sort=True,
                )
            ),
            vol.Optional(CONF_LOCAL_DEVICE_INTERVAL): NumberSelector(
                NumberSelectorConfig(min=0, mode=NumberSelectorMode.BOX)
            ),
        }
    )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = {}
    ) -> FlowResult:
        """Handle the initial step."""
        # Test if we already have a Homeduino transceiver configured
        if not HomeduinoCoordinator.instance(self.hass).has_transceiver():
            return await self.async_step_setup_transceiver(user_input)

        return await self.async_step_setup_rf_device()
        # if user_input is not None:
        #     user_selection = user_input[CONF_TYPE]
        #     if user_selection == "Transceiver":
        #         return await self.async_step_setup_transceiver()
        #     elif user_selection == "RF Device":
        #         return await self.async_step_setup_rf_device()
        #     elif user_selection == "Local Device":
        #         return await self.async_step_setup_local_device()
        #
        # list_of_types = ["RF Device", "Local Device"]
        #
        # schema = vol.Schema({vol.Required(CONF_TYPE): vol.In(list_of_types)})
        # return self.async_show_form(step_id="user", data_schema=schema)

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
                        custom_value=True,
                        sort=True,
                    )
                ),
                vol.Required(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE): vol.In(
                    BAUD_RATES
                ),
                vol.Optional(
                    CONF_RECEIVE_PIN, default=DEFAULT_RECEIVE_PIN
                ): NumberSelector(
                    NumberSelectorConfig(min=2, max=3, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_SEND_PIN, default=DEFAULT_SEND_PIN): NumberSelector(
                    NumberSelectorConfig(min=4, max=13, mode=NumberSelectorMode.BOX)
                ),
            }
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

        if errors.get(CONF_SERIAL_PORT) is None:
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
                    await homeduino.disconnect()

                _LOGGER.info("Device %s available", serial_port)
            except serial.SerialException as ex:
                _LOGGER.exception(
                    "Unable to connect to the device %s: %s", serial_port, ex
                )
                errors["base"] = "cannot_connect"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Unable to connect to the device %s: %s", serial_port, ex
                )
                errors["base"] = "cannot_connect"

        # Return title, data, options.
        return (
            f"Homeduino Transceiver {serial_port}",
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
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the setup rf switch step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            title, data, options = await self.validate_input_setup_rf_device(
                user_input, errors
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
                vol.Required(CONF_RF_PROTOCOL, default=""): vol.In(protocol_names),
                vol.Required(CONF_RF_ID): cv.positive_int,
                vol.Optional(CONF_RF_UNIT): cv.positive_int,
                vol.Optional(
                    CONF_RF_ID_IGNORE_ALL,
                    default=False,
                ): bool,
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
        rf_id: int = data.get(CONF_RF_ID)
        rf_unit: int = data.get(CONF_RF_UNIT, None)
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

    async def async_step_setup_local_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            title, data, options = await self.validate_input_setup_local_device(
                user_input, errors
            )

            if not errors:
                return self.async_create_entry(title=title, data=data, options=options)

        if user_input is not None:
            data_schema = self.add_suggested_values_to_schema(
                self._STEP_SETUP_LOCAL_DEVICE_SCHEMA, user_input
            )
        else:
            data_schema = self._STEP_SETUP_LOCAL_DEVICE_SCHEMA

        return self.async_show_form(
            step_id="setup_local_device",
            data_schema=data_schema,
            errors=errors,
        )

    async def validate_input_setup_local_device(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> (str, dict[str, Any], dict[str, Any]):
        """Validate the user input and create data.

        Data has the keys from _step_setup_rf_device_schema with values provided by the user.
        """
        # Validate the data.
        self._STEP_SETUP_LOCAL_DEVICE_SCHEMA(data)

        gpio = data.get(CONF_LOCAL_DEVICE_GPIO)
        device_type = data.get(CONF_LOCAL_DEVICE_TYPE)
        interval = data.get(CONF_LOCAL_DEVICE_INTERVAL)

        if (
            device_type
            in (
                CONF_LOCAL_DEVICE_TYPE_DS18B20,
                CONF_LOCAL_DEVICE_TYPE_ANALOG_INPUT,
                CONF_LOCAL_DEVICE_TYPE_DIGITAL_INPUT,
                CONF_LOCAL_DEVICE_TYPE_DIGITAL_OUTPUT,
                CONF_LOCAL_DEVICE_TYPE_PWM_OUTPUT,
            )
            and interval <= 0
        ):
            errors[CONF_LOCAL_DEVICE_INTERVAL] = "interval_not_set"

        title = ""
        if device_type == CONF_LOCAL_DEVICE_TYPE_DHT11:
            title = f"DHT11 {gpio}"
        elif device_type == CONF_LOCAL_DEVICE_TYPE_DHT22:
            title = f"DHT22 {gpio}"
        elif device_type == CONF_LOCAL_DEVICE_TYPE_DS18B20:
            title = f"DS18B20 {gpio}"
        elif device_type == CONF_LOCAL_DEVICE_TYPE_ANALOG_INPUT:
            title = f"Analog {gpio}"
        elif device_type == CONF_LOCAL_DEVICE_TYPE_DIGITAL_INPUT:
            title = f"Digital {gpio}"
        elif device_type == CONF_LOCAL_DEVICE_TYPE_DIGITAL_OUTPUT:
            title = f"Digital {gpio}"
        elif device_type == CONF_LOCAL_DEVICE_TYPE_PWM_OUTPUT:
            title = f"PWM {gpio}"

        data = {
            CONF_ENTRY_TYPE: device_type,
            CONF_LOCAL_DEVICE_GPIO: gpio,
        }
        options = {}
        if device_type in (
            CONF_LOCAL_DEVICE_TYPE_DS18B20,
            CONF_LOCAL_DEVICE_TYPE_ANALOG_INPUT,
            CONF_LOCAL_DEVICE_TYPE_DIGITAL_INPUT,
            CONF_LOCAL_DEVICE_TYPE_DIGITAL_OUTPUT,
            CONF_LOCAL_DEVICE_TYPE_PWM_OUTPUT,
        ):
            options[CONF_LOCAL_DEVICE_INTERVAL] = interval

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
        entry_type = config_entry.data.get(CONF_ENTRY_TYPE)

        return HomeduinoOptionsFlowHandler(config_entry)


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

        entry_type = self.config_entry.data.get(CONF_ENTRY_TYPE)

        if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_RECEIVE_PIN,
                        default=self.config_entry.options.get(
                            CONF_RECEIVE_PIN, DEFAULT_RECEIVE_PIN
                        ),
                    ): vol.In(range(2, 4)),
                    # ): vol.All(vol.Coerce(int), vol.Range(min=2, max=3)),
                    vol.Optional(
                        CONF_SEND_PIN,
                        default=self.config_entry.options.get(
                            CONF_SEND_PIN, DEFAULT_SEND_PIN
                        ),
                    ): vol.In(range(4, 14)),
                    # ): vol.All(vol.Coerce(int), vol.Range(min=4, max=13)),
                }
            )

            if user_input is not None and len(user_input) > 0:
                return self.async_create_entry(title="", data=user_input)

            return self.async_show_form(
                step_id="init", data_schema=schema, errors=errors
            )

        if entry_type == CONF_ENTRY_TYPE_RF_DEVICE:
            rf_protocol = self.config_entry.data.get(CONF_RF_PROTOCOL)
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_RF_ID_IGNORE_ALL,
                        default=self.config_entry.options.get(
                            CONF_RF_ID_IGNORE_ALL, False
                        ),
                    ): bool,
                }
            )

            if user_input is not None and len(user_input) > 0:
                return self.async_create_entry(title="", data=user_input)

            return self.async_show_form(
                step_id="init", data_schema=schema, errors=errors
            )


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path
