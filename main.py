from dotenv import load_dotenv

load_dotenv()

import base64
import re
import requests
from datetime import datetime, timedelta, timezone
import bcrypt
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
import uvicorn
from models.database_models import User, LoginUser
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

@asynccontextmanager
async def lifespan(application: FastAPI):
    await check_ttl_index()  # Ensure index exists before app starts
    yield  # Application starts here
    # Any cleanup code can go here if needed

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace * with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class TokenUpdate(BaseModel):
    token: str



@app.post('/update-fcm-token')
async def update_fcm_token(request: Request, response: Response, token_update: TokenUpdate):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "Unauthorized Access!"}

    auth_token = req_headers['auth_token']
    try:
        data = jwt.decode(auth_token, os.getenv('JWT_KEY'), algorithms=["HS256"])
    except Exception:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"message": "Unauthorized access!"}

    try:
        # Update only the socket_id field for the current user
        result = await users.update_one(
            {'_id': ObjectId(data['_id'])},
            {'$set': {'socket_id': token_update.token}}
        )
        if result.modified_count == 0:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"message": "User not found or token unchanged"}
        return {"message": "Push token updated successfully"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"Internal server error: {str(e)}"}



import requests

def send_expo_push_notification(expo_push_token, title, body, data=None):
    """
    Send a push notification via Expo Push API.
    """
    message = {
        "to": expo_push_token,
        "sound": "default",
        "title": title,
        "body": body,
        "data": data or {},
    }
    response = requests.post(
        "https://exp.host/--/api/v2/push/send",
        json=message,
        headers={
            "Accept": "application/json",
            "Accept-encoding": "gzip, deflate",
            "Content-Type": "application/json",
        },
        timeout=10
    )
    try:
        response.raise_for_status()
        return {"success": True, "response": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e), "response": response.text}

@app.post('/upload')
async def upload(request: Request, response: Response, name: str = Form(...), state: bool = Form(...), description: str = Form(...), timestamp: int = Form(...), image: UploadFile = File(...)):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "Unauthorized Access!"}

    auth_token = req_headers['auth_token']
    try:
        data = jwt.decode(auth_token, os.getenv('JWT_KEY'), algorithms=["HS256"])
    except Exception:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"message": "Unauthorized access!"}

    try:
        existing_user = await users.find_one({'_id': ObjectId(data['_id'])})
        if existing_user is None:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"message": "Unauthorized access!"}
    except Exception:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal Server Error!"}
    try:
        item = {
            'owner_mail': existing_user['mail'],
            'name': name,
            'state': state,
            'description': description,
            'timestamp': timestamp,
            'image': ''
        }
        insert_result = await items.insert_one(item)
        document_id = str(insert_result.inserted_id)
    except Exception:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Unable to upload the item in the database"}
    try:
        image_bytes = await image.read()
        upload_result = cloudinary.uploader.upload(image_bytes, public_id=document_id)
        cloudinary_url = upload_result.get("secure_url")
    except Exception:
        await items.find_one_and_delete({"_id": insert_result.inserted_id})
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Unable to upload the image!"}
    try:
        await items.update_one({"_id": ObjectId(document_id)}, {"$set": {"image": cloudinary_url}})
    except Exception:
        result = cloudinary.uploader.destroy(document_id)
        await items.find_one_and_delete({"_id": insert_result.inserted_id})
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Unable to update the item in the database!"}

    try:
        text_embedding = await get_text_embedding(description)
        image_embedding = await get_image_embedding(image_bytes)
        if state:
            upsert_lost_item_description_in_pinecone_database(document_id, text_embedding)
            upsert_lost_item_image_in_pinecone_database(document_id, image_embedding)
        else:
            upsert_found_item_description_in_pinecone_database(document_id, text_embedding)
            upsert_found_item_image_in_pinecone_database(document_id, image_embedding)
    except Exception:
        result = cloudinary.uploader.destroy(document_id)
        await items.find_one_and_delete({"_id": insert_result.inserted_id})
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Unable to upload the item to AI matching"}

    try:
        if state:
            matched_ids = get_matched_found_items_id(text_embedding, image_embedding)
            filtered_matched_ids = []
            for matched_id in matched_ids:
                matched_item = await items.find_one({'_id': ObjectId(matched_id)})
                if matched_item and matched_item['owner_mail'] != existing_user['mail']:
                    filtered_matched_ids.append(matched_id)
            await items.update_one({"_id": ObjectId(document_id)}, {"$set": {"matches": filtered_matched_ids}})
            # Send Expo push notification to uploader if matches found
            if existing_user.get('socket_id', '') and len(filtered_matched_ids) != 0:
                send_expo_push_notification(
                    existing_user['socket_id'],
                    f"New Match for {item['name']}",
                    f"Your {item['name']} has {len(filtered_matched_ids)} new possible {'match' if len(filtered_matched_ids) == 1 else 'matches'}"
                )
        else:
            matched_ids = get_matched_lost_items_id(text_embedding, image_embedding)
            for matched_id in matched_ids:
                temp_post = await items.find_one({'_id': ObjectId(matched_id)})
                if temp_post['owner_mail'] == existing_user['mail']:
                    continue
                temp_user_mail = temp_post['owner_mail']
                temp_user = await users.find_one({"mail": temp_user_mail})
                owner_push_token = temp_user.get('socket_id', '')
                await items.update_one({"_id": ObjectId(matched_id)}, {"$push": {"matches": document_id}})
                # Send Expo push notification to matched item's owner
                if owner_push_token:
                    send_expo_push_notification(
                        owner_push_token,
                        f"New Match for {temp_post['name']}",
                        f"Your {temp_post['name']} has 1 new possible match"
                    )
    except Exception:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Please Retry querying for matches!"}

    return {"message": "item uploaded successfully"}


