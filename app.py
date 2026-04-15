import json
import logging
import os
import uuid
from datetime import datetime, timezone
from functools import wraps
from io import BytesIO

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_file, url_for)
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from werkzeug.security import check_password_hash, generate_password_hash

from sqlalchemy import text

from config import Config
from models import Calculation, PrinterFile, PrinterProfile, Settings, User, db
from utils.calc_helpers import _float, _recalculate
from utils.parser import parse_file
from utils.spoolman import get_spools

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s %(message)s')

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Bitte melde dich an.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def get_settings():
    s = Settings.query.first()
    if not s:
        s = Settings()
        db.session.add(s)
        db.session.commit()
    return s


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@app.before_request
def check_setup():
    if request.endpoint in ('setup', 'static', 'service_worker', 'manifest'):
        return
    if User.query.count() == 0 and request.endpoint != 'setup':
        return redirect(url_for('setup'))


@app.context_processor
def inject_globals():
    if current_user.is_authenticated:
        return {'app_settings': get_settings()}
    return {'app_settings': None}


# ── Auth ─────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('calculation_new'))
    if User.query.count() == 0:
        return redirect(url_for('setup'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            app.logger.info("User '%s' logged in", username)
            return redirect(url_for('calculation_new'))
        app.logger.warning("Failed login attempt for user '%s'", username)
        flash('Ungültiger Benutzername oder Passwort.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if User.query.count() > 0:
        abort(404)
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Benutzername und Passwort sind erforderlich.', 'danger')
        elif len(password) < 4:
            flash('Passwort muss mindestens 4 Zeichen lang sein.', 'danger')
        else:
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                is_admin=True,
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            app.logger.info("Initial setup completed, admin user '%s' created", username)
            flash('Setup abgeschlossen! Willkommen.', 'success')
            return redirect(url_for('calculation_new'))
    return render_template('setup.html')


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')
        if not check_password_hash(current_user.password_hash, current_pw):
            flash('Aktuelles Passwort ist falsch.', 'danger')
        elif new_pw != confirm_pw:
            flash('Neue Passwörter stimmen nicht überein.', 'danger')
        elif len(new_pw) < 4:
            flash('Passwort muss mindestens 4 Zeichen lang sein.', 'danger')
        else:
            current_user.password_hash = generate_password_hash(new_pw)
            db.session.commit()
            flash('Passwort erfolgreich geändert.', 'success')
            return redirect(url_for('calculation_new'))
    return render_template('change_password.html')


# ── Calculations ─────────────────────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('calculation_new'))
    return redirect(url_for('login'))


@app.route('/calculation/new', methods=['GET', 'POST'])
@login_required
def calculation_new():
    settings = get_settings()
    printers = PrinterProfile.query.all()
    if request.method == 'POST':
        calc = _save_calculation(None, request.form)
        app.logger.info("Calculation created: id=%s, job='%s'", calc.id, calc.job_name)
        flash('Kalkulation gespeichert.', 'success')
        return redirect(url_for('calculations'))
    default_printer = PrinterProfile.query.filter_by(is_default=True).first()
    return render_template('calculation_form.html', calculation=None,
                           printers=printers, settings=settings, edit=False,
                           default_printer_id=default_printer.id if default_printer else None)


@app.route('/calculation/<int:calc_id>/edit', methods=['GET', 'POST'])
@login_required
def calculation_edit(calc_id):
    calc = Calculation.query.get_or_404(calc_id)
    if calc.user_id != current_user.id:
        abort(403)
    settings = get_settings()
    printers = PrinterProfile.query.all()
    if request.method == 'POST':
        _save_calculation(calc, request.form)
        app.logger.info("Calculation updated: id=%s, job='%s'", calc.id, calc.job_name)
        flash('Kalkulation aktualisiert.', 'success')
        return redirect(url_for('calculations'))
    return render_template('calculation_form.html', calculation=calc,
                           printers=printers, settings=settings, edit=True)


@app.route('/calculations')
@login_required
def calculations():
    all_calcs = (Calculation.query
                 .filter_by(user_id=current_user.id)
                 .order_by(Calculation.updated_at.desc())
                 .all())
    settings = get_settings()
    return render_template('calculations.html',
                           calculations=all_calcs, settings=settings)


@app.route('/calculation/<int:calc_id>/delete', methods=['POST'])
@login_required
def calculation_delete(calc_id):
    calc = Calculation.query.get_or_404(calc_id)
    if calc.user_id != current_user.id:
        abort(403)
    app.logger.info("Calculation deleted: id=%s, job='%s'", calc.id, calc.job_name)
    db.session.delete(calc)
    db.session.commit()
    flash('Kalkulation gelöscht.', 'success')
    return redirect(url_for('calculations'))


@app.route('/calculation/<int:calc_id>/pdf')
@login_required
def calculation_pdf(calc_id):
    calc = Calculation.query.get_or_404(calc_id)
    if calc.user_id != current_user.id:
        abort(403)
    s = get_settings()
    cur = s.currency
    try:
        from fpdf import FPDF
    except ImportError:
        flash('PDF-Export nicht verfügbar (fpdf2 fehlt).', 'danger')
        return redirect(url_for('calculations'))

    # Map currency symbols to latin-1 safe equivalents for PDF
    currency_map = {'€': 'EUR', '£': 'GBP', '¥': 'JPY'}
    cur = currency_map.get(cur, cur)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header
    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_text_color(240, 112, 64)
    pdf.cell(0, 12, 'PrintCostCalc', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(128, 128, 128)
    created = calc.created_at.strftime('%d.%m.%Y %H:%M') if calc.created_at else '-'
    pdf.cell(0, 5, f'Erstellt: {created}', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)

    # Job name
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(51, 51, 51)
    pdf.cell(0, 8, calc.job_name or 'Ohne Name', new_x='LMARGIN', new_y='NEXT')
    pdf.set_draw_color(240, 112, 64)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # Preview image (centered below job name)
    if calc.preview_image:
        try:
            import base64 as b64mod
            img_data = b64mod.b64decode(calc.preview_image)
            img_buf = BytesIO(img_data)
            img_w = 45
            img_x = (210 - img_w) / 2
            pdf.image(img_buf, x=img_x, y=pdf.get_y(), w=img_w)
            pdf.ln(img_w + 4)
        except Exception:
            pdf.ln(2)
    else:
        pdf.ln(2)

    def section(title):
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(240, 112, 64)
        pdf.cell(0, 7, title, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(1)

    def row(label, value):
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(95, 6, label)
        pdf.set_text_color(51, 51, 51)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, str(value), align='R', new_x='LMARGIN', new_y='NEXT')

    total_h = calc.printing_time_hours + calc.printing_time_minutes / 60

    section('Druckdaten')
    row('Druckzeit', f'{calc.printing_time_hours} Std {calc.printing_time_minutes} Min')
    row('Filamentgewicht', f'{calc.filament_weight_grams:.1f} g')
    if calc.printer_profile:
        row('Drucker', calc.printer_profile.name)
    pdf.ln(3)

    # Determine costs for PDF display
    other_total = sum(i.get('cost', 0) for i in (calc.other_costs or []) if isinstance(i, dict))
    vat = calc.vat_percent or 0
    pdf_labor = calc.labor_cost

    # If price was overridden, adjust labor costs so the total adds up cleanly
    has_override = (calc.final_price_override is not None
                    and calc.final_price_override > 0)
    if has_override:
        netto = round(calc.final_price_override / (1 + vat / 100), 2)
        fixed_costs = (round(calc.filament_cost, 2)
                       + round(calc.electricity_cost, 2)
                       + round(calc.machine_cost, 2)
                       + round(other_total, 2))
        pdf_labor = round(netto - fixed_costs, 2)
        if pdf_labor < 0:
            pdf_labor = 0

    section('Kostenaufstellung')
    row('Filamentkosten', f'{calc.filament_cost:.2f} {cur}')
    if calc.electricity_enabled and calc.electricity_cost > 0:
        row('Stromkosten', f'{calc.electricity_cost:.2f} {cur}')
    if pdf_labor > 0:
        row('Arbeitskosten', f'{pdf_labor:.2f} {cur}')
    if calc.machine_enabled and calc.machine_cost > 0:
        row('Maschinenkosten', f'{calc.machine_cost:.2f} {cur}')
    if other_total > 0:
        row('Sonstige Kosten', f'{other_total:.2f} {cur}')
    pdf.ln(3)

    # Total
    subtotal = (calc.filament_cost + calc.electricity_cost
                + pdf_labor + calc.machine_cost + other_total)

    pdf.ln(4)
    pdf.set_draw_color(240, 112, 64)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(128, 128, 128)
    if vat > 0:
        # Bei Override: Netto/MwSt vom Endpreis rückrechnen, damit alles aufgeht
        endpreis = calc.total_price
        netto = round(endpreis / (1 + vat / 100), 2)
        vat_amount = round(endpreis - netto, 2)
        pdf.cell(95, 6, 'Zwischensumme (netto)')
        pdf.cell(0, 6, f'{netto:.2f} {cur}', align='R', new_x='LMARGIN', new_y='NEXT')
        pdf.cell(95, 6, f'MwSt. ({vat:.1f}%)')
        pdf.cell(0, 6, f'{vat_amount:.2f} {cur}', align='R', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(240, 112, 64)
    pdf.cell(95, 10, 'Endpreis')
    pdf.cell(0, 10, f'{calc.total_price:.2f} {cur}', align='R', new_x='LMARGIN', new_y='NEXT')

    buf = BytesIO()
    pdf.output(buf)
    buf.seek(0)
    name = calc.job_name or str(calc.id)
    return send_file(buf, mimetype='application/pdf',
                     download_name=f'Kalkulation_{name}.pdf',
                     as_attachment=False)


# ── Printers ─────────────────────────────────────────────────────────────

@app.route('/printers')
@login_required
def printers():
    profiles = PrinterProfile.query.all()
    return render_template('printers.html', printers=profiles)


@app.route('/printers/new', methods=['GET', 'POST'])
@login_required
def printer_new():
    if request.method == 'POST':
        is_default = request.form.get('is_default') == 'on'
        if is_default:
            PrinterProfile.query.update({PrinterProfile.is_default: False})
        p = PrinterProfile(
            name=request.form.get('name', '').strip(),
            is_default=is_default,
            purchase_price=_float(request.form.get('purchase_price'), 0),
            investment_return_years=_float(request.form.get('investment_return_years'), 2),
            daily_usage_hours=_float(request.form.get('daily_usage_hours'), 6),
            repair_cost_percent=_float(request.form.get('repair_cost_percent'), 5),
            power_consumption=_float(request.form.get('power_consumption'), 100),
            energy_cost_per_kwh=_float(request.form.get('energy_cost_per_kwh'), 0.30),
        )
        db.session.add(p)
        db.session.commit()
        app.logger.info("Printer profile created: id=%s, name='%s'", p.id, p.name)
        flash('Druckerprofil erstellt.', 'success')
        return redirect(url_for('printers'))
    return render_template('printer_form.html', printer=None, edit=False)


@app.route('/printers/<int:printer_id>/edit', methods=['GET', 'POST'])
@login_required
def printer_edit(printer_id):
    p = PrinterProfile.query.get_or_404(printer_id)
    if request.method == 'POST':
        is_default = request.form.get('is_default') == 'on'
        if is_default:
            PrinterProfile.query.filter(PrinterProfile.id != p.id).update(
                {PrinterProfile.is_default: False})
        p.name = request.form.get('name', '').strip()
        p.is_default = is_default
        p.purchase_price = _float(request.form.get('purchase_price'), 0)
        p.investment_return_years = _float(request.form.get('investment_return_years'), 2)
        p.daily_usage_hours = _float(request.form.get('daily_usage_hours'), 6)
        p.repair_cost_percent = _float(request.form.get('repair_cost_percent'), 5)
        p.power_consumption = _float(request.form.get('power_consumption'), 100)
        p.energy_cost_per_kwh = _float(request.form.get('energy_cost_per_kwh'), 0.30)
        db.session.commit()
        app.logger.info("Printer profile updated: id=%s, name='%s'", p.id, p.name)
        flash('Druckerprofil aktualisiert.', 'success')
        return redirect(url_for('printers'))
    return render_template('printer_form.html', printer=p, edit=True)


@app.route('/printers/<int:printer_id>/delete', methods=['POST'])
@login_required
def printer_delete(printer_id):
    p = PrinterProfile.query.get_or_404(printer_id)
    app.logger.info("Printer profile deleted: id=%s, name='%s'", p.id, p.name)
    db.session.delete(p)
    db.session.commit()
    flash('Druckerprofil gelöscht.', 'success')
    return redirect(url_for('printers'))


# ── Settings ─────────────────────────────────────────────────────────────

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_page():
    s = get_settings()
    if request.method == 'POST':
        s.spoolman_url = request.form.get('spoolman_url', '').strip()
        s.default_markup = int(_float(request.form.get('default_markup'), 20))
        s.default_vat = _float(request.form.get('default_vat'), 19)
        s.currency = request.form.get('currency', '€').strip() or '€'
        s.default_prep_cost_per_hour = _float(request.form.get('default_prep_cost_per_hour'), 15)
        s.default_postprocessing_cost_per_hour = _float(
            request.form.get('default_postprocessing_cost_per_hour'), 15)
        s.ftp_host = request.form.get('ftp_host', '').strip()
        s.ftp_access_code = request.form.get('ftp_access_code', '').strip()
        s.ftp_sync_enabled = request.form.get('ftp_sync_enabled') == 'on'
        db.session.commit()
        app.logger.info("Settings saved by user '%s'", current_user.username)
        flash('Einstellungen gespeichert.', 'success')
        return redirect(url_for('settings_page'))
    return render_template('settings.html', settings=s)


# ── Admin ────────────────────────────────────────────────────────────────

@app.route('/admin/users', methods=['GET', 'POST'])
@admin_required
def admin_users():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Benutzername und Passwort erforderlich.', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('Benutzername existiert bereits.', 'danger')
        else:
            user = User(username=username,
                        password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            app.logger.info("Admin created user '%s'", username)
            flash(f'Benutzer „{username}" erstellt.', 'success')
    users = User.query.order_by(User.created_at).all()
    return render_template('users.html', users=users)


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_user_delete(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    if user.id == current_user.id:
        flash('Du kannst dich nicht selbst löschen.', 'danger')
    else:
        app.logger.info("Admin deleted user '%s'", user.username)
        db.session.delete(user)
        db.session.commit()
        flash(f'Benutzer „{user.username}" gelöscht.', 'success')
    return redirect(url_for('admin_users'))


# ── Import / Export ──────────────────────────────────────────────────────

@app.route('/export')
@login_required
def export_data():
    calcs = Calculation.query.filter_by(user_id=current_user.id).all()
    profiles = PrinterProfile.query.all()
    s = get_settings()

    data = {
        'version': 1,
        'exported_at': datetime.now(timezone.utc).isoformat(),
        'settings': {
            'spoolman_url': s.spoolman_url,
            'default_markup': s.default_markup,
            'default_vat': s.default_vat,
            'currency': s.currency,
            'default_prep_cost_per_hour': s.default_prep_cost_per_hour,
            'default_postprocessing_cost_per_hour': s.default_postprocessing_cost_per_hour,
            'ftp_host': s.ftp_host,
            'ftp_access_code': s.ftp_access_code,
            'ftp_sync_enabled': s.ftp_sync_enabled,
        },
        'printer_profiles': [{
            'name': p.name,
            'is_default': p.is_default,
            'purchase_price': p.purchase_price,
            'investment_return_years': p.investment_return_years,
            'daily_usage_hours': p.daily_usage_hours,
            'repair_cost_percent': p.repair_cost_percent,
            'power_consumption': p.power_consumption,
            'energy_cost_per_kwh': p.energy_cost_per_kwh,
        } for p in profiles],
        'calculations': [_calc_to_dict(c) for c in calcs],
    }

    buf = BytesIO()
    buf.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
    buf.seek(0)
    app.logger.info("User '%s' exported data: %d calculations, %d profiles",
                    current_user.username, len(calcs), len(profiles))
    return send_file(buf, mimetype='application/json',
                     download_name='printcostcalc_export.json',
                     as_attachment=True)


@app.route('/import', methods=['GET', 'POST'])
@login_required
def import_data():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Keine Datei ausgewählt.', 'danger')
            return redirect(url_for('import_data'))
        f = request.files['file']
        if not f.filename:
            flash('Keine Datei ausgewählt.', 'danger')
            return redirect(url_for('import_data'))
        try:
            data = json.loads(f.read().decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            flash('Ungültiges Dateiformat.', 'danger')
            return redirect(url_for('import_data'))

        imported_profiles = 0
        imported_calcs = 0

        # Import settings
        if 'settings' in data and request.form.get('import_settings') == 'on':
            s = get_settings()
            sd = data['settings']
            for key in ['spoolman_url', 'default_markup', 'default_vat', 'currency',
                        'default_prep_cost_per_hour', 'default_postprocessing_cost_per_hour',
                        'ftp_host', 'ftp_access_code', 'ftp_sync_enabled']:
                if key in sd:
                    setattr(s, key, sd[key])
            db.session.commit()

        # Import printer profiles
        if 'printer_profiles' in data and request.form.get('import_profiles') == 'on':
            for pd in data['printer_profiles']:
                existing = PrinterProfile.query.filter_by(name=pd['name']).first()
                if not existing:
                    p = PrinterProfile(
                        name=pd['name'],
                        is_default=pd.get('is_default', False),
                        purchase_price=pd.get('purchase_price', 0),
                        investment_return_years=pd.get('investment_return_years', 2),
                        daily_usage_hours=pd.get('daily_usage_hours', 6),
                        repair_cost_percent=pd.get('repair_cost_percent', 5),
                        power_consumption=pd.get('power_consumption', 100),
                        energy_cost_per_kwh=pd.get('energy_cost_per_kwh', 0.30),
                    )
                    db.session.add(p)
                    imported_profiles += 1
            db.session.commit()

        # Import calculations
        if 'calculations' in data and request.form.get('import_calcs') == 'on':
            for cd in data['calculations']:
                existing = Calculation.query.filter_by(uuid=cd.get('uuid')).first()
                if not existing:
                    calc = Calculation(user_id=current_user.id)
                    calc.uuid = cd.get('uuid') or str(uuid.uuid4())
                    _apply_calc_json(calc, cd)
                    db.session.add(calc)
                    imported_calcs += 1
            db.session.commit()

        app.logger.info("User '%s' imported: %d profiles, %d calculations",
                        current_user.username, imported_profiles, imported_calcs)
        flash(f'{imported_profiles} Druckerprofile und {imported_calcs} Kalkulationen importiert.', 'success')
        return redirect(url_for('calculations'))

    return render_template('import.html')


# ── API ──────────────────────────────────────────────────────────────────

@app.route('/api/calculations', methods=['GET'])
@login_required
def api_calculations_list():
    calcs = Calculation.query.filter_by(user_id=current_user.id).all()
    return jsonify([_calc_to_dict(c) for c in calcs])


@app.route('/api/calculations', methods=['POST'])
@login_required
def api_calculations_create():
    data = request.get_json(force=True)
    calc = Calculation(user_id=current_user.id)
    calc.uuid = data.get('uuid') or str(uuid.uuid4())
    _apply_calc_json(calc, data)
    db.session.add(calc)
    db.session.commit()
    app.logger.info("API: Calculation created id=%s, job='%s'", calc.id, calc.job_name)
    return jsonify(_calc_to_dict(calc)), 201


@app.route('/api/calculations/<calc_uuid>', methods=['PUT'])
@login_required
def api_calculations_update(calc_uuid):
    calc = Calculation.query.filter_by(
        uuid=calc_uuid, user_id=current_user.id).first_or_404()
    data = request.get_json(force=True)
    _apply_calc_json(calc, data)
    db.session.commit()
    app.logger.info("API: Calculation updated uuid=%s", calc_uuid)
    return jsonify(_calc_to_dict(calc))


@app.route('/api/calculations/<calc_uuid>', methods=['DELETE'])
@login_required
def api_calculations_delete_api(calc_uuid):
    calc = Calculation.query.filter_by(
        uuid=calc_uuid, user_id=current_user.id).first_or_404()
    app.logger.info("API: Calculation deleted uuid=%s", calc_uuid)
    db.session.delete(calc)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@app.route('/api/printer-profiles')
@login_required
def api_printer_profiles():
    profiles = PrinterProfile.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'purchase_price': p.purchase_price,
        'investment_return_years': p.investment_return_years,
        'daily_usage_hours': p.daily_usage_hours,
        'repair_cost_percent': p.repair_cost_percent,
        'power_consumption': p.power_consumption,
        'energy_cost_per_kwh': p.energy_cost_per_kwh,
    } for p in profiles])


@app.route('/api/settings')
@login_required
def api_settings():
    s = get_settings()
    return jsonify({
        'spoolman_url': s.spoolman_url,
        'default_markup': s.default_markup,
        'default_vat': s.default_vat,
        'currency': s.currency,
        'default_prep_cost_per_hour': s.default_prep_cost_per_hour,
        'default_postprocessing_cost_per_hour': s.default_postprocessing_cost_per_hour,
    })


@app.route('/api/spoolman/spools')
@login_required
def api_spoolman_spools():
    s = get_settings()
    if not s.spoolman_url:
        return jsonify({'error': 'Spoolman nicht konfiguriert'}), 400
    try:
        spools = get_spools(s.spoolman_url)
        app.logger.debug("Spoolman returned %d spools", len(spools))
        return jsonify(spools)
    except Exception as e:
        app.logger.error("Spoolman request failed: %s", e)
        return jsonify({'error': f'Spoolman nicht erreichbar: {e}'}), 502


@app.route('/api/spoolman/test')
@login_required
def api_spoolman_test():
    url = request.args.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL fehlt'}), 400
    try:
        spools = get_spools(url)
        return jsonify({'status': 'ok', 'count': len(spools)})
    except Exception as e:
        return jsonify({'error': str(e)}), 502


@app.route('/api/parse-file', methods=['POST'])
@login_required
def api_parse_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Keine Datei'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'Keine Datei ausgewählt'}), 400
    try:
        result = parse_file(f)
        app.logger.info("Parsed uploaded file '%s'", f.filename)
        return jsonify(result)
    except Exception as e:
        app.logger.error("Failed to parse uploaded file '%s': %s", f.filename, e)
        return jsonify({'error': str(e)}), 500


# ── Printer Files ────────────────────────────────────────────────────────

@app.route('/printer-files')
@login_required
def printer_files():
    files = PrinterFile.query.order_by(PrinterFile.modified_at.desc().nullslast(), PrinterFile.id.desc()).all()
    settings = get_settings()
    return render_template('printer_files.html', files=files, settings=settings)


# ── FTP API ──────────────────────────────────────────────────────────────

@app.route('/api/ftp/test')
@login_required
def api_ftp_test():
    host = request.args.get('host', '').strip()
    code = request.args.get('code', '').strip()
    if not host or not code:
        return jsonify({'error': 'Host und Zugriffscode erforderlich'}), 400
    try:
        from utils.ftp_sync import connect_to_printer, list_printer_files
        ftp = connect_to_printer(host, code)
        files = list_printer_files(ftp)
        ftp.quit()
        app.logger.info("FTP test successful: %s, %d files found", host, len(files))
        return jsonify({'status': 'ok', 'file_count': len(files)})
    except Exception as e:
        app.logger.error("FTP test failed for host %s: %s", host, e)
        return jsonify({'error': str(e)}), 502


@app.route('/api/ftp/sync', methods=['POST'])
@login_required
def api_ftp_sync():
    import threading
    from utils.ftp_sync import sync_printer_files

    def run_sync():
        sync_printer_files(app)

    app.logger.info("FTP sync triggered manually")
    t = threading.Thread(target=run_sync, daemon=True)
    t.start()
    return jsonify({'status': 'ok', 'message': 'Sync gestartet'})


@app.route('/printer-files/<int:file_id>/new-calc')
@login_required
def printer_file_new_calc(file_id):
    from utils.ftp_sync import parse_spool_locations, job_name_from_filename
    pf = PrinterFile.query.get_or_404(file_id)
    app.logger.info("Creating new calculation from printer file id=%s, filename='%s'", file_id, pf.filename)
    s = get_settings()
    printers_list = PrinterProfile.query.all()

    class PreFill:
        pass
    calc = PreFill()
    calc.id = None
    calc.uuid = None
    calc.job_name = job_name_from_filename(pf.filename)
    calc.printing_time_hours = pf.printing_time_hours or 0
    calc.printing_time_minutes = pf.printing_time_minutes or 0
    calc.filament_weight_grams = pf.filament_weight_grams or 0
    calc.filament_type = pf.filament_type or 'PLA'
    calc.preview_image = pf.preview_image
    calc.filament_name = ''
    calc.spool_price = 0
    calc.spool_weight = 1000
    calc.markup_percent = s.default_markup
    calc.vat_percent = s.default_vat
    calc.electricity_enabled = True
    calc.power_consumption = 0
    calc.energy_cost_per_kwh = 0.30
    calc.labor_enabled = False
    calc.prep_time_minutes = 0
    calc.prep_cost_per_hour = s.default_prep_cost_per_hour
    calc.postprocessing_time_minutes = 0
    calc.postprocessing_cost_per_hour = s.default_postprocessing_cost_per_hour
    calc.machine_enabled = True
    calc.machine_purchase_price = 0
    calc.machine_return_years = 2
    calc.machine_daily_hours = 6
    calc.machine_repair_percent = 5
    calc.other_costs = []
    calc.final_price_override = None
    calc.printer_profile_id = None

    # Apply default printer
    printer = PrinterProfile.query.filter_by(is_default=True).first()
    if printer:
        calc.printer_profile_id = printer.id
        calc.power_consumption = printer.power_consumption
        calc.energy_cost_per_kwh = printer.energy_cost_per_kwh
        calc.machine_purchase_price = printer.purchase_price
        calc.machine_return_years = printer.investment_return_years
        calc.machine_daily_hours = printer.daily_usage_hours
        calc.machine_repair_percent = printer.repair_cost_percent

    # Match spools by location
    locations = parse_spool_locations(pf.filename)
    filaments = []
    spoolman_spools = []
    if s.spoolman_url:
        try:
            spoolman_spools = get_spools(s.spoolman_url)
        except Exception:
            pass

    if locations:
        total_weight = calc.filament_weight_grams
        per_spool = round(total_weight / len(locations), 2) if locations else 0
        for loc in locations:
            fil = {'name': '', 'spool_price': 0, 'spool_weight': 1000,
                   'grams_used': per_spool, 'filament_type': calc.filament_type, 'location': loc}
            for sp in spoolman_spools:
                if str(sp.get('location', '')) == loc:
                    fil['name'] = sp.get('name', '')
                    fil['spool_price'] = float(sp.get('price', 0))
                    fil['spool_weight'] = float(sp.get('spool_weight', 1000))
                    fil['filament_type'] = sp.get('filament_type', 'PLA')
                    break
            filaments.append(fil)
    else:
        filaments.append({
            'name': '', 'spool_price': 0, 'spool_weight': 1000,
            'grams_used': calc.filament_weight_grams, 'filament_type': calc.filament_type, 'location': ''
        })

    calc.filaments = filaments

    default_printer = PrinterProfile.query.filter_by(is_default=True).first()
    return render_template('calculation_form.html', calculation=calc,
                           printers=printers_list, settings=s, edit=False,
                           default_printer_id=default_printer.id if default_printer else None,
                           printer_file_id=pf.id)


# ── PWA ──────────────────────────────────────────────────────────────────

@app.route('/sw.js')
def service_worker():
    resp = app.send_static_file('sw.js')
    resp.headers['Content-Type'] = 'application/javascript'
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp


@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')


# ── Helpers ──────────────────────────────────────────────────────────────

def _save_calculation(calc, form):
    is_new = calc is None
    if is_new:
        calc = Calculation(user_id=current_user.id)
        calc.uuid = form.get('uuid') or str(uuid.uuid4())
        db.session.add(calc)
        # Link to printer file if coming from printer files
        pf_id = form.get('printer_file_id')
        if pf_id:
            pf = PrinterFile.query.get(int(pf_id))
            if pf:
                pf.processed = True
                pf.calculation_id = None  # will be set after flush

    calc.job_name = form.get('job_name', '').strip()
    calc.printer_profile_id = form.get('printer_profile_id') or None
    calc.printing_time_hours = int(_float(form.get('printing_time_hours'), 0))
    calc.printing_time_minutes = int(_float(form.get('printing_time_minutes'), 0))
    calc.filament_weight_grams = _float(form.get('filament_weight_grams'), 0)
    calc.preview_image = form.get('preview_image') or None

    calc.filament_type = form.get('filament_type', 'PLA')
    calc.filament_name = form.get('filament_name', '').strip()
    calc.spool_price = _float(form.get('spool_price'), 0)
    calc.spool_weight = _float(form.get('spool_weight'), 1000)
    calc.markup_percent = _float(form.get('markup_percent'), 0)

    calc.electricity_enabled = form.get('electricity_enabled') == 'on'
    calc.power_consumption = _float(form.get('power_consumption'), 0)
    calc.energy_cost_per_kwh = _float(form.get('energy_cost_per_kwh'), 0.30)

    calc.labor_enabled = form.get('labor_enabled') == 'on'
    calc.prep_time_minutes = _float(form.get('prep_time_minutes'), 0)
    calc.prep_cost_per_hour = _float(form.get('prep_cost_per_hour'), 15)
    calc.postprocessing_time_minutes = _float(form.get('postprocessing_time_minutes'), 0)
    calc.postprocessing_cost_per_hour = _float(form.get('postprocessing_cost_per_hour'), 15)

    calc.machine_enabled = form.get('machine_enabled') == 'on'
    calc.machine_purchase_price = _float(form.get('machine_purchase_price'), 0)
    calc.machine_return_years = _float(form.get('machine_return_years'), 2)
    calc.machine_daily_hours = _float(form.get('machine_daily_hours'), 6)
    calc.machine_repair_percent = _float(form.get('machine_repair_percent'), 5)

    try:
        calc.filaments = json.loads(form.get('filaments_json', '[]'))
    except (json.JSONDecodeError, TypeError):
        calc.filaments = []

    try:
        calc.other_costs = json.loads(form.get('other_costs_json', '[]'))
    except (json.JSONDecodeError, TypeError):
        calc.other_costs = []

    calc.vat_percent = _float(form.get('vat_percent'), 19)

    override_val = form.get('final_price_override', '').strip()
    calc.final_price_override = float(override_val) if override_val else None

    _recalculate(calc)
    calc.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    # Link printer file after we have calc.id
    pf_id = form.get('printer_file_id')
    if pf_id and is_new:
        pf = PrinterFile.query.get(int(pf_id))
        if pf:
            pf.processed = True
            pf.calculation_id = calc.id
            db.session.commit()

    return calc


def _apply_calc_json(calc, data):
    calc.job_name = data.get('job_name', '')
    calc.printer_profile_id = data.get('printer_profile_id') or None
    calc.printing_time_hours = int(_float(data.get('printing_time_hours'), 0))
    calc.printing_time_minutes = int(_float(data.get('printing_time_minutes'), 0))
    calc.filament_weight_grams = _float(data.get('filament_weight_grams'), 0)
    calc.preview_image = data.get('preview_image')

    calc.filament_type = data.get('filament_type', 'PLA')
    calc.filament_name = data.get('filament_name', '')
    calc.spool_price = _float(data.get('spool_price'), 0)
    calc.spool_weight = _float(data.get('spool_weight'), 1000)
    calc.markup_percent = _float(data.get('markup_percent'), 0)

    calc.electricity_enabled = bool(data.get('electricity_enabled'))
    calc.power_consumption = _float(data.get('power_consumption'), 0)
    calc.energy_cost_per_kwh = _float(data.get('energy_cost_per_kwh'), 0.30)

    calc.labor_enabled = bool(data.get('labor_enabled'))
    calc.prep_time_minutes = _float(data.get('prep_time_minutes'), 0)
    calc.prep_cost_per_hour = _float(data.get('prep_cost_per_hour'), 15)
    calc.postprocessing_time_minutes = _float(data.get('postprocessing_time_minutes'), 0)
    calc.postprocessing_cost_per_hour = _float(data.get('postprocessing_cost_per_hour'), 15)

    calc.machine_enabled = bool(data.get('machine_enabled'))
    calc.machine_purchase_price = _float(data.get('machine_purchase_price'), 0)
    calc.machine_return_years = _float(data.get('machine_return_years'), 2)
    calc.machine_daily_hours = _float(data.get('machine_daily_hours'), 6)
    calc.machine_repair_percent = _float(data.get('machine_repair_percent'), 5)

    calc.other_costs = data.get('other_costs', [])
    calc.vat_percent = _float(data.get('vat_percent'), 19)
    calc.final_price_override = data.get('final_price_override')

    _recalculate(calc)
    calc.updated_at = datetime.now(timezone.utc)


def _calc_to_dict(calc):
    return {
        'id': calc.id,
        'uuid': calc.uuid,
        'job_name': calc.job_name,
        'printer_profile_id': calc.printer_profile_id,
        'printing_time_hours': calc.printing_time_hours,
        'printing_time_minutes': calc.printing_time_minutes,
        'filament_weight_grams': calc.filament_weight_grams,
        'preview_image': calc.preview_image,
        'filament_type': calc.filament_type,
        'filament_name': calc.filament_name,
        'spool_price': calc.spool_price,
        'spool_weight': calc.spool_weight,
        'markup_percent': calc.markup_percent,
        'filament_cost': calc.filament_cost,
        'electricity_enabled': calc.electricity_enabled,
        'power_consumption': calc.power_consumption,
        'energy_cost_per_kwh': calc.energy_cost_per_kwh,
        'electricity_cost': calc.electricity_cost,
        'labor_enabled': calc.labor_enabled,
        'prep_time_minutes': calc.prep_time_minutes,
        'prep_cost_per_hour': calc.prep_cost_per_hour,
        'postprocessing_time_minutes': calc.postprocessing_time_minutes,
        'postprocessing_cost_per_hour': calc.postprocessing_cost_per_hour,
        'labor_cost': calc.labor_cost,
        'machine_enabled': calc.machine_enabled,
        'machine_purchase_price': calc.machine_purchase_price,
        'machine_return_years': calc.machine_return_years,
        'machine_daily_hours': calc.machine_daily_hours,
        'machine_repair_percent': calc.machine_repair_percent,
        'machine_cost': calc.machine_cost,
        'filaments': calc.filaments or [],
        'other_costs': calc.other_costs or [],
        'vat_percent': calc.vat_percent,
        'total_price': calc.total_price,
        'final_price_override': calc.final_price_override,
        'status': calc.status,
        'created_at': calc.created_at.isoformat() if calc.created_at else None,
        'updated_at': calc.updated_at.isoformat() if calc.updated_at else None,
    }


# ── Init ─────────────────────────────────────────────────────────────────

with app.app_context():
    os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)
    # SQLite on SMB/NFS: disable WAL mode
    with db.engine.connect() as c:
        c.execute(text("PRAGMA journal_mode=DELETE"))
        c.commit()
    db.create_all()
    # Migrate existing databases
    with db.engine.connect() as conn:
        for stmt in [
            "ALTER TABLE calculation ADD COLUMN status VARCHAR(20) DEFAULT 'confirmed' NOT NULL",
            "ALTER TABLE settings ADD COLUMN api_key VARCHAR(64) DEFAULT ''",
            "ALTER TABLE settings ADD COLUMN slicer_default_user_id INTEGER",
            "ALTER TABLE settings ADD COLUMN ftp_host VARCHAR(256) DEFAULT ''",
            "ALTER TABLE settings ADD COLUMN ftp_access_code VARCHAR(256) DEFAULT ''",
            "ALTER TABLE settings ADD COLUMN ftp_sync_enabled BOOLEAN DEFAULT 0",
            "ALTER TABLE calculation ADD COLUMN filaments JSON DEFAULT '[]'",
            "ALTER TABLE printer_file ADD COLUMN modified_at DATETIME",
            "ALTER TABLE printer_file ADD COLUMN preview_image TEXT",
            "ALTER TABLE printer_file ADD COLUMN printing_time_hours INTEGER DEFAULT 0",
            "ALTER TABLE printer_file ADD COLUMN printing_time_minutes INTEGER DEFAULT 0",
            "ALTER TABLE printer_file ADD COLUMN filament_weight_grams FLOAT DEFAULT 0",
            "ALTER TABLE printer_file ADD COLUMN filament_type VARCHAR(50) DEFAULT ''",
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()

# Start PrintSync worker thread
from utils.ftp_sync import start_sync_worker
start_sync_worker(app)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
