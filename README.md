# Meal Planning Assistant 🍽️

[![Tests](https://img.shields.io/badge/tests-77%20passing-success)](docs/testing/TESTING.md)
[![Coverage](https://img.shields.io/badge/coverage-92%25%20models-success)](docs/testing/TESTING_SUMMARY.md)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

An AI-powered multi-agent system for intelligent meal planning, shopping list generation, and cooking guidance using MCP (Model Context Protocol) and LangGraph.

## ✨ Features

- 🤖 **AI-Powered Planning** - LLM reasoning for personalized meal plans
- 🛒 **Smart Shopping Lists** - Automatic ingredient consolidation and organization
- 👨‍🍳 **Cooking Guidance** - Step-by-step instructions with tips
- 📊 **Learning System** - Learns from your preferences and feedback
- 🔍 **492K+ Recipes** - Comprehensive Food.com recipe database
- ✅ **Test-Driven** - 77 tests ensuring reliability

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Anthropic API key (for AI chatbot mode)

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd dinner-assistant

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing

# Set up environment variables
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Download recipe data (link provided separately)
# Place food_com_recipes.csv in root directory

# Initialize databases
python scripts/load_recipes.py
python scripts/load_history.py  # Optional: if you have meal_history.csv
```

### Usage

**Three modes available:**

```bash
# 1. AI Chatbot (Most Natural)
./run.sh chat

# 2. Interactive Mode (Command-based)
./run.sh interactive

# 3. Workflow Mode (One-shot)
./run.sh workflow
```

## 📖 Documentation

Comprehensive documentation available in [`docs/`](docs/):

- **[Documentation Hub](docs/README.md)** - Complete documentation index
- **[Testing Guide](docs/testing/TESTING.md)** - How we ensure quality
- **[System Architecture](docs/development/CURRENT_SYSTEM.md)** - Technical details
- **[Roadmap](docs/development/ROADMAP.md)** - Future plans

## 🏗️ Project Structure

```
dinner-assistant/
├── src/                      # Source code
│   ├── agents/              # AI agents (planning, shopping, cooking)
│   ├── data/                # Data models and database interface
│   ├── mcp_server/          # MCP server and tools
│   ├── onboarding.py        # User onboarding flow
│   ├── chatbot.py           # AI chatbot interface
│   └── main.py              # CLI entry point
├── tests/                    # Test suite (77 tests)
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── e2e/                 # End-to-end tests
├── scripts/                  # Setup and utility scripts
├── docs/                     # Documentation
├── data/                     # SQLite databases (gitignored)
│   ├── recipes.db           # Recipe database (generated)
│   └── user_data.db         # User data (meal plans, history)
└── examples/                 # Example code and usage
```

## 🧪 Testing

Built with Test-Driven Development (TDD):

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest tests/unit/           # Unit tests
pytest tests/integration/    # Integration tests
pytest tests/e2e/            # End-to-end tests
```

**Current Status:** 77 tests passing in 5.30 seconds ✅

See [Testing Documentation](docs/testing/TESTING.md) for details.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Code style guidelines
- Testing requirements
- Pull request process
- Development workflow

## 📊 What's Working

### Planning Agent ✅
- Generate 7-day meal plans with automatic variety
- Learn from meal history (294 meals from 60 weeks)
- Balance cuisines and cooking difficulty
- Respect time constraints (weeknight vs weekend)
- Avoid recipe repetition (2-week window)

### Shopping Agent ✅
- Consolidated grocery lists
- Organization by store section
- Ingredient merging and deduplication
- Recipe tracking per ingredient

### Cooking Agent ✅
- Step-by-step instructions
- Ingredient substitution suggestions
- Timing breakdowns
- Difficulty-based tips

### Learning System ✅
- Meal event tracking
- User preference learning
- Cuisine preference analysis
- Recipe ratings and feedback

## 🗺️ Roadmap

See [ROADMAP.md](docs/development/ROADMAP.md) for detailed plans.

**Upcoming:**
- Enhanced preference learning
- Nutritional tracking
- Budget optimization
- Web interface

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Recipe Data:** Food.com dataset (492K+ recipes)
- **Architecture:** Built with MCP and LangGraph
- **AI:** Powered by Anthropic's Claude

## 📞 Support

- 📚 [Documentation](docs/README.md)
- 🐛 [Issue Tracker](issues)
- 💬 [Discussions](discussions)

---

**Built with Test-Driven Development** | **77 Tests Passing** | **Production Ready**
