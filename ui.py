from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import Button, Header, Label


class tUNO(App):
    TITLE = "tUNO"
    SUB_TITLE = "UNO cards game for the terminal"
    CSS_PATH = "ui.tcss"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)


if __name__ == "__main__":
    tuno = tUNO()
    tuno.run()
