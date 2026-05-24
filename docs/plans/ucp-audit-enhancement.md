Work orders are sequenced by phase. Each slice is self-contained and independently verifiable. Follow the deletion-first rule: remove or rewrite before adding. Net line count must be ≤ 0 unless an exception is stated.

---

### Phase 1 — Fix "Same Score" Bugs

---

#### Slice 1.1 — Fix `_profile_required()` to scan `error.data`

**Scope:** `app/services/ucp_audit/protocol_checks.py`
**Findings addressed:** B1
**Severity:** 🔴

**Problem:**
`_profile_required()` only checks `error.message` for the word "profile". Shopify's MCP endpoint encodes the profile signal in `error.data.code` ("invalid_profile_url") and `error.data.content` ("Unable to fetch agent profile: Missing profile uri"), not in `message`. Every Shopify MCP transport incorrectly scores 50 (reachable) instead of 70 (profile_required).

**Deletion first:**
- Delete the existing `_profile_required` function body entirely.

**New code:**
```python
def _profile_required(payload: dict) -> bool:
    error = payload.get("error")
    if not isinstance(error, dict):
        return False
    try:
        code = int(error.get("code"))
    except (TypeError, ValueError):
        return False
    data = error.get("data") if isinstance(error.get("data"), dict) else {}
    text = " ".join([
        str(error.get("message") or "").lower(),
        str(data.get("code") or "").lower(),
        str(data.get("content") or "").lower(),
    ])
    return -32099 <= code <= -32000 and "profile" in text and any(
        kw in text for kw in ("missing", "invalid", "required", "uri", "url")
    )
```

**Acceptance criteria:**
- `grep -n "_profile_required" app/services/ucp_audit/protocol_checks.py` → exactly 2 results (def + 1 call site)
- Unit test: `_profile_required({"error": {"code": -32001, "message": "ucp discovery failed", "data": {"code": "invalid_profile_url", "content": "Unable to fetch agent profile: Missing profile uri"}}})` → `True`
- Unit test: `_profile_required({"error": {"code": -32001, "message": "profile missing"}})` → `True` (existing behaviour preserved)
- Unit test: `_profile_required({"error": {"code": -32001, "message": "internal error"}})` → `False`
- Unit test: `_profile_required({})` → `False`

**Net line count:** −2 (new body is 2 lines shorter than old)

---

#### Slice 1.2 — Separate `signing_keys` from `manifest_valid`

**Scope:**
- `app/services/ucp_audit/types.py`
- `app/services/ucp_audit/discovery.py`
- `app/services/ucp_audit/protocol_checks.py`
- `app/services/ucp_audit/repair_roadmap.py`
- `app/services/config/ucp_audit.py`

**Findings addressed:** B2
**Severity:** 🔴

**Problem:**
`signing_keys` missing is bundled into `shape_errors`, which drives `profile_valid=False` → `manifest_valid=False` → `FINDING_MANIFEST_INVALID` with message "does not declare a valid shopping service." This message is factually wrong. `signing_keys` is a security field (peer of `ucp`, not inside it) and its absence should not invalidate the structural profile. Every store with a valid manifest but no signing keys gets D-UCP1=60 and a misleading finding.

**Deletion first:**
- In `_validate_manifest_shape`: delete the `signing_keys` check block (the `if not isinstance(signing_keys, list):` block).
- In `_discovery_dimension`: delete the hardcoded `60 if findings else 100` score line.

**New code:**

`types.py` — add one field to `UCPManifestResult`:
```python
signing_keys_errors: list[str] = field(default_factory=list)
```

`config/ucp_audit.py` — add constants:
```python
FINDING_SIGNING_KEYS_MISSING = "signing_keys_missing"
```

`discovery.py` — change `_validate_manifest_shape` signature and split return:
```python
def _validate_manifest_shape(payload: dict) -> tuple[list[str], list[str]]:
    """Returns (structural_errors, security_errors).
    structural_errors invalidate manifest_valid.
    security_errors are surfaced as a separate finding only.
    """
    structural_errors: list[str] = []
    security_errors: list[str] = []

    if not isinstance(payload.get("ucp"), dict):
        structural_errors.append("Missing required object: ucp")
        return structural_errors, security_errors

    root = _profile_root(payload)
    version = str(root.get("version") or "")
    if not version:
        structural_errors.append("Missing required field: ucp.version")
    elif not _VERSION_RE.match(version):
        structural_errors.append("ucp.version must be a YYYY-MM-DD date")

    for field in ("services", "capabilities"):
        if not isinstance(root.get(field), dict):
            structural_errors.append(f"Missing required object: ucp.{field}")

    signing_keys = payload.get("signing_keys")
    if not isinstance(signing_keys, list) or not signing_keys:
        security_errors.append("Missing required array: signing_keys")

    return structural_errors, security_errors
```

