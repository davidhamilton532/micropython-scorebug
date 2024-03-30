import time

import machine
import network
from machine import Pin

import config

LED_RUNNER_1 = Pin(6, Pin.OUT)
LED_RUNNER_2 = Pin(7, Pin.OUT)
LED_RUNNER_3 = Pin(8, Pin.OUT)

LED_BALL_1 = Pin(9, Pin.OUT)
LED_BALL_2 = Pin(10, Pin.OUT)
LED_BALL_3 = Pin(11, Pin.OUT)

LED_STRIKE_1 = Pin(12, Pin.OUT)
LED_STRIKE_2 = Pin(13, Pin.OUT)

LED_OUT_1 = Pin(14, Pin.OUT)
LED_OUT_2 = Pin(15, Pin.OUT)

SPI_CS = Pin(16, Pin.OUT)
SPI_DC = Pin(17, Pin.OUT)
SPI_SCK = Pin(18, Pin.OUT)
SPI_SDA = Pin(19, Pin.OUT)
SPI_RES = Pin(20, Pin.OUT)

LED_STATUS = Pin('LED', Pin.OUT)


def connect(ssid: str, password: str) -> str:
    """
    Connect to WiFi and return the received IP address.

    :param ssid: the ssid of the network to connect to
    :param password: the password to authentication with the network
    :returns: IP address
    :rtype: str
    """

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)

    # give it 10 seconds before timing out
    i = 0
    while not wlan.isconnected() and i < 10:
        i += 1
        time.sleep(1)

    if not wlan.isconnected():
        raise Exception('connection timed out')

    return wlan.ifconfig()[0]


def main():
    try:
        print('Connecting...')
        ip = connect(config.wifi_ssid, config.wifi_password)
        print(f'Connected on {ip}')
        del ip

        # enable status led to show we're online
        LED_STATUS.on()
    except Exception as e:
        # sys.print_exception(e)
        print(f'Failed to connect to wifi: {e}')
        print('Resetting in 10 seconds...')
        time.sleep(10)
        machine.reset()


if __name__ == '__main__':
    main()
