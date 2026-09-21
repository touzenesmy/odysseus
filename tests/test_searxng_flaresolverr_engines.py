"""Regression guards for the FlareSolverr-backed SearXNG engines.

Some hosts have their outbound IP CAPTCHA/429-blocked by the stock search
engines (duckduckgo, brave, startpage) and geo-poisoned on bing, which leaves
SearXNG returning ~1 result for a general query. The fix is a set of custom
engines that route each query through a FlareSolverr browser (real headless
Chrome) and parse the returned HTML. See scripts/searxng_engines/flaresolverr_engines.py.

These tests pin the wiring so the setup can't silently rot:

- the custom-engine module exists at a tracked path and is valid Python that
  exposes the per-site presets the settings template references;
- every compose file's searxng service bind-mounts that module into the engine
  directory (through an overridable path variable) so it survives recreate;
- the settings template registers the ddgfs/bravefs/bingfs engines, keeps them
  opt-in (disabled by default so hosts without flaresolverr are unaffected),
  and leaves the stock engines enabled by default for unaffected hosts.

The engine module imports lxml, which is not an Odysseus dependency, so the
structural checks read the source as text instead of importing it.
"""
import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ENGINE_FILE = ROOT / "scripts" / "searxng_engines" / "flaresolverr_engines.py"
SETTINGS_TEMPLATE = ROOT / "config" / "searxng" / "settings.yml"
CONTAINER_ENGINE_PATH = "/usr/local/searxng/searx/engines/flaresolverr_engines.py"
# Every compose file at the repo root, matched by name pattern — tracked or
# host-specific (a gitignored baremetal variant may live here too). Anything
# that defines a searxng service must mount the engine module, so a stack
# switch can't silently kill ddgfs/bravefs/bingfs.
def _root_compose_files():
    return sorted(
        f
        for f in ROOT.iterdir()
        if f.is_file()
        and "docker-compose" in f.name
        and f.suffix in (".yml", ".yaml")
    )
CUSTOM_ENGINES = ("ddgfs", "bravefs", "bingfs")
STOCK_ENGINES = ("duckduckgo", "brave", "startpage", "bing")


def test_engine_module_is_valid_python_at_tracked_path():
    assert ENGINE_FILE.is_file(), (
        f"{ENGINE_FILE} missing — the compose searxng services bind-mount it; "
        "keep the custom FlareSolverr engine module tracked in the repo"
    )
    source = ENGINE_FILE.read_text(encoding="utf-8")
    # Parses under the repo interpreter without importing (lxml not required).
    tree = ast.parse(source, filename=str(ENGINE_FILE))
    assert tree.body, "engine module parsed to an empty AST"


def test_engine_module_exposes_required_hooks_and_sites():
    source = ENGINE_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    # SearXNG engine protocol hooks the module must define.
    assert {"request", "response"} <= functions, (
        f"engine module must define request/response hooks, found {sorted(functions)}"
    )
    # The per-site presets the settings template selects via `site:`.
    for site in ("ddg", "brave", "bing"):
        assert f'"{site}"' in source or f"'{site}'" in source, (
            f"engine module missing the {site!r} site preset referenced by settings"
        )


def test_every_compose_file_mounts_engine_module():
    files = _root_compose_files()
    assert files, "expected at least docker-compose.yml at the repo root"
    checked = []
    for path in files:
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue  # not plain YAML — nothing to check here
        services = (doc or {}).get("services") or {}
        if "searxng" not in services:
            continue  # no searxng service in this file — not our concern
        checked.append(path.name)
        text = path.read_text(encoding="utf-8")
        assert CONTAINER_ENGINE_PATH in text, (
            f"{path.name} does not mount the custom engine module into "
            f"{CONTAINER_ENGINE_PATH}; the engines vanish on container recreate"
        )
        assert "SEARXNG_CUSTOM_ENGINES_PATH" in text, (
            f"{path.name} must mount the engine via the overridable "
            "SEARXNG_CUSTOM_ENGINES_PATH variable"
        )
        # The default path must be the tracked scripts location, not gitignored ./data.
        default_mount = re.search(
            r"\$\{SEARXNG_CUSTOM_ENGINES_PATH:-([^}]+)\}", text
        )
        assert default_mount, f"{path.name}: mount default not found"
        assert default_mount.group(1).startswith("./scripts/"), (
            f"{path.name} engine default must live under tracked ./scripts/, "
            f"got {default_mount.group(1)!r} (./data is gitignored and would not be versioned)"
        )
    assert "docker-compose.yml" in checked, (
        "the shipped docker-compose.yml stack must be present and checked"
    )


def _template_engines():
    loaded = yaml.safe_load(SETTINGS_TEMPLATE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "settings template root must be a mapping"
    engines = loaded.get("engines")
    assert isinstance(engines, list), "settings template must define an engines list"
    return {e.get("name"): e for e in engines if isinstance(e, dict)}


def test_settings_template_registers_custom_engines_opt_in():
    engines = _template_engines()
    for name in CUSTOM_ENGINES:
        assert name in engines, f"settings template missing the {name!r} engine"
        entry = engines[name]
        assert entry.get("engine") == "flaresolverr_engines", (
            f"{name!r} must use the flaresolverr_engines module"
        )
        assert entry.get("disabled") is True, (
            f"{name!r} must be opt-in (disabled: true) so hosts without a "
            "flaresolverr instance are unaffected; enable per-host in the live volume"
        )
        assert entry.get("enable_http") is True, (
            f"{name!r} needs enable_http: true to reach flaresolverr over plain http"
        )


def test_settings_template_leaves_stock_engines_enabled_by_default():
    engines = _template_engines()
    for name in STOCK_ENGINES:
        entry = engines.get(name)
        if entry is None:
            continue  # absent = stock default (enabled)
        assert entry.get("disabled") is not True, (
            f"stock engine {name!r} must stay enabled by default in the template; "
            "disable it per-host in the live volume only, or unaffected installs "
            "lose their working engines"
        )
