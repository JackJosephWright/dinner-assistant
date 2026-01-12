#!/usr/bin/env python3
"""
Flask web application for Meal Planning Assistant.

Provides a modern web interface for planning meals, creating shopping lists,
and accessing cooking guides.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import queue
import threading
import sqlite3
import uuid
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, Response, redirect, url_for, flash
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from main import MealPlanningAssistant
from chatbot import MealPlanningChatbot
from onboarding import OnboardingFlow, check_onboarding_status

# Setup logging with both console and file output
logs_dir = os.path.join(project_root, 'logs')
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more verbose output
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Console output
        RotatingFileHandler(
            os.path.join(logs_dir, 'app.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
    ]
)
logger = logging.getLogger(__name__)

# Import performance monitoring (optional, only if available)
try:
    sys.path.insert(0, os.path.join(project_root, 'tests'))
    from performance.instrumentation import PerformanceMonitor, track_llm_calls, track_database_queries
    PERFORMANCE_MONITORING_ENABLED = True
except ImportError:
    PERFORMANCE_MONITORING_ENABLED = False
    logger.warning("Performance monitoring not available - instrumentation.py not found")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
CORS(app)

# Structured logging helpers for snapshot operations
def log_snapshot_save(snapshot_id: str, user_id: int, week_of: str):
    """Log snapshot save operation."""
    logger.info(f"[SNAPSHOT] Saved: id={snapshot_id}, user={user_id}, week={week_of}")

def log_snapshot_load(snapshot_id: str):
    """Log snapshot load operation."""
    logger.info(f"[SNAPSHOT] Loaded: id={snapshot_id}")

# Simple user authentication
USERS = {
    "admin": "password",
    "agusta": "password",
    "lj": "password"
}

# User ID mapping (for snapshot storage)
USER_IDS = {
    "admin": 1,
    "agusta": 2,
    "lj": 3
}

def login_required(f):
    """Decorator to require login for routes."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            from flask import redirect, url_for
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize assistant (will use agentic agents if API key is set)
# Note: We'll set the progress callback per request
assistant = MealPlanningAssistant(db_dir="data", use_agentic=True)


def migrate_hardcoded_users():
    """Migrate hardcoded users to database on startup (idempotent)."""
    for username, password in USERS.items():
        existing = assistant.db.get_user_by_username(username)
        if not existing:
            password_hash = generate_password_hash(password)
            user_id = assistant.db.create_user(username, password_hash)
            if user_id:
                logger.info(f"Migrated hardcoded user to database: {username} (ID: {user_id})")
        else:
            logger.debug(f"User already exists in database: {username}")


# Migrate existing hardcoded users to database
migrate_hardcoded_users()

# Wire up performance monitoring if available
if PERFORMANCE_MONITORING_ENABLED:
    perf_monitor = PerformanceMonitor()

    # Track LLM calls if using agentic agents
    if assistant.is_agentic and hasattr(assistant.planning_agent, 'client'):
        track_llm_calls(assistant.planning_agent.client)
        logger.info("Performance monitoring enabled for planning agent")

    if assistant.is_agentic and hasattr(assistant.shopping_agent, 'client'):
        track_llm_calls(assistant.shopping_agent.client)
        logger.info("Performance monitoring enabled for shopping agent")

    if assistant.is_agentic and hasattr(assistant.cooking_agent, 'client'):
        track_llm_calls(assistant.cooking_agent.client)
        logger.info("Performance monitoring enabled for cooking agent")

    # Track database queries
    track_database_queries(assistant.db)
    logger.info("Performance monitoring enabled for database queries")
else:
    perf_monitor = None

# Helper to set progress callback for the current request
def set_agent_progress_callback(session_id: str, enable_verbose: bool = False):
    """Set progress callback for the assistant's agents."""
    def callback(message: str):
        emit_progress(session_id, message)

    def verbose_callback(message: str):
        emit_progress(session_id, message, "verbose")

    if assistant.is_agentic and hasattr(assistant.planning_agent, 'progress_callback'):
        assistant.planning_agent.progress_callback = callback
        if enable_verbose:
            assistant.planning_agent.verbose_callback = verbose_callback
        else:
            assistant.planning_agent.verbose_callback = None

# Check if API key is available
API_KEY_AVAILABLE = bool(os.environ.get("ANTHROPIC_API_KEY"))

# Initialize chatbot for chat interface (only if API key available)
chatbot_instance = None
chatbot_lock = threading.Lock()  # Lock to prevent concurrent chatbot access
if API_KEY_AVAILABLE:
    try:
        # Initialize with verbose=False to reduce log noise (focusing on shop)
        chatbot_instance = MealPlanningChatbot(verbose=False)
        logger.info("Chatbot initialized for chat interface (verbose mode disabled)")
    except Exception as e:
        logger.warning(f"Could not initialize chatbot: {e}")

# Progress tracking for streaming updates
progress_queues = {}  # session_id -> queue
progress_lock = threading.Lock()

# State change broadcasting for cross-tab synchronization
state_change_queues = {}  # tab_id -> queue
state_change_lock = threading.Lock()

# Shopping list generation locks (prevent duplicate work)
shopping_list_locks = {}  # meal_plan_id -> Lock
shopping_list_lock = threading.Lock()


def fetch_recipes_parallel(recipe_ids):
    """Fetch multiple recipes in parallel for faster enrichment."""
    recipes_map = {}

    def fetch_recipe(recipe_id):
        try:
            recipe = assistant.db.get_recipe(recipe_id)
            return (recipe_id, recipe)
        except Exception as e:
            logger.error(f"Error fetching recipe {recipe_id}: {e}")
            return (recipe_id, None)

    # Use ThreadPoolExecutor for parallel fetching
    with ThreadPoolExecutor(max_workers=min(10, len(recipe_ids))) as executor:
        futures = {executor.submit(fetch_recipe, recipe_id): recipe_id for recipe_id in recipe_ids}

        for future in as_completed(futures):
            recipe_id, recipe = future.result()
            if recipe:
                recipes_map[recipe_id] = recipe

    return recipes_map


def emit_progress(session_id: str, message: str, status: str = "progress"):
    """Emit a progress update to the client.

    Creates the queue if it doesn't exist to avoid race conditions where
    emit_progress is called before the EventSource connects.
    """
    with progress_lock:
        # Create queue if it doesn't exist (fixes race condition)
        if session_id not in progress_queues:
            progress_queues[session_id] = queue.Queue()
            logger.debug(f"Created progress queue for session {session_id} in emit_progress")
        progress_queues[session_id].put({
            "status": status,
            "message": message,
        })


def get_progress_queue(session_id: str) -> queue.Queue:
    """Get or create a progress queue for a session."""
    with progress_lock:
        if session_id not in progress_queues:
            progress_queues[session_id] = queue.Queue()
        return progress_queues[session_id]


def cleanup_progress_queue(session_id: str):
    """Clean up a progress queue."""
    with progress_lock:
        if session_id in progress_queues:
            del progress_queues[session_id]


@app.route('/api/progress-stream/<session_id>')
@login_required
def progress_stream(session_id):
    """Server-Sent Events endpoint for progress updates."""
    # session_id comes from URL path parameter

    def generate():
        progress_queue = get_progress_queue(session_id)

        try:
            while True:
                try:
                    # Wait for progress updates (with timeout)
                    update = progress_queue.get(timeout=30)

                    # Send as SSE
                    yield f"data: {json.dumps(update)}\n\n"

                    # If this is the completion event, close stream
                    if update.get("status") in ["complete", "error"]:
                        break

                except queue.Empty:
                    # Send keepalive
                    yield f"data: {json.dumps({'status': 'keepalive'})}\n\n"

        except GeneratorExit:
            # Client disconnected
            cleanup_progress_queue(session_id)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable proxy buffering (critical for Cloud Run)
            'Connection': 'keep-alive',
        }
    )


def broadcast_state_change(event_type: str, data: dict):
    """Broadcast a state change event to all listening tabs."""
    with state_change_lock:
        for tab_id, tab_queue in list(state_change_queues.items()):
            try:
                tab_queue.put({
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Error broadcasting to tab {tab_id}: {e}")


def get_state_change_queue(tab_id: str) -> queue.Queue:
    """Get or create a state change queue for a tab."""
    with state_change_lock:
        if tab_id not in state_change_queues:
            state_change_queues[tab_id] = queue.Queue()
        return state_change_queues[tab_id]


def cleanup_state_change_queue(tab_id: str):
    """Clean up a state change queue."""
    with state_change_lock:
        if tab_id in state_change_queues:
            del state_change_queues[tab_id]


@app.route('/api/state-stream')
@login_required
def state_stream():
    """Server-Sent Events endpoint for cross-tab state synchronization."""
    tab_id = request.args.get('tab_id', str(uuid.uuid4()))

    def generate():
        state_queue = get_state_change_queue(tab_id)

        try:
            while True:
                try:
                    # Wait for state changes (with timeout for keepalive)
                    update = state_queue.get(timeout=30)

                    # Send as SSE
                    yield f"data: {json.dumps(update)}\n\n"

                except queue.Empty:
                    # Send keepalive
                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"

        except GeneratorExit:
            # Client disconnected
            cleanup_state_change_queue(tab_id)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable proxy buffering (critical for Cloud Run)
            'Connection': 'keep-alive',
        }
    )


