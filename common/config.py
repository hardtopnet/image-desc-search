from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from cli.args_parser import ParsedArgs
from cli.value_parser import ValueParser
from common import constants
from .core_types import DescribeOptions, IndexOptions, OutputType, OverwriteMode, SearchOptions

class Config():
    """
    Handles loading and writing configuration from/to a config file.  
    """
    class _ConfigFileParser():
        """
        Internal utility class to parse and validate configuration file dict.  

        Returns:
            `ConfigValues` with typed optional variables.
        """
        def parse_file(self, raw: dict[str, Any]) -> ConfigValues:
            """Parses the raw dict from the config file into ConfigValues, validating types.  
            ##### Values are optional.
            """
            cfg = ConfigValues()
            if constants.CONFIG_KEYS.RECURSIVE.value in raw:
                cfg.recursive = ValueParser.parse_recursive(raw[constants.CONFIG_KEYS.RECURSIVE.value])
            if constants.CONFIG_KEYS.FILTER.value in raw:
                cfg.filter_patterns = ValueParser.parse_filter(raw[constants.CONFIG_KEYS.FILTER.value])
            if constants.CONFIG_KEYS.OVERWRITE.value in raw:
                cfg.overwrite = ValueParser.parse_overwrite(raw[constants.CONFIG_KEYS.OVERWRITE.value])
            if constants.CONFIG_KEYS.OUTPUT_TYPE.value in raw:
                cfg.output_type = ValueParser.parse_output_type(raw[constants.CONFIG_KEYS.OUTPUT_TYPE.value])
            if constants.CONFIG_KEYS.HOST.value in raw:
                cfg.host = ValueParser.normalize_host(raw[constants.CONFIG_KEYS.HOST.value])
            if constants.CONFIG_KEYS.PORT.value in raw:
                cfg.port = ValueParser.parse_port(raw[constants.CONFIG_KEYS.PORT.value])
            if constants.CONFIG_KEYS.MODEL.value in raw:
                cfg.model = ValueParser.parse_model(raw[constants.CONFIG_KEYS.MODEL.value])
            if constants.CONFIG_KEYS.MIN_RESOLUTION.value in raw:
                cfg.min_resolution = ValueParser.parse_resolution(raw[constants.CONFIG_KEYS.MIN_RESOLUTION.value])
            if constants.CONFIG_KEYS.EXCLUDE_DIR_PATTERNS.value in raw:
                cfg.exclude_dir_patterns = ValueParser.parse_filter(raw[constants.CONFIG_KEYS.EXCLUDE_DIR_PATTERNS.value])
            if constants.CONFIG_KEYS.PROMPT.value in raw:
                cfg.prompt = ValueParser.parse_prompt(raw[constants.CONFIG_KEYS.PROMPT.value])
            return cfg

    def __init__(self) -> None:
        self._parser = Config._ConfigFileParser()

    def load_config_file(self) -> ConfigValues:
        """
        Loads configuration from the config file.  
        ##### Variables are optional.

        Returns:
            ConfigValues: The loaded configuration values from file, with optional fields.
        """

        if not constants.CONFIG_PATH.exists():
            return ConfigValues.initialize_with_defaults()  # config does not exist, return defaults

        try:
            raw = json.loads(constants.CONFIG_PATH.read_text(encoding="utf-8-sig"))
        except Exception as ex:
            raise ConfigError(f"Failed to read {constants.CONFIG_FILENAME}: {ex}")

        if not isinstance(raw, dict):
            raise ConfigError(f"{constants.CONFIG_FILENAME} must contain a JSON object.")
        
        allowed = {e.value for e in constants.CONFIG_KEYS}
        unknown = sorted(set(raw.keys()) - allowed)
        if unknown:
            raise ConfigError(f"Unknown key(s) in config: {', '.join(unknown)}")

        loaded_config = self._parser.parse_file(raw)
        return loaded_config

    def merge_config_and_defaults(self, loaded_config: ConfigValues) -> ConfigValues:
        """
        Merges the loaded configuration with default values.  
        ##### All missing values are filled with defaults.  

        Returns:
            ConfigValues: The loaded configuration values from file, with all fields defined (from file or defaults).
        """

        loaded_and_defaults = ConfigValues.initialize_with_defaults()
        if loaded_config.recursive is not None: loaded_and_defaults.recursive = loaded_config.recursive
        if loaded_config.filter_patterns is not None: loaded_and_defaults.filter_patterns = list(loaded_config.filter_patterns)
        if loaded_config.overwrite is not None: loaded_and_defaults.overwrite = loaded_config.overwrite
        if loaded_config.output_type is not None: loaded_and_defaults.output_type = loaded_config.output_type
        if loaded_config.host is not None: loaded_and_defaults.host = loaded_config.host
        if loaded_config.port is not None: loaded_and_defaults.port = loaded_config.port
        if loaded_config.model is not None: loaded_and_defaults.model = loaded_config.model
        if loaded_config.min_resolution is not None: loaded_and_defaults.min_resolution = loaded_config.min_resolution
        if loaded_config.exclude_dir_patterns is not None: loaded_and_defaults.exclude_dir_patterns = list(loaded_config.exclude_dir_patterns)
        if loaded_config.prompt is not None: loaded_and_defaults.prompt = loaded_config.prompt

        return loaded_and_defaults

    def merge_loaded_and_defaults_with_cli_args(self,
        merged_loaded_and_default: ConfigValues,
        cli_values: ParsedArgs) -> ConfigValues:
        """
        Merges the loaded config (with defaults) with CLI arguments, giving precedence to CLI.  
        Returns:
            ConfigValues: with all variables defined as needed for processing."""

        if isinstance(cli_values.options, IndexOptions):
            merged = ConfigValues(
                input_dir=cli_values.options.input_dir,
                recursive=cli_values.options.recursive if cli_values.options.recursive is not None else merged_loaded_and_default.recursive,
                filter_patterns=cli_values.options.filter_patterns if cli_values.options.filter_patterns is not None else list(merged_loaded_and_default.filter_patterns or []),
                overwrite=cli_values.options.overwrite if cli_values.options.overwrite is not None else merged_loaded_and_default.overwrite,
                thumbnails_only=cli_values.options.thumbnails_only if cli_values.options.thumbnails_only is not None else False,
                host=cli_values.options.host if cli_values.options.host is not None else merged_loaded_and_default.host,
                port=cli_values.options.port if cli_values.options.port is not None else merged_loaded_and_default.port,
                model=cli_values.options.model if cli_values.options.model is not None else merged_loaded_and_default.model,
                min_resolution=cli_values.options.min_resolution if cli_values.options.min_resolution is not None else merged_loaded_and_default.min_resolution,
                exclude_dir_patterns=cli_values.options.exclude_dir_patterns if cli_values.options.exclude_dir_patterns is not None else list(merged_loaded_and_default.exclude_dir_patterns or []),
            )
        elif isinstance(cli_values.options, SearchOptions):
            merged = ConfigValues(
                input_dir=cli_values.options.input_dir,
                query=cli_values.options.query,
                output_type=cli_values.options.output_type if cli_values.options.output_type is not None else merged_loaded_and_default.output_type,
                output_file=cli_values.options.output_file,
            )
        elif isinstance(cli_values.options, DescribeOptions):
            merged = ConfigValues(
                input_file=cli_values.options.input_file,
                host=cli_values.options.host if cli_values.options.host is not None else merged_loaded_and_default.host,
                port=cli_values.options.port if cli_values.options.port is not None else merged_loaded_and_default.port,
                model=cli_values.options.model if cli_values.options.model is not None else merged_loaded_and_default.model,
            )
        else:
            raise ConfigError("Invalid CLI options provided.")
        
        return merged

    def build_config_for_save(self, args: ParsedArgs) -> ConfigValues:
        """
        Builds a `ConfigValues` from given `ParsedArgs`.  
        Used to save current options to config file.  
        ##### Undefined fields will not be written to the config file.

        Args:
            args (ParsedArgs): The parsed arguments to build the config from.

        Returns:
            ConfigValues: a ConfigValues instance with relevant fields set.
        """
        if isinstance(args.options, IndexOptions):
            return self._build_config_to_save_from_index_options(args.options)
        elif isinstance(args.options, SearchOptions):
            return self._build_config_to_save_from_search_options(args.options)
        elif isinstance(args.options, DescribeOptions):
            return self._build_config_to_save_from_describe_options(args.options)
        else:
            raise ConfigError("Cannot build ConfigValues from unknown ParsedArgs options.")

    def _build_config_to_save_from_index_options(self, options: IndexOptions) -> ConfigValues:
        """
        Builds a `ConfigValues` from given `IndexOptions`.  
        Used to save current options to config file.  
        #### Don't fill in all fields, only those that require saving.
        #### Undefined fields will not be written to the config file.

        Args:
            options (IndexOptions): The index options to build the config from. 

        Returns:
            ConfigValues: a ConfigValues instance with the relevant IndexOptions fields.
        """
        cfg = ConfigValues()
        cfg.recursive = options.recursive
        cfg.filter_patterns = options.filter_patterns
        cfg.overwrite = options.overwrite
        cfg.thumbnails_only = options.thumbnails_only
        cfg.min_resolution = options.min_resolution
        cfg.exclude_dir_patterns = options.exclude_dir_patterns
        cfg.host = options.host
        cfg.port = options.port
        cfg.model = options.model
        cfg.prompt = options.prompt
        return cfg

    def _build_config_to_save_from_search_options(self, options: SearchOptions) -> ConfigValues:
        """
        Builds a `ConfigValues` from given `SearchOptions`.  
        Used to save current options to config file.  
        #### Undefined fields will not be written to the config file.
        
        Args:
            options (SearchOptions): The search options to build the config from.
        
        Returns:
            ConfigValues: a ConfigValues instance with the relevant SearchOptions fields.
        """
        cfg = ConfigValues()
        cfg.output_type = options.output_type
        return cfg

    def _build_config_to_save_from_describe_options(self, options: DescribeOptions) -> ConfigValues:
        """
        Builds a `ConfigValues` from given `DescribeOptions`.  
        Used to save current options to config file.  
        #### Undefined fields will not be written to the config file.
        
        Args:
            options (DescribeOptions): The describe options to build the config from.
        
        Returns:
            ConfigValues: a ConfigValues instance with the relevant DescribeOptions fields.
        """
        cfg = ConfigValues()
        cfg.host = options.host
        cfg.port = options.port
        cfg.model = options.model
        cfg.prompt = options.prompt
        return cfg


    def _is_config_defined(self, cfg_payload: ConfigValues) -> bool:
        """Checks if any of the config values in the payload are defined (not None)."""
        for key in constants.CONFIG_KEYS:
            if getattr(cfg_payload, key.value) is not None:
                return True
        return False
    
    def _is_config_fully_defined(self, cfg_payload: ConfigValues) -> bool:
        """Checks if all config values in the payload are defined (not None)."""
        for key in constants.CONFIG_KEYS:
            if getattr(cfg_payload, key.value) is None:
                return False
        return True

    def save_config_file(
        self,
        write_config_payload: ConfigValues,
    ) -> None:
        """Writes the provided config values to the config file.  
        Only values that are not None will be written.  
        Uses a ConfigValues as input."""
        if not self._is_config_defined(write_config_payload):
            return

        existing = {}
        if constants.CONFIG_PATH.exists():
            try:
                existing = json.loads(constants.CONFIG_PATH.read_text(encoding="utf-8-sig"))
            except Exception as ex:
                raise ConfigError(f"Failed to read {constants.CONFIG_FILENAME}: {ex}")
            if not isinstance(existing, dict):
                raise ConfigError(f"{constants.CONFIG_FILENAME} must contain a JSON object.")

        updated: dict[str, Any] = dict(existing)
        if write_config_payload.recursive is not None:
            updated[constants.CONFIG_KEYS.RECURSIVE.value] = write_config_payload.recursive
        if write_config_payload.filter_patterns is not None:
            updated[constants.CONFIG_KEYS.FILTER.value] = ";".join(write_config_payload.filter_patterns)
        if write_config_payload.overwrite is not None:
            updated[constants.CONFIG_KEYS.OVERWRITE.value] = write_config_payload.overwrite
        if write_config_payload.output_type is not None:
            updated[constants.CONFIG_KEYS.OUTPUT_TYPE.value] = write_config_payload.output_type
        if write_config_payload.host is not None:
            updated[constants.CONFIG_KEYS.HOST.value] = write_config_payload.host
        if write_config_payload.port is not None:
            updated[constants.CONFIG_KEYS.PORT.value] = write_config_payload.port
        if write_config_payload.model is not None:
            updated[constants.CONFIG_KEYS.MODEL.value] = write_config_payload.model
        if write_config_payload.prompt is not None:
            updated[constants.CONFIG_KEYS.PROMPT.value] = write_config_payload.prompt

        allowed = {e.value for e in constants.CONFIG_KEYS}
        unknown = sorted(set(updated.keys()) - allowed)
        if unknown:
            raise ConfigError(f"Unknown key(s) in config: {', '.join(unknown)}")

        constants.CONFIG_PATH.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class ConfigError(Exception):
    pass

