"""
Ingredient category and allergen mappings for enrichment.

These mappings are used to classify ingredients into shopping categories
and identify common allergens.
"""

# Shopping categories based on typical grocery store layout
INGREDIENT_CATEGORIES = {
    # Produce
    "tomato": "produce",
    "tomatoes": "produce",
    "onion": "produce",
    "onions": "produce",
    "garlic": "produce",
    "potato": "produce",
    "potatoes": "produce",
    "carrot": "produce",
    "carrots": "produce",
    "celery": "produce",
    "bell pepper": "produce",
    "peppers": "produce",
    "lettuce": "produce",
    "spinach": "produce",
    "broccoli": "produce",
    "cauliflower": "produce",
    "zucchini": "produce",
    "cucumber": "produce",
    "mushroom": "produce",
    "mushrooms": "produce",
    "avocado": "produce",
    "lemon": "produce",
    "lime": "produce",
    "apple": "produce",
    "banana": "produce",
    "orange": "produce",
    "strawberries": "produce",
    "blueberries": "produce",
    "cilantro": "produce",
    "parsley": "produce",
    "basil": "produce",
    "thyme": "produce",
    "rosemary": "produce",
    "ginger": "produce",

    # Meat
    "chicken": "meat",
    "beef": "meat",
    "pork": "meat",
    "turkey": "meat",
    "bacon": "meat",
    "sausage": "meat",
    "ground beef": "meat",
    "ground turkey": "meat",
    "steak": "meat",
    "lamb": "meat",
    "ham": "meat",
    "prosciutto": "meat",

    # Seafood
    "salmon": "seafood",
    "tuna": "seafood",
    "shrimp": "seafood",
    "cod": "seafood",
    "tilapia": "seafood",
    "halibut": "seafood",
    "crab": "seafood",
    "lobster": "seafood",
    "scallops": "seafood",
    "mussels": "seafood",
    "clams": "seafood",
    "fish": "seafood",

    # Dairy
    "milk": "dairy",
    "cream": "dairy",
    "butter": "dairy",
    "cheese": "dairy",
    "cheddar": "dairy",
    "mozzarella": "dairy",
    "parmesan": "dairy",
    "yogurt": "dairy",
    "sour cream": "dairy",
    "cottage cheese": "dairy",
    "cream cheese": "dairy",
    "ricotta": "dairy",
    "heavy cream": "dairy",
    "half and half": "dairy",

    # Baking
    "flour": "baking",
    "sugar": "baking",
    "brown sugar": "baking",
    "powdered sugar": "baking",
    "baking powder": "baking",
    "baking soda": "baking",
    "yeast": "baking",
    "cornstarch": "baking",
    "cocoa": "baking",
    "chocolate chips": "baking",
    "vanilla": "baking",
    "vanilla extract": "baking",
    "honey": "baking",
    "maple syrup": "baking",

    # Pantry
    "oil": "pantry",
    "olive oil": "pantry",
    "vegetable oil": "pantry",
    "canola oil": "pantry",
    "coconut oil": "pantry",
    "vinegar": "pantry",
    "rice": "pantry",
    "pasta": "pantry",
    "spaghetti": "pantry",
    "beans": "pantry",
    "black beans": "pantry",
    "chickpeas": "pantry",
    "lentils": "pantry",
    "quinoa": "pantry",
    "oats": "pantry",
    "bread": "pantry",
    "breadcrumbs": "pantry",
    "tortillas": "pantry",
    "canned tomatoes": "pantry",
    "tomato paste": "pantry",
    "tomato sauce": "pantry",
    "broth": "pantry",
    "stock": "pantry",
    "coconut milk": "pantry",
    "peanut butter": "pantry",

    # Condiments
    "salt": "condiments",
    "pepper": "condiments",
    "black pepper": "condiments",
    "paprika": "condiments",
    "cumin": "condiments",
    "chili powder": "condiments",
    "oregano": "condiments",
    "cinnamon": "condiments",
    "nutmeg": "condiments",
    "garlic powder": "condiments",
    "onion powder": "condiments",
    "soy sauce": "condiments",
    "worcestershire sauce": "condiments",
    "hot sauce": "condiments",
    "sriracha": "condiments",
    "mustard": "condiments",
    "ketchup": "condiments",
    "mayonnaise": "condiments",
    "bbq sauce": "condiments",
    "salsa": "condiments",

    # Frozen
    "frozen peas": "frozen",
    "frozen corn": "frozen",
    "frozen vegetables": "frozen",
    "ice cream": "frozen",

    # Beverages
    "wine": "beverages",
    "beer": "beverages",
    "coffee": "beverages",
    "tea": "beverages",
    "juice": "beverages",

    # Eggs (technically dairy section but special category)
    "eggs": "dairy",
    "egg": "dairy",
}

