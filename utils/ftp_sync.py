import logging
import re
import ssl
import socket
import uuid
from datetime import datetime, timezone
from ftplib import FTP_TLS
from io import BytesIO

from models import Calculation, PrinterFile, PrinterProfile, Settings, User, db
from utils.calc_helpers import _recalculate
from utils.parser import _parse_3mf

logger = logging.getLogger(__name__)


class BambuFTP(FTP_TLS):
    """Implicit FTPS client for Bambu Lab printers (port 990, TLS session reuse)."""

    def connect(self, host, port=990, timeout=10):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = socket.create_connection((host, port), timeout)
        self.af = self.sock.family
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.context.check_hostname = False
        self.context.verify_mode = ssl.CERT_NONE
        self.sock = self.context.wrap_socket(self.sock, server_hostname=host)
        self.file = self.sock.makefile('r', encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome

    def ntransfercmd(self, cmd, rest=None):
        conn, size = super(FTP_TLS, self).ntransfercmd(cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(
                conn, server_hostname=self.host,
                session=self.sock.session)
        return conn, size


def connect_to_printer(host, access_code):
    """Establish FTP connection to Bambu printer."""
    logger.debug("Connecting to printer at %s:990", host)
    ftp = BambuFTP()
    ftp.connect(host, port=990)
    ftp.login(user='bblp', passwd=access_code)
    ftp.prot_p()
    logger.info("Connected to printer at %s", host)
    return ftp


def list_printer_files(ftp):
    """List all .3mf files on the printer."""
    files = []
    try:
        names = ftp.nlst('/')
    except Exception as e:
        logger.error("Failed to list files on printer: %s", e)
        return files

    for name in names:
        if name.lower().endswith('.3mf'):
            size = None
            modified = None
            try:
                size = ftp.size(name)
            except Exception:
                pass
            try:
                resp = ftp.sendcmd('MDTM ' + name)
                # Response: "213 20260415123456"
                ts = resp.split()[1]
                modified = datetime(int(ts[0:4]), int(ts[4:6]), int(ts[6:8]),
                                    int(ts[8:10]), int(ts[10:12]), int(ts[12:14]),
                                    tzinfo=timezone.utc)
            except Exception:
                pass
            files.append({'filename': name, 'size': size, 'modified': modified})
    logger.info("Found %d .3mf files on printer", len(files))
    return files


def download_and_parse(ftp, remote_path):
    """Download a .3mf file from the printer and parse it."""
    logger.debug("Downloading '%s' from printer", remote_path)
    buf = BytesIO()
    ftp.retrbinary('RETR ' + remote_path, buf.write)
    data = buf.getvalue()
    logger.debug("Downloaded '%s' (%d bytes), parsing", remote_path, len(data))
    return _parse_3mf(data)


def parse_spool_locations(filename):
    """Extract spool location numbers from filename pattern like '11+1+49_fuchs'."""
    basename = filename.rsplit('/', 1)[-1]
    basename = re.sub(r'\.(gcode\.3mf|3mf)$', '', basename, flags=re.IGNORECASE)
    m = re.match(r'^([\d+]+)_', basename)
    if m:
        parts = m.group(1).split('+')
        return [p.strip() for p in parts if p.strip()]
    return []


def job_name_from_filename(filename):
    """Extract clean job name from printer filename."""
    basename = filename.rsplit('/', 1)[-1]
    return re.sub(r'\.(gcode\.3mf|3mf)$', '', basename, flags=re.IGNORECASE)


def create_calculation_from_file(app, printer_file_id, spoolman_spools=None):
    """Create a Calculation from a PrinterFile. Returns calc id."""
    with app.app_context():
        pf = PrinterFile.query.get(printer_file_id)
        if not pf:
            logger.error("PrinterFile id=%s not found", printer_file_id)
            raise ValueError('PrinterFile not found')
        logger.info("Creating calculation from PrinterFile id=%s, filename='%s'", printer_file_id, pf.filename)

        settings = Settings.query.first()
        user_id = current_user_id(settings)

        calc = Calculation(user_id=user_id, status='confirmed')
        calc.uuid = str(uuid.uuid4())
        calc.job_name = job_name_from_filename(pf.filename)

        calc.printing_time_hours = pf.printing_time_hours or 0
        calc.printing_time_minutes = pf.printing_time_minutes or 0
        calc.filament_weight_grams = pf.filament_weight_grams or 0
        calc.filament_type = pf.filament_type or 'PLA'
        calc.preview_image = pf.preview_image

        # Apply default printer profile
        printer = PrinterProfile.query.filter_by(is_default=True).first()
        if printer:
            calc.printer_profile_id = printer.id
            calc.electricity_enabled = True
            calc.power_consumption = printer.power_consumption
            calc.energy_cost_per_kwh = printer.energy_cost_per_kwh
            calc.machine_enabled = True
            calc.machine_purchase_price = printer.purchase_price
            calc.machine_return_years = printer.investment_return_years
            calc.machine_daily_hours = printer.daily_usage_hours
            calc.machine_repair_percent = printer.repair_cost_percent

        # Match spools by location from filename
        locations = parse_spool_locations(pf.filename)
        filaments = []
        if locations and spoolman_spools:
            total_weight = calc.filament_weight_grams or 0
            matched_count = 0
            for loc in locations:
                for spool in spoolman_spools:
                    if str(spool.get('location', '')) == loc:
                        filaments.append({
                            'name': spool.get('name', ''),
                            'spool_price': float(spool.get('price', 0)),
                            'spool_weight': float(spool.get('spool_weight', 1000)),
                            'grams_used': 0,
                            'filament_type': spool.get('filament_type', 'PLA'),
                            'location': loc,
                        })
                        matched_count += 1
                        break
            # Distribute weight evenly as starting point
            if matched_count > 0 and total_weight > 0:
                per_spool = round(total_weight / matched_count, 2)
                for fil in filaments:
                    fil['grams_used'] = per_spool
        elif locations:
            # No Spoolman, create empty entries per location
            total_weight = calc.filament_weight_grams or 0
            per_spool = round(total_weight / len(locations), 2) if locations else 0
            for loc in locations:
                filaments.append({
                    'name': '',
                    'spool_price': 0,
                    'spool_weight': 1000,
                    'grams_used': per_spool,
                    'filament_type': calc.filament_type or 'PLA',
                    'location': loc,
                })

        if filaments:
            calc.filaments = filaments

        calc.markup_percent = settings.default_markup
        calc.vat_percent = settings.default_vat
        calc.prep_cost_per_hour = settings.default_prep_cost_per_hour
        calc.postprocessing_cost_per_hour = settings.default_postprocessing_cost_per_hour

        _recalculate(calc)
        db.session.add(calc)
        db.session.flush()

        pf.processed = True
        pf.calculation_id = calc.id
        db.session.commit()
        logger.info("Calculation id=%s created from PrinterFile id=%s", calc.id, printer_file_id)
        return calc.id


def current_user_id(settings):
    """Get the target user ID for new calculations."""
    user_id = getattr(settings, 'slicer_default_user_id', None)
    if not user_id:
        admin = User.query.filter_by(is_admin=True).first()
        user_id = admin.id if admin else User.query.first().id
    return user_id


def sync_printer_files(app):
    """Connect to printer, discover new files, download & store metadata."""
    with app.app_context():
        settings = Settings.query.first()
        if not settings or not settings.ftp_host or not settings.ftp_access_code:
            logger.warning("FTP sync skipped: not configured")
            return {'status': 'error', 'message': 'FTP nicht konfiguriert'}

        logger.info("Starting FTP sync with %s", settings.ftp_host)
        try:
            ftp = connect_to_printer(settings.ftp_host, settings.ftp_access_code)
        except Exception as e:
            logger.error("FTP connection to %s failed: %s", settings.ftp_host, e)
            return {'status': 'error', 'message': f'Verbindung fehlgeschlagen: {e}'}

        try:
            remote_files = list_printer_files(ftp)
            new_count = 0

            for rf in remote_files:
                existing = PrinterFile.query.filter_by(filename=rf['filename']).first()
                if not existing:
                    logger.info("New file discovered: '%s'", rf['filename'])
                    pf = PrinterFile(
                        filename=rf['filename'],
                        file_size=rf.get('size'),
                        modified_at=rf.get('modified'),
                    )
                    db.session.add(pf)
                    db.session.commit()

                    # Download and parse metadata only (no calculation)
                    try:
                        parse_result = download_and_parse(ftp, rf['filename'])
                        pf.preview_image = parse_result.get('preview_image_base64')
                        pf.preview_images = parse_result.get('preview_images') or []
                        pf.printing_time_hours = int(parse_result.get('printing_time_hours') or 0)
                        pf.printing_time_minutes = int(parse_result.get('printing_time_minutes') or 0)
                        pf.filament_weight_grams = float(parse_result.get('filament_weight_grams') or 0)
                        pf.filament_type = parse_result.get('filament_type') or ''
                        db.session.commit()
                        new_count += 1
                        logger.info("Parsed '%s': %dh%dm, %.1fg %s",
                                    rf['filename'], pf.printing_time_hours,
                                    pf.printing_time_minutes, pf.filament_weight_grams,
                                    pf.filament_type)
                    except Exception as e:
                        logger.error("Failed to parse '%s': %s", rf['filename'], e)

            ftp.quit()
        except Exception as e:
            logger.error("FTP sync error: %s", e)
            return {'status': 'error', 'message': str(e)}

        logger.info("FTP sync completed: %d new files, %d total on printer", new_count, len(remote_files))
        return {'status': 'ok', 'new_files': new_count, 'total_files': len(remote_files)}


def start_sync_worker(app):
    """Start background thread that syncs every 5 minutes."""
    import threading
    import time

    def worker():
        time.sleep(10)
        while True:
            with app.app_context():
                settings = Settings.query.first()
                if settings and settings.ftp_sync_enabled and settings.ftp_host:
                    try:
                        result = sync_printer_files(app)
                        logger.info(f"FTP sync: {result}")
                    except Exception as e:
                        logger.error(f"FTP sync error: {e}")
            time.sleep(300)

    t = threading.Thread(target=worker, daemon=True, name='ftp-sync-worker')
    t.start()
    return t
