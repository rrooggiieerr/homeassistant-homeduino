# Home Assistant integration for Homeduino RF 433 MHz transceivers

![Python][python-shield]
[![GitHub Release][releases-shield]][releases]
[![Licence][license-shield]][license]
[![Maintainer][maintainer-shield]][maintainer]
[![Home Assistant][homeassistant-shield]][homeassistant]
[![HACS][hacs-shield]][hacs]  
[![GitHub Sponsors][github-shield]][github]
[![PayPal][paypal-shield]][paypal]
[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]
[![Patreon][patreon-shield]][patreon]

## Introduction

Home Assistant integration for using various 433 MHz devices and sensors with a connected Arduino
Nano with [homeduino sketch](https://github.com/pimatic/homeduino).

This plugins supports all 433 MHz devices with [rfcontrolpy](https://github.com/rrooggiieerr/rfcontrolpy/)
[protocol implementations](https://github.com/rrooggiieerr/rfcontrolpy/blob/master/protocols.md).

## Features

* Sending and receiveing RF commands
* Supports RF switches, lights, motion and weather sensors
* Read and write local IO connected to the Arduino Nano
* Reading DHT11/DHT22 sensors connected to the Arduino Nano
* Allows multiple Homeduinos to be connected

## Hardware

A Homeduino exists of an Arduino Nano with homeduino sketch. An 433 MHz RF transmitter and receiver
can be connected to communicate with 433 MHz devices and local IO can be used to read inputs or
switch relays.

![image](https://raw.githubusercontent.com/rrooggiieerr/homeassistant-homeduino/main/homeduino1.jpg)
![image](https://raw.githubusercontent.com/rrooggiieerr/homeassistant-homeduino/main/homeduino2.jpg)

## Installation

### HACS

The recommended way to install this Home Assistant integration is by using [HACS][hacs].
Click the following button to open the integration directly on the HACS integration page.

[![Install Homeduino from HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rrooggiieerr&repository=homeassistant-homeduino&category=integration)

Or follow these instructions:

- Go to your **HACS** view in Home Assistant and then to **Integrations**
- Open the **Custom repositories** menu
- Add this repository URL to the **Custom repositories** and select
**Integration** as the **Category**
- Click **Add**
- Close the **Custom repositories** menu
- Select **+ Explore & download repositories** and search for *Homeduino*
- Select **Download**
- Restart Home Assistant

### Manually

- Copy the `custom_components/homeduino` directory of this repository into the
`config/custom_components/` directory of your Home Assistant installation
- Restart Home Assistant

## Adding a new Homeduino Transceiver

- After restarting go to **Settings** then **Devices & Services**
- Select **+ Add integration** and type in *Homeduino*
- Choose *Homeduino Transceiver*
- Select the *Serial port* or enter the path manually
- Select the *Baud rate*
- Define which digital and analog IO should be enabled.
- Select **Submit**

When your wiring is right a new Homeduino integration and device will now
be added to your Integrations view. If your wiring is not right you will get a
*Failed to connect* error message.

### Digital and analog IO

The Arduino Nano suports 12 digital IO and 8 analog inputs which can be used by the Homeduino integration

The digital IO can be configured as:
- RF receiver on digital IO 2 or 3
- RF sender on all digital IO
- Digital input on digital IO 2 till 12
- Digital output on all digital IO
- PWM output on digital IO 3, 5, 6, 9, 10 and 11 
- DHT11/DHT22 sensor on difital IO 2 till 12

The analog input reads a value between 0V and 5V and reports the measured value as a value between 0 and 1023. You can use a template sensor to use this value according to your needs.

## Adding a new RF Device

- After adding your Homeduino go to **Settings** then **Devices & Services**
- Select **+ Add integration** and type in *Homeduino*
- Choose *RF Device*
- Select the *Protocol* and give the *Device ID* and *Device unit* for your device
- Select **Submit**

## Actions

The integration supports actions so commands can be send which are (not yet) implemented.

`homeduino.send`
This action allows you to send any supported command to the Homeduino Transceiver.

```
action: homeduino.send
data:
  device_id: 9889db9c137907826b591de9390fc584
  command: RF send 4 3 453 1992 88 9228 0 0 0 0 01020102020201020101010101010102010101010202010202020202010102010102020203
```

`homeduino.rf_send`
This action allows you to send a RF command for supported protocols.

```
action: homeduino.rf_send
data:
  protocol: switch1
  id: 98765
  unit: 0
  state: true
  all: false
```

`homeduino.raw_rf_send`
This action allows you to send a raw RF command for unsupported protocols.

```
action: homeduino.raw_rf_send
data:
  command: 268 1282 2632 10168 0 0 0 0 020001000100010001000100010001000100010100010000010001000100010001000101000100010000010001010001000001010000010100000101000001000103
```

## Contribution and appreciation

You can contribute to this integration, or show your appreciation, in the following ways.

### Contribute your language

If you would like to use this Home Assistant integration in your own language you can provide a
translation file as found in the `custom_components/homeduino/translations` directory. Create a
pull request (preferred) or issue with the file attached.

More on translating custom integrations can be found
[here](https://developers.home-assistant.io/docs/internationalization/custom_integration/).

### Star this integration

Help other Home Assistant and Homeduino users find this integration by starring this GitHub page.
Click **⭐ Star** on the top right of the GitHub page.

### Support my work

Do you enjoy using this Home Assistant integration? Then consider supporting my work using one of
the following platforms, your donation is greatly appreciated and keeps me motivated:

[![GitHub Sponsors][github-shield]][github]
[![PayPal][paypal-shield]][paypal]
[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]
[![Patreon][patreon-shield]][patreon]

### Home Assistant support

[Let me answer your Home Assistant questions](https://buymeacoffee.com/rrooggiieerr/e/447353). During
a 1 hour Q&A session I help you solve your Home Assistant related issues with.

What can be done in one hour:
- Home Assistant walktrough, I explain you where is what in the Home Assistant UI
- Install and configure a Home Assistant integration
- Explain and create scenes
- Explain and create a simple automations
- Install a ZHA quirk, to make your unsupported Zigbee device work in Home Assistant

What takes more time:
- Depending on the severity I might be able to help you with recovering your crashed Home Assistant
- Support for Home Assistant Integration developers

### Hire me

If you would like to have a Home Assistant integration developed for your product or are in need
of a freelance Python developer for your project please contact me, you can find my email address
on [my GitHub profile](https://github.com/rrooggiieerr).

[python-shield]: https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54
[releases]: https://github.com/rrooggiieerr/homeassistant-homeduino/releases
[releases-shield]: https://img.shields.io/github/v/release/rrooggiieerr/homeassistant-homeduino?style=for-the-badge
[license]: ./LICENSE
[license-shield]: https://img.shields.io/github/license/rrooggiieerr/homeassistant-homeduino?style=for-the-badge
[maintainer]: https://github.com/rrooggiieerr
[maintainer-shield]: https://img.shields.io/badge/MAINTAINER-%40rrooggiieerr-41BDF5?style=for-the-badge
[homeassistant]: https://www.home-assistant.io/
[homeassistant-shield]: https://img.shields.io/badge/home%20assistant-%2341BDF5.svg?style=for-the-badge&logo=home-assistant&logoColor=white
[hacs]: https://hacs.xyz/
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[paypal]: https://paypal.me/seekingtheedge
[paypal-shield]: https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white
[buymecoffee]: https://www.buymeacoffee.com/rrooggiieerr
[buymecoffee-shield]: https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black
[github]: https://github.com/sponsors/rrooggiieerr
[github-shield]: https://img.shields.io/badge/sponsor-30363D?style=for-the-badge&logo=GitHub-Sponsors&logoColor=#EA4AAA
[patreon]: https://www.patreon.com/seekingtheedge/creators
[patreon-shield]: https://img.shields.io/badge/Patreon-F96854?style=for-the-badge&logo=patreon&logoColor=white
