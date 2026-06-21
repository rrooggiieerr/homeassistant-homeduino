"""The Homeduino 433 MHz RF transceiver integration."""

import logging

import homeassistant.helpers.config_validation as cv
import serial
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeduino import (
    DEFAULT_BAUD_RATE,
    DEFAULT_REPEATS,
    Homeduino,
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
from .coordinator import HomeduinoCoordinator

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

_service_rf_send_schema: vol.Schema


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

            entry.runtime_data = device.id

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
        if protocol_name.startswith(("contact", "dimmer", "pir", "switch", "weather"))
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
        device_id = entry.runtime_data
        await HomeduinoCoordinator.instance(hass).remove_transceiver(device_id)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Configuration options updated, reloading Homeduino integration")
    entry_type = entry.data.get(CONF_ENTRY_TYPE)
    if entry_type == CONF_ENTRY_TYPE_TRANSCEIVER:
        device_id = entry.runtime_data
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
