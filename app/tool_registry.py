"""
Tool Registry -- auto-discovers and indexes tools under app/tools/.

Each tool subdirectory must contain an __init__.py exposing a TOOL_MANIFEST dict.
Directories prefixed with '_' or named '__pycache__' are skipped.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from flask import Blueprint


@dataclass
class Tool:
    """Represents a single registered tool and its metadata."""
    name: str
    slug: str
    version: str
    description: str
    tags: List[str]
    author: str
    has_server_logic: bool
    icon: str
    blueprint: Optional[Blueprint] = field(default=None, repr=False)


class ToolRegistry:
    """Walks the tools directory, imports manifests, and builds a searchable index."""

    def __init__(self) -> None:
        self.tools: List[Tool] = []
        self._slug_map: Dict[str, Tool] = {}

    def discover(self, tools_path: Optional[str] = None) -> None:
        """Scan app/tools/ for valid tool directories and register them."""
        if tools_path is None:
            tools_path = os.path.join(os.path.dirname(__file__), "tools")

        for entry in sorted(os.listdir(tools_path)):
            full_path = os.path.join(tools_path, entry)

            if not os.path.isdir(full_path):
                continue
            if entry.startswith("_") or entry == "__pycache__":
                continue
            if not os.path.isfile(os.path.join(full_path, "__init__.py")):
                continue

            try:
                mod = importlib.import_module(f"app.tools.{entry}")
                manifest = getattr(mod, "TOOL_MANIFEST", None)
                if manifest is None:
                    continue

                bp = None
                if manifest.get("has_server_logic"):
                    routes_mod = importlib.import_module(f"app.tools.{entry}.routes")
                    bp = getattr(routes_mod, "blueprint", None)

                tool = Tool(
                    name=manifest["name"],
                    slug=manifest["slug"],
                    version=manifest["version"],
                    description=manifest["description"],
                    tags=manifest.get("tags", []),
                    author=manifest.get("author", "Unknown"),
                    has_server_logic=manifest.get("has_server_logic", False),
                    icon=manifest.get("icon", "wrench"),
                    blueprint=bp,
                )
                self.tools.append(tool)
                self._slug_map[tool.slug] = tool

            except Exception as exc:
                print(f"[ToolRegistry] Failed to load tool '{entry}': {exc}")

    def search(self, query: str) -> List[Tool]:
        """Case-insensitive ranked search across name, tags, and description.

        Ranking: name match > tag match > description match.
        """
        if not query:
            return list(self.tools)

        q = query.lower()
        name_hits: List[Tool] = []
        tag_hits: List[Tool] = []
        desc_hits: List[Tool] = []

        for tool in self.tools:
            if q in tool.name.lower():
                name_hits.append(tool)
            elif any(q in tag.lower() for tag in tool.tags):
                tag_hits.append(tool)
            elif q in tool.description.lower():
                desc_hits.append(tool)

        return name_hits + tag_hits + desc_hits

    def get(self, slug: str) -> Optional[Tool]:
        """Look up a tool by its URL slug."""
        return self._slug_map.get(slug)

    def to_json(self) -> List[dict]:
        """Serialize all tools for embedding in templates or API responses."""
        return [
            {
                "name": t.name,
                "slug": t.slug,
                "version": t.version,
                "description": t.description,
                "tags": t.tags,
                "author": t.author,
                "has_server_logic": t.has_server_logic,
                "icon": t.icon,
            }
            for t in self.tools
        ]
