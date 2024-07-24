from flask import Blueprint, request, jsonify
from database import fs_admin, fs_user
import base64

photo_bp = Blueprint('photo', __name__)

@photo_bp.route('/api/get/photos', methods=['GET'])
def get_photos_public():
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        skip = (page - 1) * page_size

        # Fetch total count of photos
        total_admin_photos = fs_admin._GridFS__files.count_documents({})
        total_photos = total_admin_photos

        # Fetch photos from admin collection
        admin_photos = fs_admin.find().skip(skip).limit(page_size)
        admin_photo_list = []
        for photo in admin_photos:
            image_data = fs_admin.get(photo._id).read()
            base64_img = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{base64_img}"
            admin_photo_list.append({
                "_id": str(photo._id),
                "filename": photo.filename,
                "base64": data_url,
                "url": f"/api/photos/{photo._id}"
            })

        # Fetch photos from user collection
        user_photos = fs_user.find().skip(skip).limit(page_size)
        user_photo_list = []
        for photo in user_photos:
            image_data = fs_user.get(photo._id).read()
            base64_img = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{base64_img}"
            user_photo_list.append({
                "_id": str(photo._id),
                "filename": photo.filename,
                "base64": data_url,
                "url": f"/api/photos/{photo._id}"
            })

        return jsonify({
            "admin_photos": admin_photo_list,
            "user_photos": user_photo_list,
            "total_photos": total_photos
        }), 200

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "Failed", "message": str(e)}), 500
