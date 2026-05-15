from pathlib import Path

import pytest

from research_tools_launcher.config import Tool, ToolParam
from research_tools_launcher.runner import ParameterError, build_cli_args, run_tool


def make_tool(script: str = "scripts/tool.py") -> Tool:
    return Tool(
        id="sample",
        name="Sample",
        group="examples-basic",
        kind="script",
        description="Sample tool",
        script=script,
        timeout_seconds=5,
        params=(
            ToolParam(
                name="message",
                label="Message",
                type="text",
                cli_flag="--message",
                required=True,
            ),
            ToolParam(
                name="repeat",
                label="Repeat",
                type="number",
                cli_flag="--repeat",
                default=1,
            ),
            ToolParam(
                name="verbose",
                label="Verbose",
                type="bool",
                cli_flag="--verbose",
            ),
            ToolParam(
                name="mode",
                label="Mode",
                type="select",
                cli_flag="--mode",
                choices=("summary", "detailed"),
                default="summary",
            ),
        ),
    )


def test_build_cli_args_converts_supported_params() -> None:
    args = build_cli_args(
        make_tool(),
        {"message": "hello", "repeat": "2", "verbose": "on", "mode": "detailed"},
    )

    assert args == [
        "--message",
        "hello",
        "--repeat",
        "2",
        "--verbose",
        "--mode",
        "detailed",
    ]


def test_build_cli_args_rejects_invalid_number() -> None:
    with pytest.raises(ParameterError, match="must be a number"):
        build_cli_args(make_tool(), {"message": "hello", "repeat": "nan-value"})


def test_run_tool_captures_stdout_and_output_file(tmp_path: Path) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    script = scripts_dir / "tool.py"
    script.write_text(
        """
import argparse
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--message", required=True)
args = parser.parse_args()
out = Path(os.environ["PHYSICS_TOOLS_OUTPUT_DIR"]) / "result.txt"
out.write_text(args.message, encoding="utf-8")
print(args.message)
""",
        encoding="utf-8",
    )
    tool = Tool(
        id="sample",
        name="Sample",
        group="examples-basic",
        kind="script",
        description="Sample tool",
        script="scripts/tool.py",
        timeout_seconds=5,
        params=(
            ToolParam(
                name="message",
                label="Message",
                type="text",
                cli_flag="--message",
                required=True,
            ),
        ),
    )

    result = run_tool(tool, tmp_path, {"message": "hello"})

    assert result.ok
    assert "hello" in result.stdout
    assert any(path.name == "result.txt" for path in result.output_files)