# @app.post('/upload')
# async def upload(request: Request, response: Response, name: str = Form(...), state: bool = Form(...), description: str = Form(...), timestamp: int = Form(...), image: UploadFile = File(...)):
#     req_headers = dict(request.headers)
#     if 'auth_token' not in req_headers :
#         response.status_code = status.HTTP_400_BAD_REQUEST
#         return {"message": "Unauthorized Access!"}
#
#     auth_token = req_headers['auth_token']
#     try:
#         data = jwt.decode(auth_token, os.getenv('JWT_KEY'), algorithms=["HS256"])
#     except Exception as e:
#         response.status_code = status.HTTP_401_UNAUTHORIZED
#         return {"message": "Unauthorized access!"}
#
#     try:
#         existing_user = await users.find_one({'_id': ObjectId(data['_id'])})
#         if existing_user is None:
#             response.status_code = status.HTTP_401_UNAUTHORIZED
#             return {"message": "Unauthorized access!"}
#     except Exception as e:
#         response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
#         return {"message": "Internal Server Error!"}
#     try:
#         item = {'owner_mail': existing_user['mail'], 'name': name, 'state': state, 'description': description, 'timestamp': timestamp, 'image': ''}
#         insert_result = await items.insert_one(item)
#         document_id = str(insert_result.inserted_id)
#     except Exception as e:
#         response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
#         return {"message": "Unable to upload the item in the database"}
#     try:
#         image_bytes = await image.read()
#         upload_result = cloudinary.uploader.upload(image_bytes, public_id=document_id)
#         cloudinary_url = upload_result.get("secure_url")
#     except Exception as e:
#         await items.find_one_and_delete({"_id": insert_result.inserted_id})
#         response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
#         return {"message": "Unable to upload the image!"}
#     try:
#         await items.update_one({"_id": ObjectId(document_id)}, {"$set": {"image": cloudinary_url}})
#     except Exception as e:
#         result = cloudinary.uploader.destroy(document_id)
#         await items.find_one_and_delete({"_id": insert_result.inserted_id})
#         response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
#         return {"message": "Unable to update the item in the database!"}
#
#
#     try:
#         text_embedding = await get_text_embedding(description)
#         image_embedding = await get_image_embedding(image_bytes)
#         if state:
#             upsert_lost_item_description_in_pinecone_database(document_id, text_embedding)
#             upsert_lost_item_image_in_pinecone_database(document_id, image_embedding)
#         else:
#             upsert_found_item_description_in_pinecone_database(document_id, text_embedding)
#             upsert_found_item_image_in_pinecone_database(document_id, image_embedding)
#
#     except Exception as e:
#         result = cloudinary.uploader.destroy(document_id)
#         await items.find_one_and_delete({"_id": insert_result.inserted_id})
#         response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
#         return {"message": "Unable to upload the item to AI matching"}
#     try:
#         if state:
#             matched_ids = get_matched_found_items_id(text_embedding, image_embedding)
#             # Filter out any matches where the owner is the same as the current user
#             filtered_matched_ids = []
#             for matched_id in matched_ids:
#                 matched_item = await items.find_one({'_id': ObjectId(matched_id)})
#                 if matched_item and matched_item['owner_mail'] != existing_user['mail']:
#                     filtered_matched_ids.append(matched_id)
#
#             await items.update_one({"_id": ObjectId(document_id)}, {"$set": {"matches": filtered_matched_ids}})
#             # if existing_user['socket_id'] != '' and len(filtered_matched_ids) != 0:
#             #   await socket_server.emit('notification', data={"message": f"Your {item['name']} has {len(filtered_matched_ids)} new possible {"match" if len(filtered_matched_ids) == 1 else "matches"}"}, room=existing_user['socket_id'])
#         else:
#             matched_ids = get_matched_lost_items_id(text_embedding, image_embedding)
#             for matched_id in matched_ids:
#                 temp_post = await items.find_one({'_id': ObjectId(matched_id)})
#                 # Skip if the matched item belongs to the current user
#                 if temp_post['owner_mail'] == existing_user['mail']:
#                     continue
#
#                 temp_user_mail = temp_post['owner_mail']
#                 temp_user = await users.find_one({"mail": temp_user_mail})
#                 owner_socket_id = temp_user['socket_id']
#                 await items.update_one({"_id": ObjectId(matched_id)}, {"$push": {"matches": document_id}})
#                 # if owner_socket_id != '':
#                 #     await socket_server.emit('notification', data={
#                 #         "message": f"Your {temp_post['name']} has 1 new possible match"},
#                 #                              room=owner_socket_id)
#
#     except Exception as e:
#         response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
#         return {"message": "Please Retry querying for matches!"}
#
#     return {"message": "item uploaded successfully"}

