from pymongo.mongo_client import MongoClient
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
import certifi
import os

load_dotenv()

ca = certifi.where()
client = MongoClient(os.getenv("MONGO_URI"), tlsCAFile=certifi.where())
db = client.fanpage
admins = db['admin']

# 관리자 계정 생성
admin_username = "superrookie"
admin_password = "Diqtkq88**#@"
hashed_password = generate_password_hash(admin_password)

# 이미 존재하지 않는 경우에만 추가
if not admins.find_one({"username": admin_username}):
    admins.insert_one({
        "username": admin_username,
        "password": hashed_password
    })
    print("Admin account created")
else:
    print("Admin account already exists")

