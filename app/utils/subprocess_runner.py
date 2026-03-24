"""
Utility for running external tools as subprocesses with streaming output.

Used by server-backed tools that shell out to installed binaries (e.g. nmap, waymore).
Output is yielded line-by-line for use with Flask's streaming responses / SSE.

Usage in a tool's routes.py:
    from app.utils.subprocess_runner import run_tool, stream_response

    @blueprint.route("/api/run", methods=["POST"])
    def run():
        cmd = ["waymore", "-i", request.json["domain"]]
        return stream_response(cmd, timeout=120)
"""

import subprocess
from flask import Response


def run_tool(cmd: list[str], timeout: int = 300):
    """Run an external tool, yielding stdout lines as they arrive.

    Args:
        cmd:     Command and arguments as a list (never pass through a shell).
        timeout: Maximum wall-clock seconds before the process is killed.

    Yields:
        Each line of combined stdout/stderr output.
    """
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for line in iter(process.stdout.readline, ""):
            yield line
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        yield "[TIMEOUT] Process killed after {}s\n".format(timeout)
    finally:
        if process.poll() is None:
            process.terminate()


def stream_response(cmd: list[str], timeout: int = 300) -> Response:
    """Wrap run_tool output as a text/event-stream SSE response."""

    def generate():
        for line in run_tool(cmd, timeout=timeout):
            yield f"data: {line.rstrip()}\n\n"
        yield "event: done\ndata: \n\n"

    return Response(generate(), mimetype="text/event-stream")