class GetProfileBody(BaseModel):
    mail: str

@app.post('/getUser')
async def getUser(request: Request, response: Response, requested_user: GetProfileBody):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
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

    requested_user_email = requested_user.mail
    try:
        existing_user = await users.find_one(
            {'mail': requested_user_email},
            {
                '_id': 0,
                'password': 0,
                'socket_id': 0
            }
        )
        if existing_user is None:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"message": "User not found!"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal Server Error!"}

    return existing_user

class GetItemsBody(BaseModel):
    page: int

@app.post('/getItems')
async def getItems(request: Request, response: Response, get_items_body: GetItemsBody):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
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
        print(existing_user)
        if existing_user is None:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"message": "Unauthorized access!"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal Server Error!"}
    page = get_items_body.page
    page_size = 10
    if page <= 0:
        page = 1
    skip = (page-1)*page_size
    try:
        fetched_items = await items.find({'owner_mail': {'$ne': existing_user['mail']}}).skip(skip).limit(page_size).to_list(length=page_size)
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal Server Error!"}

    for item in fetched_items:
        item['_id'] = str(item['_id'])
    return fetched_items

@app.post('/checkUser')
async def checkUser(request: Request, response: Response):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"valid": False, "message": "Unauthorized Access!"}

    auth_token = req_headers['auth_token']
    try:
        data = jwt.decode(auth_token, os.getenv('JWT_KEY'), algorithms=["HS256"])
    except Exception as e:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"valid": False, "message": "Unauthorized access!"}

    try:
        existing_user = await users.find_one({'_id': ObjectId(data['_id'])})
        print(existing_user)
        if existing_user is None:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"valid": False, "message": "Unauthorized access!"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"valid": False, "message": "Internal Server Error!"}
    return {"valid": True}


@app.post("/getUserItems")
async def get_user_items(request: Request, response: Response):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "Unauthorized Access!"}

    auth_token = req_headers['auth_token']
    try:
        # Decode JWT token to get user information
        decoded = jwt.decode(auth_token, os.getenv("JWT_KEY"), algorithms=["HS256"])

        # Verify user exists
        existing_user = await users.find_one({'_id': ObjectId(decoded['_id'])})
        if existing_user is None:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"message": "Unauthorized access!"}

        user_mail = existing_user['mail']

        # Query the database for items owned by this user
        user_items = await items.find({"owner_mail": user_mail}).to_list(length=100)

        # Convert ObjectId to string for JSON serialization
        for item in user_items:
            item["_id"] = str(item["_id"])
            # Convert any other ObjectId fields if present
            if "matched" in item and item["matched"]:
                item["matched"] = [str(match_id) for match_id in item["matched"]]

        return {"status": "success", "items": user_items}

    except jwt.PyJWTError:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"message": "Unauthorized access!"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error, please try again later!"}


