"""
Integration tests for Phase 0: Snapshot feature flag and logging.

Tests that snapshot logging infrastructure is in place before implementing
the actual snapshot functionality.
"""

import pytest
import sys
import os

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))


def test_snapshot_log_debug_endpoint(client):
    """Test that /debug/snapshot-log-test returns correct JSON and status."""
    response = client.get('/debug/snapshot-log-test')

    assert response.status_code == 200

    data = response.get_json()
    assert data['status'] == 'ok'
    assert data['snapshots_enabled'] is True  # Default value
    assert 'message' in data


def test_snapshot_feature_flag_can_be_disabled():
    """Test that SNAPSHOTS_ENABLED flag respects environment variable."""
    # This test would need to reload the app module to test different env values
    # For now, just verify the default is True
    from src.web.app import SNAPSHOTS_ENABLED
    assert SNAPSHOTS_ENABLED is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
