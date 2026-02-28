from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "path", "status_code"],
)

EXTERNAL_API_COUNT = Counter(
    "external_api_requests_total",
    "Total number of external API requests",
    ["source", "status"],
)

EXTERNAL_API_DURATION = Histogram(
    "external_api_duration_seconds",
    "Duration of external API requests in seconds",
    ["source"],
)

CACHE_HITS = Counter("cache_hits_total", "Total number of cache hits")
CACHE_MISSES = Counter("cache_misses_total", "Total number of cache misses")
