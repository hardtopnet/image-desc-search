# image-desc-search

Index images with a vision model (Ollama) and search them by text. Includes a fast Tkinter GUI for browsing search results as thumbnails.

## Requirements

- Windows (primary target) or any OS supported by Python/Tkinter
- Python 3.11+ recommended
- Dependencies are listed in `requirements.txt`
- Optional (for description indexing): Ollama running locally or remotely

Install dependencies:

```powershell
cd d:\DEV\_LLM\Tools\image-desc-search
pip install -r .\requirements.txt
```

## Quick start

Show help:

```powershell
python .\main.py --help
```

This repository uses `main.py` as the entry point.

## Modes

### `index`

Indexes image files into a SQLite database. Depending on flags, it can generate:

- Thumbnails (used by the GUI)
- Text descriptions (requires Ollama)

Examples:

```powershell
python .\main.py index -i "C:\\Users\\me\\Pictures" -r
python .\main.py index -i "C:\\Users\\me\\Pictures" -f "*.jpg" -o older
python .\main.py index -i "C:\\Users\\me\\Pictures" -r --exclude_dirs "thumbnails;tmp" --min_resolution 800
python .\main.py index -i "C:\\Users\\me\\Pictures" -r --host localhost --port 11434 --model llava:latest
```

Thumbnails-only indexing (no Ollama required):

```powershell
python .\main.py index -i "C:\\Users\\me\\Pictures" -r -t
```

Notes:

- The SQLite database is stored under your user AppData folder (see "Paths" below).
- When descriptions are enabled, the CLI tests the Ollama connection and verifies the model name before indexing.

### `search`

Searches the database for a text query and prints results as text or JSON.

Examples:

```powershell
python .\main.py search -q "a child holding a balloon"
python .\main.py search -q "a child holding a balloon" -i "C:\\Users\\me\\Pictures" -t json
python .\main.py search -q "sunset over the sea" -f "D:\\tmp\\results.json" -t json
```

### `describe`

Generates a description for a single image (requires Ollama).

```powershell
python .\main.py describe -i "C:\\Users\\me\\Pictures\\img001.jpg" --host localhost --port 11434 --model llava:latest
```

### `gui`

Launches a Tkinter GUI to search and browse results as thumbnails.

```powershell
python .\main.py gui
```

Current behavior (high level):

- Canvas-based virtualized grid for large result sets
- Async thumbnail loading
- Uses thumbnails stored in the database, with a disk cache under AppData
- Double-click a card to open the file

## Configuration (`config.json`)

If `config.json` exists, it is loaded and merged with CLI arguments.
Priority: hardcoded defaults < config file < CLI arguments.

Accepted keys (most common):

- `recursive`: `true|false`
- `filter_patterns`: string like `"*.png;*.jpg"` (semicolon-separated) or a list of strings
- `overwrite`: `always|older|never`
- `output_type`: `text|json`
- `host`: Ollama host
- `port`: Ollama port
- `model`: Ollama model name
- `exclude_dir_patterns`: string/list, same format as `filter_patterns`
- `min_resolution`: integer (filters images by max(width,height))
- `prompt`: string prompt used for description generation

Example:

```json
{
  "recursive": true,
  "overwrite": "older",
  "model": "llava:latest"
}
```

## Paths

By default, the project stores data under AppData:

- Database: `%APPDATA%\\image-desc-search\\image-desc-search.sqlite3`
- Disk cache: `%APPDATA%\\image-desc-search\\cache\\`
- GUI state: `%APPDATA%\\image-desc-search\\.gui_state.json`

If `%APPDATA%` is not available, it falls back to `~/.image-desc-search/`.
