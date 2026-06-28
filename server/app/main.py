from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from .game.core import Game, Player, Card
import asyncio

app = FastAPI()
rooms = {}

@app.get("/")
async def root():
    return {"status": "ok"}

@app.websocket("/ws/{room_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    await websocket.accept()
    room = rooms.setdefault(room_id, {"sockets": {}, "game": None})
    room["sockets"][player_name] = websocket

    if room["game"] is None:
        p1 = Player(player_name, [Card(1,"A1",1,1,1), Card(2,"A2",2,2,2)])
        room["game"] = Game([p1])
        # start turn loop in background
        asyncio.create_task(room["game"].turn_manager.start())
    else:
        if not any(p.name == player_name for p in room["game"].players):
            room["game"].players.append(Player(player_name, [Card(3,"B1",1,1,1), Card(4,"B2",2,2,2)]))

    try:
        while True:
            data = await websocket.receive_text()
            if data.startswith("play:"):
                idx = int(data.split(":",1)[1])
                game = room["game"]
                player = next(p for p in game.players if p.name == player_name)
                if 0 <= idx < len(player.hand):
                    card = player.hand[idx]
                    game.queue.push(game.create_play_action(player, card))
            await asyncio.sleep(0)
    except WebSocketDisconnect:
        room["sockets"].pop(player_name, None)
