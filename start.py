"""Локальный запуск: окружение, зависимости, безопасный seed и один сервер."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import webbrowser

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
DEFAULT_PORT = 8000
IMPORT_CHECK = "import fastapi, uvicorn, sqlalchemy, pydantic, dotenv, pytest, httpx"


class StartupError(Exception):
    """Понятная ошибка подготовки без изменения существующих данных."""


def run_checked(command: list[str], message: str) -> None:
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode:
        raise StartupError(message)


def prepare_environment() -> Path:
    environment = ROOT / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        if environment.exists():
            raise StartupError(
                "В .venv нет рабочего Python. Переименуйте эту папку в .venv.backup "
                "и повторите запуск. Автоматически удалять её не будем."
            )
        if sys.version_info[:2] != (3, 11):
            raise StartupError("Для создания окружения нужен Python 3.11. На Windows запустите start.bat.")
        print("[1/4] Создаём виртуальное окружение .venv…", flush=True)
        run_checked([sys.executable, "-m", "venv", str(environment)], "Не удалось создать .venv.")
    else:
        print("[1/4] Используем существующее окружение .venv", flush=True)
    result = subprocess.run(
        [str(python), "-c", "import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)"],
        cwd=ROOT, capture_output=True,
    )
    if result.returncode:
        raise StartupError("Окружение .venv должно использовать Python 3.11. См. LOCAL_RUN.md.")
    return python


def prepare_dependencies(python: Path) -> None:
    requirements = ROOT / "requirements.txt"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = ROOT / ".venv" / ".ai-sana-requirements.sha256"
    cached = marker.is_file() and marker.read_text(encoding="utf-8").strip() == digest
    if cached:
        pins = []
        for line in requirements.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if "==" in line:
                name, version = line.split("==", 1)
                pins.append((name.split("[", 1)[0].strip(), version.strip()))
        check_code = IMPORT_CHECK + (
            "; import sys, json, importlib.metadata as metadata; "
            "assert all(metadata.version(name) == version for name, version in json.loads(sys.argv[1]))"
        )
        result = subprocess.run([str(python), "-c", check_code, json.dumps(pins)], cwd=ROOT, capture_output=True)
        if result.returncode == 0:
            print("[2/4] Зависимости уже готовы — повторная загрузка не нужна", flush=True)
            return
    print("[2/4] Проверяем и устанавливаем зависимости (при первом запуске нужен интернет)…", flush=True)
    pip_check = subprocess.run([str(python), "-m", "pip", "--version"], cwd=ROOT, capture_output=True)
    if pip_check.returncode:
        print("В окружении нет pip — восстанавливаем его встроенным ensurepip…", flush=True)
        run_checked([str(python), "-m", "ensurepip", "--upgrade"], "Не удалось восстановить pip в .venv.")
    run_checked(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)],
        "Не удалось установить зависимости. Проверьте интернет и повторите запуск; данные сохранены.",
    )
    run_checked([str(python), "-m", "pip", "check"], "Обнаружен конфликт зависимостей в .venv.")
    run_checked([str(python), "-c", IMPORT_CHECK], "Не все зависимости удалось импортировать.")
    marker.write_text(digest + "\n", encoding="utf-8")


def prepare_config() -> None:
    if (ROOT / ".env").exists():
        return
    template = (ROOT / ".env.example").read_text(encoding="utf-8")
    try:
        # Режим x никогда не перезаписывает настройки пользователя.
        with (ROOT / ".env").open("x", encoding="utf-8") as destination:
            destination.write(template)
    except FileExistsError:
        pass


def choose_port(requested: int | None) -> int:
    candidates = [requested] if requested is not None else range(DEFAULT_PORT, DEFAULT_PORT + 20)
    for port in candidates:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                probe.bind((HOST, port))
            return port
        except OSError:
            continue
    raise StartupError(
        f"Порт {requested} занят или недоступен. Укажите другой через --port."
        if requested is not None else
        "Не удалось найти свободный порт 8000–8019. Укажите другой через --port."
    )


def wait_until_ready(process: subprocess.Popen, url: str, open_browser: bool, stop: threading.Event) -> None:
    opener = build_opener(ProxyHandler({}))  # Локальный запрос не отправляем через системный proxy.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and process.poll() is None and not stop.is_set():
        try:
            with opener.open(url + "/health", timeout=1) as response:
                ready = json.load(response).get("status") == "ok"
            if ready:
                print(f"\nГотово! Сайт: {url}\nAPI: {url}/docs\nДля остановки нажмите Ctrl+C в этом окне.\n", flush=True)
                if open_browser:
                    try:
                        if not webbrowser.open(url):
                            print("Браузер не открылся автоматически. Откройте ссылку выше вручную.", flush=True)
                    except webbrowser.Error:
                        print("Откройте ссылку выше в браузере вручную.", flush=True)
                return
        except (OSError, URLError, ValueError):
            pass
        stop.wait(.25)
    if process.poll() is None and not stop.is_set():
        print("Сервер ещё не ответил. Проверьте сообщения в этом окне и адрес " + url, flush=True)


def serve(python: Path, port: int, open_browser: bool) -> int:
    url = f"http://{HOST}:{port}"
    print(f"[4/4] Запускаем сайт и API одним сервером: {url}", flush=True)
    process = subprocess.Popen(
        [str(python), "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(port)],
        cwd=ROOT,
    )
    stop = threading.Event()
    watcher = threading.Thread(target=wait_until_ready, args=(process, url, open_browser, stop), daemon=True)
    watcher.start()
    try:
        return process.wait()
    except KeyboardInterrupt:
        print("\nОстанавливаем сервер…", flush=True)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()  # Только дочерний сервер, запущенный этим скриптом.
            process.wait(timeout=5)
        return 0
    finally:
        stop.set()
        watcher.join(timeout=2)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Sana: установка и локальный запуск одной командой")
    parser.add_argument("--port", type=int, help="конкретный порт; по умолчанию первый свободный 8000–8019")
    parser.add_argument("--no-browser", action="store_true", help="не открывать браузер автоматически")
    parser.add_argument("--check", action="store_true", help="подготовить проект, запустить тесты и выйти")
    args = parser.parse_args(argv)
    if args.port is not None and not 1 <= args.port <= 65535:
        parser.error("Порт должен быть от 1 до 65535")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    os.chdir(ROOT)
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        python = prepare_environment()
        prepare_dependencies(python)
        prepare_config()
        print("[3/4] Подготавливаем БД (существующие записи не удаляются)…", flush=True)
        run_checked([str(python), "-m", "app.seed.seed"], "Не удалось подготовить БД. Проверьте DATABASE_URL в .env.")
        if args.check:
            print("[4/4] Запускаем тесты…", flush=True)
            return subprocess.run([str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=ROOT).returncode
        port = choose_port(args.port)
        if args.port is None and port != DEFAULT_PORT:
            print(f"Порт {DEFAULT_PORT} занят. Используем {port}; другие процессы не трогаем.", flush=True)
        return serve(python, port, not args.no_browser)
    except (StartupError, OSError) as error:
        print(f"\nНе удалось запустить AI Sana: {error}\nИнструкция: {ROOT / 'LOCAL_RUN.md'}", file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print("\nЗапуск отменён. Существующие данные сохранены.", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
