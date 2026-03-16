"""Jinja2 template rendering utility with theme injection."""

from typing import Any

from jinja2 import Environment, TemplateError
from jinja2.environment import Template as JinjaTemplate

from app.utils.logging.db_logger import get_logger
from app.utils.settings.theme import ThemeTokens

logger = get_logger(__name__)


def inject_theme_css_variables(html: str, theme_tokens: ThemeTokens) -> str:
    """Inject CSS variables for theme tokens into HTML.

    Injects a <style> tag with CSS variables at the beginning of the <head> section,
    or creates a <head> section if it doesn't exist.

    Args:
        html: HTML template string
        theme_tokens: ThemeTokens object with all theme color values

    Returns:
        HTML string with CSS variables injected
    """
    css_variables = f"""
:root {{
    --primary: {theme_tokens.primary};
    --primary-foreground: {theme_tokens.primaryForeground};
    --background: {theme_tokens.background};
    --foreground: {theme_tokens.foreground};
    --card: {theme_tokens.card};
    --card-foreground: {theme_tokens.cardForeground};
    --popover: {theme_tokens.popover};
    --popover-foreground: {theme_tokens.popoverForeground};
    --secondary: {theme_tokens.secondary};
    --secondary-foreground: {theme_tokens.secondaryForeground};
    --muted: {theme_tokens.muted};
    --muted-foreground: {theme_tokens.mutedForeground};
    --accent: {theme_tokens.accent};
    --accent-foreground: {theme_tokens.accentForeground};
    --destructive: {theme_tokens.destructive};
    --border: {theme_tokens.border};
    --input: {theme_tokens.input};
    --ring: {theme_tokens.ring};
    --success: {theme_tokens.success};
    --success-foreground: {theme_tokens.successForeground};
    --warning: {theme_tokens.warning};
    --warning-foreground: {theme_tokens.warningForeground};
    --info: {theme_tokens.info};
    --info-foreground: {theme_tokens.infoForeground};
    --chart1: {theme_tokens.chart1};
    --chart2: {theme_tokens.chart2};
    --chart3: {theme_tokens.chart3};
    --chart4: {theme_tokens.chart4};
    --chart5: {theme_tokens.chart5};
    --sidebar: {theme_tokens.sidebar};
    --sidebar-foreground: {theme_tokens.sidebarForeground};
    --sidebar-primary: {theme_tokens.sidebarPrimary};
    --sidebar-primary-foreground: {theme_tokens.sidebarPrimaryForeground};
    --sidebar-accent: {theme_tokens.sidebarAccent};
    --sidebar-accent-foreground: {theme_tokens.sidebarAccentForeground};
    --sidebar-border: {theme_tokens.sidebarBorder};
    --sidebar-ring: {theme_tokens.sidebarRing};
}}

/* Default styling using theme variables - templates can override */
html, body {{
    margin: 0;
    padding: 0;
    background: var(--background);
    color: var(--foreground);
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    line-height: 1.5;
}}

body {{
    padding: 1rem;
}}

h1, h2, h3, h4, h5, h6 {{
    color: var(--foreground);
    margin-top: 1.5em;
    margin-bottom: 0.5em;
}}

h1 {{
    color: var(--primary);
    font-size: 2rem;
    font-weight: 600;
}}

h2 {{
    font-size: 1.5rem;
    font-weight: 600;
}}

p {{
    margin: 1em 0;
}}

table {{
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
}}

table th, table td {{
    border: 1px solid var(--border);
    padding: 0.5rem;
    text-align: left;
}}

table th {{
    background: var(--muted);
    color: var(--muted-foreground);
    font-weight: 600;
}}

ul, ol {{
    margin: 1em 0;
    padding-left: 2em;
}}

li {{
    margin: 0.5em 0;
}}
"""

    # Try to inject into existing <head> tag
    if "<head>" in html.lower():
        # Find the first <head> tag (case-insensitive)
        import re

        pattern = re.compile(r"<head>", re.IGNORECASE)
        html = pattern.sub(f"<head><style>{css_variables}</style>", html, count=1)
    elif "<html>" in html.lower():
        # Insert <head> section after <html> tag
        import re

        pattern = re.compile(r"<html[^>]*>", re.IGNORECASE)
        html = pattern.sub(
            f"\\g<0><head><style>{css_variables}</style></head>", html, count=1
        )
    else:
        # No HTML structure, prepend with head and style
        html = f"<head><style>{css_variables}</style></head>{html}"

    return html


def render_template(
    html: str, context: dict[str, Any], theme_tokens: ThemeTokens
) -> str:
    """Render Jinja2 template with theme injection.

    Args:
        html: Jinja2 template HTML string
        context: Dictionary of variables to pass to template
        theme_tokens: ThemeTokens object for CSS variable injection

    Returns:
        Rendered HTML string

    Raises:
        TemplateError: If template rendering fails
    """
    try:
        # Inject CSS variables into HTML before rendering
        html_with_theme = inject_theme_css_variables(html, theme_tokens)

        # Create Jinja2 environment with autoescape enabled for security
        env = Environment(
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Parse and render template
        template: JinjaTemplate = env.from_string(html_with_theme)
        rendered = template.render(**context)

        logger.info(f"Successfully rendered Jinja template ({len(rendered)} chars)")
        return rendered

    except TemplateError as e:
        logger.error(f"Jinja template error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error rendering template: {str(e)}")
        raise
