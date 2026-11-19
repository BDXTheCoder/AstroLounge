import asyncio
import json
import os
from http import HTTPStatus
import websockets

# Store rooms: { "room_code": { "password": "...", "clients": { ws: username } } }
rooms = {}
# Track all connected clients (even those still on the login screen) for room list updates
all_connections = set()

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Nexus Chat</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; }
        body { background-color: #1e1f22; color: #dbdee1; display: flex; height: 100vh; justify-content: center; align-items: center; }
        
        /* Login & Lobby Layout */
        .login-wrapper { display: flex; gap: 20px; align-items: stretch; }
        .card { background: #2b2d31; padding: 30px; border-radius: 12px; width: 380px; box-shadow: 0 8px 24px rgba(0,0,0,0.3); display: flex; flex-direction: column; }
        h2 { color: #fff; margin-bottom: 20px; text-align: center; }
        label { font-size: 11px; font-weight: bold; color: #b5bac1; display: block; margin-top: 12px; }
        input { width: 100%; padding: 10px; margin-top: 5px; background: #111214; border: none; border-radius: 6px; color: #fff; font-size: 14px; }
        button { width: 100%; padding: 12px; background: #5865f2; color: white; border: none; border-radius: 6px; font-weight: bold; margin-top: 20px; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #4752c4; }

        /* Active Rooms Box */
        .rooms-list { flex: 1; overflow-y: auto; max-height: 260px; display: flex; flex-direction: column; gap: 8px; }
        .room-item { background: #1e1f22; padding: 12px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; border: 1px solid transparent; transition: 0.15s; }
        .room-item:hover { border-color: #5865f2; background: #232428; }
        .room-name { font-weight: bold; color: #fff; font-size: 14px; }
        .room-meta { font-size: 12px; color: #949ba4; }
        .empty-rooms { color: #949ba4; font-size: 13px; text-align: center; margin-top: 40px; }
        
        /* Chat Screen */
        #chat-screen { display: none; width: 90vw; height: 90vh; max-width: 1000px; max-height: 700px; flex-direction: row; border-radius: 12px; overflow: hidden; background: #313338; box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
        .main-chat { flex: 1; display: flex; flex-direction: column; }
        .chat-header { padding: 15px 20px; background: #313338; border-bottom: 1px solid #1f2023; font-weight: bold; color: #fff; display: flex; justify-content: space-between; align-items: center; }
        .messages { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        .message { background: #2b2d31; padding: 10px 14px; border-radius: 8px; max-width: 70%; word-break: break-word; }
        .message.me { background: #5865f2; align-self: flex-end; }
        
        /* Typing Indicator */
        .typing-indicator { height: 22px; padding: 0 20px; font-size: 12px; font-style: italic; color: #b5bac1; display: flex; align-items: center; }
        
        .message-input-area { padding: 10px 20px 15px 20px; display: flex; gap: 10px; background: #313338; }
        .message-input-area input { margin-top: 0; background: #383A40; flex: 1; }
        .sidebar { width: 220px; background: #2b2d31; padding: 20px; border-left: 1px solid #1f2023; }
        .sidebar h3 { font-size: 12px; color: #949ba4; margin-bottom: 10px; }
        .user-item { padding: 6px 0; color: #dbdee1; font-size: 14px; }
        .leave-btn { background: #da373c; padding: 6px 12px; width: auto; margin-top: 0; }
        .leave-btn:hover { background: #a12828; }

        @media (max-width: 800px) {
            .login-wrapper { flex-direction: column; }
            .card { width: 90vw; }
        }
    </style>
</head>
<body>

    <!-- Login & Active Rooms Screen -->
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

    <!-- Chat Screen -->
    <div id="chat-screen">
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
            <h3>ONLINE MEMBERS</h3>
            <div id="user-list"></div>
        </div>
    </div>

    <script>
        let ws;
        let username;
        let typingTimeout;
        let isTyping = false;
        let typingUsers = new Set();

        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            ws = new WebSocket(protocol + window.location.host);

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                
                if (data.status === "error") {
                    alert(data.message);
                    return;
                }

                if (data.status === "joined") {
                    document.getElementById("login-screen").style.display = "none";
                    document.getElementById("chat-screen").style.display = "flex";
                    document.getElementById("room-title").innerText = "# " + data.room;
                }

                if (data.type === "room_list") {
                    renderActiveRooms(data.rooms);
                }

                if (data.type === "message") {
                    const msgBox = document.getElementById("messages");
                    const div = document.createElement("div");
                    div.className = "message" + (data.sender === username ? " me" : "");
                    div.innerHTML = `<strong>${data.sender}:</strong> ${data.text}`;
                    msgBox.appendChild(div);
                    msgBox.scrollTop = msgBox.scrollHeight;
                }

                if (data.type === "user_list") {
                    const userList = document.getElementById("user-list");
                    userList.innerHTML = "";
                    data.users.forEach(user => {
                        const uDiv = document.createElement("div");
                        uDiv.className = "user-item";
                        uDiv.innerText = "🟢 " + user;
                        userList.appendChild(uDiv);
                    });
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
            } else if (users.length === 2) {
                indicator.innerText = `${users[0]} and ${users[1]} are typing...`;
            } else {
                indicator.innerText = "Several people are typing...";
            }
        }

        function sendMessage() {
            const input = document.getElementById("msg-input");
            const text = input.value.trim();
            if (text && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: "message", text: text }));
                
                // Stop typing indicator immediately upon sending
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

        // Connect immediately on page load to fetch active rooms
        connectWebSocket();
    </script>
</body>
</html>
"""

async def chat_handler(websocket, path):
    all_connections.add(websocket)
    current_room = None
    current_username = None

    # Send current active rooms immediately upon page load
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
                    rooms[room] = {"password": password, "clients": {}}
                
                current_room = room
                current_username = username
                rooms[room]["clients"][websocket] = username
                
                await websocket.send(json.dumps({"status": "joined", "room": room}))
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
                    
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        all_connections.discard(websocket)
        if current_room and current_room in rooms:
            if websocket in rooms[current_room]["clients"]:
                del rooms[current_room]["clients"][websocket]
                if rooms[current_room]["clients"]:
                    await broadcast_user_list(current_room)
                    # Clear typing indicator if user disconnected while typing
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

async def broadcast_user_list(room):
    if room in rooms:
        users = list(rooms[room]["clients"].values())
        payload = json.dumps({"type": "user_list", "users": users})
        await asyncio.gather(*[ws.send(payload) for ws in rooms[room]["clients"]])

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

# Intercept regular HTTP requests and return our HTML chat page
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
        print(f"Chat server running on port {port}...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
