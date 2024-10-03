from flask import Blueprint
from .auth_routes import auth_bp
from .user_routes import user_bp
from .guestbook_routes import guestbook_bp
from .event_routes import event_bp
from .admin import admin_bp
from .photo_routes import photo_bp
from .schedule_routes import schedule_bp
from .stats_routes import stats_bp
from .newsrookie_routes import newsrookie_bp
from .newsjump_routes import newsjumpball_bp
from .news_routes import news_bp
from .diary_routes import diary_bp


bp = Blueprint('routes', __name__)
bp.register_blueprint(auth_bp)
bp.register_blueprint(user_bp)
bp.register_blueprint(guestbook_bp)
bp.register_blueprint(event_bp)
bp.register_blueprint(admin_bp)
bp.register_blueprint(photo_bp)
bp.register_blueprint(schedule_bp)
bp.register_blueprint(stats_bp)
bp.register_blueprint(newsrookie_bp)
bp.register_blueprint(newsjumpball_bp)
bp.register_blueprint(news_bp)
bp.register_blueprint(diary_bp)
