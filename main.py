import discord
from discord import app_commands
from discord.ext import tasks, commands
import configparser
from discord.ui import Modal, TextInput, Select, View
import random
import string
import time
import re
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
import pytz

config = configparser.ConfigParser()
with open('config.ini', 'r', encoding='utf-8') as f:
    config.read_file(f)


slots_data_file = 'slots_data.json'
ping_data_file = 'ping.json'
keys_file = 'keys_data.json'

bot_token = config['Bot']['Token']
bot_status = config['Bot']['Status']
bot_role_id = int(config['Bot']['RoleID'])
server_id = int(config['Bot']['ServerID'])
seller_channelID = int(config['Bot']['seller_channelID'])

log_channel_id = int(config['Logging']['LogChannelID'])

embed_color = int(config['Embed']['Color'], 16)  
embed_footer = config['Embed']['Footer']
embed_thumbnail_url = config['Embed']['ThumbnailURL']

category1_id = int(config['Categories']['Category1ID'])
category2_id = int(config['Categories']['Category2ID'])

premium_role_id = int(config['Roles']['PremiumRoleID'])
memberroleid = int(config['Roles']['MemberRoleId'])

TIMEZONE = config['Reset']['Timezone']
RESET_HOUR = int(config['Reset']['Hour'])
RESET_MINUTE = int(config['Reset']['Minute'])


intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name=bot_status))
    await bot.tree.sync()  # Sync commands with Discord
    ping_reset.start()
    print(f'Logged in as {bot.user.name}')



def load_json_data(file_path):
    if not os.path.exists(file_path):
        return {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json_data(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)




@bot.tree.command(name="create_slot", description="Create a slot with advanced options.")
@app_commands.describe(
    user_mention="The user to mention",
    category_number="Category number (1 or 2)",
    duration="Duration (e.g., 1d, 1w, 1m, or 'lifetime')",
    here_ping="Number of @here pings allowed (0, 1, 2, etc.)",
    everyone_ping="Number of @everyone pings allowed (0, 1, 2, etc.)"
)
async def create_slot(interaction: discord.Interaction, user_mention: discord.Member, category_number: int, duration: str, here_ping: int, everyone_ping: int):
    await interaction.response.defer()

    role = discord.utils.get(interaction.guild.roles, id=bot_role_id)
    if role not in interaction.user.roles:
        await interaction.followup.send("You do not have the required role to use this command.", ephemeral=True)
        return

    try:
        slot_data = load_json_data(slots_data_file)
        
        if slot_data:  
            for slot in slot_data.values():
                if slot["user_id"] == user_mention.id:
                    await interaction.followup.send(f"{user_mention.mention} already has an existing slot. A new slot cannot be created.", ephemeral=True)
                    return

        if category_number == 1:
            category_id = category1_id
            temp_thing = "Category1"
        elif category_number == 2:
            category_id = category2_id
            temp_thing = "Category2"
        else:
            await interaction.followup.send("Invalid category number. Choose 1 or 2.", ephemeral=True)
            return
        
        category = discord.utils.get(interaction.guild.categories, id=category_id)
        if not category:
            await interaction.followup.send("Category not found.", ephemeral=True)
            return
        
        if duration == 'lifetime':
            end_time = None
        elif duration.endswith('d'):
            duration_days = int(duration[:-1])
            end_time = datetime.now() + timedelta(days=duration_days)
        elif duration.endswith('w'):
            duration_days = int(duration[:-1]) * 7
            end_time = datetime.now() + timedelta(days=duration_days)
        elif duration.endswith('m'):
            duration_days = int(duration[:-1]) * 30
            end_time = datetime.now() + timedelta(days=duration_days)
        else:
            duration_days = int(duration)
            end_time = datetime.now() + timedelta(days=duration_days)
        
        creation_time = datetime.now()
        
        end_timestamp = int(end_time.timestamp()) if end_time else None
        creation_timestamp = int(creation_time.timestamp())

        memberrole = discord.utils.get(interaction.guild.roles, id=memberroleid)
        
        channel_name = f"・🌟┇{user_mention.name}" if end_time else f"・🌟┇{user_mention.name}"
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),  # Default role can view but not send messages
            memberrole: discord.PermissionOverwrite(read_messages=True, send_messages=False),  
            
            user_mention: discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True),  # Mentioned user can ping everyone
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        
        channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)
        
        premium_role = discord.utils.get(interaction.guild.roles, id=premium_role_id)
        if premium_role:
            await user_mention.add_roles(premium_role)
        
        slot_data[channel.id] = {
            "channel_id": channel.id,
            "user_id": user_mention.id,
            "category_id": temp_thing,
            "duration_days": duration_days if end_time else 'lifetime',
            "end_timestamp": end_timestamp,
            "creation_timestamp": creation_timestamp,
            "here_ping": here_ping,
            "status": "active",
            "everyone_ping": everyone_ping,
            "moderator_id": interaction.user.id,
            "moderator_name": interaction.user.name
        }
        save_json_data(slots_data_file, slot_data)
        
        ping_data = load_json_data(ping_data_file)
        ping_data[user_mention.id] = {
            "allowed_here_ping": here_ping,
            "allowed_everyone_ping": everyone_ping,
            "used_here_ping": 0,
            "used_everyone_ping": 0
        }
        save_json_data(ping_data_file, ping_data)
        
        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            log_embed = discord.Embed(title="Slot Created", color=embed_color)
            log_embed.add_field(name="Channel", value=channel.mention, inline=False)
            log_embed.add_field(name="User", value=user_mention.mention, inline=False)
            log_embed.add_field(name="Duration", value=f"{duration_days} days" if end_time else "Lifetime", inline=False)
            log_embed.add_field(name="Category", value=category.name, inline=False)
            log_embed.add_field(name="@here Pings Allowed", value=str(here_ping), inline=False)
            log_embed.add_field(name="@everyone Pings Allowed", value=str(everyone_ping), inline=False)
            log_embed.add_field(name="Creation Date", value=f"<t:{creation_timestamp}:R>", inline=False)
            log_embed.add_field(name="Expiry Date", value=f"<t:{end_timestamp}:R>" if end_time else "Lifetime", inline=False)
            log_embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            log_embed.set_footer(text=embed_footer)
            log_embed.set_thumbnail(url=embed_thumbnail_url)
            
            await log_channel.send(embed=log_embed)
        
        user_embed = discord.Embed(title="Your Slot Has Been Created!", color=embed_color)
        user_embed.add_field(name="Channel", value=channel.mention, inline=False)
        user_embed.add_field(name="Duration", value=f"{duration_days} days" if end_time else "Lifetime", inline=False)
        user_embed.add_field(name="Category", value=category.name, inline=False)
        user_embed.add_field(name="@here Pings Allowed", value=str(here_ping), inline=False)
        user_embed.add_field(name="@everyone Pings Allowed", value=str(everyone_ping), inline=False)
        user_embed.add_field(name="Creation Date", value=f"<t:{creation_timestamp}:R>", inline=False)
        user_embed.add_field(name="Expiry Date", value=f"<t:{end_timestamp}:R>" if end_time else "Lifetime", inline=False)
        user_embed.set_footer(text=embed_footer)
        user_embed.set_thumbnail(url=embed_thumbnail_url)
        
        await user_mention.send(embed=user_embed)
        ThumbnailURL2 = user_mention.avatar.url if user_mention.avatar else embed_thumbnail_url
        channel_embed = discord.Embed(title="Slot Information", color=embed_color)
        channel_embed.add_field(name="User", value=user_mention.mention, inline=False)
        channel_embed.add_field(name="Duration", value=f"{duration_days} days" if end_time else "Lifetime", inline=False)
        channel_embed.add_field(name="Category", value=category.name, inline=False)
        channel_embed.add_field(name="Creation Date", value=f"<t:{creation_timestamp}:R>", inline=True)
        channel_embed.add_field(name="Expiry Date", value=f"<t:{end_timestamp}:R>" if end_time else "Lifetime", inline=True)
        channel_embed.add_field(name="Ping Allowed", value=f"```@everyone : {str(everyone_ping)}\n@here : {str(here_ping)}```", inline=False)
        channel_embed.set_footer(text=embed_footer)
        channel_embed.set_thumbnail(url=ThumbnailURL2)
        
        await channel.send(embed=channel_embed)
        
        await interaction.followup.send("Slot created successfully!", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in create_slot command: {e}")







@bot.tree.command(name="hold", description="Put a slot on hold with a reason.")
@app_commands.describe(
    user_mention="The user to mention",
    reason="Reason for putting the slot on hold"
)
async def hold(interaction: discord.Interaction, user_mention: discord.Member, reason: str):
    await interaction.response.defer()

    role = discord.utils.get(interaction.guild.roles, id=bot_role_id)
    if role not in interaction.user.roles:
        await interaction.followup.send("You do not have the required role to use this command.", ephemeral=True)
        return

    try:
        slot_data = load_json_data(slots_data_file)
        
        slot = next((slot for slot in slot_data.values() if slot["user_id"] == user_mention.id), None)
        if not slot:
            await interaction.followup.send(f"No slot found for {user_mention.mention}.", ephemeral=True)
            return
        
        if slot["status"] == "on hold":
            await interaction.followup.send(f"{user_mention.mention}'s slot is already on hold.", ephemeral=True)
            return

        channel = bot.get_channel(slot["channel_id"])
        if not channel:
            await interaction.followup.send("Slot channel not found.", ephemeral=True)
            return

        slot["status"] = "on hold"
        save_json_data(slots_data_file, slot_data)


        await channel.set_permissions(user_mention, send_messages=False)
        
        premium_role = discord.utils.get(interaction.guild.roles, id=premium_role_id)
        if premium_role:
            await user_mention.remove_roles(premium_role)


        user_dm_embed = discord.Embed(title="Your Slot is on Hold", color=embed_color)
        user_dm_embed.add_field(name="Reason", value=reason, inline=False)
        user_dm_embed.add_field(name="Channel", value=channel.mention, inline=False)
        user_dm_embed.add_field(name="Executed By", value=interaction.user.mention, inline=False)
        user_dm_embed.set_footer(text="This action is reversible. Contact admin for more information.")
        user_dm_embed.set_thumbnail(url=embed_thumbnail_url)
        
        await user_mention.send(embed=user_dm_embed)

        slot_channel_embed = discord.Embed(title="Slot On Hold", color=embed_color)
        slot_channel_embed.add_field(name="User", value=user_mention.mention, inline=False)
        slot_channel_embed.add_field(name="Reason", value=reason, inline=False)
        slot_channel_embed.add_field(name="Executed By", value=interaction.user.mention, inline=False)
        slot_channel_embed.set_footer(text="This action is reversible. Contact admin for more information.")
        slot_channel_embed.set_thumbnail(url=embed_thumbnail_url)

        await channel.send(embed=slot_channel_embed)

        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            log_embed = discord.Embed(title="Slot On Hold", color=embed_color)
            log_embed.add_field(name="User", value=user_mention.mention, inline=False)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.add_field(name="Channel", value=channel.mention, inline=False)
            log_embed.add_field(name="Executed By", value=interaction.user.mention, inline=False)
            log_embed.set_footer(text=embed_footer)
            log_embed.set_thumbnail(url=embed_thumbnail_url)

            await log_channel.send(embed=log_embed)
        
        await interaction.followup.send(f"{user_mention.mention}'s slot has been put on hold.", ephemeral=True)
    

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)