Update the caller in `discover_ucp_manifest` to unpack the tuple and pass `security_errors` into `UCPManifestResult.signing_keys_errors`. Combine both lists for the `.errors` field to preserve backward compatibility with `build_contract_payload`.

Update `profile_valid` to use only `structural_errors`:
```python
structural_errors, security_errors = _validate_manifest_shape(payload)
# ...
profile_valid = (
    isinstance(root, dict)
    and not missing_services
    and not structural_errors
    and not entry_errors
)
```

`protocol_checks.py` — update `_discovery_dimension`:
```python
def _discovery_dimension(manifest: UCPManifestResult) -> UCPDimensionScore:
    findings: list[UCPFinding] = []

    if not manifest.manifest_found:
        findings.append(UCPFinding(
            code=config.FINDING_MANIFEST_MISSING,
            dimension_id=config.D_UCP1_ID,
            severity=config.UCP_FINDING_BLOCKING,
            message="UCP discovery profile was not found at /.well-known/ucp.",
        ))
        return _dimension(config.D_UCP1_ID, 0, findings)

    if not manifest.manifest_valid:
        findings.append(UCPFinding(
            code=config.FINDING_MANIFEST_INVALID,
            dimension_id=config.D_UCP1_ID,
            severity=config.UCP_FINDING_BLOCKING,
            message="UCP discovery profile has structural errors.",
            evidence=[{
                "errors": [e for e in manifest.errors if "signing_keys" not in e]
            }],
        ))

    if getattr(manifest, "signing_keys_errors", []):
        findings.append(UCPFinding(
            code=config.FINDING_SIGNING_KEYS_MISSING,
            dimension_id=config.D_UCP1_ID,
            severity=config.UCP_FINDING_WARNING,
            message=(
                "signing_keys array is missing or empty. "
                "Webhook signatures cannot be verified per RFC 7797."
            ),
            evidence=[{"errors": list(manifest.signing_keys_errors)}],
        ))

    if (
        manifest.final_url
        and not manifest.final_url.endswith(config.UCP_MANIFEST_PATH)
    ):
        findings.append(UCPFinding(
            code=config.FINDING_MANIFEST_REDIRECTED,
            dimension_id=config.D_UCP1_ID,
            severity=config.UCP_FINDING_WARNING,
            message="UCP discovery profile did not resolve at the canonical well-known path.",
            evidence=[{
                "final_url": manifest.final_url,
                "redirect_chain": manifest.redirect_chain,
            }],
        ))

    # Graduated scoring:
    # 0   = not found (handled above)
    # 40  = structural errors (missing ucp object, version, services)
    # 80  = valid structure but signing_keys missing or redirect warning
    # 100 = fully compliant
    if any(f.code == config.FINDING_MANIFEST_INVALID for f in findings):
        score = 40
    elif findings:
        score = 80
    else:
        score = 100

    return _dimension(config.D_UCP1_ID, score, findings)
```

`repair_roadmap.py` — add entry to `_ACTION_BY_CODE` and `_EFFORT_BY_CODE`:
```python
config.FINDING_SIGNING_KEYS_MISSING: (
    "Add a signing_keys array at the top level of /.well-known/ucp with at least one "
    "EC or RSA JWK public key. Required fields per JWK spec: kty, kid, alg, use='sig'. "
    "Used for webhook signature verification per RFC 7797."
),
# effort:
config.FINDING_SIGNING_KEYS_MISSING: "2-4 hours",
```

**Acceptance criteria:**
- `grep -n "signing_keys" app/services/ucp_audit/discovery.py` → signing_keys check is in `_validate_manifest_shape` only, no other location
- `grep -n "FINDING_SIGNING_KEYS_MISSING" app/services/ucp_audit/` → present in config, `protocol_checks.py`, and `repair_roadmap.py`
- `grep -n "60 if findings" app/services/ucp_audit/protocol_checks.py` → 0 results
- `grep -n "does not declare a valid shopping service" app/services/ucp_audit/protocol_checks.py` → 0 results
- Unit test: manifest with valid structure but no `signing_keys` → `manifest_valid=True`, `signing_keys_errors` non-empty, D-UCP1 score = 80, finding code = `signing_keys_missing`
- Unit test: manifest with missing `ucp.services` → `manifest_valid=False`, D-UCP1 score = 40, finding code = `manifest_invalid`

