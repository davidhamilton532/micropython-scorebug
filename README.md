# micropython-scorebug
This repository serves to host the code for a personal electronics project to create a wall-mountable, semi-live updating scorebug following a configured MLB team.

Once configured and running, the scorebug device will periodically poll the MLB Stats API for the configured team's schedule and do one of the following:
1. Display that there are no games today.
2. Display the score, count, and runners for an in-progress game, updated periodically.
3. Display the start time of the next game today.
4. Display the final score of the last completed game today.

## Dependencies
The following packages are required to be installed on the device:
- datetime
- [micropython-ssd1309](https://github.com/rdagger/micropython-ssd1309)

These packages can be installed using `mip.install()` from either the [micropython-stdlib](https://github.com/micropython/micropython-lib) or their linked repository.

## Configuration
To configure the application, rename `config.example.py` to `config.py` and set values for the following variables:
- `team_id`: This is the MLB team ID as returned by the [MLB Stats API](https://statsapi.mlb.com/api/v1/teams/?sportId=1) (default: `136` - Seattle Mariners)
- `tz_offset`: This is the offset in hours from UTC for the local timezone (default: `-7` - Pacific Time)
- `update_interval`: This is how many seconds to wait between fetching updates for an ongoing game (default: `60`)
- `wifi_ssid`: This is the network SSID to connect to
- `wifi_password`: This is the password to use for authentication

## Hardware
This project requires the following:
- 1x Raspberry Pi Pico W + power source (USB, battery, etc.)
- 1x SSD1309 SPI display
- 3x Green LEDs
- 5x Yellow LEDS
- 2x Red LEDs

### Schematic
![Schematic](https://i.imgur.com/4w5ZDb3.png)

## Copyright Notice
This project and its author are not affiliated with MLB or any MLB team.

This project interfaces with MLB's Stats API.

Use of MLB data is subject to the notice posted at http://gdx.mlb.com/components/copyright.txt.
