# -*- coding: utf-8 -*-

import discord
from discord import Forbidden
#from discord.ext import commands
import random
from dict import DictionaryReader
from botkey import Key
from subprocess import call
import sys
from priestLogger import PriestLogger
from perspectiveHandler import PerspectiveHandler
import logging
import time
from discord import HTTPException
from discord import utils
from discord import DMChannel
from roleHandler import RoleHandler

logging.basicConfig(level=logging.INFO)

client = discord.Client()

prefix = Key().prefix()

logger = PriestLogger()

toxicity = PerspectiveHandler()

@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')

@client.event
async def on_message(message):
    r = DictionaryReader()

    if message.channel.id == int(r.perspectiveLogChannelH2P()):
        await toxicity.addReactions(r, message)

    # we do not want the bot to reply to itself
    if message.author == client.user:
        return
        
    if message.content.startswith(prefix):
        await messageHandler(message)
        
    if isinstance(message.channel, DMChannel) or message.channel.name in r.logChannels():
        logger.log(message)
        await toxicity.measure(client, message)    
        
@client.event
async def on_message_edit(before, after):
    logger.logEdit(before, after)    
    
@client.event
async def on_member_join(member):
    await sendWelcomeMessage(member)
    await logAction(member, member.guild, 'joined')

@client.event
async def on_raw_reaction_add(payload):

    if payload.user_id == client.user.id:
        return

    r = DictionaryReader()

    print(r.readEntry('subscriptionchannel',''))
    print(payload.emoji.name)
    #Only for reactions inside the report channel
    if payload.channel_id == int(r.perspectiveLogChannel()):
        await toxicity.feedback(payload.emoji, payload.user_id, r)

    elif payload.channel_id == int(r.readEntry('subscriptionchannel','')):
        await RoleHandler.newsSubscriptionAdd(client, payload.emoji, payload.user_id, payload.guild_id)

@client.event
async def on_raw_reaction_remove(payload):
    r = DictionaryReader()

    if payload.channel_id == int(r.readEntry('subscriptionchannel','')):
        await RoleHandler.newsSubscriptionRemove(client, payload.emoji, payload.user_id, payload.guild_id)

@client.event   
async def on_member_remove(member):
    print('member left')
    await logAction(member, member.guild, 'left')
    await RoleHandler.toggleUserState(client, member, None)
    
@client.event
async def on_member_ban(guild, user):
    await logAction(user, guild, 'banned')
    
@client.event
async def on_member_unban(member):
    await logAction(member, member.guild, 'unbanned')
    
@client.event
async def on_member_update(before, after):
    await RoleHandler.toggleUserState(client, before, after)
    
async def logAction(user, guild, action):
    r = DictionaryReader()
    if guild:
        await client.get_channel(int(r.actionLogChannel())).send('['+time.strftime("%Y-%m-%d %H:%M:%S")+'] {1.name} - {0.name} {0.mention} ({0.id}) {2}'.format(user, guild, action))
    else:
        await client.get_channel(int(r.actionLogChannel())).send('No Server - {0.name} {0.mention} ({0.id}) {1}'.format(user, action))
    #print('error while writing {0} log'.format(action))
    
            
async def messageHandler(message):
    p = DictionaryReader()

    if message.guild:
        await client.get_channel(p.logReportChannel()).send('{0.guild.name} - {0.channel.name} - {0.author} invoked {0.content}'.format(message))
    else:
        await client.get_channel(p.logReportChannel()).send('PM - PM - {0.author} invoked {0.content}'.format(message))
    
    if message.content.startswith(prefix+'fullupdate') or message.content.startswith(prefix+'update') or message.content.startswith(prefix+'channel'):
        await maintenanceMessages(message)

    elif message.content.startswith(prefix+'send'):
        await forwardMessage(message)
        
    elif message.content.startswith(prefix+'item'):
        await itemMessage(message)
    
    elif message.content.startswith(prefix+'pin') or message.content.startswith(prefix+'pins'):
        await sendPinMessages(message)

    elif message.content.startswith(prefix+'sub'):
        await RoleHandler.newsSubscription(client, message)
        await message.delete()
        
    elif message.content.startswith(prefix+'ban') or message.content.startswith(prefix+'info'):
        await adminControl(message)
        
    elif message.content.startswith(prefix+'stream'):
        print('StreamCommand')
        await RoleHandler.toggleStream(client, message)
        await message.delete()
        
    else:
        await generalMessage(message)

async def maintenanceMessages(message):
    if message.content.startswith(prefix+'update'):
        call(["git","pull"])
    p = DictionaryReader()
    if message.content.startswith(prefix+'fullupdate'): 
        if str(message.author.id) not in p.admins():
            await message.channel.send('You\'re not my dad, {0.mention}!'.format(message.author))
            return
        call(["git","pull"])
        call(["start_bot.sh"])
        sys.exit()
    elif message.content.startswith(prefix+'channel'):
        await message.author.send(str(message.channel.id))

