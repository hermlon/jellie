import discord
import jellieconfig
import asyncio
import requests
from bs4 import BeautifulSoup
from datetime import datetime

class JellieClient(discord.Client):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.current_locations = set()
        self.startup = True
        self.bg_task = self.loop.create_task(self.refresh_info())

    async def on_ready(self):
        print('i\'m readyy')

    async def refresh_info(self):
        await self.wait_until_ready()
        while not self.is_closed():
            await self.get_new_data()
            self.startup = False
            await asyncio.sleep(jellieconfig.interval*60)

    async def notify(self, locations):
        channel = self.get_channel(jellieconfig.channel_id)
        if locations:
            message = '@everyone neue Termine:\n' + '\n'.join(locations)
            if startup:
                message = 'vielleicht nicht ganz so neue Termine:\n' + '\n'.join(locations)
            await channel.send(message)
        # update bot status
        timestring = datetime.now().strftime("(%a - %H:%M)") 
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=timestring))

    async def get_new_data(self):
        page = requests.get(jellieconfig.url)
        soup = BeautifulSoup(page.text, 'html.parser')

        options = soup.find(id='select-ort-pub').find_all('option')[1:]

        locations = set()
        for option in options:
            locations.add(option.string)
        await self.process_locations(locations) 

    def matches_town(self, location):
        return jellieconfig.location in location

    async def process_locations(self, locations):
        new_loc = set()
        notify_loc = set()
        for loc in locations:
            if self.matches_town(loc):
                new_loc.add(loc)
                if loc not in self.current_locations:
                    notify_loc.add(loc)
        self.current_locations = new_loc
        await self.notify(notify_loc)


client = JellieClient()
client.run(jellieconfig.token)

