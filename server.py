import asyncio
import json
import os
from http import HTTPStatus
import websockets

# Store rooms: { "room_code": { "password": "...", "clients": { ws: username }, "op": ws, "game": {...} } }
rooms = {}
all_connections = set()

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexus Chat & Arcade</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; }
        body { background-color: #1e1f22; color: #dbdee1; display: flex; min-height: 100vh; justify-content: center; align-items: center; padding: 10px; }
        
        .login-wrapper { display: flex; gap: 20px; align-items: stretch; flex-wrap: wrap; justify-content: center; }
        .card { background: #2b2d31; padding: 25px; border-radius: 12px; width: 380px; max-width: 95vw; box-shadow: 0 8px 24px rgba(0,0,0,0.3); display: flex; flex-direction: column; }
        h2 { color: #fff; margin-bottom: 15px; text-align: center; }
        label { font-size: 11px; font-weight: bold; color: #b5bac1; display: block; margin-top: 10px; }
        input { width: 100%; padding: 10px; margin-top: 5px; background: #111214; border: none; border-radius: 6px; color: #fff; font-size: 14px; }
        button { width: 100%; padding: 12px; background: #5865f2; color: white; border: none; border-radius: 6px; font-weight: bold; margin-top: 15px; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #4752c4; }

        .rooms-list { flex: 1; overflow-y: auto; max-height: 220px; display: flex; flex-direction: column; gap: 8px; }
        .room-item { background: #1e1f22; padding: 10px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; border: 1px solid transparent; transition: 0.15s; }
        .room-item:hover { border-color: #5865f2; background: #232428; }
        .room-name { font-weight: bold; color: #fff; font-size: 14px; }
        .room-meta { font-size: 12px; color: #949ba4; }
        .empty-rooms { color: #949ba4; font-size: 13px; text-align: center; margin-top: 30px; }
        
        #chat-screen { display: none; width: 95vw; height: 92vh; max-width: 1300px; max-height: 800px; flex-direction: row; border-radius: 12px; overflow: hidden; background: #313338; box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
        
        /* Left Pane: Game Arena */
        .game-arena { width: 0px; background: #2b2d31; border-right: 1px solid #1f2023; display: flex; flex-direction: column; align-items: center; justify-content: center; transition: width 0.3s ease; overflow: hidden; padding: 0; }
        .game-arena.active { width: 340px; padding: 12px; }
        .game-title { color: #fff; margin-bottom: 8px; font-size: 16px; font-weight: bold; }
        
        /* Tic Tac Toe Grid */
        .ttt-board { display: none; grid-template-columns: repeat(3, 80px); grid-template-rows: repeat(3, 80px); gap: 6px; background: #1e1f22; padding: 8px; border-radius: 8px; }
        .ttt-cell { background: #313338; border: none; border-radius: 6px; font-size: 32px; font-weight: bold; color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 0.15s; }
        .ttt-cell:hover { background: #383a40; }

        /* Connect Four Grid */
        .c4-board { display: none; grid-template-columns: repeat(7, 36px); grid-template-rows: repeat(6, 36px); gap: 4px; background: #1e1f22; padding: 6px; border-radius: 8px; }
        .c4-cell { width: 36px; height: 36px; background: #313338; border: none; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 0.15s; overflow: hidden; position: relative; }
        .c4-cell:hover { background: #383a40; }
        .c4-piece { width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 10px; color: white; }

        .game-status { margin-top: 8px; font-size: 12px; color: #b5bac1; text-align: center; }

        .main-chat { flex: 1; display: flex; flex-direction: column; min-width: 250px; }
        .chat-header { padding: 12px 15px; background: #313338; border-bottom: 1px solid #1f2023; font-weight: bold; color: #fff; display: flex; justify-content: space-between; align-items: center; }
        .messages { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        .message { background: #2b2d31; padding: 10px 14px; border-radius: 8px; max-width: 80%; word-break: break-word; }
        .message.me { background: #5865f2; align-self: flex-end; }
        .message.system { background: #232428; color: #949ba4; align-self: center; font-size: 13px; text-align: center; max-width: 90%; }
        
        .join-game-btn { background: #248046; color: white; border: none; padding: 6px 14px; border-radius: 6px; font-weight: bold; margin-top: 8px; cursor: pointer; display: inline-block; }
        .join-game-btn:hover { background: #1a6335; }
        
        .typing-indicator { height: 20px; padding: 0 15px; font-size: 11px; font-style: italic; color: #b5bac1; display: flex; align-items: center; }
        
        .message-input-area { padding: 10px 15px; display: flex; gap: 8px; background: #313338; }
        .message-input-area input { margin-top: 0; background: #383A40; flex: 1; }
        
        .sidebar { width: 220px; background: #2b2d31; padding: 15px; border-left: 1px solid #1f2023; display: flex; flex-direction: column; gap: 12px; }
        .sidebar h3 { font-size: 11px; color: #949ba4; margin-bottom: 4px; }
        .user-item { padding: 4px 0; color: #dbdee1; font-size: 13px; display: flex; justify-content: space-between; align-items: center; }
        .kick-btn { background: #da373c; color: white; border: none; padding: 2px 5px; border-radius: 4px; font-size: 10px; cursor: pointer; display: none; }
        .kick-btn:hover { background: #a12828; }
        
        .game-panel { background: #1e1f22; padding: 10px; border-radius: 8px; margin-top: auto; }
        .game-select { width: 100%; padding: 6px; background: #383A40; border: none; border-radius: 6px; color: #fff; font-size: 12px; margin-top: 4px; }
        .game-btn { background: #248046; margin-top: 6px; padding: 6px; font-size: 12px; }
        .game-btn:hover { background: #1a6335; }
        .close-game-btn { background: #da373c; margin-top: 6px; padding: 6px; font-size: 12px; display: none; }
        .close-game-btn:hover { background: #a12828; }

        .leave-btn { background: #da373c; padding: 5px 10px; width: auto; margin-top: 0; font-size: 12px; }
        .leave-btn:hover { background: #a12828; }

        @media (max-width: 768px) {
            body { align-items: flex-start; padding: 5px; }
            .login-wrapper { flex-direction: column; align-items: center; gap: 10px; width: 100%; }
            .card { width: 100%; max-width: 100%; padding: 15px; }
            #chat-screen { flex-direction: column; height: 96vh; width: 98vw; }
            .sidebar { width: 100%; flex-direction: row; flex-wrap: wrap; justify-content: space-between; padding: 8px 12px; gap: 6px; max-height: 110px; overflow-y: auto; }
            .sidebar > div { flex: 1; min-width: 120px; }
            .game-panel { margin-top: 0; min-width: 140px; }
            .game-arena.active { width: 100%; max-height: 240px; padding: 8px; }
            .c4-board { transform: scale(0.85); transform-origin: top center; margin-bottom: -15px; }
        }
    </style>
</head>
<body>

    <div id="login-screen" class="login-wrapper">
        <div class="card">
            <h2>Nexus Chat</h2>
            <label>USERNAME</label>
            <input type="text" id="username" placeholder="Your name">
            <label>ROOM CODE</label>
            <input type="text" id="room" placeholder="e.g. general">
            <label>ROOM PASSWORD (OPTIONAL)</label>
            <input type="password" id="password" placeholder="••••••••">
            <button onclick="joinRoom()">Join / Create Room</button>
        </div>

        <div class="card">
            <h2>Active Rooms</h2>
            <div id="active-rooms-list" class="rooms-list">
                <div class="empty-rooms">No active rooms right now.<br>Create one on the left!</div>
            </div>
        </div>
    </div>

    <div id="chat-screen">
        <!-- Left Pane: Game Arena -->
        <div class="game-arena" id="game-arena">
            <div class="game-title" id="game-arena-title">Arcade Game</div>
            
            <!-- Tic-Tac-Toe Board -->
            <div class="ttt-board" id="ttt-board">
                <button class="ttt-cell" onclick="makeMove(0)"></button>
                <button class="ttt-cell" onclick="makeMove(1)"></button>
                <button class="ttt-cell" onclick="makeMove(2)"></button>
                <button class="ttt-cell" onclick="makeMove(3)"></button>
                <button class="ttt-cell" onclick="makeMove(4)"></button>
                <button class="ttt-cell" onclick="makeMove(5)"></button>
                <button class="ttt-cell" onclick="makeMove(6)"></button>
                <button class="ttt-cell" onclick="makeMove(7)"></button>
                <button class="ttt-cell" onclick="makeMove(8)"></button>
            </div>

            <!-- Connect Four Board -->
            <div class="c4-board" id="c4-board"></div>

            <div class="game-status" id="game-status">Game starting...</div>
            <button class="game-btn" onclick="resetGame()" style="margin-top: 6px; width: auto; padding: 4px 10px;">Reset Board</button>
        </div>

        <div class="main-chat">
            <div class="chat-header">
                <span id="room-title"># room</span>
                <button class="leave-btn" onclick="location.reload()">Leave</button>
            </div>
            <div class="messages" id="messages"></div>
            <div class="typing-indicator" id="typing-indicator"></div>
            <div class="message-input-area">
                <input type="text" id="msg-input" placeholder="Type a message..." oninput="handleTyping()" onkeypress="handleKey(event)">
                <button style="width: 80px; margin-top:0;" onclick="sendMessage()">Send</button>
            </div>
        </div>
        
        <div class="sidebar">
            <div style="flex: 1;">
                <h3>ONLINE MEMBERS</h3>
                <div id="user-list"></div>
            </div>
            <div class="game-panel" id="game-panel" style="display:none;">
                <h3>ARCADE</h3>
                <div id="op-controls" style="display:none;">
                    <select id="game-select" class="game-select">
                        <option value="tictactoe">Tic-Tac-Toe</option>
                        <option value="connectfour">Connect Four</option>
                    </select>
                    <button class="game-btn" onclick="launchGame()">Launch Game</button>
                </div>
                <button class="close-game-btn" id="close-game-btn" onclick="closeGame()">Close Game</button>
                <div id="player-waiting" style="font-size: 10px; color: #949ba4; margin-top: 3px;">Waiting for Op.</div>
            </div>
        </div>
    </div>

    <script>
        let ws;
        let username;
        let isOp = false;
        let typingTimeout;
        let isTyping = false;
        let typingUsers = new Set();
        
        let gameState = {
            game_type: "tictactoe",
            active: false,
            board: [],
            turn: "X",
            winner: null,
            players: { X: null, O: null }
        };

        // Initialize Connect Four board DOM elements (42 cells: 7 cols x 6 rows)
        const c4BoardEl = document.getElementById("c4-board");
        for (let i = 0; i < 42; i++) {
            const cell = document.createElement("button");
            cell.className = "c4-cell";
            cell.onclick = () => makeMove(i);
            c4BoardEl.appendChild(cell);
        }

        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            ws = new WebSocket(protocol + window.location.host);

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                
                if (data.status === "error") {
                    alert(data.message);
                    return;
                }

                if (data.status === "kicked") {
                    alert("You have been kicked from the room by the operator.");
                    location.reload();
                    return;
                }

                if (data.status === "joined") {
                    document.getElementById("login-screen").style.display = "none";
                    document.getElementById("chat-screen").style.display = "flex";
                    document.getElementById("room-title").innerText = "# " + data.room;
                    isOp = data.is_op;
                    
                    document.getElementById("game-panel").style.display = "block";
                    if (isOp) {
                        document.getElementById("op-controls").style.display = "block";
                        document.getElementById("player-waiting").style.display = "none";
                    }
                }

                if (data.type === "room_list") {
                    renderActiveRooms(data.rooms);
                }

                if (data.type === "message") {
                    const msgBox = document.getElementById("messages");
                    const div = document.createElement("div");
                    
                    if (data.sender === "System") {
                        div.className = "message system";
                        div.innerHTML = data.text;
                    } else {
                        div.className = "message" + (data.sender === username ? " me" : "");
                        div.innerHTML = `<strong>${data.sender}:</strong> ${data.text}`;
                    }
                    
                    msgBox.appendChild(div);
                    msgBox.scrollTop = msgBox.scrollHeight;
                }

                if (data.type === "user_list") {
                    const userList = document.getElementById("user-list");
                    userList.innerHTML = "";
                    data.users.forEach(u => {
                        const uDiv = document.createElement("div");
                        uDiv.className = "user-item";
                        
                        const crown = u.is_op ? " 👑" : "";
                        uDiv.innerHTML = `<span>🟢 ${u.name}${crown}</span>`;

                        if (isOp && u.name !== username) {
                            const kickBtn = document.createElement("button");
                            kickBtn.className = "kick-btn";
                            kickBtn.innerText = "Kick";
                            kickBtn.onclick = () => kickUser(u.name);
                            uDiv.appendChild(kickBtn);
                        }
                        userList.appendChild(uDiv);
                    });
                }

                if (data.type === "game_launch") {
                    if (isOp) {
                        document.getElementById("close-game-btn").style.display = "block";
                    }
                }

                if (data.type === "game_state") {
                    gameState = data;
                    if (gameState.active) {
                        document.getElementById("game-arena").classList.add("active");
                        if (gameState.game_type === "tictactoe") {
                            document.getElementById("game-arena-title").innerText = "Tic-Tac-Toe";
                            document.getElementById("ttt-board").style.display = "grid";
                            document.getElementById("c4-board").style.display = "none";
                        } else {
                            document.getElementById("game-arena-title").innerText = "Connect Four";
                            document.getElementById("ttt-board").style.display = "none";
                            document.getElementById("c4-board").style.display = "grid";
                        }
                    } else {
                        document.getElementById("game-arena").classList.remove("active");
                    }
                    updateGameUI();
                }

                if (data.type === "typing") {
                    if (data.is_typing) {
                        typingUsers.add(data.sender);
                    } else {
                        typingUsers.delete(data.sender);
                    }
                    updateTypingUI();
                }
            };

            ws.onclose = function() {
                setTimeout(connectWebSocket, 2000);
            };
        }

        function renderActiveRooms(roomList) {
            const container = document.getElementById("active-rooms-list");
            if (!roomList || roomList.length === 0) {
                container.innerHTML = '<div class="empty-rooms">No active rooms right now.<br>Create one on the left!</div>';
                return;
            }
            container.innerHTML = "";
            roomList.forEach(r => {
                const div = document.createElement("div");
                div.className = "room-item";
                div.onclick = () => {
                    document.getElementById("room").value = r.name;
                    document.getElementById("username").focus();
                };
                const lockIcon = r.locked ? "🔒 " : "";
                div.innerHTML = `
                    <span class="room-name">${lockIcon}# ${r.name}</span>
                    <span class="room-meta">${r.count} online</span>
                `;
                container.appendChild(div);
            });
        }

        function joinRoom() {
            username = document.getElementById("username").value.trim();
            const room = document.getElementById("room").value.trim().toLowerCase();
            const password = document.getElementById("password").value.trim();

            if (!username || !room) {
                alert("Username and Room Code are required!");
                return;
            }

            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: "join", room: room, password: password, sender: username }));
            }
        }

        function kickUser(targetName) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: "kick", target: targetName }));
            }
        }

        function launchGame() {
            const gameType = document.getElementById("game-select").value;
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: "launch_game", game: gameType }));
            }
        }

        function closeGame() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: "close_game" }));
            }
        }

        function joinGameAction() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: "join_game" }));
            }
        }

        function makeMove(index) {
            if (!gameState.active || gameState.winner) return;
            
            let moveIndex = index;
            if (gameState.game_type === "connectfour") {
                moveIndex = index % 7;
            }
            
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: "game_move", index: moveIndex }));
            }
        }

        function resetGame() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: "game_reset" }));
            }
        }

        function updateGameUI() {
            if (gameState.game_type === "tictactoe") {
                const cells = document.getElementsByClassName("ttt-cell");
                for (let i = 0; i < cells.length; i++) {
                    cells[i].innerText = gameState.board[i] || "";
                    cells[i].style.color = gameState.board[i] === "X" ? "#5865f2" : "#ed4245";
                }
            } else if (gameState.game_type === "connectfour") {
                const cells = document.getElementsByClassName("c4-cell");
                for (let i = 0; i < cells.length; i++) {
                    cells[i].innerHTML = "";
                    const val = gameState.board[i];
                    if (val) {
                        const piece = document.createElement("div");
                        piece.className = "c4-piece";
                        piece.style.backgroundColor = val === "X" ? "#5865f2" : "#ed4245";
                        piece.innerText = val;
                        cells[i].appendChild(piece);
                    }
                }
            }

            const status = document.getElementById("game-status");
            let roleText = "";
            if (gameState.players.X === username) roleText = " (You are X)";
            else if (gameState.players.O === username) roleText = " (You are O)";
            else roleText = " (Spectating)";

            if (gameState.winner) {
                if (gameState.winner === "Tie") {
                    status.innerText = `It's a Tie! 🤝`;
                } else {
                    const winnerName = gameState.players[gameState.winner];
                    status.innerText = `Winner: ${winnerName} (${gameState.winner})! 🎉`;
                }
            } else {
                status.innerText = `Turn: ${gameState.turn} (${gameState.players[gameState.turn] || 'Waiting...'})${roleText}`;
            }
        }

        function handleTyping() {
            if (!ws || ws.readyState !== WebSocket.OPEN) return;

            if (!isTyping) {
                isTyping = true;
                ws.send(JSON.stringify({ action: "typing", is_typing: true }));
            }

            clearTimeout(typingTimeout);
            typingTimeout = setTimeout(() => {
                isTyping = false;
                ws.send(JSON.stringify({ action: "typing", is_typing: false }));
            }, 1500);
        }

        function updateTypingUI() {
            const indicator = document.getElementById("typing-indicator");
            const users = Array.from(typingUsers);
            if (users.length === 0) {
                indicator.innerText = "";
            } else if (users.length === 1) {
                indicator.innerText = `${users[0]} is typing...`;
            } else {
                indicator.innerText = "Several people are typing...";
            }
        }

        function sendMessage() {
            const input = document.getElementById("msg-input");
            const text = input.value.trim();
            if (text && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: "message", text: text }));
                
                clearTimeout(typingTimeout);
                if (isTyping) {
                    isTyping = false;
                    ws.send(JSON.stringify({ action: "typing", is_typing: false }));
                }

                const msgBox = document.getElementById("messages");
                const div = document.createElement("div");
                div.className = "message me";
                div.innerHTML = `<strong>Me:</strong> ${text}`;
                msgBox.appendChild(div);
                msgBox.scrollTop = msgBox.scrollHeight;

                input.value = "";
            }
        }

        function handleKey(e) {
            if (e.key === "Enter") sendMessage();
        }

        connectWebSocket();
    </script>
</body>
</html>
"""

def check_winner(board, game_type):
    if game_type == "tictactoe":
        wins = [
            (0,1,2), (3,4,5), (6,7,8),
            (0,3,6), (1,4,7), (2,5,8),
            (0,4,8), (2,4,6)
        ]
        for a, b, c in wins:
            if board[a] and board[a] == board[b] == board[c]:
                return board[a]
    elif game_type == "connectfour":
        # Check horizontal
        for r in range(6):
            for c in range(4):
                idx = r * 7 + c
                if board[idx] and board[idx] == board[idx+1] == board[idx+2] == board[idx+3]:
                    return board[idx]
        # Check vertical
        for r in range(3):
            for c in range(7):
                idx = r * 7 + c
                if board[idx] and board[idx] == board[idx+7] == board[idx+14] == board[idx+21]:
                    return board[idx]
        # Check diagonal positive slope
        for r in range(3):
            for c in range(4):
                idx = r * 7 + c
                if board[idx] and board[idx] == board[idx+8] == board[idx+16] == board[idx+24]:
                    return board[idx]
        # Check diagonal negative slope
        for r in range(3, 6):
            for c in range(4):
                idx = r * 7 + c
                if board[idx] and board[idx] == board[idx-6] == board[idx-12] == board[idx-18]:
                    return board[idx]

    if "" not in board:
        return "Tie"
    return None

async def chat_handler(websocket, path):
    all_connections.add(websocket)
    current_room = None
    current_username = None

    await send_room_list(websocket)

    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")
            
            if action == "join":
                room = data.get("room", "").strip().lower()
                password = data.get("password", "")
                username = data.get("sender", "Anonymous")
                
                if room in rooms:
                    if rooms[room]["password"] != password:
                        await websocket.send(json.dumps({"status": "error", "message": "Incorrect room password!"}))
                        continue
                else:
                    rooms[room] = {
                        "password": password, 
                        "clients": {}, 
                        "op": websocket, 
                        "game": {
                            "game_type": "tictactoe",
                            "active": False,
                            "board": [""] * 9,
                            "turn": "X",
                            "winner": None,
                            "players": {"X": None, "O": None}
                        }
                    }
                
                current_room = room
                current_username = username
                rooms[room]["clients"][websocket] = username
                
                is_op = (rooms[room]["op"] == websocket)
                await websocket.send(json.dumps({"status": "joined", "room": room, "is_op": is_op}))
                
                g = rooms[room]["game"]
                await websocket.send(json.dumps({
                    "type": "game_state", 
                    "game_type": g["game_type"],
                    "board": g["board"], 
                    "turn": g["turn"], 
                    "winner": g["winner"],
                    "active": g["active"],
                    "players": g["players"]
                }))

                await broadcast_user_list(room)
                await broadcast_room_list()
                await broadcast_message(room, "System", f"{username} joined the room.", exclude=websocket)
                
            elif action == "message":
                if current_room and current_room in rooms:
                    await broadcast_message(current_room, current_username, data.get("text"), exclude=websocket)

            elif action == "typing":
                if current_room and current_room in rooms:
                    payload = json.dumps({
                        "type": "typing",
                        "sender": current_username,
                        "is_typing": data.get("is_typing", False)
                    })
                    targets = [ws for ws in rooms[current_room]["clients"] if ws != websocket]
                    if targets:
                        await asyncio.gather(*[ws.send(payload) for ws in targets])

            elif action == "launch_game":
                if current_room and current_room in rooms:
                    if rooms[current_room]["op"] == websocket:
                        g_type = data.get("game", "tictactoe")
                        board_size = 42 if g_type == "connectfour" else 9
                        
                        rooms[current_room]["game"] = {
                            "game_type": g_type,
                            "active": True,
                            "board": [""] * board_size,
                            "turn": "X",
                            "winner": None,
                            "players": {"X": None, "O": None}
                        }
                        
                        await broadcast_game_state(current_room)
                        launch_payload = json.dumps({"type": "game_launch"})
                        await asyncio.gather(*[ws.send(launch_payload) for ws in rooms[current_room]["clients"]])
                        
                        game_name = "Connect Four" if g_type == "connectfour" else "Tic-Tac-Toe"
                        join_msg = f'🎮 Room Operator started {game_name}!<br><button class="join-game-btn" onclick="joinGameAction()">Join Game</button>'
                        await broadcast_message(current_room, "System", join_msg)

            elif action == "close_game":
                if current_room and current_room in rooms:
                    if rooms[current_room]["op"] == websocket:
                        rooms[current_room]["game"]["active"] = False
                        await broadcast_game_state(current_room)
                        await broadcast_message(current_room, "System", "🎮 Room Operator closed the game.")

            elif action == "join_game":
                if current_room and current_room in rooms:
                    g = rooms[current_room]["game"]
                    if g["active"]:
                        if not g["players"]["X"] and g["players"]["O"] != current_username:
                            g["players"]["X"] = current_username
                            await broadcast_message(current_room, "System", f"👤 {current_username} joined as Player X.")
                        elif not g["players"]["O"] and g["players"]["X"] != current_username:
                            g["players"]["O"] = current_username
                            await broadcast_message(current_room, "System", f"👤 {current_username} joined as Player O.")
                        await broadcast_game_state(current_room)

            elif action == "game_move":
                if current_room and current_room in rooms:
                    g = rooms[current_room]["game"]
                    idx = data.get("index")
                    
                    current_player_name = g["players"].get(g["turn"])
                    if g["active"] and not g["winner"] and current_player_name == current_username:
                        valid_move = False
                        
                        if g["game_type"] == "tictactoe":
                            if 0 <= idx < 9 and g["board"][idx] == "":
                                g["board"][idx] = g["turn"]
                                valid_move = True
                        elif g["game_type"] == "connectfour":
                            col = idx
                            if 0 <= col < 7:
                                for row in range(5, -1, -1):
                                    cell_idx = row * 7 + col
                                    if g["board"][cell_idx] == "":
                                        g["board"][cell_idx] = g["turn"]
                                        valid_move = True
                                        break
                        
                        if valid_move:
                            winner = check_winner(g["board"], g["game_type"])
                            if winner:
                                g["winner"] = winner
                                game_name = "Connect Four" if g["game_type"] == "connectfour" else "Tic-Tac-Toe"
                                if winner == "Tie":
                                    await broadcast_message(current_room, "System", f"🤝 {game_name} ended in a Tie!")
                                else:
                                    winner_name = g["players"][winner]
                                    await broadcast_message(current_room, "System", f"🎉 {winner_name} ({winner}) won {game_name}!")
                            else:
                                g["turn"] = "O" if g["turn"] == "X" else "X"
                                
                            await broadcast_game_state(current_room)

            elif action == "game_reset":
                if current_room and current_room in rooms:
                    if rooms[current_room]["op"] == websocket:
                        g = rooms[current_room]["game"]
                        board_size = 42 if g["game_type"] == "connectfour" else 9
                        g["board"] = [""] * board_size
                        g["turn"] = "X"
                        g["winner"] = None
                        await broadcast_game_state(current_room)

            elif action == "kick":
                if current_room and current_room in rooms:
                    if rooms[current_room]["op"] == websocket:
                        target_name = data.get("target")
                        target_ws = None
                        for ws, uname in rooms[current_room]["clients"].items():
                            if uname == target_name:
                                target_ws = ws
                                break
                        if target_ws:
                            await target_ws.send(json.dumps({"status": "kicked"}))
                            await target_ws.close()
                    
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        all_connections.discard(websocket)
        if current_room and current_room in rooms:
            if websocket in rooms[current_room]["clients"]:
                del rooms[current_room]["clients"][websocket]
                if rooms[current_room]["clients"]:
                    if rooms[current_room]["op"] == websocket:
                        rooms[current_room]["op"] = list(rooms[current_room]["clients"].keys())[0]
                    
                    g = rooms[current_room]["game"]
                    if g["players"]["X"] == current_username: g["players"]["X"] = None
                    if g["players"]["O"] == current_username: g["players"]["O"] = None
                    
                    await broadcast_user_list(current_room)
                    await broadcast_game_state(current_room)
                    clear_typing = json.dumps({"type": "typing", "sender": current_username, "is_typing": False})
                    await asyncio.gather(*[ws.send(clear_typing) for ws in rooms[current_room]["clients"]])
                    await broadcast_message(current_room, "System", f"{current_username} left the room.")
                else:
                    del rooms[current_room]
                await broadcast_room_list()

async def broadcast_message(room, sender, text, exclude=None):
    if room in rooms:
        payload = json.dumps({"type": "message", "sender": sender, "text": text})
        targets = [ws for ws in rooms[room]["clients"] if ws != exclude]
        if targets:
            await asyncio.gather(*[ws.send(payload) for ws in targets])

async def broadcast_game_state(room):
    if room in rooms:
        g = rooms[room]["game"]
        payload = json.dumps({
            "type": "game_state",
            "game_type": g["game_type"],
            "board": g["board"],
            "turn": g["turn"],
            "winner": g["winner"],
            "active": g["active"],
            "players": g["players"]
        })
        await asyncio.gather(*[ws.send(payload) for ws in rooms[room]["clients"]])

async def broadcast_user_list(room):
    if room in rooms:
        room_info = rooms[room]
        users = [
            {"name": uname, "is_op": (ws == room_info["op"])}
            for ws, uname in room_info["clients"].items()
        ]
        payload = json.dumps({"type": "user_list", "users": users})
        await asyncio.gather(*[ws.send(payload) for ws in room_info["clients"]])

def get_room_list_payload():
    room_data = [
        {
            "name": name,
            "count": len(info["clients"]),
            "locked": bool(info["password"])
        }
        for name, info in rooms.items()
    ]
    return json.dumps({"type": "room_list", "rooms": room_data})

async def send_room_list(websocket):
    await websocket.send(get_room_list_payload())

async def broadcast_room_list():
    if all_connections:
        payload = get_room_list_payload()
        await asyncio.gather(*[ws.send(payload) for ws in all_connections], return_exceptions=True)

async def process_request(path, request_headers):
    if "Upgrade" in request_headers.get("Connection", ""):
        return None
    return (
        HTTPStatus.OK,
        [("Content-Type", "text/html; charset=utf-8")],
        HTML_PAGE.encode("utf-8")
    )

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(chat_handler, "0.0.0.0", port, process_request=process_request):
        print(f"Server running on port {port}...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
