import discord
from discord.ext import commands
import logging
import asyncio
import atexit
from koncertohandler import KoncertoHandler


logging.basicConfig(level=logging.DEBUG)
logging.getLogger("websockets").setLevel(logging.WARNING)
#logging.getLogger("discord.http").setLevel(logging.WARNING)
#logging.getLogger("discord.client").setLevel(logging.WARNING)
logging.getLogger("discord.gateway").setLevel(logging.WARNING)

if not discord.opus.is_loaded() :
    discord.opus.load("opus")

class Answer:
    """ Class that represents an entry for a blindtest """
    def __init__(self, entry=None):
        self.url = None
        self.answers = []

        if entry is not None:
            self.load(entry)

    def load(self, entry):
        self.url = entry["url"]
        self.answers = [x.strip() for x in entry["answers"].lower().split(",")]

    def isRight(self, answer):
        return (answer in self.answers)

    def getUrl(self):
        return self.url


class PlayerManager:
    """ Manager players for the blindtest """
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def addPlayer(self, idPlayer):
        if self.isPlayer(idPlayer) == False:
            self.players[idPlayer] = 0
            await self.bot.say(":white_check_mark: <@"+str(idPlayer) + "> **registered !**")
        else:
            await self.bot.say(":x: <@"+str(idPlayer)+"> **you are already registered !**")

    def isPlayer(self, idPlayer):
        return (idPlayer in self.players)

    async def removePlayer(self, idPlayer):
        if self.isPlayer(idPlayer) == True:
            del self.players[idPlayer]
            await bot.say(":white_check_mark: <@"+str(idPlayer) + "> **removed !**")
        else:
            await bot.say(":x: <@" + str(idPlayer) + "> **you are not registered as a player !**")

    async def addPoint(self, idPlayer):
        self.players[idPlayer] += 1
        await self.bot.say("<@" + str(idPlayer) + "> good job !\nCurrent score : " + str(self.players[idPlayer]))

    def getWinner(self):
        winners = []

        if len(self.players) <= 0:
            return None

        maxValue = max(self.players.values())  #<-- max of values
        
        for key in self.players:
            if self.players[key] == maxValue:
                winners.append((key, maxValue))

        return winners

    async def scores(self, member=None):
        if member is not None:
                if member.id not in self.players:
                    await self.bot.say(":x: <@" + str(member.id) + "> is not registered as a player !")
                else:
                    await self.bot.say(":speech_left: <@"+ str(member.id) + "> has " + str(self.players[member.id]) + " points !")
        else:
            if len(self.players) <= 0:
                await self.bot.say(":speech_left: There is no player")
            else:
                for player in self.players:
                    await self.bot.say(":speech_left: <@" + str(player) + "> has " + str(self.players[player]) + " points !")

    def clean(self):
        self.players.clear()

