import asyncio

from nanobot import Nanobot

import os

config_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".nanobot", "config.json"
)


async def main() -> None:
    async with Nanobot.from_config(config_path) as bot:
        result = await bot.run("What time is it in Tokyo?")
    print(result.content)


asyncio.run(main())


async def run_agent(query):
    async with Nanobot.from_config(config_path) as bot:
        result = await bot.run(query)
        return result.content