**Net line count:** +18 (new field, new finding, new config constants — justified: replaces hardcoded behaviour with correct branched logic)

---

#### Slice 1.3 — Tighten transport negotiation finding to reachable-only transports

**Scope:** `app/services/ucp_audit/protocol_checks.py` → `_transport_dimension()`
**Findings addressed:** B3
**Severity:** 🟠

**Problem:**
`any(not item.negotiated for item in transport_probes)` fires even when a transport is unreachable (score 0). The finding message claims "at least one transport is reachable but did not complete full negotiation" — which is wrong for unreachable transports. Also fires when a fully-negotiated transport coexists with an unreachable one, hiding the fact that negotiation succeeded.

**Deletion first:**
- Delete the existing `if any(not item.negotiated ...)` block entirely (4 lines).

**New code:**
```python
reachable_incomplete = [
    item for item in transport_probes
    if _transport_reachable(item, schema_probes) and not item.negotiated
]
if reachable_incomplete:
    findings.append(
        UCPFinding(
            code=config.FINDING_TRANSPORT_NEGOTIATION_INCOMPLETE,
            dimension_id=config.D_UCP3_ID,
            severity=config.UCP_FINDING_WARNING,
            message="At least one reachable transport did not complete full negotiation.",
            evidence=[asdict(item) for item in reachable_incomplete],
        )
    )
```

**Acceptance criteria:**
- `grep -n "any(not item.negotiated" app/services/ucp_audit/protocol_checks.py` → 0 results
- `grep -n "reachable_incomplete" app/services/ucp_audit/protocol_checks.py` → 2 results (assignment + if check)
- Unit test: single unreachable transport → NEGOTIATION_INCOMPLETE finding NOT present, TRANSPORT_UNREACHABLE finding IS present
- Unit test: one negotiated + one reachable-but-not-negotiated → NEGOTIATION_INCOMPLETE IS present, evidence contains only the non-negotiated probe

**Net line count:** −1

---

### Phase 2 — Schema Correctness

---

#### Slice 2.1 — Resolve JSON Schema `$ref` before field searching

**Scope:** `app/services/ucp_audit/protocol_checks.py`
**Findings addressed:** B5
**Severity:** 🟠

**Problem:**
`_schema_contains_field` does a recursive key search but never follows `$ref` pointers. UCP schemas use OpenAPI 3.x with `$ref` chains into `components/schemas`. A required field defined in a referenced component is never found → every compliant site using standard OpenAPI composition gets false "missing field" findings on D-UCP4 and D-UCP6.

**Deletion first:**
- Rewrite `_schema_contains_field` entirely (do not keep the old signature; add `root` param).

**New code — add `_resolve_refs` helper, update `_schema_contains_field`, update `_schema_field_results` caller:**
```python
def _resolve_refs(node: object, root: dict) -> object:
    """Single-step local $ref resolution against the root document.
    Only resolves '#/...' refs. Skips external refs silently.
    """
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if not ref or not isinstance(ref, str) or not ref.startswith("#/"):
        return node
    parts = ref.lstrip("#/").split("/")
    cursor: object = root
    for part in parts:
        if not isinstance(cursor, dict):
            return node  # resolution failed — return original
        cursor = cursor.get(part, {})
    return cursor if cursor != {} else node


def _schema_contains_field(value: object, field: str, root: dict | None = None) -> bool:
    if root is None:
        root = value if isinstance(value, dict) else {}
    if isinstance(value, dict):
        value = _resolve_refs(value, root)
        if not isinstance(value, dict):
            return False
        for key, child in value.items():
            if str(key).lower() == field:
                return True
            if key == "required" and isinstance(child, list):
                if any(str(item).lower() == field for item in child):
                    return True
            if key == "properties" and isinstance(child, dict):
                if any(str(k).lower() == field for k in child):
                    return True
            if _schema_contains_field(child, field, root):
                return True
    if isinstance(value, list):
        return any(_schema_contains_field(item, field, root) for item in value)
    return False


def _schema_field_results(payload: dict) -> dict[str, dict[str, bool]]:
    # Pass payload as root so $refs resolve against the full document
    return {
        group: {
            field: _schema_contains_field(payload, field, root=payload)
            for field in required_fields
        }
        for group, required_fields in config.UCP_REQUIRED_SCHEMA_FIELDS.items()
    }
```

