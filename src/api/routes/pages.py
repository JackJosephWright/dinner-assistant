"""
Page routes for serving HTML templates.

Serves the web UI pages using Jinja2 templates.
"""
import logging
import os
import sys

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# Add project root for imports
project_root = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from ..services.plan_service import get_plan_service, AsyncPlanService

logger = logging.getLogger(__name__)

router = APIRouter()

# Set up Jinja2 templates (reuse Flask templates)
templates_dir = os.path.join(project_root, 'src', 'web', 'templates')
templates = Jinja2Templates(directory=templates_dir)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Redirect to plan page."""
    return RedirectResponse(url="/plan")


@router.get("/plan", response_class=HTMLResponse)
async def plan_page(request: Request):
    """Render the meal planning page."""
    return templates.TemplateResponse(
        "plan.html",
        {
            "request": request,
            "current_plan": None,
            "user_profile": None,
        }
    )


@router.get("/shop", response_class=HTMLResponse)
async def shop_page(
    request: Request,
    service: AsyncPlanService = Depends(lambda: get_plan_service())
):
    """Render the shopping list page."""
    return templates.TemplateResponse(
        "shop.html",
        {
            "request": request,
            "grocery_list": None,
        }
    )


@router.get("/cook", response_class=HTMLResponse)
async def cook_page(
    request: Request,
    service: AsyncPlanService = Depends(lambda: get_plan_service())
):
    """Render the cooking guide page."""
    return templates.TemplateResponse(
        "cook.html",
        {
            "request": request,
            "current_plan": None,
        }
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render the settings page."""
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
        }
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page."""
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
        }
    )
