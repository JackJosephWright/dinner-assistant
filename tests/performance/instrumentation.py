"""
Performance instrumentation for tracking metrics during tests.

This module provides tools to monitor:
- LLM API call counts and timing
- Database query counts and timing
- HTTP request/response timing
- Memory usage
"""

import time
import functools
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMCallMetric:
    """Metrics for a single LLM API call."""
    timestamp: datetime
    model: str
    max_tokens: int
    duration: float
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached: bool = False


@dataclass
class DatabaseQueryMetric:
    """Metrics for a single database query."""
    timestamp: datetime
    query: str
    duration: float
    rows_returned: Optional[int] = None


@dataclass
class HTTPRequestMetric:
    """Metrics for an HTTP request."""
    timestamp: datetime
    method: str
    path: str
    status_code: int
    duration: float


@dataclass
class PerformanceMetrics:
    """Collection of all performance metrics."""
    llm_calls: List[LLMCallMetric] = field(default_factory=list)
    db_queries: List[DatabaseQueryMetric] = field(default_factory=list)
    http_requests: List[HTTPRequestMetric] = field(default_factory=list)

    def reset(self):
        """Clear all metrics."""
        self.llm_calls.clear()
        self.db_queries.clear()
        self.http_requests.clear()

    def summary(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        llm_total_time = sum(c.duration for c in self.llm_calls)
        llm_count = len(self.llm_calls)
        llm_cached = sum(1 for c in self.llm_calls if c.cached)

        db_total_time = sum(q.duration for q in self.db_queries)
        db_count = len(self.db_queries)

        http_total_time = sum(r.duration for r in self.http_requests)

        return {
            "llm_calls": {
                "count": llm_count,
                "total_duration": llm_total_time,
                "avg_duration": llm_total_time / llm_count if llm_count else 0,
                "cached_calls": llm_cached,
                "cache_hit_rate": llm_cached / llm_count if llm_count else 0,
            },
            "database": {
                "query_count": db_count,
                "total_duration": db_total_time,
                "avg_duration": db_total_time / db_count if db_count else 0,
            },
            "http": {
                "request_count": len(self.http_requests),
                "total_duration": http_total_time,
            }
        }

    def print_report(self, title: str = "Performance Report"):
        """Print a formatted performance report."""
        print(f"\n{'='*70}")
        print(f"{title:^70}")
        print(f"{'='*70}\n")

        summary = self.summary()

        # LLM Stats
        print("🤖 LLM API Calls:")
        print(f"  Count: {summary['llm_calls']['count']}")
        print(f"  Total time: {summary['llm_calls']['total_duration']:.2f}s")
        if summary['llm_calls']['count'] > 0:
            print(f"  Average time: {summary['llm_calls']['avg_duration']:.2f}s")
            print(f"  Cache hit rate: {summary['llm_calls']['cache_hit_rate']*100:.1f}%")

        # Database Stats
        print(f"\n💾 Database Queries:")
        print(f"  Count: {summary['database']['query_count']}")
        print(f"  Total time: {summary['database']['total_duration']:.2f}s")
        if summary['database']['query_count'] > 0:
            print(f"  Average time: {summary['database']['avg_duration']:.3f}s")

        # HTTP Stats
        print(f"\n🌐 HTTP Requests:")
        print(f"  Count: {summary['http']['request_count']}")
        print(f"  Total time: {summary['http']['total_duration']:.2f}s")

        # Detailed breakdown
        if self.llm_calls:
            print(f"\n📊 LLM Call Breakdown:")
            for i, call in enumerate(self.llm_calls, 1):
                cached_str = " [CACHED]" if call.cached else ""
                print(f"  {i}. {call.model} - {call.duration:.2f}s{cached_str}")

        print(f"\n{'='*70}\n")


class PerformanceMonitor:
    """Thread-safe performance monitoring context manager."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.metrics = PerformanceMetrics()
        return cls._instance

    def track_llm_call(self, model: str, max_tokens: int, duration: float, **kwargs):
        """Record an LLM API call."""
        metric = LLMCallMetric(
            timestamp=datetime.now(),
            model=model,
            max_tokens=max_tokens,
            duration=duration,
            **kwargs
        )
        self.metrics.llm_calls.append(metric)

    def track_db_query(self, query: str, duration: float, rows: Optional[int] = None):
        """Record a database query."""
        metric = DatabaseQueryMetric(
            timestamp=datetime.now(),
            query=query,
            duration=duration,
            rows_returned=rows
        )
        self.metrics.db_queries.append(metric)

    def track_http_request(self, method: str, path: str, status: int, duration: float):
        """Record an HTTP request."""
        metric = HTTPRequestMetric(
            timestamp=datetime.now(),
            method=method,
            path=path,
            status_code=status,
            duration=duration
        )
        self.metrics.http_requests.append(metric)

    def reset(self):
        """Reset all metrics."""
        self.metrics.reset()

    def get_metrics(self) -> PerformanceMetrics:
        """Get current metrics."""
        return self.metrics


def timeit(func: Callable) -> Callable:
    """Decorator to time function execution."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        logger.info(f"{func.__name__} took {duration:.2f}s")
        return result
    return wrapper


def track_llm_calls(anthropic_client):
    """
    Wrap an Anthropic client to track all API calls.

    Usage:
        from anthropic import Anthropic
        client = Anthropic()
        tracked_client = track_llm_calls(client)
    """
    monitor = PerformanceMonitor()
    original_create = anthropic_client.messages.create

    @functools.wraps(original_create)
    def tracked_create(*args, **kwargs):
        start = time.time()
        result = original_create(*args, **kwargs)
        duration = time.time() - start

        model = kwargs.get('model', 'unknown')
        max_tokens = kwargs.get('max_tokens', 0)

        monitor.track_llm_call(
            model=model,
            max_tokens=max_tokens,
            duration=duration
        )

        return result

    anthropic_client.messages.create = tracked_create
    return anthropic_client


def track_database_queries(db_interface):
    """
    Wrap a DatabaseInterface to track all queries.

    Usage:
        db = DatabaseInterface()
        tracked_db = track_database_queries(db)
    """
    monitor = PerformanceMonitor()

    # Track search_recipes
    original_search = db_interface.search_recipes

    @functools.wraps(original_search)
    def tracked_search(*args, **kwargs):
        start = time.time()
        result = original_search(*args, **kwargs)
        duration = time.time() - start

        query = f"search_recipes(query={kwargs.get('query', '')})"
        monitor.track_db_query(query, duration, len(result))

        return result

    db_interface.search_recipes = tracked_search

    # Track get_recipe
    original_get = db_interface.get_recipe

    @functools.wraps(original_get)
    def tracked_get(*args, **kwargs):
        start = time.time()
        result = original_get(*args, **kwargs)
        duration = time.time() - start

        recipe_id = args[0] if args else kwargs.get('recipe_id', '')
        monitor.track_db_query(f"get_recipe({recipe_id})", duration, 1 if result else 0)

        return result

    db_interface.get_recipe = tracked_get

    return db_interface


class PerformanceTestContext:
    """Context manager for performance testing."""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.monitor = PerformanceMonitor()
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.monitor.reset()
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time

        print(f"\n⏱️  {self.test_name} completed in {duration:.2f}s")
        self.monitor.metrics.print_report(f"{self.test_name} - Performance Report")

        return False

    def get_metrics(self) -> PerformanceMetrics:
        """Get collected metrics."""
        return self.monitor.get_metrics()


def detect_duplicate_requests(metrics: PerformanceMetrics) -> List[Dict[str, Any]]:
    """
    Analyze metrics to detect duplicate/redundant requests.

    Returns list of duplicate patterns found.
    """
    duplicates = []

    # Check for duplicate HTTP requests
    http_paths = {}
    for req in metrics.http_requests:
        key = (req.method, req.path)
        if key not in http_paths:
            http_paths[key] = []
        http_paths[key].append(req)

    for (method, path), requests in http_paths.items():
        if len(requests) > 1:
            # Check if requests were made within short time window (< 1 second apart)
            for i in range(len(requests) - 1):
                time_diff = (requests[i+1].timestamp - requests[i].timestamp).total_seconds()
                if time_diff < 1.0:
                    duplicates.append({
                        "type": "http",
                        "pattern": f"{method} {path}",
                        "count": len([r for r in requests if (r.timestamp - requests[i].timestamp).total_seconds() < 1.0]),
                        "time_span": f"{time_diff:.2f}s"
                    })
                    break

    # Check for duplicate database queries
    db_queries = {}
    for query in metrics.db_queries:
        if query.query not in db_queries:
            db_queries[query.query] = []
        db_queries[query.query].append(query)

    for query_str, queries in db_queries.items():
        if len(queries) > 1:
            duplicates.append({
                "type": "database",
                "pattern": query_str,
                "count": len(queries)
            })

    return duplicates