@dataclass
class ConfigValues:
    """
    Holds configuration values loaded from file or to write to file.  
    ##### Values may be `None` if not defined in the loaded config file or not to be saved to file.  
    > Use static builder when writing config to file.  
    """
    recursive: bool | None = None
    filter_patterns: list[str] | None = None
    overwrite: OverwriteMode | None = None
    output_type: OutputType | None = None
    thumbnails_only: bool | None = None
    host: str | None = None
    port: int | None = None
    model: str | None = None
    min_resolution: int | None = None
    exclude_dir_patterns: list[str] | None = field(default_factory=lambda: list(constants.DEFAULT_EXCLUDE_DIR_PATTERNS))
    prompt: str | None = None
    input_dir: Path | None = None
    input_file: Path | None = None
    query: str | None = None
    output_file: Path | None = None

    @staticmethod
    def initialize_with_defaults() -> 'ConfigValues':
        """
        Initializes a `ConfigValues` with default values.  
        ##### If config present and loaded, those values will override the defaults.  
        ##### Any command-line provided values will override both config and defaults.

        Returns:
            ConfigValues: A ConfigValues instance with all fields set to defaults.
        """
        cfg = ConfigValues()
        cfg.recursive = constants.DEFAULT_RECURSIVE
        cfg.filter_patterns = list(constants.DEFAULT_FILTER_PATTERNS)
        cfg.overwrite = constants.DEFAULT_OVERWRITE_MODE
        cfg.output_type = constants.DEFAULT_OUTPUT_TYPE
        cfg.thumbnails_only = constants.DEFAULT_THUMBNAILS_ONLY
        cfg.host = constants.DEFAULT_HOST
        cfg.port = constants.DEFAULT_PORT
        cfg.model = constants.DEFAULT_MODEL
        cfg.min_resolution = constants.DEFAULT_MIN_RESOLUTION
        cfg.exclude_dir_patterns = list(constants.DEFAULT_EXCLUDE_DIR_PATTERNS)
        cfg.prompt = constants.DEFAULT_PROMPT
        return cfg
