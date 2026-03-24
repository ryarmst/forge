# Tool Template

This is the canonical template for creating a new Forge tool. Copy this entire
directory into `app/tools/<your_tool_slug>/` and follow the steps below.

## Setup Checklist

1. **Rename the directory** to your tool's slug (lowercase, underscores).
2. **Edit `__init__.py`**: fill in every field in `TOOL_MANIFEST`.
   - `slug` must match the directory name exactly.
   - `icon` should be a valid [Lucide icon name](https://lucide.dev/icons/).
3. **Edit `tool.html`**: build your tool's UI inside the `tool_content` block.
   - For **client-side-only** tools: put all logic in `<script>` tags.
   - For **server-backed** tools: keep `routes.py` and set `has_server_logic: True`.
4. **Edit `routes.py`** (only if `has_server_logic` is True):
   - Rename the blueprint to match your slug.
   - Add your API endpoints.
5. **Delete this README** or replace it with tool-specific documentation.

## Inputs / Outputs

Document what your tool accepts and produces.

## Security Considerations

Note any security implications (user input handling, subprocess calls, etc.).
