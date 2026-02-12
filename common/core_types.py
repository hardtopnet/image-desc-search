from __future__ import annotations

from pathlib import Path
from typing import Literal, get_args
from typing import Any, TypeAlias

OverwriteMode = Literal["always", "older", "never"]
OutputType = Literal["text", "json"]

_OVERWRITE_MODES = frozenset(get_args(OverwriteMode))
_OUTPUT_TYPES = frozenset(get_args(OutputType))

def is_overwrite_mode(val: str) -> bool:
    return val in _OVERWRITE_MODES

def is_output_type(val: str) -> bool:
    return val in _OUTPUT_TYPES

Payload: TypeAlias = dict[str, str | bool | int | list[dict[str, Any]]] | dict[str, str | None]

class DescribeOptions():
    input_file: Path | None
    host: str | None
    port: int | None
    model: str | None
    prompt: str | None

    def __init__(self) -> None:
        self.input_file = None
        self.host = None
        self.port = None
        self.model = None
        self.prompt = None

    def validate(self) -> None:
        """
        Validates the current option values.

        Raises:
            ValueError: If any of the values is invalid.
        """
        if self.input_file is None:
            raise ValueError("input_file is not defined")
        if not self.input_file.exists() or not self.input_file.is_file():
            raise ValueError(f"Invalid file for --input: {self.input_file}")
        if self.prompt is not None and self.prompt.strip() == "":
            raise ValueError("Prompt cannot be empty if defined.")

    def is_defined(self, options: DescribeOptions) -> bool:
        """
        Checks if all option values are defined.

        Returns:
            bool: True if all option values are defined, False otherwise.
        """
        return (
            options.input_file is not None and
            options.host is not None and
            options.port is not None and
            options.model is not None and
            options.prompt is not None
        )

class IndexOptions():
    input_dir: Path | None
    recursive: bool | None
    filter_patterns: list[str] | None
    overwrite: OverwriteMode | None
    host: str | None
    port: int | None
    model: str | None
    thumbnails_only: bool | None
    min_resolution: int | None
    exclude_dir_patterns: list[str] | None
    prompt: str | None

    def __init__(self) -> None:
        self.input_dir = None
        self.recursive = None
        self.filter_patterns = None
        self.overwrite = None
        self.host = None
        self.port = None
        self.model = None
        self.thumbnails_only = None
        self.min_resolution = None
        self.exclude_dir_patterns = None
        self.prompt = None

    def validate(self) -> None:
        """
        Validates the current option values.

        Raises:
            ValueError: If any of the values is invalid.
        """

        if self.input_dir is None:
            raise ValueError("input_dir is not defined")
        if not self.input_dir.exists() or not self.input_dir.is_dir():
            raise ValueError(f"Invalid directory for --input: {self.input_dir}")
        if self.prompt is not None and self.prompt.strip() == "":
            raise ValueError("Prompt cannot be empty if defined.")

    def is_defined(self, options: IndexOptions) -> bool:
        """
        Checks if all option values are defined.

        Returns:
            bool: True if all option values are defined, False otherwise.
        """
        return (
            options.input_dir is not None and
            options.recursive is not None and
            options.filter_patterns is not None and
            options.overwrite is not None and
            options.host is not None and
            options.port is not None and
            options.model is not None and
            options.thumbnails_only is not None and
            options.min_resolution is not None and
            options.exclude_dir_patterns is not None and
            options.prompt is not None
        )

class SearchOptions():
    query: str | None
    input_dir: Path | None
    output_type: OutputType | None
    output_file: Path | None

    def __init__(self) -> None:
        self.query = None
        self.input_dir = None
        self.output_type = None
        self.output_file = None

    def validate(self) -> None:
        """
        Validates the current option values.

        Raises:
            ValueError: If any of the values is invalid.
        """

        if self.input_dir is None:
            raise ValueError("input_dir is not defined")
        if not self.input_dir.exists() or not self.input_dir.is_dir():
            raise ValueError(f"Invalid directory for --input: {self.input_dir}")
   