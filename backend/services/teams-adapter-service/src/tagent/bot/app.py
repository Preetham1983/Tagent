"""Bot application entrypoint — configures and runs the Teams bot."""

from __future__ import annotations

from aiohttp import web
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity

from tagent.bot.controllers.message_controller import MessageController
from tagent.bot.settings import TeamsAdapterSettings


def create_app(settings: TeamsAdapterSettings) -> web.Application:
    """Create the aiohttp web application with bot message endpoint."""
    adapter_settings = BotFrameworkAdapterSettings(
        app_id=settings.ms_app_id,
        app_password=settings.ms_app_password,
    )
    adapter = BotFrameworkAdapter(adapter_settings)

    controller = MessageController(settings.orchestrator_base_url)

    async def messages(req: web.Request) -> web.Response:
        if req.content_type == "application/json":
            body = await req.json()
        else:
            return web.Response(status=415)

        activity = Activity().deserialize(body)
        auth_header = req.headers.get("Authorization", "")

        async def _call_bot(turn_context: TurnContext) -> None:
            await controller.on_turn(turn_context)

        await adapter.process_activity(activity, auth_header, _call_bot)
        return web.Response(status=201)

    app = web.Application()
    app.router.add_post("/api/messages", messages)
    return app
