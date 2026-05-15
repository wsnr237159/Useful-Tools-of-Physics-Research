from pathlib import Path

import pytest

from research_tools_launcher.config import ConfigError, load_config, resolve_project_path


def write_project(tmp_path: Path, config_text: str) -> Path:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "tool.py").write_text("print('ok')\n", encoding="utf-8")
    config_path = tmp_path / "tools.toml"
    config_path.write_text(config_text, encoding="utf-8")
    return config_path


def test_load_config_orders_categories_and_groups_tools(tmp_path: Path) -> None:
    config_path = write_project(
        tmp_path,
        """
[[categories]]
id = "physics"
name = "Physics"
order = 20

[[categories]]
id = "examples"
name = "Examples"
order = 10

[[groups]]
id = "general"
name = "General"
category = "examples"
order = 20

[[groups]]
id = "physics-tools"
name = "Physics Tools"
category = "physics"
order = 10

[[tools]]
id = "sample"
name = "Sample"
group = "general"
kind = "script"
description = "Sample tool"
script = "scripts/tool.py"
timeout_seconds = 5

[[tools.params]]
name = "message"
label = "Message"
type = "text"
required = true
cli_flag = "--message"
""",
    )

    config = load_config(config_path, tmp_path)

    assert [category.id for category in config.categories] == ["examples", "physics"]
    assert [group.id for group in config.groups_for_category("examples")] == ["general"]
    assert config.tools_for_group("general")[0].id == "sample"
    assert config.tools_by_id["sample"].params[0].cli_flag == "--message"


def test_load_config_rejects_unknown_group(tmp_path: Path) -> None:
    config_path = write_project(
        tmp_path,
        """
[[categories]]
id = "examples"
name = "Examples"

[[groups]]
id = "general"
name = "General"
category = "examples"

[[tools]]
id = "sample"
name = "Sample"
group = "missing"
kind = "script"
description = "Sample tool"
script = "scripts/tool.py"
""",
    )

    with pytest.raises(ConfigError, match="unknown group"):
        load_config(config_path, tmp_path)


def test_load_config_supports_page_tools(tmp_path: Path) -> None:
    page_dir = tmp_path / "pages"
    page_dir.mkdir()
    (page_dir / "tool.html").write_text("<h1>Page Tool</h1>\n", encoding="utf-8")
    config_path = write_project(
        tmp_path,
        """
[[categories]]
id = "physics"
name = "Physics"

[[groups]]
id = "dipole-trap"
name = "Dipole Trap"
category = "physics"

[[tools]]
id = "page-tool"
name = "Page Tool"
group = "dipole-trap"
kind = "page"
description = "HTML page"
page = "pages/tool.html"
""",
    )

    config = load_config(config_path, tmp_path)

    assert config.tools_by_id["page-tool"].kind == "page"
    assert config.tools_by_id["page-tool"].page == "pages/tool.html"


def test_resolve_project_path_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="escapes project root"):
        resolve_project_path(tmp_path, "../outside.py")
