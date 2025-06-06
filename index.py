import discord
from discord import app_commands
from discord.ui import Select, View, Button, Modal, TextInput
import json
import re
from dotenv import load_dotenv
import os

def configure():
    load_dotenv()

# Utility functions

def human_readable_number(n):
    suffixes = [
        (1e15, "quadrillion"),
        (1e12, "trillion"),
        (1e9, "billion"),
        (1e6, "million"),
        (1e3, "thousand"),
        (1e2, "hundred")
    ]
    for factor, suffix in suffixes:
        if n >= factor:
            return f"{n / factor:.2f} {suffix}"
    return str(int(n))

def load_items_by_category():
    with open("values.json", "r", encoding="utf-8") as f:
        items = json.load(f)

    gear_options = []
    pet_options = []

    for item, info in items.items():
        emoji = info.get("emoji", "")
        min_val = info.get("min", 0)
        max_val = info.get("max", 0)
        avg_val = (min_val + max_val) / 2
        formatted_avg = human_readable_number(avg_val)
        option = discord.SelectOption(
            label=f"{item.title()} {emoji}",
            value=item,
            description=f"~ {formatted_avg} sheckles"
        )
        if info.get("category") == "gear":
            gear_options.append(option)
        elif info.get("category") == "pet":
            pet_options.append(option)

    return items, gear_options, pet_options

# Trade data
user_trades = {}
last_dropdown_message = {}

# Select Menus

class GearSelect(Select):
    def __init__(self, side: str):
        _, gear_options, _ = load_items_by_category()
        super().__init__(placeholder="Select a gear item", min_values=1, max_values=1, options=gear_options)
        self.side = side

    async def callback(self, interaction: discord.Interaction):
        item = self.values[0]
        user_id = interaction.user.id
        user_trades.setdefault(user_id, {"your_trade": [], "their_trade": []})
        user_trades[user_id][self.side].append({"item": item, "amount": None})
        summary = format_trade_summary(user_trades[user_id])
        await interaction.response.edit_message(
            content=f"Select an item to add to **{self.side.replace('_', ' ').title()}**:\n\n{summary}",
            view=None
        )

class PetSelect(Select):
    def __init__(self, side: str):
        _, _, pet_options = load_items_by_category()
        super().__init__(placeholder="Select a pet item", min_values=1, max_values=1, options=pet_options)
        self.side = side

    async def callback(self, interaction: discord.Interaction):
        item = self.values[0]
        user_id = interaction.user.id
        user_trades.setdefault(user_id, {"your_trade": [], "their_trade": []})
        user_trades[user_id][self.side].append({"item": item, "amount": None})
        summary = format_trade_summary(user_trades[user_id])
        await interaction.response.edit_message(
            content=f"Select an item to add to **{self.side.replace('_', ' ').title()}**:\n\n{summary}",
            view=None
        )

# View to hold the selectors

class MultiItemSelectView(View):
    def __init__(self, side: str):
        super().__init__(timeout=60)
        self.side = side
        self.add_item(GearSelect(side))
        self.add_item(PetSelect(side))

    @discord.ui.button(label="Add Sheckles", style=discord.ButtonStyle.secondary, custom_id="sheckles_button")
    async def sheckles_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ShecklesModal(self.side))

# Formatting and parsing helpers

def parse_value(value_str: str) -> float:
    value_str = value_str.lower().replace("sheckles", "").strip()
    number_words = {
        "hundred": 1e2,
        "thousand": 1e3,
        "million": 1e6,
        "billion": 1e9,
        "trillion": 1e12,
        "quadrillion": 1e15
    }
    for word, multiplier in number_words.items():
        if word in value_str:
            num_str = re.findall(r"[\d.,]+", value_str)
            if not num_str:
                raise ValueError("Invalid input.")
            num = float(num_str[0].replace(",", "").replace(".", ""))
            return num * multiplier
    normalized = re.sub(r"[.,]", "", value_str)
    if not normalized.isdigit():
        raise ValueError("Invalid number format")
    return float(normalized)

def format_trade_summary(trade):
    def format_item(entry):
        item = entry["item"]
        amount = entry["amount"]
        if item == "sheckles":
            return f"{human_readable_number(amount)} sheckles"
        else:
            return item.title()

    def calculate_total(trade_list):
        total = 0
        items, _, _ = load_items_by_category()
        for entry in trade_list:
            item = entry["item"]
            amount = entry["amount"]
            if item == "sheckles":
                total += amount
            else:
                info = items.get(item, {"min": 0, "max": 0})
                avg_val = (info["min"] + info["max"]) / 2
                total += avg_val
        return total

    your = "\n".join([f"- {format_item(i)}" for i in trade["your_trade"]]) or "*No items yet*"
    their = "\n".join([f"- {format_item(i)}" for i in trade["their_trade"]]) or "*No items yet*"

    your_total = calculate_total(trade["your_trade"])
    their_total = calculate_total(trade["their_trade"])

    your_value = f"💰 Total: {human_readable_number(your_total)} sheckles"
    their_value = f"💰 Total: {human_readable_number(their_total)} sheckles"

    return f"**Your Trade:**\n{your}\n{your_value}\n\n**Their Trade:**\n{their}\n{their_value}"


