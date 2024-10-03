from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required
from database import fs_admin, fs_user, fs_event, fs_guestbooks
from bson import ObjectId
import base64
import gridfs.errors

admin_photo_bp = Blueprint('admin_photo_bp', __name__)

@admin_photo_bp.route('/api/admin/postphoto', methods=['POST'])
@jwt_required()
def post_photo():
    try:
        files = request.files.getlist("photos")
        for file in files:
            fs_admin.put(file, filename=file.filename, content_type=file.content_type)
        return jsonify({"message": "Photos uploaded successfully"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@admin_photo_bp.route('/api/admin/get/photo/<photo_id>', methods=['GET'])
@jwt_required()
def get_photo(photo_id):
    try:
        try:
            file = fs_admin.get(ObjectId(photo_id))
        except gridfs.errors.NoFile:
            file = fs_user.get(ObjectId(photo_id))

        data = file.read()

        response = make_response(data)
        response.headers.set('Content-Type', file.content_type)
        response.headers.set('Content-Disposition', 'inline', filename=file.filename)
        
        return response

    except Exception as e:
        return jsonify({"status": "Failed", "message": str(e)}), 500

@admin_photo_bp.route('/api/admin/get/photos', methods=['GET'])
# @jwt_required()
def get_photos():
    try:
        # token = request.headers.get('Authorization').split()[1]

        admin_photos = fs_admin.find()
        admin_photo_list = []
        for photo in admin_photos:
            image_data = fs_admin.get(photo._id).read()
            base64_img = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{base64_img}"
            admin_photo_list.append({
                "_id": str(photo._id),
                "filename": photo.filename,
                "base64": data_url,
                # "url": f"/api/admin/get/photo/{photo._id}?token={token}"
                "url": f"/api/admin/get/photo/{photo._id}"
            })

        user_photos = fs_user.find()
        user_photo_list = []
        for photo in user_photos:
            image_data = fs_user.get(photo._id).read()
            base64_img = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{base64_img}"
            user_photo_list.append({
                "_id": str(photo._id),
                "filename": photo.filename,
                "base64": data_url,
                # "url": f"/api/admin/get/photo/{photo._id}?token={token}"
                "url": f"/api/admin/get/photo/{photo._id}"
            })

        return jsonify({"admin_photos": admin_photo_list, "user_photos": user_photo_list}), 200

    except Exception as e:
        return jsonify({"status": "Failed", "message": str(e)}), 500

@admin_photo_bp.route('/api/admin/deletephoto', methods=['DELETE'])
@jwt_required()
def delete_photos():
    try:
        data = request.get_json()
        photo_ids = data.get('photoIds', [])
        
        if not photo_ids:
            return jsonify({"message": "No photo IDs provided"}), 400

        for photo_id in photo_ids:
            if fs_admin.exists({"_id": ObjectId(photo_id)}):
                fs_admin.delete(ObjectId(photo_id))
            elif fs_user.exists({"_id": ObjectId(photo_id)}):
                fs_user.delete(ObjectId(photo_id))
            else:
                return jsonify({"message": f"Photo with ID {photo_id} does not exist"}), 404

        return jsonify({"message": "Photos deleted successfully"}), 200

    except Exception as e:
        return jsonify({"message": "Failed to delete photos", "error": str(e)}), 500
