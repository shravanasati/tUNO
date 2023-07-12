from datetime import date
from pathlib import Path
from cycle import cycle
import random
import logging
from structures import Card, CardValue, Color, Player

from rich.align import Align
from rich.panel import Panel
from rich import print


def get_log_file_location():
    tuno_dir = Path.home() / ".tuno"
    if not tuno_dir.exists():
        tuno_dir.mkdir()
    logs = tuno_dir / "logs"
    if not logs.exists():
        logs.mkdir()
    today = str(date.today()) + ".log"
    filepath = str(logs / today)
    return filepath


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.FileHandler(get_log_file_location(), encoding="utf-8"))
stdout_handler = logger.handlers[0]
logger.removeHandler(stdout_handler)


class GameplayError(Exception):
    """
    Raised when there's an internal logic error in the game.
    """


class UNOGame:
    """
    UNO Game class.
    """

    def __init__(self, *players: str) -> None:
        if len(players) not in range(2, 11):
            raise GameplayError("too less or too many players")
        if len(players) != len(set(players)):
            raise GameplayError("duplicate players")

        deck = self.build_deck()
        random.shuffle(deck)

        self.players: dict[str, list[Card]] = {}
        for i, player in enumerate(players):
            self.players[player] = deck[i * 7 : (i + 1) * 7]

        self.draw_pile = deck[len(players) * 7 :]
        self.discard_pile = []

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
        Draws a card from the draw pile.
        """
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
            card.color == Color.COLORLESS,  # wild cards
            last_card.color == Color.COLORLESS,
        )

        return any(conditions)

    def play_card(self, player_name: str, card: Card) -> bool:
        """
        Plays the card if it's playable.
        Raises `GameplayError` otherwise.

        Returns a boolean whether the card is an action card, so as to implement actions
        associated with it in the game loop.
        """
        if self.is_card_playable(card):
            player_deck = self.players[player_name]
            player_deck.remove(card)
            self.players[player_name] = player_deck
            self.discard_pile.append(card)
        else:
            last_card = self.get_last_card()
            raise GameplayError(f"unplayable {card=}. {last_card=}")

        return card.is_action_card()

    def computer_move(self, comp_player: Player):
        """
        Selects a move to play and plays it.
        """
        last_card = self.get_last_card()
        deck = self.players["computer"]
        # if the first card is being played
        if not last_card:
            logger.debug("playing a random card because first")
            return self.play_card("computer", random.choice(deck))

        # if the last card is either wild card, play randomly
        if last_card.value in (CardValue.WILD, CardValue.WILD_DRAW_FOUR):
            logging.debug("playing a random card because last card is wild")
            return self.play_card("computer", random.choice(deck))

        # get card by color or value
        for card in deck:
            if card.color == last_card.color or card.value == last_card.value:
                logger.debug(f"playing {str(card)=} as per last card")
                action_needed = self.play_card("computer", card)
                return action_needed

        # if no card by color or value, use a wild card if present
        for card in deck:
            if card.color == Color.COLORLESS:
                logger.debug("playing a wild card cuz no options")
                action_needed = self.play_card("computer", card)
                return action_needed

        # last resort, draw a card from draw pile
        drawn_card = self.draw_card(comp_player)
        logger.debug("drawing a card")
        if self.is_card_playable(drawn_card):
            logger.debug(f"playing the {str(drawn_card)=}")
            action_needed = self.play_card("computer", drawn_card)
            return action_needed

        return False

    def apply_actions(self):
        """
        Takes the last card and applies relevant actions, if any.
        """
        last_card = self.get_last_card()
        if not last_card.is_action_card():
            return

        next_player: Player = self.player_cycle.next(False)
        match last_card.value:
            case CardValue.DRAW_TWO:
                [self.draw_card(next_player) for _ in range(2)]
            case CardValue.WILD_DRAW_FOUR:
                [self.draw_card(next_player) for _ in range(4)]
            case CardValue.SKIP:
                # to skip the players, run next once
                self.player_cycle.next()
            case CardValue.REVERSE:
                # create a new player cycle with reversed order
                further_players = [
                    self.player_cycle.next() for _ in range(self.player_cycle.length)
                ]
                further_players = further_players[::-1]
                self.player_cycle = cycle(further_players)
            case _:
                raise GameplayError("unable to match an action card")

    def display_piles(self):
        last_card = self.get_last_card()
        if not last_card:
            last_card = Card(Color.COLORLESS, "no card yet")

        color_mappings = {
            Color.RED: "red",
            Color.GREEN: "green",
            Color.BLUE: "blue",
            Color.YELLOW: "yellow",
            Color.COLORLESS: "grey",
        }
        color = color_mappings[last_card.color]
        value = last_card.value
        if value != "no card yet":
            value = value.value
        formatted_text = f"[bold {color}]{value}[/]"
        p = Panel(formatted_text, title="Discard Pile")
        print(Align(p))

    def play(self):
        """
        Main game loop.
        """
        self.player_cycle = cycle([Player(k, v) for k, v in self.players.items()])
        running = True
        while running:
            self.display_piles()
            current_player: Player = self.player_cycle.next()
            if current_player.name == "computer":
                self.computer_move(current_player)
                logger.debug(
                    f"computer deck: {tuple(str(i) for i in current_player.cards)}"
                )
            else:
                draw_count = 0
                while True:
                    available_cards = "/".join((str(i) for i in current_player.cards))
                    available_cards += "/draw" if draw_count < 1 else "/pass"
                    card_to_play = input(f"Select a card ({available_cards}): ").strip()
                    if card_to_play == "pass":
                        if draw_count > 0:
                            break
                        else:
                            print("cant pass without drawing atleast once")
                            continue
                    elif card_to_play == "draw":
                        if draw_count > 0:
                            print(
                                "Cannot draw again in the same chance. Either pass or play a valid card."
                            )
                            continue
                        draw_count += 1
                        self.draw_card(current_player)
                        continue
                    if card_to_play not in available_cards.split("/"):
                        print("Can't play this card")
                        continue
                    card_to_play = Card.from_string(card_to_play)
                    if self.is_card_playable(card_to_play):
                        self.play_card(current_player.name, card_to_play)
                        break
                    print("Can't play this card")

            self.apply_actions()
            if len(current_player.cards) == 1:
                print(f"{current_player.name}: UNO")
            elif len(current_player.cards) == 0:
                print(f"{current_player.name}: UNO-finish")
                print(current_player.name, "wins the game!")
                break


if __name__ == "__main__":
    game = UNOGame("player", "computer")
    game.play()
