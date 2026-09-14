import os
import asyncio
import re
import random
import sqlite3

import discord
from discord.ext import commands
from dotenv import load_dotenv


# ==================================================
# Configuration
# ==================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
QUOTE_CHANNEL_ID = int(os.getenv("QUOTE_CHANNEL_ID"))


# ==================================================
# Discord setup
# ==================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==================================================
# Database setup
# ==================================================

db = sqlite3.connect("quotes.db")

db.execute("""
    CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quote TEXT NOT NULL,
        year INTEGER NOT NULL,
        message_id TEXT NOT NULL UNIQUE
    )
""")

db.commit()


# ==================================================
# Quote parser
# ==================================================

QUOTE_PATTERN = re.compile(
    r"^(?P<quote>.*?)\s*-\s*(?P<attribution>.+?)\s+(?P<year>\d{4})$",
    re.DOTALL
)


def parse_quote(content):
    """
    Parse a message in the format:

    Quote text - Name 2026

    Names can contain spaces.
    If the attribution contains " to ",
    everything after " to " is ignored.

    """

    match = QUOTE_PATTERN.match(content.strip())

    if not match:
        return None

    quote = match.group("quote").strip()
    attribution = match.group("attribution").strip()
    year = int(match.group("year"))

    # --------------------------------------------------
    # Remove everything after " to "
    # --------------------------------------------------
    
    attribution_parts = re.split(
        r"\s+to\s+",
        attribution,
        maxsplit=1,
        flags=re.IGNORECASE
    )

    name = attribution_parts[0].strip()

    if not name:
        return None

    return {
        "quote": quote,
        "name": name,
        "year": year
    }


# ==================================================
# Save quote to database
# ==================================================

def save_quote(parsed, message_id):
    """
    Save a parsed quote to SQLite.

    Returns True if a new quote was added.
    Returns False if the quote already exists.
    """

    try:

        db.execute("""
            INSERT INTO quotes
            (name, quote, year, message_id)

            VALUES (?, ?, ?, ?)
        """, (
            parsed["name"],
            parsed["quote"],
            parsed["year"],
            str(message_id)
        ))

        db.commit()

        return True

    except sqlite3.IntegrityError:

        # Message is already in the database.
        return False


# ==================================================
# Bot startup
# ==================================================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")

    try:

        synced = await bot.tree.sync()

        print(f"Synced {len(synced)} command(s)")

    except Exception as e:

        print(f"Failed to sync commands: {e}")


# ==================================================
# Watch new messages
# ==================================================

@bot.event
async def on_message(message):

    # Ignore bot messages.
    if message.author.bot:
        return

    # Only watch the quote channel.
    if message.channel.id != QUOTE_CHANNEL_ID:
        return

    parsed = parse_quote(message.content)

    if parsed is None:
        return

    added = save_quote(
        parsed,
        message.id
    )

    if added:

        print()
        print("New quote added:")
        print(f"  Name:  {parsed['name']}")
        print(f"  Year:  {parsed['year']}")
        print(f"  Quote: {parsed['quote']}")
        print()


# ==================================================
# /ping
# ==================================================

@bot.tree.command(
    name="ping",
    description="Check whether the bot is alive."
)
async def ping(interaction: discord.Interaction):

    await interaction.response.send_message(
        "Pong! 🏓"
    )


# ==================================================
# /scanquotes
# ==================================================

@bot.tree.command(
    name="scanquotes",
    description="Scan the quote channel and import quotes."
)
async def scanquotes(interaction: discord.Interaction):

    await interaction.response.send_message(
        "📚 Scanning the quote archive..."
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
    added = 0

    async for message in channel.history(
        limit=None,
        oldest_first=True
    ):

        if message.author.bot:
            continue

        parsed = parse_quote(message.content)

        if parsed is None:
            continue

        found += 1

        if save_quote(parsed, message.id):
            added += 1

            print()
            print("Imported quote:")
            print(f"  Name:  {parsed['name']}")
            print(f"  Year:  {parsed['year']}")
            print(f"  Quote: {parsed['quote']}")

    print()
    print("=" * 60)
    print(f"Quotes found: {found}")
    print(f"New quotes added: {added}")
    print("=" * 60)
    print()

    await interaction.followup.send(
        f"✅ Scan complete!\n"
        f"Found **{found}** quotes.\n"
        f"Added **{added}** new quotes to the database."
    )


# ==================================================
# /quote
# ==================================================

@bot.tree.command(
    name="quote",
    description="Get a random quote from someone."
)
async def quote_command(
    interaction: discord.Interaction,
    name: str
):

    # LOWER() on both sides makes this case-insensitive.
    cursor = db.execute("""
        SELECT quote, year, name
        FROM quotes
        WHERE LOWER(name) = LOWER(?)
    """, (name,))

    quotes = cursor.fetchall()

    if not quotes:

        await interaction.response.send_message(
            f"❌ I couldn't find any quotes from **{name}**."
        )

        return

    quote, year, stored_name = random.choice(quotes)

    await interaction.response.send_message(
        f"💬 **{stored_name}, {year}:**\n"
        f"> {quote}"
    )


# ==================================================
# Start bot
# ==================================================

async def main():

    async with bot:
        await bot.start(TOKEN)


asyncio.run(main())