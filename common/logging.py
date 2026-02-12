import sys
from datetime import datetime
import json

from common.core_types import Payload

class Logging():
    verbose: bool = False
    
    def set_verbosity(self, verbose: bool) -> None:
        self.verbose = verbose

    def error(self, message: str | Payload, force: bool = False) -> None:
        if self.verbose or force:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(message, dict):
                self._out_json(message, force=force)
            else: 
                print(f"[{ts}] {message}", file=sys.stderr)
                
    def out(self, message: str | Payload, force: bool = False) -> None:
        if self.verbose or force:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(message, dict):
                self._out_json(message, force=force)
            else: 
                print(f"[{ts}] {message}", file=sys.stdout)

    def _out_json(self, obj: object, force: bool = False) -> None:
        json_string = json.dumps(obj, indent=2, ensure_ascii=False)
        json_string = json_string.splitlines()
        for line in json_string:
            self.out(line, force=force)
