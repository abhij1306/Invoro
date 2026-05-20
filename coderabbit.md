Fix the following issues. The issues can be from different files or can overlap on same lines in one file.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/monitor_service.py at line 160, The call to session.delete(monitor) is being awaited although SQLAlchemy's AsyncSession.delete is synchronous; remove the leading await so you just call session.delete(monitor) to mark the ORM object for deletion, and ensure you perform the actual async DB operation later (e.g., await session.commit() or await session.flush()) where appropriate in the function that contains session.delete; update the code in monitor_service.py replacing "await session.delete(monitor)" with "session.delete(monitor)" and confirm subsequent commit/flush calls remain awaited.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/monitor_service.py around lines 158 - 161, Add an authorization check to delete_monitor by accepting a user parameter and ensuring ownership: change delete_monitor(session: AsyncSession, monitor_id: int) to delete_monitor(session: AsyncSession, monitor_id: int, user: User), call get_monitor(session, monitor_id=monitor_id, user=user) (mirroring delete_project's pattern) so get_monitor enforces the owner check, and only if it returns a monitor proceed to session.delete and commit; also update the API caller that invokes delete_monitor to pass the current user.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/orchestration_service.py at line 103, The call "await session.delete(project)" uses await on the synchronous SQLAlchemy method session.delete; remove the await and call session.delete(project) directly (while keeping any subsequent async operations like await session.commit() or await session.flush() as they are). Locate the usage of session.delete(project) in orchestration_service.py (where AsyncSession is used) and replace "await session.delete(project)" with "session.delete(project)" to avoid awaiting a non-async method.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_monitors_api_e2e.py around lines 370 - 381, The test doesn't assert that the head check was skipped on the second run; after calling service.check_due_jobs() the second time (and refreshing monitor) add an assertion that head_checks length is still 1 (or that head_checks == ["https://dummy-monitor.example/products/widget-prime"]) to confirm no new head check was performed; locate the relevant variables head_checks and dispatch_calls and the invocation service.check_due_jobs() in the test and add the assertion immediately after db_session.refresh(monitor) and before asserting dispatch_calls.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/app/monitors/page.tsx around lines 147 - 163, The ConfirmDialog is receiving a shared error state (`error`) used by both `updateMutation` and `deleteMutation`, causing stale update errors to show in the delete dialog; create an isolated delete error (e.g., `deleteError`) or use `deleteMutation.error` directly and pass that to `ConfirmDialog` instead of the shared `error`, clear `deleteError` when `deleteTargetId` is set/cleared (in the `onOpenChange`/open logic), and ensure `deleteMutation` sets/clears that separate error state on failure/success so the dialog only shows deletion-specific errors (references: ConfirmDialog, deleteTargetId, deleteMutation, updateMutation, error).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/components/crawl/log-terminal.tsx around lines 215 - 236, StageChip currently applies hardcoded Tailwind color classes for each stage; replace those with theme CSS custom properties so the chips follow the app theme. Update the conditional class entries in StageChip (function StageChip, referencing STAGE_CONFIG and the stage values 'acquisition','extraction','normalize','persistence','system') to use your theme tokens (e.g. var(--info), var(--accent), var(--warning), var(--success), var(--muted)) for background, border and text instead of bg-*/border-*/text-* classes—either by using inline style attributes that reference the CSS vars or Tailwind arbitrary values that point to the vars; ensure the same token mapping is used consistently for each stage so the chip colors adapt to theming.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/components/monitors/monitor-form.tsx around lines 216 - 229, The toggle buttons rendered in monitor-form.tsx (the button inside the map using key={field}) need ARIA state so screen readers know selection; update that button element to include role="checkbox" and aria-checked={isSelected} (keeping the existing onClick that calls toggleField(field) and the current className logic), ensuring the attributes reflect the isSelected boolean.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/components/monitors/monitor-form.tsx around lines 264 - 281, Wrap the priority selector container (where priorityOptions is mapped) with role="radiogroup" and add radio semantics to each option button: give each rendered button role="radio" and set aria-checked={priority === option.value} (and keep the onClick calling setPriority(option.value)); ensure the same unique key (option.value) stays on the Tooltip wrapper and preserve existing classes and type="button" so interaction doesn't change.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/components/monitors/monitor-header.tsx around lines 63 - 71, The remove() handler swallows rejection from onDelete(), leaving the dialog open with no feedback; add an error state in the component (e.g., const [deleteError, setDeleteError] = useState<string|undefined>()) and in remove() catch the error and call setDeleteError(error.message || String(error)) before finally clearing deletePending; add an error?: string prop to MonitorHeaderProps and pass error={deleteError} into the ConfirmDialog (or clear deleteError on successful delete/setDeleteOpen(false)); alternatively, if you prefer page-level handling, ensure the page uses deleteMutation.isError/deleteMutation.error and passes that error into MonitorHeader as the error prop and renders it in the ConfirmDialog.