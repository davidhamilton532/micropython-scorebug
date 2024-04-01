import time

import machine
from machine import Pin

import config
import wifi

LED_STATUS = Pin('LED', Pin.OUT)


def main():
    try:
        wifi.connect(config.wifi_ssid, config.wifi_password)
    except Exception as e:
        # sys.print_exception(e)
        print(f'Failed to connect to wifi: {e}')
        print('Resetting in 10 seconds...')
        time.sleep(10)
        machine.reset()


if __name__ == '__main__':
    main()
