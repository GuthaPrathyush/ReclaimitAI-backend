from fastapi import FastAPI, Request, Response, status
import controllers.pinecone_database
from mysocket import sio_app
from pydantic import BaseModel
import uvicorn
from models.database_models import User, Item

app = FastAPI()

app.mount('/ws', sio_app)

@app.get('/')
async def index():
    return {"message": "Hello welcome to lost and found portal!"}

# @app.post('/register')
# async def register(user: User):
#     #code to create object in database!
#     # _id = motor.lasdfjlsaf
#     user['_id'] = _id
#
#     auth_token = {
#         _id: _id
#     }
#     return {'auth_token': encrypt}


@app.post('/upload')
async def upload(request: Request, response: Response, item: Item):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "Unauthorized Access!"}
    auth_token = req_headers['auth_token']
    #uploading items
    return {"message": "item uploaded successfully"}


@app.get('/ws')
async def ws():
    return {"message": "this is websocket"}

if __name__ == '__main__':
    uvicorn.run('main:app', reload=True)


