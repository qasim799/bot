import discord
from discord.ext import commands
import io
import contextlib
import pickle
import textwrap
import subprocess
import json
import asyncio
import os
import re
import requests
import aiohttp
import threading
from groq import AsyncGroq

RAPIDAPI_KEY = "20f8b0e060mshba26fe0a89931b1p1f5d14jsn387bbba3f769"
RAPIDAPI_HOST = "midjourney-imaginecraft-generative-ai-api.p.rapidapi.com"
GROQ_API_KEY = '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'
GET_RESULT_ENDPOINT = "https://midjourney-imaginecraft-generative-ai-api.p.rapidapi.com/midjourney/getresult"
IMAGINE_PARAMETER_ENDPOINT = "https://midjourney-imaginecraft-generative-ai-api.p.rapidapi.com/midjourney/imagineparameter"
TOKEN = 'MTI0MTUyNjQ1MjQzNjg2NTA4NQ.Gdqw-Z.DAqjH1IvxvN_05OaZEEW76CL3SWWQBDLJz9MXc'
BOT_USER_ID = '1241526452436865085'
CONVERSATION_HISTORY_FILE = "conversation_history.pkl"

# Initialize the Groq client
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

# Define intents
intents = discord.Intents.all()
intents.message_content = True
intents.members = True
intents.typing = True
intents.presences = True

# Initialize bot to use '!' and mentions as command prefixes
bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'), intents=intents)

# Event to print a greeting message when the bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    print('Alisa is ready to greet!')

# Event to send a greeting message when the bot joins a server
@bot.event
async def on_guild_join(guild):
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            await channel.send("Hi, I'm Alisa Bosconovitch BOT made by qasim799, "
                               "I can run the python code provided to me in a message "
                               "to manage servers like a well-oiled Machine.!")
            break

# Event to handle messages
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('!') or f'<@{bot.user.id}>' in message.content:
        ctx = await bot.get_context(message)
        if ctx.command is None:
            commands_list = [f'`{command}`' for command in bot.commands]
            await message.reply("Here are my available commands:\n" + "\n".join(commands_list))
        else:
            await bot.process_commands(message)
    else:
        await bot.process_commands(message)

# Error handler for unknown commands and missing arguments
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        commands_list = [f'`{command}`' for command in bot.commands]
        await ctx.message.reply(f"Invalid command! Please use one of the following commands:\n" + "\n".join(commands_list))
    elif isinstance(error, commands.MissingRequiredArgument):
        if ctx.command.name == "AI":
            await ctx.message.reply("To use the AI command, type `!AI your question here` or `@alisa AI your question here, You Noob XD`.")
        else:
            await ctx.message.reply(f"Missing argument: {error.param.name}")
    else:
        raise error

# Function to save conversation history to a file
async def save_conversation_history():
    with open(CONVERSATION_HISTORY_FILE, "wb") as file:
        pickle.dump(conversation_history, file)

# Function to load conversation history from a file
def load_conversation_history():
    try:
        with open(CONVERSATION_HISTORY_FILE, "rb") as file:
            return pickle.load(file)
    except FileNotFoundError:
        return {}

# Load conversation history when the bot starts up
conversation_history = load_conversation_history()

# Helper function to split the message into chunks of 2000 characters or less
def split_message(message, max_length=2000):
    return [message[i:i + max_length] for i in range(0, len(message), max_length)]

# Function to truncate conversation history
def truncate_history(history, max_length=8192):
    total_length = 0
    truncated_history = []
    for message in reversed(history):
        message_length = len(message['content'])
        if total_length + message_length > max_length:
            break
        truncated_history.insert(0, message)
        total_length += message_length
    return truncated_history

# Command to interact with AI assistant
@bot.command(name="AI", help="Ask AI a question. Usage: !AI [your question]")
async def AI(ctx, *, query: str = None):
    if query is None:
        await ctx.reply(f"{ctx.message.author.mention}, for asking AI, type !AI [your question here].")
        return

    try:
        # Get or initialize conversation history for the user
        user_id = str(ctx.author.id)
        history = conversation_history.get(user_id, [])

        # Append the user's query to the conversation history
        history.append({"role": "user", "content": query})

        # Truncate the conversation history to fit within the context length limit
        truncated_history = truncate_history(history)

        # Asynchronously call the Groq API with conversation history
        chat_completion = await groq_client.chat.completions.create(
            messages=truncated_history,
            model="llama3-70b-8192"
        )
        response = chat_completion.choices[0].message.content

        # Update conversation history with AI's response
        history.append({"role": "assistant", "content": response})
        conversation_history[user_id] = history

        # Save conversation history to file asynchronously
        await save_conversation_history()

        # Split response if it's too long for a single Discord message
        response_chunks = split_message(response)

        for chunk in response_chunks:
            await ctx.send(f"{ctx.message.author.mention}, {chunk}")
    except Exception as e:
        if 'context_length_exceeded' in str(e):
            await ctx.reply(f"{ctx.message.author.mention}, your query is too long. Please ask to make it concise or short in your querry.")
        elif 'Invalid Form Body' in str(e):
            await ctx.reply(f"{ctx.message.author.mention}, the response is too long to be sent in one message due to limitations by discord. Please ask to make it concise or short in your querry.")
        else:
            await ctx.reply(f"{ctx.message.author.mention}, an error occurred contact qasim: {e}")

