import time

import network


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