@bot.tree.command(name="unhold", description="Remove the hold from a slot.")
@app_commands.describe(
    user_mention="The user to mention"
)
async def unhold(interaction: discord.Interaction, user_mention: discord.Member):
    await interaction.response.defer()

    role = discord.utils.get(interaction.guild.roles, id=bot_role_id)
    if role not in interaction.user.roles:
        await interaction.followup.send("You do not have the required role to use this command.", ephemeral=True)
        return

    try:
        slot_data = load_json_data(slots_data_file)
        
        slot = next((slot for slot in slot_data.values() if slot["user_id"] == user_mention.id), None)
        if not slot:
            await interaction.followup.send(f"No slot found for {user_mention.mention}.", ephemeral=True)
            return
        
        
        if slot["status"] == "active":
            await interaction.followup.send(f"{user_mention.mention}'s slot is already active.", ephemeral=True)
            return

        channel = bot.get_channel(slot["channel_id"])
        if not channel:
            await interaction.followup.send("Slot channel not found.", ephemeral=True)
            return

        slot["status"] = "active"
        save_json_data(slots_data_file, slot_data)

        premium_role = discord.utils.get(interaction.guild.roles, id=premium_role_id)
        if premium_role:
            await user_mention.add_roles(premium_role)


        await channel.set_permissions(user_mention, read_messages=True, send_messages=True, mention_everyone=True)
        
        user_dm_embed = discord.Embed(title="Your Slot is No Longer On Hold", color=embed_color)
        user_dm_embed.add_field(name="Channel", value=channel.mention, inline=False)
        user_dm_embed.add_field(name="Executed By", value=interaction.user.mention, inline=False)
        user_dm_embed.set_footer(text=embed_footer)
        user_dm_embed.set_thumbnail(url=embed_thumbnail_url)
        
        await user_mention.send(embed=user_dm_embed)

        slot_channel_embed = discord.Embed(title="Slot Released", color=embed_color)
        slot_channel_embed.add_field(name="User", value=user_mention.mention, inline=False)
        slot_channel_embed.add_field(name="Executed By", value=interaction.user.mention, inline=False)
        slot_channel_embed.set_footer(text=embed_footer)
        slot_channel_embed.set_thumbnail(url=embed_thumbnail_url)

        await channel.send(embed=slot_channel_embed)

        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            log_embed = discord.Embed(title="Slot Released", color=embed_color)
            log_embed.add_field(name="User", value=user_mention.mention, inline=False)
            log_embed.add_field(name="Channel", value=channel.mention, inline=False)
            log_embed.add_field(name="Executed By", value=interaction.user.mention, inline=False)
            log_embed.set_footer(text=embed_footer)
            log_embed.set_thumbnail(url=embed_thumbnail_url)

            await log_channel.send(embed=log_embed)
        
        await interaction.followup.send(f"{user_mention.mention}'s slot has been released from hold.", ephemeral=True)
    

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)



