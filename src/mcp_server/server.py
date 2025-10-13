#!/usr/bin/env python3
"""
MCP Server for Meal Planning Assistant.

This server exposes tools for planning, shopping, and cooking agents
via the Model Context Protocol.
"""

import asyncio
import logging
from typing import Any, Dict, List
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from ..data.database import DatabaseInterface
from .tools.planning_tools import PlanningTools, PLANNING_TOOL_DEFINITIONS

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class MealPlanningServer:
    """MCP Server for meal planning tools."""

    def __init__(self, db_dir: str = "data"):
        """
        Initialize the MCP server.

        Args:
            db_dir: Directory containing database files
        """
        self.app = Server("meal-planning-assistant")
        self.db = DatabaseInterface(db_dir=db_dir)
        self.planning_tools = PlanningTools(self.db)

        # Register handlers
        self._register_handlers()

        logger.info("Meal Planning MCP Server initialized")

    def _register_handlers(self):
        """Register MCP protocol handlers."""

        @self.app.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools."""
            tools = []

            # Convert planning tool definitions to MCP Tool objects
            for tool_def in PLANNING_TOOL_DEFINITIONS:
                tools.append(
                    Tool(
                        name=tool_def["name"],
                        description=tool_def["description"],
                        inputSchema=tool_def["input_schema"],
                    )
                )

            logger.info(f"Listed {len(tools)} tools")
            return tools

        @self.app.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """
            Handle tool calls from agents.

            Args:
                name: Tool name
                arguments: Tool arguments

            Returns:
                Tool results as TextContent
            """
            logger.info(f"Tool called: {name} with arguments: {arguments}")

            try:
                # Route to appropriate tool
                result = None

                if name == "search_recipes":
                    result = self.planning_tools.search_recipes(
                        query=arguments.get("query"),
                        max_time=arguments.get("max_time"),
                        tags=arguments.get("tags"),
                        exclude_ids=arguments.get("exclude_ids"),
                        limit=arguments.get("limit", 20),
                    )

                elif name == "get_meal_history":
                    result = self.planning_tools.get_meal_history(
                        weeks_back=arguments.get("weeks_back", 8)
                    )

                elif name == "save_meal_plan":
                    result = self.planning_tools.save_meal_plan(
                        week_of=arguments["week_of"],
                        meals=arguments["meals"],
                        preferences_applied=arguments.get("preferences_applied"),
                    )

                elif name == "get_user_preferences":
                    result = self.planning_tools.get_user_preferences()

                elif name == "get_recipe_details":
                    result = self.planning_tools.get_recipe_details(
                        recipe_id=arguments["recipe_id"]
                    )

                else:
                    error_msg = f"Unknown tool: {name}"
                    logger.error(error_msg)
                    return [TextContent(type="text", text=error_msg)]

                # Format result as JSON string
                import json

                result_text = json.dumps(result, indent=2)
                return [TextContent(type="text", text=result_text)]

            except Exception as e:
                error_msg = f"Error executing tool {name}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return [TextContent(type="text", text=error_msg)]

    async def run(self):
        """Run the MCP server."""
        logger.info("Starting MCP server...")
        async with stdio_server() as (read_stream, write_stream):
            await self.app.run(
                read_stream,
                write_stream,
                self.app.create_initialization_options(),
            )


async def main():
    """Main entry point."""
    # Determine db directory relative to script location
    script_dir = Path(__file__).parent.parent.parent  # Go up to project root
    db_dir = script_dir / "data"

    server = MealPlanningServer(db_dir=str(db_dir))
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
