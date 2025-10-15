# Meal Planning Assistant - Web Application

A modern web interface for the Meal Planning Assistant, built with Flask and Tailwind CSS.

## Features

### 🍽️ Home Page
- Overview of system capabilities
- Quick access to all features
- Database statistics (492K+ recipes)

### 📅 Meal Planning
- AI-powered or algorithmic meal planning
- Generate 5-7 day meal plans
- Swap individual meals with natural language requests
- View recipe details inline

### 🛒 Shopping List
- Auto-consolidated ingredients
- Organized by store section
- **NEW:** Natural language recipe scaling
  - "double the Italian sandwiches"
  - "triple the chicken for meal prep"
  - "reduce pasta by half"
- Checkboxes for shopping
- Print-friendly layout

### 👨‍🍳 Cooking Guide
- Recipe search with filters
- Step-by-step instructions
- Ingredient lists with quantities
- Cooking time and serving info

## Quick Start

### 1. Install Dependencies

```bash
# Install Flask and other web dependencies
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
# Required for AI features
export ANTHROPIC_API_KEY='your-api-key-here'

# Optional: Set Flask secret key (for production)
export FLASK_SECRET_KEY='your-secret-key-here'

# Load environment
source .env
```

### 3. Run the Web Server

```bash
# From project root
cd src/web
python app.py
```

The server will start at `http://localhost:5000`

### 4. Open in Browser

Navigate to: **http://localhost:5000**

## Usage

### Planning Meals

1. Go to **Plan Meals** page
2. Select week start date (or leave empty for next Monday)
3. Choose number of days (5 or 7)
4. Click **Generate Plan**
5. AI will create a personalized meal plan
6. Swap meals by clicking the exchange icon

### Creating Shopping List

1. After creating a meal plan, go to **Shopping List** page
2. (Optional) Add scaling instructions:
   - "double the Italian sandwiches"
   - "triple the chicken"
   - "reduce pasta by half"
3. Click **Generate Shopping List**
4. Review items organized by store section
5. Check off items as you shop
6. Print the list if needed

### Cooking

1. Go to **Cook** page
2. Search for recipes by keyword/time
3. Click a recipe to view full instructions
4. Follow step-by-step guide

## API Endpoints

The Flask app exposes these REST API endpoints:

### Planning
- `POST /api/plan` - Generate meal plan
  ```json
  {
    "week_of": "2025-10-20",  // optional
    "num_days": 7
  }
  ```

- `POST /api/swap-meal` - Swap a meal
  ```json
  {
    "date": "2025-10-20",
    "requirements": "vegetarian pasta"
  }
  ```

### Shopping
- `POST /api/shop` - Create shopping list
  ```json
  {
    "meal_plan_id": "mp_...",  // optional if in session
    "scaling_instructions": "double the Italian sandwiches"  // optional
  }
  ```

### Cooking
- `GET /api/cook/<recipe_id>` - Get cooking guide
- `POST /api/search-recipes` - Search recipes
  ```json
  {
    "query": "chicken",
    "max_time": 45,
    "limit": 20
  }
  ```

### User Data
- `GET /api/preferences` - Get user preferences and stats
- `GET /api/meal-history?weeks_back=4` - Get meal history

## Architecture

```
src/web/
├── app.py                  # Flask application
├── templates/              # Jinja2 HTML templates
│   ├── base.html          # Base layout with navigation
│   ├── index.html         # Home page
│   ├── plan.html          # Meal planning page
│   ├── shop.html          # Shopping list page
│   └── cook.html          # Cooking guide page
└── static/                # Static assets (CSS, JS)
```

### Tech Stack

- **Backend:** Flask 3.0+ (Python web framework)
- **Frontend:** Tailwind CSS (utility-first CSS)
- **Icons:** Font Awesome 6
- **Database:** SQLite (existing user_data.db)
- **AI:** Claude via Anthropic API (optional)

### Session Management

The app uses Flask sessions to track:
- `meal_plan_id` - Current meal plan
- `shopping_list_id` - Current shopping list

Sessions persist across page reloads but are cleared when the browser closes.

## Development

### Run in Debug Mode

Debug mode is enabled by default in `app.py`:

```python
app.run(
    host='0.0.0.0',
    port=5000,
    debug=True,  # Auto-reload on code changes
)
```

### Customize Port

```bash
# Run on different port
python app.py --port 8000
```

Or modify in `app.py`:
```python
app.run(host='0.0.0.0', port=8000)
```

## Deployment

### Option 1: Local Network

Run on your local network:

```bash
python app.py
# Server accessible at http://YOUR_LOCAL_IP:5000
```

### Option 2: Production Server

For production deployment:

1. **Set production secret key:**
   ```bash
   export FLASK_SECRET_KEY='long-random-production-key'
   ```

2. **Use a production WSGI server:**
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

3. **Deploy to cloud platform:**
   - **Render:** `render.yaml` (coming soon)
   - **Heroku:** `Procfile` (coming soon)
   - **DigitalOcean:** App Platform
   - **AWS:** Elastic Beanstalk

### Option 3: Docker

(Docker support coming soon)

## Troubleshooting

### Port Already in Use

```bash
# Kill process on port 5000
lsof -ti:5000 | xargs kill -9
```

### API Key Not Working

```bash
# Verify API key is set
echo $ANTHROPIC_API_KEY

# Re-source environment
source .env
```

### Templates Not Found

Make sure you're running from the correct directory:

```bash
# Should be in src/web/
pwd
# Output: /path/to/dinner-assistant/src/web

# Or run from project root with full path
python src/web/app.py
```

### Database Not Found

The app looks for databases in `data/` directory:

```bash
ls data/
# Should show: recipes.db, user_data.db
```

If missing, run the recipe loader:

```bash
python scripts/load_recipes.py
```

## Features Comparison

| Feature | AI Mode (API Key) | Basic Mode (No API Key) |
|---------|-------------------|-------------------------|
| Meal Planning | ✅ Personalized AI | ✅ Algorithmic |
| Shopping List | ✅ Smart consolidation | ✅ Basic consolidation |
| Recipe Scaling | ✅ Natural language | ❌ Not available |
| Meal Swapping | ✅ AI suggestions | ❌ Not available |
| Cooking Guide | ✅ AI tips | ✅ Basic instructions |
| Recipe Search | ✅ Enhanced | ✅ Basic |

## Browser Support

- ✅ Chrome/Edge (recommended)
- ✅ Firefox
- ✅ Safari
- ✅ Mobile browsers

## Performance

- **Load time:** < 1 second
- **Meal planning:** 10-30 seconds (AI mode)
- **Shopping list:** 5-15 seconds (AI mode)
- **Recipe search:** < 1 second

## Future Enhancements

- [ ] Real-time AI streaming responses
- [ ] Drag-and-drop meal planning
- [ ] Calendar view for meal plans
- [ ] Export shopping list to mobile
- [ ] Nutritional information
- [ ] Recipe ratings and reviews
- [ ] Meal prep mode
- [ ] Budget tracking

---

**Built with:** Flask, Tailwind CSS, Font Awesome, Claude AI

**Powered by:** 492,630 recipes • Python • SQLite • LangGraph
