from dataclasses import dataclass
import logging
import random
import time
from datetime import date, datetime
from pathlib import Path
from statistics import mode
from threading import Lock, Thread

from rich import print
from rich.align import Align
from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

from cycle import cycle
from prompt import prompt
from structures import Card, CardValue, Color, Player


@dataclass(frozen=True)
class AlertItem:
    """
    Represents an element in the alert queue.
    """

    text: str
    created_time: datetime


def get_log_file_location():
    """
    Returns ~/.tuno/logs/{today}.log by creating the parent directories if they don't exist.
    """
    tuno_dir = Path.home() / ".tuno"
    if not tuno_dir.exists():
        tuno_dir.mkdir()
    logs = tuno_dir / "logs"
    if not logs.exists():
        logs.mkdir()
    today = str(date.today()) + ".log"
    filepath = str(logs / today)
    return filepath


def purge_logs(limit_days: int = 30):
    """
    Deletes log files older than `limit` days.
    """
    logs_dir = Path.home() / ".tuno" / "logs"
    if not logs_dir.exists():
        return

    days_to_seconds = limit_days * 24 * 60 * 60
    for file in logs_dir.iterdir():
        conditions = (
            file.is_file(),
            file.name.endswith(".log"),
            (time.time() - file.stat().st_mtime) > days_to_seconds,
            # file older than limit days
        )
        if all(conditions):
            file.unlink()


class GameplayError(Exception):
    """
    Raised when there's an internal logic error in the game.
    """


