import asyncio
import inspect

class CLIArgument:
    def __init__(self, name: str, type_: callable = str, default: object | None = None):
        self.name = name
        self.type = type_
        self.default = default

    def __repr__(self):
        if self.default is not None:
            return f'{self.name}:{self.type.__name__}={self.default}'
        return f'{self.name}:{self.type.__name__}'


class CLICommand:
    def __init__(
        self,
        name: str,
        handler: callable,
        args: list[CLIArgument],
        prefix: str | None = None,
        description: str | None = None,
        category: str | None = None,
        hidden: bool = False
    ):
        self.name = name
        self.handler = handler
        self.args = args
        self.prefix = prefix
        self.description = description or (handler.__doc__ or '').strip()
        self.category = category
        self.hidden = hidden

    async def run(self, **kwargs):
        if inspect.iscoroutinefunction(self.handler):
            return await self.handler(**kwargs)
        return self.handler(**kwargs)


class CommandNode:
    def __init__(self):
        self.children: dict[str, CommandNode] = {}
        self.command: CLICommand | None = None

class LiveCLI:
    def __init__(self, prefix: str | None = None):
        self.root = CommandNode()
        self.prefix = prefix
        self.type_registry: dict[str, callable] = {}
        self.aliases: dict[str, str] = {}
        self.outputMode = 'both'
        self.buffer: list[str] = []
        self._register_builtin()

    def write(self, msg: str):
        self.buffer.append(str(msg))

    def flush_buffer(self):
        for msg in self.buffer:
            print(msg)
        self.buffer.clear()

    def register_type(self, name: str, type_: callable):
        self.type_registry[name] = type_

    def alias(self, name: str, target: str):
        self.aliases[name] = target

    def command(self, name: str, args: list[str] | None = None,
                prefix: str | None = None, description: str | None = None,
                category: str | None = None, hidden: bool = False):

        if any(part == "help" for part in name.split(".")) and name != "help":
            raise ValueError("Cannot define a command named 'help'. It is reserved.")

        def decorator(func: callable):
            parsed_args = self._parse_args(args or [])
            cmd = CLICommand(name, func, parsed_args, prefix, description, category, hidden)
            self._insert_command(name.split('.'), cmd)
            return func

        return decorator

    def _insert_command(self, path: list[str], cmd: CLICommand):
        node = self.root
        for part in path:
            node = node.children.setdefault(part, CommandNode())
        node.command = cmd

    def _parse_args(self, args: list[str]) -> list[CLIArgument]:
        parsed: list[CLIArgument] = []

        for arg in args:
            if ':' not in arg:
                parsed.append(CLIArgument(arg, str, None))
                continue

            name, rest = arg.split(':', 1)

            if '=' in rest:
                type_name, default_str = rest.split('=', 1)
            else:
                type_name, default_str = rest, None

            if type_name.startswith("enum(") and type_name.endswith(")"):
                options = type_name[5:-1].split(',')
                def enum_type(v):
                    if v not in options:
                        raise ValueError(f"Invalid value '{v}'. Expected: {', '.join(options)}")
                    return v
                type_ = enum_type

            elif type_name in self.type_registry:
                type_ = self.type_registry[type_name]

            else:
                type_ = {
                    'str': str,
                    'int': int,
                    'float': float,
                    'bool': bool
                }.get(type_name, str)

            if default_str is not None:
                if type_ is bool:
                    default = default_str.lower() == 'true'
                else:
                    default = type_(default_str)
            else:
                default = None

            parsed.append(CLIArgument(name, type_, default))

        return parsed

    def _register_builtin(self):
        @self.command('help', args=['topic:str=None'])
        def help_cmd(topic=None):
            if topic:
                cmd = self._find_command(topic.split('.'))
                if cmd:
                    self._print_command_help(cmd)
                else:
                    subs = self._list_subcommands(topic.split('.'))
                    if subs:
                        print(f"Unknown command: {topic}. Subcommands: {', '.join(subs)}")
                    else:
                        print(f"Unknown command: {topic}")
                return

            print('Available commands:')
            for name, cmd in self._list_commands():
                if not cmd.hidden:
                    print(f'  {name:<20} {cmd.description}')

        @self.command('view', args=['mode:enum(both,cli,silent)'])
        def view_cmd(mode):
            self.outputMode = mode
            print(f'Output mode set to {mode}')

    def _find_command(self, path: list[str]) -> CLICommand | None:
        node = self.root
        for part in path:
            if part not in node.children:
                return None
            node = node.children[part]
        return node.command

    def _list_subcommands(self, path: list[str]) -> list[str]:
        node = self.root
        for part in path:
            if part not in node.children:
                return []
            node = node.children[part]
        return list(node.children.keys())

    def _list_commands(self) -> list[tuple[str, CLICommand]]:
        results: list[tuple[str, CLICommand]] = []

        def walk(node: CommandNode, prefix: str):
            if node.command:
                results.append((prefix, node.command))
            for name, child in node.children.items():
                walk(child, f'{prefix}.{name}' if prefix else name)

        walk(self.root, '')
        return results

    def _resolve_command(self, tokens: list[str]) -> tuple[CLICommand | None, list[str]]:
        if self.prefix and tokens[0].startswith(self.prefix):
            tokens[0] = tokens[0][len(self.prefix):]

        if tokens[0] in self.aliases:
            tokens[0] = self.aliases[tokens[0]]

        local_help = False
        if tokens[-1] == "help":
            tokens = tokens[:-1]
            local_help = True

        node = self.root
        path: list[str] = []
        idx = 0

        while idx < len(tokens) and tokens[idx] in node.children:
            path.append(tokens[idx])
            node = node.children[tokens[idx]]
            idx += 1

        if not node.command:
            subs = self._list_subcommands(path)
            if subs:
                raise ValueError(f"Unknown command: {' '.join(path)}. Subcommands: {', '.join(subs)}")
            raise ValueError(f"Unknown command: {' '.join(path)}")

        cmd = node.command

        if local_help:
            self._print_command_help(cmd)
            return None, []

        return cmd, tokens[idx:]

    def _parse_arguments(self, cmd: CLICommand, arg_tokens: list[str]) -> dict[str, object]:
        args = cmd.args
        kwargs: dict[str, object] = {}

        pos_index = 0
        for token in arg_tokens:
            if '=' in token:
                break
            if pos_index >= len(args):
                raise ValueError(f"Too many positional arguments. Expected: {', '.join(a.name for a in args)}")
            arg = args[pos_index]
            kwargs[arg.name] = self._convert_arg(arg, token)
            pos_index += 1

        for token in arg_tokens[pos_index:]:
            if '=' not in token:
                raise ValueError(f'Expected named argument, got "{token}"')
            name, value = token.split('=', 1)
            match = next((a for a in args if a.name == name), None)
            if not match:
                raise ValueError(
                    f"Unknown argument '{name}'. Expected: {', '.join(a.name for a in args)}"
                )
            kwargs[name] = self._convert_arg(match, value)

        for arg in args:
            if arg.name not in kwargs:
                if arg.default is not None:
                    kwargs[arg.name] = arg.default
                else:
                    raise ValueError(f"Missing required argument: {arg.name}")

        return kwargs

    def _convert_arg(self, arg: CLIArgument, value: str) -> object:
        if arg.type is bool:
            return value.lower() == 'true'
        return arg.type(value)

    def _print_command_help(self, cmd: CLICommand):
        arglist = ' '.join([f'<{repr(a)}>' for a in cmd.args])
        print(f'{cmd.name.replace(".", " ")} {arglist}')
        print(f'    {cmd.description}')

    async def run(self):
        while True:
            line = await asyncio.to_thread(input, '> ')
            line = line.strip()
            if not line:
                continue

            tokens = line.split()

            try:
                cmd, arg_tokens = self._resolve_command(tokens)
                if cmd is None:
                    continue

                kwargs = self._parse_arguments(cmd, arg_tokens)
                result = await cmd.run(**kwargs)

                if result is not None and self.outputMode in ('both', 'cli'):
                    print(result)

                # flush cli buffer
                if self.outputMode == 'cli':
                    self.flush_buffer()

            except Exception as e:
                print(f'Error: {e}')
