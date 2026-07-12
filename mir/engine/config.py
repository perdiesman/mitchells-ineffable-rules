import os
import argparse
import yaml
from typing import List, Dict, Any, Optional

from mir.engine.rules_help import handle_rule_help

DEFAULT_CONFIG_FILES = [".ir-config.yaml", ".ir-config.yml"]

class Config:
    def __init__(self):
        self.rules_to_disable: List[str] = []
        self.fix: bool = False
        self.dry_run: bool = False
        self.verbose: bool = False
        self.paths: List[str] = []
        self.rule_configs: Dict[str, Any] = {}
        self.config_file_path: Optional[str] = None
        self.include_dirs: List[str] = []
        self.rule_mode: str = "extend"
        self.content: Optional[str] = None
        self.lang: Optional[str] = None
        self.disable_all: bool = False
        self.rules_to_enable: List[str] = []
        self.quiet: bool = False
        self.warnings_only: bool = False
        self.no_warnings: bool = False

def load_config(args_list: Optional[List[str]] = None) -> Config:
    # 1. Parse CLI arguments first to check for config path, flags, and targets
    parser = argparse.ArgumentParser(
        description="Mitchell's Ineffable Rules (IR) Linter - Java, XML, SQL",
        add_help=False  # Disable default help to use custom rule help logic
    )
    parser.add_argument(
        "-h", "--help",
        nargs="?",
        const="standard",
        help="Show this help message. Specify 'rules', 'rules:<lang>', 'docs', 'docs:<path>', '<rule_id>', or '<lang>:<rule_id>' for details."
    )
    parser.add_argument(
        "--version",
        action="version",
        version="mir-linter 0.1.0a3",
        help="Show version information"
    )
    parser.add_argument("paths", nargs="*", help="Files or directories to lint")
    parser.add_argument("-c", "--config", help="Path to config file")
    parser.add_argument("--fix", action="store_true", default=None, help="Fix rule violations where possible")
    parser.add_argument("--dry-run", action="store_true", default=None, help="Show fixes without applying them")
    parser.add_argument("-v", "--verbose", action="store_true", default=None, help="Verbose output (shows descriptions and offending lines)")
    parser.add_argument("--disable", help="Comma-separated list of rule IDs to disable globally")
    parser.add_argument("--include-dir", action="append", help="Directory containing custom rules for extending or replacing rule sets")
    parser.add_argument("--rule-mode", choices=["extend", "replace"], help="Rule mode: 'extend' (default) or 'replace'")
    parser.add_argument("--content", help="Raw string of content to lint")
    parser.add_argument("--lang", "--language", dest="lang", help="Language of the content (required if using --content or piping stdin)")
    parser.add_argument("--disable-all", action="store_true", default=None, help="Disable all rules by default")
    parser.add_argument("--enable", help="Comma-separated list of rule IDs to enable")
    parser.add_argument("-q", "--quiet", action="store_true", default=None, help="Quiet mode (no output, just set appropriate exit code)")
    parser.add_argument("--warnings-only", action="store_true", default=None, help="Only show warnings")
    parser.add_argument("--no-warnings", action="store_true", default=None, help="Hide all warnings")
    
    parsed_args = parser.parse_args(args_list)
    
    config = Config()
    config.paths = parsed_args.paths or ["."]
    
    # 2. Determine config file path
    # CLI > Env > Default files
    cli_config_path = parsed_args.config
    env_config_path = os.environ.get("IR_CONFIG")
    
    config_file_to_load = None
    if cli_config_path:
        config_file_to_load = cli_config_path
    elif env_config_path:
        config_file_to_load = env_config_path
    else:
        for f in DEFAULT_CONFIG_FILES:
            if os.path.exists(f):
                config_file_to_load = f
                break
                
    # 3. Load config file if it exists
    file_config: Dict[str, Any] = {}
    if config_file_to_load:
        if os.path.exists(config_file_to_load):
            config.config_file_path = config_file_to_load
            try:
                with open(config_file_to_load, "r", encoding="utf-8") as f:
                    content = yaml.safe_load(f)
                    if isinstance(content, dict):
                        file_config = content
            except Exception as e:
                print(f"Warning: Failed to load config file '{config_file_to_load}': {e}")
        elif cli_config_path:
            # If user explicitly passed a config file and it doesn't exist, raise error or print warning
            print(f"Warning: Specified config file '{cli_config_path}' does not exist.")
            
    # 4. Resolve variables with precedence: CLI > Env > Config File > Default
    
    # -- fix --
    if parsed_args.fix is not None:
        config.fix = parsed_args.fix
    elif os.environ.get("IR_FIX") is not None:
        config.fix = os.environ.get("IR_FIX").lower() in ("true", "1", "yes")
    else:
        config.fix = file_config.get("fix", False)
        
    # -- dry_run --
    if parsed_args.dry_run is not None:
        config.dry_run = parsed_args.dry_run
    elif os.environ.get("IR_DRY_RUN") is not None:
        config.dry_run = os.environ.get("IR_DRY_RUN").lower() in ("true", "1", "yes")
    else:
        config.dry_run = file_config.get("dry_run", False)
        
    # -- verbose --
    if parsed_args.verbose is not None:
        config.verbose = parsed_args.verbose
    elif os.environ.get("IR_VERBOSE") is not None:
        config.verbose = os.environ.get("IR_VERBOSE").lower() in ("true", "1", "yes")
    else:
        config.verbose = file_config.get("verbose", False)
        
    # -- disable --
    disabled_rules_set = set()
    
    # 1. Config file disabled rules
    file_disabled = file_config.get("disable", [])
    if isinstance(file_disabled, list):
        for r in file_disabled:
            if isinstance(r, str):
                disabled_rules_set.add(r.strip())
                
    # 2. Env disabled rules
    env_disable = os.environ.get("IR_DISABLE")
    if env_disable:
        for r in env_disable.split(","):
            disabled_rules_set.add(r.strip())
            
    # 3. CLI disabled rules
    cli_disable = parsed_args.disable
    if cli_disable:
        for r in cli_disable.split(","):
            disabled_rules_set.add(r.strip())
            
    config.rules_to_disable = sorted(list(disabled_rules_set))
    
    # -- rule_mode --
    if parsed_args.rule_mode is not None:
        config.rule_mode = parsed_args.rule_mode
    elif os.environ.get("IR_RULE_MODE") is not None:
        config.rule_mode = os.environ.get("IR_RULE_MODE").lower()
    else:
        config.rule_mode = file_config.get("rule_mode", "extend")
        
    if config.rule_mode not in ("extend", "replace"):
        config.rule_mode = "extend"
        
    # -- include_dirs --
    cli_include = parsed_args.include_dir
    env_include = os.environ.get("IR_INCLUDE_DIRS")
    file_include = file_config.get("include_dirs", [])
    
    resolved_include_dirs = []
    if cli_include:
        for path in cli_include:
            for p in path.split(","):
                resolved_include_dirs.append(p.strip())
    elif env_include:
        for p in env_include.split(","):
            resolved_include_dirs.append(p.strip())
    elif isinstance(file_include, list):
        for p in file_include:
            if isinstance(p, str):
                resolved_include_dirs.append(p.strip())
                
    config.include_dirs = [p for p in resolved_include_dirs if p]
    
    # Load rules-specific configurations from file
    config.rule_configs = file_config.get("rules", {})
    if not isinstance(config.rule_configs, dict):
        config.rule_configs = {}
        
    # -- content and lang --
    config.content = parsed_args.content
    config.lang = parsed_args.lang or os.environ.get("IR_LANG") or file_config.get("lang")
    
    # -- disable_all --
    if parsed_args.disable_all is not None:
        config.disable_all = parsed_args.disable_all
    elif os.environ.get("IR_DISABLE_ALL") is not None:
        config.disable_all = os.environ.get("IR_DISABLE_ALL").lower() in ("true", "1", "yes")
    else:
        config.disable_all = file_config.get("disable_all", False)
        
    # -- rules_to_enable --
    enabled_rules_set = set()
    file_enabled = file_config.get("enable", [])
    if isinstance(file_enabled, list):
        for r in file_enabled:
            if isinstance(r, str):
                enabled_rules_set.add(r.strip())
    env_enable = os.environ.get("IR_ENABLE")
    if env_enable:
        for r in env_enable.split(","):
            enabled_rules_set.add(r.strip())
    cli_enable = parsed_args.enable
    if cli_enable:
        for r in cli_enable.split(","):
            enabled_rules_set.add(r.strip())
    config.rules_to_enable = sorted(list(enabled_rules_set))
    
    # -- quiet --
    if parsed_args.quiet is not None:
        config.quiet = parsed_args.quiet
    elif os.environ.get("IR_QUIET") is not None:
        config.quiet = os.environ.get("IR_QUIET").lower() in ("true", "1", "yes")
    else:
        config.quiet = file_config.get("quiet", False)
        
    # -- warnings_only --
    if parsed_args.warnings_only is not None:
        config.warnings_only = parsed_args.warnings_only
    elif os.environ.get("IR_WARNINGS_ONLY") is not None:
        config.warnings_only = os.environ.get("IR_WARNINGS_ONLY").lower() in ("true", "1", "yes")
    else:
        config.warnings_only = file_config.get("warnings_only", False)
        
    # -- no_warnings --
    if parsed_args.no_warnings is not None:
        config.no_warnings = parsed_args.no_warnings
    elif os.environ.get("IR_NO_WARNINGS") is not None:
        config.no_warnings = os.environ.get("IR_NO_WARNINGS").lower() in ("true", "1", "yes")
    else:
        config.no_warnings = file_config.get("no_warnings", False)
        
    # 5. Handle rule help AFTER config resolution so that include_dirs and rule_mode are resolved
    if parsed_args.help is not None:
        handle_rule_help(parsed_args.help, parser, config.include_dirs, config.rule_mode)
        
    return config