class UNOGame:
    """
    UNO Game class.
    """

    def __init__(self, *players: str) -> None:
        """
        Initializes decks for all the given players and starts an alert queue purger thread.
        """
        if len(players) not in range(2, 11):
            raise GameplayError("too less or too many players")
        if len(players) != len(set(players)):
            raise GameplayError("duplicate players")

        deck = self.build_deck()
        random.shuffle(deck)

        # shuffle players once before the game
        players_list = list(players)
        random.shuffle(players_list)

        self.players: dict[str, list[Card]] = {}
        for i, player in enumerate(players_list):
            self.players[player] = deck[i * 7 : (i + 1) * 7]

        self.draw_pile = deck[len(players_list) * 7 :]
        self.discard_pile = []
        self.color_mappings = {
            Color.RED: "red",
            Color.GREEN: "green",
            Color.BLUE: "blue",
            Color.YELLOW: "yellow",
            Color.COLORLESS: "violet",
        }
        self._game_exit = (
            False  # flag to indicate the alert_purger_thread to stop working
        )
        self.__alert_queue: list[AlertItem] = []
        self.__alert_lock = Lock()
        self._alert_purger_thread = Thread(target=self.purge_old_alerts)
        self._alert_purger_thread.start()

    @staticmethod
    def build_deck() -> list[Card]:
        """
        Builds a UNO deck of 108 cards.
        """
        # add 4 wild cards
        deck: list[Card] = []
        deck += [Card(Color.COLORLESS, CardValue.WILD)] * 4
        deck += [Card(Color.COLORLESS, CardValue.WILD_DRAW_FOUR)] * 4

        for color in Color:
            # colorless ones aleady added
            if color == Color.COLORLESS:
                continue

            for card in CardValue:
                # wild cards already added
                if card in (CardValue.WILD, CardValue.WILD_DRAW_FOUR):
                    continue

                deck.append(Card(color, card))
                # except 0, all colors have 2 cards each of same value
                if card != CardValue.ZERO:
                    deck.append(Card(color, card))

        return deck

    def draw_card(self, player: Player) -> Card:
        """
        Draws a card from the draw pile, and rebuilds the draw pile if it's empty.
        """
        while True:
            try:
                card = self.draw_pile[0]
                self.draw_pile.remove(card)
                player.cards.append(card)
                return card
            except IndexError:
                # refill the draw pile with cards on discard pile
                new_cards = self.discard_pile[:-1]
                random.shuffle(new_cards)
                self.discard_pile = self.discard_pile[:-1]
                self.draw_pile = new_cards

    def get_last_card(self) -> Card | None:
        """
        Returns the last card played on the discard pile. Returns `None` if there isn't any.
        """
        if len(self.discard_pile) == 0:
            return None
        return self.discard_pile[-1]

    def is_card_playable(self, card: Card) -> bool:
        """
        Checks whether the given card is playable in the context of the last played card.
        """
        # if the first card is being played
        last_card = self.get_last_card()
        if not last_card:
            return True

        conditions = (
            card.color == last_card.color,
            card.value == last_card.value,
            card.value in (CardValue.WILD, CardValue.WILD_DRAW_FOUR)
            # card.color == Color.COLORLESS,  # wild cards
            # last_card.color == Color.COLORLESS,
        )

        return any(conditions)

    def play_card(self, player_name: str, card: Card) -> bool:
        """
        Plays the card if it's playable.
        Raises `GameplayError` otherwise.
        Also calls the self.apply_actions method.

        Returns a boolean whether the card is an action card.
        """
        if self.is_card_playable(card):
            player_deck = self.players[player_name]
            player_deck.remove(card)
            self.players[player_name] = player_deck
            self.discard_pile.append(card)
        else:
            last_card = self.get_last_card()
            raise GameplayError(f"unplayable {card=}. {last_card=}")

        self.apply_actions()
        return card.is_action_card()

    def computer_move(self, comp_player: Player):
        """
        Selects a move to play and plays it.
        """
        last_card = self.get_last_card()
        deck = self.players["computer"]
        # if the first card is being played
        if not last_card:
            logging.debug("playing a random card because first")
            return self.play_card("computer", random.choice(deck))

        # if the last card is either wild card, play randomly
        # ! commented out because wild cards can have colors too
        # if last_card.value in (CardValue.WILD, CardValue.WILD_DRAW_FOUR):
        #     logging.debug("playing a random card because last card is wild")
        #     return self.play_card("computer", random.choice(deck))

        # get card by color or value
        for card in deck:
            if card.color == last_card.color or card.value == last_card.value:
                logging.debug(f"playing {str(card)=} as per last card")
                action_needed = self.play_card("computer", card)
                return action_needed

        # if no card by color or value, use a wild card if present
        for card in deck:
            if card.color == Color.COLORLESS:
                logging.debug("playing a wild card cuz no options")
                action_needed = self.play_card("computer", card)
                return action_needed

        # last resort, draw a card from the draw pile
        drawn_card = self.draw_card(comp_player)
        logging.debug("drawing a card")
        if self.is_card_playable(drawn_card):
            logging.debug(f"playing the {str(drawn_card)=}")
            action_needed = self.play_card("computer", drawn_card)
            return action_needed

        # pass
        return False

    def computer_get_wild_color(self):
        """
        Chooses a color from ( R, G, B, Y ) to place on the wild card computer is using.
        """
        deck = self.players["computer"]
        colors = [card.color.value for card in deck if card.color != Color.COLORLESS]
        if len(colors) == 0:
            c = random.choice(list("RGBY"))
            logging.debug(f"chose color '{c}' for wild card in random")
            return c
        c = mode(colors)
        logging.debug(f"chose color '{c}' for wild card as its mode")
        return c

    def apply_actions(self):
        """
        Takes the last card and applies relevant actions, if any.
        """
        last_card = self.get_last_card()
        if not last_card:  # in case it's none
            return
        if not last_card.is_action_card():
            return

        next_player: Player = self.player_cycle.next(False)
        last_player: Player = self.player_cycle[self.player_cycle._last_index]
        match last_card.value:
            case CardValue.WILD:
                # choose the color for the wild card
                if last_player.name == "computer":
                    new_color = self.computer_get_wild_color()
                else:
                    new_color = prompt(
                        "Choose the color to set for the wild card",
                        choices=list("RGBY"),
                        transform_functions=(lambda x: x.upper(),),
                    )
                new_color = Color(new_color)
                self.discard_pile[-1] = Card(new_color, last_card.value)
                self.alert(
                    f"Color acceptable on wild card: {self.color_mappings[new_color]}"
                )

            case CardValue.DRAW_TWO:
                # add 2 cards on the next player
                [self.draw_card(next_player) for _ in range(2)]
                self.alert(f"2 cards added on {next_player.name}'s deck")

            case CardValue.WILD_DRAW_FOUR:
                # add 4 cards on the next player and choose the color for the wild card
                [self.draw_card(next_player) for _ in range(4)]
                if last_player.name == "computer":
                    new_color = self.computer_get_wild_color()
                else:
                    new_color = prompt(
                        "Choose the color to set for the wild card",
                        choices=list("RGBY"),
                        transform_functions=(lambda x: x.upper(),),
                    )
                new_color = Color(new_color)
                self.discard_pile[-1] = Card(Color(new_color), last_card.value)
                self.alert(
                    f"4 cards added on {next_player.name}'s deck \nColor acceptable on wild card: {self.color_mappings[new_color]}"
                )

            case CardValue.SKIP:
                # to skip the players, run next once
                skipped_player: Player = self.player_cycle.next()
                self.alert(f"{skipped_player.name}'s chance is skipped.")

            case CardValue.REVERSE:
                # create a new player cycle with reversed order
                if len(self.players) > 2:
                    further_players = [last_player]
                    further_players.extend(
                        [
                            self.player_cycle.next()
                            for _ in range(self.player_cycle._length - 1)
                        ]
                    )
                    further_players = further_players[::-1]
                    self.player_cycle = cycle(further_players)
                else:
                    further_players = [last_player, next_player]
                    # no need to reverse
                    self.player_cycle = cycle(further_players)

                self.alert("Player cycle reversed.")

            case _:
                raise GameplayError("unable to match an action card")

    def get_piles_panel(self):
        """
        Return a rich.Panel of the discard pile.
        """
        last_card = self.get_last_card()
        if not last_card:
            last_card = Card(Color.COLORLESS, "no card yet")

        color = self.color_mappings[last_card.color]
        value = last_card.value
        if value != "no card yet":
            value = value.value
        rich_text = Text(value, style=f"black on {color}", justify="center")
        p = Panel(rich_text, title="discard pile")
        return p

    def alert(self, text: str):
        """
        Updates the renderable in the alerts layout with the given text in a certain style.
        Also adds the given alert to self.__alert_queue.
        """
        now = datetime.now()
        with self.__alert_lock:
            self.__alert_queue.append(AlertItem(text, now))
            renderable = Align(
                "\n".join(
                    [
                        f"[cyan bold]{i + 1}. {a.text} [i](at {a.created_time.strftime('%H:%M:%S')})[/][/]"
                        for i, a in enumerate(self.__alert_queue[-5:])
                    ]
                ),
                align="center",
            )
        # renderable = Align(f"[cyan bold]{text} [i](at {now})[/][/]", align="center")
        self.layout["alerts"].update(renderable)

    def purge_old_alerts(self):
        """
        Must be ran as an independent thread. Removes alerts from self.__alert_queue which are older
        than 30 seconds. It stops working when it sees self._game_exit flag set to True.
        """
        while True:
            if self._game_exit:
                break

            now = datetime.now()
            with self.__alert_lock:
                old_items = (
                    a for a in self.__alert_queue if (now - a.created_time).seconds > 30
                )
                for old_alert in old_items:
                    self.__alert_queue.remove(old_alert)

            time.sleep(1)

    def update_layout(
        self, cards_to_show: list[Card | str], current_player: str
    ) -> None:
        """
        Updates self.layout's discard pile, and cards with the given deck of cards.
        """
        player_order_text = "[black on white]" + " -> ".join(
            (
                p.name if p.name != current_player else f"[u black on red]{p.name}[/]"
                for p in self.player_cycle._iterable
            )
        ) + "[/]"
        self.layout["player_order"].update(
            Group(
                "\n",
                Align(
                    Panel(player_order_text, title="player order"),
                    "center",
                ),
            )
        )
        self.layout["pile"].update(Align(self.get_piles_panel(), "center"))
        rich_cards = [
            Panel(
                Text(
                    card.value.value if not isinstance(card, str) else card,
                    style=f"black on {self.color_mappings[card.color] if not isinstance(card, str) else 'pink'}",
                    justify="center",
                ),
                subtitle=f"{i+1}",
                # height=4
            )
            for i, card in enumerate(cards_to_show)
        ]

        nlayouts = int(len(rich_cards) / 8)
        if len(rich_cards) % 8 != 0:
            nlayouts += 1
        self.layout["cards"].ratio = nlayouts

        self.layout["cards"].split_column(
            *[Layout(name=f"row{i}") for i in range(nlayouts)]
        )
        for i in range(nlayouts):
            self.layout["cards"][f"row{i}"].split_row(
                *(rich_cards[i * 8 : (i + 1) * 8])
            )

    def play(self):
        """
        Main game loop.
        """
        self.player_cycle = cycle([Player(k, v) for k, v in self.players.items()])

        self.layout = Layout()
        # todo show current order in the layout
        self.layout.split_column(
            Layout(name="player_order"),
            Layout(name="pile"),
            Layout(name="alerts"),
            Layout(name="cards"),
        )
        self.layout["player_order"].ratio = 1
        self.layout["pile"].ratio = 1
        self.layout["alerts"].ratio = 1
        self.layout["cards"].ratio = 1

        self.alert("Alerts will show up here.")
        self.alert(
            f"Current player order: {'->'.join((i.name for i in self.player_cycle.all()))}"
        )

        running = True
        while running:
            current_player: Player = self.player_cycle.next()
            logging.debug(f"current cycle: {[i.name for i in self.player_cycle.all()]}")
            if current_player.name == "computer":
                self.computer_move(current_player)
                logging.debug(
                    f"computer deck: {tuple(str(i) for i in current_player.cards)}"
                )
            else:
                draw_count = 0
                while True:
                    cards_to_show: list[Card | str] = []
                    cards_to_show.extend(current_player.cards.copy())
                    cards_to_show.append("pass" if draw_count else "draw")
                    self.update_layout(cards_to_show, current_player.name)
                    print(self.layout)

                    ans = prompt(
                        "Choose the card to play",
                        choices=list(map(str, range(1, len(cards_to_show) + 1))),
                    )
                    # todo set timeout above and pass if timeout expired
                    ans = int(ans) - 1

                    card_to_play = cards_to_show[ans]
                    if card_to_play == "pass":
                        if draw_count > 0:
                            break
                        else:
                            self.alert("Can't pass without drawing atleast once!")
                            continue
                    elif card_to_play == "draw":
                        if draw_count > 0:
                            self.alert(
                                "Can't draw twice in the same chance. Either pass or play a valid card."
                            )
                            continue
                        draw_count += 1
                        self.draw_card(current_player)
                        continue

                    if isinstance(card_to_play, Card):
                        if self.is_card_playable(card_to_play):
                            self.play_card(current_player.name, card_to_play)
                            break
                        self.alert(
                            f"Can't play the card {str(card_to_play)} (against the rules)!"
                        )

            # self.apply_actions()

            if len(current_player.cards) == 1:
                self.alert(f"{current_player.name}: UNO")
            elif len(current_player.cards) == 0:
                self.alert(f"{current_player.name}: UNO-finish")
                self.update_layout(list(), "")

                self.layout["cards"].ratio = 1
                self.layout["cards"].update(
                    Align(
                        Panel(f"[green bold]{current_player.name} wins the game![/]"),
                        align="center",
                    )
                )
                print(self.layout)
                running = False
                self._game_exit = True


if __name__ == "__main__":
    game: UNOGame | None = None
    try:
        logging.basicConfig(
            filename=get_log_file_location(),
            filemode="a",
            level=logging.DEBUG,
            encoding="utf-8",
            format="%(asctime)s %(name)s %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        purge_logs()
        game = UNOGame("player", "computer", "player2")
        game.play()

    except KeyboardInterrupt:
        print("[green]byeee[/]")

    except GameplayError as ge:
        logging.exception(ge)
        print(
            f"[red]the game did something it shouldn't, a log file has been generated at `{get_log_file_location()}`.[/]"
        )

    except Exception as e:
        logging.exception(e)
        print(
            f"[red]an unknown error occured, a log file with the exception traceback has been generated at `{get_log_file_location()}`.[/]"
        )

    finally:
        # regardless of whatever happens, stop the alert purger thread
        if game:
            game._game_exit = True
