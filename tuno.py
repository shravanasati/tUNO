from itertools import cycle
import random
from structures import Card, CardValue, Color, Player
from pprint import pprint


class GameplayError(Exception):
    """
    Raised when there's an internal logic error in the game.
    """


class UNOGame:
    """
    UNO Game class.
    """

    def __init__(self, *players: str) -> None:
        if len(players) != len(set(players)):
            raise GameplayError("duplicate players")

        deck = self.build_deck()
        random.shuffle(deck)

        self.players: dict[str, list[Card]] = {}
        for i, player in enumerate(players):
            self.players[player] = deck[i * 7 : (i + 1) * 7]

        self.draw_pile = deck[len(players) * 7 :]
        self.discard_pile = []

        self.player_cycle = cycle((Player(k, v) for k, v in self.players.items()))

    def draw_card(self) -> Card:
        """
        Draws a card from the draw pile.
        """
        card = self.draw_pile[0]
        self.draw_pile.remove(card)
        return card

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
            last_card.color == Color.COLORLESS
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

    def computer_move(self):
        """
        Selects a move to play and plays it.
        """
        last_card = self.get_last_card()
        # if the first card is being played
        if not last_card:
            self.play_card(random.choice(self.players["computer"]))
            return

        # if the last card is either wild card, play randomly
        if last_card.value in (CardValue.WILD, CardValue.WILD_DRAW_FOUR):
            self.play_card(random.choice(self.players["computer"]))
            return

        # get card by color or value
        deck = self.players["computer"]
        for card in deck:
            if card.color == last_card.color or card.value == last_card.value:
                action_needed = self.play_card("computer", card)
                return action_needed

        # if no card by color or value, use a wild card if present
        for card in deck:
            if card.color == Color.COLORLESS:
                action_needed = self.play_card("computer", card)
                return action_needed

        # last resort, draw a card from draw pile
        drawn_card = self.draw_card()
        if self.is_card_playable(drawn_card):
            action_needed = self.play_card("computer", drawn_card)
            return action_needed

        return False

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


if __name__ == "__main__":
    pprint(tuple(str(i) for i in UNOGame().deck))
