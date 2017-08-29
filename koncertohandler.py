import aiohttp
import asyncio
import async_timeout
import configparser
import json

class KoncertoHandler:

    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.config = configparser.ConfigParser()
        
        self.config.read("config.ini")

    async def fetch(self, url):
        """Get the source code of an url"""
        with async_timeout.timeout(10):
            async with self.session.get(url) as response:
                return await response.text(encoding="utf8")

    async def getList(self, tid):
        """ Fetch and load a blindtest from the website"""
        tjson = await self.fetch(self.config["koncerto"]["url"] + "/get.php?tid=" + str(tid))
        data = json.loads(tjson)
        
        return data
    
    async def cleanup(self):
        """ Clean everything that was left opened """
        self.session.close()

async def main():
    kh = KoncertoHandler()

    await kh.cleanup()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())