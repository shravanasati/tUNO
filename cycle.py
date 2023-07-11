from typing import TypeVar

T = TypeVar("T")


class cycle:
    def __init__(self, iterable: list[T]) -> None:
        self.iterable = iterable
        self.length = len(self.iterable)

        self.last_index = -1

    def next(self, save_last: bool = True) -> T:
        if self.last_index >= 0:
            next_index = self.last_index + 1
            item = self[next_index]
            if save_last:
                self.last_index = next_index
            return item
        else:
            item = self.iterable[0]
            if save_last:
                self.last_index = 0
            return item

    def __getitem__(self, item: int) -> T:
        if not isinstance(item, int):
            raise ValueError(f"invalid {type(item)=} for subscription of cycle")

        item %= self.length
        return self.iterable[item]


if __name__ == "__main__":
    players = cycle(list("pqr"))
    print(players[8])
    print(players.next())
    print(players.next(False))
    print(players.next())
