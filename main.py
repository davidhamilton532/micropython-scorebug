import gc
import sys
import time
from datetime import datetime, timezone, timedelta

import machine
import network
import ntptime
import requests
from machine import Pin, SPI
from ssd1309 import Display
from xglcd_font import XglcdFont

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

FONT_SYS = ('fonts/Wendy7x8.c', 7, 8)
FONT_NORMAL = ('fonts/ArcadePix9x11.c', 9, 11)
FONT_SCORE = ('fonts/PerfectPixel_18x25.c', 18, 25)
font_sys: XglcdFont | None = None
font_normal: XglcdFont | None = None
font_score: XglcdFont | None = None

try:
    local_tz = timezone(timedelta(hours=config.tz_offset))
except Exception as e:
    sys.print_exception(e)
    local_tz = timezone.utc


class Team:
    def __init__(self, pk: int):
        self.pk = pk

        data = requests.get(f'https://statsapi.mlb.com/api/v1/teams/{pk}').json()
        self.name: str = data['teams'][0]['name']
        self.abbreviation: str = data['teams'][0]['abbreviation']
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


def init_fonts():
    global font_sys, font_normal, font_score
    font_sys = XglcdFont(*FONT_SYS)
    font_normal = XglcdFont(*FONT_NORMAL)
    font_score = XglcdFont(*FONT_SCORE)


def reset_leds():
    set_runners((False, False, False))
    set_count(0, 0, 0)


def display_msg(msg: list[str] | str, font: XglcdFont = font_sys):
    if not isinstance(msg, list):
        msg = msg.splitlines()

    display.clear()
    for i, l in enumerate(msg):
        line_len = font.measure_text(l)
        display.draw_text(
            int(display.width / 2) - int(line_len / 2),
            int(display.height / 2) - int((font.height * len(msg)) / 2) + (i * font.height),
            l, font)
    display.present()


def display_sys_msg(msg: list[str] | str):
    display_msg(msg=msg, font=font_sys)


def display_normal_msg(msg: list[str] | str):
    display_msg(msg=msg, font=font_normal)


def connect_wifi(ssid: str, password: str):
    display_sys_msg(f"Connecting...")

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)

    while not wlan.isconnected():
        time.sleep(1)

    display_sys_msg(['Connected:', wlan.ifconfig()[0]])


def sync_time():
    display_sys_msg(f"Syncing time")
    ntptime.settime()
    now = datetime.now(local_tz)
    display_sys_msg(['Time synced:', now.isoformat()])


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


def set_count(balls: int, strikes: int, outs: int):
    set_balls(balls)
    set_strikes(strikes)
    set_outs(outs)


def set_score(home_team: Team, away_team: Team, home_score: int, away_score: int, inning: int = 0, top_of_inning: bool = False, final: bool = False):
    display.clear()

    # draw team abbreviations at top and bottom left corners
    display.draw_text(0, 0, away_team.abbreviation, font_score)
    display.draw_text(0, display.height - font_score.height, home_team.abbreviation, font_score)

    # draw scores at top and bottom right corners
    display.draw_text(display.width - font_score.measure_text(str(away_score)), 0, str(away_score), font_score)
    display.draw_text(display.width - font_score.measure_text(str(home_score)), display.height - font_score.height, str(home_score), font_score)

    # draw inning in the middle of remaining space
    inning_txt = 'F' if final else str(inning)
    x1 = max([font_score.measure_text(home_team.abbreviation), font_score.measure_text(away_team.abbreviation)])
    x2 = min([display.width - font_score.measure_text(str(home_score)), display.width - font_score.measure_text(str(away_score))])
    display.draw_text(
        int((x1 + x2) / 2) - int(font_score.measure_text(inning_txt) / 2),
        int(display.height / 2) - int(font_score.height / 2),
        inning_txt, font_score)

    # draw indicator to show top/bottom of inning
    if not final:
        if top_of_inning:
            display.fill_circle(int((x1 + x2) / 2) - 1, int(font_score.height / 2) - 2, 4)
        else:
            display.fill_circle(int((x1 + x2) / 2) - 1, display.height - int(font_score.height / 2) - 2, 4)

    display.present()


def get_schedule(team_pk: int) -> list[tuple[int, datetime, str, Team, Team]]:
    games = []
    # the data returned by this request just shows games for the current date
    data = requests.get(f'https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&teamId={team_pk}').json()
    for date in data['dates']:
        for game in date['games']:
            game_datetime = datetime.fromisoformat(game['gameDate'].replace('Z', '+00:00')).astimezone(tz=local_tz)
            games.append((
                game['gamePk'],
                game_datetime,
                game['status']['statusCode'],
                Team(game['teams']['home']['team']['id']),
                Team(game['teams']['away']['team']['id'])))

            gc.collect()

    return games


def show_no_games():
    display_sys_msg(['No Games Today!', 'Rechecking in 1 hour...'])


def show_next_game(start_time: datetime, home_team: Team, away_team: Team):
    teams_txt = f'{away_team.abbreviation} @ {home_team.abbreviation}'
    date_txt = f'{start_time.month}/{start_time.day}/{start_time.year}'
    time_txt = f"{((start_time.hour % 12) or 12):02d}:{start_time.minute:02d} {'AM' if start_time.hour < 12 else 'PM'}"
    display_normal_msg([teams_txt, date_txt, time_txt])


def show_game(game: Game):
    set_runners(game.runners)
    set_count(game.balls, game.strikes, game.outs)
    set_score(game.home_team, game.away_team, game.home_runs, game.away_runs, inning=game.inning, top_of_inning=game.top_of_inning)


def show_final(game: Game):
    reset_leds()
    set_score(game.home_team, game.away_team, game.home_runs, game.away_runs, final=True)


def main():
    try:
        init_display()
        init_fonts()
        connect_wifi(config.wifi_ssid, config.wifi_password)
        sync_time()

        display_sys_msg('Loading schedule...')
        while True:
            gc.collect()

            schedule = sorted(get_schedule(config.team_id), key=lambda x: x[1])
            gc.collect()

            if len(schedule) == 0:
                show_no_games()
                print('Sleeping 1 hour...')
                time.sleep(3600)
                continue

            now = datetime.now(local_tz)
            started = [x for x in schedule if x[1] <= now]
            upcoming = [x for x in schedule if x[1] > now]

            if len(started) == 0:
                show_next_game(upcoming[0][1], upcoming[0][3], upcoming[0][4])
                print(f'Sleeping {(upcoming[0][1] - now).total_seconds()} seconds...')
                time.sleep((upcoming[0][1] - now).total_seconds())
                continue

            game = Game(started[-1][0])
            while not game.finished:
                game.update()
                show_game(game)
                print(f'Sleeping {config.update_interval} seconds...')
                time.sleep(config.update_interval)
                gc.collect()

            game.update()
            show_final(game)
            print('Sleeping 1 hour...')
            time.sleep(3600)
    except Exception as e:
        sys.print_exception(e)
        reset_leds()
        if display is not None:
            display_sys_msg([
                '!!! ERROR !!!',
                '',
                'An error occurred.',
                'Resetting in 1 minute...'])
        print('Sleeping 1 minute...')
        time.sleep(60)
        machine.reset()


if __name__ == '__main__':
    main()
