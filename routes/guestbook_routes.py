from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import guestbooks, fs_guestbooks
from bson import ObjectId
import base64

guestbook_bp = Blueprint('guestbook', __name__)

@guestbook_bp.route('/api/post_guestbook', methods=['POST'])
def post_guestbook():
    try:
        name = request.form.get('name', '')
        message = request.form.get('message', '')
        date = request.form.get('date', '')

        if not name or not message:
            return jsonify({"message": "Name and message are required"}), 400

        guestbook_entry = {
            "name": name,
            "message": message,
            "date": date
        }

        photo = request.files.get('photo')
        if photo:
            photo_id = fs_guestbooks.put(photo, filename=f"{name}_photo.jpg")
            guestbook_entry["photo_id"] = str(photo_id)

        guestbooks.insert_one(guestbook_entry)
        return jsonify({"status": "Guestbook entry added"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@guestbook_bp.route('/api/get_guestbook_entries', methods=['GET'])
def get_guestbook_entries():
    try:
        entries = guestbooks.find().sort('date', -1)
        photo_entries = []
        no_photo_entries = []

        for entry in entries:
            entry['_id'] = str(entry['_id'])
            if entry.get('photo_id'):
                photo = fs_guestbooks.get(ObjectId(entry['photo_id']))
                photo_data = base64.b64encode(photo.read()).decode('utf-8')
                entry['photo_data'] = photo_data
                photo_entries.append(entry)
            else:
                no_photo_entries.append(entry)

        return jsonify({"photo_entries": photo_entries, "no_photo_entries": no_photo_entries}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@guestbook_bp.route('/api/delete/guestbook', methods=['DELETE'])
@jwt_required()
def delete_guestbook():
    try:
        nickname = get_jwt_identity()
        entry_id = request.args.get('entry_id')

        if not entry_id:
            return jsonify({"message": "Entry ID is required"}), 400

        guestbook_entry = guestbooks.find_one({"_id": ObjectId(entry_id), "name": nickname})

        if not guestbook_entry:
            return jsonify({"message": "Guestbook entry not found or you do not have permission to delete this entry"}), 404

        if "photo_id" in guestbook_entry:
            fs_guestbooks.delete(ObjectId(guestbook_entry["photo_id"]))

        guestbooks.delete_one({"_id": ObjectId(entry_id)})

        return jsonify({"message": "Guestbook entry deleted successfully"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@guestbook_bp.route('/api/get_user_guestbook_entries', methods=['GET'])
def get_user_guestbook_entries():
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        skip = (page - 1) * page_size
        user = request.args.get('user', None)

        query = {}
        if user:
            query['name'] = user

        entries = guestbooks.find(query).sort('date', -1).skip(skip).limit(page_size)
        entry_list = []
        for entry in entries:
            entry['_id'] = str(entry['_id'])
            if entry.get('photo_id'):
                photo = fs_guestbooks.get(ObjectId(entry['photo_id']))
                photo_data = base64.b64encode(photo.read()).decode('utf-8')
                entry['photo_data'] = photo_data
            entry_list.append(entry)

        total_entries = guestbooks.count_documents(query)
        return jsonify({"entries": entry_list, "total_entries": total_entries}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@guestbook_bp.route('/api/update_guestbook_entry', methods=['PUT'])
def update_guestbook_entry():
    try:
        entry_id = request.form.get('id')
        message = request.form.get('message')  # message는 필수

        if not entry_id:
            return jsonify({"message": "ID is required"}), 400
        if not message:
            return jsonify({"message": "Message is required"}), 400

        # message 필드만 업데이트
        updated_entry = {
            "message": message,  # 필수 수정
        }

        # 사진 업데이트 처리
        photo = request.files.get('photo')
        if photo:
            # 기존 엔트리 조회
            old_entry = guestbooks.find_one({"_id": ObjectId(entry_id)})
            if old_entry is None:
                return jsonify({"message": "Entry not found"}), 404

            # 기존 photo_id가 있으면 삭제 후 새로 업로드
            if old_entry.get('photo_id'):
                fs_guestbooks.delete(ObjectId(old_entry['photo_id']))
            photo_id = fs_guestbooks.put(photo, filename=f"{old_entry['name']}_photo.jpg")
            updated_entry['photo_id'] = str(photo_id)

        result = guestbooks.update_one(
            {"_id": ObjectId(entry_id)},
            {"$set": updated_entry}
        )

        if result.matched_count == 0:
            return jsonify({"message": "Entry not found"}), 404

        return jsonify({"message": "Entry updated successfully"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500



