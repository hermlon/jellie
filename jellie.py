import logging
import discord
import jellieconfig
import asyncio
import requests
from bs4 import BeautifulSoup
from datetime import datetime

class JellieClient(discord.Client):

    def handle_task_result(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logging.exception(task)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.current_locations = set()
        self.startup = True
        self.bg_task = self.loop.create_task(self.refresh_info())
        self.bg_task.add_done_callback(self.handle_task_result)

    async def on_ready(self):
        print('i\'m readyy')

    async def refresh_info(self):
        await self.wait_until_ready()
        while not self.is_closed():
            await self.get_new_data()
            self.startup = False
            await asyncio.sleep(jellieconfig.interval*60)

    async def notify(self, locations):
        if locations:
            message_str = '*neue Termine:*\n' + '\n'.join(locations)
            if self.startup:
                message_str = '*vielleicht nicht ganz so neue Termine:*\n' + '\n'.join(locations)

            # check if above character limit
            if len(message_str) >= 2000:
                message_str = message_str[:-1000] + '...\n*und mehr...*'

            for channel in jellieconfig.channels:
                c = self.get_channel(channel['channel_id'])
                if c:
                    print(message_str)
                    message = await c.send(message_str)
                    if channel['publish']:
                        try:
                            await message.publish()
                        except discord.errors.HTTPException:
                            # rate limit is 10 per hour
                            print("publishing message failed due to rate limit")


        # update bot status
        timestring = datetime.now().strftime("%a - %H:%M") 
        print("Last update: {}".format(timestring))
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="({})".format(timestring)))

    async def get_new_data(self):
        try:
            page = requests.get(jellieconfig.url)
            soup = BeautifulSoup(page.text, 'html.parser')

            options = soup.find(id='select-ort-pub').find_all('option')[1:]

            locations = set()
            for option in options:
                locations.add(option.string)
            await self.process_locations(locations)
        except requests.exceptions.ConnectionError as e:
            print("No internet connection")

    def matches_town(self, location):
        return any([loc in location for loc in jellieconfig.matches])

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


logging.basicConfig(level=logging.ERROR)

client = JellieClient()
client.run(jellieconfig.token)

