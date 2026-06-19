"""Static checks that supported install paths consume the Python pin file."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_docker_ci_and_make_consume_python_constraints():
    constraint = "--constraint backend/requirements.txt"

    assert constraint in (ROOT / "Dockerfile").read_text()
    assert constraint in (ROOT / ".github/workflows/ci.yml").read_text()
    assert constraint in (ROOT / "Makefile").read_text()


def test_repair_dependencies_are_exactly_pinned():
    requirements = (ROOT / "backend/requirements.txt").read_text().splitlines()

    assert "fastapi==0.137.1" in requirements
    assert "uvicorn==0.49.0" in requirements
    assert "pytest==9.1.0" in requirements
    assert "httpx==0.28.1" in requirements
    assert "httpx2==2.4.0" in requirements
    assert "anyio==4.13.0" in requirements
