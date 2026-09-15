"""Guards scripts/authorize.py against scope drift.

authorize.py deliberately hard-codes SCOPES so it can run standalone before
the package is installed. That duplication is safe only while the two lists
agree: a refresh token minted with the wrong scopes fails at runtime, days
later, with a 403 that points nowhere near the cause.
"""
import ast
from pathlib import Path

from adkar_bot import config

AUTHORIZE = Path(__file__).resolve().parents[1] / "scripts" / "authorize.py"


def _scopes_literal_from(path: Path) -> list[str]:
    """Read the SCOPES assignment without importing the module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SCOPES":
                    return ast.literal_eval(node.value)
    raise AssertionError(f"no SCOPES assignment found in {path}")


def test_authorize_scopes_match_config():
    assert _scopes_literal_from(AUTHORIZE) == list(config.SCOPES)


def test_authorize_omits_force_ssl():
    """Commenting is gone, so force-ssl (comment/delete/caption access) must
    not be requested — a leaked upload-only token cannot delete videos."""
    scopes = _scopes_literal_from(AUTHORIZE)
    assert "https://www.googleapis.com/auth/youtube.force-ssl" not in scopes
    assert scopes == [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]