**Acceptance criteria:**
- `grep -n "_resolve_refs" app/services/ucp_audit/protocol_checks.py` → 2 results (def + 1 call)
- `grep -n "root=payload" app/services/ucp_audit/protocol_checks.py` → 1 result (inside `_schema_field_results`)
- Unit test: schema with `{"properties": {"items": {"$ref": "#/components/schemas/Product"}}, "components": {"schemas": {"Product": {"properties": {"product_id": {}}}}}}` → `_schema_contains_field(..., "product_id", root=schema)` returns `True`
- Unit test: external ref `{"$ref": "https://example.com/schema.json"}` → does not raise, returns original node

**Net line count:** +12 (new helper; justified — eliminates false findings on all compliant OpenAPI schemas)

---

#### Slice 2.2 — Fix monolithic schema group detection

**Scope:** `app/services/config/ucp_audit.py`, `app/services/ucp_audit/protocol_checks.py` → `_schema_groups()`
**Findings addressed:** B6
**Severity:** 🟠

**Problem:**
A site with a single `rest.openapi.json` covering all UCP capabilities gets keyword-matched to one group only (e.g. `"catalog"`). Cart/checkout and order/policy field coverage is then scored as zero — D-UCP5 and D-UCP6 are under-scored on every site using the canonical monolithic OpenAPI approach.

**Deletion first:**
- Delete existing `UCP_REQUIRED_SCHEMA_KEYWORDS` dict in config (replace entirely).
- In `_schema_groups`, the field-presence fallback block may already exist — confirm and keep; if missing, add it.

**New config:**
```python
UCP_REQUIRED_SCHEMA_KEYWORDS: dict[str, tuple[str, ...]] = {
    "catalog":       ("catalog", "product", "search", "lookup", "shopping"),
    "cart_checkout": ("cart", "checkout", "shopping"),
    "order_policy":  ("order", "fulfillment", "discount", "policy", "return", "shopping"),
}
```

**`_schema_groups` — ensure field-presence fallback is present:**
```python
def _schema_groups(url: str, payload: dict) -> list[str]:
    text = f"{url} {payload.get('title') or ''} {payload.get('$id') or ''}".lower()
    groups = [
        group
        for group, keywords in config.UCP_REQUIRED_SCHEMA_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]
    # Field-presence fallback: if the schema actually contains fields for a group,
    # assign it even if URL/title keywords didn't match.
    field_results = _schema_field_results(payload)
    for group, results in field_results.items():
        if any(results.values()) and group not in groups:
            groups.append(group)
    return groups
```

**Acceptance criteria:**
- `grep -n "\"shopping\"" app/services/config/ucp_audit.py` → present in all 3 keyword tuples
- Unit test: schema URL `"https://ucp.dev/2026-04-08/services/shopping/rest.openapi.json"` with fields from all 3 groups → `_schema_groups(url, payload)` returns all 3 groups
- Unit test: schema URL `"https://example.com/api/schema.json"` (no keywords) but payload contains `product_id` field → `"catalog"` still in result

**Net line count:** +4

---

### Phase 3 — Transport Accuracy

---

#### Slice 3.1 — Harden REST probe against CORS false positives

**Scope:** `app/services/ucp_audit/protocol_checks.py` → `_probe_rest()`
**Findings addressed:** B4
**Severity:** 🟠

**Problem:**
`negotiated = response.status_code < 400 and bool(allow or response.headers)` marks any server with CORS headers as fully negotiated. Any non-UCP API with a generic OPTIONS handler scores 100 on REST transport.

**Deletion first:**
- Delete the existing `_probe_rest` function body (keep signature).

