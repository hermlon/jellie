import discord
import jellieconfig

class JellieClient(discord.Client):
    async def on_ready(self):
        print('i\'m readyy')

client = JellieClient()
client.run(jellieconfig.token)
