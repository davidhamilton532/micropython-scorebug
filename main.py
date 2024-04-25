import gc
import sys
import time
from datetime import datetime, timezone, timedelta

import network
import ntptime
import requests
from machine import Pin, SPI, reset
from ssd1309 import Display
from xglcd_font import XglcdFont

import config

status_led: Pin = Pin('LED', Pin.OUT)
runner_leds: tuple[Pin, Pin, Pin] = (Pin(8, Pin.OUT), Pin(7, Pin.OUT), Pin(6, Pin.OUT))
balls_leds: tuple[Pin, Pin, Pin] = (Pin(9, Pin.OUT), Pin(10, Pin.OUT), Pin(11, Pin.OUT))
strikes_leds: tuple[Pin, Pin] = (Pin(12, Pin.OUT), Pin(13, Pin.OUT))
outs_leds: tuple[Pin, Pin] = (Pin(14, Pin.OUT), Pin(15, Pin.OUT))

display = Display(spi=SPI(0, baudrate=10000000, sck=Pin(18), mosi=Pin(19)), dc=Pin(17), cs=Pin(16), rst=Pin(20))
sm_font = XglcdFont('fonts/Wendy7x8.c', 7, 8)
md_font = XglcdFont('fonts/ArcadePix9x11.c', 9, 11)
lg_font = XglcdFont('fonts/PerfectPixel_18x25.c', 18, 25)

try:
    local_tz = timezone(timedelta(hours=config.tz_offset))
except:
    print('Failed to set local timezone - defaulting to UTC')
    local_tz = timezone.utc


class Team:
    def __init__(self, _id: int, **kwargs):
        self.id: int = _id
        self.name: str | None = kwargs.get('name')
        self.abbreviation: str | None = kwargs.get('abbreviation')
        self.runs: int = kwargs.get('runs', 0)

    def __str__(self):
        return f'Team<{self.id}>'

    def refresh(self):
        data = requests.get(f'https://statsapi.mlb.com/api/v1/teams/{self.id}').json()['teams'][0]
        self.name = data['name']
        self.abbreviation = data['abbreviation']
        del data
        gc.collect()


class Game:
    def __init__(self, _id: int, **kwargs):
        self.id: int = _id
        self.start_time: datetime | None = kwargs.get('start_time')
        self.status: str | None = kwargs.get('status')
        self.inning: int = kwargs.get('inning', 1)
        self.top_of_inning: bool = kwargs.get('top_of_inning', True)
        self.home_team: Team | None = kwargs.get('home_team')
        self.away_team: Team | None = kwargs.get('away_team')
        self.runners: tuple[bool, bool, bool] = kwargs.get('runners', (False, False, False))
        self.balls: int = kwargs.get('balls', 0)
        self.strikes: int = kwargs.get('strikes', 0)
        self.outs: int = kwargs.get('outs', 0)

    def __str__(self):
        return f'Game<{self.id}>'

    @property
    def is_upcoming(self) -> bool:
        return not self.is_in_progress and not self.is_finished

    @property
    def is_in_progress(self) -> bool:
        return self.status in ('I', 'L')

    @property
    def is_finished(self) -> bool:
        return self.status in ('O', 'F')

    def refresh(self):
        data = requests.get(f'https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&gamePk={self.id}'
                            ).json()['dates'][0]['games'][0]
        self.status = data['status']['abstractGameCode']
        del data
        gc.collect()

        data = requests.get(f'https://statsapi.mlb.com/api/v1/game/{self.id}/linescore').json()
        self.inning = data['currentInning']
        self.top_of_inning = data['isTopInning']
        self.home_team.runs = data['teams']['home']['runs']
        self.away_team.runs = data['teams']['away']['runs']
        self.runners = ('first' in data['offense'], 'second' in data['offense'], 'third' in data['offense'])
        self.balls = data['balls']
        self.strikes = data['strikes']
        self.outs = data['outs']
        del data
        gc.collect()


def parse_datetime(date_str: str) -> datetime:
    date_str = date_str.replace('Z', '+00:00')
    return datetime.fromisoformat(date_str).astimezone(tz=local_tz)


def display_msg(msg: list[str] | str, font: XglcdFont = sm_font, console: bool = False):
    if not isinstance(msg, list):
        msg = msg.splitlines()

    display.clear()

    for i, l in enumerate(msg):
        line_len = font.measure_text(l)
        display.draw_text(
            int(display.width / 2) - int(line_len / 2),
            int(display.height / 2) - int((font.height * len(msg)) / 2) + (i * font.height),
            l, font)

        if console:
            print(l)

    display.present()


