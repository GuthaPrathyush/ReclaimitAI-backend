from fastapi import FastAPI
from mysocket import sio_app
from controllers import pinecone_database
from pydantic import BaseModel
import uvicorn

app = FastAPI()

app.mount('/ws', sio_app)

@app.get('/')
async def index():
    return {"message": "Hello welcome to lost and found portal!"}

@app.post('/upload')

@app.get('/ws')
async def ws():
    return {"message": "this is websocket"}

if __name__ == '__main__':
    uvicorn.run('main:app', reload=True)


