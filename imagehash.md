Investigate (do NOT implement) whether deterministic perceptual image hashing (pHash) adds real product-discovery matches for Belk beyond what the current brand+title+UPC confidence scoring already catches. This is a spike to decide go/no-go before any code lands.

Context you must read first:

belk-product-discovery-recall-plan.md
 — the just-completed UPC-first discovery work. Confidence is now driven by brand-exact + title-similarity (no SKU/style, GTIN floors when present), variant-spec guard, per-domain throttle removed. Image hashing was explicitly deferred as "Tier 4, investigation-only."
INVARIANTS.md
 Rule 1 (config in app/services/config/*), Rule 6 (acquisition observes, no fabricated fields), Rule 10 (no LLM unless gated). pHash must stay deterministic, no LLM.
Product Intelligence owners in 
CODEBASE_MAP.md
: backend/app/services/product_intelligence/{discovery,matching,service}.py.
Ground truth data already available:

DB run_id=3 has 4 Belk ecommerce_detail products with real image_url and (3 of 4) real UPC barcode. SerpAPI key is in .env (SERPAPI_API_KEY).
The candidate listings (macys, jcpenney, crateandbarrel, nfm, hsn, ebay, bestbuy, etc.) and their thumbnail URLs come back in discovery payloads.
What to actually do (a throwaway probe script, deleted after, like prior _pi_* probes):

For each run_id=3 source product, run live discovery, then for each candidate fetch both the Belk source image and the candidate listing image.
Compute pHash (use imagehash + Pillow) for source vs each candidate image; report Hamming distance.
Cross-reference against the current deterministic confidence score for the same candidate.
Answer these questions with real numbers, not theory:

For candidates that are TRUE matches, what pHash Hamming distance range do they fall in? Is there a clean threshold separating true from false?
Are there true matches that current brand+title scoring rates LOW/UNCERTAIN but pHash would rescue? (This is the only justification for adding pHash.) Quantify how many.
False-positive risk: do different-color/variant images of the same product, or different products with similar packaging, collide under pHash?
Practical blockers: how often is the candidate image missing, a thumbnail-only low-res, hotlink-blocked, or a sprite/placeholder? What fraction of candidates even have a usable image?
Cost/latency: extra image fetches per product.
Deliverable: a short findings report with a clear recommendation — pHash adds enough net-new true matches to justify implementation (and at what Hamming threshold), or it doesn't. If yes, sketch where it fits (a deterministic tier in matching.py/discovery.py, config thresholds in 
product_intelligence.py
) but write no production code in this session.

Constraints: deterministic only, no LLM, no Google Lens/Vision API (paid), use local pHash. Keep SerpAPI dispatch untouched. Clean up any probe scripts and temp images before finishing.