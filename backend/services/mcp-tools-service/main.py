from __future__ import annotations

import sys
import traceback


def main() -> None:
    print("[mcp-server] starting", file=sys.stderr, flush=True)
    try:
        from tagent.mcp.server import run_mcp_server  # noqa: PLC0415

        print("[mcp-server] imports OK", file=sys.stderr, flush=True)
        run_mcp_server()
    except Exception:
        print("[mcp-server] FATAL:", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
