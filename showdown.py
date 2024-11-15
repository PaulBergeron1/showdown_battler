import asyncio
import websockets
import json
import random
import aiohttp

SERVER_URI = "wss://sim3.psim.us/showdown/websocket"
LOGIN_URI = "https://play.pokemonshowdown.com/action.php"
USERNAME = "USERNAME"
PASSWORD = "PASSWORD"

class ShowdownBot:
    def __init__(self):
        self.websocket = None
        self.challstr = None
        self.battle_id = None
        self.in_battle = False  # Track if the bot is currently in a battle or searching
        self.moves = {}  # Store move data

    async def connect(self):
        """Connect to the Pokémon Showdown server."""
        self.websocket = await websockets.connect(SERVER_URI)
        print("Connected to server")

    async def login(self):
        """Log in to Pokémon Showdown using the challstr."""
        async for message in self.websocket:
            if "|challstr|" in message:
                # Extract challstr for login
                self.challstr = message.split("|")[2] + "|" + message.split("|")[3]
                print("Received challstr:", self.challstr)

                # Send login request to obtain assertion
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "act": "login",
                        "name": USERNAME,
                        "pass": PASSWORD,
                        "challstr": self.challstr
                    }
                    
                    async with session.post(LOGIN_URI, data=payload) as resp:
                        data = await resp.text()
                        login_response = json.loads(data[1:])  # Skip the leading ] when parsing json
                        print("Login response:", login_response)
                        if "assertion" in login_response:
                            assertion = login_response["assertion"]
                            # Send login command with assertion
                            await self.websocket.send(f"|/trn {USERNAME},0,{assertion}")
                            print("Sent login command with assertion")
                        else:
                            print("Login failed:", login_response)
                break

    async def fetch_move_data(self, move_name):
        """Fetch move data from the pokiapi"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://pokeapi.co/api/v2/move/{move_name.lower()}") as resp:
                if resp.status == 200:
                    move_data = await resp.json()
                    self.moves[move_name] = move_data
                    print(f"Fetched data for move: {move_name}")
                else:
                    print(f"Failed to fetch data for move: {move_name}")

    async def start_battle(self):
        """Start searching for a Gen 8 random battle"""
        if not self.in_battle:  # Only start a new search if not already in a battle or search
            self.in_battle = True  # Immediately set to True to prevent re-searches
            print("Searching for a Gen 8 random battle.")
            await self.websocket.send(f"|/utm null")
            await self.websocket.send(f"|/search gen8randombattle")

    def pick_safest_move(self, moves):
        """Select the safest move based on a simple heuristic"""
        move_index = random.choice(range(len(moves)))
        return move_index

    async def handle_battle_message(self, message):
        """Handle messages during the battle"""
        print(f"Received message: {message}")
        if "|request|" in message:
            # Handle incoming request to pick a move
            try:
                request_data = message.split("|request|")[1]
                request = json.loads(request_data)
                if "active" in request:
                    active_pokemon = request["active"]
                    if active_pokemon:
                        moves = active_pokemon[0].get("moves", [])
                        if moves:
                            move_index = self.pick_safest_move(moves)
                            if move_index is not None:
                                move_name = moves[move_index]["move"]
                                print(f"Choosing move: {move_name}")
                                print("HERE IS SUPER AMAZING BATTLE ID" + self.battle_id)
                                print(move_index+1)
                                asyncio.sleep(5)
                                print("sending move to server")
                                await self.websocket.send(f"{self.battle_id[1:]}|/choose move {move_index + 1}")
                            else:
                                print("No valid move found.")
                        else:
                            print("No available moves.")
                    else:
                        print("No active Pokémon.")
            except Exception as e:
                print(f"Error while handling battle message: {e}")
       


        elif "|win|" in message:
            print("Battle ended!")
            if f"|win|{USERNAME}" in message:
                print("Bot won the battle!")
            else:
                print("Bot lost the battle.")
            # Mark as not in battle and start a new search
            self.in_battle = False
            await self.start_battle()


    async def handle_messages(self):
        """Handle all messages received from the server"""
        async for message in self.websocket:
            print("Received:", message)
            
            if "|popup|Your team was rejected" in message:
                print("Error: Team was rejected. Check team compatibility.")
                return
            elif "|updateuser|" in message and f"|{USERNAME}|1|" in message:
                # Successfully logged in, send the team and start searching for a battle
                print("Login successful")
                #await self.send_team()  # Send the team to the server
                await self.start_battle()  # Start searching for a battle
            elif "|init|battle" in message:
                # Enter a new battle room
                self.battle_id = message.split("|")[0].rstrip()
                self.in_battle = True  # Mark as in battle
                print(f"Entered battle with ID {self.battle_id}")
                await self.websocket.send(f"{self.battle_id[1:]}|/timer on")
            elif self.battle_id and message.startswith(self.battle_id):
                # Handle messages within the battle room
                print("Handling battle messages")
                await self.handle_battle_message(message)
            elif "|updatesearch|" in message:
                # If search updates indicate no games found retry search if not in a battle
                if '"searching":[]' in message and not self.in_battle:
                    print("No games found, retrying search after a delay...")
                    await asyncio.sleep(5)  # Wait 5 seconds before retrying
                    await self.start_battle()  # Retry searching for a game

    async def run(self):
        """Run the bot by connecting, logging in, and handling messages"""
        await self.connect()
        await self.login()
        await self.handle_messages()

# Run the bot
bot = ShowdownBot()
asyncio.run(bot.run())
