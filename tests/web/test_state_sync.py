"""
Tests for SSE-based cross-tab state synchronization.

Tests the state broadcasting infrastructure added in src/web/app.py
for keeping Plan, Shop, and Cook tabs in sync.
"""

import json
import pytest
import queue
import threading
from flask import Flask
from datetime import datetime

from src.web.app import app, broadcast_state_change, state_change_queues, state_change_lock


class TestStateBroadcasting:
    """Test the state broadcasting infrastructure."""

    def test_broadcast_to_single_tab(self):
        """Test broadcasting to a single listening tab."""
        # Setup
        tab_id = "test_tab_1"
        test_queue = queue.Queue()

        with state_change_lock:
            state_change_queues[tab_id] = test_queue

        try:
            # Broadcast event
            broadcast_state_change('meal_plan_changed', {
                'meal_plan_id': 'mp_123',
                'date_changed': '2025-11-07'
            })

            # Verify event received
            event = test_queue.get(timeout=1)
            assert event['type'] == 'meal_plan_changed'
            assert event['data']['meal_plan_id'] == 'mp_123'
            assert event['data']['date_changed'] == '2025-11-07'
            assert 'timestamp' in event
        finally:
            # Cleanup
            with state_change_lock:
                if tab_id in state_change_queues:
                    del state_change_queues[tab_id]

    def test_broadcast_to_multiple_tabs(self):
        """Test broadcasting to multiple tabs simultaneously."""
        # Setup multiple tabs
        tab_ids = ['tab_1', 'tab_2', 'tab_3']
        test_queues = {}

        for tab_id in tab_ids:
            test_queue = queue.Queue()
            test_queues[tab_id] = test_queue
            with state_change_lock:
                state_change_queues[tab_id] = test_queue

        try:
            # Broadcast event
            broadcast_state_change('shopping_list_changed', {
                'shopping_list_id': 'sl_456'
            })

            # Verify all tabs received the event
            for tab_id, test_queue in test_queues.items():
                event = test_queue.get(timeout=1)
                assert event['type'] == 'shopping_list_changed'
                assert event['data']['shopping_list_id'] == 'sl_456'
                assert 'timestamp' in event
        finally:
            # Cleanup
            with state_change_lock:
                for tab_id in tab_ids:
                    if tab_id in state_change_queues:
                        del state_change_queues[tab_id]

    def test_broadcast_with_no_listeners(self):
        """Test that broadcasting with no listeners doesn't error."""
        # Should not raise any exceptions
        broadcast_state_change('meal_plan_changed', {
            'meal_plan_id': 'mp_789'
        })

    def test_event_timestamp_format(self):
        """Test that event timestamps are valid ISO format."""
        tab_id = "test_tab_timestamp"
        test_queue = queue.Queue()

        with state_change_lock:
            state_change_queues[tab_id] = test_queue

        try:
            broadcast_state_change('meal_plan_changed', {'meal_plan_id': 'mp_111'})

            event = test_queue.get(timeout=1)
            # Should be able to parse the timestamp
            timestamp = datetime.fromisoformat(event['timestamp'])
            assert isinstance(timestamp, datetime)
        finally:
            with state_change_lock:
                if tab_id in state_change_queues:
                    del state_change_queues[tab_id]