def restore_session_from_db():
    """
    Restore session data from database if session IDs are missing.
    This handles cases where user returns after closing browser.
    Also updates session to latest plan if a newer one exists.
    """
    user_id = session.get('user_id', 1)
    # Always get the most recent meal plan and update session if newer
    recent_plans = assistant.db.get_recent_meal_plans(user_id=user_id, limit=1)

    # If user cleared plan, only show plans created AFTER the clear
    if session.get('plan_cleared'):
        if not recent_plans:
            return  # No plans at all, stay cleared

        # Check if the most recent plan is the same one that was cleared
        cleared_plan_id = session.get('cleared_plan_id')
        latest_plan_id = recent_plans[0].id

        if cleared_plan_id == latest_plan_id:
            # Same plan that was cleared, don't restore it
            logger.info(f"Honoring plan_cleared flag - not restoring {latest_plan_id}")
            return
        else:
            # A NEW plan was created after clearing, show it
            session.pop('plan_cleared', None)
            session.pop('cleared_plan_id', None)
            logger.info(f"New plan created after clear: {latest_plan_id} (was {cleared_plan_id})")

    if recent_plans:
        latest_plan_id = recent_plans[0].id
        current_session_plan_id = session.get('meal_plan_id')

        if current_session_plan_id != latest_plan_id:
            session['meal_plan_id'] = latest_plan_id
            logger.info(f"Updated session to latest meal plan: {latest_plan_id} (was: {current_session_plan_id})")
        elif 'meal_plan_id' not in session:
            session['meal_plan_id'] = latest_plan_id
            logger.info(f"Restored meal_plan_id from database: {session['meal_plan_id']}")

            # Also try to restore shopping list for this plan
            if 'shopping_list_id' not in session:
                meal_plan = recent_plans[0]
                # Query for grocery list by week_of
                with sqlite3.connect(assistant.db.user_db) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM grocery_lists WHERE week_of = ? AND user_id = ? ORDER BY created_at DESC LIMIT 1",
                        (meal_plan.week_of, user_id)
                    )
                    row = cursor.fetchone()
                    if row:
                        session['shopping_list_id'] = row['id']
                        logger.info(f"Restored shopping_list_id from database: {session['shopping_list_id']}")


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page with database authentication."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Try database authentication first
        user = assistant.db.get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            session['username'] = username
            session['user_id'] = user['id']
            logger.info(f"User {username} (ID: {user['id']}) logged in successfully via database")
            return redirect('/plan')

        # Fallback to hardcoded users (for backward compatibility during migration)
        if username in USERS and USERS[username] == password:
            session['username'] = username
            session['user_id'] = USER_IDS.get(username, 1)
            logger.info(f"User {username} (ID: {session['user_id']}) logged in via hardcoded auth")
            return redirect('/plan')

        return render_template('login.html', error='Invalid username or password')

    # If already logged in, redirect to plan
    if 'username' in session:
        return redirect('/plan')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        if not username or not password:
            return render_template('register.html', error='Username and password are required')

        if len(username) < 3:
            return render_template('register.html', error='Username must be at least 3 characters')

        if len(password) < 4:
            return render_template('register.html', error='Password must be at least 4 characters')

        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')

        # Check if username already exists
        existing_user = assistant.db.get_user_by_username(username)
        if existing_user:
            return render_template('register.html', error='Username already taken')

        # Create user
        password_hash = generate_password_hash(password)
        user_id = assistant.db.create_user(username, password_hash)

        if user_id:
            logger.info(f"New user registered: {username} (ID: {user_id})")
            # Auto-login after registration
            session['username'] = username
            session['user_id'] = user_id
            return redirect('/plan')
        else:
            return render_template('register.html', error='Failed to create account. Please try again.')

    # If already logged in, redirect to plan
    if 'username' in session:
        return redirect('/plan')

    return render_template('register.html')


@app.route('/logout')
def logout():
    """Logout and clear session."""
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"User {username} logged out")
    from flask import redirect
    return redirect('/login')


@app.route('/health')
def health_check():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200


@app.route('/')
@login_required
def index():
    """Home page - redirect to plan."""
    from flask import redirect
    return redirect('/plan')


@app.route('/plan')
@login_required
def plan_page():
    """Meal planning page."""
    # Restore session from DB if needed
    restore_session_from_db()

    # Check if user needs onboarding (must use their user_id, not default)
    user_id = session.get('user_id', 1)
    needs_onboarding = not check_onboarding_status(assistant.db, user_id=user_id)

    # Get current meal plan if exists
    current_plan = None

    # Try loading from snapshot first
    # Note: snapshot_id == meal_plan_id in this codebase
    # IMPORTANT: Chatbot's current plan takes priority over stale session data
    # (background threads can't update session, so session may be outdated)
    snapshot_id = session.get('snapshot_id')
    if chatbot_instance and chatbot_instance.current_meal_plan_id:
        if chatbot_instance.current_meal_plan_id != snapshot_id:
            logger.info(f"[/plan] Updating stale session snapshot_id: {snapshot_id} -> {chatbot_instance.current_meal_plan_id}")
            snapshot_id = chatbot_instance.current_meal_plan_id
            session['snapshot_id'] = snapshot_id  # Sync session

    # Load plan from snapshot (snapshots are now the only source)
    if snapshot_id:
        try:
            snapshot = assistant.db.get_snapshot(snapshot_id)
            if snapshot and snapshot.get('planned_meals'):
                log_snapshot_load(snapshot_id)

                # Transform snapshot data to frontend format
                enriched_meals = []
                for meal_dict in snapshot['planned_meals']:
                    # Flatten recipe fields for frontend compatibility
                    if 'recipe' in meal_dict and meal_dict['recipe']:
                        recipe = meal_dict['recipe']
                        meal_dict['recipe_id'] = recipe.get('id')
                        meal_dict['recipe_name'] = recipe.get('name')
                        meal_dict['description'] = recipe.get('description')
                        meal_dict['estimated_time'] = recipe.get('estimated_time')
                        meal_dict['cuisine'] = recipe.get('cuisine')
                        meal_dict['difficulty'] = recipe.get('difficulty')

                    # Check for variant (modified recipe)
                    if 'variant' in meal_dict and meal_dict['variant']:
                        meal_dict['has_variant'] = True
                        variant = meal_dict['variant']
                        # Use compiled recipe name for display
                        if 'compiled_recipe' in variant:
                            meal_dict['recipe_name'] = variant['compiled_recipe'].get('name', meal_dict.get('recipe_name'))
                            # Use variant ID for cook link
                            meal_dict['recipe_id'] = variant.get('variant_id', meal_dict.get('recipe_id'))
                    else:
                        meal_dict['has_variant'] = False

                    # Format date nicely (e.g., "Friday, November 1")
                    date_str = meal_dict.get('date')
                    if date_str:
                        from datetime import datetime
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        meal_dict['meal_date'] = date_obj.strftime('%A, %B %d')
                    else:
                        meal_dict['meal_date'] = date_str
                    enriched_meals.append(meal_dict)

                current_plan = {
                    'id': snapshot['id'],
                    'week_of': snapshot['week_of'],
                    'meals': enriched_meals,
                }
        except Exception as e:
            logger.error(f"Error loading meal plan from snapshot: {e}")

    return render_template(
        'plan.html',
        current_plan=current_plan,
        api_key_available=API_KEY_AVAILABLE,
        needs_onboarding=needs_onboarding,
    )


@app.route('/shop')
@login_required
def shop_page():
    """Shopping list page."""
    # Restore session from DB if needed
    restore_session_from_db()

    # Load shopping list from snapshot (snapshots are now the only source)
    current_list = None

    # IMPORTANT: Chatbot's current plan takes priority over stale session data
    snapshot_id = session.get('snapshot_id')
    if chatbot_instance and chatbot_instance.current_meal_plan_id:
        if chatbot_instance.current_meal_plan_id != snapshot_id:
            logger.info(f"[/shop] Updating stale session snapshot_id: {snapshot_id} -> {chatbot_instance.current_meal_plan_id}")
            snapshot_id = chatbot_instance.current_meal_plan_id
            session['snapshot_id'] = snapshot_id  # Sync session

    if snapshot_id:
        try:
            snapshot = assistant.db.get_snapshot(snapshot_id)
            if snapshot and snapshot.get('grocery_list'):
                current_list = snapshot['grocery_list']
                log_snapshot_load(snapshot_id)
                logger.info(f"Shop tab loaded from snapshot {snapshot_id}")
            elif snapshot and not snapshot.get('grocery_list'):
                logger.info(f"Snapshot exists but grocery_list is None (still generating)")
        except Exception as e:
            logger.error(f"Error loading snapshot: {e}", exc_info=True)

    return render_template(
        'shop.html',
        current_list=current_list,
        meal_plan_id=session.get('meal_plan_id'),
        api_key_available=API_KEY_AVAILABLE,
    )


