import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.errors import RetryableError, SkippableError


class GeminiQuickSearch:
    """Runs the step 2 Gemini quick search with Google Search grounding."""

    def __init__(self, db, logger, config=None):
        from src.config import default_config

        self.db = db
        self.logger = logger or logging.getLogger(__name__)
        self.config = config or default_config
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = None

        if not self.api_key:
            self._log_warning("GEMINI_API_KEY is missing; quick search disabled.")
            return

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                model_name=self.config.GEMINI_QUICK_MODEL,
                tools=[{"google_search": {}}],
            )
        except Exception as error:
            self._log_warning(f"Failed to initialize Gemini client: {error}")

    # -- Public API --

    def search(self, company_id: int) -> dict:
        """Search for Vietnamese company contact data using Gemini grounding.

        Args:
            company_id: The company ID to process.

        Returns:
            Dict containing normalized contact fields, grounding URLs, token usage,
            sufficiency status, and fallback reason.

        Raises:
            RetryableError: If Gemini keeps rate limiting after retries.
        """
        company = self.db.get_company(company_id)
        if not company:
            raise SkippableError(f"Company not found: {company_id}")

        if not self.model:
            return self._empty_response("Gemini client is not available.")

        quota_reason = self._quota_fallback_reason()
        if quota_reason:
            self._log_warning(f"[{company_id}] {quota_reason}")
            return self._empty_response(quota_reason)

        company_name = company.get("original_name", "")
        prompt = self._build_prompt(company_name)
        started_at = datetime.now()
        api_used = False

        try:
            response = self._generate_with_retry(prompt, company_id)
            api_used = True
            self._increment_gemini_quota()
            elapsed_ms = (datetime.now() - started_at).total_seconds() * 1000
            parsed = self._parse_json_response(self._response_text(response))
            result = self._normalize_result(parsed)
            grounding_urls = self._extract_grounding_urls(response)
            input_tokens, output_tokens = self._extract_token_usage(response)
            is_sufficient = self._is_sufficient(result)
            fallback_reason = "" if is_sufficient else self._fallback_reason(result)

            self._update_company(company_id, result)
            self._insert_log(
                company_id=company_id,
                status="success",
                credits_used=1,
                network_latency_ms=elapsed_ms,
                raw_request=prompt,
                raw_response_summary=json.dumps(
                    {
                        "result": result,
                        "grounding_urls": grounding_urls[:10],
                        "is_sufficient": is_sufficient,
                        "fallback_reason": fallback_reason,
                    },
                    ensure_ascii=False,
                ),
            )

            return {
                "result": result,
                "grounding_urls": grounding_urls,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "is_sufficient": is_sufficient,
                "fallback_reason": fallback_reason,
            }
        except RetryableError:
            self._insert_log(
                company_id=company_id,
                status="failed",
                credits_used=0,
                error_message="Gemini rate limited after retries.",
                error_category="rate_limit",
                raw_request=prompt,
            )
            raise
        except Exception as error:
            if self._is_quota_exceeded_error(error):
                fallback_reason = f"Gemini quota exceeded: {error}"
                self._log_warning(f"[{company_id}] {fallback_reason}")
                self._insert_log(
                    company_id=company_id,
                    status="failed",
                    credits_used=1 if api_used else 0,
                    error_message=fallback_reason,
                    error_category="quota_exceeded",
                    raw_request=prompt,
                )
                return self._empty_response(fallback_reason)

            self._log_error(f"[{company_id}] Gemini quick search failed: {error}")
            self._insert_log(
                company_id=company_id,
                status="failed",
                credits_used=1 if api_used else 0,
                error_message=str(error),
                error_category=type(error).__name__,
                raw_request=prompt,
            )
            return self._empty_response(f"Gemini quick search failed: {error}")

    # -- Private helpers --

    def _generate_with_retry(self, prompt: str, company_id: int) -> Any:
        max_retries = max(1, getattr(self.config, "MAX_RETRIES", 3))
        for attempt in range(1, max_retries + 1):
            try:
                return self.model.generate_content(prompt)
            except Exception as error:
                if self._is_quota_exceeded_error(error):
                    self._log_warning(f"[{company_id}] Gemini quota exceeded: {error}")
                    raise
                if self._is_rate_limit_error(error):
                    if attempt >= max_retries:
                        raise RetryableError(
                            f"Gemini rate limited after {max_retries} retries"
                        ) from error
                    wait_seconds = 60 * attempt
                    self._log_warning(
                        f"[{company_id}] Gemini rate limited; retrying in "
                        f"{wait_seconds}s (attempt {attempt}/{max_retries})."
                    )
                    time.sleep(wait_seconds)
                    continue
                raise

    def _build_prompt(self, company_name: str) -> str:
        return f"""
Tìm thông tin liên hệ của công ty "{company_name}" tại Việt Nam.

Hãy dùng Google Search để kiểm chứng thông tin. Trả về DUY NHẤT một JSON object,
không markdown, không giải thích thêm, với các trường:
{{
  "core_name_vi": "Tên đăng ký kinh doanh bằng tiếng Việt",
  "tax_code": "Mã số thuế 10 hoặc 13 chữ số, hoặc chuỗi rỗng nếu không tìm được",
  "phone": "Số điện thoại liên hệ, hoặc chuỗi rỗng nếu không tìm được",
  "address": "Địa chỉ tại Việt Nam, hoặc chuỗi rỗng nếu không tìm được",
  "website": "Website chính thức, hoặc chuỗi rỗng nếu không tìm được",
  "confidence": 0.0
}}

Quy tắc:
- Ưu tiên nguồn chính thức, trang mã số thuế/doanh nghiệp, và trang liên hệ.
- Chỉ trả phone nếu nguồn có vẻ liên quan trực tiếp tới công ty.
- confidence là số từ 0.0 đến 1.0 phản ánh độ tin cậy tổng thể.
""".strip()

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}

        cleaned = text.strip()
        fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
        if fenced_match:
            cleaned = fenced_match.group(1).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            object_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if object_match:
                return json.loads(object_match.group(0))
            raise

    def _normalize_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        confidence = data.get("confidence", 0.0)
        try:
            confidence_float = float(confidence)
        except (TypeError, ValueError):
            confidence_float = 0.0

        return {
            "core_name_vi": self._clean_text(data.get("core_name_vi")),
            "tax_code": self._clean_tax_code(data.get("tax_code")),
            "phone": self._clean_text(data.get("phone")),
            "address": self._clean_text(data.get("address")),
            "website": self._clean_text(data.get("website")),
            "confidence": max(0.0, min(1.0, confidence_float)),
        }

    def _extract_grounding_urls(self, response: Any) -> List[str]:
        urls: List[str] = []
        candidates = getattr(response, "candidates", []) or []
        for candidate in candidates:
            metadata = self._get_attr(candidate, "grounding_metadata", "groundingMetadata")
            chunks = self._get_attr(metadata, "grounding_chunks", "groundingChunks") or []
            for chunk in chunks:
                web = self._get_attr(chunk, "web")
                uri = self._get_attr(web, "uri")
                if uri:
                    urls.append(str(uri))

            supports = self._get_attr(metadata, "grounding_supports", "groundingSupports") or []
            for support in supports:
                support_chunks = self._get_attr(
                    support, "grounding_chunk_indices", "groundingChunkIndices"
                ) or []
                for index in support_chunks:
                    try:
                        chunk = chunks[int(index)]
                    except (IndexError, TypeError, ValueError):
                        continue
                    web = self._get_attr(chunk, "web")
                    uri = self._get_attr(web, "uri")
                    if uri:
                        urls.append(str(uri))

        return list(dict.fromkeys(urls))

    def _extract_token_usage(self, response: Any) -> tuple[int, int]:
        usage = self._get_attr(response, "usage_metadata", "usageMetadata")
        input_tokens = self._get_attr(usage, "prompt_token_count", "promptTokenCount") or 0
        output_tokens = (
            self._get_attr(usage, "candidates_token_count", "candidatesTokenCount") or 0
        )
        return int(input_tokens), int(output_tokens)

    def _response_text(self, response: Any) -> str:
        try:
            text = getattr(response, "text", None)
        except Exception:
            text = None
        if text:
            return str(text)

        parts_text: List[str] = []
        for candidate in getattr(response, "candidates", []) or []:
            content = self._get_attr(candidate, "content")
            for part in self._get_attr(content, "parts") or []:
                part_text = self._get_attr(part, "text")
                if part_text:
                    parts_text.append(str(part_text))
        return "\n".join(parts_text)

    def _is_sufficient(self, result: Dict[str, Any]) -> bool:
        threshold = getattr(self.config, "GEMINI_QUICK_CONFIDENCE_THRESHOLD", 0.7)
        return bool(result.get("phone")) and result.get("confidence", 0.0) >= threshold

    def _fallback_reason(self, result: Dict[str, Any]) -> str:
        reasons = []
        if not result.get("phone"):
            reasons.append("missing phone")
        threshold = getattr(self.config, "GEMINI_QUICK_CONFIDENCE_THRESHOLD", 0.7)
        if result.get("confidence", 0.0) < threshold:
            reasons.append(f"confidence below {threshold}")
        return "; ".join(reasons) if reasons else ""

    def _quota_fallback_reason(self) -> str:
        quota = self.db.get_daily_quota()
        used = int(quota.get("gemini_grounding_used") or 0)
        limit = int(getattr(self.config, "GEMINI_DAILY_LIMIT", 1450))
        if used >= limit:
            return f"Gemini grounding daily quota reached ({used}/{limit})."
        return ""

    def _increment_gemini_quota(self) -> None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        quota = self.db.get_daily_quota(date_str)
        used = int(quota.get("gemini_grounding_used") or 0)
        self.db.upsert_daily_quota(date_str, gemini_grounding_used=used + 1)

    def _update_company(self, company_id: int, result: Dict[str, Any]) -> None:
        updates = {}
        if result.get("core_name_vi"):
            updates["vietnamese_name"] = result["core_name_vi"]
        if result.get("tax_code"):
            updates["tax_code"] = result["tax_code"]
        if result.get("address"):
            updates["address"] = result["address"]
        if updates:
            updates["vn_data_source"] = "gemini_grounding"
            self.db.update_company(company_id, **updates)

    def _insert_log(self, **kwargs) -> None:
        fields = {
            "step": "ai_quick_search",
            "source_name": "gemini_grounding",
            "completed_at": datetime.now().isoformat(),
            **kwargs,
        }
        try:
            self.db.insert_pipeline_log(**fields)
        except Exception as error:
            self._log_warning(f"Failed to insert pipeline log: {error}")

    def _empty_response(self, fallback_reason: str) -> dict:
        return {
            "result": {
                "core_name_vi": "",
                "tax_code": "",
                "phone": "",
                "address": "",
                "website": "",
                "confidence": 0.0,
            },
            "grounding_urls": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "is_sufficient": False,
            "fallback_reason": fallback_reason,
        }

    def _is_rate_limit_error(self, error: Exception) -> bool:
        status = self._error_status(error)
        return status == 429 or "429" in str(error) or "rate limit" in str(error).lower()

    def _is_quota_exceeded_error(self, error: Exception) -> bool:
        message = str(error).lower()
        status = self._error_status(error)
        return status == 402 or "quota" in message or "resource_exhausted" in message

    def _error_status(self, error: Exception) -> Optional[int]:
        for attr in ("status_code", "code"):
            value = getattr(error, attr, None)
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        response = getattr(error, "response", None)
        value = getattr(response, "status_code", None)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _get_attr(self, value: Any, *names: str) -> Any:
        if value is None:
            return None
        for name in names:
            if isinstance(value, dict) and name in value:
                return value[name]
            attr = getattr(value, name, None)
            if attr is not None:
                return attr
        return None

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _clean_tax_code(self, value: Any) -> str:
        text = self._clean_text(value)
        digits = re.sub(r"\D", "", text)
        if len(digits) in (10, 13):
            return digits
        return text

    def _log_warning(self, message: str) -> None:
        if hasattr(self.logger, "warning"):
            self.logger.warning(message)

    def _log_error(self, message: str) -> None:
        if hasattr(self.logger, "error"):
            self.logger.error(message)
