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
    print(f'{sid} connected')

@socket_server.event
async def disconnect(sid):
    print(f'{sid} disconnected')