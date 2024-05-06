# Home Assistant integration for Homeduino RF 433 MHz transceivers

![Python][python-shield]
[![GitHub Release][releases-shield]][releases]
[![Licence][license-badge]][license]
[![Home Assistant][homeassistant-shield]][homeassistant]
[![HACS][hacs-shield]][hacs]  
[![Github Sponsors][github-shield]][github]
[![PayPal][paypal-shield]][paypal]
[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]
[![Patreon][patreon-shield]][patreon]

## Introduction

Home Assistant integration for using various 433 MHz devices and sensors with a connected Arduino
with homeduino sketch.

This plugins supports all 433 MHz devices with [rfcontrolpy](https://github.com/rrooggiieerr/rfcontrolpy/)
[protocol implementations](https://github.com/rrooggiieerr/rfcontrolpy/blob/master/protocols.md).

## Features

## Hardware

ToDo

## Installation

### HACS

The recomended way to install this Home Assistant integration is using by [HACS][hacs].
Click the following button to open the integration directly on the HACS integration page.

[![Install XY Screens from HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rrooggiieerr&repository=homeassistant-homeduino&category=integration)

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

## Adding a new Homeduino

- After restarting go to **Settings** then **Devices & Services**
- Select **+ Add integration** and type in *Homeduino*
- Select the *Serial port* or enter the path manually
- Select **Submit**

When your wiring is right a new Homeduino integration and device will now
be added to your Integrations view. If your wiring is not right you will get a
*Failed to connect* error message.

## Adding a new RF Actor

- After adding your Homeduino go to **Settings** then **Devices & Services**
- Select **+ Add integration** and type in *Homeduino*
- Select the *Protocol* and give the *Device ID* and *Device unit* for your device
- Select **Submit**

## Contributing

If you would like to use this Home Assistant integration in youw own language you can provide me
with a translation file as found in the `custom_components/axaremote/translations` directory.
Create a pull request (preferred) or issue with the file attached.

More on translating custom integrations can be found
[here](https://developers.home-assistant.io/docs/internationalization/custom_integration/).

## Support my work

Do you enjoy using this Home Assistant integration? Then consider supporting my work using one of
the following platforms:

[![Github Sponsors][github-shield]][github]
[![PayPal][paypal-shield]][paypal]
[![BuyMeCoffee][buymecoffee-shield]][buymecoffee]
[![Patreon][patreon-shield]][patreon]

---

[python-shield]: https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54
[releases]: https://github.com/rrooggiieerr/homeassistant-axaremote/releases
[releases-shield]: https://img.shields.io/github/v/release/rrooggiieerr/homeassistant-axaremote?style=for-the-badge
[license]: ./LICENSE
[license-badge]: https://img.shields.io/github/license/rrooggiieerr/homeassistant-axaremote?style=for-the-badge
[homeassistant]: https://www.home-assistant.io/
[homeassistant-shield]: https://img.shields.io/badge/home%20assistant-%2341BDF5.svg?style=for-the-badge&logo=home-assistant&logoColor=white
[hacs]: https://hacs.xyz/
[hacs-shield]: https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge
[paypal]: https://paypal.me/seekingtheedge
[paypal-shield]: https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white
[buymecoffee]: https://www.buymeacoffee.com/rrooggiieerr
[buymecoffee-shield]: https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black
[github]: https://github.com/sponsors/rrooggiieerr
[github-shield]: https://img.shields.io/badge/sponsor-30363D?style=for-the-badge&logo=GitHub-Sponsors&logoColor=#EA4AAA
[patreon]: https://www.patreon.com/seekingtheedge/creators
[patreon-shield]: https://img.shields.io/badge/Patreon-F96854?style=for-the-badge&logo=patreon&logoColor=white
