import uuid
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    calculations = db.relationship('Calculation', backref='user', lazy=True, cascade='all, delete-orphan')


class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spoolman_url = db.Column(db.String(256), default='')
    default_markup = db.Column(db.Integer, default=20)
    default_vat = db.Column(db.Float, default=19.0)
    currency = db.Column(db.String(10), default='€')
    default_prep_cost_per_hour = db.Column(db.Float, default=15.0)
    default_postprocessing_cost_per_hour = db.Column(db.Float, default=15.0)
    api_key = db.Column(db.String(64), default='')
    slicer_default_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    ftp_host = db.Column(db.String(256), default='')
    ftp_access_code = db.Column(db.String(256), default='')
    ftp_sync_enabled = db.Column(db.Boolean, default=False)


class PrinterProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    purchase_price = db.Column(db.Float, default=0)
    investment_return_years = db.Column(db.Float, default=2)
    daily_usage_hours = db.Column(db.Float, default=6)
    repair_cost_percent = db.Column(db.Float, default=5)
    power_consumption = db.Column(db.Float, default=100)
    energy_cost_per_kwh = db.Column(db.Float, default=0.30)


class Calculation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    job_name = db.Column(db.String(200), default='')
    printer_profile_id = db.Column(db.Integer, db.ForeignKey('printer_profile.id'), nullable=True)

    # Print Info
    printing_time_hours = db.Column(db.Integer, default=0)
    printing_time_minutes = db.Column(db.Integer, default=0)
    filament_weight_grams = db.Column(db.Float, default=0)
    preview_image = db.Column(db.Text, nullable=True)
    preview_images = db.Column(db.JSON, default=list)

    # Filament
    filament_type = db.Column(db.String(50), default='PLA')
    filament_name = db.Column(db.String(200), default='')
    spool_price = db.Column(db.Float, default=0)
    spool_weight = db.Column(db.Float, default=1000)
    markup_percent = db.Column(db.Float, default=20)
    filament_cost = db.Column(db.Float, default=0)

    # Electricity
    electricity_enabled = db.Column(db.Boolean, default=False)
    power_consumption = db.Column(db.Float, default=0)
    energy_cost_per_kwh = db.Column(db.Float, default=0.30)
    electricity_cost = db.Column(db.Float, default=0)

    # Labor
    labor_enabled = db.Column(db.Boolean, default=False)
    prep_time_minutes = db.Column(db.Float, default=0)
    prep_cost_per_hour = db.Column(db.Float, default=15)
    postprocessing_time_minutes = db.Column(db.Float, default=0)
    postprocessing_cost_per_hour = db.Column(db.Float, default=15)
    labor_cost = db.Column(db.Float, default=0)

    # Machine
    machine_enabled = db.Column(db.Boolean, default=False)
    machine_purchase_price = db.Column(db.Float, default=0)
    machine_return_years = db.Column(db.Float, default=2)
    machine_daily_hours = db.Column(db.Float, default=6)
    machine_repair_percent = db.Column(db.Float, default=5)
    machine_cost = db.Column(db.Float, default=0)

    # Multiple filaments: [{name, spool_price, spool_weight, grams_used, filament_type, location}]
    filaments = db.Column(db.JSON, default=list)

    # Other costs
    other_costs = db.Column(db.JSON, default=list)

    # Final
    vat_percent = db.Column(db.Float, default=19)
    total_price = db.Column(db.Float, default=0)
    final_price_override = db.Column(db.Float, nullable=True)

    # Status: 'pending' (from slicer) or 'confirmed' (normal)
    status = db.Column(db.String(20), default='confirmed', nullable=False)

    printer_profile = db.relationship('PrinterProfile', backref='calculations')


class PrinterFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(500), unique=True, nullable=False)
    first_seen_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    processed = db.Column(db.Boolean, default=False)
    calculation_id = db.Column(db.Integer, db.ForeignKey('calculation.id'), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    modified_at = db.Column(db.DateTime, nullable=True)
    # Parsed metadata for display
    preview_image = db.Column(db.Text, nullable=True)
    preview_images = db.Column(db.JSON, default=list)
    printing_time_hours = db.Column(db.Integer, default=0)
    printing_time_minutes = db.Column(db.Integer, default=0)
    filament_weight_grams = db.Column(db.Float, default=0)
    filament_type = db.Column(db.String(50), default='')

    calculation = db.relationship('Calculation', backref='printer_file')
