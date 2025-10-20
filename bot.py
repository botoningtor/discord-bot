import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
import yt_dlp

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

FFMPEG_PATH = r"D:\project\discord python\ffmpeg\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG_PATH):
    print("Ошибка: ffmpeg не найден!")
    exit(1)

os.environ["FFMPEG_BINARY"] = FFMPEG_PATH

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

queue = []
is_playing = False
repeat = False
current_track = None

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
            # Если это плейлист, берем первый трек
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

async def get_youtube_info(url):
    """Асинхронное получение информации о YouTube видео"""
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        
        if 'entries' in data:
            data = data['entries'][0]
            
        return data['url'], data['title']
    except Exception as e:
        raise Exception(f"Ошибка загрузки видео: {str(e)}")

@bot.command()
async def join(ctx):
    """Подключение к голосовому каналу"""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        if not voice or not voice.is_connected():
            await channel.connect()
            await ctx.send(f"Sankt Bogen")
    else:
        await ctx.send("Вы должны быть квинси")

@bot.command()
async def play(ctx, *, query):
    """Добавление трека в очередь"""
    global is_playing, current_track
    
    async with ctx.typing():
        try:
            # Используем yt-dlp для получения аудио
            player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
            
            queue.append((player.url, player.title))
            await ctx.send(f"Heilig Bogen: {player.title}")

            if not is_playing:
                await play_next(ctx)
        except Exception as e:
            await ctx.send(f"Heilig Pfeil: {str(e)}")

async def play_next(ctx):
    """Воспроизведение следующего трека"""
    global is_playing, current_track, repeat
    
    if repeat and current_track:
        queue.insert(0, current_track)
    
    if queue:
        is_playing = True
        current_track = queue.pop(0)
        url, title = current_track
        await play_audio(ctx, url, title)
    else:
        is_playing = False
        current_track = None
        voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        if voice:
            await ctx.send("魂を切り裂くもの")
            await asyncio.sleep(60)
            if voice and not voice.is_playing() and not voice.is_paused():
                await voice.disconnect()
                await ctx.send("Kojaku")

async def play_audio(ctx, url, title):
    """Воспроизведение аудио"""
    voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice or not voice.is_connected():
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
            voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        else:
            await ctx.send("Зайдите в голосовой канал")
            return

    try:
        # Создаем аудио источник с правильными настройками
        audio_source = discord.FFmpegPCMAudio(
            url,
            **ffmpeg_options,
            executable=FFMPEG_PATH
        )
        
        def after_playback(error):
            if error:
                print(f"Ошибка воспроизведения: {error}")
            asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        
        voice.play(audio_source, after=after_playback)
        await ctx.send(f"Ginrei Kojaku: {title}")

    except Exception as e:
        await ctx.send(f"Hoffnung: {str(e)}")
        # Пытаемся воспроизвести следующий трек при ошибке
        await play_next(ctx)

@bot.command()
async def toggle_repeat(ctx):
    """Переключение режима повтора текущего трека"""
    global repeat
    repeat = not repeat
    state = "включен" if repeat else "выключен"
    await ctx.send(f"Режим повтора {state}")

@bot.command()
async def leave(ctx):
    """Отключение от голосового канала"""
    global queue, is_playing, current_track
    voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice and voice.is_connected():
        queue.clear()
        is_playing = False
        current_track = None
        await voice.disconnect()
        await ctx.send("Выхожу")
    else:
        await ctx.send("Freund Schild")

@bot.command()
async def skip(ctx):
    """Пропуск текущего трека"""
    global repeat
    repeat = False
    voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice and voice.is_playing():
        voice.stop()
        await ctx.send("Ставлю другую")
    else:
        await ctx.send("Музыки нету")

@bot.command()
async def queue_list(ctx):
    """Показать текущую очередь"""
    if queue:
        queue_text = "\n".join([f"{i+1}. {title}" for i, (_, title) in enumerate(queue)])
        await ctx.send(f"Очередь:\n{queue_text}")
    else:
        await ctx.send("Очередь пуста")

@bot.command()
async def pause(ctx):
    """Пауза текущего трека"""
    voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice and voice.is_playing():
        voice.pause()
        await ctx.send("Пауза ⏸️")
    else:
        await ctx.send("Нечего ставить на паузу")

@bot.command()
async def resume(ctx):
    """Продолжить воспроизведение"""
    voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice and voice.is_paused():
        voice.resume()
        await ctx.send("Продолжаем ▶️")
    else:
        await ctx.send("Не на паузе")

@bot.event
async def on_command_error(ctx, error):
    """Обработка ошибок команд"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Неизвестная команда")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Пропущен обязательный аргумент")
    else:
        await ctx.send(f"Произошла ошибка: {str(error)}")

if __name__ == "__main__":
    bot.run(TOKEN)