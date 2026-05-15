from pathlib import Path

from research_tools_launcher.app import create_app


def write_project(tmp_path: Path, script_body: str, timeout_seconds: int = 5) -> Path:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "tool.py").write_text(script_body, encoding="utf-8")
    page_dir = tmp_path / "pages"
    page_dir.mkdir()
    (page_dir / "tool.html").write_text("<h1>Page Tool</h1>\n", encoding="utf-8")
    config_path = tmp_path / "tools.toml"
    config_path.write_text(
        f"""
[[categories]]
id = "examples"
name = "Examples"
order = 10

[[groups]]
id = "basic"
name = "Basic"
category = "examples"
order = 10

[[tools]]
id = "sample"
name = "Sample"
group = "basic"
kind = "script"
description = "Sample tool"
script = "scripts/tool.py"
timeout_seconds = {timeout_seconds}

[[tools.params]]
name = "message"
label = "Message"
type = "text"
required = true
cli_flag = "--message"

[[tools]]
id = "page-tool"
name = "Page Tool"
group = "basic"
kind = "page"
description = "HTML page tool"
page = "pages/tool.html"
""",
        encoding="utf-8",
    )
    return config_path


def test_home_and_tool_pages_render(tmp_path: Path) -> None:
    config_path = write_project(tmp_path, "print('ok')\n")
    app = create_app(project_root=tmp_path, config_path=config_path)

    with app.test_client() as client:
        home = client.get("/")
        detail = client.get("/tools/sample")

    assert home.status_code == 200
    assert b"Sample" in home.data
    assert b"Basic" in home.data
    assert detail.status_code == 200
    assert b"Run Tool" in detail.data


def test_successful_run_renders_result(tmp_path: Path) -> None:
    config_path = write_project(
        tmp_path,
        """
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--message", required=True)
args = parser.parse_args()
print(args.message)
""",
    )
    app = create_app(project_root=tmp_path, config_path=config_path)

    with app.test_client() as client:
        response = client.post("/tools/sample/run", data={"message": "hello"})

    assert response.status_code == 200
    assert b"Run Complete" in response.data
    assert b"hello" in response.data


def test_run_validation_error_returns_tool_page(tmp_path: Path) -> None:
    config_path = write_project(tmp_path, "print('ok')\n")
    app = create_app(project_root=tmp_path, config_path=config_path)

    with app.test_client() as client:
        response = client.post("/tools/sample/run", data={"message": ""})

    assert response.status_code == 400
    assert b"Missing required parameter" in response.data


def test_page_tool_link_and_route(tmp_path: Path) -> None:
    config_path = write_project(tmp_path, "print('ok')\n")
    app = create_app(project_root=tmp_path, config_path=config_path)

    with app.test_client() as client:
        home = client.get("/")
        page = client.get("/pages/page-tool")

    assert home.status_code == 200
    assert b'target="_blank"' in home.data
    assert page.status_code == 200
    assert b"Page Tool" in page.data


def test_page_route_rejects_script_tool(tmp_path: Path) -> None:
    config_path = write_project(tmp_path, "print('ok')\n")
    app = create_app(project_root=tmp_path, config_path=config_path)

    with app.test_client() as client:
        response = client.get("/pages/sample")

    assert response.status_code == 404
