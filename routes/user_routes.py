from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import users, fs_user
from bson import ObjectId
from PIL import Image
from io import BytesIO
import base64
import gridfs.errors
import logging

user_bp = Blueprint('user', __name__)
logger = logging.getLogger(__name__)

@user_bp.route('/api/put/userinfo', methods=['PUT'])
@jwt_required()
def update_profile():
    try:
        nickname = get_jwt_identity()
        user = users.find_one({"nickname": nickname})
        if not user:
            return jsonify({"message": "User not found"}), 404

        description = request.form.get("description")
        photo = request.files.get("photo")

        update_data = {}

        if description:
            update_data["description"] = description
        if photo:
            photo_id = fs_user.put(photo, filename=f"{nickname}_profile_photo.jpg")
            update_data["photo"] = f"/api/photo/{photo_id}"

        if not update_data:
            return jsonify({"message": "No data to update"}), 400

        users.update_one({"_id": user['_id']}, {"$set": update_data})

        return jsonify(update_data), 200
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({"message": str(e)}), 500

@user_bp.route('/api/get/userinfo', methods=['GET'])
@jwt_required()
def get_user_info():
    try:
        nickname = get_jwt_identity()
        user = users.find_one({"nickname": nickname})
        if not user:
            logger.debug("User not found")
            return jsonify({"message": "User not found"}), 404

        user_info = {
            "nickname": user.get("nickname", ""),
            "description": user.get("description", ""),
            "photoUrl": ""
        }

        if "photo" in user and user["photo"]:
            try:
                photo_id_str = user["photo"].split('/')[-1]
                photo_id = ObjectId(photo_id_str)
                photo_file = fs_user.get(photo_id)

                image = Image.open(photo_file)
                if image.mode == 'RGBA':
                    image = image.convert('RGB')
                buffered = BytesIO()
                image.save(buffered, format="JPEG", quality=50)
                photo_data = base64.b64encode(buffered.getvalue()).decode('utf-8')

                user_info["photoUrl"] = f"data:image/jpeg;base64,{photo_data}"
            except gridfs.errors.NoFile:
                user_info["photoUrl"] = ""
                logger.debug("NoFile error: Photo not found in GridFS")
            except Exception as e:
                logger.debug(f"Error processing image: {str(e)}")
                user_info["photoUrl"] = ""

        logger.debug(f"User info fetched: {user_info}")
        return jsonify(user_info), 200
    except Exception as e:
        logger.debug(f"Error: {str(e)}")
        return jsonify({"message": str(e)}), 500
