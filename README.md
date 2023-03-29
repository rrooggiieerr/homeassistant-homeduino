# Home Assistant Homeduino integration

Home Assistant integration for using various 433 MHz devices and sensors with a
connected Arduino with homeduino sketch.

This plugins supports all 433 MHz devices with [rfcontrolpy]((https://github.com/rrooggiieerr/rfcontrolpy/) [protocol implementations](https://github.com/rrooggiieerr/rfcontrolpy/blob/master/protocols.md).

## Hardware

ToDo

## Installation

### HACS
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

##  Adding a new Homeduino
- After restarting go to **Settings** then **Devices & Services**
- Select **+ Add integration** and type in *Homeduino*
- Select the serial port or enter the path manually
- Select **Submit**

When your wiring is right a new Homeduino integration and device will now
be added to your Integrations view. If your wiring is not right you will get a
*Failed to connect* error message.

Do you enjoy using this Home Assistant integration? Then consider supporting
my work:\
[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" >](https://www.buymeacoffee.com/rrooggiieerr)  
