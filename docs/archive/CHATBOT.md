# AI Chatbot Mode

The **real** AI chatbot! Uses Claude LLM with MCP tool access.

## 🤖 What This Is

This is a **true LLM-powered chatbot** that:
- Uses Claude (Anthropic API) as the conversational AI
- Has access to MCP tools (meal planning, recipe search, etc.)
- Understands natural conversation
- Decides when to use tools automatically
- Maintains conversation context

Unlike the command-based "interactive" mode, this uses an actual LLM to understand your requests and use tools intelligently.

---

## 🚀 Setup

### 1. Install Anthropic SDK

```bash
pip install anthropic
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

### 2. Set API Key

```bash
export ANTHROPIC_API_KEY='your-key-here'
```

Get your API key from: https://console.anthropic.com/

---

## 💬 Usage

```bash
./run.sh chat
```

Or directly:
```bash
python3 src/chatbot.py
```

---

## 🗣️ Example Conversation

```
🍽️  MEAL PLANNING ASSISTANT - AI Chatbot
======================================================================

Powered by Claude with MCP tools
I can help you plan meals, create shopping lists, and find recipes!

Just chat naturally - I'll use tools as needed.
Type 'quit' to exit.

You: Hi! I need help planning my meals for next week

🍽️  Assistant: I'd be happy to help you plan your meals for next week! Let me
create a 7-day meal plan for you with a nice variety of dishes.

[Uses plan_meals tool automatically]

I've created a meal plan for you with 7 dinners. Here's what I've planned:

- Monday: Caramelized Onion Chicken (30 min, easy)
- Tuesday: Kaccy's Chimichangas (30 min, easy)
- Wednesday: Italian Sausage Soup (15 min, easy)
[... continues ...]

The plan includes a nice variety with American, Mexican, and Italian cuisines.
Would you like me to create a shopping list for these meals?

You: yes please!

🍽️  Assistant: Great! Let me generate a consolidated shopping list for all
these meals.

[Uses create_shopping_list tool]

I've created your shopping list with 78 items, organized by store section
(produce, meat, dairy, etc.). This includes everything you need for all 7 meals.

Would you like me to show you the full list, or would you like help with
anything else?

You: can you find me some quick salmon recipes?

🍽️  Assistant: I'll search for quick salmon recipes for you.

[Uses search_recipes tool]

I found several great quick salmon recipes:

1. Salmon in a Paper Bag With Miso, Bok Choy and Shallots (30 min, easy)
2. Seared Salmon With Balsamic Vinegar and Dijon Glaze (30 min, easy)
3. Honey Glazed Salmon (25 min, easy)
[... continues ...]

Would you like cooking instructions for any of these?
```

---

## 🛠️ Available Tools

The chatbot has access to these tools (uses them automatically):

1. **plan_meals** - Generate weekly meal plans
2. **create_shopping_list** - Create organized grocery lists
3. **search_recipes** - Find recipes by keyword/time/tags
4. **get_cooking_guide** - Get detailed cooking instructions
5. **get_meal_history** - View past meals
6. **show_current_plan** - Display active meal plan
7. **show_shopping_list** - Display current shopping list

The LLM decides when to use these based on your conversation!

---

## 🎯 Key Features

### True LLM Understanding
- Understands context and intent
- Asks clarifying questions
- Provides helpful suggestions
- Maintains conversation flow

### Automatic Tool Use
- Decides which tools to use
- Chains multiple tools together
- Uses tools in response to natural questions

### Conversation Memory
- Remembers what you've asked
- Tracks current meal plan/shopping list
- References earlier parts of conversation

---

## 💡 Example Prompts

**Planning**
- "I need help planning meals for next week"
- "Can you make me a meal plan with quick weeknight meals?"
- "Plan my dinners for the next 7 days"

**Shopping**
- "Create a shopping list for my meal plan"
- "What ingredients do I need?"
- "Show me my grocery list"

**Searching**
- "Find me some easy chicken recipes"
- "I want quick meals under 30 minutes"
- "What salmon dishes do you have?"

**Cooking**
- "How do I make the first meal?"
- "Give me cooking instructions for recipe 123"
- "What are the steps for this dish?"

**History**
- "What have I been eating lately?"
- "Show my recent meals"
- "What are my favorite dishes?"

---

## 🆚 Chat vs Interactive vs Workflow

### Chat Mode (LLM-powered)
```bash
./run.sh chat
```
- **Pros**: Natural conversation, understands context, intelligent
- **Cons**: Requires API key, uses API credits
- **Best for**: Exploring, getting recommendations, conversational planning

### Interactive Mode (Command-based)
```bash
./run.sh interactive
```
- **Pros**: No API key needed, fast, offline
- **Cons**: Less intelligent, command-based
- **Best for**: Quick tasks, when API unavailable

### Workflow Mode (One-shot)
```bash
./run.sh workflow
```
- **Pros**: Super fast, no API key, one command
- **Cons**: No conversation, fixed workflow
- **Best for**: Just want a meal plan NOW

---

## ⚙️ Configuration

The chatbot uses:
- **Model**: claude-3-5-sonnet-20241022
- **Max tokens**: 4096
- **Tools**: 7 MCP tools
- **Context**: Maintains conversation history

---

## 🔒 Privacy

- Conversations are NOT saved between sessions
- API calls go to Anthropic
- Your recipes/history stay local in SQLite
- No data is shared beyond what's needed for tool execution

---

## 🐛 Troubleshooting

### "ANTHROPIC_API_KEY not set"

Set your API key:
```bash
export ANTHROPIC_API_KEY='sk-ant-...'
```

Add to your shell profile to make permanent:
```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc
source ~/.bashrc
```

### "anthropic module not found"

Install the SDK:
```bash
pip install anthropic
```

### Want to use without API?

Use command-based mode instead:
```bash
./run.sh interactive  # Command-based
./run.sh workflow     # One-shot
```

---

## 💰 Cost

Uses Anthropic's API:
- Claude 3.5 Sonnet: ~$3 per million input tokens
- Typical conversation: 5-10K tokens = $0.01-0.03
- Very affordable for personal use!

---

**This is the real AI chatbot you asked for!** 🤖

Try it:
```bash
export ANTHROPIC_API_KEY='your-key'
./run.sh chat
```
