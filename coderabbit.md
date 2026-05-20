These are comments left during a code review. Please review all issues and provide fixes.

1. logic error: Adding `monitor_jobs.last_known_values` as non-null JSONB state and dropping the default may leave empty state for existing jobs.
   Path: backend/alembic/versions/20260520_0006_agentic_delta_engine.py
   Lines: 20-20

2. logic error: Archived monitors are reported as 400 instead of 404, breaking the API's error contract.
   Path: backend/app/api/monitors.py
   Lines: 94-94

3. possible bug: Filtering the monitor list to non-archived records changes the endpoint's contract and hides existing data.
   Path: backend/app/api/monitors.py
   Lines: 70-70

4. possible bug: The public create endpoint changes the response and error contract.
   Path: backend/app/api/public_alerts.py
   Lines: 46-46

5. resource leak: A failed commit can leave the request session in a broken transaction state after authentication.
   Path: backend/app/core/public_auth.py
   Lines: 34-34

6. possible bug: Adding both alert routers does not currently create overlapping API surfaces.
   Path: backend/app/main.py
   Lines: 29-29

7. possible bug: The new webhook delivery table is defined but not integrated into the application flow.
   Path: backend/app/models/monitor.py
   Lines: 148-148

8. logic error: Failed initial polling leaves partially created alerts behind and counts against quota.
   Path: backend/app/services/alert_service.py
   Lines: 36-36

9. resource leak: The alert polling timestamp update is only an in-memory change.
   Path: backend/app/services/alert_service.py
   Lines: 186-186

Validate the correctness of each issue sequentially. For each issue that is correct, implement a fix. Please make the fixes concise and address all issues comprehensively and don't impact anything else.