@app.route('/cook')
@login_required
def cook_page():
    """Cooking guide page."""
    # Restore session from DB if needed
    restore_session_from_db()

    # Get current meal plan if exists
    current_plan = None

    # Try loading from snapshot first
    # Note: snapshot_id == meal_plan_id in this codebase
    # IMPORTANT: Chatbot's current plan takes priority over stale session data
    snapshot_id = session.get('snapshot_id')
    if chatbot_instance and chatbot_instance.current_meal_plan_id:
        if chatbot_instance.current_meal_plan_id != snapshot_id:
            logger.info(f"[/cook] Updating stale session snapshot_id: {snapshot_id} -> {chatbot_instance.current_meal_plan_id}")
            snapshot_id = chatbot_instance.current_meal_plan_id
            session['snapshot_id'] = snapshot_id  # Sync session

    # Load plan from snapshot (snapshots are now the only source)
    if snapshot_id:
        try:
            snapshot = assistant.db.get_snapshot(snapshot_id)
            if snapshot and snapshot.get('planned_meals'):
                log_snapshot_load(snapshot_id)

                # Transform snapshot data to frontend format
                enriched_meals = []
                for meal_dict in snapshot['planned_meals']:
                    # Check for variant first - use compiled_recipe if exists
                    variant = meal_dict.get('variant')
                    if variant and variant.get('compiled_recipe'):
                        # Use variant data for Cook page
                        compiled = variant['compiled_recipe']
                        meal_dict['recipe_id'] = variant.get('variant_id', compiled.get('id'))
                        meal_dict['recipe_name'] = compiled.get('name')
                        meal_dict['description'] = compiled.get('description')
                        meal_dict['estimated_time'] = compiled.get('estimated_time')
                        meal_dict['cuisine'] = compiled.get('cuisine')
                        meal_dict['difficulty'] = compiled.get('difficulty')
                        meal_dict['recipe'] = compiled  # Use compiled recipe for embedding
                        meal_dict['has_variant'] = True
                        meal_dict['warnings'] = variant.get('warnings', [])
                        logger.info(f"[COOK] Using variant for {meal_dict.get('date')}: {compiled.get('name')}")
                    elif 'recipe' in meal_dict and meal_dict['recipe']:
                        # Flatten recipe fields for frontend compatibility
                        recipe = meal_dict['recipe']
                        meal_dict['recipe_id'] = recipe.get('id')
                        meal_dict['recipe_name'] = recipe.get('name')
                        meal_dict['description'] = recipe.get('description')
                        meal_dict['estimated_time'] = recipe.get('estimated_time')
                        meal_dict['cuisine'] = recipe.get('cuisine')
                        meal_dict['difficulty'] = recipe.get('difficulty')
                        meal_dict['has_variant'] = False

                    # Format date nicely (e.g., "Friday, November 1")
                    date_str = meal_dict.get('date')
                    if date_str:
                        from datetime import datetime
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        meal_dict['meal_date'] = date_obj.strftime('%A, %B %d')
                    else:
                        meal_dict['meal_date'] = date_str
                    enriched_meals.append(meal_dict)

                current_plan = {
                    'id': snapshot['id'],
                    'week_of': snapshot['week_of'],
                    'meals': enriched_meals,
                }
        except Exception as e:
            logger.error(f"Error loading meal plan from snapshot for cook page: {e}")

    return render_template(
        'cook.html',
        current_plan=current_plan,
        api_key_available=API_KEY_AVAILABLE,
    )


@app.route('/settings')
@login_required
def settings_page():
    """Settings page."""
    user_id = session.get('user_id', 1)
    try:
        profile = assistant.db.get_user_profile(user_id=user_id)
        cuisine_prefs = assistant.db.get_cuisine_preferences(user_id=user_id)
        favorite_recipes = assistant.db.get_favorite_recipes(user_id=user_id, limit=10)

        return render_template(
            'settings.html',
            profile=profile,
            cuisine_preferences=cuisine_prefs,
            favorite_recipes=favorite_recipes,
            api_key_available=API_KEY_AVAILABLE,
        )
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return render_template(
            'settings.html',
            profile=None,
            cuisine_preferences=[],
            favorite_recipes=[],
            api_key_available=API_KEY_AVAILABLE,
        )


# API Routes
@app.route('/api/plan', methods=['POST'])
@login_required
def api_plan_meals():
    """Plan meals for the week."""
    try:
        data = request.json
        week_of = data.get('week_of')
        num_days = data.get('num_days', 7)
        include_explanation = data.get('include_explanation', False)  # Default to False for speed

        # If no week specified, default to next Monday
        if not week_of:
            today = datetime.now()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_monday = today + timedelta(days=days_until_monday)
            week_of = next_monday.strftime("%Y-%m-%d")

        logger.info(f"Planning meals for {week_of}, {num_days} days")

        result = assistant.plan_week(week_of=week_of, num_days=num_days)

        if result["success"]:
            # Store meal plan ID in session
            session['meal_plan_id'] = result['meal_plan_id']

            # Create snapshot for the new meal plan
            user_id = session.get('user_id', 1)
            try:
                # Load the MealPlan from database
                meal_plan = assistant.db.get_meal_plan(result['meal_plan_id'], user_id=user_id)
                if meal_plan:
                    # Build snapshot dict from MealPlan
                    snapshot = {
                        'id': meal_plan.id,
                        'user_id': user_id,
                        'week_of': meal_plan.week_of,
                        'created_at': meal_plan.created_at.isoformat(),
                        'version': 1,
                        'planned_meals': [meal.to_dict() for meal in meal_plan.meals],
                        'grocery_list': None,  # Will be filled by background thread
                    }

                    # Save snapshot
                    snapshot_id = assistant.db.save_snapshot(snapshot)
                    session['snapshot_id'] = snapshot_id
                    log_snapshot_save(snapshot_id, user_id, meal_plan.week_of)
                    logger.info(f"Created snapshot {snapshot_id} for meal plan {result['meal_plan_id']}")
                else:
                    logger.warning(f"Could not load meal plan {result['meal_plan_id']} for snapshot")
            except Exception as e:
                logger.error(f"Error creating snapshot: {e}", exc_info=True)
                # Don't fail the request if snapshot creation fails

            # Broadcast state change to all tabs
            broadcast_state_change('meal_plan_changed', {
                'meal_plan_id': result['meal_plan_id'],
                'week_of': week_of
            })
            logger.info(f"Broadcasted meal_plan_changed event")

            # Auto-regenerate shopping list in BACKGROUND THREAD (same as swap-meal)
            def regenerate_shopping_list_async():
                """Background thread to auto-generate shopping list for new plan."""
                try:
                    meal_plan_id = result['meal_plan_id']
                    logger.info(f"[Background] Auto-generating shopping list for plan {meal_plan_id}")

                    # Update snapshot after shopping list generation
                    # Run shopping agent (still writes to legacy grocery_lists table for now)
                    shop_result = assistant.create_shopping_list(meal_plan_id)

                    if shop_result.get("success"):
                        new_shopping_list_id = shop_result["grocery_list_id"]
                        logger.info(f"[Background] Auto-generated shopping list: {new_shopping_list_id}")

                        # Update snapshot with grocery list
                        if 'snapshot_id' in session:
                            try:
                                snapshot_id = session['snapshot_id']
                                snapshot = assistant.db.get_snapshot(snapshot_id)

                                if snapshot:
                                    # Load the grocery list and add to snapshot
                                    grocery_list = assistant.db.get_grocery_list(new_shopping_list_id, user_id=user_id)
                                    if grocery_list:
                                        snapshot['grocery_list'] = grocery_list.to_dict()
                                        snapshot['updated_at'] = datetime.now().isoformat()
                                        assistant.db.save_snapshot(snapshot)
                                        logger.info(f"[Background] Updated snapshot {snapshot_id} with grocery list")
                                else:
                                    logger.warning(f"[Background] Snapshot not found: {snapshot_id}")
                            except Exception as e:
                                logger.error(f"[Background] Error updating snapshot with grocery list: {e}", exc_info=True)

                        # Broadcast shopping list change to all tabs
                        broadcast_state_change('shopping_list_changed', {
                            'shopping_list_id': new_shopping_list_id,
                            'meal_plan_id': meal_plan_id
                        })
                        logger.info(f"[Background] Broadcasted shopping_list_changed event")
                    else:
                        logger.error(f"[Background] Shopping list generation failed: {shop_result.get('error')}")
                except Exception as e:
                    logger.error(f"[Background] Error auto-generating shopping list: {e}", exc_info=True)

            # Start background thread (daemon=True so it doesn't block Flask shutdown)
            thread = threading.Thread(target=regenerate_shopping_list_async, daemon=True)
            thread.start()
            logger.info("Started background thread for shopping list generation")

            # Get explanation only if requested (saves ~3-5s per plan)
            if include_explanation and assistant.is_agentic:
                logger.info("Generating plan explanation...")
                explanation = assistant.planning_agent.explain_plan(result['meal_plan_id'])
                result['explanation'] = explanation
            else:
                logger.info("Skipping plan explanation (not requested)")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error planning meals: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/swap-meal', methods=['POST'])
