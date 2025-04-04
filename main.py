import base64
import os
import re
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
import smtplib
from bson import ObjectId, errors
from email.message import EmailMessage
import motor.motor_asyncio
from fastapi import FastAPI, Request, Response, status, Form, File, UploadFile
from starlette.responses import HTMLResponse
from controllers.pinecone_database import *
from controllers.pinecone_controller import *
import cloudinary
import cloudinary.uploader
from mysocket import sio_app
import uvicorn
from models.database_models import User, LoginUser, Item
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_ttl_index()  # Ensure index exists before app starts
    yield  # Application starts here
    # Any cleanup code can go here if needed

app = FastAPI(lifespan=lifespan)

#cloudinary config
cloudinary.config(
    cloud_name = "ddvewtyvu",
    api_key = "253238265924481",
    api_secret = os.getenv('CLOUDINARY_API_SECRET_KEY'), # Click 'View API Keys' above to copy your API secret
    secure=True
)

#mongodb config
db_admin = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
mongoURI = f'mongodb+srv://{db_admin}:{db_password}@cluster0.c6szrff.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
client = motor.motor_asyncio.AsyncIOMotorClient(mongoURI)
database = client[os.getenv('DB_NAME')]
users = database['users']
items = database['items']
registrations = database['registrations']


async def check_ttl_index():
    indexes_cursor = registrations.list_indexes()  # This returns a cursor

    async for index in indexes_cursor:  # Iterate over the cursor asynchronously
        if "expiresAt" in index["key"]:
            return
    await registrations.create_index("expiresAt", expireAfterSeconds=0)


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
    try:
        password = user['password'].encode('utf-8')
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt(rounds=int(os.getenv('SALT_ROUNDS'))))

        user['password'] = base64.b64encode(hashed_password).decode('utf-8')

        expiry_time = datetime.now(timezone.utc) + timedelta(hours=24)

        user['expiresAt'] = expiry_time
        new_item = await registrations.insert_one(user)
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
                <p>please <a href="{os.getenv('EMAIL_REGISTRATION_LINK')}/complete-registration/{auth_key}">Click Here</a> to register for <b>ReclaimitAI</b></p>
            </body>
        </html>
        """, subtype="html")
        print(auth_key)
        smtp_server.send_message(composed_email)
        return {"message": "Registration email sent to the given email id!"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error, please try again later!"}

@app.get('/complete-registration/{auth_token}', response_class=HTMLResponse)
async def complete_registration(auth_token: str):
    new_item = None
    try:
        data = jwt.decode(auth_token, os.getenv('JWT_KEY'), algorithms=["HS256"])
        user = await registrations.find_one({'_id': ObjectId(data['_id'])})
        user = dict(user)
        user.pop('_id')
        user.pop('expiresAt')
        new_item = await users.insert_one(user)
        await registrations.find_one_and_delete({'_id': ObjectId(data['_id'])})
        return f"""
        <!DOCTYPE html>
        <html>
            <head>
                <title>Registration complete!</title>
            </head>
            <body>
                <h1>Welcome to ReclaimitAI</h1>
                <p>your registration was complete with {auth_token}</p>
                <p>Please close this tab and login using your credentials!</p>
            </body>
        </html>
        """
    except errors.InvalidId:
        if new_item is not None:
            await users.find_one_and_delete({'_id': new_item.inserted_id})
    except Exception as e:
        return f"""
        <!DOCTYPE html>
        <html>
            <head>
                <title>Registration failed!</title>
            </head>
            <body>
                <h1>Welcome to ReclaimitAI</h1>
                <p style="color: red;">your registration was not successful :(</p>
            </body>
        </html>
        """


@app.post('/login')
async def login(request: Request, user:LoginUser, response: Response):
    user = user.model_dump()
    if user['mail'].strip() == '' or user['password'].strip() == '':
        response.status_code = status.HTTP_406_NOT_ACCEPTABLE
        return {"message": "Empty fields!"}

    existing_user = await users.find_one({'mail': user['mail']})
    if existing_user is None:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"message": "User does not Exist!"}

    existing_user = dict(existing_user)
    try:
        entered_password_bytes = user['password'].encode('utf-8')

        # Decode the stored password from Base64
        stored_hashed_bytes = base64.b64decode(existing_user['password'])

        if not bcrypt.checkpw(entered_password_bytes, stored_hashed_bytes):
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"message": "Invalid password!"}
        data = {'_id': str(existing_user['_id'])}
        auth_token = jwt.encode(data, os.getenv('JWT_KEY'), algorithm="HS256")
        return {"message": "User login successful", "auth_token": auth_token}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Inernal server error, please try again later!"}


@app.post('/upload')
async def upload(request: Request, response: Response, name: str = Form(...), state: bool = Form(...), description: str = Form(...), image: UploadFile = File(...)):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers :
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "Unauthorized Access!"}

    auth_token = req_headers['auth_token']
    try:
        data = jwt.decode(auth_token, os.getenv('JWT_KEY'), algorithms=["HS256"])
    except Exception as e:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"message": "Unauthorized access!"}

    try:
        existing_user = await users.find_one({'_id': ObjectId(data['_id'])})
        if existing_user is None:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"message": "Unauthorized access!"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal Server Error!"}
    try:
        item = {'owner_id': ObjectId(data['_id']), 'name': name, 'state': state, 'description': description, 'image': ''}
        insert_result = await items.insert_one(item)
        document_id = str(insert_result.inserted_id)
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Unable to upload the item in the database"}
    try:
        upload_result = cloudinary.uploader.upload(image.file, public_id=document_id)
        cloudinary_url = upload_result.get("secure_url")
    except Exception as e:
        await items.find_one_and_delete({"_id": insert_result.inserted_id})
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Unable to upload the image!"}
    try:
        await items.update_one({"_id": ObjectId(document_id)}, {"$set": {"image": cloudinary_url}})
    except Exception as e:
        result = cloudinary.uploader.destroy(document_id)
        await items.find_one_and_delete({"_id": insert_result.inserted_id})
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Unable to update the item in the database!"}


    try:
        text_embedding = await get_text_embedding(description)
        image_embedding = await get_image_embedding(image)
        if state:
            upsert_lost_item_description_in_pinecone_database(document_id, text_embedding)
            upsert_lost_item_image_in_pinecone_database(document_id, image_embedding)
        else:
            upsert_found_item_description_in_pinecone_database(document_id, text_embedding)
            upsert_found_item_image_in_pinecone_database(document_id, image_embedding)

    except Exception as e:
        result = cloudinary.uploader.destroy(document_id)
        await items.find_one_and_delete({"_id": insert_result.inserted_id})
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Unable to upload the item to AI matching"}
    return {"message": "item uploaded successfully"}


@app.get('/ws')
async def ws():
    return {"message": "this is websocket"}

if __name__ == '__main__':
    uvicorn.run('main:app', reload=True)


