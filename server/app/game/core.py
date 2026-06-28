import asyncio
from collections import deque

class EventBus:
    def __init__(self):
        self.handlers = {}
    def on(self, typ, handler):
        self.handlers.setdefault(typ, []).append(handler)
    def emit(self, typ, payload):
        for h in list(self.handlers.get(typ, [])):
            try:
                h(payload)
            except Exception as e:
                print("Event handler error:", e)

class Action:
    def __init__(self, game, desc=""):
        self.game = game
        self.desc = desc
    async def resolve(self):
        pass

class ActionQueue:
    def __init__(self):
        self.queue = deque()
        self.processing = False
    def push(self, action):
        self.queue.append(action)
        asyncio.create_task(self._process())
    def push_priority(self, action):
        self.queue.appendleft(action)
        asyncio.create_task(self._process())
    async def _process(self):
        if self.processing: return
        self.processing = True
        while self.queue:
            a = self.queue.popleft()
            try:
                await a.resolve()
            except Exception as e:
                print("Action error:", e)
        self.processing = False
    def is_empty(self):
        return (not self.processing) and (len(self.queue) == 0)

class Card:
    def __init__(self, id, name, cost, attack=0, health=0):
        self.id = id; self.name = name; self.cost = cost
        self.attack = attack; self.health = health
        self.summoned_this_turn = False

class Player:
    def __init__(self, name, deck):
        self.name = name
        self.deck = deck[:]  # list of Card
        self.hand = []
        self.board = []
        self.life = 30
        self.max_mana = 0
        self.current_mana = 0
        self.fatigue = 0

class DrawAction(Action):
    def __init__(self, game, player, count=1):
        super().__init__(game, f"Draw {count}")
        self.player = player; self.count = count
    async def resolve(self):
        for _ in range(self.count):
            if not self.player.deck:
                self.player.fatigue += 1
                dmg = self.player.fatigue
                self.player.life -= dmg
                self.game.event_bus.emit("fatigue", {"player":self.player, "damage":dmg})
                if self.player.life <= 0:
                    self.game.event_bus.emit("playerDefeated", {"player":self.player})
                break
            card = self.player.deck.pop(0)
            self.player.hand.append(card)
            self.game.event_bus.emit("cardDrawn", {"player":self.player, "card":card})
            await asyncio.sleep(0)

class PlayCardAction(Action):
    def __init__(self, game, player, card):
        super().__init__(game, f"Play {card.name}")
        self.player = player; self.card = card
    async def resolve(self):
        if self.player.current_mana < self.card.cost:
            self.game.event_bus.emit("playFailed", {"player":self.player, "card":self.card, "reason":"no_mana"})
            return
        self.player.current_mana -= self.card.cost
        if self.card in self.player.hand:
            self.player.hand.remove(self.card)
        self.card.summoned_this_turn = True
        self.player.board.append(self.card)
        self.game.event_bus.emit("cardPlayed", {"player":self.player, "card":self.card})
        await asyncio.sleep(0)

class AttackAction(Action):
    def __init__(self, game, attacker_player, attacker_card, target_player, target_card=None):
        super().__init__(game, f"Attack {attacker_card.name}")
        self.attacker_player = attacker_player
        self.attacker_card = attacker_card
        self.target_player = target_player
        self.target_card = target_card
    async def resolve(self):
        if self.attacker_card.summoned_this_turn:
            self.game.event_bus.emit("attackFailed", {"reason":"summoning_sickness", "card":self.attacker_card})
            return
        if self.target_card:
            self.target_card.health -= self.attacker_card.attack
            self.attacker_card.health -= self.target_card.attack
            self.game.event_bus.emit("minionDamage", {"attacker":self.attacker_card, "defender":self.target_card})
            if self.target_card.health <= 0:
                self._remove_card(self.target_player, self.target_card)
                self.game.event_bus.emit("minionDied", {"player":self.target_player, "card":self.target_card})
            if self.attacker_card.health <= 0:
                self._remove_card(self.attacker_player, self.attacker_card)
                self.game.event_bus.emit("minionDied", {"player":self.attacker_player, "card":self.attacker_card})
        else:
            self.target_player.life -= self.attacker_card.attack
            self.game.event_bus.emit("playerDamaged", {"player":self.target_player, "damage":self.attacker_card.attack})
            if self.target_player.life <= 0:
                self.game.event_bus.emit("playerDefeated", {"player":self.target_player})
        await asyncio.sleep(0)
    def _remove_card(self, player, card):
        if card in player.board:
            player.board.remove(card)

class Game:
    def __init__(self, players):
        self.players = players
        self.current_index = 0
        self.event_bus = EventBus()
        self.queue = ActionQueue()
        self.turn_manager = TurnManager(self)
    @property
    def current_player(self):
        return self.players[self.current_index]
    def next_player(self):
        self.current_index = (self.current_index + 1) % len(self.players)

    def create_play_action(self, player, card):
        return PlayCardAction(self, player, card)

class TurnManager:
    def __init__(self, game):
        self.game = game
        self.running = False
        self.max_mana_cap = 10
    async def start(self):
        if self.running: return
        self.running = True
        while self.running:
            await self.run_turn()
            self.game.next_player()
    async def run_turn(self):
        p = self.game.current_player
        self.game.event_bus.emit("turnStart", {"player":p})
        self.game.event_bus.emit("turnStartTriggers", {"player":p})
        await self._wait_queue_empty()
        self.game.queue.push(DrawAction(self.game, p, 1))
        await self._wait_queue_empty()
        p.max_mana = min(self.max_mana_cap, p.max_mana + 1)
        p.current_mana = p.max_mana
        self.game.event_bus.emit("manaUpdated", {"player":p})
        for c in p.board: c.summoned_this_turn = False
        await self._wait_queue_empty()
        self.game.event_bus.emit("turnEndTriggers", {"player":p})
        await self._wait_queue_empty()
        self.game.event_bus.emit("turnEnd", {"player":p})
    async def _wait_queue_empty(self):
        while not self.game.queue.is_empty():
            await asyncio.sleep(0.01)