@bot.tree.command(name="revoke", description="Revoke a slot with a reason.")
@app_commands.describe(
    user_mention="The user to mention",
    reason="Reason for revoking the slot"
)
async def revoke(interaction: discord.Interaction, user_mention: discord.Member, reason: str):
    await interaction.response.defer()

    role = discord.utils.get(interaction.guild.roles, id=bot_role_id)
    if role not in interaction.user.roles:
        await interaction.followup.send("You do not have the required role to use this command.", ephemeral=True)
        return

    try:
        slot_data = load_json_data(slots_data_file)
        
        slot = next((slot for slot in slot_data.values() if slot["user_id"] == user_mention.id), None)
        if not slot:
            await interaction.followup.send(f"No slot found for {user_mention.mention}.", ephemeral=True)
            return

        if slot["status"] == "revoked":
            await interaction.followup.send(f"{user_mention.mention}'s slot has already been revoked.", ephemeral=True)
            return

        channel = bot.get_channel(slot["channel_id"])
        if not channel:
            await interaction.followup.send("Slot channel not found.", ephemeral=True)
            return

        slot["status"] = "revoked"
        save_json_data(slots_data_file, slot_data)

        await channel.set_permissions(user_mention, send_messages=False)

        premium_role = discord.utils.get(interaction.guild.roles, id=premium_role_id)
        if premium_role:
            await user_mention.remove_roles(premium_role)
        
        user_dm_embed = discord.Embed(title="Your Slot Has Been Revoked", color=embed_color)
        user_dm_embed.add_field(name="Reason", value=reason, inline=False)
        user_dm_embed.add_field(name="Channel", value=channel.mention, inline=False)
        user_dm_embed.add_field(name="Executed By", value=interaction.user.mention, inline=False)
        user_dm_embed.set_footer(text="This action is irreversible.")
        user_dm_embed.set_thumbnail(url=embed_thumbnail_url)
        user_dm_embed.timestamp = discord.utils.utcnow()
        
        await user_mention.send(embed=user_dm_embed)

        slot_channel_embed = discord.Embed(title="Slot Revoked", color=embed_color)
        slot_channel_embed.add_field(name="User", value=user_mention.mention, inline=False)
        slot_channel_embed.add_field(name="Reason", value=reason, inline=False)
        slot_channel_embed.add_field(name="Executed By", value=interaction.user.mention, inline=False)
        slot_channel_embed.set_footer(text="This action is irreversible.")
        slot_channel_embed.set_thumbnail(url=embed_thumbnail_url)
        slot_channel_embed.timestamp = discord.utils.utcnow()

        await channel.send(embed=slot_channel_embed)

        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            log_embed = discord.Embed(title="Slot Revoked", color=embed_color)
            log_embed.add_field(name="User", value=user_mention.mention, inline=False)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.add_field(name="Channel", value=channel.mention, inline=False)
            log_embed.add_field(name="Executed By", value=interaction.user.mention, inline=False)
            log_embed.set_footer(text="This action is irreversible.")
            log_embed.set_thumbnail(url=embed_thumbnail_url)
            log_embed.timestamp = discord.utils.utcnow()

            await log_channel.send(embed=log_embed)
        
        await interaction.followup.send(f"{user_mention.mention}'s slot has been revoked.", ephemeral=True)
    
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)


@bot.tree.command(name="nuke", description="Nuke a slot channel and recreate it.")
async def nuke(interaction: discord.Interaction):
    await interaction.response.defer()
    user_mention = interaction.user
    
    
    #role = discord.utils.get(interaction.guild.roles, id=bot_role_id)
    #if role not in interaction.user.roles:
    #    await interaction.followup.send("You do not have the required role to use this command.", ephemeral=True)
    #    return

    try:
        slot_data = load_json_data(slots_data_file)
        
        slot = next((slot for slot in slot_data.values() if slot["user_id"] == user_mention.id), None)
        if not slot:
            await interaction.followup.send(f"No slot found for the specified user.", ephemeral=True)
            return

        if slot.get("status") != "active":
            await interaction.followup.send(f"The slot is not active. Cannot nuke a slot that is not active.", ephemeral=True)
            return

        last_nuked = datetime.fromtimestamp(slot.get("last_nuked", 0))
        if datetime.now() - last_nuked < timedelta(hours=48):
            await interaction.followup.send(f"The slot cannot be nuked yet. Please wait before nuking again.", ephemeral=True)
            return

        channel = bot.get_channel(slot["channel_id"])
        if channel:
            position = channel.position
            await channel.delete()

            if slot["category_id"] == "Category1":
                categoryid = category1_id
            elif slot["category_id"] == "Category2":
                categoryid = category2_id
            else:
                await interaction.followup.send("Category Id Invalid")

            category = discord.utils.get(interaction.guild.categories, id=categoryid)
            overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),  # Default role can view but not send messages
            user_mention: discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True),  # Mentioned user can ping everyone
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        
            new_channel = await category.create_text_channel(
                name=f"slot-{user_mention}",
                position=position,
                overwrites=overwrites
            )

            slot["channel_id"] = new_channel.id
            slot["last_nuked"] = int(time.time())
            save_json_data(slots_data_file, {str(new_channel.id): slot})

            channel_embed = discord.Embed(title="Slot Information", color=embed_color)
            channel_embed.add_field(name="User", value=user_mention.mention, inline=False)
            channel_embed.add_field(name="Duration", value=f"{slot.get('duration_days', 'Lifetime')} Days", inline=False)
            channel_embed.add_field(name="Category", value=category.name, inline=False)
            channel_embed.add_field(name="Creation Date", value=f"<t:{int(time.time())}:R>", inline=True)
            channel_embed.add_field(name="Expiry Date", value=f"<t:{slot.get('end_timestamp', int(time.time()))}:R>" if slot.get('end_timestamp') else "Lifetime", inline=True)
            channel_embed.add_field(name="Ping Allowed", value=f"```@everyone : {slot.get('everyone_ping', '0')}\n@here : {slot.get('here_ping', '0')}```", inline=False)
            channel_embed.set_footer(text=embed_footer)
            channel_embed.set_thumbnail(url=embed_thumbnail_url)
            await new_channel.send(embed=channel_embed)


            channel_embed = discord.Embed(title="",description="Slot Is Just Nuked By The Owner Of This Slot !!", color=embed_color)
            channel_embed.set_footer(text=embed_footer)
            channel_embed.set_thumbnail(url=embed_thumbnail_url)
            await new_channel.send(embed=channel_embed)

            user_dm_embed = discord.Embed(title="Your Slot Channel Has Been Nuked", color=embed_color)
            user_dm_embed.add_field(name="Channel", value=new_channel.mention, inline=False)
            user_dm_embed.add_field(name="Reason", value="The slot channel was nuked and recreated.", inline=False)
            user_dm_embed.add_field(name="Executed By", value=interaction.user.mention, inline=False)
            user_dm_embed.set_footer(text="If you have any questions, contact admin.")
            user_dm_embed.set_thumbnail(url=embed_thumbnail_url)
            user_dm_embed.timestamp = discord.utils.utcnow()
            await interaction.user.send(embed=user_dm_embed)

            log_channel = bot.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(title="Slot Channel Nuked", color=embed_color)
                log_embed.add_field(name="User", value=user_mention.mention, inline=False)
                log_embed.add_field(name="New Channel", value=new_channel.mention, inline=False)
                log_embed.add_field(name="Reason", value="The slot channel was nuked and recreated.", inline=False)
                log_embed.set_footer(text="Nuke action completed.")
                log_embed.set_thumbnail(url=embed_thumbnail_url)
                log_embed.timestamp = discord.utils.utcnow()
                await log_channel.send(embed=log_embed)
        
        await interaction.followup.send(f"The slot channel has been nuked and recreated.", ephemeral=True)
    
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)








