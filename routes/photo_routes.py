from flask import Blueprint, request, jsonify
from database import fs_admin, fs_user
import base64

photo_bp = Blueprint('photo', __name__)

@photo_bp.route('/api/get/photos', methods=['GET'])
def get_photos_public():
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