def display_game(game: Game):
    if game.is_upcoming:
        time_txt = f'{((game.start_time.hour % 12) or 12):02d}:{game.start_time.minute:02d}'
        am_pm_txt = f"{'AM' if game.start_time.hour < 12 else 'PM'}"
        set_leds_off()
        display_msg(msg=[f'{game.away_team.abbreviation} @ {game.home_team.abbreviation}',
                         f'{game.start_time.month}/{game.start_time.day}/{game.start_time.year}',
                         f'{time_txt} {am_pm_txt}'], font=md_font)
    else:
        if game.is_finished:
            set_leds_off()
        elif game.outs < 3:
            set_led_runners(game.runners)
            set_led_balls(game.balls)
            set_led_strikes(game.strikes)
            set_led_outs(game.outs)
        else:
            set_leds_off(outs=False)
            set_led_outs(game.outs)

        display.clear()

        # draw team abbreviations at top and bottom left corners
        display.draw_text(0, 0, game.away_team.abbreviation, lg_font)
        display.draw_text(0, display.height - lg_font.height, game.home_team.abbreviation, lg_font)

        # draw scores at top and bottom right corners
        display.draw_text(display.width - lg_font.measure_text(str(game.away_team.runs)),
                          0, str(game.away_team.runs), lg_font)
        display.draw_text(display.width - lg_font.measure_text(str(game.home_team.runs)),
                          display.height - lg_font.height, str(game.home_team.runs), lg_font)

        # calculate middle of remaining space
        x1 = max([lg_font.measure_text(game.home_team.abbreviation),
                  lg_font.measure_text(game.away_team.abbreviation)])
        x2 = min([display.width - lg_font.measure_text(str(game.home_team.runs)),
                  display.width - lg_font.measure_text(str(game.away_team.runs))])

        if game.is_in_progress:
            # draw inning in the middle of remaining space
            display.draw_text(int((x1 + x2) / 2) - int(lg_font.measure_text(str(game.inning)) / 2),
                              int(display.height / 2) - int(lg_font.height / 2), str(game.inning), lg_font)

            # draw indicator for top/bottom of inning
            if game.top_of_inning:
                display.fill_circle(int((x1 + x2) / 2), 12, 4)
            else:
                display.fill_circle(int((x1 + x2) / 2), display.height - 12, 4)
        else:
            # draw final indicator in middle of remaining space
            display.draw_text(int((x1 + x2) / 2) - int(lg_font.measure_text('F') / 2),
                              int(display.height / 2) - int(lg_font.height / 2), 'F', lg_font)

        display.present()


def set_led_runners(runners: tuple[bool, bool, bool]):
    for i, led in enumerate(runner_leds):
        led.value(int(runners[i]))


def set_led_balls(balls: int):
    for i, led in enumerate(balls_leds):
        led.value(int(balls > i))


def set_led_strikes(strikes: int):
    for i, led in enumerate(strikes_leds):
        led.value(int(strikes > i))


def set_led_outs(outs: int):
    for i, led in enumerate(outs_leds):
        led.value(int(outs > i))


def set_leds_off(runners=True, balls=True, strikes=True, outs=True):
    if runners:
        set_led_runners((False, False, False))
    if balls:
        set_led_balls(0)
    if strikes:
        set_led_strikes(0)
    if outs:
        set_led_outs(0)


def get_schedule(team_id: int) -> tuple[list[Game], list[Game]]:
    started = []
    upcoming = []

    now = datetime.now(tz=local_tz)
    data = requests.get(f'https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&teamId={team_id}').json()
    for date in data['dates']:
        for game in date['games']:
            game_datetime = parse_datetime(game['gameDate'])
            if game_datetime <= now:
                started.append(Game(
                    _id=game['gamePk'],
                    start_time=game_datetime,
                    status=game['status']['abstractGameCode'],
                    home_team=Team(_id=game['teams']['home']['team']['id']),
                    away_team=Team(_id=game['teams']['away']['team']['id'])))
            else:
                upcoming.append(Game(
                    _id=game['gamePk'],
                    start_time=game_datetime,
                    status=game['status']['abstractGameCode'],
                    home_team=Team(_id=game['teams']['home']['team']['id']),
                    away_team=Team(_id=game['teams']['away']['team']['id'])))

    del data
    gc.collect()

    return sorted(started, key=lambda x: x.start_time), sorted(upcoming, key=lambda x: x.start_time)


def init():
    # connect wifi
    display_msg('Connecting...', console=True)

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config.wifi_ssid, config.wifi_password)

    while not wlan.isconnected():
        time.sleep(1)

    display_msg(['Connected:', wlan.ifconfig()[0]], console=True)

    # sync time
    display_msg('Syncing time...', console=True)
    ntptime.settime()
    display_msg('Synced time', console=True)

    # enable status led to show we're ready
    status_led.on()


def main():
    # initialize wifi & clock
    init()

    # enter event loop
    display_msg('Loading...', console=True)
    while True:
        gc.collect()

        started, upcoming = get_schedule(config.team_id)

        # if not game, display message and sleep an hour
        if not started and not upcoming:
            display_msg(['No Games', 'Today'], font=md_font)
            time.sleep(3600)
            continue

        # if no game started yet, display start time of next game
        if not started:
            next_game = upcoming[0]
            next_game.home_team.refresh()
            next_game.away_team.refresh()

            display_game(next_game)
            time.sleep((next_game.start_time - datetime.now(tz=local_tz)).total_seconds())
            continue

        # if we reached this point, there is either a game in progress, or all games finished for the day
        # refresh game data
        game = started[-1]
        game.home_team.refresh()
        game.away_team.refresh()
        game.refresh()

        # display in progress game until it is finished
        while not game.is_finished:
            gc.collect()
            game.refresh()
            display_game(game)
            time.sleep(config.update_interval)

        # display final
        display_game(game)

        # if there's more games today, only sleep 10 minutes
        if upcoming:
            time.sleep(600)
        else:
            time.sleep(3600)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        sys.print_exception(e)
        reset()
