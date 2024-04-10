import gc
import sys
import time
from datetime import datetime, timezone

import machine
import network
import ntptime
import requests
from machine import Pin, SPI
from ssd1309 import Display

import config

STATUS_LED = Pin('LED', Pin.OUT)

RUNNER_1_LED = Pin(8, Pin.OUT)
RUNNER_2_LED = Pin(7, Pin.OUT)
RUNNER_3_LED = Pin(6, Pin.OUT)

BALL_1_LED = Pin(9, Pin.OUT)
BALL_2_LED = Pin(10, Pin.OUT)
BALL_3_LED = Pin(11, Pin.OUT)

STRIKE_1_LED = Pin(12, Pin.OUT)
STRIKE_2_LED = Pin(13, Pin.OUT)

OUT_1_LED = Pin(14, Pin.OUT)
OUT_2_LED = Pin(15, Pin.OUT)

DISPLAY_SCK = Pin(18)
DISPLAY_SDA = Pin(19)
DISPLAY_DC = Pin(17)
DISPLAY_CS = Pin(16)
DISPLAY_RST = Pin(20)
display: Display | None = None


class Team:
    def __init__(self, pk: int):
        self.pk = pk

        data = requests.get(f'https://statsapi.mlb.com/api/v1/teams/{pk}').json()
        self.name = data['teams'][0]['name']
        self.abbreviation = data['teams'][0]['abbreviation']
        del data
        gc.collect()

    def __str__(self):
        return f'({self.abbreviation}) {self.name}'


class Game:
    def __init__(self, pk: int):
        self.pk: int = pk

        data = requests.get(f'https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&gamePk={self.pk}').json()['dates'][0]['games'][0]
        self.home_team: Team = Team(data['teams']['home']['team']['id'])
        self.away_team: Team = Team(data['teams']['away']['team']['id'])
        self.status: str = data['status']['statusCode']
        del data
        gc.collect()

        self.inning: int = 0
        self.top_of_inning: bool = True

        self.home_runs: int = 0
        self.away_runs: int = 0

        self.runners: tuple[bool, bool, bool] = (False, False, False)
        self.balls: int = 0
        self.strikes: int = 0
        self.outs: int = 0

    @property
    def finished(self) -> bool:
        return self.status == 'F'

    @property
    def runner_on_first(self) -> bool:
        return self.runners[0]

    @property
    def runner_on_second(self) -> bool:
        return self.runners[1]

    @property
    def runner_on_third(self) -> bool:
        return self.runners[2]

    def update(self):
        data = requests.get(f'https://statsapi.mlb.com/api/v1/game/{self.pk}/linescore').json()
        self.inning = data['currentInning']
        self.top_of_inning = data['isTopInning']
        self.home_runs = data['teams']['home']['runs']
        self.away_runs = data['teams']['away']['runs']
        self.runners = ('first' in data['offense'], 'second' in data['offense'], 'third' in data['offense'])
        self.balls = data['balls']
        self.strikes = data['strikes']
        self.outs = data['outs']
        del data
        gc.collect()

        data = requests.get(f'https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&gamePk={self.pk}').json()['dates'][0]['games'][0]
        self.status: str = data['status']['statusCode']
        del data
        gc.collect()


def init_display():
    global display
    spi = SPI(0, baudrate=10000000, sck=DISPLAY_SCK, mosi=DISPLAY_SDA)
    display = Display(spi, dc=DISPLAY_DC, cs=DISPLAY_CS, rst=DISPLAY_RST)


def connect_wifi(ssid: str, password: str):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)

    i = 0
    while not wlan.isconnected():
        display.clear()
        display.draw_text8x8(0, 0, f"Connecting{'.' * i}")
        display.present()
        i = (i + 1) % 4
        time.sleep(1)

    display.clear()
    display.draw_text8x8(0, 0, 'Connected:')
    display.draw_text8x8(0, 8, wlan.ifconfig()[0])
    display.present()


def sync_time():
    display.clear()
    display.draw_text8x8(0, 0, 'Syncing')
    display.draw_text8x8(0, 8, 'time...')
    display.present()

    ntptime.settime()

    now = datetime.now(timezone.utc)
    display.clear()
    display.draw_text8x8(0, 0, 'Time Synced:')
    display.draw_text8x8(0, 8, now.date().isoformat())
    display.draw_text8x8(0, 16, now.time().isoformat())
    display.present()


