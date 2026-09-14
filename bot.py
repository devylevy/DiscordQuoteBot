import os
import asyncio
import re

import discord
from discord.ext import commands
from dotenv import load_dotenv


# --------------------------------------------------
# Load configuration
# --------------------------------------------------

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
QUOTE_CHANNEL_ID = int(os.getenv("QUOTE_CHANNEL_ID"))


# --------------------------------------------------
# Discord setup
# --------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# --------------------------------------------------
# Quote parser
# --------------------------------------------------

# Looks for:
#
# Some quote text here. -Derrick 2026
#
# and extracts:
#
# quote  = Some quote text here.
# name   = Derrick
# year   = 2026

QUOTE_PATTERN = re.compile(
    r"^(?P<quote>.*?)\s*-\s*(?P<name>[A-Za-z0-9_]+)\s+(?P<year>\d{4})$",
    re.DOTALL
)


def parse_quote(content):
    """
    Try to turn a Discord message into a quote.

    Returns a dictionary if the message matches
    our quote format, otherwise returns None.
    """

    match = QUOTE_PATTERN.match(content.strip())

    if not match:
        return None

    return {
        "quote": match.group("quote").strip(),
        "name": match.group("name").strip(),
        "year": int(match.group("year"))
    }


# --------------------------------------------------
# Bot startup
# --------------------------------------------------

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")

    except Exception as e:
        print(f"Failed to sync commands: {e}")


# --------------------------------------------------
# /ping
# --------------------------------------------------

@bot.tree.command(
    name="ping",
    description="Check whether the bot is alive."
)
async def ping(interaction: discord.Interaction):

    await interaction.response.send_message(
        "Pong! 🏓"
    )


# --------------------------------------------------
# /scanquotes
# --------------------------------------------------

@bot.tree.command(
    name="scanquotes",
    description="Scan the quote channel and show detected quotes."
)
async def scanquotes(interaction: discord.Interaction):

    # Immediately acknowledge the command.
    # Discord requires a response within a few seconds.
    await interaction.response.send_message(
        "📚 Scanning the quote channel..."
    )

    channel = bot.get_channel(QUOTE_CHANNEL_ID)

    if channel is None:

        await interaction.followup.send(
            "❌ I couldn't find the configured quote channel."
        )

        return

    print()
    print("=" * 60)
    print(f"Scanning #{channel.name}")
    print("=" * 60)

    found = 0

    async for message in channel.history(
        limit=None,
        oldest_first=True
    ):

        # Ignore messages sent by bots.
        if message.author.bot:
            continue

        parsed = parse_quote(message.content)

        if parsed is None:
            continue

        found += 1

        print()
        print("Found quote:")
        print(f"  Name:  {parsed['name']}")
        print(f"  Year:  {parsed['year']}")
        print(f"  Quote: {parsed['quote']}")
        print(f"  Message ID: {message.id}")

    print()
    print("=" * 60)
    print(f"Finished scanning. Found {found} quotes.")
    print("=" * 60)
    print()

    await interaction.followup.send(
        f"✅ Scan complete! I found **{found} quotes**.\n"
        f"Check the bot's console to see them."
    )


# --------------------------------------------------
# Start bot
# --------------------------------------------------

async def main():

    async with bot:
        await bot.start(TOKEN)


asyncio.run(main())