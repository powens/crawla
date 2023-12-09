import datetime
import os
from dataclasses import dataclass

import aiohttp
import dateutil.parser
from bs4 import BeautifulSoup

BCP_BASE_URL = "https://lrs9glzzsf.execute-api.us-east-1.amazonaws.com/prod"
BCP_AUTH_CLIENT_ID = "6avfri6v9tgfe6fonujq07eu9c"
BCP_ACCESS_TOKEN = ""
BCP_ID_TOKEN = ""


def format_date_to_bcp(d: datetime.date) -> str:
    return d.strftime("%Y-%m-%d")


def convert_str_to_date(d_str: str) -> datetime.date:
    if type(d_str) is not str:
        return d_str
    try:
        return dateutil.parser.isoparse(d_str)
    except ValueError:
        return d_str


@dataclass
class ArmyList:
    name: str
    playerId: str
    event: str
    eventId: str
    list: str


def get_army_list_text_from_html(html) -> str:
    bs = BeautifulSoup(html.replace("<br>", "\n"), features="html.parser")
    army_list = bs.find(class_="list")
    return army_list.get_text()


class BcpCache:
    def __init__(self):
        self.access_token = None
        self.id_token = None

        self.cache = {}

        self.event_list = None
        self.event_list_time = None

        self.aio_session = aiohttp.ClientSession()

        # self.login_to_bcp(os.environ["BCP_USERNAME"], os.environ["BCP_PASSWORD"])

    # def login_to_bcp(self, username: str, password: str):
    #     print("Grabbing BCP auth token")
    #     url = "https://cognito-idp.us-east-1.amazonaws.com"
    #     payload = {
    #         "AuthFlow": "USER_PASSWORD_AUTH",
    #         "ClientId": BCP_AUTH_CLIENT_ID,
    #         "AuthParameters": {"USERNAME": username, "PASSWORD": password},
    #         "ClientMetadata": {},
    #     }
    #     headers = {
    #         "Content-Type": "application/x-amz-json-1.1",
    #         "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
    #     }
    #     response = requests.post(url, json=payload, headers=headers)
    #     body = response.json()
    #     auth_results = body["AuthenticationResult"]
    #     self.access_token = auth_results["AccessToken"]
    #     self.id_token = auth_results["IdToken"]

    # Fetch attributes
    # url = https://cognito-idp.us-east-1.amazonaws.com/

    async def fetch_from_bcp(self, url: str, force_refresh=False):
        # print("fetch", url)
        # if not self.access_token or force_refresh:
        # self.login_to_bcp(os.environ["BCP_USERNAME"], os.environ["BCP_PASSWORD"])

        url = f"{BCP_BASE_URL}/{url}"
        if url in self.cache:
            fetch_time, body = self.cache[url]
            now = datetime.datetime.now()
            time_diff = now - fetch_time
            if time_diff.total_seconds() <= 10 * 60:
                return body
            else:
                print("Cache expired")

        # headers = {"Authorization": self.id_token}
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
        }

        async with self.aio_session.get(url, headers=headers) as response:
            body = await response.json()
            if response.ok:
                now = datetime.datetime.now()
                self.cache[url] = (now, body)
            else:
                print("Response not okay", url, response.text)
                if "Army lists are only available to players" in body.get(
                    "errorMessage", ""
                ):
                    if force_refresh == False:
                        return await self.fetch_from_bcp(url, force_refresh=True)
                    else:
                        raise Exception("BCP Error: Unable to fetch url")
            return body

    async def fetch_event_metadata(self, event_id: str):
        return await self.fetch_from_bcp(
            f'events/{event_id}?inclPlayer=true&inclMetrics=true&userId={os.environ["BCP_USER_ID"]}'
        )

    async def fetch_players_from_event(self, event_id: str):
        players = await self.fetch_from_bcp(
            f"players?eventId={event_id}&inclEvent=false&inclMetrics=true&inclArmies=true&inclTeams=true&limit=1200&metrics=[%22resultRecord%22,%22record%22,%22numWins%22,%22battlePoints%22,%22WHArmyPoints%22,%22numWinsSoS%22,%22FFGBattlePointsSoS%22,%22mfSwissPoints%22,%22pathToVictory%22,%22mfStrengthOfSchedule%22,%22marginOfVictory%22,%22extendedNumWinsSoS%22,%22extendedFFGBattlePointsSoS%22,%22_id%22]"
        )
        has_pod = False
        for p in players:
            if "pod_record" in p and p["pod_record"]:
                has_pod = True
                break
        return players, has_pod

    async def fetch_list_for_player(self, army_list_id: str):
        response = await self.fetch_from_bcp(f"armylists/{army_list_id}?inclList=true")
        if "armyListHTML" not in response:
            print(f"armyListHTML not in army list response {army_list_id}")
            return None, None
        return get_army_list_text_from_html(response["armyListHTML"]), response

    async def fetch_event_list(
        self, start_date: datetime.date = None, end_date: datetime.date = None
    ):
        now = datetime.date.today()
        if not start_date:
            start_date = now - datetime.timedelta(days=182)
        if not end_date:
            end_date = now + datetime.timedelta(days=0)

        start_date = format_date_to_bcp(start_date)
        end_date = format_date_to_bcp(end_date)

        event_list = await self.fetch_from_bcp(
            f"eventlistings?startDate={start_date}&endDate={end_date}&gameType=1"
        )
        filter(lambda e: e.get("gameSystemName") == "Warhammer 40k", event_list)
        event_list.sort(key=lambda e: e["name"])

        # Clean up the event
        for e in event_list:
            e["eventDate"] = convert_str_to_date(e.get("eventDate"))
        self.event_list = event_list
        return event_list

    async def fetch_player_pairings(self, player_id: str):
        pairings = await self.fetch_from_bcp(f"pairings?playerId={player_id}")
        return pairings

    async def clear_cache(self):
        self.cache = {}
