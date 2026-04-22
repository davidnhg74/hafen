"""
Tests for input validation and error handling utilities.
"""

import pytest
from src.utils.validation import (
    InputValidator,
    RateLimiter,
    ValidationError,
)


class TestInputValidator:
    """Test input validation."""

    def test_validate_uuid_valid(self):
        """Test valid UUID validation."""
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        assert InputValidator.validate_uuid(valid_uuid) is True

    def test_validate_uuid_invalid(self):
        """Test invalid UUID validation."""
        assert InputValidator.validate_uuid("not-a-uuid") is False
        assert InputValidator.validate_uuid("") is False

    def test_validate_email_valid(self):
        """Test valid email validation."""
        assert InputValidator.validate_email("user@example.com") is True
        assert InputValidator.validate_email("john.doe+tag@company.co.uk") is True

    def test_validate_email_invalid(self):
        """Test invalid email validation."""
        assert InputValidator.validate_email("invalid-email") is False
        assert InputValidator.validate_email("@example.com") is False
        assert InputValidator.validate_email("user@") is False

    def test_validate_identifier_valid(self):
        """Test valid SQL identifier validation."""
        assert InputValidator.validate_identifier("table_name") is True
        assert InputValidator.validate_identifier("_private") is True
        assert InputValidator.validate_identifier("$column") is True
        assert InputValidator.validate_identifier("Col123") is True

    def test_validate_identifier_invalid(self):
        """Test invalid SQL identifier validation."""
        assert InputValidator.validate_identifier("123table") is False
        assert InputValidator.validate_identifier("table-name") is False
        assert InputValidator.validate_identifier("table name") is False

    def test_validate_hostname_valid(self):
        """Test valid hostname validation."""
        assert InputValidator.validate_hostname("example.com") is True
        assert InputValidator.validate_hostname("sub.example.com") is True
        assert InputValidator.validate_hostname("localhost") is True
        assert InputValidator.validate_hostname("192.168.1.1") is True

    def test_validate_hostname_invalid(self):
        """Test invalid hostname validation."""
        assert InputValidator.validate_hostname("-invalid.com") is False
        assert InputValidator.validate_hostname("invalid-.com") is False

    def test_validate_port_valid(self):
        """Test valid port validation."""
        assert InputValidator.validate_port(1) is True
        assert InputValidator.validate_port(8000) is True
        assert InputValidator.validate_port(65535) is True

    def test_validate_port_invalid(self):
        """Test invalid port validation."""
        assert InputValidator.validate_port(0) is False
        assert InputValidator.validate_port(65536) is False
        assert InputValidator.validate_port(-1) is False

    def test_validate_step_number_valid(self):
        """Test valid step number validation."""
        assert InputValidator.validate_step_number(1) is True
        assert InputValidator.validate_step_number(10) is True
        assert InputValidator.validate_step_number(20) is True

    def test_validate_step_number_invalid(self):
        """Test invalid step number validation."""
        assert InputValidator.validate_step_number(0) is False
        assert InputValidator.validate_step_number(21) is False
        assert InputValidator.validate_step_number(-1) is False

    def test_validate_string_length_valid(self):
        """Test valid string length validation."""
        assert InputValidator.validate_string_length("hello") is True
        assert InputValidator.validate_string_length("a" * 255) is True

    def test_validate_string_length_invalid(self):
        """Test invalid string length validation."""
        assert InputValidator.validate_string_length("", min_len=1) is False
        assert InputValidator.validate_string_length("a" * 256, max_len=255) is False

    def test_sanitize_string(self):
        """Test string sanitization."""
        # Test whitespace stripping
        assert InputValidator.sanitize_string("  hello  ") == "hello"

        # Test length limiting
        long_string = "a" * 1000
        assert len(InputValidator.sanitize_string(long_string, max_len=500)) == 500

    def test_validate_connection_config_valid_oracle(self):
        """Test valid Oracle connection config."""
        config = {
            "database_type": "oracle",
            "host": "oracle.company.com",
            "port": 1521,
            "username": "scott",
            "password": "tiger",
            "service_name": "ORCL",
        }

        is_valid, error = InputValidator.validate_connection_config(config)
        assert is_valid is True
        assert error is None

    def test_validate_connection_config_valid_postgres(self):
        """Test valid PostgreSQL connection config."""
        config = {
            "database_type": "postgres",
            "host": "localhost",
            "port": 5432,
            "username": "postgres",
            "password": "password",
            "database": "mydb",
        }

        is_valid, error = InputValidator.validate_connection_config(config)
        assert is_valid is True
        assert error is None

    def test_validate_connection_config_missing_fields(self):
        """Test connection config with missing fields."""
        config = {
            "host": "localhost",
            "port": 5432,
        }

        is_valid, error = InputValidator.validate_connection_config(config)
        assert is_valid is False
        assert error is not None

    def test_validate_connection_config_invalid_host(self):
        """Test connection config with invalid hostname."""
        config = {
            "database_type": "oracle",
            "host": "-invalid.com",
            "port": 1521,
            "username": "scott",
            "password": "tiger",
        }

        is_valid, error = InputValidator.validate_connection_config(config)
        assert is_valid is False
        assert "hostname" in error.lower()

    def test_validate_connection_config_invalid_port(self):
        """Test connection config with invalid port."""
        config = {
            "database_type": "oracle",
            "host": "localhost",
            "port": 99999,
            "username": "scott",
            "password": "tiger",
        }

        is_valid, error = InputValidator.validate_connection_config(config)
        assert is_valid is False

    def test_validate_workflow_name_valid(self):
        """Test valid workflow name."""
        is_valid, error = InputValidator.validate_workflow_name("My Migration")
        assert is_valid is True
        assert error is None

    def test_validate_workflow_name_too_short(self):
        """Test workflow name too short."""
        is_valid, error = InputValidator.validate_workflow_name("ab")
        assert is_valid is False

    def test_validate_workflow_name_too_long(self):
        """Test workflow name too long."""
        is_valid, error = InputValidator.validate_workflow_name("a" * 256)
        assert is_valid is False

    def test_validate_workflow_name_dangerous_pattern(self):
        """Test workflow name with dangerous patterns."""
        dangerous_names = [
            "Migration; DROP TABLE migrations;",
            "Test -- comment",
            "Test /* comment */",
            "Test DELETE",
        ]

        for name in dangerous_names:
            is_valid, error = InputValidator.validate_workflow_name(name)
            assert is_valid is False


class TestRateLimiter:
    """Test rate limiting."""

    @pytest.fixture
    def limiter(self):
        """Create a rate limiter."""
        return RateLimiter(max_requests=5, window_seconds=60)

    def test_allow_under_limit(self, limiter):
        """Test allowing requests under limit."""
        for i in range(5):
            assert limiter.is_allowed("client-1") is True

    def test_deny_over_limit(self, limiter):
        """Test denying requests over limit."""
        # Use up the limit
        for i in range(5):
            limiter.is_allowed("client-1")

        # Next request should be denied
        assert limiter.is_allowed("client-1") is False

    def test_separate_clients(self, limiter):
        """Test rate limiting is per-client."""
        for i in range(5):
            limiter.is_allowed("client-1")

        # Different client should have own limit
        assert limiter.is_allowed("client-2") is True

    def test_get_remaining(self, limiter):
        """Test getting remaining requests."""
        remaining = limiter.get_remaining("new-client")
        assert remaining == 5

        limiter.is_allowed("new-client")
        remaining = limiter.get_remaining("new-client")
        assert remaining == 4

        for i in range(4):
            limiter.is_allowed("new-client")

        remaining = limiter.get_remaining("new-client")
        assert remaining == 0
