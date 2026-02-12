from typing import Any, cast
from urllib.parse import urlparse

from common.core_types import OutputType, OverwriteMode, is_output_type, is_overwrite_mode

class ValueParserError(Exception):
    pass

class ValueParser:
    def __new__(cls, *args, **kwargs):
        # Prevent instantiation of this utility class.
        raise TypeError("ValueParser is a static utility class and cannot be instantiated")

    @staticmethod
    def parse_filter(value: Any) -> list[str]:
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(";")]
            parts = [p for p in parts if p]
            if not parts:
                raise ValueParserError("Invalid value for 'filter'.")
            return parts
        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            parts = [x.strip() for x in value]
            parts = [p for p in parts if p]
            if not parts:
                raise ValueParserError("Invalid value for 'filter'.")
            return parts
        raise ValueParserError("Invalid value for 'filter'.")

    @staticmethod
    def parse_overwrite(value: Any) -> OverwriteMode:
        if not isinstance(value, str):
            raise ValueParserError("Invalid value for 'overwrite'.")
        val = value.strip().lower()

        if not is_overwrite_mode(val):
            raise ValueParserError("Invalid value for 'overwrite'.")
        return cast(OverwriteMode, val)

    @staticmethod
    def parse_output_type(value: Any) -> OutputType:
        if not isinstance(value, str):
            raise ValueParserError("Invalid value for 'output_type'.")
        val = value.strip().lower()

        if not is_output_type(val):
            raise ValueParserError("Invalid value for 'output_type'.")
        return cast(OutputType, val)

    @staticmethod
    def parse_recursive(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        raise ValueParserError("Invalid value for 'recursive'.")

    @staticmethod
    def parse_host(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueParserError("Invalid value for 'host'.")
        val = value.strip()
        if not val:
            raise ValueParserError("Invalid value for 'host'.")
        return val

    @staticmethod
    def parse_port(value: Any) -> int:
        if isinstance(value, int):
            port = value
        elif isinstance(value, str) and value.strip().isdigit():
            port = int(value.strip())
        else:
            raise ValueParserError("Invalid value for 'port'.")
        if port < 1 or port > 65535:
            raise ValueParserError("Invalid value for 'port'.")
        return port

    @staticmethod
    def parse_resolution(value: Any) -> int:
        if isinstance(value, int):
            return value
        elif isinstance(value, str):
            s = value.strip()
            if not s.isdigit():
                raise ValueParserError("Invalid value for 'resolution'.")
            res = int(s)
            if res < 1:
                raise ValueParserError("Invalid value for 'resolution'.")
            return res
        raise ValueParserError("Invalid value for 'resolution'.")

    @staticmethod
    def parse_model(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueParserError("Invalid value for 'model'.")
        val = value.strip()
        if not val:
            raise ValueParserError("Invalid value for 'model'.")
        return val
    
    @staticmethod
    def parse_prompt(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueParserError("Invalid value for 'prompt'.")
        val = value.strip()
        if not val:
            raise ValueParserError("Invalid value for 'prompt'.")
        return val

    @staticmethod
    def normalize_host(raw: str) -> str:
        host = raw.strip()
        if not host:
            raise ValueParserError("Invalid host.")

        parsed = urlparse(host)
        if parsed.scheme in ("http", "https"):
            return host.rstrip("/")
        
        # Allow bare hostname/IP.
        return host