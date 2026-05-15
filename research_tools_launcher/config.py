"""Configuration loading for the local tools launcher."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from typing import Any


ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
ALLOWED_PARAM_TYPES = {"text", "number", "file", "bool", "select"}
ALLOWED_TOOL_KINDS = {"script", "page"}


class ConfigError(ValueError):
    """Raised when tools.toml is invalid."""


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    order: int = 100


@dataclass(frozen=True)
class Group:
    id: str
    name: str
    category: str
    order: int = 100


@dataclass(frozen=True)
class ToolParam:
    name: str
    label: str
    type: str
    cli_flag: str
    description: str = ""
    default: Any = None
    required: bool = False
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    group: str
    kind: str
    description: str
    script: str = ""
    page: str = ""
    timeout_seconds: int = 60
    params: tuple[ToolParam, ...] = ()
    icon: str = ""


@dataclass(frozen=True)
class LauncherConfig:
    categories: tuple[Category, ...]
    groups: tuple[Group, ...]
    tools: tuple[Tool, ...]
    project_root: Path

    @property
    def categories_by_id(self) -> dict[str, Category]:
        return {category.id: category for category in self.categories}

    @property
    def groups_by_id(self) -> dict[str, Group]:
        return {group.id: group for group in self.groups}

    @property
    def tools_by_id(self) -> dict[str, Tool]:
        return {tool.id: tool for tool in self.tools}

    def groups_for_category(self, category_id: str) -> list[Group]:
        return [group for group in self.groups if group.category == category_id]

    def tools_for_group(self, group_id: str) -> list[Tool]:
        return [tool for tool in self.tools if tool.group == group_id]

    def category_for_tool(self, tool: Tool) -> Category:
        group = self.groups_by_id[tool.group]
        return self.categories_by_id[group.category]


def load_config(config_path: Path, project_root: Path | None = None) -> LauncherConfig:
    """Load and validate the launcher TOML configuration."""

    config_path = config_path.resolve()
    project_root = (project_root or config_path.parent).resolve()

    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML: {exc}") from exc

    categories = _load_categories(raw.get("categories", []))
    category_ids = {category.id for category in categories}
    groups = _load_groups(raw.get("groups", []), category_ids)
    group_ids = {group.id for group in groups}
    tools = _load_tools(raw.get("tools", []), group_ids, project_root)

    return LauncherConfig(categories=categories, groups=groups, tools=tools, project_root=project_root)


def resolve_project_path(project_root: Path, relative_path: str) -> Path:
    """Resolve a project-local path and reject paths outside the project."""

    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise ConfigError(f"Absolute paths are not allowed: {relative_path}")

    resolved = (project_root / candidate).resolve()
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ConfigError(f"Path escapes project root: {relative_path}") from exc
    return resolved


def _load_categories(raw_categories: Any) -> tuple[Category, ...]:
    if not isinstance(raw_categories, list) or not raw_categories:
        raise ConfigError("At least one category is required.")

    categories: list[Category] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_categories, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"Category #{index} must be a table.")
        category_id = _required_string(item, "id", f"category #{index}")
        _validate_id(category_id, f"category #{index}")
        if category_id in seen_ids:
            raise ConfigError(f"Duplicate category id: {category_id}")
        seen_ids.add(category_id)
        categories.append(
            Category(
                id=category_id,
                name=_required_string(item, "name", f"category {category_id}"),
                order=int(item.get("order", 100)),
            )
        )

    return tuple(sorted(categories, key=lambda category: (category.order, category.name.lower())))


def _load_groups(raw_groups: Any, category_ids: set[str]) -> tuple[Group, ...]:
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ConfigError("At least one group is required.")

    groups: list[Group] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_groups, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"Group #{index} must be a table.")
        group_id = _required_string(item, "id", f"group #{index}")
        _validate_id(group_id, f"group #{index}")
        if group_id in seen_ids:
            raise ConfigError(f"Duplicate group id: {group_id}")
        seen_ids.add(group_id)

        category = _required_string(item, "category", f"group {group_id}")
        if category not in category_ids:
            raise ConfigError(f"Group {group_id} references unknown category: {category}")

        groups.append(
            Group(
                id=group_id,
                name=_required_string(item, "name", f"group {group_id}"),
                category=category,
                order=int(item.get("order", 100)),
            )
        )

    return tuple(sorted(groups, key=lambda group: (group.order, group.name.lower())))


def _load_tools(raw_tools: Any, group_ids: set[str], project_root: Path) -> tuple[Tool, ...]:
    if not isinstance(raw_tools, list):
        raise ConfigError("Tools must be provided as TOML tables.")

    tools: list[Tool] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_tools, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"Tool #{index} must be a table.")
        tool_id = _required_string(item, "id", f"tool #{index}")
        _validate_id(tool_id, f"tool #{index}")
        if tool_id in seen_ids:
            raise ConfigError(f"Duplicate tool id: {tool_id}")
        seen_ids.add(tool_id)

        group = _required_string(item, "group", f"tool {tool_id}")
        if group not in group_ids:
            raise ConfigError(f"Tool {tool_id} references unknown group: {group}")

        kind = str(item.get("kind", "script")).strip() or "script"
        if kind not in ALLOWED_TOOL_KINDS:
            raise ConfigError(f"Unsupported tool kind for {tool_id}: {kind}")

        script = ""
        page = ""
        params: tuple[ToolParam, ...] = ()
        if kind == "script":
            script = _required_string(item, "script", f"tool {tool_id}")
            script_path = resolve_project_path(project_root, script)
            if not script_path.exists():
                raise ConfigError(f"Script for tool {tool_id} does not exist: {script}")
            if not script_path.is_file():
                raise ConfigError(f"Script for tool {tool_id} is not a file: {script}")
            params = _load_params(item.get("params", []), tool_id)
        else:
            page = _required_string(item, "page", f"tool {tool_id}")
            page_path = resolve_project_path(project_root, page)
            if not page_path.exists():
                raise ConfigError(f"Page for tool {tool_id} does not exist: {page}")
            if not page_path.is_file():
                raise ConfigError(f"Page for tool {tool_id} is not a file: {page}")
            if page_path.suffix.lower() not in {".html", ".htm"}:
                raise ConfigError(f"Page for tool {tool_id} must be an HTML file: {page}")
            if item.get("params"):
                raise ConfigError(f"Page tool {tool_id} must not define params.")

        tools.append(
            Tool(
                id=tool_id,
                name=_required_string(item, "name", f"tool {tool_id}"),
                group=group,
                kind=kind,
                description=str(item.get("description", "")),
                script=script,
                page=page,
                timeout_seconds=int(item.get("timeout_seconds", 60)),
                params=params,
                icon=str(item.get("icon", "")),
            )
        )

    return tuple(sorted(tools, key=lambda tool: tool.name.lower()))


def _load_params(raw_params: Any, tool_id: str) -> tuple[ToolParam, ...]:
    if not isinstance(raw_params, list):
        raise ConfigError(f"Params for tool {tool_id} must be a list.")

    params: list[ToolParam] = []
    seen_names: set[str] = set()
    for index, item in enumerate(raw_params, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"Param #{index} for tool {tool_id} must be a table.")

        name = _required_string(item, "name", f"param #{index} for tool {tool_id}")
        _validate_id(name, f"param #{index} for tool {tool_id}")
        if name in seen_names:
            raise ConfigError(f"Duplicate param name for tool {tool_id}: {name}")
        seen_names.add(name)

        param_type = _required_string(item, "type", f"param {name} for tool {tool_id}")
        if param_type not in ALLOWED_PARAM_TYPES:
            raise ConfigError(f"Unsupported param type for {tool_id}.{name}: {param_type}")

        choices = tuple(str(choice) for choice in item.get("choices", ()))
        if param_type == "select" and not choices:
            raise ConfigError(f"Select param {tool_id}.{name} must define choices.")

        cli_flag = str(item.get("cli_flag", f"--{name.replace('_', '-')}"))
        if not cli_flag.startswith("--"):
            raise ConfigError(f"CLI flag for {tool_id}.{name} must start with '--'.")

        params.append(
            ToolParam(
                name=name,
                label=str(item.get("label", name.replace("_", " ").title())),
                type=param_type,
                cli_flag=cli_flag,
                description=str(item.get("description", "")),
                default=item.get("default"),
                required=bool(item.get("required", False)),
                choices=choices,
            )
        )
    return tuple(params)


def _required_string(item: dict[str, Any], key: str, context: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"Missing or invalid {key} in {context}.")
    return value.strip()


def _validate_id(value: str, context: str) -> None:
    if not ID_PATTERN.match(value):
        raise ConfigError(f"Invalid id in {context}: {value}")
