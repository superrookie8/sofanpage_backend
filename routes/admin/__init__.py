from flask import Blueprint
from .admin_routes import admin_bp as admin_main_bp
from .profile_routes import profile_bp
from .stats_routes import stats_bp
from .photo_routes import photo_bp
from .news_routes import news_bp
from .schedule_routes import admin_schedule_bp
from .guestbook_routes import admin_guestbook_bp
from .event_routes import admin_event_bp

admin_bp = Blueprint('admin', __name__)
admin_bp.register_blueprint(admin_main_bp)
admin_bp.register_blueprint(profile_bp)
admin_bp.register_blueprint(stats_bp)
admin_bp.register_blueprint(photo_bp)
admin_bp.register_blueprint(news_bp)
admin_bp.register_blueprint(admin_schedule_bp)
admin_bp.register_blueprint(admin_guestbook_bp)
admin_bp.register_blueprint(admin_event_bp)