@login_required
def api_swap_meal():
    """Swap a meal in the current plan."""
    try:
        data = request.json
        meal_plan_id = session.get('meal_plan_id')

        if not meal_plan_id:
            return jsonify({"success": False, "error": "No active meal plan"}), 400

        result = assistant.planning_agent.swap_meal(
            meal_plan_id=meal_plan_id,
            date=data['date'],
            requirements=data['requirements'],
        )

        if result.get("success"):
            user_id = session.get('user_id', 1)

            # Invalidate old shopping list (meal plan changed, list is stale)
            if 'shopping_list_id' in session:
                logger.info(f"Clearing stale shopping_list_id from session after swap")
                session.pop('shopping_list_id', None)

            # Update snapshot after swap
            if 'snapshot_id' in session:
                try:
                    snapshot_id = session['snapshot_id']
                    snapshot = assistant.db.get_snapshot(snapshot_id)

                    if snapshot:
                        # Load updated meal plan from legacy table
                        meal_plan = assistant.db.get_meal_plan(meal_plan_id, user_id=user_id)
                        if meal_plan:
                            # Update snapshot's planned_meals with new meal data
                            snapshot['planned_meals'] = [m.to_dict() for m in meal_plan.meals]
                            assistant.db.save_snapshot(snapshot)
                            log_snapshot_save(snapshot_id, snapshot['user_id'], snapshot['week_of'])
                            logger.info(f"Updated snapshot after meal swap: {data['date']}")
                except Exception as e:
                    logger.error(f"Failed to update snapshot after swap: {e}")

            # Broadcast meal plan change immediately
            broadcast_state_change('meal_plan_changed', {
                'meal_plan_id': meal_plan_id,
                'date_changed': data['date']
            })
            logger.info(f"Broadcasted meal_plan_changed event")

            # Capture snapshot_id and user_id for background thread
            snapshot_id_for_bg = session.get('snapshot_id')
            user_id_for_bg = user_id

            # Auto-regenerate shopping list in BACKGROUND THREAD
            def regenerate_shopping_list_async():
                """Background thread to regenerate shopping list and broadcast."""
                try:
                    logger.info(f"[Background] Regenerating shopping list for meal plan {meal_plan_id}")
                    shop_result = assistant.create_shopping_list(meal_plan_id)

                    if shop_result.get("success"):
                        new_shopping_list_id = shop_result["grocery_list_id"]
                        logger.info(f"[Background] Auto-generated shopping list: {new_shopping_list_id}")

                        # Update snapshot with new grocery list
                        if snapshot_id_for_bg:
                            try:
                                snapshot = assistant.db.get_snapshot(snapshot_id_for_bg)
                                if snapshot:
                                    grocery_list = assistant.db.get_grocery_list(new_shopping_list_id, user_id=user_id_for_bg)
                                    if grocery_list:
                                        snapshot['grocery_list'] = grocery_list.to_dict()
                                        snapshot['updated_at'] = datetime.now().isoformat()
                                        assistant.db.save_snapshot(snapshot)
                                        log_snapshot_save(snapshot_id_for_bg, snapshot['user_id'], snapshot['week_of'])
                                        logger.info(f"[Background] Updated snapshot grocery list")
                            except Exception as e:
                                logger.error(f"[Background] Failed to update snapshot grocery list: {e}")

                        # Broadcast shopping list changed event
                        broadcast_state_change('shopping_list_changed', {
                            'shopping_list_id': new_shopping_list_id,
                            'meal_plan_id': meal_plan_id,
                        })
                        logger.info(f"[Background] Broadcasted shopping_list_changed event")
                    else:
                        logger.warning(f"[Background] Failed to auto-generate shopping list: {shop_result.get('error')}")
                except Exception as e:
                    logger.error(f"[Background] Error auto-generating shopping list: {e}")

            # Start background thread
            thread = threading.Thread(target=regenerate_shopping_list_async, daemon=True)
            thread.start()
            logger.info("Started background thread for shopping list regeneration")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error swapping meal: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/swap-meal-direct', methods=['POST'])