# Define patterns for imagePromptUrl
patterns = {
    "imagePromptUrl": r"(?:image\s+url|image\s+reference|url)\s*=\s*(https?://[^\s]+)"
}

def extract_parameters(message):
    params = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            params[key] = value
            print(f"Pattern '{key}' found value: {params[key]}")
            # Remove the found URL from the message
            message = message.replace(match.group(0), "").strip()
    return params, message

@bot.command(name="img")
async def generate_image(ctx, *, prompt: str):
    try:
        # Extract imagePromptUrl from the prompt
        params, cleaned_prompt = extract_parameters(prompt)

        # Always include textPrompt from the cleaned message
        params["textPrompt"] = cleaned_prompt
        
        print(f"Final params: {params}")

        async with aiohttp.ClientSession() as session:
            headers = {
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": RAPIDAPI_HOST,
                "Content-Type": "application/json"
            }

            async with session.post(IMAGINE_PARAMETER_ENDPOINT, json=params, headers=headers) as response:
                imagine_data = await response.json()
                
                if response.status != 200 or not imagine_data.get("taskId"):
                    await ctx.reply(f"Failed to initiate image generation. Status: {response.status}, Error: {imagine_data.get('error', 'Unknown error')}")
                    return

                task_id = imagine_data["taskId"]
                await ctx.reply(f"Image generation initiated. Task ID: {task_id}")

                # Poll for the result every 15 seconds
                result_payload = {
                    "taskId": task_id
                }

                while True:
                    await asyncio.sleep(15)
                    async with session.post(GET_RESULT_ENDPOINT, json=result_payload, headers=headers) as result_response:
                        result_data = await result_response.json()
                        
                        if result_response.status != 200:
                            await ctx.reply(f"Error fetching image result. Status: {result_response.status}, Error: {result_data.get('error', 'Unknown error')}")
                            break

                        if result_data.get("photoUrl"):
                            await ctx.reply(result_data["photoUrl"])
                            print("Get Result Response Status:", result_response.status)
                            print("Get Result Response Content:", result_data)
                            break
                        elif result_data.get("error"):
                            await ctx.reply(f"Failed to generate image: {result_data['error']}")
                            break
                        else:
                            # Check for percentage completion and print to the terminal
                            percentage = result_data.get("percentage", "unknown")
                            print(f"Image generation {percentage}% complete.")

    except Exception as e:
        await ctx.reply(f"An error occurred: {e}")

# Command to ignorehafiz
@bot.command(name="tamatargosht")
async def ignorehafiz(ctx):
    ignorehafiz_message = "Ignore Hafiz!"
    await ctx.message.reply(ignorehafiz_message)

# Command to notgay
@bot.command(name="notgay")
async def notgay(ctx):
    notgay_message = "He is not gay he has big dick and fuck me everyday!"
    await ctx.message.reply(notgay_message)

# Command to thanks
@bot.command(name="thanks")
async def thanks(ctx):
    thnx_message = "My Lovely sweet daddy Qasim says Welcome to you!"
    await ctx.message.reply(thnx_message)

# Command to introduce the bot
@bot.command(name="alisabot")
async def alisabot(ctx):
    intro_message = "Hi, I'm Alisa Bosconovitch BOT made by qasim799, " \
                    "I can run the python code provided to me in a message " \
                    "to manage servers like a well-oiled Machine.!"
    await ctx.message.reply(intro_message)

# Command to get detailed information about a user in the server
@bot.command()
async def user_info(ctx, username: str):
    # Attempt to find the member object corresponding to the provided username
    member = discord.utils.find(lambda m: m.name == username, ctx.guild.members)
    if member:
        roles = [role.mention for role in member.roles if role != ctx.guild.default_role]  # Get all roles except @everyone
        embed = discord.Embed(title="User Information", description=f"Information about {member.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Name", value=member.name, inline=True)
        embed.add_field(name="Discriminator", value=member.discriminator, inline=True)
        embed.add_field(name="Bot", value=member.bot, inline=True)
        embed.add_field(name="Created at", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="Joined at", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="Roles", value=", ".join(roles) if roles else "None", inline=False)

        await ctx.message.reply(embed=embed)
    else:
        await ctx.message.reply("User not found in this server.")

# Command to evaluate and execute Python code
@bot.command(name="eval")
async def evaluate(ctx, *, code):
    print("Received eval command with code:", repr(code))  # Debugging: Print the received code

    # Remove code block formatting if present
    if code.startswith("```") and code.endswith("```"):
        code = code[3:-3]
    code = code.strip('` ')

    # Dedent the code to remove any leading whitespace
    code = textwrap.dedent(code)

    # Print the cleaned code for debugging
    print(f'Cleaned code:\n{repr(code)}')

    local_variables = {
        'discord': discord,
        'commands': commands,
        'bot': bot,
        'ctx': ctx
    }
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        try:
            exec(
                f"async def func():\n{textwrap.indent(code, '    ')}",
                local_variables
            )
            await local_variables['func']()
        except Exception as e:
            await ctx.message.reply(f'Error executing code: {e}')
            print(f'Error executing code: {e}')  # Debugging: Print the exception

    result = stdout.getvalue()
    print("Result of code execution:", repr(result))  # Debugging: Print the result of code execution
    await ctx.message.reply(f'```{result}```')

# Run the bot
bot.run(TOKEN)
