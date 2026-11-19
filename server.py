import asyncio
import json
import os
from http import HTTPStatus
import websockets

# Store rooms: { "ROOM_CODE": { "password": "...", "clients": { ws: username } } }
rooms = {}

# Built-in modern chat web interface
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Nexus Chat</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; }
        body { background-color: #1e1f22; color: #dbdee1; display: flex; height: 100vh; justify-content: center; align-items: center; }
        .card, .chat-container { background: #2b2d31; padding: 30px; border-radius: 12px; width: 400px; box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
        h2 { color: #fff; margin-bottom: 20px; text-align: center; }
        label { font-size: 11px; font-weight: bold; color: #b5bac1; display: block; margin-top: 10px; }
        input { width: 100%; padding: 10px; margin-top: 5px; background: #111214; border: none; border-radius: 6px; color: #fff; font-size: 14px; }
        button { width: 100%; padding: 12px; background: #5865f2; color: white; border: none; border-radius: 6px; font-weight: bold; margin-top: 20px; cursor: pointer; }
        button:hover { background: #4752c4; }
        
        #chat-screen { display: none; width: 90vw; height: 90vh; max-width: 1000px; max-height: 700px; flex-direction: row; border-radius: 12px; overflow: hidden; background: #313338; }
        .main-chat { flex: 1; display: flex; flex-direction: column; }
        .chat-header { padding: 15px 20px; background: #313338; border-bottom: 1px solid #1f2023; font-weight: bold; color: #fff; display: flex; justify-content: space-between; align-items: center; }
        .messages { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        .message { background: #2b2d31; padding: 10px 14px; border-radius: 8px; max-width: 70%; word-break: break-word; }
        .message.me { background: #5865f2; align-self: flex-end; }
        .message-input-area { padding: 15px 20px; display: flex; gap: 10px; background: #313338; }
        .message-input-area input { margin-top: 0; background: #383A40; flex: 1; }
        .sidebar { width: 220px; background: #2b2d31; padding: 20px; border-left: 1px solid #1f2023; }
        .sidebar h3 { font-size: 12px; color: #949ba4; margin-bottom: 10px; }
        .user-item { padding: 6px 0; color: #dbdee1; font-size: 14px; }
        .leave-btn { background: #da373c; padding: 6px 12px; width: auto; margin-top: 0; }
        .leave-btn:hover { background: #a12828; }
    </style>
</head>
<body>

    <!-- Login Screen -->
    <div id="login-screen" class="card">
        <h2>Nexus Chat</h2>
        <label>USERNAME</label>
        <input type="text" id="username" placeholder="Your name">
        <label>ROOM CODE</label>
        <input type="text" id="room" placeholder="e.g. general">
        <label>ROOM PASSWORD (OPTIONAL)</label>
        <input type="password" id="password" placeholder="••••••••">
        <button onclick="joinRoom()">Join Room</button>
    </div>

    <!-- Chat Screen -->
    <div id="chat-screen">
        <div class="main-chat">
            <div class="chat-header">
                <span id="room-title"># room</span>
                <button class="leave-btn" onclick="location.reload()">Leave</button>
            </div>
            <div class="messages" id="messages"></div>
            <div class="message-input-area">
                <input type="text" id="msg-input" placeholder="Type a message..." onkeypress="handleKey(event)">
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

        function joinRoom() {
            username = document.getElementById("username").value.trim();
            const room = document.getElementById("room").value.trim();
            const password = document.getElementById("password").value.trim();

            if (!username || !room) {
                alert("Username and Room Code are required!");
                return;
            }

            const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            ws = new WebSocket(protocol + window.location.host);

            ws.onopen = function() {
                ws.send(JSON.stringify({ action: "join", room: room, password: password, sender: username }));
            };

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                
                if (data.status === "error") {
                    alert(data.message);
                    ws.close();
                    return;
                }

                if (document.getElementById("login-screen").style.display !== "none") {
                    document.getElementById("login-screen").style.display = "none";
                    document.getElementById("chat-screen").style.display = "flex";
                    document.getElementById("room-title").innerText = "# " + room;
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
            };
        }

        function sendMessage() {
            const input = document.getElementById("msg-input");
            const text = input.value.trim();
            if (text && ws) {
                ws.send(JSON.stringify({ action: "message", text: text }));
                
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
    </script>
</body>
</html>
"""

async def chat_handler(websocket, path):
    current_room = None
    current_username = None
    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")
            
            if action == "join":
                room = data.get("room")
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
                
                await websocket.send(json.dumps({"status": "joined"}))
                await broadcast_user_list(room)
                await broadcast_message(room, "System", f"{username} joined the room.", exclude=websocket)
                
            elif action == "message":
                if current_room and current_room in rooms:
                    await broadcast_message(current_room, current_username, data.get("text"))
                    
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if current_room and current_room in rooms:
            if websocket in rooms[current_room]["clients"]:
                del rooms[current_room]["clients"][websocket]
                if rooms[current_room]["clients"]:
                    await broadcast_user_list(current_room)
                    await broadcast_message(current_room, "System", f"{current_username} left the room.")
                else:
                    del rooms[current_room]

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

# Intercept regular HTTP requests and return our HTML chat page
async def process_request(path, request_headers):
    if "Upgrade" in request_headers.get("Connection", ""):
        return None  # Let WebSocket connections proceed to chat_handler
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
