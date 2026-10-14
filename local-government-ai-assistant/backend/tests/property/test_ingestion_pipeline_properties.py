"""
Property-based tests for Ingestion Pipeline.

**Validates: Requirements 6.5**
"""

import pytest
from hypothesis import given, strategies as st, assume

from app.models.data_models import IngestionStatus


@given(status_str=st.text(min_size=1))
def test_property_16_ingestion_status_validity(status_str):
    """
    Property 16: Ingestion status is always valid enum value.
    
    For any status at any point in time, it must be one of the four valid values:
    {pending, processing, completed, failed}.
    
    **Validates: Requirements 6.5**
    """
    valid_statuses = {s.value for s in IngestionStatus}
    
    # Should only accept valid enum values
    if status_str in valid_statuses:
        status = IngestionStatus(status_str)
        assert status.value in valid_statuses
        assert status.value == status_str
    else:
        # Invalid status strings should raise ValueError
        with pytest.raises(ValueError):
            IngestionStatus(status_str)


def test_ingestion_status_enum_completeness():
    """Test that IngestionStatus enum has exactly 4 valid values."""
    status_values = {s.value for s in IngestionStatus}
    
    expected_values = {"pending", "processing", "completed", "failed"}
    assert status_values == expected_values, f"Status values mismatch: {status_values}"


def test_ingestion_status_transitions():
    """Test that all ingestion status transitions are valid enum values."""
    # All possible statuses
    statuses = [
        IngestionStatus.PENDING,
        IngestionStatus.PROCESSING,
        IngestionStatus.COMPLETED,
        IngestionStatus.FAILED
    ]
    
    # Verify each status is valid
    for status in statuses:
        assert isinstance(status, IngestionStatus)
        assert status.value in {"pending", "processing", "completed", "failed"}
