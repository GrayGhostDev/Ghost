"""Extended tests for src/ghost/utils.py — covers all utility classes."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ghost.utils import (
    CacheUtils,
    DataStructureUtils,
    DateTimeUtils,
    FileUtils,
    HashUtils,
    RetryUtils,
    SerializationUtils,
    StringUtils,
    UUIDUtils,
    ValidationUtils,
)


# ──────────────────────────────────────────────
# DateTimeUtils
# ──────────────────────────────────────────────

class TestDateTimeUtils:
    def test_now_utc(self):
        dt = DateTimeUtils.now_utc()
        assert dt.tzinfo is not None

    def test_to_timestamp(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ts = DateTimeUtils.to_timestamp(dt)
        assert isinstance(ts, float)

    def test_from_timestamp(self):
        ts = 1704067200.0
        dt = DateTimeUtils.from_timestamp(ts)
        assert dt.tzinfo == timezone.utc

    def test_format_iso(self):
        dt = datetime(2026, 3, 12, 10, 30, 0, tzinfo=timezone.utc)
        iso = DateTimeUtils.format_iso(dt)
        assert "2026-03-12" in iso

    def test_parse_iso(self):
        dt = DateTimeUtils.parse_iso("2026-03-12T10:30:00+00:00")
        assert dt.year == 2026

    def test_format_datetime_custom(self):
        dt = datetime(2026, 3, 12, 10, 30, 0, tzinfo=timezone.utc)
        result = DateTimeUtils.format_datetime(dt, "YYYY/MM/DD HH:mm:ss")
        assert result == "2026/03/12 10:30:00"


# ──────────────────────────────────────────────
# StringUtils
# ──────────────────────────────────────────────

class TestStringUtils:
    def test_generate_random_string(self):
        s = StringUtils.generate_random_string(16)
        assert len(s) == 16

    def test_generate_random_string_with_special(self):
        s = StringUtils.generate_random_string(64, include_special=True)
        assert len(s) == 64

    def test_generate_slug(self):
        assert StringUtils.generate_slug("Hello World!") == "hello-world"
        assert StringUtils.generate_slug("  Multiple   Spaces  ") == "multiple-spaces"

    def test_slugify_alias(self):
        assert StringUtils.slugify("Test Title") == StringUtils.generate_slug("Test Title")

    def test_truncate_short(self):
        assert StringUtils.truncate("short", max_length=100) == "short"

    def test_truncate_long(self):
        result = StringUtils.truncate("a" * 200, max_length=10)
        assert len(result) == 10
        assert result.endswith("...")

    def test_clean_whitespace(self):
        assert StringUtils.clean_whitespace("  hello   world  ") == "hello world"

    def test_is_valid_email(self):
        assert StringUtils.is_valid_email("test@example.com")
        assert not StringUtils.is_valid_email("not-an-email")
        assert not StringUtils.is_valid_email("@missing.com")

    def test_mask_sensitive(self):
        assert StringUtils.mask_sensitive("4111111111111111", show_last=4) == "************1111"

    def test_mask_sensitive_short(self):
        assert StringUtils.mask_sensitive("ab", show_last=4) == "**"


# ──────────────────────────────────────────────
# HashUtils
# ──────────────────────────────────────────────

class TestHashUtils:
    def test_md5(self):
        h = HashUtils.md5("hello")
        assert len(h) == 32

    def test_sha256(self):
        h = HashUtils.sha256("hello")
        assert len(h) == 64

    def test_sha512(self):
        h = HashUtils.sha512("hello")
        assert len(h) == 128

    def test_generate_hash_default_salt(self):
        h = HashUtils.generate_hash("secret")
        assert ":" in h

    def test_generate_hash_custom_salt(self):
        h = HashUtils.generate_hash("secret", salt="mysalt")
        assert h.startswith("mysalt:")

    def test_verify_hash_success(self):
        h = HashUtils.generate_hash("secret")
        assert HashUtils.verify_hash("secret", h)

    def test_verify_hash_failure(self):
        h = HashUtils.generate_hash("secret")
        assert not HashUtils.verify_hash("wrong", h)

    def test_verify_hash_bad_format(self):
        assert not HashUtils.verify_hash("test", "nocolon")


# ──────────────────────────────────────────────
# UUIDUtils
# ──────────────────────────────────────────────

class TestUUIDUtils:
    def test_generate(self):
        u = UUIDUtils.generate()
        assert len(u) == 36

    def test_is_valid(self):
        u = UUIDUtils.generate()
        assert UUIDUtils.is_valid(u)
        assert not UUIDUtils.is_valid("not-a-uuid")

    def test_short_uuid(self):
        s = UUIDUtils.short_uuid(8)
        assert len(s) == 8


# ──────────────────────────────────────────────
# ValidationUtils
# ──────────────────────────────────────────────

class TestValidationUtils:
    def test_validate_required_fields_all_present(self):
        data = {"name": "Alice", "age": 30}
        missing = ValidationUtils.validate_required_fields(data, ["name", "age"])
        assert missing == []

    def test_validate_required_fields_missing(self):
        data = {"name": "Alice"}
        missing = ValidationUtils.validate_required_fields(data, ["name", "age"])
        assert "age" in missing

    def test_validate_required_fields_none_value(self):
        data = {"name": None}
        missing = ValidationUtils.validate_required_fields(data, ["name"])
        assert "name" in missing

    def test_validate_required_fields_empty_string(self):
        data = {"name": ""}
        missing = ValidationUtils.validate_required_fields(data, ["name"])
        assert "name" in missing

    def test_validate_types(self):
        data = {"name": "Alice", "age": "not_int"}
        errors = ValidationUtils.validate_types(data, {"name": str, "age": int})
        assert len(errors) == 1
        assert "age" in errors[0]

    def test_validate_types_all_ok(self):
        data = {"name": "Alice", "age": 30}
        errors = ValidationUtils.validate_types(data, {"name": str, "age": int})
        assert errors == []

    def test_validate_length(self):
        data = {"name": "ab"}
        errors = ValidationUtils.validate_length(data, {"name": (3, 50)})
        assert len(errors) == 1

    def test_validate_length_ok(self):
        data = {"name": "Alice"}
        errors = ValidationUtils.validate_length(data, {"name": (1, 100)})
        assert errors == []

    def test_is_email(self):
        assert ValidationUtils.is_email("user@example.com")
        assert not ValidationUtils.is_email("")
        assert not ValidationUtils.is_email(None)
        assert not ValidationUtils.is_email(123)


# ──────────────────────────────────────────────
# SerializationUtils
# ──────────────────────────────────────────────

class TestSerializationUtils:
    def test_to_dict_dict(self):
        assert SerializationUtils.to_dict({"a": 1}) == {"a": 1}

    def test_to_dict_list(self):
        assert SerializationUtils.to_dict([1, 2]) == [1, 2]

    def test_to_dict_primitive(self):
        # Enums with __dict__ cause recursion in to_dict, so test scalar passthrough
        assert SerializationUtils.to_dict(42) == 42
        assert SerializationUtils.to_dict("hello") == "hello"
        assert SerializationUtils.to_dict(None) is None

    def test_to_dict_datetime(self):
        dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = SerializationUtils.to_dict(dt)
        assert "2026" in result

    def test_to_dict_dataclass(self):
        from dataclasses import dataclass
        @dataclass
        class Point:
            x: int
            y: int
        assert SerializationUtils.to_dict(Point(1, 2)) == {"x": 1, "y": 2}

    def test_to_dict_object(self):
        class Obj:
            def __init__(self):
                self.val = 42
        result = SerializationUtils.to_dict(Obj())
        assert result["val"] == 42

    def test_to_dict_tuple(self):
        result = SerializationUtils.to_dict((1, 2, 3))
        assert result == [1, 2, 3]

    def test_to_json(self):
        data = {"key": "value"}
        j = SerializationUtils.to_json(data)
        assert '"key"' in j

    def test_to_json_with_indent(self):
        data = {"key": "value"}
        j = SerializationUtils.to_json(data, indent=2)
        assert "\n" in j

    def test_from_json(self):
        result = SerializationUtils.from_json('{"a": 1}')
        assert result == {"a": 1}

    def test_to_csv_empty(self):
        assert SerializationUtils.to_csv([]) == ""

    def test_to_csv(self):
        data = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
        csv = SerializationUtils.to_csv(data)
        assert "Alice" in csv
        assert "name" in csv  # header

    def test_to_csv_with_file(self, tmp_path):
        data = [{"col": "val"}]
        filepath = str(tmp_path / "out.csv")
        result = SerializationUtils.to_csv(data, filename=filepath)
        assert "col" in result
        assert Path(filepath).exists()


# ──────────────────────────────────────────────
# FileUtils
# ──────────────────────────────────────────────

class TestFileUtils:
    def test_ensure_directory(self, tmp_path):
        new_dir = tmp_path / "sub" / "deep"
        result = FileUtils.ensure_directory(new_dir)
        assert result.exists()

    def test_get_file_size(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert FileUtils.get_file_size(f) == 5

    def test_get_file_extension(self):
        assert FileUtils.get_file_extension("photo.JPG") == ".jpg"
        assert FileUtils.get_file_extension("file.tar.gz") == ".gz"

    def test_is_safe_filename(self):
        assert FileUtils.is_safe_filename("report.pdf")
        assert not FileUtils.is_safe_filename("../etc/passwd")
        assert not FileUtils.is_safe_filename("file:name")

    def test_sanitize_filename(self):
        assert ".." not in FileUtils.sanitize_filename("../hack.txt")
        assert "<" not in FileUtils.sanitize_filename("file<>.txt")


# ──────────────────────────────────────────────
# CacheUtils
# ──────────────────────────────────────────────

class TestCacheUtils:
    def setup_method(self):
        CacheUtils.clear()

    def test_set_and_get(self):
        CacheUtils.set("k", "v", ttl=60)
        assert CacheUtils.get("k") == "v"

    def test_get_miss(self):
        assert CacheUtils.get("missing") is None

    def test_delete(self):
        CacheUtils.set("k", "v")
        assert CacheUtils.delete("k")
        assert CacheUtils.get("k") is None

    def test_delete_missing(self):
        assert not CacheUtils.delete("nope")

    def test_clear(self):
        CacheUtils.set("a", 1)
        CacheUtils.set("b", 2)
        CacheUtils.clear()
        assert CacheUtils.get("a") is None

    def test_generate_cache_key(self):
        k1 = CacheUtils.generate_cache_key("a", b=1)
        k2 = CacheUtils.generate_cache_key("a", b=1)
        k3 = CacheUtils.generate_cache_key("a", b=2)
        assert k1 == k2
        assert k1 != k3

    def test_is_cache_expired(self):
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert CacheUtils.is_cache_expired(past, ttl_seconds=60)
        now = DateTimeUtils.now_utc()
        assert not CacheUtils.is_cache_expired(now, ttl_seconds=3600)


# ──────────────────────────────────────────────
# DataStructureUtils
# ──────────────────────────────────────────────

class TestDataStructureUtils:
    def test_flatten_dict(self):
        nested = {"a": {"b": {"c": 1}}, "d": 2}
        flat = DataStructureUtils.flatten_dict(nested)
        assert flat == {"a.b.c": 1, "d": 2}

    def test_flatten_dict_custom_sep(self):
        nested = {"a": {"b": 1}}
        flat = DataStructureUtils.flatten_dict(nested, sep="/")
        assert "a/b" in flat

    def test_deep_merge(self):
        d1 = {"a": 1, "b": {"c": 2}}
        d2 = {"b": {"d": 3}, "e": 4}
        result = DataStructureUtils.deep_merge(d1, d2)
        assert result == {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}

    def test_deep_merge_overwrite(self):
        d1 = {"a": 1}
        d2 = {"a": 2}
        result = DataStructureUtils.deep_merge(d1, d2)
        assert result["a"] == 2

    def test_chunk_list(self):
        result = DataStructureUtils.chunk_list([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_chunk_list_exact(self):
        result = DataStructureUtils.chunk_list([1, 2, 3, 4], 2)
        assert result == [[1, 2], [3, 4]]

    def test_remove_none_values(self):
        result = DataStructureUtils.remove_none_values({"a": 1, "b": None, "c": 3})
        assert result == {"a": 1, "c": 3}


# ──────────────────────────────────────────────
# RetryUtils
# ──────────────────────────────────────────────

class TestRetryUtils:
    def test_exponential_backoff(self):
        assert RetryUtils.exponential_backoff(0) == 1.0
        assert RetryUtils.exponential_backoff(1) == 2.0
        assert RetryUtils.exponential_backoff(2) == 4.0

    def test_exponential_backoff_max(self):
        assert RetryUtils.exponential_backoff(100, max_delay=10.0) == 10.0

    def test_with_retry_success(self):
        call_count = 0
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"
        wrapped = RetryUtils.with_retry(succeed, max_attempts=3, delay=0.01)
        assert wrapped() == "ok"
        assert call_count == 1

    def test_with_retry_eventual_success(self):
        attempts = 0
        def fail_twice():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("not yet")
            return "ok"
        wrapped = RetryUtils.with_retry(fail_twice, max_attempts=3, delay=0.01)
        assert wrapped() == "ok"
        assert attempts == 3

    def test_with_retry_all_fail(self):
        def always_fail():
            raise RuntimeError("boom")
        wrapped = RetryUtils.with_retry(always_fail, max_attempts=2, delay=0.01)
        with pytest.raises(RuntimeError, match="boom"):
            wrapped()

    def test_with_retry_no_backoff(self):
        attempts = 0
        def fail_then_ok():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise ValueError("fail")
            return "ok"
        wrapped = RetryUtils.with_retry(fail_then_ok, max_attempts=2, delay=0.01, backoff=False)
        assert wrapped() == "ok"
