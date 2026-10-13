"""Persistent JSON-lines bridge for project-local Node providers."""

from __future__ import annotations

import atexit
import json
import select
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, Tuple


class NodeBridgeError(RuntimeError):
    pass


class _NodeSession:
    def __init__(self, mode: str, project_root: str):
        node = shutil.which("node")
        if not node:
            raise NodeBridgeError("Node.js is not available")
        script = Path(__file__).with_name("node_bridge.mjs")
        self.process = subprocess.Popen(
            [node, str(script), mode, project_root],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.lock = threading.Lock()
        self.sequence = 0

    def request(self, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        with self.lock:
            if self.process.poll() is not None:
                detail = (
                    self.process.stderr.read().strip() if self.process.stderr else ""
                )
                raise NodeBridgeError(
                    detail or "Node provider bridge stopped unexpectedly"
                )
            self.sequence += 1
            payload = dict(payload, requestId=self.sequence)
            assert self.process.stdin is not None
            assert self.process.stdout is not None
            self.process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
            self.process.stdin.flush()
            readable, _, _ = select.select([self.process.stdout], [], [], timeout)
            if not readable:
                self.close()
                raise NodeBridgeError(
                    f"Node provider bridge timed out after {timeout:g} seconds"
                )
            line = self.process.stdout.readline()
            if not line:
                detail = (
                    self.process.stderr.read().strip() if self.process.stderr else ""
                )
                raise NodeBridgeError(
                    detail or "Node provider bridge returned no response"
                )
            response = json.loads(line)
            if response.get("error"):
                raise NodeBridgeError(str(response["error"]))
            return response

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()


_SESSIONS: Dict[Tuple[str, str], _NodeSession] = {}
_SESSIONS_LOCK = threading.Lock()


def project_root_for_executable(executable: str) -> str:
    # Keep the project-facing node_modules path. Resolving the executable's
    # symlink lands inside the package itself and loses the configuration root.
    path = Path(executable).absolute()
    if path.parent.name == ".bin" and path.parent.parent.name == "node_modules":
        return str(path.parent.parent.parent)
    return str(path.parent)


def node_request(
    mode: str,
    executable: str,
    payload: Dict[str, Any],
    timeout: float,
) -> Dict[str, Any]:
    key = (mode, project_root_for_executable(executable))
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(key)
        if session is None or session.process.poll() is not None:
            session = _NodeSession(*key)
            _SESSIONS[key] = session
    try:
        return session.request(payload, timeout)
    except Exception:
        with _SESSIONS_LOCK:
            if _SESSIONS.get(key) is session:
                _SESSIONS.pop(key, None)
        session.close()
        raise


def close_node_sessions() -> None:
    with _SESSIONS_LOCK:
        sessions = list(_SESSIONS.values())
        _SESSIONS.clear()
    for session in sessions:
        session.close()


atexit.register(close_node_sessions)
