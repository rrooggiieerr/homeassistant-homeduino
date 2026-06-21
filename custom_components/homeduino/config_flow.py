"""Config flow for Homeduino 433 MHz RF transceiver integration."""

import logging
import os
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
)
from homeduino import (
    BAUD_RATES,
    DEFAULT_BAUD_RATE,
    DEFAULT_RECEIVE_PIN,
    DEFAULT_REPEATS,
    DEFAULT_SEND_PIN,
    Homeduino,
    HomeduinoNotReadyError,
    HomeduinoResponseTimeoutError,
)
from serial.serialutil import SerialException

from . import HomeduinoCoordinator
from .const import (
    CONF_BAUD_RATE,
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_RF_DEVICE,
    CONF_ENTRY_TYPE_TRANSCEIVER,
    CONF_IO_ANALOG_,
    CONF_IO_DHT11,
    CONF_IO_DHT22,
    CONF_IO_DIGITAL_,
    CONF_IO_DIGITAL_INPUT,
    CONF_IO_DIGITAL_OUTPUT,
    CONF_IO_NONE,
    CONF_IO_PWM_OUTPUT,
    CONF_IO_RF_RECEIVE,
    CONF_IO_RF_SEND,
    CONF_RF_ID,
    CONF_RF_ID_IGNORE_ALL,
    CONF_RF_PROTOCOL,
    CONF_RF_REPEATS,
    CONF_RF_UNIT,
    CONF_SERIAL_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_DIGITAL_IO = [
    CONF_IO_RF_SEND,
    CONF_IO_DIGITAL_INPUT,
    CONF_IO_DIGITAL_OUTPUT,
]
_DIGITAL_IO_DEVICES = [
    CONF_IO_DHT11,
    CONF_IO_DHT22,
    # CONF_IO_1_WIRE,
]


def build_transceiver_options_schema() -> {}:
    schema = {}

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

        options += _DIGITAL_IO_DEVICES

        default = CONF_IO_NONE
        if digital_io == DEFAULT_RECEIVE_PIN:
            default = CONF_IO_RF_RECEIVE
        if digital_io == DEFAULT_SEND_PIN:
            default = CONF_IO_RF_SEND

        schema[vol.Optional(f"{CONF_IO_DIGITAL_}{digital_io}", default=default)] = (
            SelectSelector(
                SelectSelectorConfig(
                    options=options,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="digital_io",
                )
            )
        )

    schema[vol.Optional(f"{CONF_IO_DIGITAL_}13", default=CONF_IO_NONE)] = (
        SelectSelector(
            SelectSelectorConfig(
                options=[
                    CONF_IO_NONE,
                    CONF_IO_RF_SEND,
                    CONF_IO_DIGITAL_OUTPUT,
                ],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="digital_io",
            )
        )
    )

    for analog_input in range(0, 8):
        schema[vol.Optional(f"{CONF_IO_ANALOG_}{analog_input}")] = BooleanSelector()

    return schema


STEP_SETUP_TRANSCEIVER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT, default=""): SerialPortSelector(),
        vol.Required(CONF_BAUD_RATE, default=str(DEFAULT_BAUD_RATE)): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=str(baud_rate), label=f"{baud_rate:n} Bd")
                    for baud_rate in BAUD_RATES
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
).extend(build_transceiver_options_schema())
TRANSCEIVER_OPTIONS_SCHEMA = vol.Schema(build_transceiver_options_schema())

