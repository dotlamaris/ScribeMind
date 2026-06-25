import asyncio

from nanobot import Nanobot


async def main() -> None:
    async with Nanobot.from_config(
        "/home/runner/workspace/.nanobot/config.json"
    ) as bot:
        result = await bot.run("What time is it in Tokyo?")
    print(result.content)


asyncio.run(main())
