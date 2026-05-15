from typing import Dict


def validate_search_result(data: dict) -> bool:
    """Validate that search result dict has required 'url' field.

    Args:
        data: Dict representing a search result.

    Returns:
        True if valid, False otherwise.
    """
    if not isinstance(data, dict):
        return False
    return bool(data.get("url"))


def validate_scored_link(data: dict) -> bool:
    """Validate that scored link dict has required fields.

    Args:
        data: Dict representing a scored link.

    Returns:
        True if all required fields present, False otherwise.
    """
    if not isinstance(data, dict):
        return False
    required = {"url", "relevance_score", "should_scrape"}
    return all(key in data for key in required)


def validate_company(data: dict) -> bool:
    """Validate that company dict has required 'original_name' field.

    Args:
        data: Dict representing a company.

    Returns:
        True if valid, False otherwise.
    """
    if not isinstance(data, dict):
        return False
    return bool(data.get("original_name"))
