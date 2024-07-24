from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required
from database import guestbooks, fs_guestbooks
from bson import ObjectId
import base64
from .admin_routes import admin_required

admin_guestbook_bp = Blueprint('guestbook_bp', __name__)

@admin_guestbook_bp.route('/api/admin/get_guestbook_entries', methods=['GET'])
@admin_required
def get_admin_guestbook_entries():
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        name_filter = request.args.get('name', None)
        skip = (page - 1) * page_size

        query = {}
        if name_filter:
            query['name'] = name_filter

        entries = guestbooks.find(query).sort('name', 1).skip(skip).limit(page_size)
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

@admin_guestbook_bp.route('/api/admin/get_guestbook_photo/<photo_id>', methods=['GET'])
@admin_required
def get_admin_guestbook_photo(photo_id):
    try:
        photo = fs_guestbooks.get(ObjectId(photo_id))
        data = photo.read()
        response = make_response(data)
        response.headers.set('Content-Type', photo.content_type)
        response.headers.set('Content-Disposition', 'inline', filename=photo.filename)
        return response
    except Exception as e:
        return jsonify({"status": "Failed", "message": str(e)}), 500

@admin_guestbook_bp.route('/api/admin/delete_guestbook_entry/<entry_id>', methods=['DELETE', 'OPTIONS'])
@admin_required
def delete_admin_guestbook_entry(entry_id):
    if request.method == 'OPTIONS':
        return jsonify({"message": "CORS preflight request successful"}), 200

    try:
        entry = guestbooks.find_one({"_id": ObjectId(entry_id)})
        if not entry:
            return jsonify({"message": "Entry not found"}), 404

        if entry.get('photo_id'):
            fs_guestbooks.delete(ObjectId(entry['photo_id']))

        guestbooks.delete_one({"_id": ObjectId(entry_id)})

        return jsonify({"message": "Entry deleted successfully"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
