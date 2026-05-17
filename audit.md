Post-Refactor Assessment — CrawlerAI
What Was Completed ✅
The refactor commit "Refactor listing extraction and LLM layout" shows meaningful structural progress across two areas.

LLM consolidation — fully done. All 12 flat llm_*.py files have been moved into services/llm/ as a proper bounded module with an __init__.py . Files renamed cleanly: budget.py, cache.py, circuit_breaker.py, config_service.py, cost_logging.py, errors.py, payloads.py, prompt_rendering.py, provider_client.py, runtime.py, tasks.py, types.py. This was the Phase 3.3 target and it is complete.

extract/ subdirectory — substantially populated. The extract/ package now has 30+ focused files : listing signal modules (listing_card_fragments.py, listing_visual.py, listing_integrity_gate.py, listing_candidate_ranking.py), structured handling (structured_listing_handler.py, network_listing_mapper.py), detail pipeline split into discrete responsibilities (detail_dom_extractor.py, detail_price_extractor.py, detail_identity.py, detail_materializer.py, detail_record_finalizer.py, detail_text_sanitizer.py), variant logic (variant_record_normalization.py, variant_structural_pruning.py, variant_dom_cues.py, variant_group_validator.py), and a contracts.py interface file. The signal extraction decomposition matches Phase 1.1 intent. field_candidates/ subdirectory now exists as a nested package — Phase 2.3 split appears partially done.

New infrastructure visible. crawl/, dispatch/, dom/, js_state/, pipeline/, fetch/, normalizers/, publish/, review/, storage/, data_enrichment/, product_intelligence/ directories are all confirmed present , representing broad domain boundary creation from Phase 4.1.

What Still Needs Fixing 🔴🟡
🔴 listing_extractor.py — Still a God Object at 42,352 bytes
This is the most critical unresolved issue. The file is 42KB at HEAD — it has actually grown from the pre-refactor 48KB, meaning only some logic was extracted but the core monolith still stands at services/listing_extractor.py. The extract/ submodules (listing_card_fragments, listing_visual, etc.) were created as new additions or forward-extracted copies, but the original file was not hollowed out. This is a Copy-Paste anti-pattern risk — if the logic in extract/listing_card_fragments.py duplicates what's still in listing_extractor.py, you now have two sources of truth.

Immediate action required: Verify that listing_extractor.py now acts as a thin orchestrator importing from extract/. If it still contains the signal extraction implementations inline, the split is incomplete and the new extract/ files are dead code or duplicates.

🔴 extraction_runtime.py — Still 30,074 bytes, Still at Services Root
Down from 38KB before refactor, so some reduction happened, but at 30KB it is still far above the 200-line orchestrator target . The mega-dispatcher pattern is not resolved. It remains at the services/ root rather than inside services/pipeline/ or services/extract/. The pipeline/ directory exists but extraction_runtime.py was not moved into it.

🔴 shared_variant_logic.py — New God Object at 58,915 bytes
This is a new problem introduced by the refactor. At nearly 59KB, extract/shared_variant_logic.py is the largest file in the entire codebase now . The word "shared" in a filename is a classic Logical Cohesion red flag — it means "stuff we didn't know where else to put." This file must be broken down by its actual variant logic concerns (normalization, structural pruning, DOM cues, value guards) — several of which already have their own separate files in extract/. This suggests shared_variant_logic.py is either the undecomposed remainder or a dump file.

🔴 detail_dom_extractor.py + detail_materializer.py + detail_record_finalizer.py + detail_identity.py — Four Files Still 35–52KB Each
All four detail-domain files are 35K–52K bytes each :

detail_dom_extractor.py — 51,982 B

detail_materializer.py — 50,379 B

detail_record_finalizer.py — 47,452 B

detail_identity.py — 35,566 B

detail_price_extractor.py — 35,590 B

detail_text_sanitizer.py — 28,438 B

These are the new God Objects created during the refactor. The file names are more specific than the old monolith, but the sizes prove each still contains multiple responsibilities. A detail_materializer.py at 50KB is not a single-responsibility module.

🟡 dashboard_service.py — Unchanged at 17,336 bytes
Still sits at the services/ root, identical size to before . This file was not touched in the refactor. At 17KB it likely mixes query assembly, aggregation logic, and data formatting — three distinct concerns that belong in services/crawl/ or a services/reporting/ boundary.

🟡 selectors_runtime.py — Unchanged at 26,739 bytes
Also untouched, still at the services root . At 26KB this is a strong candidate for the next round of splitting, particularly if it handles both selector execution and selector scoring/fallback logic.

🟡 structured_sources.py — Unchanged at 20,448 bytes
Untouched. Should either be absorbed into extract/structured_listing_handler.py or confirmed as a separate responsibility .

🟡 extraction_context.py — Still at Services Root at 11,404 bytes
This file belongs inside services/extract/ or services/pipeline/ as it is the context type that extraction stages consume. Leaving it at the root means the boundary between the extract/ module and the root is still porous .

🟡 network_payload_mapper.py — Still at Root, 21,765 bytes
Not moved into extract/ despite extract/network_listing_mapper.py being created. There are now two files handling network-to-record mapping at different paths — potential duplication .

Confirmed Progress vs. Remaining Work
Area	Status	Action
Area	Status	Action
LLM module consolidation	✅ Complete	Done
extract/ subpackage creation	✅ Structural shell done	Content audit needed
listing_extractor.py reduction	🔴 Incomplete (42KB)	Must hollow out to orchestrator
extraction_runtime.py reduction	🔴 Incomplete (30KB)	Move into pipeline/, strip stages
shared_variant_logic.py	🔴 New God Object (59KB)	Split immediately
Detail extract/ files	🔴 4 new God Objects (35–52KB each)	Each needs a second-pass split
dashboard_service.py	🟡 Untouched	Move to crawl/ or reporting/
selectors_runtime.py	🟡 Untouched	Split by selector execution vs. scoring
extraction_context.py	🟡 Misplaced	Move into extract/
network_payload_mapper.py vs network_listing_mapper.py	🟡 Possible duplication	Audit and consolidate
The structural skeleton is now in place — the bounded modules (llm/, extract/, crawl/, pipeline/) exist and represent the correct intended shape. The next phase of work is not creating new files but hollowing out the remaining monoliths and resolving the new oversized files that emerged from the first pass.