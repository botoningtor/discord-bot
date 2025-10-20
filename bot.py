import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
import yt_dlp

load_dotenv()

class Config:
    TOKEN = os.getenv("DISCORD_TOKEN")
    FFMPEG_PATH = os.getenv("FFMPEG_PATH", r"D:\project\discord python\ffmpeg\bin\ffmpeg.exe")
    PREFIX = os.getenv("BOT_PREFIX", "!")

class MusicPlayer:
    """Класс для управления музыкой на сервере"""
    def __init__(self):
        self.queue = []
        self.is_playing = False
        self.repeat = False
        self.current_track = None
        self.volume = 0.5

class YhawaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=Config.PREFIX, intents=intents)
        self.players = {}  # guild_id -> MusicPlayer
    
    def get_player(self, guild_id):
        """Получить плеер для сервера"""
        if guild_id not in self.players:
            self.players[guild_id] = MusicPlayer()
        return self.players[guild_id]

bot = YhawaBot()

# Проверка FFmpeg
if not os.path.exists(Config.FFMPEG_PATH):
    print("Bankai! FFmpeg не найден! Zangetsu не может проявиться!")
    exit(1)

os.environ["FFMPEG_BINARY"] = Config.FFMPEG_PATH

# Настройки yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 25M',
    'options': '-vn -bufsize 512k'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

@bot.command()
async def join(ctx):
    """Подключение к голосовому каналу"""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        if not voice or not voice.is_connected():
            await channel.connect()
            await ctx.send("⚔️ **Sankt Bogen!** Прибыл в ваш отряд, капитан!")
        else:
            await ctx.send("🚫 **Quincy!** Я уже на позиции!")
    else:
        await ctx.send("🚫 **Blut!** Вы должны быть в голосовом канале, как Quincy в Ванденрейхе!")

@bot.command()
async def play(ctx, *, query):
    """Добавление трека в очередь"""
    player = bot.get_player(ctx.guild.id)
    
    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
            
            bot.get_player(ctx.guild.id).queue.append((player.url, player.title))
            await ctx.send(f"🎯 **Heilig Bogen!** {player.title} заряжен в лук!")

            if not bot.get_player(ctx.guild.id).is_playing:
                await play_next(ctx)
        except Exception as e:
            await ctx.send(f"💥 **Heilig Pfeil!** Ошибка зарядки: {str(e)}")

async def play_next(ctx):
    """Воспроизведение следующего трека"""
    player = bot.get_player(ctx.guild.id)
    
    if player.repeat and player.current_track:
        player.queue.insert(0, player.current_track)
    
    if player.queue:
        player.is_playing = True
        player.current_track = player.queue.pop(0)
        url, title = player.current_track
        await play_audio(ctx, url, title)
    else:
        player.is_playing = False
        player.current_track = None
        voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        if voice:
            await ctx.send("🌀 **Zangetsu!** Музыка рассеялась...")
            await asyncio.sleep(60)
            if voice and not voice.is_playing() and not voice.is_paused():
                await voice.disconnect()
                await ctx.send("🌙 **Kojaku!** Zangetsu возвращается в сон...")

async def play_audio(ctx, url, title):
    """Воспроизведение аудио"""
    voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice or not voice.is_connected():
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
            voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        else:
            await ctx.send("🚫 **Shatter!** Зайдите в голосовой канал, шампуры!")
            return

    try:
        audio_source = discord.FFmpegPCMAudio(
            url,
            **ffmpeg_options,
            executable=Config.FFMPEG_PATH
        )
        
        def after_playback(error):
            if error:
                print(f"Ошибка воспроизведения: {error}")
            asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        
        voice.play(audio_source, after=after_playback)
        await ctx.send(f"🎵 **Ginrei Kojaku!** Исполняю: {title}")

    except Exception as e:
        await ctx.send(f"💫 **Hoffnung!** Духовная сила подвела: {str(e)}")
        await play_next(ctx)

