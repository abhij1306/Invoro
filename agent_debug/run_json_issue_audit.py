from __future__ import annotations

if __package__:
    from .json_issue_audit_cli import main
else:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from agent_debug.json_issue_audit_cli import main


__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
