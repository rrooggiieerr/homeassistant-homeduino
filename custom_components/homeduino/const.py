"""Constants for the Homeduino 433 MHz RF transceiver integration."""

from typing import Final

DOMAIN: Final = "homeduino"

CONF_ENTRY_TYPE: Final = "entry_type"
CONF_ENTRY_TYPE_TRANSCEIVER: Final = "transceiver"
CONF_ENTRY_TYPE_RF_DEVICE: Final = "rf_device"

CONF_SERIAL_PORT: Final = "serial_port"
CONF_BAUD_RATE: Final = "baud_rate"
CONF_RECEIVE_PIN: Final = "receive_pin"
CONF_SEND_PIN: Final = "send_pin"

CONF_IO_DIGITAL_ = "digital_"
CONF_IO_ANALOG_ = "analog_"
CONF_IO_NONE = "none"
CONF_IO_RF_RECEIVE = "rf_receive"
CONF_IO_RF_SEND = "rf_send"
CONF_IO_DIGITAL_INPUT: Final = "digital_input"
CONF_IO_DIGITAL_OUTPUT: Final = "digital_output"
CONF_IO_PWM_OUTPUT: Final = "pwm_output"
CONF_IO_DHT11: Final = "dht11"
CONF_IO_DHT22: Final = "dht22"
CONF_IO_1_WIRE: Final = "1_wire"

CONF_RF_PROTOCOL: Final = "rf_protocol"
CONF_RF_ID: Final = "rf_id"
CONF_RF_UNIT: Final = "rf_unit"
CONF_RF_ID_IGNORE_ALL: Final = "rf_id_ignore_all"
CONF_RF_REPEATS: Final = "rf_repeats"
