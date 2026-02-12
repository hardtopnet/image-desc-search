from __future__ import annotations

from textwrap import dedent
from common import constants

def usage() -> str:
    default_filter = ";".join(constants.DEFAULT_FILTER_PATTERNS)
    return dedent(
      """\
        Usage:
          image-desc-search [-h|--help] <mode> [options]

        Modes:
          index   Index image files and store descriptions in SQLite.
          search  Search indexed images using a text query.
          describe  Describe a single image using Ollama.
          gui     Start the graphical user interface.

        Global options:
          -h, --help                 Show this help and exit.

        Index mode options:
          -i, --input <path>         Input directory to process (required).
          -r, --recursive            Recurse into subdirectories (default: false).
          -f, --filter <patterns>    Semicolon-separated wildcards (default: {default_filter}).
          --exclude_dirs <patterns>  Exclude directory patterns (default: thumbnails;temp;tmp).
          --min_resolution <int>     Only include images with max(width,height) >= value (default: 1).
          -o, --overwrite <mode>     Existing entries policy: always|older|never (default: older).
          -t, --thumbnails_only      Only generate thumbnails (no Ollama required).
          --prompt <text>            Prompt for description generation.
          --host <address>           Ollama server address (default: localhost).
          --port <port>              Ollama server port (default: 11434).
          --model <model_name>       Vision model to use (default: llava:latest).
          -w, --write_defaults       Persist provided options to config.json.
          -v, --verbose              Enable verbose logging.

        Search mode options:
          -q, --query <text>         Search query (required).
          -i, --input <path>         Directory scope (default: all).
          -t, --output_type <type>   Output type: text|json (default: text).
          -f, --file <path>          Write output to file (default: stdout).
          -w, --write_defaults       Persist provided options to config.json.
          -v, --verbose              Enable verbose logging.

        Describe mode options:
          -i, --input <path>         Input image file to describe (required).
          --prompt <text>            Prompt for description generation.
          --host <address>           Ollama server address (default: localhost).
          --port <port>              Ollama server port (default: 11434).
          --model <model_name>       Vision model to use (default: llava:latest).
          -w, --write_defaults       Persist provided options to config.json.
          -v, --verbose              Enable verbose logging.

        GUI mode options:
          -w, --write_defaults       Persist provided options to config.json.
          -v, --verbose              Enable verbose logging.
        """
      ).format(
        default_filter=default_filter,
      )
