"""Static contracts for the zero-friction download-and-run path."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_docker_image_contains_ui_sdk_and_cli():
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert "FROM node:" in dockerfile
    assert "npm ci" in dockerfile
    assert "npm run build" in dockerfile
    assert "COPY --from=ui-builder" in dockerfile
    assert "./sdk ./cli ./backend" in dockerfile
    assert "AFR_UI_DIST=/app/ui/dist" in dockerfile
    assert "HEALTHCHECK" in dockerfile


def test_makefile_exposes_supported_build_and_run_targets():
    makefile = (ROOT / "Makefile").read_text()

    assert "build-ui:" in makefile
    assert "run: build-ui serve" in makefile
    assert "start:" in makefile
    assert "package: build-ui" in makefile


def test_ci_validates_ui_docker_and_portable_bundle():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()

    assert "UI build quarantined" not in workflow
    assert "npm run build" in workflow
    assert "Integrated Docker smoke test" in workflow
    assert "agent-flight-recorder-portable.zip" in workflow
    assert "actions/upload-artifact@" in workflow


def test_cross_platform_launchers_are_present():
    assert (ROOT / "start.sh").is_file()
    assert (ROOT / "start.ps1").is_file()
    assert (ROOT / "start.cmd").is_file()
