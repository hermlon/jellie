import logging
import discord
import jellieconfig
import asyncio
import requests
import time
import itertools
import operator
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
            data = self.api.get_pretty_new_data()
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
            message_str = 'Aktuell verfügbare Termine:\n'
        else:
            message_str = '**__Neue Termine__** *(für Booster nach Zweifach-Impfung), Auszug*\n'
        for location in data:
            message_str += '• {}\n'.format(location['location'])
            for date in location['dates']:
                message_str += '    - {}: '.format(date['date'])
                for time in date['times']:
                    message_str += ' `{}`'.format(time)
                message_str += '\n'

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

    def date_sort(date):
        return date[1][-10:]

    def get_pretty_new_data(self):
        diff = self.get_new_data()
        diff = sorted(diff, key=operator.itemgetter(0))
        result = []
        for location, entry3 in itertools.groupby(diff, operator.itemgetter(0)):
            res = {'location': location, 'dates': []}
            dates = sorted(entry3, key=Api.date_sort)
            for date, times in itertools.groupby(dates, operator.itemgetter(1)):
                d = {'date': date, 'times': []}
                times = sorted(times, key=operator.itemgetter(2))
                for time in times:
                    d['times'].append(time[2])
                res['dates'].append(d)
            result.append(res)
        return result


    def get_new_data(self):
        locations = filter(self.matches_town, self.get_locations())
        diff = set()
        new_cache = set()
        for location in locations:
            times = self.get_times(location['id'])
            for time in times:
                combined = (location['name'],) + time
                if combined[0] not in self.cache:
                    diff.add(combined)
                new_cache.add(combined[0])
        self.cache = new_cache
        return diff

    def get_times(self, location):
        try:
            payload = {'typ': '1', 'ort': location, 'pos': '0', 'tmstmp': self.get_time()}
            page = requests.post(jellieconfig.url, data=payload)
            soup = BeautifulSoup(page.text, 'html.parser')

            times = []

            for day in soup.find_all('optgroup'):
                for time in day.find_all('option'):
                    times.append((day['label'], time.text[-5:]))
            return times
        except requests.exceptions.ConnectionError as e:
            return None

        
    def get_locations(self):
        try:
            payload = {'typ': '3', 'indi': '35', 'aktiv': '1', 'tmstmp': self.get_time()}
            page = requests.post(jellieconfig.url, data=payload)
            soup = BeautifulSoup(page.text, 'html.parser')

            locations = []

            for loc in soup.find_all('option'):
                if loc['value'] != '0':
                    locations.append({'id': loc['value'], 'name': loc.text})
            return locations
        except requests.exceptions.ConnectionError as e:
            print(e)
            return []

    def matches_town(self, location):
        return any([loc in location['name'] for loc in jellieconfig.matches])

    def get_time(self):
        return int(time.time()*1000)



logging.basicConfig(level=logging.ERROR)

client = JellieClient()
client.run(jellieconfig.token)
