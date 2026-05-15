class PipelineError(Exception):
    """Base exception for all pipeline errors."""
    pass


class RetryableError(PipelineError):
    """Error that can be retried (e.g., 429 rate limit)."""
    pass


class CriticalError(PipelineError):
    """Error that must stop the pipeline immediately (e.g., 402 credits exhausted)."""
    pass


class SkippableError(PipelineError):
    """Error that allows skipping this company and moving to next."""
    pass