**New code:**
```python
async def _probe_rest(*, service: str, endpoint: str) -> UCPTransportProbe:
    try:
        async with build_async_http_client(
            follow_redirects=True,
            timeout=config.UCP_TRANSPORT_TIMEOUT_SECONDS,
        ) as client:
            # Step 1: OPTIONS for capability advertisement
            options_resp = await client.options(
                endpoint,
                headers={"Accept": config.UCP_ACCEPT_HEADER},
            )
            # Step 2: GET to confirm UCP-shaped response
            get_resp = await client.get(
                endpoint,
                headers={"Accept": config.UCP_ACCEPT_HEADER},
            )

        allow = options_resp.headers.get("allow", "")
        reachable = options_resp.status_code < 500

        get_payload = _safe_json(get_resp)
        ucp_shaped = (
            isinstance(get_payload.get("capabilities"), (list, dict))
            or isinstance(get_payload.get("services"), dict)
            or bool(get_resp.headers.get("UCP-Version"))
            or "ucp" in str(get_payload.get("$schema") or "").lower()
        )
        negotiated = (
            reachable
            and get_resp.status_code < 400
            and ucp_shaped
        )
        return UCPTransportProbe(
            service=service,
            transport="rest",
            endpoint=endpoint,
            reachable=reachable,
            negotiated=negotiated,
            status_code=options_resp.status_code,
            error="" if reachable else options_resp.text[:240],
            response_preview={"allow": allow, "get_keys": sorted(get_payload.keys())} if allow else {},
        )
    except (httpx.HTTPError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
        logger.debug("UCP REST probe failed for %s: %s", endpoint, exc, exc_info=True)
        return UCPTransportProbe(service=service, transport="rest", endpoint=endpoint, error=str(exc))
```

**Acceptance criteria:**
- `grep -n "bool(allow or response.headers)" app/services/ucp_audit/protocol_checks.py` → 0 results
- `grep -n "ucp_shaped" app/services/ucp_audit/protocol_checks.py` → 2 results (assignment + use)
- Unit test: endpoint returning OPTIONS 200 with CORS headers + GET 200 with `{"error": "not found"}` → `negotiated=False`
- Unit test: endpoint returning GET 200 with `{"capabilities": [...]}` → `negotiated=True`

**Net line count:** +10 (justified — eliminates a class of false positives)

---

#### Slice 3.2 — Use best-transport score instead of average

**Scope:** `app/services/ucp_audit/protocol_checks.py` → `_transport_dimension()`
**Findings addressed:** B7
**Severity:** 🟠

**Problem:**
`_average(scores)` across all transport probes means a site with one negotiated REST transport (100) and one broken MCP transport (0) scores 50. The spec only requires one working transport. Averaging punishes breadth.

**Deletion first:**
- Delete the `scores = [...]` + `return _dimension(..., _average(scores), ...)` lines.

**New code:**
```python
scores = [_transport_probe_score(item, schema_probes) for item in transport_probes]
best = max(scores, default=0)
# Small breadth bonus: +5 per additional transport scoring >= 70, capped at +10
bonus = min(10, 5 * max(0, len([s for s in scores if s >= 70]) - 1))
final_score = min(100, best + bonus)
return _dimension(config.D_UCP3_ID, final_score, findings)
```

**Acceptance criteria:**
- `grep -n "_average(scores)" app/services/ucp_audit/protocol_checks.py` → 0 results
- `grep -n "best = max(scores" app/services/ucp_audit/protocol_checks.py` → 1 result
- Unit test: probes = [score 100, score 0] → D-UCP3 score = 100
- Unit test: probes = [score 70, score 70] → D-UCP3 score = 75 (70 + 5 bonus)
- Unit test: probes = [score 50] → D-UCP3 score = 50

**Net line count:** −1

---

#### Slice 3.3 — Add `UCP-Agent` header to MCP probe

**Scope:** `app/services/config/ucp_audit.py`, `app/services/ucp_audit/protocol_checks.py` → `_probe_mcp()`
**Findings addressed:** G1
**Severity:** 🟡

**Problem:**
Without a `UCP-Agent` header pointing to a platform profile, conformant UCP servers reject the MCP probe per spec. The audit is testing as a malformed client; the server's rejection is correct behaviour, not a server failure.

**Config addition:**
```python
# Set to a real hosted platform profile for meaningful negotiation.
# Without a real profile, servers will still accept the header format
# and the rejection reason will shift from "missing profile uri" to
# "capability intersection failed" — which is more informative.
UCP_AUDIT_PLATFORM_PROFILE_URL = "https://your-audit-platform.example.com/.well-known/ucp"
```

**`_probe_mcp` change — replace headers dict:**
```python
# Before:
headers={"Accept": config.UCP_ACCEPT_HEADER}

# After:
headers={
    "Accept": config.UCP_ACCEPT_HEADER,
    "UCP-Agent": f'profile="{config.UCP_AUDIT_PLATFORM_PROFILE_URL}"',
}
```

