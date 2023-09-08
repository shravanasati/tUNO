from typing import TypeVar, Generic

T = TypeVar("T")


class cycle(Generic[T]):
    def __init__(self, iterable: list[T]) -> None:
        self._iterable = iterable
        self._length = len(self._iterable)

        self._last_index = -1

    def next(self, save_last: bool = True) -> T:
        if self._last_index >= 0:
            next_index = self._last_index + 1
            item = self[next_index]
            if save_last:
                self._last_index = next_index
            return item
        else:
            item = self._iterable[0]
            if save_last:
                self._last_index = 0
            return item

    def __getitem__(self, item: int) -> T:
        if not isinstance(item, int):
            raise ValueError(f"invalid {type(item)=} for subscription of cycle")

        item %= self._length
        return self._iterable[item]

    def all(self) -> list[T]:
        """
        Returns the current cycle.
        """
        return [self[self._last_index + 1 + i] for i in range(self._length)]


if __name__ == "__main__":
    players = cycle(list("pqr"))
    print(players.all())
    print(players[8])
    print(players.next())
    print(players.next(False))
    print(players.next())
    print(players.all())
