import base64
import os
import re
from datetime import datetime, timedelta, timezone
from http.cookiejar import UTC_ZONES

import bcrypt
import jwt
import smtplib
from bson import ObjectId
from email.message import EmailMessage
import motor.motor_asyncio
from fastapi import FastAPI, Request, Response, status
import controllers.pinecone_database
from mysocket import sio_app
from pydantic import BaseModel
import uvicorn
from models.database_models import User, Item

app = FastAPI()

#mongodb config
db_admin = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
mongoURI = f'mongodb+srv://{db_admin}:{db_password}@cluster0.c6szrff.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
client = motor.motor_asyncio.AsyncIOMotorClient(mongoURI)
database = client[os.getenv('DB_NAME')]
users = database['users']
items = database['items']
registrations = database['registrations']

emailRegex = r"^[a-zA-Z0-9](?:[a-zA-Z0-9._%+-]*[a-zA-Z0-9])?@srmap\.edu\.in$"
passwordRegex = r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[\W\_])[A-Za-z\d\W\_]+$"
phoneRegex = r"^\+?[1-9]\d{0,2}\d{6,14}$"

app.mount('/ws', sio_app)

@app.get('/')
async def index():
    return {"message": "Hello welcome to lost and found portal!"}


@app.post('/register')
async def register(response: Response, user: User):
    user = user.model_dump()
    if 'mail' not in user or 'password' not in user or 'name' not in user or 'phone' not in user:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "Missing Fields!"}

    if user['name'].strip() == '' or user['phone'].strip() == '' or user['mail'].strip() == '' or user['password'].strip() == '':
        response.status_code = status.HTTP_406_NOT_ACCEPTABLE
        return {"message": "Empty Fields!"}

    if not re.match(emailRegex, user['mail']):
        response.status_code = status.HTTP_406_NOT_ACCEPTABLE
        return {"message": "Email mismatch!"}

    if not re.match(phoneRegex, user['phone']):
        response.status_code = status.HTTP_406_NOT_ACCEPTABLE
        return {"message": "Invalid mobile number!"}

    if not re.match(passwordRegex, user['password']):
        response.status_code = status.HTTP_406_NOT_ACCEPTABLE
        return {"message": "Password is not secure!"}

    if user['socket_id'] != '':
        response.status_code = status.HTTP_406_NOT_ACCEPTABLE
        return {"message": "Socket id should not be provided!"}

    existing_user = await users.find_one({"mail": user['mail']})

    if existing_user is not None:
        response.status_code = status.HTTP_409_CONFLICT
        return {"message": "Email already Exists!"}

    password = user['password'].encode('utf-8')
    hashed_password = bcrypt.hashpw(password, bcrypt.gensalt(rounds=int(os.getenv('SALT_ROUNDS'))))

    user['password'] = base64.b64encode(hashed_password).decode('utf-8')

    expiry_time = datetime.now(timezone.utc) + timedelta(hours=24)
    user['expiresAt'] = expiry_time
    new_item = await registrations.insert_one(user)
    await users.create_index("expiresAt", expireAfterSeconds=0)
    data = {'_id': str(new_item.inserted_id)}
    auth_key = jwt.encode(data, os.getenv('JWT_KEY'), algorithm="HS256")
    smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
    smtp_server.starttls()
    smtp_server.login(os.getenv('EMAIL'), os.getenv('EMAIL_PASSWORD'))
    composed_email = EmailMessage()
    composed_email['Subject'] = 'Complete your registration at ReclaimitAI'
    composed_email['From'] = os.getenv('EMAIL')
    composed_email['To'] = user['mail']
    composed_email.add_alternative(f"""
    <!DOCTYPE html>
    <html>
        <body>
            <h2>Welcome to one of the most sophisticated and secure lost and found applications!</h2>
            <p>To complete your registration</p>
            <p>please <a href="{os.getenv('EMAIL_REGISTRATION_LINK')}/register/{auth_key}">Click Here</a> to register for <b>ReclaimitAI</b></p>
        </body>
    </html>
    """, subtype="html")
    print(auth_key)
    smtp_server.send_message(composed_email)
    return {"message": "Registration email sent to the given email id!"}


# @app.post('/login')
# async def login(request: Request, )

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


