from rich import print
from typing import Callable, Iterable


ValidatorFunc = Callable[[str], bool]
TransformFunc = Callable[[str], str]


def prompt(
    text: str,
    *,  # all parameters below must be keyword only
    validate_functions: Iterable[ValidatorFunc] | None = None,
    transform_functions: Iterable[TransformFunc] | None = None,
    choices: Iterable[str] | None = None,
    show_choices: bool = True,
    wrong_input_text: str = "Wrong input!",
):
    """
    Custom prompt function inspired from rich, with transformers and validators.

    The transform_func is applied on the input string before validator_func is checked.
    """
    prompt_text = f"{text}"
    validators: list[ValidatorFunc] = []
    transformers: list[TransformFunc] = []
    transformers.append(
        lambda x: x.strip()
    )  # adding strip function above inside the list declaration messes with type hinting

    if validate_functions:
        validators.extend(validate_functions)

    if transform_functions:
        transformers.extend(transform_functions)

    if choices:
        validators.append(lambda x: x in choices)
        if show_choices:
            choices_text = f" [purple][{'/'.join(choices)}][/]"
            prompt_text += choices_text

    prompt_text += ": "

    input_validated = False
    ans: str = ""
    while not input_validated:
        print(prompt_text, end="")
        ans = input()
        for transformer in transformers:
            ans = transformer(ans)
        for validator in validators:
            if not validator(ans):
                print(f"[red]{wrong_input_text}[/]")
                break
        else:
            input_validated = True

    return ans


if __name__ == "__main__":
    ans = prompt(
        "Choose the card to play",
        choices=list("RGBY"),
        transform_functions=(lambda x: x.upper(),),
    )
    print(ans)
