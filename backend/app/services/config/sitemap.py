from __future__ import annotations

SITEMAP_DEFAULT_FILTER_KEYWORD = ""
SITEMAP_DEFAULT_MAX_URLS = 500
SITEMAP_FETCH_TIMEOUT_SECONDS = 15
SITEMAP_FETCH_RETRY_ATTEMPTS = 2
SITEMAP_FETCH_RETRY_DELAY_SECONDS = 0.5
SITEMAP_FETCH_RETRY_STATUS_CODES = (429, 502, 503, 504)
SITEMAP_USER_AGENT = "Mozilla/5.0 (compatible; CrawlwiseBot/1.0)"
# Path tokens that signal a page is not a category/listing/detail candidate
# (account, auth, support, legal, transactional flows, on-page search). These
# are surface-agnostic — we deliberately do NOT exclude /blog or /news here
# because content/article surfaces use the same homepage fallback path and
# blog/news hubs are valid listing targets for those surfaces.
SITEMAP_HOMEPAGE_FALLBACK_EXCLUDED_PATH_TOKENS = (
    "/account",
    "/auth",
    "/cart",
    "/checkout",
    "/contact",
    "/faq",
    "/faqs",
    "/help",
    "/login",
    "/logout",
    "/policies",
    "/policy",
    "/privacy",
    "/refund",
    "/register",
    "/returns",
    "/search",
    "/shipping",
    "/signin",
    "/signup",
    "/support",
    "/terms",
    "/wishlist",
)
SITEMAP_HOMEPAGE_FALLBACK_EXCLUDED_EXTENSIONS = (
    ".avif",
    ".css",
    ".gif",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".pdf",
    ".png",
    ".svg",
    ".txt",
    ".webp",
    ".xml",
    ".zip",
)
# Long department/category labels on retail navs ("Home & Kitchen Storage
# & Organization") routinely exceed 6 words. Use 10 to keep real categories
# while still rejecting obvious sentences/marketing copy.
SITEMAP_HOMEPAGE_FALLBACK_MAX_LINK_TEXT_WORDS = 10

# Threshold below which a sitemap result is considered "thin" — when the
# real sitemap returns fewer usable URLs than this and homepage fallback is
# allowed, also harvest the homepage and merge the two ranked sets. Keeps
# coverage on sites that publish a token sitemap (policy pages only).
SITEMAP_THIN_RESULT_THRESHOLD = 5
