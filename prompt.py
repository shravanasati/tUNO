import time
from typing import Callable, Iterable
from rich import print

import platform

WINDOWS = platform.system() == "Windows"

if WINDOWS:
    import msvcrt
    import sys
else:
    import signal


class TimeoutExpired(Exception):
    """
    TimeoutExpired is raised when user doesn't input anything until given number of seconds.
    """

    pass


def __input_with_timeout_windows(prompt: str, timeout: int) -> str | None:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    endtime = time.monotonic() + timeout

    result = []
    while time.monotonic() < endtime:
        if msvcrt.kbhit():
            result.append(msvcrt.getwche())
            if result[-1] == "\r":
                return "".join(result[:-1])

        time.sleep(0.04)  # just to yield to other processes/threads

    raise TimeoutExpired("Input timeout!")


def __timeout_handler(signal_num, stack_frame):
    raise TimeoutExpired(
        f"Input timeout! Signal number: {signal_num}, stack frame: {stack_frame}"
    )


def __input_with_timeout_unix(prompt: str, timeout: int) -> str | None:
    signal.signal(signal.SIGALRM, __timeout_handler)
    signal.alarm(timeout)

    ans = input(prompt)
    signal.alarm(0)

    return ans


def __input_with_timeout(prompt: str, timeout: int) -> str | None:
    if WINDOWS:
        return __input_with_timeout_windows(prompt, timeout)
    else:
        return __input_with_timeout_unix(prompt, timeout)


ValidatorFunc = Callable[[str], bool]
TransformFunc = Callable[[str], str]


def prompt(
    text: str,
    *,  # all parameters below must be keyword only
    validate_functions: Iterable[ValidatorFunc] | None = None,
    transform_functions: Iterable[TransformFunc] | None = None,
    choices: Iterable[str] | None = None,
    show_choices: bool = True,
    default: str | None = None,
    show_default: bool = True,
    validate_default: bool = True,
    transform_default: bool = True,
    wrong_input_text: str = "Wrong input!",
    timeout: int | None = None,
) -> str:
    """
    Custom prompt function inspired from rich, with transformers and validators.

    The transform functions are applied on the input string before validator functions are checked.

    The default argument would also be validated by the given validations if `validate_default` is set to True.

    Returns default if the timeout argument is given and input duration exceeds the timeout. Thus, the default argument must be provided if timeout is being used. It would raise a ValueError otherwise.
    """
    if not default:
        default = ""
    if timeout and not default:
        raise ValueError("prompt: a default argument must be provided if timeout is being used")

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

    if default and show_default:
        default_text = f" [cyan]({default})[/]"
        prompt_text += default_text

    prompt_text += ": "

    input_validated = False
    ans: str = ""
    init = time.time()
    while not input_validated:
        if timeout:
            if (time.time() - init) > timeout:
                # wrong input resets the internal timer of __input_with_timeout
                # therefore check for time here too
                # this is different that input with timeout cuz that can kill the input, this if condition can't
                print()
                ans = default
            else:
                try:
                    print(prompt_text, end="")
                    a = __input_with_timeout("", timeout)
                    ans = a if a else ""
                except TimeoutExpired:
                    print()
                    ans = default
        else:
            print(prompt_text, end="")
            ans = input()

        for transformer in transformers:
            ans = transformer(ans)
            if transform_default:
                default = transformer(default)

        if ans == "":
            ans = default
        if not validate_default and ans == default:
            break

        for validator in validators:
            if not validator(ans):
                nlc = "\n"
                print(f"{nlc if timeout else ''}[red]{wrong_input_text}[/]")
                break
        else:
            input_validated = True

    if timeout:
        print()
    return ans


if __name__ == "__main__":
    ans = prompt(
        "Choose the card to play",
        choices=list("RGBY"),
        transform_functions=(lambda x: x.upper(),),
        default="Re",
        timeout=5,
    )
    if ans:
        print(ans)
    else:
        print("timeout!")
