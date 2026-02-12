import enum
from pathlib import Path
import os

FONT_FAMILY = "Segoe UI"
FONT_SIZE = 9

class Mode(enum.Enum):
    INDEX = "index"
    SEARCH = "search"
    DESCRIBE = "describe"
    GUI = "gui"

def _appdir(sub: str) -> Path:
    # Windows: %APPDATA%\image-desc-search\cache
    # Fallback: ~/.image-desc-search/cache
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "image-desc-search" / sub
    return Path.home() / ".image-desc-search" / sub

# hardcoded values
DB_FILENAME = "image-desc-search.sqlite3"
CONFIG_FILENAME = "config.json"
GUISTATE_FILENAME = ".gui_state.json"
CONFIG_PATH = _appdir("") / CONFIG_FILENAME
DB_PATH = _appdir("") / DB_FILENAME
CACHE_PATH = _appdir("cache")
GUISTATE_PATH = _appdir("") / GUISTATE_FILENAME

class CONFIG_KEYS(enum.Enum):
    RECURSIVE = "recursive"
    FILTER = "filter_patterns"
    OVERWRITE = "overwrite"
    OUTPUT_TYPE = "output_type"
    HOST = "host"
    PORT = "port"
    MODEL = "model"
    MIN_RESOLUTION = "min_resolution"
    EXCLUDE_DIR_PATTERNS = "exclude_dir_patterns"
    PROMPT = "prompt"

# defaults
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 11434
DEFAULT_MODEL = "llava:latest"
DEFAULT_INPUT_DIR = Path("~/Pictures").expanduser()
DEFAULT_RECURSIVE = False
DEFAULT_OVERWRITE_MODE = "older"
DEFAULT_THUMBNAILS_ONLY = False
DEFAULT_OUTPUT_TYPE = "text"
DEFAULT_FILTER_PATTERNS = ["*.png", "*.jpg", "*.jpeg", "*.webp"]
DEFAULT_MIN_RESOLUTION = 1 # all images
DEFAULT_EXCLUDE_DIR_PATTERNS = ["thumbnails", "temp", "tmp"]
DEFAULT_PROMPT = "Describe this image. First the overall features, then focus on the people if any, then describe the background. Finally, describe the overall mood, feeling, atmosphere, and colors. Be concise but descriptive."