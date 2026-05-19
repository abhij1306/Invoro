Fix the following issues. The issues can be from different files or can overlap on same lines in one file.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/alembic/versions/20260519_0005_orchestration.py around lines 66 - 75, Rename the composite index created by op.create_index from "ix_orchestration_workflows_project_created" to follow the same table-name pattern as the others (e.g., "ix_orchestration_workflow_runs_project_created") and keep it targeting the "orchestration_workflow_runs" table with columns ["project_id", "created_at"]; then update the corresponding index name in OrchestrationWorkflowRun.__table_args__ in orchestration.py to use the exact new name so the migration and ORM model stay consistent.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/api/orchestration.py around lines 163 - 168, The promote response is computing tracked_fields incorrectly by reading workflow.pipeline_config.get("fields") instead of using the service's _workflow_fields logic; update the code that builds OrchestrationPromoteResponse to use the same sources and rules as _workflow_fields (check intent_inputs.get("fields") first, then fallback to project.tracked_fields, merge in pipeline_config.get("custom_fields"), and apply the same defaults), or alternatively modify promote_workflow_to_monitor to return the resolved tracked_fields and use that value when constructing OrchestrationPromoteResponse so the response matches the service layer exactly.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/models/orchestration.py around lines 43 - 46, Remove the duplicate index on the status column: choose one approach—either delete the explicit Index("ix_orchestration_workflows_status", "status") from __table_args__ so the column-level status definition with index=True (in the Orchestration/OrchestrationWorkflowRun model) creates the index, or remove index=True from the status Column and keep the explicit Index if you need the specific name; ensure the remaining index name matches the migration (ix_orchestration_workflow_runs_status) and update __table_args__/Column accordingly.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/schemas/orchestration.py around lines 118 - 129, PriceComparisonRow currently declares price and was_price as Any; change them to a stricter union (e.g., decimal.Decimal | float | None) to preserve numeric precision and improve API docs. Update the annotations for the PriceComparisonRow model (fields price and was_price) to use Decimal|float|None (or Optional[Decimal|float]) and add the necessary import from decimal (Decimal) and typing if needed; ensure Pydantic will parse Decimal values (or use condecimal if you prefer) so validation and OpenAPI schema reflect numeric types instead of Any.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/orchestration_service.py around lines 345 - 361, The call int(workflow.user_id) can raise TypeError when workflow.user_id is None; update the create_crawl_run invocation to safely handle nullable user IDs by passing either int(workflow.user_id) when not None or None otherwise (e.g. user_arg = int(workflow.user_id) if workflow.user_id is not None else None) and use that user_arg in the create_crawl_run call before dispatch_run; apply the same null-safe conversion wherever you convert workflow.user_id to int (notably in the _dispatch_detail_step path) so the code never calls int(None).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_orchestration_service.py around lines 22 - 31, Update the test data to make the project name consistent with the competitor domain used in the test: change the payload name passed to orchestration_service.create_project (in test_orchestration_service.py where create_project is called and the local variable project is assigned) from "Ajio jeans watch" to something matching the competitor domain like "Example.com jeans watch" so the test name reflects the example.com workflow and URLs.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_orchestration_service.py around lines 18 - 21, Replace the simple stub fake_dispatch_run with a tracking AsyncMock and use monkeypatch.setattr(orchestration_service, "dispatch_run", mock_dispatch) so you can assert it was called; in the relevant tests (where fake_dispatch_run is set) add assertions on mock_dispatch.call_count and/or inspect mock_dispatch.call_args_list to verify expected runs were dispatched (e.g., that a listing run and subsequent detail run(s) with the correct run.url were invoked).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_orchestration_service.py around lines 48 - 50, Extract the repeated comprehension into a small async helper (e.g., get_workflow_steps_by_id) that calls orchestration_service.workflow_steps(db_session, workflow_id) and returns a dict keyed by step.step_id to eliminate duplication; add the helper (accepting db_session: AsyncSession and workflow_id: int and returning dict[str, WorkflowStep]) to the test module or a test utils module, then replace the four occurrences of `{step.step_id: step for step in await orchestration_service.workflow_steps(...)} ` with `steps = await get_workflow_steps_by_id(db_session, workflow.id)` (or equivalent) to centralize the logic.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_orchestration_service.py around lines 113 - 119, Enhance the test for orchestration_service.price_comparison by adding assertions that validate the full row structure and response metadata: after calling orchestration_service.price_comparison(db_session, workflow_id=workflow.id, user=test_user) and checking detail_run_id, assert comparison contains a "rows" list of expected length, and for comparison["rows"][0] assert presence and non-empty values for keys "title", "brand", "currency", "availability", "was_price" and "url" (and that "price" equals "1299"); also assert the set of field names matches expected fields to detect missing keys. Use the existing variables detail_run, comparison and orchestration_service.price_comparison to locate the assertions to add.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/app/projects/[id]/page.tsx around lines 226 - 229, The custom hook useStateMessage simply wraps React's useState and is redundant; replace all uses of useStateMessage with a direct const [message, setMessage] = useState('') in the component(s) that call it (keeping the same variable names message and setMessage), then remove the useStateMessage function definition; ensure imports include useState from React if not already present and update any references that expect the hook signature to work identically.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/app/projects/new/page.tsx around lines 176 - 189, The function domainListFromUrls currently aborts parsing and returns an empty array on the first URL parse error, discarding valid domains; change the catch behavior in domainListFromUrls so it does not return early—either (preferred) skip invalid URLs and continue processing remaining urls (optionally logging or collecting invalid entries) or, if you want to prevent creation on bad input, rethrow a descriptive error instead; update the catch block in domainListFromUrls to continue (or throw) and ensure duplicates are still deduplicated by the existing hostname logic.