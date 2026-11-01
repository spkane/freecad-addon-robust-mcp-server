"""Exercise inventory pull request automation with local Git repositories."""

import os
import subprocess  # nosec B404 - fixed local test commands
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TAG = "robust-mcp-server-v1.0.0"


def run(
    *args: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a local command and return captured output."""
    return subprocess.run(  # nosec B603  # noqa: S603 - test-controlled commands
        list(args), cwd=cwd, env=env, text=True, capture_output=True, check=True
    )


@pytest.fixture
def action_environment(tmp_path: Path) -> tuple[Path, dict[str, str], str]:
    """Prepare a local bare remote and stub only GitHub and inventory generation."""
    remote = tmp_path / "remote.git"
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    run("git", "init", "--bare", str(remote), cwd=tmp_path)
    run("git", "init", "-b", "main", cwd=checkout)
    run("git", "config", "user.name", "Test", cwd=checkout)
    run("git", "config", "user.email", "test@example.invalid", cwd=checkout)
    (checkout / "cam-compatibility.toml").write_text("initial\n")
    run("git", "add", "cam-compatibility.toml", cwd=checkout)
    run("git", "commit", "-m", "Initial inventory", cwd=checkout)
    run("git", "remote", "add", "origin", str(remote), cwd=checkout)
    run("git", "push", "origin", "main", cwd=checkout)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").write_text(
        '#!/bin/sh\nprintf "%s\\n" "$INVENTORY_CONTENT" > cam-compatibility.toml\n'
    )
    (bin_dir / "gh").write_text(
        "#!/bin/sh\n"
        'if [ "$1 $2" = "pr list" ]; then printf "%s" "$EXISTING_PR"; exit 0; fi\n'
        'if [ "$1 $2" = "pr create" ]; then printf "create\\n" >> "$GH_LOG"; '
        '[ "${FAIL_PR:-0}" = 0 ]; exit; fi\n'
        "exit 1\n"
    )
    for executable in bin_dir.iterdir():
        executable.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GITHUB_REPOSITORY": "owner/repository",
        "RELEASE_TAG": TAG,
        "INVENTORY_CONTENT": "release-one",
        "EXISTING_PR": "",
        "GH_LOG": str(tmp_path / "gh.log"),
    }
    action = yaml.safe_load(
        (ROOT / ".github/actions/update-cam-inventory/action.yml").read_text()
    )
    return checkout, env, action["runs"]["steps"][1]["run"]


def test_failed_pr_creation_can_retry_existing_branch(
    action_environment: tuple[Path, dict[str, str], str],
) -> None:
    """A failed PR creation leaves a branch that a later run can reuse."""
    checkout, env, script = action_environment
    failed = subprocess.run(  # nosec B603  # noqa: S603
        ["/bin/bash", "-c", script],
        cwd=checkout,
        env={**env, "FAIL_PR": "1"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert failed.returncode != 0
    assert "Could not create inventory PR" in failed.stderr
    run("git", "switch", "main", cwd=checkout)
    run("bash", "-c", script, cwd=checkout, env=env)
    assert Path(env["GH_LOG"]).read_text().splitlines() == ["create", "create"]


def test_existing_pr_with_stale_inventory_is_rejected(
    action_environment: tuple[Path, dict[str, str], str],
) -> None:
    """An open PR must not conceal an out-of-date generated inventory."""
    checkout, env, script = action_environment
    run("bash", "-c", script, cwd=checkout, env=env)
    run("git", "switch", "main", cwd=checkout)
    result = subprocess.run(  # nosec B603  # noqa: S603
        ["/bin/bash", "-c", script],
        cwd=checkout,
        env={
            **env,
            "EXISTING_PR": "https://example.invalid/pr/1",
            "INVENTORY_CONTENT": "release-two",
        },
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "differs from the proposed update" in result.stderr


def test_existing_matching_pr_is_reused(
    action_environment: tuple[Path, dict[str, str], str],
) -> None:
    """A matching open PR is reused without creating another one."""
    checkout, env, script = action_environment
    run("bash", "-c", script, cwd=checkout, env=env)
    run("git", "switch", "main", cwd=checkout)
    result = run(
        "bash",
        "-c",
        script,
        cwd=checkout,
        env={**env, "EXISTING_PR": "https://example.invalid/pr/1"},
    )
    assert "already exists" in result.stdout
    assert Path(env["GH_LOG"]).read_text().splitlines() == ["create"]