@login_required
def api_swap_meal_direct():
    """
    Direct swap without LLM - instant response.

    Request body:
        date: Date of meal to swap (YYYY-MM-DD)
        new_recipe_id: ID of the recipe to swap in

    This bypasses LLM selection for when user has already chosen a recipe.
    """
    try:
        data = request.json
        meal_plan_id = session.get('meal_plan_id')
        user_id = session.get('user_id', 1)

        if not meal_plan_id:
            return jsonify({"success": False, "error": "No active meal plan"}), 400

        date = data.get('date')
        new_recipe_id = data.get('new_recipe_id')

        if not date or not new_recipe_id:
            return jsonify({"success": False, "error": "Missing date or new_recipe_id"}), 400

        # Get the new recipe to return its name
        new_recipe = assistant.db.get_recipe(new_recipe_id)
        if not new_recipe:
            return jsonify({"success": False, "error": "Recipe not found"}), 404

        # Get old meal info before swap
        meal_plan = assistant.db.get_meal_plan(meal_plan_id, user_id=user_id)
        old_recipe_name = None
        if meal_plan:
            for meal in meal_plan.meals:
                if meal.date == date:
                    old_recipe_name = meal.recipe.name
                    break

        # Perform direct swap (no LLM)
        updated_plan = assistant.db.swap_meal_in_plan(
            meal_plan_id, date, new_recipe_id, user_id=user_id
        )

        if not updated_plan:
            return jsonify({"success": False, "error": "Failed to update meal plan"}), 500

        # Invalidate old shopping list (meal plan changed, list is stale)
        if 'shopping_list_id' in session:
            logger.info(f"Clearing stale shopping_list_id from session after direct swap")
            session.pop('shopping_list_id', None)

        # Update snapshot after swap
        if 'snapshot_id' in session:
            try:
                snapshot_id = session['snapshot_id']
                snapshot = assistant.db.get_snapshot(snapshot_id)

                if snapshot:
                    snapshot['planned_meals'] = [m.to_dict() for m in updated_plan.meals]
                    assistant.db.save_snapshot(snapshot)
                    log_snapshot_save(snapshot_id, snapshot['user_id'], snapshot['week_of'])
                    logger.info(f"Updated snapshot after direct meal swap: {date}")
            except Exception as e:
                logger.error(f"Failed to update snapshot after direct swap: {e}")

        # Broadcast meal plan change immediately
        broadcast_state_change('meal_plan_changed', {
            'meal_plan_id': meal_plan_id,
            'date_changed': date
        })
        logger.info(f"Broadcasted meal_plan_changed event (direct swap)")

        # Capture for background thread
        snapshot_id_for_bg = session.get('snapshot_id')
        user_id_for_bg = user_id

        # Auto-regenerate shopping list in BACKGROUND THREAD
        def regenerate_shopping_list_async():
            try:
                logger.info(f"[Background] Regenerating shopping list after direct swap")
                shop_result = assistant.create_shopping_list(meal_plan_id)

                if shop_result.get("success"):
                    new_shopping_list_id = shop_result["grocery_list_id"]
                    logger.info(f"[Background] Auto-generated shopping list: {new_shopping_list_id}")

                    if snapshot_id_for_bg:
                        try:
                            snapshot = assistant.db.get_snapshot(snapshot_id_for_bg)
                            if snapshot:
                                grocery_list = assistant.db.get_grocery_list(new_shopping_list_id, user_id=user_id_for_bg)
                                if grocery_list:
                                    snapshot['grocery_list'] = grocery_list.to_dict()
                                    snapshot['updated_at'] = datetime.now().isoformat()
                                    assistant.db.save_snapshot(snapshot)
                                    logger.info(f"[Background] Updated snapshot grocery list")
                        except Exception as e:
                            logger.error(f"[Background] Failed to update snapshot grocery list: {e}")

                    broadcast_state_change('shopping_list_changed', {
                        'shopping_list_id': new_shopping_list_id,
                        'meal_plan_id': meal_plan_id,
                    })
                    logger.info(f"[Background] Broadcasted shopping_list_changed event")
            except Exception as e:
                logger.error(f"[Background] Error auto-generating shopping list: {e}")

        thread = threading.Thread(target=regenerate_shopping_list_async, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "meal_plan_id": meal_plan_id,
            "date": date,
            "old_recipe": old_recipe_name,
            "new_recipe": new_recipe.name,
            "new_recipe_id": new_recipe_id,
        })

    except Exception as e:
        logger.error(f"Error in direct swap: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/meal-feedback', methods=['POST'])
@login_required
def api_submit_meal_feedback():
    """Submit user feedback for a cooked meal (ratings, notes, etc.)."""
    try:
        data = request.json
        date = data.get('date')
        meal_type = data.get('meal_type', 'dinner')

        if not date:
            return jsonify({"success": False, "error": "Date is required"}), 400

        # Find the meal_event for this date/meal_type (should exist from UPSERT in save_meal_plan)
        import sqlite3
        with sqlite3.connect(assistant.db.user_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM meal_events WHERE date = ? AND meal_type = ?",
                (date, meal_type)
            )
            row = cursor.fetchone()

            if row:
                # Update existing meal_event with feedback
                event_id = row['id']
                updates = {}

                if data.get('user_rating') is not None:
                    updates['user_rating'] = data['user_rating']
                if data.get('would_make_again') is not None:
                    updates['would_make_again'] = data['would_make_again']
                if data.get('notes') is not None:
                    updates['notes'] = data['notes']
                if data.get('servings_actual') is not None:
                    updates['servings_actual'] = data['servings_actual']
                if data.get('cooking_time_actual') is not None:
                    updates['cooking_time_actual'] = data['cooking_time_actual']

                # Build UPDATE query dynamically
                if updates:
                    set_clauses = ', '.join([f"{k} = ?" for k in updates.keys()])
                    values = list(updates.values()) + [event_id]

                    cursor.execute(
                        f"UPDATE meal_events SET {set_clauses} WHERE id = ?",
                        values
                    )
                    conn.commit()

                    logger.info(f"Updated meal_event {event_id} for {date} with feedback: {updates}")
                    return jsonify({
                        "success": True,
                        "message": "Feedback saved successfully",
                        "event_id": event_id
                    })
                else:
                    return jsonify({
                        "success": False,
                        "error": "No feedback data provided"
                    }), 400
            else:
                # No meal_event found - this meal wasn't planned
                logger.warning(f"No meal_event found for {date} {meal_type} - cannot save feedback")
                return jsonify({
                    "success": False,
                    "error": f"No planned meal found for {date}. Feedback can only be saved for planned meals."
                }), 404

    except Exception as e:
        logger.error(f"Error saving meal feedback: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/shop', methods=['POST'])
@login_required
def api_create_shopping_list():
    """Create shopping list from meal plan."""
    try:
        data = request.json
        meal_plan_id = data.get('meal_plan_id') or session.get('meal_plan_id')
        scaling_instructions = data.get('scaling_instructions')

        if not meal_plan_id:
            return jsonify({"success": False, "error": "No meal plan available"}), 400

        user_id = session.get('user_id', 1)

        # Check if already exists (cache check)
        if not scaling_instructions and session.get('shopping_list_id'):
            # Return cached shopping list
            existing_list = assistant.db.get_grocery_list(session['shopping_list_id'], user_id=user_id)
            if existing_list:
                logger.info(f"Returning cached shopping list: {session['shopping_list_id']}")
                return jsonify({
                    "success": True,
                    "grocery_list_id": session['shopping_list_id'],
                    "cached": True
                })

        # Acquire lock to prevent duplicate generation
        with shopping_list_lock:
            if meal_plan_id not in shopping_list_locks:
                shopping_list_locks[meal_plan_id] = threading.Lock()

        lock = shopping_list_locks[meal_plan_id]
        if not lock.acquire(blocking=False):
            logger.warning(f"Shopping list already being generated for {meal_plan_id}")
            return jsonify({
                "success": False,
                "error": "Shopping list already being generated. Please wait."
            }), 409

        try:
            logger.info(f"Creating shopping list for {meal_plan_id}")

            # DEBUG: Check meal plan details
            meal_plan = assistant.db.get_meal_plan(meal_plan_id, user_id=user_id)
            if meal_plan:
                logger.debug(f"Meal plan has {len(meal_plan.meals)} meals")
                for i, meal in enumerate(meal_plan.meals):
                    logger.debug(f"  Meal {i+1}: {meal.recipe.name} (ID: {meal.recipe.id})")
                    logger.debug(f"    Enriched: {bool(meal.recipe.ingredients_structured)}")
                    logger.debug(f"    Raw ingredients count: {len(meal.recipe.ingredients_raw)}")
            else:
                logger.error(f"Meal plan {meal_plan_id} not found!")

            if scaling_instructions:
                logger.info(f"Scaling: {scaling_instructions}")

            logger.info("Calling assistant.create_shopping_list()...")
            result = assistant.create_shopping_list(
                meal_plan_id,
                scaling_instructions=scaling_instructions
            )
            logger.info(f"Shopping list creation result: success={result.get('success')}")

            if result.get("success"):
                logger.debug(f"Shopping list ID: {result.get('grocery_list_id')}")
                # Store shopping list ID in session
                session['shopping_list_id'] = result['grocery_list_id']

                # Broadcast state change to all tabs
                broadcast_state_change('shopping_list_changed', {
                    'shopping_list_id': result['grocery_list_id'],
                    'meal_plan_id': meal_plan_id
                })
            else:
                logger.error(f"Shopping list creation failed: {result.get('error')}")

            return jsonify(result)
        finally:
            lock.release()

    except Exception as e:
        logger.error(f"Error creating shopping list: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/cook/<recipe_id>', methods=['GET'])
@login_required
def api_get_cooking_guide(recipe_id):
    """Get cooking guide for a recipe.

    Supports variant IDs (variant:{snapshot_id}:{date}:{meal_type}).
    For variants, returns the compiled_recipe from the snapshot.
    """
    try:
        logger.info(f"[VARIANT_LOOKUP] Getting cooking guide for {recipe_id}")

        # Check if this is a variant ID
        if recipe_id.startswith('variant:'):
            from patch_engine import parse_variant_id

            try:
                snapshot_id, date, meal_type = parse_variant_id(recipe_id)
                logger.info(f"[VARIANT_LOOKUP] Parsed variant: snapshot={snapshot_id}, date={date}, meal={meal_type}")

                # Load snapshot
                snapshot = assistant.db.get_snapshot(snapshot_id)
                if not snapshot:
                    logger.warning(f"[VARIANT_LOOKUP] Snapshot not found: {snapshot_id}")
                    return jsonify({"success": False, "error": f"Snapshot not found: {snapshot_id}"}), 404

                # Find planned meal matching date and meal_type
                planned_meals = snapshot.get('planned_meals', [])
                matching_meal = None
                for meal in planned_meals:
                    if meal.get('date') == date and meal.get('meal_type') == meal_type:
                        matching_meal = meal
                        break

                if not matching_meal:
                    logger.warning(f"[VARIANT_LOOKUP] No meal found for {date}/{meal_type}")
                    return jsonify({"success": False, "error": f"No meal found for {date}/{meal_type}"}), 404

                # Check for variant
                variant = matching_meal.get('variant')
                if not variant or 'compiled_recipe' not in variant:
                    logger.warning(f"[VARIANT_LOOKUP] No variant found for {date}/{meal_type}")
                    return jsonify({"success": False, "error": f"No variant found for {date}/{meal_type}"}), 404

                # Return the compiled recipe
                compiled_recipe = variant['compiled_recipe']
                logger.info(f"[VARIANT_LOOKUP] Found variant: {compiled_recipe.get('name')}")

                return jsonify({
                    "success": True,
                    "recipe": compiled_recipe,
                    "is_variant": True,
                    "variant_id": recipe_id,
                    "warnings": variant.get('warnings', []),
                })

            except ValueError as e:
                logger.error(f"[VARIANT_LOOKUP] Invalid variant ID: {e}")
                return jsonify({"success": False, "error": str(e)}), 400

        # Regular recipe ID - use standard cooking guide
        result = assistant.get_cooking_guide(recipe_id)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting cooking guide: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/clear-variant', methods=['POST'])
@login_required
def api_clear_variant():
    """Clear a variant from a planned meal, reverting to base recipe.

    Request body:
        snapshot_id: Snapshot ID
        date: Date string (YYYY-MM-DD)
        meal_type: Meal type (breakfast/lunch/dinner/snack)
    """
    try:
        data = request.json
        snapshot_id = data.get('snapshot_id')
        date = data.get('date')
        meal_type = data.get('meal_type')

        if not all([snapshot_id, date, meal_type]):
            return jsonify({
                "success": False,
                "error": "Missing required fields: snapshot_id, date, meal_type"
            }), 400

        # Load snapshot
        snapshot = assistant.db.get_snapshot(snapshot_id)
        if not snapshot:
            return jsonify({"success": False, "error": f"Snapshot not found: {snapshot_id}"}), 404

        # Clear the variant
        from patch_engine import clear_variant
        cleared = clear_variant(snapshot, date, meal_type)

        if cleared:
            # Save updated snapshot
            snapshot['updated_at'] = datetime.now().isoformat()
            assistant.db.save_snapshot(snapshot)

            # Broadcast update to other tabs
            broadcast_state_change('meal_plan_changed', {
                'snapshot_id': snapshot_id,
                'date': date,
                'meal_type': meal_type,
                'action': 'variant_cleared',
            })

            return jsonify({
                "success": True,
                "message": f"Variant cleared for {date} {meal_type}",
            })
        else:
            return jsonify({
                "success": True,
                "message": f"No variant to clear for {date} {meal_type}",
            })

    except Exception as e:
        logger.error(f"Error clearing variant: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/search-recipes', methods=['POST'])
@login_required
def api_search_recipes():
    """Search for recipes."""
    try:
        data = request.json

        recipes = assistant.db.search_recipes(
            query=data.get('query'),
            max_time=data.get('max_time'),
            tags=data.get('tags'),
            limit=data.get('limit', 20),
        )

        return jsonify({
            "success": True,
            "recipes": [recipe.to_dict() for recipe in recipes],
        })

    except Exception as e:
        logger.error(f"Error searching recipes: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/browse-recipes', methods=['GET'])
@login_required
def api_browse_recipes():
    """
    Browse recipes with advanced filtering (no LLM involved).

    Query params:
        query: Text search in name/description/ingredients
        include_tags: Comma-separated tags recipes MUST have (e.g., "main-dish,whole-chicken")
        exclude_tags: Comma-separated tags recipes must NOT have (e.g., "salads")
        max_time: Maximum cooking time in minutes
        limit: Max results (default 20)

    Example: /api/browse-recipes?query=chicken&include_tags=main-dish,whole-chicken&exclude_tags=salads
    """
    try:
        query = request.args.get('query')
        include_tags_str = request.args.get('include_tags', '')
        exclude_tags_str = request.args.get('exclude_tags', '')
        max_time = request.args.get('max_time', type=int)
        limit = request.args.get('limit', 20, type=int)

        # Parse comma-separated tags
        include_tags = [t.strip() for t in include_tags_str.split(',') if t.strip()] or None
        exclude_tags = [t.strip() for t in exclude_tags_str.split(',') if t.strip()] or None

        recipes = assistant.db.search_recipes(
            query=query,
            max_time=max_time,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
            limit=limit,
        )

        return jsonify({
            "success": True,
            "recipes": [recipe.to_dict() for recipe in recipes],
            "count": len(recipes),
            "filters": {
                "query": query,
                "include_tags": include_tags,
                "exclude_tags": exclude_tags,
                "max_time": max_time,
            }
        })

    except Exception as e:
        logger.error(f"Error browsing recipes: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/preferences', methods=['GET'])
@login_required
def api_get_preferences():
    """Get user preferences and stats."""
    user_id = session.get('user_id', 1)
    try:
        profile = assistant.db.get_user_profile(user_id=user_id)
        cuisine_prefs = assistant.db.get_cuisine_preferences(user_id=user_id)
        favorite_recipes = assistant.db.get_favorite_recipes(user_id=user_id, limit=10)

        return jsonify({
            "success": True,
            "profile": profile.to_dict() if profile else None,
            "cuisine_preferences": [pref.to_dict() for pref in cuisine_prefs],
            "favorite_recipes": [recipe.to_dict() for recipe in favorite_recipes],
        })

    except Exception as e:
        logger.error(f"Error getting preferences: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/meal-history', methods=['GET'])
@login_required
def api_get_meal_history():
    """Get meal history."""
    user_id = session.get('user_id', 1)
    try:
        weeks_back = request.args.get('weeks_back', default=4, type=int)

        history = assistant.db.get_meal_history(user_id=user_id, weeks_back=weeks_back)

        return jsonify({
            "success": True,
            "meals": [meal.to_dict() for meal in history],
        })

    except Exception as e:
        logger.error(f"Error getting meal history: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    """Chat with the AI assistant."""
    try:
        if not chatbot_instance:
            return jsonify({
                "success": False,
                "error": "Chat requires API key. Set ANTHROPIC_API_KEY environment variable."
            }), 400

        data = request.json
        message = data.get('message')
        session_id = data.get('session_id', 'default')
        selected_dates = data.get('selected_dates')  # Get selected dates from UI
        week_start = data.get('week_start')          # Get week start from UI
        context = data.get('context')                # Get page context (e.g., 'shop')
        verbose = data.get('verbose', False)         # Get verbose mode preference

        if not message:
            return jsonify({"success": False, "error": "No message provided"}), 400

        logger.info(f"Chat message: {message}")
        if context:
            logger.info(f"Chat context: {context}")
        if selected_dates:
            logger.info(f"Selected dates from UI: {selected_dates}")
        if week_start:
            logger.info(f"Week start from UI: {week_start}")

        # Store old IDs to detect changes
        old_meal_plan_id = chatbot_instance.current_meal_plan_id or session.get('meal_plan_id')
        old_shopping_list_id = chatbot_instance.current_shopping_list_id or session.get('shopping_list_id')

        # Restore IDs from session to chatbot ONLY if chatbot doesn't have them
        # (Don't overwrite chatbot's current state with stale session data)
        if not chatbot_instance.current_meal_plan_id and session.get('meal_plan_id'):
            chatbot_instance.current_meal_plan_id = session.get('meal_plan_id')
            logger.info(f"Restored meal_plan_id from session: {session.get('meal_plan_id')}")
        if not chatbot_instance.current_shopping_list_id and session.get('shopping_list_id'):
            chatbot_instance.current_shopping_list_id = session.get('shopping_list_id')
            logger.info(f"Restored shopping_list_id from session: {session.get('shopping_list_id')}")

        # Pass selected dates to chatbot for meal planning
        if selected_dates:
            chatbot_instance.selected_dates = selected_dates
        if week_start:
            chatbot_instance.week_start = week_start

        # Restore pending swap options from session
        if 'pending_swap_options' in session:
            chatbot_instance.pending_swap_options = session['pending_swap_options']
            logger.info("Restored pending_swap_options from session")

        # Set up verbose callback to emit to progress stream
        def verbose_callback(msg):
            emit_progress(session_id, msg, "verbose")

        chatbot_instance.verbose_callback = verbose_callback

        # Set up progress callback for this session (for agents)
        set_agent_progress_callback(session_id, enable_verbose=verbose)

        # Emit initial progress
        emit_progress(session_id, "Processing your request...")

        # Modify message if in shop context to prioritize add_extra_items
        actual_message = message
        if context == 'shop':
            actual_message = f"[SHOP MODE: User is on the shopping list page. For simple items like 'bread', 'milk', 'bananas', use add_extra_items tool, NOT recipe search or meal planning tools.] {message}"
            logger.info(f"Modified message for shop context: {actual_message}")

        # Process chat in background thread - return immediately
        import threading

        # Capture session data for background thread (session not accessible in thread)
        snapshot_id_for_bg = session.get('snapshot_id')
        user_id_for_bg = session.get('user_id', 1)

        # Pass snapshot_id to chatbot for variant operations
        # Note: snapshot_id == current_meal_plan_id in this codebase (both use mp_{week}_{timestamp})
        if not snapshot_id_for_bg and chatbot_instance.current_meal_plan_id:
            snapshot_id_for_bg = chatbot_instance.current_meal_plan_id
            logger.info(f"Using chatbot.current_meal_plan_id as snapshot_id: {snapshot_id_for_bg}")
        if snapshot_id_for_bg:
            chatbot_instance.current_snapshot_id = snapshot_id_for_bg
            logger.info(f"Set chatbot snapshot_id: {snapshot_id_for_bg}")

        def process_chat_in_background():
            """Process chat asynchronously and broadcast state changes."""
            try:
                # Acquire lock to prevent concurrent chatbot access (serializes requests)
                logger.info(f"[Background] Waiting for chatbot lock...")
                with chatbot_lock:
                    logger.info(f"[Background] Lock acquired - starting chatbot.chat() for message: {message[:50]}...")
                    response = chatbot_instance.chat(actual_message)
                    logger.info(f"[Background] Chatbot.chat() completed successfully")

                    # Check for state changes (inside lock to ensure consistent state)
                    plan_changed = False

                    # Check if meal plan was created or changed
                    if chatbot_instance.current_meal_plan_id:
                        if chatbot_instance.current_meal_plan_id != old_meal_plan_id:
                            plan_changed = True
                            logger.info(f"[Background] New meal plan created: {chatbot_instance.current_meal_plan_id}")
                        else:
                            # Same meal plan - always assume it was modified to refresh UI
                            plan_changed = True
                            logger.info(f"[Background] Plan interaction detected - refreshing UI")

                    # Create snapshot for chat-generated meal plans
                    if plan_changed and chatbot_instance.current_meal_plan_id:
                        try:
                            # Prefer chatbot's cached plan (has backup_recipes) over DB load
                            meal_plan = chatbot_instance.last_meal_plan
                            if not meal_plan or meal_plan.id != chatbot_instance.current_meal_plan_id:
                                # Fallback to DB if cache miss
                                meal_plan = assistant.db.get_meal_plan(chatbot_instance.current_meal_plan_id, user_id=user_id_for_bg)

                            if meal_plan:
                                # Serialize backup_recipes as lightweight objects for instant swap modal
                                backup_recipes_light = []
                                for category, recipes in meal_plan.backup_recipes.items():
                                    for recipe in recipes[:20]:
                                        if len(backup_recipes_light) >= 20:
                                            break
                                        diet_tags = [t for t in recipe.tags if t in (
                                            "vegetarian", "vegan", "gluten-free", "low-carb",
                                            "dairy-free", "keto", "healthy"
                                        )]
                                        backup_recipes_light.append({
                                            "id": recipe.id,
                                            "name": recipe.name,
                                            "estimated_time": recipe.estimated_time,
                                            "cuisine": recipe.cuisine,
                                            "diet_tags": diet_tags,
                                        })
                                    if len(backup_recipes_light) >= 20:
                                        break

                                snapshot = {
                                    'id': meal_plan.id,
                                    'user_id': user_id_for_bg,  # Use captured variable
                                    'week_of': meal_plan.week_of,
                                    'created_at': meal_plan.created_at.isoformat(),
                                    'version': 1,
                                    'planned_meals': [m.to_dict() for m in meal_plan.meals],
                                    'grocery_list': None,
                                    'backup_recipes': backup_recipes_light,  # For instant swap modal
                                }
                                new_snapshot_id = assistant.db.save_snapshot(snapshot)
                                # Update captured variable for nested thread
                                nonlocal snapshot_id_for_bg
                                snapshot_id_for_bg = new_snapshot_id
                                log_snapshot_save(new_snapshot_id, user_id_for_bg, meal_plan.week_of)
                                logger.info(f"[Background] Created snapshot {new_snapshot_id} with {len(backup_recipes_light)} backup recipes")
                        except Exception as e:
                            logger.error(f"[Background] Failed to create snapshot: {e}", exc_info=True)

                    # Broadcast meal plan change immediately
                    if plan_changed and chatbot_instance.current_meal_plan_id:
                        broadcast_state_change('meal_plan_changed', {
                            'meal_plan_id': chatbot_instance.current_meal_plan_id,
                        })
                        logger.info(f"[Background] Broadcasted meal_plan_changed event")

                    # Auto-regenerate shopping list in background if plan changed
                    if plan_changed and chatbot_instance.current_meal_plan_id and not chatbot_instance.pending_swap_options:
                        meal_plan_id = chatbot_instance.current_meal_plan_id

                        def regenerate_shopping_list_async():
                            """Nested background thread to regenerate shopping list."""
                            try:
                                logger.info(f"[Background-Shop] Regenerating shopping list for meal plan {meal_plan_id}")
                                shop_result = assistant.create_shopping_list(meal_plan_id)

                                if shop_result.get("success"):
                                    new_shopping_list_id = shop_result["grocery_list_id"]
                                    logger.info(f"[Background-Shop] Auto-generated shopping list: {new_shopping_list_id}")

                                    # Update chatbot state (with lock)
                                    with chatbot_lock:
                                        chatbot_instance.current_shopping_list_id = new_shopping_list_id

                                    # Update snapshot with grocery list
                                    if snapshot_id_for_bg:
                                        try:
                                            snapshot = assistant.db.get_snapshot(snapshot_id_for_bg)
                                            if snapshot:
                                                grocery_list = assistant.db.get_grocery_list(new_shopping_list_id, user_id=user_id_for_bg)
                                                if grocery_list:
                                                    snapshot['grocery_list'] = grocery_list.to_dict()
                                                    snapshot['updated_at'] = datetime.now().isoformat()
                                                    assistant.db.save_snapshot(snapshot)
                                                    log_snapshot_save(snapshot_id_for_bg, snapshot['user_id'], snapshot['week_of'])
                                                    logger.info(f"[Background-Shop] Updated snapshot {snapshot_id_for_bg} with grocery list")
                                        except Exception as e:
                                            logger.error(f"[Background-Shop] Failed to update snapshot: {e}", exc_info=True)

                                    # Broadcast shopping list changed event
                                    broadcast_state_change('shopping_list_changed', {
                                        'shopping_list_id': new_shopping_list_id,
                                        'meal_plan_id': meal_plan_id,
                                    })
                                    logger.info(f"[Background-Shop] Broadcasted shopping_list_changed event")
                                else:
                                    logger.warning(f"[Background-Shop] Failed to auto-generate shopping list: {shop_result.get('error')}")
                            except Exception as e:
                                logger.error(f"[Background-Shop] Error auto-generating shopping list: {e}")

                        # Start nested background thread for shopping list (daemon=False to complete)
                        shop_thread = threading.Thread(target=regenerate_shopping_list_async, daemon=False)
                        shop_thread.start()
                        logger.info("[Background] Started nested thread for shopping list regeneration")

                    # Emit completion with full state
                    emit_progress(session_id, response, "complete")
                    logger.info("[Background] Chat processing complete")

            except Exception as e:
                logger.error(f"[Background] Error in chatbot.chat(): {e}", exc_info=True)
                emit_progress(session_id, f"Error: {str(e)}", "error")

        # Start background processing (daemon=False to survive container shutdown)
        chat_thread = threading.Thread(target=process_chat_in_background, daemon=False)
        chat_thread.start()
        logger.info(f"Started background chat processing thread")

        # Return immediately - don't wait for completion
        return jsonify({
            "success": True,
            "message": "Processing request...",
            "session_id": session_id
        })

    except Exception as e:
        logger.error(f"Error in chat: {e}", exc_info=True)
        # Emit error progress
        if 'session_id' in locals():
            emit_progress(session_id, f"Error: {str(e)}", "error")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/onboarding/check', methods=['GET'])
@login_required
def api_onboarding_check():
    """Check if user needs onboarding."""
    user_id = session.get('user_id', 1)
    try:
        needs_onboarding = not check_onboarding_status(assistant.db, user_id=user_id)
        profile = assistant.db.get_user_profile(user_id=user_id)

        return jsonify({
            "success": True,
            "needs_onboarding": needs_onboarding,
            "profile": profile.to_dict() if profile else None,
        })

    except Exception as e:
        logger.error(f"Error checking onboarding: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/onboarding/start', methods=['POST'])
@login_required
def api_onboarding_start():
    """Start or get current onboarding step."""
    try:
        # Get or create onboarding flow in session
        if 'onboarding_flow' not in session:
            flow = OnboardingFlow(assistant.db)
            welcome = flow.start()
            # Store flow state in session
            session['onboarding_data'] = flow.profile_data
            session['onboarding_step'] = flow.current_step

            return jsonify({
                "success": True,
                "message": welcome,
                "step": 0,
                "total_steps": len(flow.steps),
            })
        else:
            # Return current state
            return jsonify({
                "success": True,
                "step": session.get('onboarding_step', 0),
                "message": "Onboarding in progress",
            })

    except Exception as e:
        logger.error(f"Error starting onboarding: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/onboarding/answer', methods=['POST'])
@login_required
def api_onboarding_answer():
    """Process onboarding answer and get next question."""
    try:
        data = request.json
        answer = data.get('answer')

        if not answer:
            return jsonify({"success": False, "error": "No answer provided"}), 400

        # Recreate flow from session
        flow = OnboardingFlow(assistant.db)
        flow.profile_data = session.get('onboarding_data', {})
        flow.current_step = session.get('onboarding_step', 0)

        # Process answer
        is_complete, message = flow.process_answer(answer)

        # Update session
        session['onboarding_data'] = flow.profile_data
        session['onboarding_step'] = flow.current_step

        if is_complete:
            # Clear onboarding session data
            session.pop('onboarding_data', None)
            session.pop('onboarding_step', None)

        return jsonify({
            "success": True,
            "is_complete": is_complete,
            "message": message,
            "step": flow.current_step,
            "total_steps": len(flow.steps),
        })

    except Exception as e:
        logger.error(f"Error processing onboarding answer: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/preferences/reset', methods=['POST'])
@login_required
def api_preferences_reset():
    """Reset preferences to trigger onboarding again."""
    try:
        user_id = session.get('user_id', 1)

        # Reset onboarding_completed flag in database
        with assistant.db._get_user_connection() as conn:
            conn.execute(
                "UPDATE user_profile SET onboarding_completed = FALSE WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

        # Clear all session data
        session.pop('onboarding_data', None)
        session.pop('onboarding_step', None)
        session.pop('onboarding_flow', None)
        session.pop('meal_plan_id', None)
        session.pop('shopping_list_id', None)

        return jsonify({
            "success": True,
            "message": "Preferences reset. Please complete onboarding again.",
        })

    except Exception as e:
        logger.error(f"Error resetting preferences: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/plan/current', methods=['GET'])
@login_required
def api_get_current_plan():
    """Get current meal plan with enriched data."""
    try:
        # Check chatbot's current plan first (source of truth), then fall back to session
        meal_plan_id = None
        if chatbot_instance and chatbot_instance.current_meal_plan_id:
            meal_plan_id = chatbot_instance.current_meal_plan_id
            # Update session to stay in sync
            if meal_plan_id != session.get('meal_plan_id'):
                session['meal_plan_id'] = meal_plan_id
                logger.info(f"[/api/plan/current] Using chatbot's current plan: {meal_plan_id}")

        # Fall back to session if chatbot doesn't have a plan
        if not meal_plan_id:
            meal_plan_id = session.get('meal_plan_id')
            logger.info(f"[/api/plan/current] Using session plan: {meal_plan_id}")

        if not meal_plan_id:
            return jsonify({"success": False, "error": "No active meal plan"}), 404

        user_id = session.get('user_id', 1)
        # Use get_effective_meal_plan to get variant data from snapshot
        meal_plan = assistant.db.get_effective_meal_plan(meal_plan_id, user_id=user_id)
        if not meal_plan:
            return jsonify({"success": False, "error": "Meal plan not found"}), 404

        # Use embedded Recipe objects from PlannedMeal (Phase 2 enhancement)
        # No need to fetch recipes separately - they're already embedded!
        # Sort meals by date to ensure chronological order in UI
        sorted_meals = sorted(meal_plan.meals, key=lambda m: m.date)
        enriched_meals = []
        for meal in sorted_meals:
            meal_dict = meal.to_dict()
            # Check for variant - use compiled_recipe if exists
            if meal.variant and 'compiled_recipe' in meal.variant:
                compiled = meal.variant['compiled_recipe']
                meal_dict['recipe_id'] = meal.variant.get('variant_id', compiled.get('id'))
                meal_dict['recipe_name'] = compiled.get('name')
                meal_dict['description'] = compiled.get('description')
                meal_dict['estimated_time'] = compiled.get('estimated_time')
                meal_dict['cuisine'] = compiled.get('cuisine')
                meal_dict['difficulty'] = compiled.get('difficulty')
                meal_dict['recipe'] = compiled  # Include full recipe for Cook page
                meal_dict['has_variant'] = True
                meal_dict['warnings'] = meal.variant.get('warnings', [])
            elif meal.recipe:
                # Flatten recipe fields for frontend compatibility
                meal_dict['recipe_id'] = meal.recipe.id
                meal_dict['recipe_name'] = meal.recipe.name
                meal_dict['description'] = meal.recipe.description
                meal_dict['estimated_time'] = meal.recipe.estimated_time
                meal_dict['cuisine'] = meal.recipe.cuisine
                meal_dict['difficulty'] = meal.recipe.difficulty
                meal_dict['has_variant'] = False
            # Rename 'date' to 'meal_date' for clarity
            meal_dict['meal_date'] = meal_dict.pop('date', None)
            enriched_meals.append(meal_dict)

        # Get backup_recipes from snapshot (if available)
        backup_recipes = []
        snapshot_id = session.get('snapshot_id')
        if snapshot_id:
            try:
                snapshot = assistant.db.get_snapshot(snapshot_id)
                if snapshot and 'backup_recipes' in snapshot:
                    backup_recipes = snapshot['backup_recipes']
                    logger.debug(f"[/api/plan/current] Found {len(backup_recipes)} backup recipes in snapshot")
            except Exception as e:
                logger.warning(f"Failed to load backup recipes from snapshot: {e}")

        return jsonify({
            "success": True,
            "plan": {
                'id': meal_plan.id,
                'week_of': meal_plan.week_of,
                'meals': enriched_meals,
                'backup_recipes': backup_recipes,  # For instant swap modal
            }
        })

    except Exception as e:
        logger.error(f"Error getting current plan: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/plan/<meal_plan_id>', methods=['GET'])
@login_required
def api_get_plan_by_id(meal_plan_id):
    """Get meal plan by ID (for cook page and localStorage-based lookups)."""
    user_id = session.get('user_id', 1)
    try:
        # Use get_effective_meal_plan to get variant data from snapshot
        meal_plan = assistant.db.get_effective_meal_plan(meal_plan_id, user_id=user_id)
        if not meal_plan:
            return jsonify({"success": False, "error": "Meal plan not found"}), 404

        # Use embedded Recipe objects from PlannedMeal (Phase 2 enhancement)
        enriched_meals = []
        for meal in meal_plan.meals:
            meal_dict = meal.to_dict()
            # Check for variant - use compiled_recipe if exists
            if meal.variant and 'compiled_recipe' in meal.variant:
                compiled = meal.variant['compiled_recipe']
                meal_dict['recipe_id'] = meal.variant.get('variant_id', compiled.get('id'))
                meal_dict['recipe_name'] = compiled.get('name')
                meal_dict['description'] = compiled.get('description')
                meal_dict['estimated_time'] = compiled.get('estimated_time')
                meal_dict['cuisine'] = compiled.get('cuisine')
                meal_dict['difficulty'] = compiled.get('difficulty')
                meal_dict['recipe'] = compiled  # Include full recipe for Cook page
                meal_dict['has_variant'] = True
                meal_dict['warnings'] = meal.variant.get('warnings', [])
            elif meal.recipe:
                meal_dict['recipe_id'] = meal.recipe.id
                meal_dict['recipe_name'] = meal.recipe.name
                meal_dict['description'] = meal.recipe.description
                meal_dict['estimated_time'] = meal.recipe.estimated_time
                meal_dict['cuisine'] = meal.recipe.cuisine
                meal_dict['difficulty'] = meal.recipe.difficulty
                meal_dict['has_variant'] = False
            meal_dict['meal_date'] = meal_dict.pop('date', None)
            enriched_meals.append(meal_dict)

        return jsonify({
            "success": True,
            "plan": {
                'id': meal_plan.id,
                'week_of': meal_plan.week_of,
                'meals': enriched_meals,
            }
        })

    except Exception as e:
        logger.error(f"Error getting plan by ID: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/plan/preload', methods=['POST'])
@login_required
def api_preload_plan_data():
    """Preload shopping list and cook page data for current meal plan."""
    try:
        meal_plan_id = session.get('meal_plan_id')
        if not meal_plan_id:
            return jsonify({"success": False, "error": "No active meal plan"}), 400

        logger.info(f"Preloading data for meal plan {meal_plan_id}")

        user_id = session.get('user_id', 1)

        # Priority 1: Create shopping list if it doesn't exist
        shopping_result = None
        if not session.get('shopping_list_id'):
            # Check if a shopping list already exists for this week
            meal_plan = assistant.db.get_meal_plan(meal_plan_id, user_id=user_id)
            if meal_plan:
                existing_list = assistant.db.get_grocery_list_by_week(meal_plan.week_of, user_id=user_id)
                if existing_list:
                    session['shopping_list_id'] = existing_list.id
                    logger.info(f"Found existing shopping list: {existing_list.id}, restoring to session")
                else:
                    logger.info("Generating shopping list (this may take 20-40 seconds)...")
                    shopping_result = assistant.create_shopping_list(meal_plan_id)
                    if shopping_result["success"]:
                        session['shopping_list_id'] = shopping_result['grocery_list_id']
                        logger.info(f"Created shopping list: {shopping_result['grocery_list_id']}")
        else:
            logger.info("Shopping list already exists in session, skipping generation")

        # Priority 2: Preload cook page recipe details (DISABLED - focusing on shop)
        recipes_preloaded = 0
        # try:
        #     meal_plan = assistant.db.get_meal_plan(meal_plan_id)
        #     if meal_plan:
        #         logger.info(f"Preloading {len(meal_plan.meals)} recipes for cook page...")
        #         # Use embedded Recipe objects (Phase 2 enhancement)
        #         recipe_ids = [meal.recipe.id for meal in meal_plan.meals if meal.recipe]
        #         recipes_preloaded = len(recipe_ids)

        #         # Preload cooking guides for each recipe
        #         def fetch_cooking_guide(recipe_id):
        #             try:
        #                 result = assistant.get_cooking_guide(recipe_id)
        #                 return (recipe_id, result["success"])
        #             except Exception as e:
        #                 logger.error(f"Error preloading cooking guide for {recipe_id}: {e}")
        #                 return (recipe_id, False)

        #         with ThreadPoolExecutor(max_workers=min(5, len(recipe_ids))) as executor:
        #             futures = {executor.submit(fetch_cooking_guide, recipe_id): recipe_id
        #                       for recipe_id in recipe_ids}
        #             guides_loaded = sum(1 for future in as_completed(futures) if future.result()[1])

        #         logger.info(f"Preloaded {guides_loaded}/{len(recipe_ids)} cooking guides")
        # except Exception as e:
        #     logger.error(f"Error preloading cook page data: {e}")

        return jsonify({
            "success": True,
            "message": "Shop and Cook tabs are now ready for instant loading!",
            "shopping_list_created": shopping_result is not None,
            "shopping_list_id": session.get('shopping_list_id'),
            "meal_plan_id": meal_plan_id,
            "recipes_preloaded": recipes_preloaded,
        })

    except Exception as e:
        logger.error(f"Error preloading data: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/plan/clear', methods=['POST'])
@login_required
def api_clear_plan():
    """Clear the current meal plan from session (start fresh)."""
    try:
        # Clear meal plan and shopping list from session
        old_plan_id = session.get('meal_plan_id')
        old_shopping_id = session.get('shopping_list_id')

        session.pop('meal_plan_id', None)
        session.pop('shopping_list_id', None)

        # Set flag to prevent auto-restore
        session['plan_cleared'] = True

        logger.info(f"Cleared meal plan {old_plan_id} and shopping list {old_shopping_id} from session")

        return jsonify({
            "success": True,
            "message": "Plan cleared successfully"
        })

    except Exception as e:
        logger.error(f"Error clearing plan: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/performance/metrics', methods=['GET'])
@login_required
def api_get_performance_metrics():
    """Get current performance metrics (admin/debugging endpoint)."""
    if not PERFORMANCE_MONITORING_ENABLED or not perf_monitor:
        return jsonify({"success": False, "error": "Performance monitoring not enabled"}), 503

    try:
        metrics = perf_monitor.get_metrics()
        summary = metrics.summary()

        return jsonify({
            "success": True,
            "metrics": summary,
            "llm_calls": [
                {
                    "timestamp": call.timestamp.isoformat(),
                    "model": call.model,
                    "duration": call.duration,
                    "cached": call.cached
                }
                for call in metrics.llm_calls
            ],
            "db_queries": [
                {
                    "timestamp": query.timestamp.isoformat(),
                    "query": query.query,
                    "duration": query.duration,
                    "rows": query.rows_returned
                }
                for query in metrics.db_queries
            ]
        })

    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/performance/reset', methods=['POST'])
def api_reset_performance_metrics():
    """Reset performance metrics (admin/debugging endpoint)."""
    if not PERFORMANCE_MONITORING_ENABLED or not perf_monitor:
        return jsonify({"success": False, "error": "Performance monitoring not enabled"}), 503

    try:
        perf_monitor.reset()
        logger.info("Performance metrics reset")
        return jsonify({"success": True, "message": "Performance metrics reset"})

    except Exception as e:
        logger.error(f"Error resetting performance metrics: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/debug/snapshot-log-test')
def debug_snapshot_log():
    """Test route to verify snapshot logging works."""
    log_snapshot_save("test_mp_2025-11-24_20251123", 1, "2025-11-24")
    log_snapshot_load("test_mp_2025-11-24_20251123")
    return jsonify({
        "status": "ok",
        "message": "Check logs for [SNAPSHOT] entries"
    })


if __name__ == '__main__':
    # Check for API key
    if not API_KEY_AVAILABLE:
        logger.warning("ANTHROPIC_API_KEY not set - some features may be limited")

    # Run development server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
    )
