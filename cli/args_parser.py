from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlparse
from cli.cli import CliError
from cli.value_parser import ValueParser
from common.constants import Mode
from common.core_types import DescribeOptions, IndexOptions, OutputType, OverwriteMode, SearchOptions, is_output_type, is_overwrite_mode

class ArgsParser():
    def __init__(self) -> None:
        pass

    def _pop_value(self, argv: list[str], idx: int, flag: str) -> tuple[str, int]:
        if idx + 1 >= len(argv):
            raise CliError(f"Missing value for {flag}.")
        return argv[idx + 1], idx + 2

    def parse_args(self, argv: list[str]) -> ParsedArgs:
        """Parses command-line arguments for the CLI and returns a normalized `ParsedArgs`.

        Args:
            argv: Raw command-line arguments (typically `sys.argv`). `argv[1]` is
                interpreted as the mode.
        Returns:
            ParsedArgs: Container with:
                mode: index, search, gui.
                options: IndexOptions, SearchOptions, DescribeOptions.  
                    Values must all be defined and valid before use.
                verbose: Whether -v/--verbose was provided.
                write_defaults: Whether -w/--write_defaults was provided.   
                    Specifies whether to write current options to config file.
        Raises:
            CliError: If the mode is missing/invalid, an unknown switch is encountered,
                required options are missing, provided values are invalid, or if parsing
                ends in an inconsistent state.
        """
        
        if len(argv) <= 1:
            raise CliError("Missing mode.")

        mode = argv[1].strip().lower()
        allowed_modes = {m.value for m in Mode}
        if mode not in allowed_modes:
            raise CliError(f"Unknown mode: {argv[1]}")

        options: IndexOptions | SearchOptions | DescribeOptions
        verbose_flag = False

        if mode == Mode.INDEX.value:
            options = IndexOptions()
            write_defaults_flag = False
            verbose_flag = False

            i = 2
            while i < len(argv):
                arg = argv[i]
                if arg in ("-i", "--input"):
                    value, i = self._pop_value(argv, i, arg)
                    options.input_dir = Path(value)
                    continue
                if arg in ("-r", "--recursive"):
                    options.recursive = True
                    i += 1
                    continue
                if arg in ("-f", "--filter"):
                    value, i = self._pop_value(argv, i, arg)
                    options.filter_patterns = ValueParser.parse_filter(value)
                    continue
                if arg in ("--exclude_dirs"):
                    value, i = self._pop_value(argv, i, arg)
                    options.exclude_dir_patterns = ValueParser.parse_filter(value)
                    continue
                if arg in ("--min_resolution"):
                    value, i = self._pop_value(argv, i, arg)
                    options.min_resolution = ValueParser.parse_resolution(value)
                    continue
                if arg in ("-o", "--overwrite"):
                    value, i = self._pop_value(argv, i, arg)
                    options.overwrite = ValueParser.parse_overwrite(value)
                    continue
                if arg in ("-t", "--thumbnails_only"):
                    options.thumbnails_only = True
                    i += 1
                    continue
                if arg in ("--prompt"):
                    value, i = self._pop_value(argv, i, arg)
                    options.prompt = value
                    continue
                if arg == "--host":
                    value, i = self._pop_value(argv, i, arg)
                    options.host = ValueParser.normalize_host(value)
                    continue
                if arg == "--port":
                    value, i = self._pop_value(argv, i, arg)
                    options.port = ValueParser.parse_port(value)
                    continue
                if arg == "--model":
                    value, i = self._pop_value(argv, i, arg)
                    options.model = ValueParser.parse_model(value)
                    continue
                if arg in ("-w", "--write_defaults"):
                    write_defaults_flag = True
                    i += 1
                    continue
                if arg in ("-v", "--verbose"):
                    verbose_flag = True
                    i += 1
                    continue

                if arg.startswith("-"):
                    raise CliError(f"Unknown switch: {arg}")
                raise CliError(f"Unexpected argument: {arg}")

        elif mode == Mode.SEARCH.value:
            options = SearchOptions()
            write_defaults_flag = False
            verbose_flag = False

            i = 2
            while i < len(argv):
                arg = argv[i]
                if arg in ("-q", "--query"):
                    value, i = self._pop_value(argv, i, arg)
                    options.query = value
                    continue
                if arg in ("-i", "--input"):
                    value, i = self._pop_value(argv, i, arg)
                    options.input_dir = Path(value)
                    continue
                if arg in ("-t", "--output_type"):
                    value, i = self._pop_value(argv, i, arg)
                    options.output_type = ValueParser.parse_output_type(value)
                    continue
                if arg in ("-f", "--file"):
                    value, i = self._pop_value(argv, i, arg)
                    options.output_file = Path(value)
                    continue
                if arg in ("-w", "--write_defaults"):
                    write_defaults_flag = True
                    i += 1
                    continue
                if arg in ("-v", "--verbose"):
                    verbose_flag = True
                    i += 1
                    continue

                if arg.startswith("-"):
                    raise CliError(f"Unknown switch: {arg}")
                raise CliError(f"Unexpected argument: {arg}")

        elif mode == Mode.DESCRIBE.value:
            options = DescribeOptions()
            write_defaults_flag = False
            verbose_flag = False

            i = 2
            while i < len(argv):
                arg = argv[i]
                if arg in ("-i", "--input"):
                    value, i = self._pop_value(argv, i, arg)
                    options.input_file = Path(value)
                    continue
                if arg in ("--prompt"):
                    value, i = self._pop_value(argv, i, arg)
                    options.prompt = value
                    continue
                if arg == "--host":
                    value, i = self._pop_value(argv, i, arg)
                    options.host = ValueParser.normalize_host(value)
                    continue
                if arg == "--port":
                    value, i = self._pop_value(argv, i, arg)
                    options.port = ValueParser.parse_port(value)
                    continue
                if arg == "--model":
                    value, i = self._pop_value(argv, i, arg)
                    options.model = ValueParser.parse_model(value)
                    continue
                if arg in ("-w", "--write_defaults"):
                    write_defaults_flag = True
                    i += 1
                    continue
                if arg in ("-v", "--verbose"):
                    verbose_flag = True
                    i += 1
                    continue

                if arg.startswith("-"):
                    raise CliError(f"Unknown switch: {arg}")
                raise CliError(f"Unexpected argument: {arg}")

        elif mode == Mode.GUI.value:
            # No CLI options for GUI mode yet.
            options = SearchOptions()
            write_defaults_flag = False
            verbose_flag = False

            i = 2
            while i < len(argv):
                arg = argv[i]
                if arg in ("-w", "--write_defaults"):
                    write_defaults_flag = True
                    i += 1
                    continue
                if arg in ("-v", "--verbose"):
                    verbose_flag = True
                    i += 1
                    continue

                if arg.startswith("-"):
                    raise CliError(f"Unknown switch: {arg}")
                raise CliError(f"Unexpected argument: {arg}")

        else:
            raise CliError(f"Invalid mode {mode}.")
        
        if options is None:
            raise CliError("Args parsing error.")

        return ParsedArgs(
            mode=mode,
            options=options,
            verbose=verbose_flag,
            write_defaults=write_defaults_flag,
        )

    def is_help_requested(self, argv: list[str]) -> bool:
        return any(arg in ("-h", "--help") for arg in argv[1:])

@dataclass(frozen=True)
class ParsedArgs:
    """
    Holds the parsed command-line arguments, cast to their appropriate types.
    
    Attributes:
        mode (str): The operation mode ('index', 'search', or 'gui').
        options (IndexOptions | SearchOptions): The options for the selected mode.  
            Fields are ensured to be defined.
        verbose (bool): Whether to enable verbose output to the console.
        write_defaults (bool): Whether to write default values to the config.
    """
    mode: str
    options: IndexOptions | SearchOptions | DescribeOptions
    verbose: bool
    write_defaults: bool