from __future__ import annotations

from aiohttp import web

from tagent.bot.app import create_app
from tagent.bot.settings import TeamsAdapterSettings


def main() -> None:
    settings = TeamsAdapterSettings()
    app = create_app(settings)
    web.run_app(app, host="0.0.0.0", port=3978)


if __name__ == "__main__":
    main()
