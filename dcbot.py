import discord
from discord.ext import commands
import json
from config import TOKEN

# Assuming users.json is in the current directory or adjust the path accordingly
with open('users.json', 'r') as file:
    users = json.load(file)

intents = discord.Intents.all()
# Required for member intents to access guild member properties like roles
intents.members = True  
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.slash_command(name="authenticate", description="Authenticate a user")
async def authenticate(ctx):
    # Ensure command is used in a guild
    if not ctx.guild:
        await ctx.respond("This command cannot be used in direct messages.", ephemeral=True)
        return
    
    # Check if the user already has the "Verified User" role
    verified_role = discord.utils.get(ctx.guild.roles, name="Verified User")
    if verified_role in ctx.author.roles:
        await ctx.respond("You are already verified.", ephemeral=True)
        return

    # Since we cannot safely ask for password in a public or private channel, we instruct the user
    await ctx.respond("Please check your DM for authentication steps.", ephemeral=True)
    
    def check(m):
        return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)
    
    # Open DM and prompt for username
    await ctx.author.send("You're initiating the verification process. Please enter your username:")
    username_msg = await bot.wait_for('message', check=check)
    username = username_msg.content

    # Prompt for password in DM
    await ctx.author.send("Please enter your password:")
    password_msg = await bot.wait_for('message', check=check)
    password = password_msg.content

    # Verify credentials
    user_info = users.get(username, {})
    if user_info.get("password") == password:
        await ctx.author.send('Authentication successful.')
        if verified_role:
            await ctx.author.add_roles(verified_role)
            await ctx.author.send('You have been given the "Verified User" role.')
    else:
        await ctx.author.send('Authentication failed. Incorrect username or password.')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

bot.run(TOKEN)
