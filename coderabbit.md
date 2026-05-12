Fix the following issues. The issues can be from different files or can overlap on same lines in one file.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/api/crawls.py at line 222, There is a redundant local import of CrawlRun ("from app.models.crawl_run import CrawlRun") that duplicates the module-level import; remove the local import to avoid redundancy, or if it was added to avoid a circular dependency keep it but document the reason and instead use a conditional import pattern (e.g., move the import into a block guarded by typing.TYPE_CHECKING or refactor to a late import at call site with a clear comment) so the symbol CrawlRun is only defined once and the intent is clear.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/api/review.py around lines 49 - 50, The code calls _get_review_run_or_404(session, run_id=run_id, user=user) to fetch run but then passes run.id to build_review_payload; simplify by using run_id directly (build_review_payload(session, run_id)) when only the ID is required, or alternatively modify build_review_payload to accept the run object (e.g., build_review_payload(session, run)) if additional run fields are needed; apply the same change to the review_artifact_html call to remove unnecessary run.id indirection and keep calls consistent with the chosen approach.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/core/dependencies.py around lines 69 - 73, get_run_dispatcher currently constructs a new CeleryRunDispatcher or LocalRunDispatcher on every call (causing resource leaks when used as a FastAPI dependency); change it to return a single shared instance instead — either by decorating get_run_dispatcher with functools.lru_cache() so it returns a singleton or by creating the dispatcher once during app startup (lifespan) and storing it on app.state (e.g., app.state.run_dispatcher) then update the dependency to read that value; also ensure you call the dispatchers' cleanup/shutdown method on app shutdown to close broker connections/thread pools.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/crawl_run.py around lines 98 - 101, The set_status method (function set_status) currently updates self.status but does not set completed_at when reaching a terminal state; modify set_status to check the resolved CrawlStatus (from transition_status) against TERMINAL_STATUSES and, if it is terminal and self.completed_at is None, set self.completed_at = _utcnow() before returning next_status; reference transition_status, CrawlStatus, TERMINAL_STATUSES, completed_at and _utcnow when making the change so the timestamp is automatically populated on terminal transitions.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/crawl_run.py around lines 137 - 140, The apply_batch_progress_patch method simply forwards to merge_summary_patch with no extra logic; remove this redundant indirection by deleting apply_batch_progress_patch from CrawlRun and update all call sites to call merge_summary_patch(patch) directly, or if you intend to keep a semantic alias, retain apply_batch_progress_patch but add a one-line docstring indicating it is an alias for merge_summary_patch and keep it trivial; locate the methods apply_batch_progress_patch and merge_summary_patch in the CrawlRun class to perform the change and update any imports/usages accordingly.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/crawl_run.py around lines 168 - 174, The enrichment_status mapped_column currently sets both a Python-side default and a database-side server_default to DATA_ENRICHMENT_STATUS_UNENRICHED; remove the redundancy by dropping one of them—preferably remove the Python-side default argument (default=...) and keep server_default=DATA_ENRICHMENT_STATUS_UNENRICHED so the DB enforces the value and SQLAlchemy will reflect it, leaving enrichment_status, mapped_column, nullable=False, and index=True unchanged; if you prefer Python-level defaults for tests, instead remove server_default and keep default=DATA_ENRICHMENT_STATUS_UNENRICHED.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/data_enrichment.py at line 26, The user_id foreign key mapping (user_id: Mapped[int] = mapped_column(ForeignKey(USERS_FK), index=True)) lacks an ondelete policy; update the ForeignKey definition to include the desired ondelete behavior (e.g., ondelete="CASCADE") so deletions of the referenced user propagate to DataEnrichment rows, or if you prefer to preserve jobs use ondelete="SET NULL" and change the user_id mapped type to be nullable; adjust the mapped_column call for user_id accordingly.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/data_enrichment.py at line 67, The model field source_url currently uses mapped_column(Text, default="") which stores an empty string instead of a true NULL; change it to use nullable semantics by updating the annotation to Mapped[Optional[str]] and the column to mapped_column(Text, nullable=True) (or if empty strings are required at DB-level use server_default=text("''") and import text from sqlalchemy); update any callers/tests that assume non-empty default as needed.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/data_enrichment.py at line 90, The diagnostics column currently uses a mutable Python default (Mapped[dict] = mapped_column(JSONB, default=dict)); replace the Python-side default with a PostgreSQL server default to avoid shared mutable state: remove default=dict and add a server_default using sqlalchemy.text to set '{}'::jsonb (ensure text is imported), leaving the column definition as diagnostics: Mapped[dict] = mapped_column(JSONB, server_default=text("'{ }'::jsonb") or text("'{}'::jsonb")). Ensure the import for text is present and adjust accordingly in the same module where diagnostics, Mapped, mapped_column and JSONB are defined.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/domain_memory.py around lines 78 - 82, The model defines source_run_id as a ForeignKey but lacks an ORM relationship for navigation; add a relationship for CrawlRun by importing sqlalchemy.orm.relationship if needed and declare a mapped relationship attribute (e.g., source_run: Mapped["CrawlRun"]) on the same class using relationship("CrawlRun", foreign_keys=[source_run_id]) so you can traverse from this model to the related CrawlRun via source_run.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/domain_memory.py at line 25, The JSONB column "selectors" uses a Python-side default (default=dict); change it to have a DB-level default as well by adding a server_default using SQL text for an empty JSON object (e.g. server_default=text("'{ }'::jsonb") — use the correct JSON empty object literal) while keeping the Python default for ORM behavior, and import text (or sqlalchemy.text) if not present; apply the same change to every other JSONB column in this file that currently uses default=dict so the database will supply an empty JSON object for inserts from raw SQL/migrations/external tools.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/product_intelligence.py around lines 44 - 45, The JSONB mapped columns options and summary are using a mutable default that can be shared across instances; update their mapped_column declarations to use a callable factory or a DB-level default instead (e.g., replace default=dict with a callable that returns a new dict for each instance or use server_default with an empty JSONB literal), and adjust imports if needed (refer to the options and summary mapped_column calls and JSONB usage to locate the lines and to add sqlalchemy.text or appropriate factory usage).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/product_intelligence.py at line 77, The payload column definition uses a mutable default (default=dict) which can lead to shared state; update the mapped_column call for payload in product_intelligence (the Mapped[dict] payload field) to use a callable default (e.g., default=lambda: {}) or a server-side default (e.g., server_default='{}') instead of default=dict so each row gets its own empty dict instance.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/product_intelligence.py around lines 150 - 151, The columns score_reasons and llm_enrichment currently use the mutable default antipattern (default=dict); update their mapped_column definitions to use a callable factory or a DB server default instead. Specifically, change mapped_column(JSONB, default=dict) to use a callable like mapped_column(JSONB, default=lambda: {}) or set a server default such as mapped_column(JSONB, server_default=text(" '{}'::jsonb")) (import text from sqlalchemy) so each instance gets its own empty object and you avoid shared mutable state.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/product_intelligence.py around lines 112 - 127, The composite index ix_product_intelligence_matches_job_source already covers (job_id, source_product_id) and you currently also add a standalone index by using index=True on the mapped_column for source_product_id; decide which to keep based on query patterns and either remove index=True from the source_product_id mapped_column in product_intelligence.py (to avoid duplicate indexes) or keep it if you have frequent filters solely on source_product_id, and then generate the corresponding DB migration to add/remove the redundant index accordingly.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/product_intelligence.py at line 107, The payload column uses a mutable default (payload: Mapped[dict] = mapped_column(JSONB, default=dict)); replace the mutable default with a callable or a server default to avoid shared state — for example change the mapped_column call to use a callable factory (e.g. default_factory=dict) or set a JSONB server default (e.g. server_default=text("'{ }'::jsonb") or similar), updating the mapped_column(JSONB, ...) invocation for the payload attribute accordingly.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/product_intelligence.py at line 33, The user_id foreign key on the ProductIntelligence model (user_id: Mapped[int] = mapped_column(ForeignKey(USERS_FK), index=True)) lacks an ondelete rule; update the ForeignKey definition for user_id to include an explicit ondelete behavior (e.g., ondelete="CASCADE" if ProductIntelligence rows should be removed when a User is deleted, or ondelete="SET NULL" and adjust the column to allow nulls if jobs should remain unlinked). Ensure the change is applied to the mapped_column/ForeignKey invocation for the user_id field and run or add the corresponding migration to apply the constraint to the database.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/review.py around lines 16 - 20, The Review model currently indexes run_id and domain separately (mapped columns run_id, domain, surface); add appropriate table-level constraints to match query patterns: if queries filter by run_id+domain add a composite Index via __table_args__ including Index('ix_review_run_domain', 'run_id', 'domain'); if business rules require uniqueness of the tuple add a UniqueConstraint in __table_args__ such as UniqueConstraint('run_id', 'domain', 'surface', name='uq_review_run_domain_surface'). Ensure __table_args__ is added to the Review model class so the ORM creates the composite index/unique constraint.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/review.py around lines 21 - 22, approved_schema and field_mapping are using a Python-level default(dict) only; update their mapped_column declarations to enforce non-null DB constraints by adding nullable=False and a JSONB server default (e.g. server_default using SQL text for an empty JSON object like "'{}'::jsonb" via sqlalchemy.text), and add a corresponding migration to set existing NULLs to {} and alter the columns to use the new server_default; locate the fields by name (approved_schema, field_mapping) and modify the mapped_column(...) calls that use MutableDict.as_mutable(JSONB).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/config/extraction_rules.exports.json at line 4431, The regex entry "^ships?\\s+(?:in|within|same\\s*day|today)\\s*[\\w\\d\\-\\s/(),%]*$" is too permissive at the end and can match arbitrary trailing content; update that pattern (the string shown in the diff) to constrain the trailing portion to only allow explicit timeframe phrases (e.g., numeric ranges like "in 2-3 days", "within 5 business days", or the fixed phrases "same day" / "today") and ensure the pattern still uses anchors so no extra text (phone numbers, notes, or percentages) can follow. Locate the exact regex string in extraction_rules.exports.json and replace the permissive tail with a stricter timeframe-only alternative that accepts numeric ranges and known units (days, business days, hours) and then ends.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/config/extraction_rules.py around lines 1330 - 1341, The change adds "swatch", "dyo-" and "/static-dyo" to NON_PRODUCT_IMAGE_HINTS which risks filtering legitimate variant-selection swatch images; review the addition against docs/INVARIANTS.md Rule 3 and either narrow the pattern or move site-specific tokens into a separate config. Update NON_PRODUCT_IMAGE_HINTS in extraction_rules.py to replace the broad "swatch" token with more specific heuristics (e.g., URL path prefixes, filename suffixes, or context checks like DOM sibling/class patterns and image dimensions) and remove or relocate "dyo-" and "/static-dyo" into a site-specific rules file (e.g., extraction_rules.exports.json) so generic variant extraction (functions that consume NON_PRODUCT_IMAGE_HINTS) is not broken.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/dispatch/base.py around lines 10 - 17, Update the RunDispatcher Protocol docstring to explicitly state transaction and return-value semantics: clarify whether implementations must commit/rollback the provided session or leave that to the caller (e.g., "implementations should not commit; caller is responsible" or vice versa), describe that the returned CrawlRun is a refreshed instance tied to the same DB row (or a newly reloaded instance) and whether it may be the same Python object or a new one, and enumerate expected error behavior (which exceptions to raise on failures such as ValueError/RuntimeError/DatabaseError or a custom DispatchError) so implementers know how to signal retryable vs fatal errors; reference RunDispatcher, CrawlRun, and the session parameter in the text so readers can map these semantics to the protocol methods.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/dispatch/celery_dispatcher.py at line 43, The code repeatedly wraps run.id and loaded_run.id with int(...) which is either redundant or unsafe if id can be None; update the Celery dispatcher to either remove the int() casts if run.id/loaded_run.id are already typed as int, or add explicit non-null guards (e.g., assert/run.id is not None or raise a ValueError) before converting to int so a TypeError is avoided; apply this change for the occurrences referencing run.id and loaded_run.id in celery_dispatcher.py (the variables named run and loaded_run).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/dispatch/celery_dispatcher.py around lines 42 - 49, The code currently loads the run with _load_run_with_normalized_status and then sets a task id with _set_task_id/_new_task_id before committing, which allows a race where another transaction can change the run state between load and commit; fix this by acquiring a row lock when loading the run (use SQLAlchemy select(...).where(CrawlRun.id==run.id).with_for_update() or modify _load_run_with_normalized_status to perform the SELECT FOR UPDATE), then re-check the status (PENDING or RUNNING), call _new_task_id and _set_task_id on the locked loaded_run, and finally commit; ensure you raise the same ValueError if the run is missing or in an invalid state after acquiring the lock.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/dispatch/celery_dispatcher.py around lines 57 - 62, The run fallback leaves a stale Celery task_id on loaded_run even though we fall back to in-process execution; clear loaded_run.task_id (set earlier) and persist that change to the DB before calling track_local_run_task to avoid inconsistent state. Locate the warning/except block containing logger.warning(...) and track_local_run_task(int(loaded_run.id)) and, before invoking track_local_run_task, set loaded_run.task_id = None, add/persist the loaded_run to the session (or call the existing save/commit routine used when setting the task_id), and commit the transaction so the database reflects that no Celery task is active.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/dispatch/local_dispatcher.py around lines 101 - 107, The ValueError raised in _load_run_with_normalized_status lacks context; change the exception to include the run_id (e.g., raise ValueError(f"Run not found: {run_id}")) so callers and logs can identify which run failed to load; update the raise in the function that currently does await session.get(CrawlRun, run_id) and leave the returned tuple (run, run.status_value) unchanged.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/dispatch/local_dispatcher.py around lines 113 - 128, The dispatch implementation calls recover_stale_local_runs on every invocation, permits RUNNING which risks duplicate execution, and can persist a task_id then fail to start the task leaving inconsistent state; update dispatch to (1) remove the call to recover_stale_local_runs (move that call to startup or a periodic background job outside the dispatch flow), (2) disallow dispatching runs already in CrawlStatus.RUNNING (only allow PENDING) or ensure any existing task is cancelled via clear_local_run_task before assigning a new task, and (3) make the commit + task start atomic by wrapping _set_task_id/ session.commit()/ session.refresh()/ track_local_run_task in a try/except: on failure rollback the session and clear the persisted task_id (using clear_local_run_task or resetting on loaded_run and committing) so the DB does not retain a dangling task_id; refer to _load_run_with_normalized_status, _set_task_id, track_local_run_task, clear_local_run_task, and recover_stale_local_runs when making these changes.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/dispatch/local_dispatcher.py around lines 45 - 53, clear_local_run_task currently removes the Task from _local_run_tasks but doesn't cancel it, allowing orphaned concurrent runs; update clear_local_run_task(run_id, *, expected_task=None) to check the found Task and, if it matches expected_task (or if expected_task is None), call task.cancel() before popping it from _local_run_tasks, and optionally await its completion or swallow asyncio.CancelledError where appropriate; adjust track_local_run_task to rely on this behavior when replacing an existing task so no running task is left untracked.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/domain_memory_service.py at line 6, You moved the DomainMemory class into app.models.domain_memory; verify and update all import sites to use this new module path (e.g., replace prior imports like from app.models import DomainMemory or from app.models.some_other_module import DomainMemory with from app.models.domain_memory import DomainMemory), search the repo for "DomainMemory" references to catch stale imports, update any failing tests or lint errors, and ensure any __init__.py in app.models either re-exports DomainMemory or remove old re-export usages accordingly.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/listing_candidate_ranking.py around lines 40 - 45, The fallback signature returned for empty/error cases currently uses a leading pipe ("|0|0") which yields an inconsistent 4-part string when split; update the returns in this block (the branch that checks `if not raw` and the `except ValueError` branch around the `urlsplit(raw)` call) to use a consistent 3-part signature format (e.g. "0|0|0" or "{prefix}|{detail}|{depth}" with zeros) so all signatures produced by this code are 3-part when split by '|'.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/listing_candidate_ranking.py around lines 110 - 124, The diagnostics code recomputes cohort homogeneity and signatures; update _listing_record_set_score to include and return the homogeneity (and/or signature counts) as part of its score tuple, then update callers (e.g., where score is produced and used in best_listing_candidate_set / the variable score) to unpack the homogeneity value and use it for diagnostics_sink instead of recomputing; remove the duplicate calls to _set_cohort_homogeneity and the signature Counter block in the diagnostics emission so prepared and score are reused for diagnostic fields like "cohort_homogeneity_ratio" and "dominant_signature_count".

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/listing_candidate_ranking.py around lines 59 - 72, The function _set_cohort_homogeneity currently accepts an unused page_url parameter and contains a redundant check for not signatures; remove the unused page_url parameter from the signature (or, if you must keep it for API compatibility, add a comment explaining it's intentionally unused) and delete the redundant "if not signatures" branch since records is already guarded by "if not records" and we append one signature per record; ensure any callers are updated if you remove page_url or leave a TODO comment if retained for future use.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/listing_card_fragments.py around lines 144 - 150, The prefix comparison can fail because path is lowercased but each item from LISTING_CATEGORY_PATH_PREFIXES isn't; update the comparison in the loop that sets prefix_bucket so prefix_text is normalized (e.g., lowercased and cast to str) before calling startswith, or ensure LISTING_CATEGORY_PATH_PREFIXES is pre-normalized to lowercase; adjust the logic around parsed.path, prefix_text, LISTING_CATEGORY_PATH_PREFIXES, and the prefix_bucket assignment so comparisons use the same case.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/listing_card_fragments.py at line 93, Replace the direct call signature = listing_node_signature(node, include_title=False) with the existing wrapper _listing_node_signature(node) for consistency with other functions in this file; locate the occurrence where signature is assigned and change it to use _listing_node_signature(node) so all calls uniformly wrap listing_node_signature(node, include_title=False).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/listing_card_fragments.py around lines 73 - 76, The type hint for _listing_count_bucket is inconsistent with its None check; update the signature to accept None (change count: int to count: int | None or Optional[int]) and adjust the docstring to state it accepts None, or if callers never pass None, remove the None branch (the conditional on line with value = int(count) if count is not None else 0) and simplify to value = int(count). Update the function signature and docstring accordingly and keep the internal variable name/value logic in _listing_count_bucket consistent with the chosen approach.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/listing_integrity_gate.py at line 75, The if condition "if record_count > 0 and record_count < min_records:" is redundant; remove the unnecessary "record_count > 0" check and simplify it to "if record_count < min_records:" (keeping the existing empty-set guard above intact). Update the check in listing_integrity_gate.py where record_count and min_records are used so the code reads only the simpler comparison, ensuring behavior is unchanged.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/listing_integrity_gate.py around lines 169 - 174, Add a short clarifying comment above the for loop that iterates LISTING_CATEGORY_PATH_PREFIXES explaining the dual-check: the first condition path.startswith(prefix) handles absolute paths (with leading slash) while the second reconstructed check (f"/{'/'.join(segments[:2])}".startswith(prefix) if len(segments) >= 2 else False) handles relative URLs that lack a leading slash by rebuilding the first two segments with a leading slash; reference the variables LISTING_CATEGORY_PATH_PREFIXES, path, segments, and prefix_bucket so future readers understand why both checks are necessary.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/listing_integrity_gate.py around lines 27 - 34, Update the IntegrityDecision dataclass to use a stricter Literal type for the outcome field: import typing.Literal and change outcome: str to outcome: Literal["product_grid", "promo_only_cluster"] in the IntegrityDecision definition; also update any references or type annotations that construct or consume IntegrityDecision (e.g., evaluate_listing_integrity return hints) to use the new Literal type to preserve type-safety and IDE autocomplete.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/listing_integrity_gate.py around lines 246 - 265, Replace the hardcoded default in _get_support_fields with the ecommerce_listing entry from LISTING_INTEGRITY_SUPPORT_FIELDS (use LISTING_INTEGRITY_SUPPORT_FIELDS.get("ecommerce_listing") and pass through _ensure_frozenset) so the fallback always reflects the configured values; additionally, when LISTING_INTEGRITY_SUPPORT_FIELDS is not a dict, either log a warning (using the module logger) or raise a ValueError indicating the configuration is invalid before returning a fallback, and keep references to _get_support_fields, LISTING_INTEGRITY_SUPPORT_FIELDS, and _ensure_frozenset to locate the change.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/listing_integrity_gate.py around lines 214 - 222, The local import of listing_detail_like_path inside _has_detail_identity_marker suggests it may be unnecessary; if there is no circular dependency, move the import to the module top with the other imports and remove the in-function import; update the module-level imports to include "from app.services.extract.detail_identity import listing_detail_like_path" and leave _has_detail_identity_marker to simply call listing_detail_like_path(url, is_job=is_job).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/listing_integrity_gate.py around lines 36 - 120, The function evaluate_listing_integrity currently falls through and returns a product_grid for an empty records list; add an early guard at the top of evaluate_listing_integrity that detects an empty records (if not records or record_count == 0) and immediately returns IntegrityDecision(outcome="promo_only_cluster", reason="no_records", metrics=metrics) where metrics is populated with record_count=0 and zeros for cohort_homogeneity_ratio, dominant_signature_count, sibling_category_count, support_signal_count, and detail_marker_count (or compute them as zeros) so the function never treats an empty candidate set as a product_grid.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/listing_extractor.py around lines 990 - 1008, Replace the fragile hasattr check in _attach_gate_decision_to_artifacts with a type-based validation: import or reference IntegrityDecision and use isinstance(decision, IntegrityDecision) to decide whether to read decision.outcome/reason/metrics; if the object is not an IntegrityDecision, log the actual type (using the module logger) and set artifacts["listing_integrity"] to the "unknown"/"invalid_decision" payload as before so malformed runtime values are observable and not silently masked.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/listing_extractor.py around lines 1021 - 1031, The broad except Exception around the call to evaluate_listing_integrity should be narrowed and should capture traceback on failures: replace the generic except with either specific expected exceptions (e.g., except (ValueError, ListingIntegrityError):) or catch Exception but immediately re-raise unexpected programming errors after logging; also change logger.warning to logger.error and pass exc_info=True to record the full traceback for evaluate_listing_integrity(page_url=page_url, surface=surface, records=records) so debugging is possible while still returning decision = None for expected integrity failures.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/pipeline/extraction_loop.py around lines 860 - 864, The code redundantly calls gate_payload.get("metrics") twice when constructing gate_decision; retrieve metrics once into a local variable (e.g., metrics = gate_payload.get("metrics")) and then pass metrics if it's a dict else {} into _ListingIntegritySnapshot (keeping outcome and reason logic unchanged). Update the gate_decision creation to use that single lookup and ensure the variable name (metrics) is used in the metrics= argument to avoid duplicate calls.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/pipeline/extraction_loop.py at line 961, The increment of context.listing_integrity_retry_count assumes the attribute exists; ensure URLProcessingContext (or _URLProcessingContext) defines listing_integrity_retry_count as an int default (e.g., listing_integrity_retry_count = 0) so the += operation never raises AttributeError, or alternatively make the increment defensive in extraction_loop.py by reading the current value with getattr(context, "listing_integrity_retry_count", 0) and writing back with setattr(context, "listing_integrity_retry_count", value + 1); reference the symbols listing_integrity_retry_count and URLProcessingContext/_URLProcessingContext when applying the fix.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/pipeline/listing_escalation_decision.py around lines 97 - 105, Move the settings.listing_integrity_escalation_enabled check up into the early skip rules so it runs before any expensive computations (e.g., before effective_blocked()) and is not split between other policy checks; specifically, in listing_escalation_decision.py evaluate if not settings.listing_integrity_escalation_enabled then return _skip("escalation_disabled") immediately after the surface check (or as the first policy-level check), and keep the challenge_state and host_hard_block checks grouped together afterward to preserve logical flow.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/pipeline/run_progress.py around lines 156 - 186, The _merge_run_acquisition_metrics function repeats the same “build counter dict + increment” logic for methods, platform_families, failure_reasons (and traversal_modes_used elsewhere); extract a small helper (e.g. _increment_category_count) that accepts the existing mapping (current), the dict key name (like "methods"), and the category_value (like the derived method/platform_family/failure_reason string) and returns the updated counter dict using mapping_or_empty and as_int; then replace each repeated block in _merge_run_acquisition_metrics with calls to this helper to reduce boilerplate and ensure identical behavior.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/pipeline/run_progress.py around lines 308 - 312, The running-average math reconstructs total via current.get("score") * scored_urls which can cause FP drift; change the summary to persist a "score_total" and read that instead of recomputing: use current_score_total = _as_float(current.get("score_total", 0.0)), compute next_score_total = current_score_total + _as_float(url_quality.get("score", 0.0)), next_scored_urls = as_int(current.get("scored_urls", 0)) + 1, then compute average_score = round(next_score_total / next_scored_urls, 4) and write both "score_total" and the derived "score" back into the summary (update places that read/write average_score/current_score_total to use the new "score_total" key).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/pipeline/run_progress.py around lines 56 - 61, The current loop in run_progress.py that computes completed_count iterates from index 0 and breaks on the first falsy verdict, which undercounts when verdicts are recorded out of order; update the logic in the block that reads raw_verdicts (the completed_count computation) to count all non-empty entries (e.g., sum over truthy entries) rather than counting consecutive entries from the start, and ensure this aligns with how record_url_result extends/assigns verdicts by arbitrary idx.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/pipeline/run_progress.py around lines 78 - 99, record_url_result currently always increments completed_count, persisted_record_count, and verdict_counts causing double-counting if the same idx is recorded more than once; change the logic to first detect whether this idx was previously recorded via existing = (idx < len(self.url_verdicts) and self.url_verdicts[idx] != ""); if not existing then (1) increment self.completed_count and add to self.persisted_record_count, (2) set self.url_verdicts[idx] = verdict (extending the list if needed), (3) increment self.verdict_counts[verdict], and (4) merge acquisition_summary and quality_summary; if existing and the previous verdict differs, decrement self.verdict_counts[previous_verdict] and increment self.verdict_counts[verdict] and update self.url_verdicts[idx] but do NOT change completed_count or persisted_record_count or re-merge the summaries; use the function name record_url_result and attributes url_verdicts, completed_count, persisted_record_count, verdict_counts, acquisition_summary, and quality_summary to locate where to apply the fix.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_browser_expansion_runtime.py at line 1320, The current assertion uses result.browser_diagnostics["phase_timings_ms"]["readiness_wait"] >= 0 which is too permissive; update the assertion to require a positive wait time (use > 0) to ensure the test verifies actual readiness waiting occurred, i.e., change the check on readiness_wait in test_browser_expansion_runtime.py to assert readiness_wait > 0 (unless you intentionally need to match the existing pattern on nearby assertions, in which case add a comment explaining that consistency).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_crawl_engine.py around lines 1379 - 1383, The test is using monkeypatch.setattr on extraction_runtime.crawler_runtime_settings which is a dict-like value; replace that with monkeypatch.setitem targeting extraction_runtime.crawler_runtime_settings and the key "listing_cohort_homogeneity_min_ratio" (i.e., monkeypatch.setitem(extraction_runtime.crawler_runtime_settings, "listing_cohort_homogeneity_min_ratio", 1.01)), or if crawler_runtime_settings is actually an object with attributes, use monkeypatch.setattr on extraction_runtime.crawler_runtime_settings and the attribute name; update the call in the test to the appropriate monkeypatch helper so the value is correctly set.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_crawl_service.py around lines 894 - 927, The test creates an asyncio.Task via the fake _fake_track (replacing local_dispatch_module.track_local_run_task) but never cleans it up; update the test_local_dispatch_commits_task_id_before_launching_task test so the fake _fake_track returns the created task but also capture that task (e.g., in a local variable or list) and after awaiting crawl_service.dispatch_run(db_session, run) cancel the task and await it (handle CancelledError) to ensure no lingering tasks remain; reference the _fake_track replacement of track_local_run_task and the dispatch_run call when adding the cleanup.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_extraction_runtime_listing_integrity.py around lines 48 - 68, The test suite lacks coverage for the edge case where artifacts["listing_integrity"] is non-dict while browser_diagnostics already contains a valid listing_integrity; add a test that calls _propagate_listing_integrity_to_diagnostics with browser_diagnostics having a dict decision and artifacts having a non-dict value and assert that browser_diagnostics["listing_integrity"] remains unchanged (i.e., the existing decision is not overwritten or mutated); reference the function _propagate_listing_integrity_to_diagnostics and the test module test_extraction_runtime_listing_integrity.py when adding the new test.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_extraction_runtime_listing_integrity.py around lines 55 - 68, Add a unit test for the nested-retry scenario around _propagate_listing_integrity_to_diagnostics: create first_decision, second_decision, third_decision; seed browser_diagnostics["listing_integrity"] as {**second_decision, "previous": first_decision}, set artifacts["listing_integrity"]=third_decision, call _propagate_listing_integrity_to_diagnostics(artifacts, browser_diagnostics), then assert the top-level outcome/reason match third_decision and that listing_integrity["previous"] equals second_decision (i.e., previous is overwritten with the immediate prior decision); if the implementation currently doesn't behave this way, update _propagate_listing_integrity_to_diagnostics to shift the existing current into previous rather than preserving a nested previous chain.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_extraction_runtime_listing_integrity.py around lines 85 - 101, The test currently only checks that a "previous" key wasn't added to artifacts["listing_integrity"]; to fully verify immutability, make a deep copy of the artifacts dict (using copy.deepcopy) before calling _propagate_listing_integrity_to_diagnostics and then assert the copied object equals the original artifacts after the call (in addition to the existing assertions) so the entire structure is unchanged.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_listing_escalation_decision.py around lines 195 - 198, Update the test_job_listing_surface_triggers_retry test to assert the missing keys for consistency: add assertions that result["prior_tier"] equals the expected prior tier value and that result["reason"] equals the expected reason string (match the values used in other happy-path tests), keeping the existing checks for result["should_retry"] and result["next_tier"] so test_job_listing_surface_triggers_retry validates prior_tier and reason alongside those fields.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_listing_integrity_gate.py around lines 216 - 223, The test's records list in test_listing_integrity_gate currently creates 5 identical job dicts which prevents the integrity gate from exercising URL/cohort diversity; update the comprehension that builds records so each entry has a unique URL (e.g., incorporate the loop index into the URL or job id) while keeping other fields the same—modify the block that assigns to records in test_listing_integrity_gate to generate distinct URLs per iteration.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_listing_integrity_gate.py around lines 198 - 209, The test test_decision_is_frozen_dataclass currently catches Exception too broadly; update it to catch the specific exception raised when mutating a frozen dataclass (use dataclasses.FrozenInstanceError or AttributeError) instead of Exception, and add the necessary import (from dataclasses import FrozenInstanceError or import AttributeError is builtin) at the top of the test file so the mutation assertion for IntegrityDecision returned by evaluate_listing_integrity clearly verifies immutability without masking other errors.

These are comments left during a code review. Please review all issues and provide fixes.

1. logic error: The compound size regex is overly broad and can misclassify text.
   Path: backend/app/services/config/extraction_rules.py
   Lines: 1377-1377

2. possible bug: The slash-separated matcher does not cover all extended XL combinations.
   Path: backend/app/services/config/extraction_rules.py
   Lines: 1380-1380

3. logic error: Remapping generic axes into core axes can create conflicting parent and variant state.
   Path: backend/app/services/extract/variant_record_normalization.py
   Lines: 221-221

4. possible bug: The review notes file contains no runtime code to patch.
   Path: coderabbit.md
   Lines: 1-1

5. logic error: Non-job surfaces are routed to the wrong readiness selector group.
   Path: backend/app/services/acquisition/browser_page_flow.py
   Lines: 827-827

Validate the correctness of each issue sequentially. For each issue that is correct, implement a fix. Please make the fixes concise and address all issues comprehensively and don't impact anything else.

Fix the following issues. The issues can be from different files or can overlap on same lines in one file.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/core/dependencies.py around lines 83 - 94, The shutdown_run_dispatchers function can exit early if a dispatcher's cleanup raises; wrap the call to each dispatcher's shutdown/close (the local variable cleanup inside shutdown_run_dispatchers iterating over _run_dispatchers) in a try/except that catches Exception, logs a warning including the dispatcher's type/name and the exception, and continues to the next dispatcher; ensure awaiting awaitable results remains inside the try so exceptions from async cleanup are also caught, and always clear _run_dispatchers after the loop to guarantee cache cleanup.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/core/dependencies.py around lines 73 - 80, The get_run_dispatcher function performs a non-thread-safe check-then-create on the shared _run_dispatchers dict; introduce a module-level threading.Lock (e.g., _dispatcher_lock) and use it to guard the lookup-and-create sequence so only one thread can create and store a dispatcher at a time; specifically, add _dispatcher_lock = threading.Lock() near the _run_dispatchers declaration and wrap the logic inside get_run_dispatcher (the check of _run_dispatchers, instantiation of CeleryRunDispatcher or LocalRunDispatcher, and assignment back into _run_dispatchers) in a with _dispatcher_lock: block to prevent duplicate creations and resource leaks.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/main.py around lines 50 - 52, The logging is being configured at import time via configure_logging() next to logger = logging.getLogger("app"); move that call out of module-level scope and instead invoke configure_logging() during the application's startup/lifespan phase (e.g., inside your ASGI/FastAPI lifespan or startup handler) so imports don't trigger global side effects; keep logger = logging.getLogger("app") at module level but ensure configure_logging() is executed once during the lifespan startup and (if needed) a matching shutdown/cleanup in the lifespan teardown.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/_batch_runtime.py around lines 102 - 103, Cache diagnostics.get("browser_attempted") to avoid duplicate lookups: assign it to a local variable (e.g., browser_attempted = diagnostics.get("browser_attempted")) and then check that variable in the if and convert to bool when setting metrics["browser_attempted"]; update the code around diagnostics and metrics in _batch_runtime.py accordingly.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/_batch_runtime.py at line 254, The unawaited background task prewarm_task created from _prewarm_browser_pool inside process_run can be destroyed pending on early returns; ensure proper cleanup by awaiting prewarm_task before any early return or, on cancellation paths (pause/kill/terminal), cancel prewarm_task and await it (handle asyncio.CancelledError). Locate the asyncio.create_task(...) call that assigns prewarm_task and add logic in process_run to either await it before returning normally or call prewarm_task.cancel() followed by awaiting it in exception/early-exit handlers so the task is not left pending.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/acquisition/browser_page_flow.py at line 74, The loop unnecessarily copies the sequence by calling list() when iterating over CARD_SELECTORS.get(group); update the iteration in browser_page_flow.py to iterate directly over the fallback iterable instead of making a copy — replace the line using list(CARD_SELECTORS.get(group) or []) with a direct iteration like for selector in CARD_SELECTORS.get(group) or []: so the loop still handles None but avoids the unneeded allocation.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/adapters/amazon.py around lines 471 - 496, The permutation loop in _best_twister_dimension_order can blow up for many dimensions; add a cap (e.g., MAX_DIM_PERMUTATION = 5) and short-circuit when len(dim_order) exceeds it: skip generating all permutations and return the initial dim_order or a heuristic ordering (e.g., sorted by frequency using _score_twister_dimension_order or by raw_dims metadata). Implement the cap check at the start of _best_twister_dimension_order (before calling permutations) and ensure behavior is deterministic and logged or documented so callers know a full search was not performed.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/config/extraction_rules.py around lines 1330 - 1341, The new tokens ("shipping", "sameday", "same-day", "shipsintime", "shipstime", "swatch", "dyo-", "/static-dyo") added to the image-filter list in extraction_rules.py may be too broad (especially "swatch" and "shipping"); update the matching logic for that token list to use stricter rules (e.g., word-boundary or filename-prefix/suffix regexes rather than naive substring matching) and add a small validation step that samples production URLs containing these tokens to ensure we don't over-filter legitimate product images; locate the token array in extraction_rules.py and replace substring checks with targeted regex matches and run spot-checks on real URLs to confirm behaviour.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/config/variant_policy.py at line 107, PUBLIC_VARIANT_AXIS_FIELDS now includes "firmness" and "thickness" but VARIANT_AXIS_CANONICAL_MAPPING has no entries for those names; add canonical mapping entries inside the VARIANT_AXIS_CANONICAL_MAPPING dict (near its definition) to normalize expected aliases (e.g., a frozenset of alias strings mapping to the canonical "firmness" and a frozenset mapping to "thickness"), using the existing pattern for other mappings so downstream normalization code (which references VARIANT_AXIS_CANONICAL_MAPPING and PUBLIC_VARIANT_AXIS_FIELDS) will map synonyms like "firm"/"soft" or "thick"/"thin" to the canonical keys.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/fetch/fetch_context.py around lines 1084 - 1092, The function _retryable_status_for_http_fetch currently rebuilds and reparses crawler_runtime_settings.http_retry_status_codes on every call; change it to parse once and cache the resulting set of ints (e.g. a module-level or class-level _cached_http_retry_status_codes) and have _retryable_status_for_http_fetch consult that cache instead of rebuilding it each time; ensure you still log warnings for invalid entries during parsing and provide a clear mechanism to invalidate/refresh the cache when crawler_runtime_settings.http_retry_status_codes changes (e.g. a setter or refresh function that re-parses and updates the cached set).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/fetch/fetch_context.py around lines 920 - 922, The branching around passing proxy to the selected fetcher is unnecessary if both fetch implementations accept proxy=None; update the call site in fetch_context where fetcher is invoked (the fetcher variable that may point to _http_fetch or _curl_fetch) to always pass proxy as a keyword argument (e.g., call fetcher(context.url, http_timeout, proxy=proxy)), and before changing remove the conditional and verify both _http_fetch and _curl_fetch signatures accept proxy=None so no runtime errors occur.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/fetch/fetch_context.py around lines 894 - 895, The current sentinels _retry_sentinel and _http_attempt_failed are plain object() instances which degrade static typing (e.g. return annotations like PageFetchResult | object); replace them with tiny typed sentinel classes (e.g., class _RetrySentinel: __slots__ = (); class _HttpAttemptFailed: __slots__ = ()) and instantiate as Final constants (_retry_sentinel: Final = _RetrySentinel(), _http_attempt_failed: Final = _HttpAttemptFailed()); update any function return annotations such as _attempt_http_fetch to use the specific sentinel types (PageFetchResult | _HttpAttemptFailed) so the type checker can distinguish sentinel values.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/fetch/fetch_context.py around lines 1095 - 1096, The function _sleep_before_retry is dead code and should be removed: delete the async def _sleep_before_retry(attempt: int) wrapper and any associated unused imports; verify there are no remaining references to _sleep_before_retry and keep using _sleep_retry_delay(attempt) where the actual sleep is performed (e.g., places currently calling _sleep_retry_delay directly).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/fetch/fetch_context.py around lines 80 - 87, The on_event parameter in _emit_fetch_event is currently typed as object | None but should be an async callable; update its annotation to something like Optional[Callable[[str, str], Awaitable[None]]] (import Optional, Callable, Awaitable from typing) and adjust the type hint on the function signature accordingly so static checkers/IDEs know on_event is an async function accepting (level: str, message: str) and returning Awaitable[None]; keep the same runtime behavior (check for None, await on_event(level, message), catch Exception).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/shared/field_coerce.py at line 605, Update the regex used when assigning to the variable cleaned so it tolerates no-space and minor separators between "size" and "chart"; replace r"\s*\(size\s+chart\)" with a more flexible pattern such as r"\s*\(size\s*[_\s-]?chart\)" (or at minimum r"\s*\(size\s*chart\)") in the same assignment to ensure variants like "(sizechart)", "(size_chart)", "(size-chart)" and "(size chart)" are removed.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_browser_expansion_runtime.py around lines 125 - 139, The test test_generic_card_selectors_use_all_groups_for_unknown_listing_surface currently asserts list equality which makes it order-dependent; update the assertion to compare sets (e.g., assert set(selectors) == {".product-card", ".job-card"}) to make it order-independent, or if _generic_card_selectors_for_surface guarantees a deterministic order, add a comment in the test documenting that ordering expectation and keep the list equality; reference the test function name and browser_page_flow._generic_card_selectors_for_surface when making the change.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_crawl_service.py around lines 710 - 733, The test test_pause_run_preserves_live_local_task_bookkeeping can leak state if an assertion fails before cleanup; modify the test to perform the removal from local_dispatch_module._local_run_tasks and cancel/wait the local_task in a finally block (or use try/finally around the assertions) so cleanup always runs; locate the setup using local_task = asyncio.create_task(...) and the assignment local_dispatch_module._local_run_tasks[run.id] = local_task and move the pop/cancel/await logic into the finally to guarantee removal and cancellation even on failure.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_crawl_service.py around lines 757 - 817, The test test_recover_stale_local_runs_clears_task_entries_and_task_ids can leak task entries into local_dispatch_module._local_run_tasks if an assertion fails; wrap the part that creates and assigns finished_pending/finished_running to local_dispatch_module._local_run_tasks and the assertions in a try/finally and in the finally ensure you remove any keys for pending_run.id and running_run.id from local_dispatch_module._local_run_tasks and cancel awaited tasks (finished_pending, finished_running) if still pending so no state persists across tests; reference the local variables pending_run, running_run, finished_pending, finished_running and the module symbol local_dispatch_module._local_run_tasks when adding the cleanup.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_crawl_service.py around lines 735 - 755, The test test_kill_run_clears_local_task_bookkeeping should defensively clean up the created local task and its entry in local_dispatch_module._local_run_tasks in a finally block to avoid leaks if assertions fail; wrap the setup, call to crawl_service.kill_run, and assertions in try/finally and in the finally ensure that if run.id still exists in local_dispatch_module._local_run_tasks it is popped and the local_task is cancelled (and awaited/cancelled appropriately) so the task is removed and not left running between tests.