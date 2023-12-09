import asyncio
import bcp
import csv
import time

bcp = bcp.BcpCache()

fieldnames = [
    "event_id",
    "event_name",
    "num_rounds",
    "player_id",
    "player_name",
    "army_name",
    "num_wins",
    "num_losses",
    "num_ties",
]


def record_from_result_record(result_record):
    wins = 0
    losses = 0
    ties = 0
    for rr in result_record:
        if rr == 0:
            losses += 1
        elif rr == 1:
            ties += 1
        elif rr == 2:
            wins += 1

    return wins, losses, ties


async def get_event_list():
    return await bcp.fetch_event_list()


def is_desired_event(e):
    num_rounds = e.get("numberOfRounds", -1)
    num_players = e.get("totalPlayers", -1)
    if num_rounds is None:
        return False
    if num_players is None:
        return False
    return (num_rounds >= 5) and (num_players >= 25)


async def main():
    with open("out.csv", "w") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        events = await get_event_list()
        total_events = len(events)
        print(f"Got {total_events} events")
        i = 0
        for e in events:
            event_id = e.get("eventObjId")
            i += 1
            if not event_id:
                continue
            if not is_desired_event(e):
                # print(f"Skipping {event_id}")
                continue
            print(f"[{i}/{total_events}] Fetching {event_id} - {e.get('name')}")

            players, _ = await bcp.fetch_players_from_event(event_id)
            for p in players:
                player_name = (
                    f'{p.get("firstName", "")} {p.get("lastName", "")}'.strip()
                )
                wins, losses, ties = record_from_result_record(
                    p.get("resultRecord", [])
                )
                writer.writerow(
                    {
                        "event_id": event_id,
                        "event_name": e.get("name", "").strip(),
                        "num_rounds": e.get("numberOfRounds", ""),
                        "player_id": p.get("userId", ""),
                        "army_name": p.get("army", {}).get("name", ""),
                        "player_name": player_name,
                        "num_wins": wins,
                        "num_losses": losses,
                        "num_ties": ties,
                    }
                )

            time.sleep(5)


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