class BlindTest:

    def __init__(self, bot):
        self.bot = bot
        self.kh = KoncertoHandler()
        self.pm = PlayerManager(bot)
        self.voice = None
        self.playing = False
        self.player = None
        #Blind test
        self.bt = None
        self.entries= []
        self.indexEntry = 0
        #We have to keep a trace of the channel used to discuss with the bot
        self.channel = None

    @commands.command(no_pm=True, pass_context=True, description="Print the discord id of the caller")
    async def id(self, context):
        """ Print discord user id"""
        await self.bot.say(context.message.author.id)

    @commands.group(no_pm=True, pass_context=True, description="Start a blind test with a")
    async def start(self, context):
        """ Start a blindtest """

        summonedChannel = context.message.author.voice_channel
        self.channel = context.message.channel

        if summonedChannel is None:
            await self.bot.say(":x: <@" + str(context.message.author.id + "> you are not in a voice channel !"))
            return
        
        if self.voice is None:
            self.voice = await self.bot.join_voice_channel(summonedChannel)

        if self.playing is True:
            await self.bot.say(":x: A blindtest is currently, playing, stop it before stating a new one !")

        if context.subcommand_passed is not None:
            tid = context.subcommand_passed

            self.bt = await self.kh.getList(tid)

            logging.debug(self.bt)

            if self.bt["owner"] == None:
                await self.bot.say(":x: Unknow test id : **" + tid + "**")
                return

            if context.message.author.id == self.bt["owner"]:

                for entry in self.bt["entries"]:
                    if entry["url"] is not "" :
                        self.entries.append(Answer(entry))

                await self.bot.say("**The blindtest will start.** \nRegister yourself as a player whith the `$reg` command\n\n")
                await self.bot.say(":arrow_forward: Starting " + self.bt["title"] + "!")

                self.indexEntry = 0
                self.player = await self.voice.create_ytdl_player(self.entries[self.indexEntry].getUrl(), after=self.nextSongAfter)
                self.player.start()
                self.playing = True
            else:
                await self.bot.say(":x: **Only the creator of the blindtest can start the test !**")

        else :
            await self.bot.say(":x: **You have to indicate you test id :** \n```$start [test id]```")

    @commands.command(no_pm=True, pass_context=True, description="Registrer yourself as a player")
    async def reg(self, context):
        """ Register the caller as a player """
        
        idPlayer = context.message.author.id 
        await self.pm.addPlayer(idPlayer)

    @commands.command(no_pm=True, pass_context=True, description="Unregister yourself as a player")
    async def unreg(self, context):
        """ Remove yourself from the player list """

        idPlayer = context.message.author.id
        await self.pm.removePlayer(idPlayer)

    @commands.command(no_pm=True, pass_context=True, description="Summon the bot in your voice channel")
    async def summon(self, context):
        """ Add the bot to your voice channel, you must call it before starting the game """
        summonedChannel = context.message.author.voice_channel

        if summonedChannel is None:
            await self.bot.say(":x: <@" + str(context.message.author.id + "> you are not in a voice channel !"))
            return
        
        if self.voice is None:
            self.voice = await self.bot.join_voice_channel(summonedChannel)
        else:
            await self.bot.move_to(summonedChannel)

    @commands.command(no_pm=True, description="Stop the bot")
    async def stop(self):
        """ Stop the blindtest and leave the voice channel """
        self.playing = False
        self.pm.clean()
        self.entries[:] = []

        await self.bot.say(":information_source: Stopping the blindtest")

        if self.player is not None:
            if self.player.is_playing() is True:
                self.player.stop()

        if self.voice is not None:
            if self.voice.is_connected() is True:
                await self.voice.disconnect()
        
        self.voice = None
        self.player = None

    @commands.group(no_pm=True, pass_context=True, description="Print players's score. No param = all scores")
    async def score(self, context, member: discord.Member = None):
        """ Print player's score. You have to mention him with @. No param = all scores"""
        await self.pm.scores(member)


    @commands.group(no_pm=True, pass_context=True, description="Answer")
    async def a(self, context, *, message: str):
        """ Give your answer for the current music played """

        idPlayer = context.message.author.id

        if self.playing == False:
            await self.bot.say(":speech_left: No blindtest currently playing")
            return

        if self.pm.isPlayer(context.message.author.id) is not True:
            await self.bot.say("<@" + str(idPlayer) + "> you have to register as a player first with `$reg` command !")
            return

        answer = message

        if answer is not None:
            if self.entries[self.indexEntry].isRight(answer) is True:
                await self.pm.addPoint(idPlayer)
                self.player.stop()

    @commands.command(no_pm=True, pass_context=True)
    async def givepoint(self, context, member: discord.Member = None, description="Give point to a player"):
        """ Give a point to a player. You have to mention him with a @ """

        if self.playing == False:
            await self.bot.say(":speech_left: No blindtest currently playing")
            return 

        authorId = context.message.author.id

        if member is None:
            await self.bot.say(":speech_left: Use the command as follow : `$givepoint @Member`")

        if context.message.author.id == self.bt["owner"]:
            if self.pm.isPlayer(member.id) is True:
                await self.pm.addPoint(member.id)
                self.player.stop()
            else:
                await self.bot.say(":speech_left: <@" + str(member.id) + "> is not a player !")
        else:
            await self.bot.say("<@" + str(authorId)+"> you are not the game master. Are you trying to cheat ? :rage:")

    async def done(self):
        await self.bot.send_message(self.channel, "Done !")
        await self.bot.send_message(self.channel, "The winner is :")
        winners = self.pm.getWinner()

        if winners is None:
            await self.bot.send_message(self.channel, "No winner !")
        else:
            for winner in winners:
                await self.bot.send_message(self.channel, "<@" + str(winner[0]) + "> with " + str(winner[1]) + " points ! :fireworks:")

        self.playing = False
        self.pm.clean()
        self.entries[:] = []

        if self.player is not None:
            if self.player.is_playing() is True:
               self.player.stop()

        if self.voice is not None:
            if self.voice.is_connected() is True:
                await self.voice.disconnect()
        
        self.voice = None
        self.player = None

    def nextSongAfter(self):
        coro = self.nextSong()
        fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

        try:
            fut.result(3)
        except Exception as e:
            logging.exception(e)

    async def nextSong(self):
        """ Function to pass to the next song """
        self.indexEntry += 1

        if self.indexEntry >= len(self.entries):
            await self.done()
        else:
            if self.voice is not None:
                await self.bot.send_message(self.channel, ":speech_left: Next song !")
                self.player = await self.voice.create_ytdl_player(self.entries[self.indexEntry].getUrl(), after=self.nextSongAfter)
                self.player.start()
            else:
                await self.bot.send_message(self.channel, ":x: **An error has occured, stopping the game**")
                await self.stop()

    async def cleanup():
        """ Don't forget to clean everything up """
        self.kh.cleanup() 

async def my_command_error(exception, context):
    command = context.invoked_with

    logging.debug("<" + command + ">")

    logging.debug(command == "givepoint")

    if command == "givepoint":
        await bot.send_message(context.message.channel, ":x: An error occured. You might have mentionned an unexisting or special user.")
    if command == "score":
        await bot.send_message(context.message.channel, ":x: An error occured. You might have mentionned an unexisting or special user.")
    else:
        await bot.send_message(context.message.channel, ":x: An error occurend. Unknown command : **" + command + "**")

atexit.register(BlindTest.cleanup)

bot = commands.Bot(command_prefix=commands.when_mentioned_or("$"), description="ENJOY SOME OF THE BEST BLINDTEST EVER")
bot.add_cog(BlindTest(bot))
bot.add_listener(my_command_error, "on_command_error")

bot.run("MzQzMjg5MTE4NjY0NTU2NTU3.DG7pcg.vEj-6cz5w6cQEmTOSbNIwJOYq9I")

@bot.event
async def on_ready():
    await bot.edit_profile(username="Koncerto")
    await bot.change_status(game=discord.Game(name="$help"))