**Acceptance criteria:**
- `grep -n "UCP-Agent" app/services/ucp_audit/protocol_checks.py` → 1 result (inside `_probe_mcp`)
- `grep -n "UCP_AUDIT_PLATFORM_PROFILE_URL" app/services/config/ucp_audit.py` → 1 result
- Integration test against a local mock MCP server: request headers include `UCP-Agent`

**Net line count:** +3

---

### Phase 4 — Spec Completeness

---

#### Slice 4.1 — Validate `Cache-Control` header on manifest response

**Scope:** `app/services/ucp_audit/discovery.py` (new helper), `app/services/ucp_audit/protocol_checks.py` → `_discovery_dimension()`, `app/services/config/ucp_audit.py`
**Findings addressed:** G2
**Severity:** 🟡

**Config addition:**
```python
FINDING_CACHE_CONTROL_MISSING = "cache_control_missing"
```

**New helper in `discovery.py`:**
```python
def check_manifest_cache_headers(headers: dict) -> list[str]:
    cc = str(headers.get("cache-control") or headers.get("Cache-Control") or "").lower()
    if not cc:
        return ["Missing Cache-Control header (spec requires public, max-age >= 60)"]
    errors: list[str] = []
    if "public" not in cc:
        errors.append("Cache-Control header missing 'public' directive")
    m = re.search(r"max-age=(\d+)", cc)
    if not m or int(m.group(1)) < 60:
        errors.append("Cache-Control max-age must be >= 60 seconds per UCP spec")
    return errors
```

Expose `response_headers` through `UCPManifestResult` (add `response_headers: dict = field(default_factory=dict)`), populate it in `discover_ucp_manifest`, and call `check_manifest_cache_headers` inside `_discovery_dimension` to append a warning finding if errors exist.

**Repair roadmap addition:**
```python
config.FINDING_CACHE_CONTROL_MISSING: (
    "Add 'Cache-Control: public, max-age=300' (or higher) to the /.well-known/ucp response. "
    "The UCP spec requires at least 60 seconds to allow platforms to cache the profile."
),
```

**Acceptance criteria:**
- `grep -n "FINDING_CACHE_CONTROL_MISSING" app/services/ucp_audit/` → present in config, `protocol_checks.py`, `repair_roadmap.py`
- `grep -n "check_manifest_cache_headers" app/services/ucp_audit/` → def in `discovery.py`, call in `protocol_checks.py`
- Unit test: headers `{}` → error list non-empty
- Unit test: headers `{"cache-control": "public, max-age=300"}` → empty list

**Net line count:** +18

---

#### Slice 4.2 — Add A2A transport probe stub

**Scope:** `app/services/ucp_audit/protocol_checks.py` → `probe_transports()`
**Findings addressed:** G3
**Severity:** 🟡

**Problem:**
`transport: a2a` entries fall through all `if` branches and receive an empty probe with `reachable=False` and misleading error "missing schema or endpoint."

**Deletion first:**
- Remove the implicit fall-through to the catch-all `probes.append(UCPTransportProbe(..., error="missing schema or endpoint"))` for `a2a` transports (keep for truly unknown transports).

**New code — add A2A branch and minimal probe:**
```python
if transport == "a2a" and endpoint:
    probes.append(await _probe_a2a(service=service, endpoint=endpoint))
    continue

# ... existing fallthrough for unknown/missing transports ...


async def _probe_a2a(*, service: str, endpoint: str) -> UCPTransportProbe:
    """Minimal A2A probe: reachability check + agent-card detection."""
    try:
        async with build_async_http_client(
            follow_redirects=True,
            timeout=config.UCP_TRANSPORT_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(
                endpoint,
                headers={"Accept": config.UCP_ACCEPT_HEADER},
            )
        payload = _safe_json(response)
        # A2A agent cards declare "capabilities" or have an "agent" key
        a2a_shaped = (
            isinstance(payload.get("capabilities"), (list, dict))
            or "agent" in payload
            or bool(response.headers.get("A2A-Version"))
        )
        return UCPTransportProbe(
            service=service,
            transport="a2a",
            endpoint=endpoint,
            reachable=response.status_code < 500,
            negotiated=response.status_code < 400 and a2a_shaped,
            status_code=response.status_code,
            error="" if response.status_code < 400 else response.text[:240],
            response_preview=_preview(payload),
        )
    except (httpx.HTTPError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
        logger.debug("UCP A2A probe failed for %s: %s", endpoint, exc, exc_info=True)
        return UCPTransportProbe(service=service, transport="a2a", endpoint=endpoint, error=str(exc))
```