class ItemIdRequest(BaseModel):
    item_id: str


@app.post("/getMatchedItems")
async def get_matched_items(request: Request, response: Response, item_request: ItemIdRequest):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "Unauthorized Access!"}

    auth_token = req_headers['auth_token']
    try:
        # Decode JWT token to get user information
        decoded = jwt.decode(auth_token, os.getenv("JWT_KEY"), algorithms=["HS256"])

        # Verify user exists
        existing_user = await users.find_one({'_id': ObjectId(decoded['_id'])})
        if existing_user is None:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"message": "Unauthorized access!"}

        user_mail = existing_user['mail']

        # Validate that the item exists and belongs to the user
        item = await items.find_one({"_id": ObjectId(item_request.item_id), "owner_mail": user_mail})

        if not item:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"message": "Item not found or doesn't belong to the user"}

        # Check if the item has matched items
        matched_items = []
        if "matches" in item and item["matches"]:
            # Query all matched items
            matched_ids = [ObjectId(match_id) if isinstance(match_id, str) else match_id
                           for match_id in item["matches"]]

            matched_items = await items.find({"_id": {"$in": matched_ids}}).to_list(length=100)

            # Convert ObjectId to string for JSON serialization
            for matched_item in matched_items:
                matched_item["_id"] = str(matched_item["_id"])
                # Convert any other ObjectId fields if present
                if "matches" in matched_item and matched_item["matches"]:
                    matched_item["matches"] = [str(m_id) for m_id in matched_item["matches"]]

        return {"status": "success", "matched_items": matched_items}

    except jwt.PyJWTError:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"message": "Unauthorized access!"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error, please try again later!"}


class DeleteMatchedItemRequest(BaseModel):
    item_id: str
    matched_item_id: str


@app.post("/deleteMatchedItem")
async def delete_matched_item(request: Request, response: Response, delete_request: DeleteMatchedItemRequest):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "Unauthorized Access!"}

    auth_token = req_headers['auth_token']
    try:
        # Decode JWT token to get user information
        decoded = jwt.decode(auth_token, os.getenv("JWT_KEY"), algorithms=["HS256"])

        # Verify user exists
        existing_user = await users.find_one({'_id': ObjectId(decoded['_id'])})
        if existing_user is None:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"message": "Unauthorized access!"}

        user_mail = existing_user['mail']

        # Validate that the item exists and belongs to the user
        item = await items.find_one({"_id": ObjectId(delete_request.item_id), "owner_mail": user_mail})

        if not item:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"message": "Item not found or doesn't belong to the user"}

        # Check if the item has matched items and the specified matched item exists
        if "matches" not in item or not item["matches"] or ObjectId(delete_request.matched_item_id) not in item[
            "matches"]:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"message": "Matched item not found"}

        # Remove the matched item from the matched array
        await items.update_one(
            {"_id": ObjectId(delete_request.item_id)},
            {"$pull": {"matches": ObjectId(delete_request.matched_item_id)}}
        )

        return {"status": "success", "message": "Matched item removed successfully"}

    except jwt.PyJWTError:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"message": "Unauthorized access!"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": "Internal server error, please try again later!"}


