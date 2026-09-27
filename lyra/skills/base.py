"""
============================================================
 SKILLS BASE
============================================================
 Shared types for all PC-control skills.
============================================================
"""


class Confirmation:
    """
    Returned by a skill when an action is dangerous
    (shutdown, restart, sleep, empty recycle bin).
    Lyra asks the prompt, waits for confirm/cancel.
    """

    def __init__(self, prompt, action, say_on_confirm=None):
        self.prompt = prompt
        self.action = action              # callable, executed on "confirm"
        self.say_on_confirm = say_on_confirm
