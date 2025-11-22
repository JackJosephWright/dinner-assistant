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
from flask import Flask, render_template, request, jsonify, session, Response
from flask_cors import CORS
from dotenv import load_dotenv

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

# Simple user authentication
USERS = {
    "admin": "password",
    "agusta": "password"
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
    """Emit a progress update to the client."""
    with progress_lock:
        if session_id in progress_queues:
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


@app.route('/api/progress-stream')
@login_required
def progress_stream():
    """Server-Sent Events endpoint for progress updates."""
    session_id = request.args.get('session_id', session.get('_id', 'default'))

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

    return Response(generate(), mimetype='text/event-stream')


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

    return Response(generate(), mimetype='text/event-stream')


def restore_session_from_db():
    """
    Restore session data from database if session IDs are missing.
    This handles cases where user returns after closing browser.
    """
    # Don't restore if user explicitly cleared the plan
    if session.get('plan_cleared'):
        return

    if 'meal_plan_id' not in session:
        # Get most recent meal plan
        recent_plans = assistant.db.get_recent_meal_plans(limit=1)
        if recent_plans:
            session['meal_plan_id'] = recent_plans[0].id
            logger.info(f"Restored meal_plan_id from database: {session['meal_plan_id']}")

            # Also try to restore shopping list for this plan
            if 'shopping_list_id' not in session:
                meal_plan = recent_plans[0]
                # Query for grocery list by week_of
                with sqlite3.connect(assistant.db.user_db) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM grocery_lists WHERE week_of = ? ORDER BY created_at DESC LIMIT 1",
                        (meal_plan.week_of,)
                    )
                    row = cursor.fetchone()
                    if row:
                        session['shopping_list_id'] = row['id']
                        logger.info(f"Restored shopping_list_id from database: {session['shopping_list_id']}")


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username in USERS and USERS[username] == password:
            session['username'] = username
            logger.info(f"User {username} logged in successfully")
            from flask import redirect
            return redirect('/plan')
        else:
            return render_template('login.html', error='Invalid username or password')

    # If already logged in, redirect to plan
    if 'username' in session:
        from flask import redirect
        return redirect('/plan')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout and clear session."""
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"User {username} logged out")
    from flask import redirect
    return redirect('/login')


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

    # Check if user needs onboarding
    needs_onboarding = not check_onboarding_status(assistant.db)

    # Get current meal plan if exists
    current_plan = None
    if 'meal_plan_id' in session:
        try:
            meal_plan = assistant.db.get_meal_plan(session['meal_plan_id'])
            if meal_plan:
                # Use embedded Recipe objects from PlannedMeal (Phase 2 enhancement)
                enriched_meals = []
                for meal in meal_plan.meals:
                    meal_dict = meal.to_dict()
                    # Flatten recipe fields for frontend compatibility
                    if meal.recipe:
                        meal_dict['recipe_id'] = meal.recipe.id
                        meal_dict['recipe_name'] = meal.recipe.name
                        meal_dict['description'] = meal.recipe.description
                        meal_dict['estimated_time'] = meal.recipe.estimated_time
                        meal_dict['cuisine'] = meal.recipe.cuisine
                        meal_dict['difficulty'] = meal.recipe.difficulty
                    # Format date nicely (e.g., "Friday, November 1")
                    date_str = meal_dict.pop('date', None)
                    if date_str:
                        from datetime import datetime
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        meal_dict['meal_date'] = date_obj.strftime('%A, %B %d')
                    else:
                        meal_dict['meal_date'] = date_str
                    enriched_meals.append(meal_dict)

                current_plan = {
                    'id': meal_plan.id,
                    'week_of': meal_plan.week_of,
                    'meals': enriched_meals,
                }
        except Exception as e:
            logger.error(f"Error loading meal plan: {e}")

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

    # Get current shopping list if exists
    # IMPORTANT: Always fetch LATEST shopping list for current meal plan
    # (background thread may have regenerated it without updating session)
    current_list = None
    if 'meal_plan_id' in session:
        try:
            meal_plan = assistant.db.get_meal_plan(session['meal_plan_id'])
            if meal_plan:
                # Query for most recent grocery list for this week
                with sqlite3.connect(assistant.db.user_db) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM grocery_lists WHERE week_of = ? ORDER BY created_at DESC LIMIT 1",
                        (meal_plan.week_of,)
                    )
                    row = cursor.fetchone()
                    if row:
                        latest_shopping_list_id = row['id']
                        # Update session with latest ID
                        session['shopping_list_id'] = latest_shopping_list_id
                        logger.info(f"Loaded latest shopping list: {latest_shopping_list_id}")

                        grocery_list = assistant.db.get_grocery_list(latest_shopping_list_id)
                        if grocery_list:
                            current_list = grocery_list.to_dict()
        except Exception as e:
            logger.error(f"Error loading shopping list: {e}")
    elif 'shopping_list_id' in session:
        # Fallback: use session ID if no meal plan
        try:
            grocery_list = assistant.db.get_grocery_list(session['shopping_list_id'])
            if grocery_list:
                current_list = grocery_list.to_dict()
        except Exception as e:
            logger.error(f"Error loading shopping list: {e}")

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
    if 'meal_plan_id' in session:
        try:
            meal_plan = assistant.db.get_meal_plan(session['meal_plan_id'])
            if meal_plan:
                # Use embedded Recipe objects from PlannedMeal (Phase 2 enhancement)
                enriched_meals = []
                for meal in meal_plan.meals:
                    meal_dict = meal.to_dict()
                    # Flatten recipe fields for frontend compatibility
                    if meal.recipe:
                        meal_dict['recipe_id'] = meal.recipe.id
                        meal_dict['recipe_name'] = meal.recipe.name
                        meal_dict['description'] = meal.recipe.description
                        meal_dict['estimated_time'] = meal.recipe.estimated_time
                        meal_dict['cuisine'] = meal.recipe.cuisine
                        meal_dict['difficulty'] = meal.recipe.difficulty
                    # Format date nicely (e.g., "Friday, November 1")
                    date_str = meal_dict.pop('date', None)
                    if date_str:
                        from datetime import datetime
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        meal_dict['meal_date'] = date_obj.strftime('%A, %B %d')
                    else:
                        meal_dict['meal_date'] = date_str
                    enriched_meals.append(meal_dict)

                current_plan = {
                    'id': meal_plan.id,
                    'week_of': meal_plan.week_of,
                    'meals': enriched_meals,
                }
        except Exception as e:
            logger.error(f"Error loading meal plan for cook page: {e}")

    return render_template(
        'cook.html',
        current_plan=current_plan,
        api_key_available=API_KEY_AVAILABLE,
    )


@app.route('/settings')
@login_required
def settings_page():
    """Settings page."""
    try:
        profile = assistant.db.get_user_profile()
        cuisine_prefs = assistant.db.get_cuisine_preferences()
        favorite_recipes = assistant.db.get_favorite_recipes(limit=10)

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
                    logger.info(f"[Background] Auto-generating shopping list for new plan {result['meal_plan_id']}")
                    shop_result = assistant.create_shopping_list(result['meal_plan_id'])

                    if shop_result.get("success"):
                        new_shopping_list_id = shop_result["grocery_list_id"]
                        logger.info(f"[Background] Auto-generated shopping list: {new_shopping_list_id}")

                        # Update session with new shopping list ID
                        # Note: session updates in background thread require app context
                        with app.app_context():
                            from flask import session as bg_session
                            # Can't modify session from background thread reliably
                            # Will be updated when user visits Shop tab
                            pass

                        # Broadcast shopping list change to all tabs
                        broadcast_state_change('shopping_list_changed', {
                            'shopping_list_id': new_shopping_list_id,
                            'meal_plan_id': result['meal_plan_id']
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
            # Broadcast meal plan change immediately
            broadcast_state_change('meal_plan_changed', {
                'meal_plan_id': meal_plan_id,
                'date_changed': data['date']
            })
            logger.info(f"Broadcasted meal_plan_changed event")

            # Auto-regenerate shopping list in BACKGROUND THREAD
            def regenerate_shopping_list_async():
                """Background thread to regenerate shopping list and broadcast."""
                try:
                    logger.info(f"[Background] Regenerating shopping list for meal plan {meal_plan_id}")
                    shop_result = assistant.create_shopping_list(meal_plan_id)

                    if shop_result.get("success"):
                        new_shopping_list_id = shop_result["grocery_list_id"]
                        logger.info(f"[Background] Auto-generated shopping list: {new_shopping_list_id}")

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

        # Check if already exists (cache check)
        if not scaling_instructions and session.get('shopping_list_id'):
            # Return cached shopping list
            existing_list = assistant.db.get_grocery_list(session['shopping_list_id'])
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
            meal_plan = assistant.db.get_meal_plan(meal_plan_id)
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
    """Get cooking guide for a recipe."""
    try:
        logger.info(f"Getting cooking guide for {recipe_id}")

        result = assistant.get_cooking_guide(recipe_id)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting cooking guide: {e}", exc_info=True)
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


@app.route('/api/preferences', methods=['GET'])
@login_required
def api_get_preferences():
    """Get user preferences and stats."""
    try:
        profile = assistant.db.get_user_profile()
        cuisine_prefs = assistant.db.get_cuisine_preferences()
        favorite_recipes = assistant.db.get_favorite_recipes(limit=10)

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
    try:
        weeks_back = request.args.get('weeks_back', default=4, type=int)

        history = assistant.db.get_meal_history(weeks_back=weeks_back)

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
        old_meal_plan_id = session.get('meal_plan_id')
        old_shopping_list_id = session.get('shopping_list_id')

        # Restore IDs from session to chatbot to ensure state persistence
        if old_meal_plan_id:
            chatbot_instance.current_meal_plan_id = old_meal_plan_id
        if old_shopping_list_id:
            chatbot_instance.current_shopping_list_id = old_shopping_list_id

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

        # Get AI response
        response = chatbot_instance.chat(actual_message)

        # Save pending swap options to session
        session['pending_swap_options'] = chatbot_instance.pending_swap_options
        if chatbot_instance.pending_swap_options:
            logger.info("Saved pending_swap_options to session")

        # Update session with any IDs from chatbot
        plan_changed = False
        shopping_changed = False

        logger.info(f"After chat - chatbot meal_plan_id: {chatbot_instance.current_meal_plan_id}, old: {old_meal_plan_id}")

        # Check if chatbot created or changed meal plan
        if chatbot_instance.current_meal_plan_id:
            session['meal_plan_id'] = chatbot_instance.current_meal_plan_id
            # Clear the plan_cleared flag since we now have a plan
            session.pop('plan_cleared', None)
            if chatbot_instance.current_meal_plan_id != old_meal_plan_id:
                # New meal plan created
                plan_changed = True
                logger.info(f"New meal plan created: {chatbot_instance.current_meal_plan_id}")
            else:
                # Same meal plan - always assume it was modified to refresh UI
                # User can use "Clear Plan" button if they want to start fresh
                plan_changed = True
                logger.info(f"Plan interaction detected - refreshing UI for plan: {chatbot_instance.current_meal_plan_id}")

        if chatbot_instance.current_shopping_list_id:
            session['shopping_list_id'] = chatbot_instance.current_shopping_list_id
            if chatbot_instance.current_shopping_list_id != old_shopping_list_id:
                shopping_changed = True
                logger.info(f"New shopping list created: {chatbot_instance.current_shopping_list_id}")
            else:
                # Same shopping list - check if user wanted to modify it
                modification_keywords = ['double', 'triple', 'half', 'add', 'remove', 'scale']
                if any(keyword in message.lower() for keyword in modification_keywords):
                    shopping_changed = True
                    logger.info(f"Detected shopping list modification request in message: '{message}'")
                # If meal plan changed, shopping list was likely updated incrementally
                elif plan_changed:
                    shopping_changed = True
                    logger.info(f"Meal plan changed - shopping list updated incrementally")

        # Broadcast meal plan change immediately (don't wait for shopping list)
        if plan_changed and chatbot_instance.current_meal_plan_id:
            broadcast_state_change('meal_plan_changed', {
                'meal_plan_id': chatbot_instance.current_meal_plan_id,
            })
            logger.info(f"Broadcasted meal_plan_changed event")

        # Auto-regenerate shopping list in BACKGROUND THREAD (parallel with response)
        if plan_changed and chatbot_instance.current_meal_plan_id and not chatbot_instance.pending_swap_options:
            meal_plan_id = chatbot_instance.current_meal_plan_id

            def regenerate_shopping_list_async():
                """Background thread to regenerate shopping list and broadcast."""
                try:
                    logger.info(f"[Background] Regenerating shopping list for meal plan {meal_plan_id}")
                    shop_result = assistant.create_shopping_list(meal_plan_id)

                    if shop_result.get("success"):
                        new_shopping_list_id = shop_result["grocery_list_id"]
                        logger.info(f"[Background] Auto-generated shopping list: {new_shopping_list_id}")

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

        # If shopping list was changed synchronously (e.g., via direct shop commands), broadcast it
        if shopping_changed and chatbot_instance.current_shopping_list_id and not plan_changed:
            broadcast_state_change('shopping_list_changed', {
                'shopping_list_id': chatbot_instance.current_shopping_list_id,
                'meal_plan_id': chatbot_instance.current_meal_plan_id,
            })
            logger.info(f"Broadcasted shopping_list_changed event")

        # Emit completion
        emit_progress(session_id, "Done!", "complete")

        return jsonify({
            "success": True,
            "response": response,
            "meal_plan_id": chatbot_instance.current_meal_plan_id,
            "shopping_list_id": chatbot_instance.current_shopping_list_id,
            "plan_changed": plan_changed,
            "shopping_changed": shopping_changed,
            "awaiting_confirmation": bool(chatbot_instance.pending_swap_options),
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
    try:
        needs_onboarding = not check_onboarding_status(assistant.db)
        profile = assistant.db.get_user_profile()

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
        # Clear all session data to trigger onboarding
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
        meal_plan_id = session.get('meal_plan_id')
        if not meal_plan_id:
            return jsonify({"success": False, "error": "No active meal plan"}), 404

        meal_plan = assistant.db.get_meal_plan(meal_plan_id)
        if not meal_plan:
            return jsonify({"success": False, "error": "Meal plan not found"}), 404

        # Use embedded Recipe objects from PlannedMeal (Phase 2 enhancement)
        # No need to fetch recipes separately - they're already embedded!
        enriched_meals = []
        for meal in meal_plan.meals:
            meal_dict = meal.to_dict()
            # Flatten recipe fields for frontend compatibility
            if meal.recipe:
                meal_dict['recipe_id'] = meal.recipe.id
                meal_dict['recipe_name'] = meal.recipe.name
                meal_dict['description'] = meal.recipe.description
                meal_dict['estimated_time'] = meal.recipe.estimated_time
                meal_dict['cuisine'] = meal.recipe.cuisine
                meal_dict['difficulty'] = meal.recipe.difficulty
            # Rename 'date' to 'meal_date' for clarity
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
        logger.error(f"Error getting current plan: {e}", exc_info=True)
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

        # Priority 1: Create shopping list if it doesn't exist
        shopping_result = None
        if not session.get('shopping_list_id'):
            # Check if a shopping list already exists for this week
            meal_plan = assistant.db.get_meal_plan(meal_plan_id)
            if meal_plan:
                existing_list = assistant.db.get_grocery_list_by_week(meal_plan.week_of)
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
