"""Проверки безопасного однокомандного запуска без изменения реальных настроек."""

import socket
from pathlib import Path
from unittest.mock import Mock

import pytest

import start


def test_config_created_once_without_overwriting(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ROOT", tmp_path)
    (tmp_path / ".env.example").write_text("DATABASE_URL=sqlite:///./example.db\n", encoding="utf-8")
    start.prepare_config()
    assert (tmp_path / ".env").read_text(encoding="utf-8").endswith("example.db\n")
    (tmp_path / ".env").write_text("DATABASE_URL=sqlite:///./my-data.db\n", encoding="utf-8")
    start.prepare_config()
    assert "my-data.db" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_busy_port_is_skipped_but_explicit_port_is_not(monkeypatch):
    with socket.socket() as occupied:
        occupied.bind((start.HOST, 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        monkeypatch.setattr(start, "DEFAULT_PORT", port)
        assert start.choose_port(None) > port
        with pytest.raises(start.StartupError, match="занят"):
            start.choose_port(port)


def test_dependency_cache_and_requirements_change(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ROOT", tmp_path)
    (tmp_path / ".venv").mkdir()
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("fastapi==0.115.12\n", encoding="utf-8")
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(start.subprocess, "run", run)
    start.prepare_dependencies(Path("python"))
    assert any("install" in call.args[0] for call in run.call_args_list)
    run.reset_mock()
    start.prepare_dependencies(Path("python"))
    assert not any("install" in call.args[0] for call in run.call_args_list)
    requirements.write_text("fastapi==0.115.12\nhttpx==0.28.1\n", encoding="utf-8")
    start.prepare_dependencies(Path("python"))
    assert any("install" in call.args[0] for call in run.call_args_list)


def test_broken_environment_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ROOT", tmp_path)
    environment = tmp_path / ".venv"
    environment.mkdir()
    marker = environment / "user-file.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(start.StartupError, match="удалять"):
        start.prepare_environment()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_missing_pip_is_restored_automatically(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ROOT", tmp_path)
    (tmp_path / ".venv").mkdir()
    (tmp_path / "requirements.txt").write_text("fastapi==0.115.12\n", encoding="utf-8")
    def result(command, **kwargs):
        return Mock(returncode=1 if "pip" in command and "--version" in command else 0)
    run = Mock(side_effect=result)
    monkeypatch.setattr(start.subprocess, "run", run)
    start.prepare_dependencies(Path("python"))
    assert any("ensurepip" in call.args[0] for call in run.call_args_list)


@pytest.mark.parametrize("port", ["0", "-1", "65536"])
def test_invalid_port_rejected(port):
    with pytest.raises(SystemExit) as error:
        start.parse_args(["--port", port])
    assert error.value.code == 2