@app.post("/getNotifications")
async def get_notifications(request: Request, response: Response):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "Unauthorized Access!"}

    auth_token = req_headers['auth_token']
    try:
        # Decode JWT token to get user information
        decoded = jwt.decode(auth_token, os.getenv("JWT_KEY"), algorithms=["HS256"])

        # Verify user exists
        existing_user = await users.find_one({'_id': ObjectId(decoded['_id'])})
        if existing_user is None:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {"message": "Unauthorized access!"}

        user_mail = existing_user['mail']

        # Get all items owned by the user
        user_items = await items.find({"owner_mail": user_mail}).to_list(length=100)

        notifications = []

        # For each item, process its matches
        for item in user_items:
            if "matches" in item and item["matches"]:
                # Get the matched items' details
                matched_ids = [ObjectId(match_id) if isinstance(match_id, str) else match_id
                               for match_id in item["matches"]]

                matched_items = await items.find({"_id": {"$in": matched_ids}}).to_list(length=100)

                for matched_item in matched_items:
                    # Get the owner details of the matched item
                    owner = await users.find_one(
                        {"mail": matched_item["owner_mail"]},
                        {"_id": 0, "name": 1, "phone": 1, "mail": 1}
                    )

                    notification = {
                        "item_id": str(item["_id"]),
                        "item_name": item["name"],
                        "item_state": item["state"],
                        "item_image": item["image"],
                        "matched_item_id": str(matched_item["_id"]),
                        "matched_item_name": matched_item["name"],
                        "matched_item_state": matched_item["state"],
                        "matched_item_description": matched_item["description"],
                        "matched_item_image": matched_item["image"],
                        "matched_item_timestamp": matched_item["timestamp"],
                        "owner_name": owner["name"] if owner else "Unknown",
                        "owner_phone": owner["phone"] if owner else "Unknown",
                        "owner_mail": owner["mail"] if owner else "Unknown",
                    }

                    notifications.append(notification)

        return {"status": "success", "notifications": notifications}

    except jwt.PyJWTError:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"message": "Unauthorized access!"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"Internal server error, please try again later! {str(e)}"}


@app.post('/update-phone')
async def update_phone(request: Request, response: Response, phone_update: dict):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
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

        # Validate phone number with regex
        phone_regex = re.compile(r'^\+?[1-9]\d{0,2}\d{6,14}$')
        if not phone_regex.match(phone_update.get('phone', '')):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"message": "Invalid phone number format"}

        # Update phone number
        result = await users.update_one(
            {'_id': ObjectId(data['_id'])},
            {'$set': {'phone': phone_update.get('phone')}}
        )

        if result.modified_count == 0:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"message": "Failed to update phone number"}

        return {"message": "Phone number updated successfully"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"Internal server error: {str(e)}"}


@app.delete('/delete-item/{item_id}')
async def delete_item(request: Request, response: Response, item_id: str):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
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

        # Find the item
        item = await items.find_one({'_id': ObjectId(item_id)})
        if item is None:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"message": "Item not found"}

        # Check if the user is the owner
        if item['owner_mail'] != existing_user['mail']:
            response.status_code = status.HTTP_403_FORBIDDEN
            return {"message": "You don't have permission to delete this item"}

        # Delete from MongoDB
        delete_result = await items.delete_one({'_id': ObjectId(item_id)})

        if delete_result.deleted_count == 0:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {"message": "Failed to delete item from database"}

        # Delete from Cloudinary
        try:
            # Extract public_id from the URL or use the item_id
            public_id = item_id  # Assuming you're using the item_id as the public_id
            cloudinary.uploader.destroy(public_id)
        except Exception as e:
            print(f"Error deleting from Cloudinary: {str(e)}")
            # Continue even if Cloudinary delete fails

        # Delete from Pinecone based on state
        try:
            if item['state']:  # Lost item
                delete_lost_item_description_in_pinecone_database(item_id)
                delete_lost_item_image_in_pinecone_database(item_id)
            else:  # Found item
                delete_found_item_description_in_pinecone_database(item_id)
                delete_found_item_image_in_pinecone_database(item_id)
        except Exception as e:
            print(f"Error deleting from Pinecone: {str(e)}")
            # Continue even if Pinecone delete fails

        # Also remove this item from any matches in other items
        try:
            await items.update_many(
                {"matches": item_id},
                {"$pull": {"matches": item_id}}
            )
        except Exception as e:
            print(f"Error removing item from matches: {str(e)}")

        return {"message": "Item deleted successfully"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"Internal server error: {str(e)}"}


@app.post('/getUserProfile')
async def get_user_profile(request: Request, response: Response):
    req_headers = dict(request.headers)
    if 'auth_token' not in req_headers:
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

        # Remove sensitive information like password
        if 'password' in existing_user:
            del existing_user['password']

        # Convert ObjectId to string for JSON serialization
        existing_user['_id'] = str(existing_user['_id'])

        return {"user": existing_user}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"Internal server error: {str(e)}"}


if __name__ == '__main__':
    PORT = int(os.getenv('PORT', 8000))
    uvicorn.run("main:app", host='0.0.0.0', port=PORT)


