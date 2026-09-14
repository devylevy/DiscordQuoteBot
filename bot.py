import os
import asyncio
import re
import random
import sqlite3
from collections import Counter

import discord
from discord import app_commands
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
# Common words to ignore when calculating
# "Most Common Word"
# ==================================================

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all",
    "am", "an", "and", "any", "are", "as", "at", "be", "because",
    "been", "before", "being", "below", "between", "both", "but",
    "by", "can", "could", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "get",
    "gets", "got", "had", "has", "have", "having", "he", "her",
    "here", "hers", "herself", "him", "himself", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "it's", "itself", "just",
    "me", "more", "most", "my", "myself", "no", "nor", "not",
    "now", "of", "off", "on", "once", "only", "or", "other",
    "our", "ours", "ourselves", "out", "over", "own", "same",
    "she", "should", "so", "some", "such", "than", "that",
    "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom",
    "why", "will", "with", "would", "you", "your", "yours",
    "yourself", "yourselves"
}


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

    Example:

        Something funny - Mom Smith to Sam 2026

    becomes:

        Name: Mom Smith
        Year: 2026
    """

    match = QUOTE_PATTERN.match(content.strip())

    if not match:
        return None

    quote = match.group("quote").strip()
    attribution = match.group("attribution").strip()
    year = int(match.group("year"))

    # Remove everything after " to "
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
# Save quote
# ==================================================

def save_quote(parsed, message_id):

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

    if message.author.bot:
        return

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
@app_commands.describe(
    name="The person whose quote you want."
)
async def quote_command(
    interaction: discord.Interaction,
    name: str
):

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
# /quote AUTOCOMPLETE
# ==================================================

@quote_command.autocomplete("name")
async def quote_autocomplete(
    interaction: discord.Interaction,
    current: str
):

    cursor = db.execute("""
        SELECT DISTINCT name
        FROM quotes
        WHERE LOWER(name) LIKE LOWER(?)
        ORDER BY name
        LIMIT 25
    """, (f"%{current}%",))

    names = cursor.fetchall()

    return [
        app_commands.Choice(
            name=name[0],
            value=name[0]
        )
        for name in names
    ]


# ==================================================
# /randomquote
# ==================================================

@bot.tree.command(
    name="randomquote",
    description="Get a completely random quote from the archive."
)
async def randomquote(interaction: discord.Interaction):

    cursor = db.execute("""
        SELECT quote, year, name
        FROM quotes
        ORDER BY RANDOM()
        LIMIT 1
    """)

    result = cursor.fetchone()

    if result is None:

        await interaction.response.send_message(
            "❌ There aren't any quotes in the database yet."
        )

        return

    quote, year, name = result

    await interaction.response.send_message(
        f"🎲 **Random Quote**\n\n"
        f"**{name}, {year}:**\n"
        f"> {quote}"
    )


# ==================================================
# /leaderboard
# ==================================================

@bot.tree.command(
    name="leaderboard",
    description="Show who has the most archived quotes."
)
async def leaderboard(interaction: discord.Interaction):

    cursor = db.execute("""
        SELECT name, COUNT(*) AS quote_count
        FROM quotes
        GROUP BY LOWER(name)
        ORDER BY quote_count DESC, name ASC
        LIMIT 10
    """)

    results = cursor.fetchall()

    if not results:

        await interaction.response.send_message(
            "❌ There aren't any quotes in the database yet."
        )

        return

    medals = [
        "🥇",
        "🥈",
        "🥉"
    ]

    lines = []

    for index, (name, count) in enumerate(results):

        if index < 3:
            prefix = medals[index]
        else:
            prefix = f"**{index + 1}.**"

        lines.append(
            f"{prefix} **{name}** — {count} quote"
            f"{'s' if count != 1 else ''}"
        )

    embed = discord.Embed(
        title="🏆 Quote Leaderboard",
        description="\n".join(lines)
    )

    total = db.execute(
        "SELECT COUNT(*) FROM quotes"
    ).fetchone()[0]

    embed.set_footer(
        text=f"{total} total quotes in the archive"
    )

    await interaction.response.send_message(
        embed=embed
    )


# ==================================================
# Most common meaningful word
# ==================================================

def get_most_common_word(name):

    cursor = db.execute("""
        SELECT quote
        FROM quotes
        WHERE LOWER(name) = LOWER(?)
    """, (name,))

    quotes = cursor.fetchall()

    word_counter = Counter()

    for (quote,) in quotes:

        # Extract words and ignore punctuation.
        words = re.findall(
            r"[A-Za-z']+",
            quote.lower()
        )

        for word in words:

            if word in STOP_WORDS:
                continue

            # Ignore one-letter words.
            if len(word) <= 1:
                continue

            word_counter[word] += 1

    if not word_counter:
        return None, 0

    return word_counter.most_common(1)[0]


# ==================================================
# /quotestats
# ==================================================

@bot.tree.command(
    name="quotestats",
    description="Show statistics for someone's quotes."
)
@app_commands.describe(
    name="The person whose quote statistics you want."
)
async def quotestats(
    interaction: discord.Interaction,
    name: str
):

    # --------------------------------------------------
    # Total quotes
    # --------------------------------------------------

    total = db.execute("""
        SELECT COUNT(*)
        FROM quotes
        WHERE LOWER(name) = LOWER(?)
    """, (name,)).fetchone()[0]

    if total == 0:

        await interaction.response.send_message(
            f"❌ I couldn't find any quotes from **{name}**."
        )

        return

    # --------------------------------------------------
    # Most quoted year
    # --------------------------------------------------

    most_quoted_year = db.execute("""
        SELECT year, COUNT(*) AS count
        FROM quotes
        WHERE LOWER(name) = LOWER(?)
        GROUP BY year
        ORDER BY count DESC, year DESC
        LIMIT 1
    """, (name,)).fetchone()

    year = most_quoted_year[0]
    year_count = most_quoted_year[1]

    # --------------------------------------------------
    # First recorded quote
    # --------------------------------------------------

    first_quote = db.execute("""
        SELECT quote, year, name
        FROM quotes
        WHERE LOWER(name) = LOWER(?)
        ORDER BY id ASC
        LIMIT 1
    """, (name,)).fetchone()

    first_quote_text = first_quote[0]
    first_quote_year = first_quote[1]
    stored_name = first_quote[2]

    # --------------------------------------------------
    # Last recorded quote
    # --------------------------------------------------

    last_quote = db.execute("""
        SELECT quote, year, name
        FROM quotes
        WHERE LOWER(name) = LOWER(?)
        ORDER BY id DESC
        LIMIT 1
    """, (name,)).fetchone()

    last_quote_text = last_quote[0]
    last_quote_year = last_quote[1]

    # --------------------------------------------------
    # Most common word
    # --------------------------------------------------

    common_word, common_word_count = get_most_common_word(name)

    if common_word is None:
        common_word_display = "No meaningful words found"
    else:
        common_word_display = (
            f"**{common_word}** "
            f"({common_word_count} occurrence"
            f"{'s' if common_word_count != 1 else ''})"
        )

    # --------------------------------------------------
    # Build embed
    # --------------------------------------------------

    embed = discord.Embed(
        title=f"📊 Quote Statistics — {stored_name}",
        description=(
            f"Here is the archaeological record "
            f"of **{stored_name}**."
        )
    )

    embed.add_field(
        name="📚 Total Quotes",
        value=f"**{total}**",
        inline=True
    )

    embed.add_field(
        name="📅 Most Quoted Year",
        value=f"**{year}** ({year_count} quotes)",
        inline=True
    )

    embed.add_field(
        name="🔤 Most Common Word",
        value=common_word_display,
        inline=True
    )

    embed.add_field(
        name=f"🏛️ First Recorded Quote — {first_quote_year}",
        value=f"> {first_quote_text}",
        inline=False
    )

    embed.add_field(
        name=f"🕐 Last Recorded Quote — {last_quote_year}",
        value=f"> {last_quote_text}",
        inline=False
    )

    embed.set_footer(
        text="The collective never forgets."
    )

    await interaction.response.send_message(
        embed=embed
    )


# ==================================================
# Start bot
# ==================================================

async def main():

    async with bot:
        await bot.start(TOKEN)


asyncio.run(main())