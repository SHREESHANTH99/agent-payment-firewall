"""Tests for brand constants and rejection of legacy name 'Gatekeeper' in user-visible docs and app."""
import os
import re
from pathlib import Path
from app.core.config import settings

def test_backend_brand_settings():
    """Verify backend settings contain Spendlatch brand constants."""
    assert settings.PRODUCT_NAME == "Spendlatch"
    assert settings.PRODUCT_TAGLINE == "Payment firewall for AI agents"
    assert "github.com" in settings.PRODUCT_REPO_URL


def test_no_legacy_brand_in_visible_docs_and_app():
    """Scan docs, README, and app files to ensure 'Gatekeeper' does not appear."""
    repo_root = Path(__file__).resolve().parent.parent.parent

    # Allowlist: archive results, this test file itself, CHANGELOG if present
    allowlisted_rel_paths = {
        "backend/tests/test_brand.py",
        "CHANGELOG.md",
    }

    violations = []
    pattern = re.compile(r"gatekeeper", re.IGNORECASE)

    target_dirs = ["docs", "backend/app"]
    target_files = ["README.md"]

    for t_file in target_files:
        p = repo_root / t_file
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="ignore")
            if pattern.search(text):
                violations.append(str(p.relative_to(repo_root)))

    for t_dir in target_dirs:
        d = repo_root / t_dir
        if d.exists():
            for p in d.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(repo_root).as_posix()
                    if rel in allowlisted_rel_paths or "archive" in rel:
                        continue
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    if pattern.search(text):
                        violations.append(rel)

    assert violations == [], f"Found legacy brand 'Gatekeeper' in user-visible files: {violations}"
