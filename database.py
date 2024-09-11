from pymongo.mongo_client import MongoClient
import certifi
from config import Config
import gridfs

ca = certifi.where()
client = MongoClient(Config.MONGO_URI, tlsCAFile=certifi.where())
db = client.fanpage

fs_admin = gridfs.GridFS(db, collection='admin_photo')
fs_user = gridfs.GridFS(db, collection='user_photo')
fs_event = gridfs.GridFS(db, collection="event_photo")
fs_guestbooks = gridfs.GridFS(db, collection="guestbooks_photo")
fs_diary = gridfs.GridFS(db, collection='diary_photo')

users = db['users']
guestbooks = db['guestbooks']
admins = db['admin']
profiles = db['admin_profile']
admin_stats = db['admin_stats']
news = db['admin_news']
schedules = db['admin_schedules']
events = db['admin_events']
news_rookie = db['news_rookie']
news_jumpball = db['news_jumpball']
diaries = db['diaries']