# Allergen mappings
INGREDIENT_ALLERGENS = {
    # Gluten
    "flour": ["gluten"],
    "wheat": ["gluten"],
    "bread": ["gluten"],
    "pasta": ["gluten"],
    "spaghetti": ["gluten"],
    "breadcrumbs": ["gluten"],
    "soy sauce": ["gluten", "soy"],

    # Dairy
    "milk": ["dairy"],
    "cream": ["dairy"],
    "butter": ["dairy"],
    "cheese": ["dairy"],
    "cheddar": ["dairy"],
    "mozzarella": ["dairy"],
    "parmesan": ["dairy"],
    "yogurt": ["dairy"],
    "sour cream": ["dairy"],
    "cottage cheese": ["dairy"],
    "cream cheese": ["dairy"],
    "ricotta": ["dairy"],
    "heavy cream": ["dairy"],
    "half and half": ["dairy"],

    # Eggs
    "eggs": ["eggs"],
    "egg": ["eggs"],
    "mayonnaise": ["eggs"],

    # Nuts
    "peanuts": ["peanuts"],
    "peanut": ["peanuts"],
    "peanut butter": ["peanuts"],
    "almonds": ["tree-nuts"],
    "walnuts": ["tree-nuts"],
    "pecans": ["tree-nuts"],
    "cashews": ["tree-nuts"],
    "pistachios": ["tree-nuts"],
    "hazelnuts": ["tree-nuts"],
    "almond": ["tree-nuts"],
    "walnut": ["tree-nuts"],

    # Soy
    "soy": ["soy"],
    "tofu": ["soy"],
    "soy milk": ["soy"],
    "edamame": ["soy"],

    # Fish
    "salmon": ["fish"],
    "tuna": ["fish"],
    "cod": ["fish"],
    "tilapia": ["fish"],
    "halibut": ["fish"],
    "fish": ["fish"],
    "anchovy": ["fish"],
    "anchovies": ["fish"],

    # Shellfish
    "shrimp": ["shellfish"],
    "crab": ["shellfish"],
    "lobster": ["shellfish"],
    "scallops": ["shellfish"],
    "mussels": ["shellfish"],
    "clams": ["shellfish"],
    "oysters": ["shellfish"],

    # Sesame
    "sesame": ["sesame"],
    "tahini": ["sesame"],
}

# Non-substitutable ingredients (critical to recipe structure)
NON_SUBSTITUTABLE = {
    "water",
    "salt",
    "ice",
}

def get_category(ingredient_name: str) -> str:
    """
    Get shopping category for an ingredient.

    Args:
        ingredient_name: Normalized ingredient name (lowercase)

    Returns:
        Category string (produce, meat, dairy, etc.) or "other"
    """
    name_lower = ingredient_name.lower().strip()

    # Direct lookup
    if name_lower in INGREDIENT_CATEGORIES:
        return INGREDIENT_CATEGORIES[name_lower]

    # Partial match (e.g., "ground beef" matches "beef")
    for key, category in INGREDIENT_CATEGORIES.items():
        if key in name_lower or name_lower in key:
            return category

    return "other"


def get_allergens(ingredient_name: str) -> list:
    """
    Get allergens associated with an ingredient.

    Args:
        ingredient_name: Normalized ingredient name (lowercase)

    Returns:
        List of allergen strings (e.g., ["gluten", "dairy"])
    """
    name_lower = ingredient_name.lower().strip()

    # Direct lookup
    if name_lower in INGREDIENT_ALLERGENS:
        return INGREDIENT_ALLERGENS[name_lower].copy()

    # Partial match
    allergens = []
    for key, allergen_list in INGREDIENT_ALLERGENS.items():
        if key in name_lower:
            allergens.extend(allergen_list)

    return list(set(allergens))  # Remove duplicates


def is_substitutable(ingredient_name: str) -> bool:
    """
    Check if an ingredient can typically be substituted.

    Args:
        ingredient_name: Normalized ingredient name (lowercase)

    Returns:
        True if substitutable, False if critical to recipe
    """
    name_lower = ingredient_name.lower().strip()
    return name_lower not in NON_SUBSTITUTABLE
