from __future__ import annotations

import sys
import json
from pathlib import Path

from cli.cli_exceptions import CliError
from cli import args_parser
from cli.cli_usage import usage

from common import constants
from common.config import ConfigError, Config
from common.db import connect, migrate
from common.image_meta import ImageMetadata
from common.indexer import ConsoleIndexLogger, Indexer
from common.searcher import Searcher
from common.logging import Logging
from common.ollama_handler import OllamaHandler
from gui.app import run_gui


def _collect_image_files(root: Path, *, recursive: bool, file_patterns: list[str], exclude_dir_patterns: list[str], min_resolution: int) -> list[Path]:
    results: list[Path] = []

    def _iter_dir(dir_path: Path) -> None:
        for exclude_pattern in exclude_dir_patterns:
            if dir_path.match(exclude_pattern):
                return
        for pattern in file_patterns:
            for p in dir_path.glob(pattern):
                if p.is_file():
                    res = ImageMetadata.image_resolution(p)
                    maxres = 0
                    
                    if res is not None:
                        maxres = max(res.h, res.w)
                    
                    if maxres >= min_resolution:
                        results.append(p)

    _iter_dir(root)
    if recursive:
        for dir_path in (p for p in root.rglob("*") if p.is_dir()):
            _iter_dir(dir_path)

    seen: set[str] = set()
    unique: list[Path] = []
    for p in results:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)

    unique.sort(key=lambda x: str(x))
    return unique


