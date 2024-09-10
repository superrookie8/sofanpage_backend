from flask import Blueprint, request, jsonify
from database import events, fs_event
from bson import ObjectId
import base64
import gridfs.errors

event_bp = Blueprint('event', __name__)

@event_bp.route('/api/get/event-list', methods=['GET'])
def get_event_list():
    try:
        # date 필드를 기준으로 최신순으로 정렬 (-1)
        events_list = list(events.find({}, {"_id": 1, "title": 1, "url": 1, "description": 1, "date": 1, "check_1": 1, "check_2": 1, "check_3": 1, "photos": 1}).sort("date", -1))
        
        # _id를 문자열로 변환
        for event in events_list:
            event["_id"] = str(event["_id"])

        return jsonify({"events": events_list}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@event_bp.route('/api/get/event-detail/<event_id>', methods=['GET'])
def get_event_detail(event_id):
    try:
        event = events.find_one({"_id": ObjectId(event_id)})
        if event:
            event["_id"] = str(event["_id"])
            check_fields = {
                "check_1": event.get("check_1", ""),
                "check_2": event.get("check_2", ""),
                "check_3": event.get("check_3", "")
            }
            event["checkFields"] = check_fields
            event["photos"] = []

            return jsonify({"event": event}), 200
        else:
            return jsonify({"message": "Event not found"}), 404
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@event_bp.route('/api/get/event-photos/<event_id>', methods=['GET'])
def get_event_photos(event_id):
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 5))

        event = events.find_one({"_id": ObjectId(event_id)})
        if event and "photos" in event:
            photo_ids = event["photos"]
            total_photos = len(photo_ids)
            start = (page - 1) * page_size
            end = start + page_size

            photos = []
            for photo_id in photo_ids[start:end]:
                try:
                    photo_file = fs_event.get(ObjectId(photo_id))
                    photo_data = base64.b64encode(photo_file.read()).decode('utf-8')
                    photos.append(f"data:{photo_file.content_type};base64,{photo_data}")
                except gridfs.errors.NoFile:
                    continue

            total_pages = (total_photos + page_size - 1) // page_size

            return jsonify({
                "photos": photos,
                "total_photos": total_photos,
                "total_pages": total_pages,
                "page": page,
                "page_size": page_size
            }), 200
        else:
            return jsonify({
                "photos": [],
                "total_photos": 0,
                "total_pages": 0,
                "page": 1,
                "page_size": page_size
            }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
