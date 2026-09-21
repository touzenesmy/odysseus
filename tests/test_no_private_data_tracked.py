"""Guard tests: personal data must never be committed.

The repo is shared (multiple users fork it), so user-specific state stays
outside git: data/ (skills, memories, preferences, user DB), the live
searxng settings (real secret_key), env files, and credential files.
.gitignore hides these from casual `git add .`; scripts/git-hooks/pre-commit
is the second line of defense (catches `git add -f`). These tests pin both:

- the hook exists and its rule set is intact (so the rules can't silently
  drift from what this test verifies);
- the rule set itself, mirrored here in Python, blocks the personal paths
  and lets every legitimately tracked file through;
- nothing private is actually tracked in git right now.
"""
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "scripts" / "git-hooks" / "pre-commit"

PRIVATE_PATHS = [
    "data/skills/x/SKILL.md",
    "data/memories.json",
    "data/user.db",
    "services/data/x",
    "research_data/x",
    "skills/odysseus/SKILL.md",
    "memory/user-memory.json",
    ".env",
    ".env.production",
    "secrets.yml",
    "secrets.json",
    "keys/server.key",
    "cert.pem",
    "id_rsa",
    "id_rsa.pub",
    "docker-compose.yml.bak",
    "docker-compose.yml.bak.20260920",
]

TRUSTED_PATHS = [
    ".env.example",
    "src/secret_storage.py",
    ".github/workflows/secret-scan.yml",
    "services/memory/service.py",
    "services/hwfit/data/hf_models.json",
    "docker-compose.yml",
    "scripts/searxng_engines/flaresolverr_engines.py",
    "scripts/git-hooks/pre-commit",
    "config/searxng/settings.yml",
]

# Patterns the hook source must contain (keeps hook and this test in sync).
REQUIRED_HOOK_PATTERNS = [
    r"data/\*",
    r"services/data/\*",
    r"research_data/\*",
    r"skills/\*",
    r"memory/\*",
    r"\.env",
    r"secrets\.\*",
    r"\*\.pem",
    r"\*\.key",
    r"id_rsa\*",
    r"\*\.bak",
]


def _guard(path: str) -> bool:
    """Mirror of scripts/git-hooks/pre-commit: True if the commit is blocked."""
    if re.match(r"^(data/|services/data/|research_data/|skills/|memory/)", path):
        return True
    base = path.rsplit("/", 1)[-1]
    if base == ".env" or base.startswith(".env."):
        return not base.endswith(".example")
    return bool(
        re.match(
            r"^(secrets\.|.*\.pem$|.*\.key$|.*\.p12$|.*\.pfx$|id_rsa.*|.*\.bak|.*\.bak\..*)",
            base,
        )
    )


def test_hook_file_exists_and_is_nonempty():
    assert HOOK.exists(), "scripts/git-hooks/pre-commit is missing"
    src = HOOK.read_text()
    assert "COMMIT BLOCKED" in src
    assert "git diff --cached --name-only" in src


def test_hook_patterns_are_intact():
    src = HOOK.read_text()
    missing = [p for p in REQUIRED_HOOK_PATTERNS if not re.search(p, src)]
    assert not missing, f"hook lost rule patterns: {missing}"


def test_guard_blocks_private_paths():
    blocked = [p for p in PRIVATE_PATHS if not _guard(p)]
    assert not blocked, f"guard fails to block: {blocked}"


def test_guard_allows_tracked_files():
    allowed = [p for p in TRUSTED_PATHS if _guard(p)]
    assert not allowed, f"guard would block legitimately tracked files: {allowed}"


def test_guard_covers_every_tracked_file():
    """The guard must not reject any file git currently tracks — otherwise
    the hook would block ordinary commits on a healthy repo."""
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True
    ).stdout.splitlines()
    assert tracked, "git ls-files returned nothing — is this a repo checkout?"
    blocked = [f for f in tracked if _guard(f)]
    assert not blocked, f"hook would block tracked files: {blocked}"


def test_no_private_paths_tracked():
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True
    ).stdout.splitlines()
    leaked = [f for f in tracked if _guard(f)]
    assert not leaked, f"private-looking paths are tracked: {leaked}"