STEP_SETUP_RF_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_RF_PROTOCOL, default=""): SelectSelector(
            SelectSelectorConfig(
                options=[
                    protocol_name
                    for protocol_name in Homeduino.get_protocols()
                    if protocol_name.startswith(
                        ("contact", "dimmer", "pir", "switch", "weather")
                    )
                ],
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
RF_DEVICE_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_RF_ID_IGNORE_ALL): BooleanSelector(),
        vol.Optional(CONF_RF_REPEATS, default=DEFAULT_REPEATS): NumberSelector(
            NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


class HomeduinoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homeduino 433 MHz RF transceiver."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Test if we already have a Homeduino transceiver configured
        if not HomeduinoCoordinator.instance(self.hass).has_transceiver():
            return await self.async_step_setup_transceiver(user_input)

        return self.async_show_menu(
            step_id="user",
            menu_options=["setup_transceiver", "setup_rf_device"],
        )

    async def async_step_setup_transceiver(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the setup transceiver step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the data can be used to set up a connection.
            STEP_SETUP_TRANSCEIVER_SCHEMA(user_input)

            serial_port = user_input.get(CONF_SERIAL_PORT)
            baud_rate = int(user_input[CONF_BAUD_RATE])

            await self.async_set_unique_id(f"{DOMAIN}-{serial_port}")
            self._abort_if_unique_id_configured()

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
                _LOGGER.exception("Unable to connect to the device %s", serial_port)
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unable to connect to the device %s", serial_port)
                errors["base"] = "cannot_connect"

            if not errors:
                title = f"Homeduino Transceiver {serial_port}"
                data = {
                    CONF_ENTRY_TYPE: CONF_ENTRY_TYPE_TRANSCEIVER,
                    CONF_SERIAL_PORT: serial_port,
                    CONF_BAUD_RATE: baud_rate,
                }

                options = {}

                for digital_io in range(2, 14):
                    key = CONF_IO_DIGITAL_ + str(digital_io)
                    value = user_input.get(key)
                    if value == CONF_IO_NONE:
                        value = None
                    options[key] = value

                for analog_input in range(0, 8):
                    key = CONF_IO_ANALOG_ + str(analog_input)
                    options[key] = user_input.get(key)

                return self.async_create_entry(title=title, data=data, options=options)

        # Combine user input with schema.
        data_schema = self.add_suggested_values_to_schema(
            STEP_SETUP_TRANSCEIVER_SCHEMA, user_input or {}
        )

        return self.async_show_form(
            step_id="setup_transceiver",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_setup_rf_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the setup rf switch step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the data.
            STEP_SETUP_RF_DEVICE_SCHEMA(user_input)

            rf_protocol: str = user_input.get(CONF_RF_PROTOCOL).strip()
            rf_id: int = int(user_input.get(CONF_RF_ID))
            rf_unit: int = user_input.get(CONF_RF_UNIT, None)
            if rf_unit is not None:
                rf_unit = int(rf_unit)
            rf_id_ignore_all: bool = user_input.get(CONF_RF_ID_IGNORE_ALL, False)

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

            if not errors:
                return self.async_create_entry(title=title, data=data, options=options)

        data_schema = self.add_suggested_values_to_schema(
            STEP_SETUP_RF_DEVICE_SCHEMA, user_input or {}
        )

        return self.async_show_form(
            step_id="setup_rf_device",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return HomeduinoOptionsFlowHandler()


class HomeduinoOptionsFlowHandler(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        entry_type = self.config_entry.data.get(CONF_ENTRY_TYPE)

        data_schema: vol.Schema
        if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
            data_schema = TRANSCEIVER_OPTIONS_SCHEMA
        elif entry_type == CONF_ENTRY_TYPE_RF_DEVICE:
            data_schema = RF_DEVICE_OPTIONS_SCHEMA

        if user_input is not None:
            data_schema(user_input)

            if entry_type == CONF_ENTRY_TYPE_RF_DEVICE:
                user_input[CONF_RF_REPEATS] = int(
                    user_input.get(CONF_RF_REPEATS, DEFAULT_REPEATS)
                )

            return self.async_create_entry(title="", data=user_input)

        data_schema = self.add_suggested_values_to_schema(
            data_schema, user_input or self.config_entry.options
        )

        return self.async_show_form(
            step_id=entry_type, data_schema=data_schema, errors=errors
        )

    async def async_step_transceiver(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_init(user_input)

    async def async_step_rf_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
