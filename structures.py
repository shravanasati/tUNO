from enum import Enum, StrEnum
from dataclasses import dataclass


class Color(StrEnum):
    """
    Represents card colors. COLORLESS is reserved only for wild draw four and wild card.
    """

    BLUE = "B"
    RED = "R"
    GREEN = "G"
    YELLOW = "Y"
    COLORLESS = ""


class CardValue(Enum):
    ZERO = "0"
    ONE = "1"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"

    DRAW_TWO = "+2"
    SKIP = "skip"
    REVERSE = "reverse"

    WILD = "wild"
    WILD_DRAW_FOUR = "wild +4"


@dataclass(frozen=True, order=True)
class Card:
    """
    Represents a UNO card.
    """

    color: Color
    value: CardValue

    @classmethod
    def from_string(cls, string: str):
        if len(string) < 2:
            raise ValueError(f"invalid {string=} to construct a card")
        color = string[0]
        if color in ("R", "G", "B", "Y"):
            color = Color(color)
            value = CardValue(string[1:])
        else:
            color = Color.COLORLESS
            value = CardValue(string)
        return cls(color, value)

    def __str__(self) -> str:
        return f"{self.color.value}{self.value.value}"

    def is_action_card(self):
        return self.value in (
            CardValue.WILD_DRAW_FOUR,
            CardValue.DRAW_TWO,
            CardValue.SKIP,
            CardValue.REVERSE,
        )


@dataclass(frozen=True, order=True)
class Player:
    name: str
    cards: list[Card]