**Acceptance criteria:**
- `grep -n "_probe_a2a" app/services/ucp_audit/protocol_checks.py` → 2 results (def + call)
- `grep -n "transport == \"a2a\"" app/services/ucp_audit/protocol_checks.py` → 1 result
- Unit test: transport entry with `transport="a2a"` and valid endpoint → probe is not the catch-all stub, `error != "missing schema or endpoint"`

**Net line count:** +22 (justified — new transport class; no existing code deleted)

---

#### Slice 4.3 — Validate JWK structure in `signing_keys`

**Scope:** `app/services/ucp_audit/discovery.py` — extend security_errors from Slice 1.2
**Findings addressed:** G4
**Severity:** 🟡

**Add after the `signing_keys` array check inside `_validate_manifest_shape`:**
```python
_JWK_REQUIRED_FIELDS = frozenset({"kid", "kty", "use", "alg"})

# Inside _validate_manifest_shape, after the array existence check:
if isinstance(signing_keys, list):
    for i, key in enumerate(signing_keys):
        if not isinstance(key, dict):
            security_errors.append(f"signing_keys[{i}] is not an object")
            continue
        missing_jwk = _JWK_REQUIRED_FIELDS - set(key.keys())
        if missing_jwk:
            security_errors.append(
                f"signing_keys[{i}] missing required JWK fields: {sorted(missing_jwk)}"
            )
        if str(key.get("use") or "") not in ("sig",):
            security_errors.append(
                f"signing_keys[{i}].use must be 'sig', got: {key.get('use')!r}"
            )
```

**Acceptance criteria:**
- `grep -n "_JWK_REQUIRED_FIELDS" app/services/ucp_audit/discovery.py` → 2 results (def + use)
- Unit test: `signing_keys=[{}]` → security_errors contains JWK field errors
- Unit test: `signing_keys=[{"kid":"k1","kty":"EC","use":"sig","alg":"ES256","crv":"P-256","x":"...","y":"..."}]` → security_errors empty

**Net line count:** +12

---

#### Slice 4.4 — Validate `spec` URL in service and capability entries

**Scope:** `app/services/ucp_audit/discovery.py` → `_validate_entry_versions()`
**Findings addressed:** G5
**Severity:** 🟡

**Add inside the per-entry loop:**
```python
if not str(entry.get("spec") or "").strip():
    errors.append(f"Missing spec URL for {kind} {entry.get('name')!r}")
```

**Acceptance criteria:**
- `grep -n "spec URL" app/services/ucp_audit/discovery.py` → 1 result
- Unit test: service entry with no `spec` field → `_errors` contains "Missing spec URL"
- Unit test: service entry with valid `spec` URL → `_errors` does not contain spec error

**Net line count:** +2

---

#### Slice 4.5 — Check capability version alignment against service version

**Scope:** `app/services/ucp_audit/discovery.py` (new helper), `app/services/ucp_audit/protocol_checks.py` → `_services_dimension()`, `app/services/config/ucp_audit.py`
**Findings addressed:** G7
**Severity:** 🟡

**Config addition:**
```python
FINDING_CAPABILITY_VERSION_MISMATCH = "capability_version_mismatch"
```

**New helper in `discovery.py`:**
```python
def check_version_alignment(
    service_entries: list[dict],
    capability_entries: list[dict],
    required_service: str,
) -> list[str]:
    service_version = next(
        (str(e.get("version") or "") for e in service_entries if e.get("name") == required_service),
        "",
    )
    if not service_version:
        return []
    mismatches = []
    for cap in capability_entries:
        cap_version = str(cap.get("version") or "")
        if cap_version and cap_version != service_version:
            mismatches.append(
                f"{cap['name']} declares version {cap_version!r} but service is "
                f"{service_version!r} — may fail capability intersection"
            )
    return mismatches
```

In `_services_dimension`, call `check_version_alignment` after entry validation and append a warning finding if mismatches exist.

**Acceptance criteria:**
- `grep -n "check_version_alignment" app/services/ucp_audit/` → def in `discovery.py`, call in `protocol_checks.py`
- Unit test: service `2026-04-08`, capability `2026-01-11` → mismatch error returned
- Unit test: service `2026-04-08`, capability `2026-04-08` → empty list

