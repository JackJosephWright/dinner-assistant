"""
Enrich recipe ingredients with structured parsed data.

This script parses raw ingredient strings from recipes.db and adds
structured data including quantity, unit, category, allergens, etc.

Usage:
    python scripts/enrich_recipe_ingredients.py --sample 10  # Test on 10 recipes
    python scripts/enrich_recipe_ingredients.py --sample 100 # Test on 100 recipes
    python scripts/enrich_recipe_ingredients.py --full       # Process all recipes
"""

import sqlite3
import json
import re
import argparse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ingredient_mappings import get_category, get_allergens, is_substitutable


@dataclass
class IngredientStructured:
    """Structured ingredient data."""
    raw: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    name: str = ""
    modifier: Optional[str] = None
    preparation: Optional[str] = None
    category: str = "other"
    allergens: List[str] = None
    substitutable: bool = True
    confidence: float = 1.0
    parse_method: str = "auto"

    def __post_init__(self):
        if self.allergens is None:
            self.allergens = []

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class SimpleIngredientParser:
    """
    Simple regex-based ingredient parser.

    This is a fallback parser that doesn't require external dependencies.
    For production, consider using ingredient-parser-py library for better accuracy.
    """

    # Common units (abbreviated and full)
    UNITS = {
        # Volume
        "cup": "cup", "cups": "cup", "c": "cup",
        "tablespoon": "tablespoon", "tablespoons": "tablespoon", "tbsp": "tablespoon", "T": "tablespoon",
        "teaspoon": "teaspoon", "teaspoons": "teaspoon", "tsp": "teaspoon", "t": "teaspoon",
        "pint": "pint", "pints": "pint", "pt": "pint",
        "quart": "quart", "quarts": "quart", "qt": "quart",
        "gallon": "gallon", "gallons": "gallon", "gal": "gallon",
        "ounce": "ounce", "ounces": "ounce", "oz": "ounce", "fl oz": "ounce",
        "liter": "liter", "liters": "liter", "l": "liter",
        "milliliter": "milliliter", "milliliters": "milliliter", "ml": "milliliter",

        # Weight
        "pound": "pound", "pounds": "pound", "lb": "pound", "lbs": "pound",
        "gram": "gram", "grams": "gram", "g": "gram",
        "kilogram": "kilogram", "kilograms": "kilogram", "kg": "kilogram",

        # Other
        "package": "package", "packages": "package", "pkg": "package",
        "can": "can", "cans": "can",
        "jar": "jar", "jars": "jar",
        "bottle": "bottle", "bottles": "bottle",
        "bunch": "bunch", "bunches": "bunch",
        "clove": "clove", "cloves": "clove",
        "slice": "slice", "slices": "slice",
        "piece": "piece", "pieces": "piece",
        "pinch": "pinch", "pinches": "pinch",
        "dash": "dash", "dashes": "dash",
    }

    # Preparation keywords (after commas usually)
    PREPARATIONS = [
        "chopped", "diced", "minced", "sliced", "crushed", "grated",
        "shredded", "peeled", "seeded", "cored", "julienned",
        "cubed", "halved", "quartered", "whole",
        "fresh", "frozen", "canned", "dried",
        "cooked", "uncooked", "raw",
        "softened", "melted", "room temperature",
        "sifted", "beaten", "whisked",
        "to taste", "as needed", "optional",
    ]

    def parse(self, raw_ingredient: str) -> IngredientStructured:
        """
        Parse a raw ingredient string into structured data.

        Args:
            raw_ingredient: Original ingredient string

        Returns:
            IngredientStructured object
        """
        try:
            # Clean input
            text = raw_ingredient.strip()

            # Extract quantity and unit
            quantity, unit, remaining = self._extract_quantity_unit(text)

            # Extract preparation (after comma)
            name_part, preparation = self._extract_preparation(remaining)

            # Extract modifier and name
            name, modifier = self._extract_name_modifier(name_part)

            # Get category and allergens
            category = get_category(name)
            allergens = get_allergens(name)
            substitutable = is_substitutable(name)

            # Calculate confidence
            confidence = self._calculate_confidence(quantity, unit, name)

            return IngredientStructured(
                raw=raw_ingredient,
                quantity=quantity,
                unit=unit,
                name=name,
                modifier=modifier,
                preparation=preparation,
                category=category,
                allergens=allergens,
                substitutable=substitutable,
                confidence=confidence,
                parse_method="auto"
            )

        except Exception as e:
            # Fallback: minimal structure
            return IngredientStructured(
                raw=raw_ingredient,
                name=raw_ingredient[:50],  # Use first 50 chars as name
                confidence=0.1,
                parse_method="fallback"
            )

    def _extract_quantity_unit(self, text: str) -> Tuple[Optional[float], Optional[str], str]:
        """
        Extract quantity and unit from beginning of string.

        Returns:
            (quantity, unit, remaining_text)
        """
        # Pattern: number (optional fraction) optional unit
        # Examples: "2 cups", "1/2 cup", "2-3 tablespoons", "1 (14 oz) can"
        pattern = r'^(\d+(?:\s*[-/]\s*\d+)?(?:\.\d+)?)\s*(\w+)?\s*(.*)$'
        match = re.match(pattern, text, re.IGNORECASE)

        if match:
            quantity_str, unit_str, remaining = match.groups()

            # Parse quantity (handle fractions)
            try:
                if '/' in quantity_str:
                    parts = quantity_str.split('/')
                    quantity = float(parts[0].strip()) / float(parts[1].strip())
                elif '-' in quantity_str:
                    # Range: use average
                    parts = quantity_str.split('-')
                    quantity = (float(parts[0].strip()) + float(parts[1].strip())) / 2
                else:
                    quantity = float(quantity_str)
            except:
                quantity = None

            # Normalize unit
            unit = None
            if unit_str:
                unit_lower = unit_str.lower()
                unit = self.UNITS.get(unit_lower, unit_str)

            return quantity, unit, remaining.strip()

        # No quantity found
        return None, None, text

    def _extract_preparation(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Extract preparation instructions (usually after comma).

        Returns:
            (name_part, preparation)
        """
        if ',' in text:
            parts = text.split(',', 1)
            name_part = parts[0].strip()
            prep_part = parts[1].strip()

            # Check if prep part contains known preparation keywords
            prep_lower = prep_part.lower()
            if any(keyword in prep_lower for keyword in self.PREPARATIONS):
                return name_part, prep_part

            # Otherwise, might be part of name (e.g., "tomatoes, diced" is prep, but "salt, kosher" is modifier)
            return name_part, prep_part

        return text, None

    def _extract_name_modifier(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Extract ingredient name and optional modifier.

        Returns:
            (name, modifier)
        """
        # Common modifiers
        modifiers = [
            "all-purpose", "self-rising", "whole wheat",
            "fresh", "dried", "frozen", "canned",
            "large", "medium", "small", "extra-large",
            "boneless", "skinless",
            "unsalted", "salted",
            "light", "dark",
            "raw", "cooked",
        ]

        text_lower = text.lower()

        # Check for modifiers
        for mod in modifiers:
            if mod in text_lower:
                # Modifier found
                name = text_lower.replace(mod, "").strip()
                return name, mod

        # No modifier found
        return text.lower().strip(), None

    def _calculate_confidence(self, quantity: Optional[float], unit: Optional[str], name: str) -> float:
        """
        Calculate confidence score for parsing.

        Returns:
            Float between 0.0 and 1.0
        """
        confidence = 0.5  # Start at medium

        # Has quantity: +0.2
        if quantity is not None:
            confidence += 0.2

        # Has unit: +0.2
        if unit is not None:
            confidence += 0.2

        # Has reasonable name (not too short, not empty): +0.1
        if name and len(name) > 2:
            confidence += 0.1

        return min(confidence, 1.0)


class RecipeEnricher:
    """Main enrichment orchestrator."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.parser = SimpleIngredientParser()

    def enrich_sample(self, sample_size: int = 10) -> Dict:
        """
        Enrich a sample of recipes for testing.

        Args:
            sample_size: Number of recipes to process

        Returns:
            Statistics dictionary
        """
        print(f"\n🔬 Enriching {sample_size} sample recipes...")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get sample recipes
        cursor.execute(f"""
            SELECT id, name, ingredients_raw
            FROM recipes
            WHERE ingredients_raw IS NOT NULL
            LIMIT {sample_size}
        """)
        recipes = cursor.fetchall()

        stats = {
            "total": len(recipes),
            "success": 0,
            "partial": 0,
            "failed": 0,
            "avg_confidence": 0.0,
        }

        total_confidence = 0.0

        print("\nProcessing recipes:")
        for recipe in recipes:
            recipe_id = recipe["id"]
            recipe_name = recipe["name"]
            ingredients_raw = json.loads(recipe["ingredients_raw"])

            print(f"\n📝 {recipe_name} (ID: {recipe_id})")
            print(f"   Ingredients: {len(ingredients_raw)}")

            structured = []
            recipe_confidences = []

            for raw_ing in ingredients_raw:
                parsed = self.parser.parse(raw_ing)
                structured.append(parsed.to_dict())
                recipe_confidences.append(parsed.confidence)

                # Show first 3 for sample
                if len(structured) <= 3:
                    print(f"   ✓ {raw_ing[:50]}")
                    print(f"     → {parsed.name} ({parsed.quantity} {parsed.unit or ''}) [{parsed.confidence:.2f}]")

            # Calculate recipe stats
            avg_conf = sum(recipe_confidences) / len(recipe_confidences) if recipe_confidences else 0
            total_confidence += avg_conf

            if avg_conf >= 0.8:
                stats["success"] += 1
            elif avg_conf >= 0.5:
                stats["partial"] += 1
            else:
                stats["failed"] += 1

            print(f"   Average confidence: {avg_conf:.2f}")

        stats["avg_confidence"] = total_confidence / stats["total"] if stats["total"] > 0 else 0

        conn.close()

        return stats

    def enrich_full(self) -> Dict:
        """
        Enrich all recipes in the database.

        Returns:
            Statistics dictionary
        """
        print("\n🚀 Starting full enrichment of all recipes...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if column exists
        cursor.execute("PRAGMA table_info(recipes)")
        columns = [col[1] for col in cursor.fetchall()]

        if "ingredients_structured" not in columns:
            print("   Adding ingredients_structured column...")
            cursor.execute("ALTER TABLE recipes ADD COLUMN ingredients_structured TEXT")
            conn.commit()

        # Get total count
        cursor.execute("SELECT COUNT(*) FROM recipes WHERE ingredients_raw IS NOT NULL")
        total = cursor.fetchone()[0]

        print(f"   Total recipes to process: {total:,}")

        conn.row_factory = sqlite3.Row

        stats = {
            "total": total,
            "success": 0,
            "partial": 0,
            "failed": 0,
            "avg_confidence": 0.0,
        }

        total_confidence = 0.0
        batch_size = 1000
        processed = 0

        # Process in batches
        cursor.execute("""
            SELECT id, name, ingredients_raw
            FROM recipes
            WHERE ingredients_raw IS NOT NULL
        """)

        print("\nProcessing:")
        while True:
            recipes = cursor.fetchmany(batch_size)
            if not recipes:
                break

            for recipe in recipes:
                recipe_id = recipe["id"]
                ingredients_raw = json.loads(recipe["ingredients_raw"])

                structured = []
                recipe_confidences = []

                for raw_ing in ingredients_raw:
                    parsed = self.parser.parse(raw_ing)
                    structured.append(parsed.to_dict())
                    recipe_confidences.append(parsed.confidence)

                # Calculate recipe stats
                avg_conf = sum(recipe_confidences) / len(recipe_confidences) if recipe_confidences else 0
                total_confidence += avg_conf

                if avg_conf >= 0.8:
                    stats["success"] += 1
                elif avg_conf >= 0.5:
                    stats["partial"] += 1
                else:
                    stats["failed"] += 1

                # Update database
                cursor.execute("""
                    UPDATE recipes
                    SET ingredients_structured = ?
                    WHERE id = ?
                """, (json.dumps(structured), recipe_id))

                processed += 1

                # Progress indicator
                if processed % 1000 == 0:
                    pct = (processed / total) * 100
                    print(f"   [{pct:5.1f}%] {processed:,} / {total:,} recipes processed...")

            conn.commit()

        stats["avg_confidence"] = total_confidence / stats["total"] if stats["total"] > 0 else 0

        conn.close()

        return stats


def print_stats(stats: Dict):
    """Print enrichment statistics."""
    print("\n" + "="*60)
    print("📊 ENRICHMENT STATISTICS")
    print("="*60)
    print(f"Total recipes:       {stats['total']:,}")
    print(f"✅ High quality:     {stats['success']:,} ({stats['success']/stats['total']*100:.1f}%)")
    print(f"⚠️  Partial:          {stats['partial']:,} ({stats['partial']/stats['total']*100:.1f}%)")
    print(f"❌ Low quality:      {stats['failed']:,} ({stats['failed']/stats['total']*100:.1f}%)")
    print(f"📈 Avg confidence:   {stats['avg_confidence']:.3f}")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description="Enrich recipe ingredients with structured data")
    parser.add_argument("--sample", type=int, help="Process N sample recipes for testing")
    parser.add_argument("--full", action="store_true", help="Process all recipes")
    parser.add_argument("--db", default="data/recipes.db", help="Path to recipes database")

    args = parser.parse_args()

    if not args.sample and not args.full:
        parser.print_help()
        print("\n❌ Error: Must specify --sample N or --full")
        sys.exit(1)

    enricher = RecipeEnricher(args.db)

    if args.sample:
        stats = enricher.enrich_sample(args.sample)
    else:
        stats = enricher.enrich_full()

    print_stats(stats)

    print("\n✅ Enrichment complete!")


if __name__ == "__main__":
    main()
