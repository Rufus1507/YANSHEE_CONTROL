"""
SQLAlchemy ORM models for all project tables.
"""
import sqlalchemy as sa
from database.db import Base


class User(Base):
    __tablename__ = "users"
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    user_id = sa.Column(sa.String, unique=True, nullable=False)
    full_name = sa.Column(sa.String, nullable=False)
    role = sa.Column(sa.String, nullable=False)
    note = sa.Column(sa.String, nullable=True)
    created_at = sa.Column(sa.String)
    updated_at = sa.Column(sa.String)
    is_active = sa.Column(sa.Integer, default=1, nullable=False)


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    user_id = sa.Column(sa.String, nullable=False)
    embedding = sa.Column(sa.LargeBinary, nullable=False)
    angle_label = sa.Column(sa.String, nullable=True)
    quality_score = sa.Column(sa.Float, nullable=True)
    model_name = sa.Column(sa.String, nullable=True)
    created_at = sa.Column(sa.String)


class RecognitionLog(Base):
    __tablename__ = "recognition_logs"
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    user_id = sa.Column(sa.String, nullable=True)
    full_name = sa.Column(sa.String, nullable=True)
    role = sa.Column(sa.String, nullable=True)
    result = sa.Column(sa.String, nullable=True)
    best_score = sa.Column(sa.Float, nullable=True)
    second_score = sa.Column(sa.Float, nullable=True)
    threshold = sa.Column(sa.Float, nullable=True)
    confidence = sa.Column(sa.Float, nullable=True)
    liveness_passed = sa.Column(sa.Integer, nullable=True)
    processing_time_ms = sa.Column(sa.Float, nullable=True)
    frame_id = sa.Column(sa.Integer, nullable=True)
    robot_action = sa.Column(sa.String, nullable=True)
    robot_status = sa.Column(sa.String, nullable=True)
    created_at = sa.Column(sa.String)


class SystemLog(Base):
    __tablename__ = "system_logs"
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    level = sa.Column(sa.String)
    module = sa.Column(sa.String)
    message = sa.Column(sa.String)
    created_at = sa.Column(sa.String)


class RobotAction(Base):
    __tablename__ = "robot_actions"
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    role = sa.Column(sa.String)
    speech_text = sa.Column(sa.String)
    motion_name = sa.Column(sa.String)
    enabled = sa.Column(sa.Integer, default=1)