**Net line count:** +20

---

### Phase 5 — Polish

---

#### Slice 5.1 — Fix `_status()` to use severity check, not `not findings`

**Scope:** `app/services/ucp_audit/protocol_checks.py` → `_status()`
**Findings addressed:** G6
**Severity:** 🟡

**Delete** the current `_status` body. **Replace:**
```python
def _status(score: int, findings: list[UCPFinding]) -> str:
    if any(item.severity == config.UCP_FINDING_BLOCKING for item in findings):
        return config.UCP_STATUS_FAIL
    has_warnings = any(item.severity == config.UCP_FINDING_WARNING for item in findings)
    if score >= 80 and not has_warnings:
        return config.UCP_STATUS_PASS
    if score >= 50:
        return config.UCP_STATUS_WARNING
    return config.UCP_STATUS_FAIL
```

**Acceptance criteria:**
- `grep -n "not findings" app/services/ucp_audit/protocol_checks.py` → 0 results in `_status`
- Unit test: score=100, findings=[warning-severity finding] → status = "warning"
- Unit test: score=100, findings=[] → status = "pass"
- Unit test: score=80, findings=[] → status = "pass"

**Net line count:** −1

---

#### Slice 5.2 — Surface finding-specific errors in repair roadmap actions

**Scope:** `app/services/ucp_audit/repair_roadmap.py` → `build_repair_roadmap()`
**Findings addressed:** G9
**Severity:** 💡

**Add private helper, use it inside the list comprehension:**
```python
def _action_for(finding: UCPFinding) -> str:
    base = _ACTION_BY_CODE.get(finding.code, finding.message or finding.code)
    if finding.evidence:
        errors = finding.evidence[0].get("errors") or []
        if errors and finding.code in {
            config.FINDING_MANIFEST_INVALID,
            config.FINDING_SIGNING_KEYS_MISSING,
            config.FINDING_SERVICE_INVALID,
            config.FINDING_CAPABILITY_INVALID,
        }:
            detail = "; ".join(str(e) for e in errors[:3])
            return f"{base} Errors: {detail}"
    return base

# In build_repair_roadmap, replace:
#   action=_ACTION_BY_CODE.get(finding.code, finding.message or finding.code),
# with:
#   action=_action_for(finding),
```

**Acceptance criteria:**
- `grep -n "_action_for" app/services/ucp_audit/repair_roadmap.py` → 2 results (def + call)
- Unit test: finding with `code=FINDING_MANIFEST_INVALID` and `evidence=[{"errors":["Missing ucp.version"]}]` → action contains "Missing ucp.version"

**Net line count:** +8

---

## Verification Checklist (run after all phases complete)

```bash
# 1. No old patterns remain
grep -rn "60 if findings"                   app/services/ucp_audit/  # → 0
grep -rn "does not declare a valid shopping" app/services/ucp_audit/  # → 0
grep -rn "any(not item.negotiated"           app/services/ucp_audit/  # → 0
grep -rn "bool(allow or response.headers)"   app/services/ucp_audit/  # → 0
grep -rn "_average(scores)"                  app/services/ucp_audit/  # → 0

# 2. New patterns present
grep -rn "FINDING_SIGNING_KEYS_MISSING"      app/services/ucp_audit/  # → ≥ 3
grep -rn "_resolve_refs"                     app/services/ucp_audit/  # → 2
grep -rn "UCP-Agent"                         app/services/ucp_audit/  # → 1
grep -rn "reachable_incomplete"              app/services/ucp_audit/  # → 2
grep -rn "ucp_shaped"                        app/services/ucp_audit/  # → 2
grep -rn "_probe_a2a"                        app/services/ucp_audit/  # → 2
grep -rn "best = max(scores"                 app/services/ucp_audit/  # → 1
grep -rn "check_manifest_cache_headers"      app/services/ucp_audit/  # → 2
grep -rn "check_version_alignment"           app/services/ucp_audit/  # → 2

# 3. Unit test suite passes
pytest app/tests/ucp_audit/ -v

# 4. Smoke test against known-good Shopify store
# Expected after fixes:
# D-UCP1: 80 (signing_keys_missing warning, not manifest_invalid)
# D-UCP3: 70 (profile_required=True, not reachable-only 50)
# D-UCP4/5/6: scores reflect actual schema field coverage, not all-missing