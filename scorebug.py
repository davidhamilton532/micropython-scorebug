from machine import Pin

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


def set_runners(first: bool, second: bool, third: bool):
    LED_RUNNER_1.value(int(first))
    LED_RUNNER_2.value(int(second))
    LED_RUNNER_3.value(int(third))


def set_balls(balls: int):
    LED_BALL_1.value(int(balls > 1))
    LED_BALL_2.value(int(balls > 2))
    LED_BALL_3.value(int(balls > 3))


def set_strikes(strikes: int):
    LED_STRIKE_1.value(int(strikes > 1))
    LED_STRIKE_2.value(int(strikes > 2))


def set_outs(outs: int):
    LED_OUT_1.value(int(outs > 1))
    LED_OUT_2.value(int(outs > 2))