def set_runners(runners: tuple[bool, bool, bool]):
    RUNNER_1_LED.value(int(runners[0]))
    RUNNER_2_LED.value(int(runners[1]))
    RUNNER_3_LED.value(int(runners[2]))


def set_balls(balls: int):
    BALL_1_LED.value(int(balls >= 1))
    BALL_2_LED.value(int(balls >= 2))
    BALL_3_LED.value(int(balls >= 3))


def set_strikes(strikes: int):
    STRIKE_1_LED.value(int(strikes >= 1))
    STRIKE_2_LED.value(int(strikes >= 2))


def set_outs(outs: int):
    OUT_1_LED.value(int(outs >= 1))
    OUT_2_LED.value(int(outs >= 2))


def get_schedule(team_pk: int) -> list[tuple[int, datetime, str, Team, Team]]:
    games = []
    data = requests.get(f'https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&teamId={team_pk}').json()
    for date in data['dates']:
        for game in date['games']:
            games.append((
                game['gamePk'],
                datetime.fromisoformat(game['gameDate'].replace('Z', '+00:00')),
                game['status']['statusCode'],
                Team(game['teams']['home']['team']['id']),
                Team(game['teams']['away']['team']['id'])))

            gc.collect()

    return games


def show_no_games():
    display.clear()
    display.draw_text8x8(0, 0, 'No Games Today!')
    display.draw_text8x8(0, 8, 'Checking again')
    display.draw_text8x8(0, 16, 'in 1 Hour...')
    display.present()


def show_next_game(start_time: datetime, home_team: Team, away_team: Team):
    display.clear()
    display.draw_text8x8(0, 0, 'Next Game:')
    display.draw_text8x8(0, 8, f'{away_team.abbreviation} v {home_team.abbreviation}')
    display.draw_text8x8(0, 16, start_time.date().strftime('%m/%d/%Y'))
    display.draw_text8x8(0, 24, start_time.date().strftime('%H:%M:%S'))
    display.present()


def show_ongoing_game(game: Game, interval: int):
    while not game.finished:
        gc.collect()
        game.update()

        set_runners(game.runners)
        set_balls(game.balls)
        set_strikes(game.strikes)
        set_outs(game.outs)

        display.clear()
        display.draw_text8x8(0, 0, f'{game.away_team.abbreviation}: {game.away_runs}')
        display.draw_text8x8(0, 16, f"{'T' if game.top_of_inning else 'B'}{game.inning}")
        display.draw_text8x8(0, 32, f'{game.home_team.abbreviation}: {game.home_runs}')
        display.present()

        time.sleep(interval)


def show_finished_game(game: Game):
    game.update()

    # turn off all leds
    set_runners((False, False, False))
    set_balls(0)
    set_strikes(0)
    set_outs(0)

    display.clear()
    display.draw_text8x8(0, 0, f'{game.away_team.abbreviation}: {game.away_runs}')
    display.draw_text8x8(0, 16, 'Final')
    display.draw_text8x8(0, 32, f'{game.home_team.abbreviation}: {game.home_runs}')
    display.present()

    time.sleep(3600)


def main():
    try:
        init_display()
        connect_wifi(config.wifi_ssid, config.wifi_password)
        time.sleep(2)
        sync_time()
        time.sleep(2)

        while True:
            gc.collect()

            schedule = sorted(get_schedule(config.team_id), key=lambda x: x[1])
            gc.collect()

            if len(schedule) == 0:
                show_no_games()
                time.sleep(3600)
                continue

            now = datetime.now(timezone.utc)
            started = [x for x in schedule if x[1] <= now]
            upcoming = [x for x in schedule if x[1] > now]

            if len(started) == 0:
                show_next_game(upcoming[0][1], upcoming[0][3], upcoming[0][4])
                time.sleep((upcoming[0][1] - now).total_seconds() + 30)
                continue

            game = Game(started[-1][0])
            if game.finished:
                show_finished_game(game)
                time.sleep(3600)
            else:
                show_ongoing_game(game, config.update_interval)
    except Exception as e:
        sys.print_exception(e)
        if display is not None:
            display.clear()
            display.draw_text8x8(0, 0, 'ERROR')
            display.draw_text8x8(0, 8, 'Resetting in')
            display.draw_text8x8(0, 16, '1 minute...')
            display.present()
        time.sleep(60)
        machine.reset()


if __name__ == '__main__':
    main()
