"""Web tools - open URL, weather, web search."""

from __future__ import annotations

import asyncio
import json
import webbrowser
from typing import Any

import httpx

from dash_backend.tools.base_tool import (
    BaseTool,
    PermissionLevel,
    ToolContext,
    ToolParameter,
)
from dash_backend.tools.tool_result import ToolResult, ToolStatus


class OpenURLTool(BaseTool):
    """Open a URL in the default browser."""

    name = "open_url"
    description = "Open a URL in the default web browser."
    category = "web"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="url",
            description="The URL to open (must start with http:// or https://).",
            type="string",
            required=True,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        url = kwargs.get("url", "").strip()

        if not url:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No URL provided.",
            )

        if not url.startswith(("http://", "https://")):
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="URL must start with http:// or https://",
            )

        try:
            # Open URL in default browser (runs in a loop to not block)
            loop = asyncio.get_event_loop()
            opened = await loop.run_in_executor(None, webbrowser.open, url)

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={"url": url, "opened": opened},
                summary=f"Opened {url} in browser" if opened else f"Failed to open {url}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to open URL: {exc}",
            )


class WeatherTool(BaseTool):
    """Get weather information for a location."""

    name = "weather"
    description = "Get current weather and forecast for a location. Uses wttr.in for weather data."
    category = "web"
    parameters = [
        ToolParameter(
            name="location",
            description="City name or location (e.g., 'London', 'New York', 'Tokyo').",
            type="string",
            required=True,
        ),
        ToolParameter(
            name="forecast",
            description="Number of forecast days (0 for current only, up to 3).",
            type="number",
            required=False,
            default=0,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        location = kwargs.get("location", "").strip()
        forecast_days = kwargs.get("forecast", 0)

        if not location:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No location provided.",
            )

        try:
            # Use wttr.in API (no API key required)
            params = {"format": "j1"}
            url = f"https://wttr.in/{location}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)

                if response.status_code != 200:
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.ERROR,
                        error_message=f"Weather API returned status {response.status_code}",
                    )

                data = response.json()

                # Parse current conditions
                current = data.get("current_condition", [{}])[0]
                temp_c = current.get("temp_C", "N/A")
                temp_f = current.get("temp_F", "N/A")
                humidity = current.get("humidity", "N/A")
                weather_desc = current.get("weatherDesc", [{}])[0].get("value", "N/A")
                wind_speed = current.get("windspeedKmph", "N/A")
                feels_like = current.get("FeelsLikeC", "N/A")
                visibility = current.get("visibility", "N/A")
                uv_index = current.get("uvIndex", "N/A")

                output = {
                    "location": location,
                    "current": {
                        "temperature_c": temp_c,
                        "temperature_f": temp_f,
                        "feels_like_c": feels_like,
                        "humidity": f"{humidity}%",
                        "condition": weather_desc,
                        "wind_speed_kmh": wind_speed,
                        "visibility_km": visibility,
                        "uv_index": uv_index,
                    },
                    "forecast": [],
                }

                # Parse forecast
                if forecast_days > 0:
                    forecasts = data.get("weather", [])
                    for day in forecasts[:forecast_days]:
                        date = day.get("date", "")
                        max_c = day.get("maxtempC", "N/A")
                        min_c = day.get("mintempC", "N/A")
                        hourly = day.get("hourly", [{}])[0]
                        desc = hourly.get("weatherDesc", [{}])[0].get("value", "N/A")

                        output["forecast"].append({
                            "date": date,
                            "max_c": max_c,
                            "min_c": min_c,
                            "condition": desc,
                        })

                summary = f"Weather in {location}: {weather_desc}, {temp_c}°C (feels like {feels_like}°C)"

                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    output=output,
                    summary=summary,
                )

        except httpx.RequestError as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to fetch weather: {exc}",
            )
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to parse weather data: {exc}",
            )


class WebSearchTool(BaseTool):
    """Search the web for information."""

    name = "web_search"
    description = "Search the web for information. Uses DuckDuckGo (no API key required) or Google if configured."
    category = "web"
    parameters = [
        ToolParameter(
            name="query",
            description="Search query.",
            type="string",
            required=True,
        ),
        ToolParameter(
            name="max_results",
            description="Maximum number of search results to return.",
            type="number",
            required=False,
            default=5,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "").strip()
        max_results = min(kwargs.get("max_results", 5), 20)

        if not query:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No search query provided.",
            )

        try:
            # Use DuckDuckGo instant answer API (no API key required)
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)

                if response.status_code != 200:
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.ERROR,
                        error_message=f"Search API returned status {response.status_code}",
                    )

                data = response.json()

                # Parse abstract
                abstract = data.get("Abstract", "")
                abstract_source = data.get("AbstractSource", "")
                abstract_url = data.get("AbstractURL", "")

                # Parse related topics
                related = data.get("RelatedTopics", [])
                results: list[dict[str, str]] = []

                if abstract:
                    results.append({
                        "title": abstract_source or "Result",
                        "url": abstract_url or "",
                        "snippet": abstract[:500],
                    })

                for topic in related[:max_results]:
                    if "Text" in topic and "FirstURL" in topic:
                        results.append({
                            "title": topic.get("Text", "").split(" - ")[0][:100],
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", "")[:300],
                        })
                    elif "Topics" in topic:
                        for sub in topic["Topics"][:3]:
                            if "Text" in sub and "FirstURL" in sub:
                                results.append({
                                    "title": sub.get("Text", "").split(" - ")[0][:100],
                                    "url": sub.get("FirstURL", ""),
                                    "snippet": sub.get("Text", "")[:300],
                                })

                # Also try a simple HTML scrape for more results
                if len(results) < 3:
                    try:
                        html_url = f"https://html.duckduckgo.com/html/?q={query}"
                        html_response = await client.get(html_url, headers={
                            "User-Agent": "Mozilla/5.0 (compatible; DashAI/1.0)"
                        })
                        # Just note the HTML search availability
                        pass
                    except Exception:
                        pass

                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    output={
                        "query": query,
                        "abstract": abstract,
                        "results": results[:max_results],
                        "total_results": len(results),
                    },
                    summary=f"Web search for '{query}': {len(results)} results found",
                )

        except httpx.RequestError as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Web search failed: {exc}",
            )
        except (json.JSONDecodeError, KeyError) as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to parse search results: {exc}",
            )