@bot.command()
async def toggle_repeat(ctx):
    """Переключение режима повтора текущего трека"""
    player = bot.get_player(ctx.guild.id)
    player.repeat = not player.repeat
    state = "активирован" if player.repeat else "деактивирован"
    await ctx.send(f"🔁 **Bankai!** Режим вечного боя {state}!")

@bot.command()
async def leave(ctx):
    """Отключение от голосового канала"""
    player = bot.get_player(ctx.guild.id)
    voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice and voice.is_connected():
        player.queue.clear()
        player.is_playing = False
        player.current_track = None
        await voice.disconnect()
        await ctx.send("☄️ **Seele Schneider!** Quincy уходит с поля боя!")
    else:
        await ctx.send("🛡️ **Freund Schild!** Я уже в бездействии!")

@bot.command()
async def skip(ctx):
    """Пропуск текущего трека"""
    player = bot.get_player(ctx.guild.id)
    player.repeat = False
    voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice and voice.is_playing():
        voice.stop()
        await ctx.send("⚡ **Blitz Schnell!** Меняю духовную pressure!")
    else:
        await ctx.send("🌌 **Sprenger!** Нечего пропускать, капитан!")

@bot.command()
async def queue_list(ctx):
    """Показать текущую очередь"""
    player = bot.get_player(ctx.guild.id)
    if player.queue:
        queue_text = "\n".join([f"{i+1}. {title}" for i, (_, title) in enumerate(player.queue)])
        await ctx.send(f"📜 **Quincy Zeichen!** Очередь атак:\n{queue_text}")
    else:
        await ctx.send("🎯 **Letzt Stil!** Очередь пуста - все стрелы выпущены!")

@bot.command()
async def pause(ctx):
    """Пауза текущего трека"""
    voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice and voice.is_playing():
        voice.pause()
        await ctx.send("⏸️ **Blut Vene!** Защита активирована - музыка на паузе!")
    else:
        await ctx.send("🎭 **Shadow!** Нечего ставить на паузу!")

@bot.command()
async def resume(ctx):
    """Продолжить воспроизведение"""
    voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice and voice.is_paused():
        voice.resume()
        await ctx.send("▶️ **Blut Arterie!** Атака продолжается!")
    else:
        await ctx.send("🎵 **Vollständig!** Музыка уже звучит!")

@bot.command()
async def volume(ctx, volume: int = None):
    """Изменение громкости"""
    if volume is None:
        await ctx.send(f"🎚️ **Spiritual Pressure!** Текущая громкость: {int(bot.get_player(ctx.guild.id).volume * 100)}%")
        return
    
    if 0 <= volume <= 100:
        player = bot.get_player(ctx.guild.id)
        player.volume = volume / 100
        voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        if voice and voice.source:
            voice.source.volume = player.volume
        await ctx.send(f"🔊 **Reishi Control!** Громкость установлена на {volume}%")
    else:
        await ctx.send("🚫 **Limit Break!** Громкость должна быть от 0 до 100!")

@bot.command()
async def nowplaying(ctx):
    """Информация о текущем треке"""
    player = bot.get_player(ctx.guild.id)
    if player.current_track:
        url, title = player.current_track
        await ctx.send(f"🎶 **Current Battle:** {title}")
    else:
        await ctx.send("🌫️ **No Spiritual Pressure!** Сейчас ничего не играет")

@bot.event
async def on_ready():
    print(f'🎭 {bot.user} has manifested in Soul Society!')
    await bot.change_presence(activity=discord.Game(name="Bankai! | !help"))

@bot.event
async def on_command_error(ctx, error):
    """Обработка ошибок команд"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❓ **Unknown Kido!** Неизвестная команда, капитан!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚡ **Incomplete Incantation!** Пропущен обязательный аргумент!")
    else:
        await ctx.send(f"💥 **Spiritual Pressure Crash!** Произошла ошибка: {str(error)}")

if __name__ == "__main__":
    print("🎭 Activating Quincy powers...")
    bot.run(Config.TOKEN)
