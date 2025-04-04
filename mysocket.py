import socketio
from dotenv import load_dotenv
import os

load_dotenv()


socket_server = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=["*"]
)

sio_app = socketio.ASGIApp(
    socketio_server=socket_server,
    socketio_path=os.getenv('SOCKET_PATH')
)

@socket_server.event
async def connect(sid, environ, auth):
    auth_token = auth['auth_token']
    print(f'{auth_token} connected as {sid}')

@socket_server.event
async def disconnect(sid):
    print(f'{sid} disconnected')

@socket_server.event
async def ping(sid, data):
    try:
        await socket_server.emit('pong', {"message": "Helloo"}, room=sid)
    except Exception as e:
        print('Connection lost!')


