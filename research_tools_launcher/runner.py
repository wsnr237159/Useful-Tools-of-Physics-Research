"""Script execution helpers for registered launcher tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
import sys
import time
from typing import Any, Mapping
from uuid import uuid4

from .config import Tool, ToolParam, resolve_project_path


class ParameterError(ValueError):
    """Raised when submitted form data is invalid."""


@dataclass(frozen=True)
class RunResult:
    tool: Tool
    command: tuple[str, ...]
    output_dir: Path
    output_files: tuple[Path, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def run_tool(
    tool: Tool,
    project_root: Path,
    form_data: Mapping[str, Any],
    uploaded_files: Mapping[str, Any] | None = None,
    python_executable: str | None = None,
) -> RunResult:
    """Run a registered tool synchronously and capture the result."""

    project_root = project_root.resolve()
    script_path = resolve_project_path(project_root, tool.script)
    output_dir = project_root / "outputs" / _new_run_id(tool.id)
    input_dir = output_dir / "inputs"
    output_dir.mkdir(parents=True, exist_ok=False)

    args = build_cli_args(tool, form_data, uploaded_files or {}, input_dir)
    command = tuple([python_executable or sys.executable, str(script_path), *args])
    env = os.environ.copy()
    env["PHYSICS_TOOLS_OUTPUT_DIR"] = str(output_dir)

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=tool.timeout_seconds,
            shell=False,
            check=False,
        )
        duration = time.monotonic() - started
        return RunResult(
            tool=tool,
            command=command,
            output_dir=output_dir,
            output_files=tuple(_discover_output_files(output_dir)),
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        stdout = _decode_timeout_output(exc.stdout)
        stderr = _decode_timeout_output(exc.stderr)
        if stderr:
            stderr = f"{stderr}\nTool timed out after {tool.timeout_seconds} seconds."
        else:
            stderr = f"Tool timed out after {tool.timeout_seconds} seconds."
        return RunResult(
            tool=tool,
            command=command,
            output_dir=output_dir,
            output_files=tuple(_discover_output_files(output_dir)),
            exit_code=None,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            timed_out=True,
        )


def build_cli_args(
    tool: Tool,
    form_data: Mapping[str, Any],
    uploaded_files: Mapping[str, Any] | None = None,
    input_dir: Path | None = None,
) -> list[str]:
    """Convert submitted form values into CLI arguments for a tool."""

    args: list[str] = []
    files = uploaded_files or {}
    for param in tool.params:
        if param.type == "bool":
            if _coerce_bool(_submitted_value(form_data, param)):
                args.append(param.cli_flag)
            continue

        value = _submitted_value(form_data, param)
        if param.type == "file":
            value = _resolve_file_value(param, value, files, input_dir)
        elif value in (None, ""):
            value = param.default

        if value in (None, ""):
            if param.required:
                raise ParameterError(f"Missing required parameter: {param.label}")
            continue

        value_text = _validate_value(param, value)
        args.extend([param.cli_flag, value_text])

    return args


def _submitted_value(form_data: Mapping[str, Any], param: ToolParam) -> Any:
    if param.name in form_data:
        return form_data[param.name]
    return None


def _resolve_file_value(
    param: ToolParam,
    value: Any,
    uploaded_files: Mapping[str, Any],
    input_dir: Path | None,
) -> Any:
    uploaded = uploaded_files.get(param.name)
    if uploaded is not None and getattr(uploaded, "filename", ""):
        if input_dir is None:
            raise ParameterError("An input directory is required for file uploads.")
        input_dir.mkdir(parents=True, exist_ok=True)
        target = input_dir / _safe_filename(str(uploaded.filename))
        uploaded.save(target)
        return str(target)

    if value in (None, ""):
        return param.default
    return value


def _validate_value(param: ToolParam, value: Any) -> str:
    value_text = str(value)
    if param.type == "number":
        try:
            float(value_text)
        except ValueError as exc:
            raise ParameterError(f"{param.label} must be a number.") from exc
    elif param.type == "select":
        if value_text not in param.choices:
            raise ParameterError(f"{param.label} must be one of: {', '.join(param.choices)}")
    return value_text


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in {"1", "true", "yes", "on"}


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    return name or "upload.dat"


def _new_run_id(tool_id: str) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{tool_id}-{uuid4().hex[:8]}"


def _discover_output_files(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    files = [path for path in output_dir.rglob("*") if path.is_file()]
    return sorted(files, key=lambda path: str(path.relative_to(output_dir)))


def _decode_timeout_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