@bot.tree.command(name="transfer", description="Transfer slot ownership from one user to another.")
async def transfer(interaction: discord.Interaction, old_user_id: str, new_user_mention: discord.Member):
    await interaction.response.defer()

    role = discord.utils.get(interaction.guild.roles, id=bot_role_id)
    if role not in interaction.user.roles:
        await interaction.followup.send("You do not have the required role to use this command.", ephemeral=True)
        return

    try:
        slot_data = load_json_data(slots_data_file)

        old_user_id_int = int(old_user_id)
        new_user_id = new_user_mention.id

        old_slot_key = next((key for key, slot in slot_data.items() if slot.get("user_id") == old_user_id_int), None)
        if not old_slot_key:
            await interaction.followup.send("No slot found for the specified old user.", ephemeral=True)
            return

        if any(slot.get("user_id") == new_user_id for slot in slot_data.values()):
            await interaction.followup.send("The new user already has a slot. Please unassign their current slot before transferring.", ephemeral=True)
            return

        slot_data[old_slot_key]["user_id"] = new_user_id

        channel = interaction.guild.get_channel(slot_data[old_slot_key]["channel_id"])
        if channel:
            old_user = interaction.guild.get_member(old_user_id_int)
            if old_user:
                await channel.set_permissions(old_user, send_messages=False)
                old_user_role = discord.utils.get(interaction.guild.roles, id=premium_role_id)
                if old_user_role:
                    await old_user.remove_roles(old_user_role)

            await channel.set_permissions(new_user_mention, read_messages=True, send_messages=True, mention_everyone=True)
            premium_role = discord.utils.get(interaction.guild.roles, id=premium_role_id)
            if premium_role:
                await new_user_mention.add_roles(premium_role)

            slot_embed = discord.Embed(title="Slot Ownership Transferred", color=embed_color)
            slot_embed.add_field(name="Old User", value=f"<@{old_user_id}>", inline=False)
            slot_embed.add_field(name="New User", value=new_user_mention.mention, inline=False)
            slot_embed.add_field(name="Note", value="The slot ownership has been transferred. Contact the new user if you have any pending deals.", inline=False)
            slot_embed.set_footer(text="This action is irreversible.")
            slot_embed.timestamp = datetime.now(timezone.utc)
            await channel.send(embed=slot_embed)

            new_user_embed = discord.Embed(title="Slot Ownership Transferred", color=embed_color)
            new_user_embed.add_field(name="Channel", value=channel.mention, inline=False)
            new_user_embed.add_field(name="Note", value="You have been assigned a new slot. If you have any questions, contact the previous owner or admin.", inline=False)
            new_user_embed.set_footer(text="Welcome to your new slot!")
            new_user_embed.timestamp = datetime.now(timezone.utc)
            await new_user_mention.send(embed=new_user_embed)

            log_channel = bot.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(title="Slot Ownership Transferred", color=embed_color)
                log_embed.add_field(name="Old User", value=f"<@{old_user_id}>", inline=False)
                log_embed.add_field(name="New User", value=new_user_mention.mention, inline=False)
                log_embed.add_field(name="Channel", value=channel.mention, inline=False)
                log_embed.add_field(name="Executed By", value=interaction.user.mention, inline=False)
                log_embed.set_footer(text="Slot transfer log.")
                log_embed.timestamp = datetime.now(timezone.utc)
                await log_channel.send(embed=log_embed)

        ping_data = load_json_data(ping_data_file)
        if str(old_user_id_int) in ping_data:
            ping_data[str(new_user_id)] = ping_data.pop(str(old_user_id_int))

        save_json_data(slots_data_file, slot_data)
        save_json_data(ping_data_file, ping_data)

        await interaction.followup.send("Slot ownership has been successfully transferred.", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)





