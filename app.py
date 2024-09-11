from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config
from routes import auth_bp, user_bp, guestbook_bp, event_bp, photo_bp, schedule_bp, stats_bp, newsrookie_bp, newsjumpball_bp, news_bp, diary_bp
from routes.admin.admin_routes import admin_bp
from routes.admin.profile_routes import profile_bp
from routes.admin.schedule_routes import admin_schedule_bp
from routes.admin.event_routes import admin_event_bp
from routes.admin.guestbook_routes import admin_guestbook_bp
from routes.admin.stats_routes import admin_stats_bp
from database import db

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.config.from_object(Config)

jwt = JWTManager(app)

app.config['db'] = db

app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(guestbook_bp)
app.register_blueprint(event_bp)
app.register_blueprint(photo_bp)
app.register_blueprint(admin_schedule_bp)
app.register_blueprint(schedule_bp)
app.register_blueprint(admin_event_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(admin_guestbook_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(admin_stats_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(newsrookie_bp)
app.register_blueprint(newsjumpball_bp)
app.register_blueprint(news_bp)
app.register_blueprint(diary_bp)

if __name__ == '__main__':
    print(app.url_map)
    app.run(debug=True, host='0.0.0.0', port=5001)
