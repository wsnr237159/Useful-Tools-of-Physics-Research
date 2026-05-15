"""Flask application for the local research tools launcher."""

from __future__ import annotations

from pathlib import Path
import os

from flask import Flask, abort, redirect, render_template, request, send_file, url_for

from .config import ConfigError, LauncherConfig, load_config, resolve_project_path
from .runner import ParameterError, run_tool


DEFAULT_CONFIG_NAME = "tools.toml"


def create_app(project_root: str | Path | None = None, config_path: str | Path | None = None) -> Flask:
    """Create the Flask application."""

    root = Path(project_root or Path.cwd()).resolve()
    config_file = Path(config_path or root / DEFAULT_CONFIG_NAME).resolve()

    app = Flask(__name__)
    app.config["PROJECT_ROOT"] = root
    app.config["TOOLS_CONFIG_PATH"] = config_file

    @app.context_processor
    def inject_app_name() -> dict[str, str]:
        return {"app_name": "Research Tools Launcher"}

    @app.get("/")
    def index():
        config = _load_launcher_config()
        query = request.args.get("q", "").strip().lower()
        selected_category_id = request.args.get("category", "")

        if query:
            tools = [
                tool
                for tool in config.tools
                if query in tool.name.lower()
                or query in tool.description.lower()
                or query in tool.id.lower()
            ]
            selected_category_id = ""
            sections = _build_group_sections(config, tools=tools)
        else:
            if selected_category_id not in config.categories_by_id:
                selected_category_id = config.categories[0].id if config.categories else ""
            sections = _build_group_sections(config, category_id=selected_category_id)

        return render_template(
            "index.html",
            config=config,
            selected_category_id=selected_category_id,
            sections=sections,
            query=request.args.get("q", ""),
        )

    @app.get("/tools/<tool_id>")
    def tool_detail(tool_id: str):
        config = _load_launcher_config()
        tool = config.tools_by_id.get(tool_id)
        if tool is None:
            abort(404)
        if tool.kind == "page":
            return redirect(url_for("page_tool", tool_id=tool.id))
        category = config.category_for_tool(tool)
        group = config.groups_by_id[tool.group]
        return render_template("tool.html", tool=tool, category=category, group=group, errors=[])

    @app.post("/tools/<tool_id>/run")
    def run_tool_route(tool_id: str):
        config = _load_launcher_config()
        tool = config.tools_by_id.get(tool_id)
        if tool is None:
            abort(404)
        if tool.kind != "script":
            abort(404)
        category = config.category_for_tool(tool)
        group = config.groups_by_id[tool.group]

        try:
            result = run_tool(
                tool=tool,
                project_root=app.config["PROJECT_ROOT"],
                form_data=request.form,
                uploaded_files=request.files,
            )
        except ParameterError as exc:
            return render_template(
                "tool.html",
                tool=tool,
                category=category,
                group=group,
                errors=[str(exc)],
            ), 400

        return render_template("result.html", tool=tool, category=category, group=group, result=result)

    @app.get("/pages/<tool_id>")
    def page_tool(tool_id: str):
        config = _load_launcher_config()
        tool = config.tools_by_id.get(tool_id)
        if tool is None or tool.kind != "page":
            abort(404)
        page_path = resolve_project_path(app.config["PROJECT_ROOT"], tool.page)
        return send_file(page_path, mimetype="text/html")

    @app.errorhandler(ConfigError)
    def config_error(error: ConfigError):
        return render_template("error.html", title="Configuration Error", message=str(error)), 500

    return app


def _build_group_sections(
    config: LauncherConfig,
    category_id: str | None = None,
    tools: list | None = None,
) -> list[dict]:
    selected_tools = tools if tools is not None else list(config.tools)
    selected_tool_ids = {tool.id for tool in selected_tools}
    sections = []
    for group in config.groups:
        if category_id is not None and group.category != category_id:
            continue
        group_tools = [
            tool
            for tool in config.tools_for_group(group.id)
            if tool.id in selected_tool_ids
        ]
        if not group_tools:
            continue
        sections.append(
            {
                "category": config.categories_by_id[group.category],
                "group": group,
                "tools": group_tools,
            }
        )
    return sections


def _load_launcher_config() -> LauncherConfig:
    from flask import current_app

    return load_config(
        config_path=Path(current_app.config["TOOLS_CONFIG_PATH"]),
        project_root=Path(current_app.config["PROJECT_ROOT"]),
    )


def main() -> None:
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes", "on"}
    app = create_app()
    app.run(host="127.0.0.1", port=port, debug=debug)


if __name__ == "__main__":
    main()
