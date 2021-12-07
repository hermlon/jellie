import logging
import discord
import jellieconfig
import asyncio
import requests
import time
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

        self.api = Api()
        self.startup = True
        self.bg_task = self.loop.create_task(self.refresh_info())
        self.bg_task.add_done_callback(self.handle_task_result)

    async def on_ready(self):
        print('i\'m readyy')

    async def refresh_info(self):
        await self.wait_until_ready()
        while not self.is_closed():
            data = self.api.get_new_data()
            if data:
                await self.notify(data)
                await self.update_status('New data')
            else:
                await self.update_status('No new data')
            self.startup = False
            await asyncio.sleep(jellieconfig.interval*60)

    async def notify(self, data):
        message_str = ''
        if self.startup:
            message_str = 'eventuell Termine verfügbar an folgenden Orten:\n'
        else:
            message_str = '**__eventuell neue Termine an folgenden Orten__** *(für Booster nach Zweifach-Impfung), Auszug*\n'
        for location in data:
            message_str += '• {}\n'.format(location)

        # check if above character limit
        if len(message_str) >= 2000:
            message_str = message_str[:-1000] + '...\n*und mehr...*'

        for channel in jellieconfig.channels:
            c = self.get_channel(channel['channel_id'])
            if c:
                print(message_str)
                try:
                    message = await c.send(message_str)
                    if channel['publish']:
                        try:
                            await message.publish()
                        except discord.errors.HTTPException:
                            # rate limit is 10 per hour
                            print("publishing message failed due to rate limit")
                except discord.errors.Forbidden:
                    print("sending message failed for channel {}. Missing permissions?".format(str(c)))
                
    async def update_status(self, message):
        # update bot status
        timestring = datetime.now().strftime("%a - %H:%M") 
        print("{}: {}".format(message, timestring))
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="({})".format(timestring)))
    
class Api:

    def __init__(self):
        self.cache = set()

    def get_new_data(self):
        locations = filter(self.matches_town, self.get_locations())
        diff = set()
        for location in locations:
            if location not in self.cache:
                diff.add(location)
        self.cache = locations
        return diff

    def get_locations(self):
        try:
            payload = {'typ': '3', 'indi': '35', 'aktiv': '1', 'tmstmp': self.get_time()}
            page = requests.post(jellieconfig.url, data=payload)
            soup = BeautifulSoup(page.text, 'html.parser')

            locations = []

            for loc in soup.find_all('option'):
                if loc['value'] != '0':
                    locations.append(loc.text)
            return locations
        except requests.exceptions.ConnectionError as e:
            print(e)
            return []

    def matches_town(self, location):
        return any([loc in location for loc in jellieconfig.matches])

    def get_time(self):
        return int(time.time()*1000)



logging.basicConfig(level=logging.ERROR)

client = JellieClient()
client.run(jellieconfig.token)
