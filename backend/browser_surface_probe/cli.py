from __future__ import annotations

from ._core_shared import *  # noqa: F403
from .probe_runner import build_report
from .runtime_source import (
    _json_dump,
    _report_root,
    _resolve_runtime_source,
    _utc_stamp,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, default=None)
    parser.add_argument("--proxy", action="append", default=[])
    parser.add_argument("--proxy-profile-json", default=None)
    parser.add_argument("--target-url", action="append", default=[])
    parser.add_argument("--geo-country", default=None)
    parser.add_argument("--language-hint", default=None)
    parser.add_argument("--currency-hint", default=None)
    parser.add_argument(
        "--browser-engine",
        choices=("chromium", "real_chrome", "patchright"),
        default="chromium",
    )
    parser.add_argument("--report-dir", default=None)
    return parser


async def async_main(args: argparse.Namespace) -> Path:
    runtime_source = await _resolve_runtime_source(args)
    bundle_dir = _report_root(args.report_dir) / _utc_stamp()
    await build_report(
        runtime_source=runtime_source,
        report_dir=bundle_dir,
        target_urls=list(args.target_url or []),
    )
    return bundle_dir


async def _run(args: argparse.Namespace) -> int:
    bundle_dir: Path | None = None
    try:
        bundle_dir = await async_main(args)
    finally:
        await shutdown_browser_runtime()
    if bundle_dir is None:
        raise RuntimeError("Fingerprint report bundle was not created")
    print(_json_dump({"report_dir": str(bundle_dir)}))
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_run(args))


__all__ = tuple(name for name in globals() if not name.startswith("__"))