@bot.tree.command(name="redeem", description="Redeem a key for a slot.")
@app_commands.describe(
    key="The key to redeem"
)
async def redeem(interaction: discord.Interaction, key: str):
    await interaction.response.defer()

    

    try:
        keys_data = load_json_data(keys_file)
        slot_data = load_json_data(slots_data_file)
        
        key_data = keys_data.get(key)
        if not key_data:
            await interaction.followup.send("Invalid key.", ephemeral=True)
            return

        if key_data["redeemed"]:
            await interaction.followup.send("This key has already been redeemed.", ephemeral=True)
            return

        existing_slot = next((slot for slot in slot_data.values() if slot["user_id"] == interaction.user.id), None)

        if key_data["category_name"] == "Category1":
            category_id = category1_id
        elif key_data["category_name"] == "Category2":
            category_id = category2_id
        else:
            await interaction.followup.send("Invalid category in key data.", ephemeral=True)
            return
        
        category = discord.utils.get(interaction.guild.categories, id=category_id)
        if not category:
            await interaction.followup.send("Category not found.", ephemeral=True)
            return
        
        
        if key_data["duration"] == 'lifetime':
            end_time = None
        elif key_data["duration"].endswith('d'):
            duration_days = int(key_data["duration"][:-1])
            end_time = datetime.now() + timedelta(days=duration_days)
        elif key_data["duration"].endswith('w'):
            duration_days = int(key_data["duration"][:-1]) * 7
            end_time = datetime.now() + timedelta(days=duration_days)
        elif key_data["duration"].endswith('m'):
            duration_days = int(key_data["duration"][:-1]) * 30
            end_time = datetime.now() + timedelta(days=duration_days)
        else:
            duration_days = int(key_data["duration"])
            end_time = datetime.now() + timedelta(days=duration_days)

        creation_time = datetime.now()
        end_timestamp = int(end_time.timestamp()) if end_time else None
        creation_timestamp = int(creation_time.timestamp())

        if existing_slot:
            await interaction.followup.send("You already have an existing slot. You cannot redeem this key.", ephemeral=True)
            return

        else:
            channel_name = f"slot-{interaction.user.name}" if end_time else f"slot-{interaction.user.name}"
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, mention_everyone=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }

            channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)

            premium_role = discord.utils.get(interaction.guild.roles, id=premium_role_id)
            if premium_role:
                await interaction.user.add_roles(premium_role)

            slot_data[channel.id] = {
                "channel_id": channel.id,
                "user_id": interaction.user.id,
                "category_id": category_id,
                "duration_days": key_data["duration"] if end_time else 'lifetime',
                "end_timestamp": end_timestamp,
                "creation_timestamp": creation_timestamp,
                "here_ping": key_data["here_ping"],
                "status": "active",
                "everyone_ping": key_data["everyone_ping"],
                "moderator_id": interaction.user.id,
                "moderator_name": interaction.user.name
            }
            save_json_data(slots_data_file, slot_data)

            ping_data = load_json_data(ping_data_file)
            ping_data[interaction.user.id] = {
                "allowed_here_ping": key_data["here_ping"],
                "allowed_everyone_ping": key_data["everyone_ping"],
                "used_here_ping": 0,
                "used_everyone_ping": 0
            }
            save_json_data(ping_data_file, ping_data)

            keys_data[key]["redeemed"] = True
            save_json_data(keys_file, keys_data)

            channel_embed = discord.Embed(title="Slot Info", color=embed_color)
            channel_embed.add_field(name="User", value=interaction.user.mention, inline=False)
            channel_embed.add_field(name="Duration", value=f"{key_data['duration']}", inline=False)
            channel_embed.add_field(name="Category", value=key_data["category_name"], inline=False)
            channel_embed.add_field(name="Creation Date", value=f"<t:{creation_timestamp}:R>", inline=True)
            channel_embed.add_field(name="Expiry Date", value=f"<t:{end_timestamp}:R>" if end_time else "Lifetime", inline=True)
            channel_embed.add_field(name="Ping Allowed", value=f"```@everyone : {key_data['everyone_ping']}\n@here : {key_data['here_ping']}```", inline=False)
            channel_embed.set_footer(text=embed_footer)
            channel_embed.timestamp = datetime.now(timezone.utc)
            await channel.send(embed=channel_embed)

            user_embed = discord.Embed(title="Your Slot Has Been Created!", color=embed_color)
            user_embed.add_field(name="Channel", value=channel.mention, inline=False)
            user_embed.add_field(name="Duration", value=f"{key_data['duration']}", inline=False)
            user_embed.add_field(name="Category", value=key_data["category_name"], inline=False)
            user_embed.add_field(name="Creation Date", value=f"<t:{creation_timestamp}:R>", inline=False)
            user_embed.add_field(name="Expiry Date", value=f"<t:{end_timestamp}:R>" if end_time else "Lifetime", inline=False)
            user_embed.set_footer(text=embed_footer)
            user_embed.timestamp = datetime.now(timezone.utc)
            await interaction.user.send(embed=user_embed)

            log_channel = bot.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(title="Slot Created", color=embed_color)
                log_embed.add_field(name="Channel", value=channel.mention, inline=False)
                log_embed.add_field(name="User", value=interaction.user.mention, inline=False)
                log_embed.add_field(name="Duration", value=f"{key_data['duration']}", inline=False)
                log_embed.add_field(name="Category", value=key_data["category_name"], inline=False)
                log_embed.add_field(name="@here Pings Allowed", value=str(key_data["here_ping"]), inline=False)
                log_embed.add_field(name="@everyone Pings Allowed", value=str(key_data["everyone_ping"]), inline=False)
                log_embed.add_field(name="Creation Date", value=f"<t:{creation_timestamp}:R>", inline=False)
                log_embed.add_field(name="Expiry Date", value=f"<t:{end_timestamp}:R>" if end_time else "Lifetime", inline=False)
                log_embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
                log_embed.set_footer(text=embed_footer)
                log_embed.timestamp = datetime.now(timezone.utc)
                await log_channel.send(embed=log_embed)

        await interaction.followup.send("Slot redeemed successfully!", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in redeem command: {e}")





def generate_keys(num_keys, key_length=16):
    return [''.join(random.choices(string.ascii_uppercase + string.digits, k=key_length)) for _ in range(num_keys)]

class KeyGenerationModal(Modal):
    def __init__(self, interaction, amount):
        self.interaction = interaction
        self.amount = amount
        super().__init__(title="Key Generation Details")

    category_input = TextInput(
        label="Category Number",
        placeholder="Enter a number corresponding to a category (e.g., 1 for Category1)",
        required=True
    )
    duration_input = TextInput(
        label="Duration",
        placeholder="Enter the duration (e.g., 1d, 1w, 1m, or 'lifetime')",
        required=True
    )
    here_ping_input = TextInput(
        label="@here Pings Allowed",
        placeholder="Enter the number of @here pings allowed",
        required=True
    )
    everyone_ping_input = TextInput(
        label="@everyone Pings Allowed",
        placeholder="Enter the number of @everyone pings allowed",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        keys_file = 'keys_data.json'
        category_number = self.category_input.value
        category_name = CATEGORY_MAPPING.get(category_number, "Default") 
        duration = self.duration_input.value
        here_ping = int(self.here_ping_input.value)
        everyone_ping = int(self.everyone_ping_input.value)

        generated_keys = generate_keys(self.amount)

        keys_data = load_json_data(keys_file)

        for key in generated_keys:
            keys_data[key] = {
                "redeemed": False,
                "category_name": category_name,
                "duration": duration,
                "here_ping": here_ping,
                "everyone_ping": everyone_ping
            }

        save_json_data(keys_file, keys_data)

        keys_message = "\n".join(generated_keys)
        dm_embed = discord.Embed(title="Generated Keys", color=0x00FF00)
        dm_embed.add_field(name="Keys", value=f"```{keys_message}```", inline=False)
        dm_embed.set_footer(text="Keys are valid until redeemed.")
        dm_embed.timestamp = datetime.now(timezone.utc)

        try:
            await self.interaction.user.send(embed=dm_embed)
        except discord.Forbidden:
            await self.interaction.response.send_message("I can't send you a DM. Please make sure you have DMs enabled.", ephemeral=True)
            return

        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            log_embed = discord.Embed(title="Keys Generated", color=0x00FF00)
            log_embed.add_field(name="User", value=self.interaction.user.mention, inline=False)
            log_embed.add_field(name="Number of Keys", value=str(self.amount), inline=False)
            log_embed.add_field(name="Category Name", value=category_name, inline=False)
            log_embed.add_field(name="Duration", value=duration, inline=False)
            log_embed.add_field(name="@here Pings Allowed", value=str(here_ping), inline=False)
            log_embed.add_field(name="@everyone Pings Allowed", value=str(everyone_ping), inline=False)
            log_embed.add_field(name="Timestamp", value=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inline=False)
            log_embed.set_footer(text="Key generation log")
            log_embed.timestamp = datetime.now(timezone.utc)
            await log_channel.send(embed=log_embed)

        await self.interaction.followup.send(f"{self.amount} keys have been generated and sent to your DM.", ephemeral=True)


CATEGORY_MAPPING = {
    "1": "Category1",
    "2": "Category2",
    "3": "Category3"  
}


@bot.tree.command(name="generate", description="Generate a specified number of keys with details.")
@app_commands.describe(amount="Number of keys to generate")
async def generate(interaction: discord.Interaction, amount: int):
    role = discord.utils.get(interaction.guild.roles, id=bot_role_id)

    if role not in interaction.user.roles:

        await interaction.followup.send("You do not have the required role to use this command.", ephemeral=True)

        return
    
    if amount < 1:
        await interaction.response.send_message("Please specify a positive number of keys to generate.", ephemeral=True)
        return

    modal = KeyGenerationModal(interaction, amount)
    await interaction.response.send_modal(modal)






def parse_duration(duration: str) -> timedelta:
    """Parse duration string and return a timedelta object."""
    match = re.match(r"(\d+)([dwmy])", duration)
    if match:
        value, unit = match.groups()
        value = int(value)
        if unit == 'd':
            return timedelta(days=value)
        elif unit == 'w':
            return timedelta(weeks=value)
        elif unit == 'm':
            return timedelta(days=value * 30)  # Approximation for months
        elif unit == 'y':
            return timedelta(days=value * 365)  # Approximation for years
    else:
        return timedelta(days=int(duration))  # Default: days




@bot.tree.command(name="renew", description="Renew a user's slot with a specified duration.")
async def renew(interaction: discord.Interaction, user_mention: discord.Member, duration: str):
    await interaction.response.defer()

    role = discord.utils.get(interaction.guild.roles, id=bot_role_id)
    if role not in interaction.user.roles:
        await interaction.followup.send("You do not have the required role to use this command.", ephemeral=True)
        return

    try:
        slot_data = load_json_data(slots_data_file)

        user_id = user_mention.id
        user_slot_key = next((key for key, slot in slot_data.items() if slot.get("user_id") == user_id), None)
        if not user_slot_key:
            await interaction.followup.send("No slot found for the specified user.", ephemeral=True)
            return

        current_end_timestamp = slot_data[user_slot_key].get("end_timestamp")
        old_duration_days = slot_data[user_slot_key].get("duration_days", 0)


        if current_end_timestamp is None:
            await interaction.followup.send("This slot is already set to lifetime and cannot be renewed.", ephemeral=True)
            return


        if current_end_timestamp:
            current_end_time = datetime.fromtimestamp(current_end_timestamp, tz=timezone.utc)
        else:
            current_end_time = None

        if duration.lower() == "lifetime":
            new_end_time = None 
            new_end_timestamp = None
            duration_days_added = 0
        else:
            renewal_period = parse_duration(duration)
            duration_days_added = renewal_period.days 
            
            if current_end_time:
                new_end_time = current_end_time + renewal_period
            else:
                new_end_time = datetime.now(timezone.utc) + renewal_period

            new_end_timestamp = int(new_end_time.timestamp())


        if new_end_timestamp:
            slot_data[user_slot_key]["end_timestamp"] = new_end_timestamp
        else:
            slot_data[user_slot_key]["end_timestamp"] = "lifetime"  
            
        if old_duration_days == "lifetime":
            slot_data[user_slot_key]["duration_days"] = "lifetime"
        else:
            new_duration_days = old_duration_days + duration_days_added
            slot_data[user_slot_key]["duration_days"] = new_duration_days

        save_json_data(slots_data_file, slot_data)

        old_expiry_time = current_end_time.strftime("%Y-%m-%d %H:%M:%S") if current_end_time else "No previous expiry time (first-time renewal or lifetime)"
        new_expiry_time = new_end_time.strftime("%Y-%m-%d %H:%M:%S") if new_end_time else "Lifetime"


        user_embed = discord.Embed(title="Slot Renewed", color=embed_color)
        user_embed.add_field(name="Old Expiry Time", value=old_expiry_time, inline=False)
        user_embed.add_field(name="New Expiry Time", value=new_expiry_time, inline=False)
        user_embed.add_field(name="Duration", value=duration, inline=False)
        user_embed.set_footer(text="Thank you for renewing your slot!")
        user_embed.timestamp = datetime.now(timezone.utc)
        await user_mention.send(embed=user_embed)


        channel = interaction.guild.get_channel(slot_data[user_slot_key]["channel_id"])
        if channel:
            slot_embed = discord.Embed(title="Slot Renewed", color=embed_color)
            slot_embed.add_field(name="User", value=user_mention.mention, inline=False)
            slot_embed.add_field(name="Old Expiry Time", value=old_expiry_time, inline=False)
            slot_embed.add_field(name="New Expiry Time", value=new_expiry_time, inline=False)
            slot_embed.add_field(name="Duration", value=duration, inline=False)
            slot_embed.set_footer(text="This slot has been renewed.")
            slot_embed.timestamp = datetime.now(timezone.utc)
            await channel.send(embed=slot_embed)


        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            log_embed = discord.Embed(title="Slot Renewed", color=embed_color)
            log_embed.add_field(name="User", value=user_mention.mention, inline=False)
            log_embed.add_field(name="Old Expiry Time", value=old_expiry_time, inline=False)
            log_embed.add_field(name="New Expiry Time", value=new_expiry_time, inline=False)
            log_embed.add_field(name="Duration", value=duration, inline=False)
            log_embed.add_field(name="Executed By", value=interaction.user.mention, inline=False)
            log_embed.set_footer(text="Slot renewal log.")
            log_embed.timestamp = datetime.now(timezone.utc)
            await log_channel.send(embed=log_embed)

        await interaction.followup.send("Slot has been successfully renewed.", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return


    if message.channel.category_id in [category1_id, category2_id]:

        if '@here' in message.content or '@everyone' in message.content:
            user_id_str = str(message.author.id)


            ping_data = load_json_data(ping_data_file)

            if user_id_str in ping_data:
                user_ping_data = ping_data[user_id_str]
                allowed_here_ping = user_ping_data.get('allowed_here_ping', 0)
                allowed_everyone_ping = user_ping_data.get('allowed_everyone_ping', 0)
                used_here_ping = user_ping_data.get('used_here_ping', 0)
                used_everyone_ping = user_ping_data.get('used_everyone_ping', 0)

                if '@here' in message.content:
                    if used_here_ping < allowed_here_ping:
                        used_here_ping += 1
                        user_ping_data['used_here_ping'] = used_here_ping
                        save_json_data(ping_data_file, ping_data)
                        await message.channel.send(f"- **{used_here_ping}/{allowed_here_ping}** `@here` **| USE MM TO BE SURE**")
                    else:
                        await message.channel.send("- `Revoking Slot !!`")
                        await revoke_slot(message.author, "Overused @here pings.")

                if '@everyone' in message.content:
                    if used_everyone_ping < allowed_everyone_ping:
                        used_everyone_ping += 1
                        user_ping_data['used_everyone_ping'] = used_everyone_ping
                        save_json_data(ping_data_file, ping_data)
                        await message.channel.send(f"- **{used_everyone_ping}/{allowed_everyone_ping}** `@everyone` **| USE MM TO BE SURE!**")
                    else:
                        await message.channel.send("- `Revoking Slot !!`")
                        await revoke_slot(message.author, "Overused @everyone pings.")
            else:
                await message.channel.send("You don't have any allowed pings configured.")

    await bot.process_commands(message)


async def revoke_slot(user: discord.Member, reason: str):
    try:

        slot_data = load_json_data(slots_data_file)
        

        slot = next((slot for slot in slot_data.values() if slot["user_id"] == user.id), None)
        if not slot:
            return  
            
        if slot["status"] == "revoked":
            return  
            
        channel = bot.get_channel(slot["channel_id"])
        if not channel:
            return  
            
        slot["status"] = "revoked"
        save_json_data(slots_data_file, slot_data)


        await channel.set_permissions(user, send_messages=False)


        premium_role = discord.utils.get(user.guild.roles, id=premium_role_id)
        if premium_role:
            await user.remove_roles(premium_role)
        

        user_dm_embed = discord.Embed(title="Your Slot Has Been Revoked", color=embed_color)
        user_dm_embed.add_field(name="Reason", value=reason, inline=False)
        user_dm_embed.add_field(name="Channel", value=channel.mention, inline=False)
        user_dm_embed.add_field(name="Executed By", value="System (Auto-Revoked)", inline=False)
        user_dm_embed.set_footer(text="This action is irreversible.")
        user_dm_embed.set_thumbnail(url=embed_thumbnail_url)
        user_dm_embed.timestamp = discord.utils.utcnow()
        
        await user.send(embed=user_dm_embed)


        slot_channel_embed = discord.Embed(title="Slot Revoked", color=embed_color)
        slot_channel_embed.add_field(name="User", value=user.mention, inline=False)
        slot_channel_embed.add_field(name="Reason", value=reason, inline=False)
        slot_channel_embed.add_field(name="Executed By", value="System (Auto-Revoked)", inline=False)
        slot_channel_embed.set_footer(text="This action is irreversible.")
        slot_channel_embed.set_thumbnail(url=embed_thumbnail_url)
        slot_channel_embed.timestamp = discord.utils.utcnow()

        await channel.send(embed=slot_channel_embed)


        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            log_embed = discord.Embed(title="Slot Revoked", color=embed_color)
            log_embed.add_field(name="User", value=user.mention, inline=False)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.add_field(name="Channel", value=channel.mention, inline=False)
            log_embed.add_field(name="Executed By", value="System (Auto-Revoked)", inline=False)
            log_embed.set_footer(text="This action is irreversible.")
            log_embed.set_thumbnail(url=embed_thumbnail_url)
            log_embed.timestamp = discord.utils.utcnow()

            await log_channel.send(embed=log_embed)
        
    except Exception as e:
        print(f"An error occurred while revoking the slot: {e}")




@bot.tree.command(name="slot-info", description="View details of a slot.")
@app_commands.describe(user_mention="The user to mention (optional)")
async def slot_info(interaction: discord.Interaction, user_mention: discord.Member = None):
    await interaction.response.defer()

    bot_role = discord.utils.get(interaction.guild.roles, id=bot_role_id)
    if not bot_role or bot_role not in interaction.user.roles:
        if user_mention and user_mention != interaction.user:
            await interaction.followup.send("You do not have the required role to view other users' slots.", ephemeral=True)
            return


    target_user = user_mention if user_mention else interaction.user


    try:
        with open(slots_data_file, 'r') as file:
            slot_data = json.load(file)
    except FileNotFoundError:
        await interaction.followup.send("Slot data file not found.", ephemeral=True)
        return
    except json.JSONDecodeError:
        await interaction.followup.send("Error decoding slot data file.", ephemeral=True)
        return


    try:
        with open(ping_data_file, 'r') as file:
            ping_data = json.load(file)
    except FileNotFoundError:
        await interaction.followup.send("Ping data file not found.", ephemeral=True)
        return
    except json.JSONDecodeError:
        await interaction.followup.send("Error decoding ping data file.", ephemeral=True)
        return


    slot = next((slot for slot in slot_data.values() if slot["user_id"] == target_user.id), None)
    if not slot:
        if target_user == interaction.user:
            await interaction.followup.send("You do not have an active slot.", ephemeral=True)
        else:
            await interaction.followup.send(f"{target_user.mention} does not have an active slot.", ephemeral=True)
        return


    user_ping_data = ping_data.get(str(target_user.id), {})
    total_here_ping = user_ping_data.get("allowed_here_ping", 0)
    used_here_ping = user_ping_data.get("used_here_ping", 0)
    total_everyone_ping = user_ping_data.get("allowed_everyone_ping", 0)
    used_everyone_ping = user_ping_data.get("used_everyone_ping", 0)


    def unix_to_datetime(timestamp):
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if timestamp else "N/A"
        except Exception as e:
            return f"Error converting timestamp: {e}"

    purchase_date = unix_to_datetime(slot.get("creation_timestamp"))
    expiry_date = unix_to_datetime(slot.get("end_timestamp"))


    channel = bot.get_channel(int(slot["channel_id"]))
    slot_name = "N/A"
    print(channel.name)
    if channel:
        slot_name = channel.name
    else:
        slot_name = "N/A"
    


    slot_embed = discord.Embed(title=f"Slot Information for {target_user.display_name}", color=embed_color)
    

    slot_embed.add_field(name="User Details", value=(
        f"**Username:** `{target_user.display_name}`\n"
        f"**User ID:** `{target_user.id}`"
    ), inline=False)
    

    slot_embed.add_field(name="Slot Details", value=(
        f"**Slot Name:** `{slot_name}` `{slot.get('channel_id', 'N/A')}`\n"
        f"**Category ID:** `{slot.get('category_id', 'N/A')}`\n\n"
        f"**Duration:** `{slot.get('duration_days', 'N/A')}`\n"
        f"**Purchase Date:** `{purchase_date}`\n"
        f"**Expiry Date:** `{expiry_date}`"
    ), inline=False)
    
    ping_details = (
    f"```diff\n"
    f"@here | Used: {used_here_ping}/{total_here_ping}\n"
    f"@everyone | Used: {used_everyone_ping}/{total_everyone_ping}\n"
    f"```"
)


    slot_embed.add_field(name="Ping Details", value=ping_details, inline=False)



    icon_url = target_user.avatar.url if target_user.avatar else None
    if icon_url:
        slot_embed.set_thumbnail(url=icon_url)

    slot_embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    slot_embed.timestamp = datetime.now()


    try:
        await interaction.followup.send(embed=slot_embed)
    except discord.HTTPException as e:
        await interaction.followup.send(f"Failed to send embed: {e}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)




@bot.tree.command(name="recovery", description="Recover channels by deleting old ones and creating new ones for each slot user.")
async def recovery(interaction: discord.Interaction):
    await interaction.response.defer()

    role = discord.utils.get(interaction.guild.roles, id=bot_role_id)
    if role not in interaction.user.roles:
        await interaction.followup.send("You do not have the required role to use this command.", ephemeral=True)
        return

    try:

        slot_data = load_json_data(slots_data_file)



        created_channels = 0
        active_slots = 0
        held_slots = 0


        for category_id in [category1_id, category2_id]:
            category = discord.utils.get(interaction.guild.categories, id=category_id)
            if category:
                for channel in category.channels:
                    await channel.delete()


        for key, slot in slot_data.items():
            user_id = slot.get('user_id')
            user = interaction.guild.get_member(user_id)
            if not user:
                continue


            if slot.get('status') == 'revoked':
                continue


            category = discord.utils.get(interaction.guild.categories, id=category1_id)  # Use appropriate category ID
            if not category:
                continue

            new_channel = await interaction.guild.create_text_channel(f"slot-{user}", category=category)


            permissions = {
                user: discord.PermissionOverwrite(mention_everyone=True)
            }
            if slot.get('status') == 'active':
                permissions[user] = discord.PermissionOverwrite(send_messages=True, mention_everyone=True)

                premium_role = discord.utils.get(interaction.guild.roles, id=premium_role_id)
                if premium_role:
                    await user.add_roles(premium_role)
                active_slots += 1
            elif slot.get('status') == 'on hold':
                permissions[user] = discord.PermissionOverwrite(send_messages=False, mention_everyone=False)
                held_slots += 1

            await new_channel.edit(overwrites=permissions)


            channel_embed = discord.Embed(title="Slot Info", color=embed_color)
            channel_embed.add_field(name="User", value=user.mention, inline=False)
            channel_embed.add_field(name="Duration", value=f"{slot.get('duration_days', 'Lifetime')} Days", inline=False)
            channel_embed.add_field(name="Category", value=category.name, inline=False)
            channel_embed.add_field(name="Creation Date", value=f"<t:{int(time.time())}:R>", inline=True)
            channel_embed.add_field(name="Expiry Date", value=f"<t:{slot.get('end_timestamp', int(time.time()))}:R>" if slot.get('end_timestamp') else "Lifetime", inline=True)
            channel_embed.add_field(name="Ping Allowed", value=f"```@everyone : {slot.get('everyone_ping', '0')}\n@here : {slot.get('here_ping', '0')}```", inline=False)
            channel_embed.set_footer(text=embed_footer)
            channel_embed.set_thumbnail(url=embed_thumbnail_url)
            await new_channel.send(embed=channel_embed)


            status_embed = discord.Embed(title="Slot Status", color=embed_color)
            if slot.get('status') == 'active':
                status_embed.add_field(name="Status", value="The slot is active. You have received permission to send messages and ping everyone.", inline=False)
            elif slot.get('status') == 'on hold':
                status_embed.add_field(name="Status", value="The slot is temporarily on hold. You will not have permission to send messages or ping everyone.", inline=False)
            status_embed.set_footer(text=embed_footer)
            await new_channel.send(embed=status_embed)


            dm_embed = discord.Embed(title="Slot Created", color=embed_color)
            dm_embed.add_field(name="Channel", value=f"<#{new_channel.id}>", inline=False)
            dm_embed.add_field(name="Duration", value=f"{slot.get('duration_days', 'Lifetime')} Days", inline=False)
            dm_embed.add_field(name="Status", value="Active" if slot.get('status') == 'active' else "On Hold", inline=False)
            dm_embed.set_footer(text=embed_footer)
            try:
                await user.send(embed=dm_embed)
            except discord.Forbidden:
                print(f"Could not send DM to {user.name}")


            slot_data[key]['channel_id'] = new_channel.id


            await asyncio.sleep(2)

            created_channels += 1


        save_json_data(slots_data_file, slot_data)


        stats_embed = discord.Embed(title="Recovery Completed", color=embed_color)
        stats_embed.add_field(name="Channels Created", value=str(created_channels), inline=False)
        stats_embed.add_field(name="Active Slots", value=str(active_slots), inline=False)
        stats_embed.add_field(name="Held Slots", value=str(held_slots), inline=False)
        stats_embed.set_footer(text=embed_footer)
        await interaction.followup.send(embed=stats_embed, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)




@bot.tree.command(name="slot-ping", description="Check your slot ping allowances and slot expiry date.")
async def slot_ping(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user_id = interaction.user.id


    slot_data = load_json_data(slots_data_file)
    ping_data = load_json_data(ping_data_file)


    user_slot = None
    for key, slot in slot_data.items():
        if slot['user_id'] == user_id:
            user_slot = slot
            break


    if not user_slot:
        await interaction.followup.send("You don't have an active slot.", ephemeral=True)
        return


    user_ping_data = ping_data.get(str(user_id), {})
    allowed_everyone_pings = user_ping_data.get('allowed_everyone_ping', 0)
    allowed_here_pings = user_ping_data.get('allowed_here_ping', 0)
    used_everyone_pings = user_ping_data.get('used_everyone_ping', 0)
    used_here_pings = user_ping_data.get('used_here_ping', 0)


    end_timestamp = user_slot.get('end_timestamp')
    expiry_date = f"<t:{end_timestamp}:R>" if end_timestamp else "Lifetime"


    current_time = datetime.now(pytz.timezone(TIMEZONE))
    reset_time_today = current_time.replace(hour=RESET_HOUR, minute=RESET_MINUTE, second=0, microsecond=0)
    
    if current_time > reset_time_today:
        reset_time_today += timedelta(days=1)
    
    next_reset_time = f"<t:{int(reset_time_today.timestamp())}:F>"

    ping_details = (
        f"@here: {used_here_pings}/{allowed_here_pings}\n"
        f"@everyone: {used_everyone_pings}/{allowed_everyone_pings}"
    )


    slot_ping_embed = discord.Embed(title="Slot Ping Info", color=embed_color)
    slot_ping_embed.add_field(name="User", value=interaction.user.mention, inline=False)
    slot_ping_embed.add_field(name="Ping Details", value=f"```{ping_details}```", inline=False)
    slot_ping_embed.add_field(name="Slot Expiry Date", value=expiry_date, inline=True)
    slot_ping_embed.add_field(name="Next Reset Time", value=next_reset_time, inline=True)

    slot_ping_embed.set_footer(text=embed_footer)
    slot_ping_embed.set_thumbnail(url=embed_thumbnail_url)


    await interaction.followup.send(embed=slot_ping_embed, ephemeral=True)


@tasks.loop(minutes=1)
async def ping_reset():
    current_time = datetime.now(pytz.timezone(TIMEZONE))

    if current_time.hour == RESET_HOUR and current_time.minute == RESET_MINUTE:
        try:
            with open(ping_data_file, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}


        for ping_data in data.values():
            ping_data["used_here_ping"] = 0
            ping_data["used_everyone_ping"] = 0


        with open(ping_data_file, "w") as f:
            json.dump(data, f, indent=2)

        guild = bot.get_guild(server_id)
        if guild is not None:
            channel = guild.get_channel(seller_channelID)
            if channel is not None:
                embed = discord.Embed(
                    title="Ping Reset",
                    description="Pings have been reseted!<@&1250097968275525674>",
                    color=embed_color
                )
                embed.set_footer(text=embed_footer)
                embed.timestamp = datetime.now()
                embed.set_thumbnail(url=embed_thumbnail_url)

                await channel.send(embed=embed)
                print("Ping usage has been reset and notification sent.")
            else:
                print("Seller channel not found.")
        else:
            print("Guild not found.")




@bot.tree.command(name="reset-pings", description="Manually reset ping data for all users.")
async def reset_pings(interaction: discord.Interaction):
    role = discord.utils.get(interaction.guild.roles, id=bot_role_id)
    if role not in interaction.user.roles:
        await interaction.followup.send("You do not have the required role to use this command.", ephemeral=True)
        return


    try:
        with open(ping_data_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}


    for ping_data in data.values():
        ping_data["used_here_ping"] = 0
        ping_data["used_everyone_ping"] = 0


    with open(ping_data_file, "w") as f:
        json.dump(data, f, indent=2)


    guild = bot.get_guild(server_id)
    if guild is not None:
        channel = guild.get_channel(seller_channelID)
        if channel is not None:
            embed = discord.Embed(
                title="Ping Data Reset",
                description="Pings have been reseted!<@&1250097968275525674>",
                color=embed_color
            )
            embed.set_footer(text=embed_footer)
            embed.set_thumbnail(url=embed_thumbnail_url)
            embed.timestamp = datetime.now()

            await channel.send(embed=embed)
            await interaction.response.send_message("Ping data has been successfully reset.", ephemeral=True)
        else:
            await interaction.response.send_message("Seller channel not found.", ephemeral=True)
    else:
        await interaction.response.send_message("Guild not found.", ephemeral=True)



@bot.tree.command(name="delete", description="Delete all revoked slots and their details.")
async def delete_slots(interaction: discord.Interaction):
    role = discord.utils.get(interaction.guild.roles, id=bot_role_id)
    if role not in interaction.user.roles:
        await interaction.followup.send("You do not have the required role to use this command.", ephemeral=True)
        return


    try:
        with open(slots_data_file, "r") as f:
            slot_data = json.load(f)
    except FileNotFoundError:
        slot_data = {}

    try:
        with open(ping_data_file, "r") as f:
            ping_data = json.load(f)
    except FileNotFoundError:
        ping_data = {}

    guild = bot.get_guild(server_id)
    if guild is None:
        await interaction.response.send_message("Guild not found.", ephemeral=True)
        return


    deleted_slots_count = 0
    channels_deleted = 0
    pings_deleted_count = 0


    for slot_id in list(slot_data.keys()):
        if slot_data[slot_id].get('status') == 'revoked':
            user_id = slot_data[slot_id].get('user_id')


            channel_id = slot_data[slot_id].get('channel_id')
            if channel_id:
                channel = guild.get_channel(channel_id)
                if channel:
                    try:
                        await channel.delete()
                        channels_deleted += 1
                    except discord.Forbidden:
                        print(f"Permission error: Could not delete channel {channel_id}.")
                    except discord.HTTPException as e:
                        print(f"HTTP exception: {e}")


            del slot_data[slot_id]
            deleted_slots_count += 1


            if str(user_id) in ping_data:
                del ping_data[str(user_id)]
                pings_deleted_count += 1


    with open(slots_data_file, "w") as f:
        json.dump(slot_data, f, indent=2)

    with open(ping_data_file, "w") as f:
        json.dump(ping_data, f, indent=2)


    channel = guild.get_channel(seller_channelID)
    if channel:
        embed = discord.Embed(
            title="Revoked Slots Deleted",
            description=(
                f"All revoked slots, their associated channels, and ping data have been deleted.\n"
                f"Total deleted slots: {deleted_slots_count}.\n"
                f"Channels deleted: {channels_deleted}.\n"
                f"Ping data removed: {pings_deleted_count}."
            ),
            color=embed_color
        )
        embed.set_footer(text=embed_footer)
        embed.set_thumbnail(url=embed_thumbnail_url)
        embed.timestamp = datetime.now()

        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"Revoked slots, their channels, and ping data have been successfully deleted.\n"
            f"Total deleted slots: {deleted_slots_count}.\n"
            f"Channels deleted: {channels_deleted}.\n"
            f"Ping data removed: {pings_deleted_count}.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message("Seller channel not found.", ephemeral=True)


bot.run(bot_token)