async def forwardMessage(message):
    p = DictionaryReader()
    roles = message.author.roles
    canSend = False
    for role in roles:
        canSend = canSend or (role.name in p.roles())
    if not canSend:
        print('{0.author.name} can\'t send whispers'.format(message))
        return
    entries = message.content.split(' ')
    target = message.mentions[0]
    if target != None:
        entry = ' '.join(entries[2::])
        msg = p.commandReader(entry)
        if msg != None:
            await target.send(msg)
            await message.delete()
            await message.author.send('Message sent to {0.mention}'.format(target))
        else:
            await message.channel.send('Invalid Message, {0.mention}'.format(message.author))

async def itemMessage(message):
    p = DictionaryReader()
    msg = p.itemReader(message.content[1::])
    await message.channel.send(msg)
    
async def sendWelcomeMessage(member):
    p = DictionaryReader()
    msg = p.commandReader('help')
    await member.send(msg)
    
async def sendPinMessages(message):
    pins = await message.channel.pins()
    size = 10
    count = 0
    command = message.content.split(' ')
    try:
        await message.delete()
    except (HTTPException, Forbidden):
        print('Error deleting message, probably from whisper')
    if len(command) > 1:
        size = int(command[1]) if isinstance(command[1], int) else 10
        
    for msg in pins:
        if count >= size:
            return
        if msg.content:
            await message.author.send('``` Pin '+ str(count+1) + ' ```')
            await message.author.send(msg.content)
        count += 1

async def generalMessage(message):
    p = DictionaryReader()
    try:
        roles = len(message.author.roles)
    except Exception:
        roles = 10
    command = message.content[1::].split(' ')[0].lower()
    msg = ''
    if not isinstance(message.channel, DMChannel):
        msg = p.commandReader(message.content[1::],message.channel.name)
    else:
        msg = p.commandReader(message.content[1::],'PM')
        
    if msg != None:
        if command in p.whisperCommands():
            if command == 'pub' and roles > 1 and 'help' not in message.content:
                await message.channel.send(msg)
            else:
                await message.author.send(msg)
                try:
                    await message.delete()
                except (HTTPException, Forbidden):
                    print('Error deleting message, probably from whisper')
        else:
            await message.channel.send(msg)
    else:
        if not isinstance(message.channel, DMChannel):
            msg = p.commandReader(message.content[1::],message.channel.name)
        else:
            msg = p.commandReader(message.content[1::],'PM')
        print(message.content[1::])
        print(msg)
        await message.author.send(msg)        
        try:
            await message.delete()
        except (HTTPException, Forbidden):
            print('Error deleting message, probably from whisper')

async def adminControl(message):
    p = DictionaryReader()
    roles = message.author.roles
    canBan = False
    for role in roles:
        canBan = canBan or (role.name in p.roles())
    if not canBan:
        print('{0.author.name} can\'t manage members!'.format(message))
        await message.author.send('You can\'t manage members!')  
        return
    else:
        # Bans - Format:  !ban 9999999999999
        if message.content.startswith(prefix+'ban'):
            if not message.guild.me.guild_permissions.ban_members:
                await message.author.send('The bot does not have permissions to manage members.')
                return
            id = message.content.split(' ')[1]
            reason = ' '.join(message.content.split(' ')[2::])
            try:
                user = await client.get_user_info(id)
                await message.guild.ban(user=user, reason=reason)
                if user != None:
                    await message.author.send('User {0.mention} banned successfully'.format(user))
                else:
                    await message.author.send('Invalid user ID')                            
            except discord.HTTPException:
                pass
            finally:
                await message.delete()
        # Ban info - Format:  !info 9999999999999
        if message.content.startswith(prefix+'info'):        
            if not message.guild.me.guild_permissions.view_audit_log:
                await message.author.send('The bot does not have permissions to view audit logs.')
                return
            id = message.content.split(' ')[1]
            isUserBanned = False
            
            try:
                await message.delete()
            except (HTTPException, Forbidden):
                print('Error deleting message, probably from whisper')
            
            user = await client.get_user_info(id)
            
            await message.author.send( 'User {0.mention}\n```Bans```'.format(user) )
            
            async for entry in message.guild.audit_logs(action=discord.AuditLogAction.ban):                
                if str(entry.target.id) == str(id):               
                    await message.author.send('-> User {0.target}({0.target.id}) was **banned** by {0.user}({0.user.id}) on {0.created_at} (UTC)\n\tReason: {0.reason}\n'.format(entry))
                    isUserBanned = True
            
            await message.author.send( '```Unbans```' )
            async for entry in message.guild.audit_logs(action=discord.AuditLogAction.unban):
                if entry.target.id == int(id):
                    await message.author.send('-> User {0.target} was **unbanned** by {0.user}({0.user.id}) on {0.created_at} (UTC)'.format(entry))                    
            if not isUserBanned:
                await message.author.send('User was never banned.')
client.run(Key().value())