# Modal for entering sheckles

class ShecklesModal(Modal):
    def __init__(self, side):
        super().__init__(title=f"Enter Sheckles amount for {side.replace('_', ' ').title()}")
        self.side = side
        self.amount_input = TextInput(
            label="Sheckles amount (e.g. 3 trillion)",
            style=discord.TextStyle.short,
            placeholder="3 trillion",
            required=True
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        try:
            amount = parse_value(self.amount_input.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid sheckles amount format. Try `3 trillion`, `500000000`, `50.000.000` etc.",
                ephemeral=True
            )
            return

        user_trades.setdefault(user_id, {"your_trade": [], "their_trade": []})
        user_trades[user_id][self.side].append({"item": "sheckles", "amount": amount})
        summary = format_trade_summary(user_trades[user_id])

        await interaction.response.edit_message(
            content=f"Select an item to add to **{self.side.replace('_', ' ').title()}**:\n\n{summary}",
            view=None
        )

# Buttons View

class AddItemView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item_your_trade = Button(label="Add Item to Your Trade", style=discord.ButtonStyle.primary)
        self.add_item_your_trade.callback = self.add_your_callback
        self.add_item_their_trade = Button(label="Add Item to Their Trade", style=discord.ButtonStyle.primary)
        self.add_item_their_trade.callback = self.add_their_callback
        self.evaluate_trade = Button(label="Evaluate Trade", style=discord.ButtonStyle.success)
        self.evaluate_trade.callback = self.evaluate_callback

        self.add_item(self.add_item_your_trade)
        self.add_item(self.add_item_their_trade)
        self.add_item(self.evaluate_trade)

    async def add_your_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        trade = user_trades.get(user_id, {"your_trade": [], "their_trade": []})
        summary = format_trade_summary(trade)

        if user_id in last_dropdown_message:
            try:
                msg = await interaction.channel.fetch_message(last_dropdown_message[user_id])
                await msg.delete()
            except discord.NotFound:
                pass

        msg = await interaction.channel.send(
            f"Select an item to add to **Your Trade**:\n\n{summary}",
            view=MultiItemSelectView("your_trade")
        )
        last_dropdown_message[user_id] = msg.id
        await interaction.response.defer()

    async def add_their_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        trade = user_trades.get(user_id, {"your_trade": [], "their_trade": []})
        summary = format_trade_summary(trade)

        if user_id in last_dropdown_message:
            try:
                msg = await interaction.channel.fetch_message(last_dropdown_message[user_id])
                await msg.delete()
            except discord.NotFound:
                pass

        msg = await interaction.channel.send(
            f"Select an item to add to **Their Trade**:\n\n{summary}",
            view=MultiItemSelectView("their_trade")
        )
        last_dropdown_message[user_id] = msg.id
        await interaction.response.defer()

    async def evaluate_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        trade = user_trades.get(user_id)
        if not trade:
            await interaction.response.send_message("You haven't added any items yet!", ephemeral=True)
            return

        result = evaluate_trade(trade["your_trade"], trade["their_trade"])
        await interaction.response.send_message(result, ephemeral=True)
        user_trades.pop(user_id, None)

# Evaluation logic

def evaluate_trade(your_trade, their_trade) -> str:
    def total_value(trade_list):
        total_min, total_max = 0, 0
        for entry in trade_list:
            item = entry["item"]
            amount = entry["amount"]
            if item == "sheckles":
                total_min += amount
                total_max += amount
            else:
                items, _, _ = load_items_by_category()
                base = items.get(item, {"min": 0, "max": 0})
                base_min = base["min"]
                base_max = base["max"]
                total_min += base_min
                total_max += base_max
        return total_min, total_max

    your_min, your_max = total_value(your_trade)
    their_min, their_max = total_value(their_trade)
    your_mid = (your_min + your_max) / 2
    their_mid = (their_min + their_max) / 2
    diff = abs(your_mid - their_mid)
    avg = (your_mid + their_mid) / 2

    if diff <= 0.1 * avg:
        return f"✅ The trade looks balanced!\nYour trade value: {human_readable_number(your_mid)} sheckles\nTheir trade value: {human_readable_number(their_mid)} sheckles"
    else:
        if your_mid > their_mid:
            return f"❌ Your side is more valuable.\nYour trade value: {human_readable_number(your_mid)} sheckles\nTheir trade value: {human_readable_number(their_mid)} sheckles"
        else:
            return f"❌ Their side is more valuable.\nYour trade value: {human_readable_number(your_mid)} sheckles\nTheir trade value: {human_readable_number(their_mid)} sheckles"

# Bot setup

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        @self.tree.command(name="trade", description="Start a Grow a Garden trade evaluation")
        async def trade_command(interaction: discord.Interaction):
            user_id = interaction.user.id
            user_trades[user_id] = {"your_trade": [], "their_trade": []}

            view = AddItemView()
            await interaction.response.send_message(
                "Start building your trade. Use the buttons below to add items to each side, then evaluate.",
                view=view,
                ephemeral=True
            )

        await self.tree.sync()

configure()
bot = MyBot()
bot.run(os.getenv('api_key'))  # Replace with your real bot token