def run(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)

    parser = args_parser.ArgsParser()
    logging = Logging()
    config = Config()
    loaded_config = config.load_config_file()
    loaded_and_default_config = config.merge_config_and_defaults(loaded_config)

    if parser.is_help_requested(argv):
        logging.out(usage(), force=True)
        return 0

    try:
        parsed_args = parser.parse_args(argv)
    except ConfigError as ex:
        logging.error(f"Error: {ex}")
        logging.error(usage())
        return 2
    except CliError as ex:
        logging.error(f"Error: {ex}")
        logging.error(usage())
        return 2
    
    # merge configfile/defaults with parsed args
    config_values = config.merge_loaded_and_defaults_with_cli_args(loaded_and_default_config, parsed_args)
    config_for_save = config.build_config_for_save(parsed_args)

    logging.set_verbosity(parsed_args.verbose)

    try:
        if (parsed_args.write_defaults):
            config.save_config_file(config_for_save)

        if parsed_args.mode == "describe":
            assert config_values.input_file is not None
            assert config_values.host is not None
            assert config_values.port is not None
            assert config_values.model is not None
        
            ollama = OllamaHandler(config_values.host, config_values.port)
            
            logging.out(f"Using Ollama at {ollama.ollama_host}, testing connection")
            
            try:
                ollama.test_connection()
                logging.out("Connection to Ollama successful.")
                logging.out("Fetching available models")
                models = ollama.fetch_ollama_models()
            except CliError as ex:
                logging.error(f"Error: {ex}")
                return 2

            logging.out(f"Found {len(models)} available model{len(models) > 1 and 's' or ''}.")
            logging.out(f"Checking model availability: {config_values.model}")
            if config_values.model not in models:
                preview = ", ".join(models[:10])
                more = "" if len(models) <= 10 else f" (+{len(models) - 10} more)"
                logging.error(f"Error: Model not found on server: {config_values.model}")
                logging.error(f"Available models: {preview}{more}")
                return 2
            
            indexer = Indexer(ollama)
            desc: str = indexer.generate_description(image_path=config_values.input_file, model=config_values.model)
            logging.out(desc)
            return 0
        if parsed_args.mode == "index":
            # parsed_args.options is ensured to be IndexOptions with all values defined
            assert config_values.input_dir is not None
            assert config_values.recursive is not None
            assert config_values.filter_patterns is not None
            assert config_values.overwrite is not None
            assert config_values.thumbnails_only is not None
            assert config_values.host is not None
            assert config_values.port is not None
            assert config_values.model is not None
            assert config_values.exclude_dir_patterns is not None
            assert config_values.min_resolution is not None

            image_paths = _collect_image_files(config_values.input_dir,
                                               recursive=config_values.recursive,
                                               file_patterns=config_values.filter_patterns,
                                               exclude_dir_patterns=config_values.exclude_dir_patterns,
                                               min_resolution=config_values.min_resolution)

            logging.out(f"Found {len(image_paths)} image file(s) to index.")
            
            ollama: OllamaHandler | None = None
            if not config_values.thumbnails_only: # thumbnails only doesn't require ollama
                ollama = OllamaHandler(config_values.host, config_values.port)
                
                logging.out(f"Using Ollama at {ollama.ollama_host}, testing connection")
                
                try:
                    ollama.test_connection()
                    logging.out("Connection to Ollama successful.")
                    logging.out("Fetching available models")
                    models = ollama.fetch_ollama_models()
                except CliError as ex:
                    logging.error(f"Error: {ex}")
                    return 2

                logging.out(f"Found {len(models)} available model{len(models) > 1 and 's' or ''}.")
                logging.out(f"Checking model availability: {config_values.model}")
                if config_values.model not in models:
                    preview = ", ".join(models[:10])
                    more = "" if len(models) <= 10 else f" (+{len(models) - 10} more)"
                    logging.error(f"Error: Model not found on server: {config_values.model}")
                    logging.error(f"Available models: {preview}{more}")
                    return 2
            
            indexer = Indexer(ollama)

            logging.out(f"Connecting database at {constants.DB_PATH}")
            conn = connect(constants.DB_PATH)
            try:
                migrate(conn)
                consoleindexlogger = ConsoleIndexLogger(logging)
                logging.out(f"Starting indexing into database")
                result = indexer.index_paths(
                    conn,
                    image_paths,
                    overwrite=config_values.overwrite,
                    model=config_values.model,
                    thumbnails_only=config_values.thumbnails_only,
                    logger=consoleindexlogger,
                )
            finally:
                conn.close()

            # payload: Payload = {
            #     "mode": "index",
            #     "db": str(db_path),
            #     "input": str(idx.input_dir),
            #     "recursive": idx.recursive,
            #     "filter": ";".join(idx.filter_patterns),
            #     "overwrite": idx.overwrite,
            #     "host": idx.host,
            #     "port": idx.port,
            #     "model": idx.model,
            #     "files_found": len(image_paths),
            #     "indexed": result.indexed,
            #     "skipped": result.skipped,
            #     "warnings": [w.__dict__ for w in result.warnings],
            #     "errors": [e.__dict__ for e in result.errors],
            # }
            logging.out(f"\nIndexing complete: {result.indexed} indexed, {result.skipped} skipped, {len(result.warnings)} warnings, {len(result.errors)} errors.")
            return 1 if result.errors else 0
        elif parsed_args.mode == "search":
            assert config_values.input_dir is not None
            assert config_values.output_type is not None
            assert config_values.query is not None

            conn = connect(constants.DB_PATH)
            try:
                migrate(conn)
                searcher = Searcher()
                result = searcher.search(conn, input_dir=config_values.input_dir, query=config_values.query)
            finally:
                conn.close()

            if config_values.output_type == "json":
                payload = {
                    "mode": "search",
                    "db": str(constants.DB_PATH),
                    "input": str(config_values.input_dir),
                    "query": config_values.query,
                    "count": len(result.matches),
                    "matches": [{"path": m.path, "description": m.description} for m in result.matches],
                }
                out_text = json.dumps(payload, indent=2, ensure_ascii=False)
            else:
                lines: list[str] = []
                lines.append(f"Matches: {len(result.matches)}")
                lines.append("")
                for m in result.matches:
                    lines.append(m.path)
                    lines.append(m.description)
                    lines.append("")
                out_text = "\n".join(lines).rstrip() + "\n"

            if config_values.output_file is None:
                logging.out(out_text, force=True)
            else:
                config_values.output_file.write_text(out_text, encoding="utf-8")
                logging.out(f"Wrote results to: {config_values.output_file}")

            # payload: Payload = {
            #     "mode": "search",
            #     "query": sea.query,
            #     "input": str(sea.input_dir) if sea.input_dir else None,
            #     "output_type": sea.output_type,
            #     "file": str(sea.output_file) if sea.output_file else None,
            # }
            return 0
        elif parsed_args.mode == "gui":
            run_gui()
            return 0
        else:
            raise ConfigError(f"Invalid mode: {parsed_args.mode}")
    except ConfigError as ex:
        logging.error(f"Error: {ex}")
        return 2

if __name__ == "__main__":
    raise SystemExit(run())