class TestStateStreamEndpoint:
    """Test the /api/state-stream SSE endpoint."""

    @pytest.fixture
    def client(self):
        """Flask test client."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_state_stream_connection(self, client):
        """Test connecting to the state stream endpoint."""
        # Start stream in background thread
        events = []

        def consume_stream():
            response = client.get('/api/state-stream?tab_id=test_stream_tab')
            # Read first event (should be keepalive or actual event)
            for line in response.response:
                if line.startswith(b'data:'):
                    data = json.loads(line[5:])
                    events.append(data)
                    break

        thread = threading.Thread(target=consume_stream)
        thread.daemon = True
        thread.start()
        thread.join(timeout=2)

        # Should have received at least one event (keepalive)
        assert len(events) > 0

    def test_state_stream_receives_broadcast(self, client):
        """Test that connected stream receives broadcast events."""
        tab_id = 'test_broadcast_tab'
        events = []
        stop_event = threading.Event()

        def consume_stream():
            response = client.get(f'/api/state-stream?tab_id={tab_id}')
            for line in response.response:
                if stop_event.is_set():
                    break
                if line.startswith(b'data:'):
                    data = json.loads(line[5:])
                    events.append(data)
                    if data.get('type') == 'meal_plan_changed':
                        stop_event.set()

        # Start stream consumer
        thread = threading.Thread(target=consume_stream)
        thread.daemon = True
        thread.start()

        # Give it time to connect
        import time
        time.sleep(0.5)

        # Broadcast event
        broadcast_state_change('meal_plan_changed', {
            'meal_plan_id': 'mp_broadcast_test'
        })

        # Wait for event to be received
        thread.join(timeout=2)

        # Verify event was received
        meal_plan_events = [e for e in events if e.get('type') == 'meal_plan_changed']
        assert len(meal_plan_events) > 0
        assert meal_plan_events[0]['data']['meal_plan_id'] == 'mp_broadcast_test'


class TestCrossTabScenarios:
    """Test realistic cross-tab synchronization scenarios."""

    def test_meal_swap_invalidates_shopping_list(self):
        """
        Test that swapping a meal in Plan tab invalidates Shop tab's list.

        Scenario:
        1. User has shopping list open in Shop tab
        2. User swaps a meal in Plan tab
        3. Shop tab receives 'meal_plan_changed' event
        4. Shop tab should show stale notification
        """
        tab_plan = "plan_tab"
        tab_shop = "shop_tab"

        shop_queue = queue.Queue()
        plan_queue = queue.Queue()

        with state_change_lock:
            state_change_queues[tab_plan] = plan_queue
            state_change_queues[tab_shop] = shop_queue

        try:
            # Simulate meal swap in Plan tab
            broadcast_state_change('meal_plan_changed', {
                'meal_plan_id': 'mp_123',
                'date_changed': '2025-11-07'
            })

            # Shop tab should receive the event
            shop_event = shop_queue.get(timeout=1)
            assert shop_event['type'] == 'meal_plan_changed'

            # Plan tab should also receive it (for auto-refresh)
            plan_event = plan_queue.get(timeout=1)
            assert plan_event['type'] == 'meal_plan_changed'
        finally:
            with state_change_lock:
                for tab_id in [tab_plan, tab_shop]:
                    if tab_id in state_change_queues:
                        del state_change_queues[tab_id]

    def test_shopping_list_regeneration_notifies_all_tabs(self):
        """
        Test that regenerating shopping list notifies all tabs.

        Scenario:
        1. User clicks "Regenerate Now" in Shop tab
        2. New shopping list created
        3. All Shop tabs receive 'shopping_list_changed' event
        4. All Shop tabs reload to show new list
        """
        shop_tabs = ['shop_tab_1', 'shop_tab_2', 'shop_tab_3']
        queues = {}

        for tab_id in shop_tabs:
            test_queue = queue.Queue()
            queues[tab_id] = test_queue
            with state_change_lock:
                state_change_queues[tab_id] = test_queue

        try:
            # Simulate shopping list regeneration
            broadcast_state_change('shopping_list_changed', {
                'shopping_list_id': 'sl_new_456',
                'meal_plan_id': 'mp_123'
            })

            # All shop tabs should receive the event
            for tab_id, test_queue in queues.items():
                event = test_queue.get(timeout=1)
                assert event['type'] == 'shopping_list_changed'
                assert event['data']['shopping_list_id'] == 'sl_new_456'
        finally:
            with state_change_lock:
                for tab_id in shop_tabs:
                    if tab_id in state_change_queues:
                        del state_change_queues[tab_id]

    def test_plan_tab_auto_refresh_on_meal_change(self):
        """
        Test that Plan tab auto-refreshes when meal plan changes.

        Scenario:
        1. User has Plan tab open
        2. Meal gets swapped (from any tab or chatbot)
        3. Plan tab receives 'meal_plan_changed' event
        4. Plan tab auto-refreshes meal plan display
        """
        plan_tab = "plan_tab_autorefresh"
        test_queue = queue.Queue()

        with state_change_lock:
            state_change_queues[plan_tab] = test_queue

        try:
            # Simulate meal change
            broadcast_state_change('meal_plan_changed', {
                'meal_plan_id': 'mp_999',
                'date_changed': '2025-11-08'
            })

            # Plan tab should receive event to trigger refresh
            event = test_queue.get(timeout=1)
            assert event['type'] == 'meal_plan_changed'
            assert event['data']['meal_plan_id'] == 'mp_999'
            assert event['data']['date_changed'] == '2025-11-08'
        finally:
            with state_change_lock:
                if plan_tab in state_change_queues:
                    del state_change_queues[plan_tab]


@pytest.mark.slow
class TestStateStreamResilience:
    """Test error handling and edge cases."""

    def test_queue_cleanup_on_disconnect(self):
        """Test that queues are cleaned up when tab disconnects."""
        # This would be tested by monitoring state_change_queues
        # after a client disconnects from the SSE stream
        # In real implementation, cleanup happens in the SSE generator's finally block
        pass  # Placeholder for future implementation

    def test_broadcast_continues_after_tab_error(self):
        """Test that broadcast continues to other tabs if one tab errors."""
        good_tab = "good_tab"
        bad_tab = "bad_tab"

        good_queue = queue.Queue()
        bad_queue = None  # Intentionally None to cause error

        with state_change_lock:
            state_change_queues[good_tab] = good_queue
            state_change_queues[bad_tab] = bad_queue

        try:
            # Should not raise exception despite bad_tab having None queue
            broadcast_state_change('meal_plan_changed', {'meal_plan_id': 'mp_resilience'})

            # Good tab should still receive the event
            event = good_queue.get(timeout=1)
            assert event['type'] == 'meal_plan_changed'
        finally:
            with state_change_lock:
                for tab_id in [good_tab, bad_tab]:
                    if tab_id in state_change_queues:
                        del state_change_queues[tab_id]
