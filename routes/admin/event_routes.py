from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from database import events, fs_event,db
from bson import ObjectId
import base64
import gridfs.errors
import datetime
from .admin_routes import admin_required

admin_event_bp = Blueprint('admin_event', __name__)

@admin_event_bp.route('/api/admin/get/events', methods=['GET'])
@admin_required
def get_admin_events():
    try:
        events = list(db.admin_events.find({}))
        for event in events:
            event["_id"] = str(event["_id"])  # ObjectId를 문자열로 변환
            if "check_1" in event or "check_2" in event or "check_3" in event:
                check_fields = {
                    "check_1": event.get("check_1", ""),
                    "check_2":
                event.get("check_2", ""),
                    "check_3": event.get("check_3", "")
                }
                event["checkFields"] = check_fields

            if "photos" in event:
                photo_ids = event["photos"]
                photos = []
                for photo_id in photo_ids:
                    try:
                        photo_file = fs_event.get(ObjectId(photo_id))
                        photo_data = base64.b64encode(photo_file.read()).decode('utf-8')
                        photos.append(f"data:{photo_file.content_type};base64,{photo_data}")
                    except gridfs.errors.NoFile:
                        continue
                event["photos"] = photos
            else:
                event["photos"] = []

        return jsonify({"events": events}), 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"message": str(e)}), 500

@admin_event_bp.route('/api/admin/postevents', methods=['POST'])
@admin_required
def post_events():
    try:
        title = request.form.get('title', '')
        url = request.form.get('url', '')
        description = request.form.get('description', '')

        check_fields = {}
        for key in request.form.keys():
            if key.startswith('check_'):
                check_fields[key] = request.form.get(key, '')

        event_data = {
            "title": title,
            "url": url,
            "description": description,
            "date": datetime.datetime.utcnow(),
            **check_fields
        }

        event_id = events.insert_one(event_data).inserted_id

        files = request.files.getlist("photos")
        photo_ids = []
        for file in files:
            file_id = fs_event.put(file, filename=file.filename, content_type=file.content_type)
            photo_ids.append(str(file_id))

        events.update_one(
            {"_id": event_id},
            {"$set": {"photos": photo_ids}}
        )

        return jsonify({"message": "Event and photos uploaded successfully"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@admin_event_bp.route('/api/admin/delete/eventphoto', methods=['DELETE'])
@admin_required
def delete_photo():
    try:
        data = request.get_json()
        event_id = data['eventId']
        photo_index = data['photoIndex']

        event = events.find_one({"_id": ObjectId(event_id)})
        if not event:
            return jsonify({"message": "Event not found"}), 404

        photo_id = event['photos'][photo_index]

        fs_event.delete(ObjectId(photo_id))

        events.update_one(
            {"_id": ObjectId(event_id)},
            {"$pull": {"photos": photo_id}}
        )

        return jsonify({"message": "Photo deleted successfully"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@admin_event_bp.route('/api/admin/delete/event', methods=['DELETE'])
@admin_required
def delete_event():
    try:
        data = request.get_json()
        event_id = data['eventId']

        event = events.find_one({"_id": ObjectId(event_id)})
        if not event:
            return jsonify({"message": "Event not found"}), 404

        if "photos" in event:
            for photo_id in event["photos"]:
                try:
                    fs_event.delete(ObjectId(photo_id))
                except gridfs.errors.NoFile:
                    continue

        events.delete_one({"_id": ObjectId(event_id)})

        return jsonify({"message": "Event and its photos deleted successfully"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
