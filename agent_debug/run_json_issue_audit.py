from __future__ import annotations

if __package__:
    from .json_issue_audit_cli import *  # noqa: F403
    from .json_issue_audit_core import *  # noqa: F403
    from .json_issue_audit_triage import *  # noqa: F403
else:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from agent_debug.json_issue_audit_cli import *  # noqa: F403
    from agent_debug.json_issue_audit_core import *  # noqa: F403
    from agent_debug.json_issue_audit_triage import *  # noqa: F403


__all__ = tuple(
    name for name in globals() if not name.startswith("__")
)

if __name__ == "__main__":
    raise SystemExit(main())
