# Local Research Tools Launcher

This project is a local Flask web launcher for research and study tools. It behaves like a small Windows-style start menu: choose a category, open a group, and launch either a registered script or a local HTML page.

The UI, code, configuration, comments, and documentation are written in English by default.

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m research_tools_launcher.app
```

Open <http://127.0.0.1:5000> in a browser.

## Stopping the Server

If the server is running in your terminal, press `Ctrl+C`.

If the server was started in the background, stop it with:

```bash
pkill -f research_tools_launcher.app
```

Check whether port `5000` is still in use:

```bash
ss -ltnp | grep 5000
```

If the command prints nothing, the local server is closed.

## Project Layout

```text
research_tools_launcher/  Flask app, config loader, runner, templates, and styles
scripts/                  Standalone scripts launched from the web UI
pages/                    Project-local HTML pages opened from the launcher
tests/                    Pytest coverage for config, runner, and routes
tools.toml                Manual registry for categories, groups, and tools
outputs/                  Per-run output directories, ignored by git
```

## Registering a Tool

Tools are organized as `Category -> Group -> Tool`.

Add a category and group to `tools.toml`:

```toml
[[categories]]
id = "physics"
name = "Physics"
order = 30

[[groups]]
id = "dipole-trap"
name = "Dipole Trap"
category = "physics"
order = 10
```

Add a script tool:

```toml
[[tools]]
id = "my-tool"
name = "My Tool"
group = "dipole-trap"
kind = "script"
description = "Short description shown in the launcher."
script = "scripts/my_tool.py"
timeout_seconds = 60
icon = "MT"

[[tools.params]]
name = "input_value"
label = "Input Value"
type = "text"
required = true
cli_flag = "--input-value"
```

Add an HTML page tool:

```toml
[[tools]]
id = "my-page"
name = "My Page"
group = "dipole-trap"
kind = "page"
description = "Interactive HTML calculator."
page = "pages/physics/dipole_trap/my_page.html"
icon = "MP"
```

Scripts and pages must live inside the project directory. The launcher runs only registered scripts and uses `subprocess.run(..., shell=False)`. Page tools open in a new browser tab/window.

## Script Contract

Scripts should remain runnable from the terminal. The launcher passes form values as command-line flags and sets:

```text
PHYSICS_TOOLS_OUTPUT_DIR
```

Use that directory for generated files. Every run receives its own directory under `outputs/`.

Supported parameter types in v1:

- `text`
- `number`
- `file`
- `bool`
- `select`

## Development

Run tests:

```bash
.venv/bin/python -m pytest
```

Run the sample script directly:

```bash
PHYSICS_TOOLS_OUTPUT_DIR=outputs/manual-test .venv/bin/python scripts/example_echo.py --message "Hello" --repeat 2 --mode detailed --write-file
```
