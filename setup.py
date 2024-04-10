import time

import mip
import network

import config


def setup():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config.wifi_ssid, config.wifi_password)
    while not wlan.isconnected():
        time.sleep(1)

    mip.install('datetime')
    mip.install('https://github.com/rdagger/micropython-ssd1309/raw/master/ssd1309.py')
    mip.install('https://github.com/rdagger/micropython-ssd1309/raw/master/xglcd_font.py')


if __name__ == '__main__':
    setup()
