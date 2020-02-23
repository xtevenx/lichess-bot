import typing

import src.model
import src.engine_wrapper
import src.lichess


class Conversation:
    command_prefix: str = "!"
    username_prefix: str = "@"
    spectator_prefix: str = "spectator<"
    built_in_commands: typing.List[str] = [
        "name", "howto", "eval", "queue", "chat"
    ]

    def __init__(self, game: src.model.Game, engine: src.engine_wrapper.UCIEngine,
                 xhr: src.lichess.Lichess, version: str, challenge_queue: list,
                 commands: typing.Dict[str, str], username: str):
        self.game: src.model.Game = game
        self.engine: src.engine_wrapper.UCIEngine = engine
        self.xhr: src.lichess.Lichess = xhr
        self.version: str = version
        self.challengers: list = challenge_queue
        self._commands: typing.Dict[str, str] = commands
        self.username: str = username

        self._commands = {k.lower(): v for k, v in self._commands.items()}
        self._commands_string: str = Conversation.command_prefix + (
            ", {}".format(Conversation.command_prefix).join(
                frozenset(Conversation.built_in_commands + list(commands.keys()))
            )
        )

        self._username_string: str = f"{Conversation.username_prefix}{username} ".lower()

    def react(self, line: "ChatLine", game: src.model.Game) -> None:
        print("*** {} [{}] {}: {}".format(
            self.game.url(), line.room, line.username, line.text.encode("utf-8")
        ))

        if line.text[:len(self._username_string)].lower() == self._username_string \
                and line.room == "spectator":
            self.forward_to_private(line, line.text[len(self._username_string):])

        elif line.text[:len(Conversation.spectator_prefix)].lower() == Conversation.spectator_prefix \
                and line.room == "player" and line.username.lower() == self.username.lower():
            self.forward_to_public(line, line.text[len(Conversation.spectator_prefix):])

        elif line.text[:len(self.command_prefix)] == self.command_prefix:
            self.command(line, game, line.text[len(self.command_prefix):].split()[0].lower())

    def command(self, line: "ChatLine", game: src.model.Game, cmd: str) -> None:
        if cmd == "commands" or cmd == "help":
            self.send_reply(line, f"Supported commands: {self._commands_string}.")

        try:
            # `config.yml` defined commands
            self.send_reply(line, self._commands[cmd].format(
                engine=self.engine.name,
                version=self.version
            ))

        except KeyError:
            if cmd == "wait" and game.is_abortable():
                game.abort_in(60)
                self.send_reply(line, "Waiting 60 seconds...")

            elif cmd == "name":
                self.send_reply(line, f"{self.engine.name()} (lichess-bot v{self.version}).")

            elif cmd == "howto":
                self.send_reply(line, "How to run your own bot: lichess.org/api#tag/Chess-Bot")

            elif cmd == "eval":
                if line.room == "spectator" or line.username.lower() == self.username.lower():
                    stats = self.engine.get_stats()
                    if len(stats) == 0:
                        self.send_reply(line, "No evaluation reported.")
                    else:
                        self.send_reply(line, ", ".join(stats) + ".")
                else:
                    self.send_reply(line, "I don't tell that to my opponent, sorry.")

            elif cmd == "queue":
                if self.challengers:
                    challengers = ", ".join(
                        f"@{challenger.challenger_name}" for challenger in reversed(self.challengers)
                    )
                    self.send_reply(line, f"Challenge queue: {challengers}")
                else:
                    self.send_reply(line, "No challenges queued.")

            elif cmd == "chat":
                self.send_reply(
                    line, f"You can chat with me (if I'm watching) by prepending messages with "
                          f"\"{Conversation.username_prefix}{self.username} \"."
                )

    def forward_to_private(self, line: "ChatLine", text: str) -> None:
        line.room = "player"
        self.send_reply(line, f"Message from {line.username}: {text}")

    def forward_to_public(self, line: "ChatLine", text: str) -> None:
        line.room = "spectator"
        self.send_reply(line, text)

    def send_reply(self, line: "ChatLine", reply: str) -> None:
        self.xhr.chat(self.game.id, line.room, reply)


class ChatLine:
    def __init__(self, json: dict):
        self.room: str = json.get("room")
        self.username: str = json.get("username")
        self.text: str = json.get("text")
