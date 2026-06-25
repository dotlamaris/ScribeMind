import asyncio

from nanobot import Nanobot

import os

config_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".nanobot", "config.json"
)


async def async_agent(query):
    async with Nanobot.from_config(config_path) as bot:
        result = await bot.run(query)
        return result.content


def run_agent(query):
    return asyncio.run(async_agent(query))


if __name__ == "__main__":
    run_agent("What time is it in Tokyo?")
