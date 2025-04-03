from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
import pandas as pd
from io import BytesIO
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'votre_clé_secrète_ici'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///devices.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Models
class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    serial_number = db.Column(db.String(100), nullable=False, unique=True)
    status = db.Column(db.String(20), default='actif')
    assigned_to = db.Column(db.String(100))
    service = db.Column(db.String(100))
    department = db.Column(db.String(100))
    mac_address = db.Column(db.String(17))
    notes = db.Column(db.Text)
    maintenance_records = db.relationship('MaintenanceRecord', backref='device', lazy=True, cascade="all, delete-orphan")
    ownership_changes = db.relationship('OwnershipChange', backref='device', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Device {self.name}>'

class MaintenanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    reference = db.Column(db.String(20))
    maintenance_date = db.Column(db.Date, nullable=False)
    issue_description = db.Column(db.Text, nullable=False)
    actions_taken = db.Column(db.Text)
    status = db.Column(db.String(20), default='en attente')
    technician = db.Column(db.String(100), nullable=False)
    completion_date = db.Column(db.Date)
    notes = db.Column(db.Text)

    def __repr__(self):
        return f'<MaintenanceRecord {self.id}>'

class OwnershipChange(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    previous_owner = db.Column(db.String(100))
    new_owner = db.Column(db.String(100))
    change_date = db.Column(db.DateTime, default=datetime.now)
    notes = db.Column(db.Text)

    def __repr__(self):
        return f'<OwnershipChange {self.id}>'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Database initialization
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def index():
    data = {
        'total_devices': Device.query.count(),
        'active_devices': Device.query.filter_by(status='actif').count(),
        'maintenance_devices': Device.query.filter_by(status='en maintenance').count(),
        'inactive_devices': Device.query.filter_by(status='inactif').count(),
        'recent_devices': Device.query.order_by(Device.id.desc()).limit(5).all(),
        'recent_maintenance': MaintenanceRecord.query.order_by(MaintenanceRecord.maintenance_date.desc()).limit(5).all(),
        'assigned_data': db.session.query(
            Device.assigned_to, 
            db.func.count(Device.id).label('device_count')
        ).filter(
            Device.assigned_to != '', 
            Device.assigned_to != None
        ).group_by(Device.assigned_to).all()
    }
    
    return render_template('index.html', **data)

@app.route('/devices')
@login_required
def devices():
    devices = Device.query.all()
    return render_template('devices.html', devices=devices)

@app.route('/device/<int:device_id>')
@login_required
def device_details(device_id):
    device = Device.query.get_or_404(device_id)
    maintenance_records = MaintenanceRecord.query.filter_by(device_id=device_id).order_by(MaintenanceRecord.maintenance_date.desc()).all()
    return render_template('device_details.html', **locals())

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Permission denied', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/add_device', methods=['GET', 'POST'])
@login_required
@admin_required
def add_device():
    if request.method == 'POST':
        name = request.form['name']
        type = request.form['type']
        serial_number = request.form['serial_number']
        status = request.form['status']
        assigned_to = request.form.get('assigned_to', '')
        service = request.form.get('service', '')
        department = request.form.get('department', '')
        mac_address = request.form.get('mac_address', '')
        notes = request.form.get('notes', '')

        existing_device = Device.query.filter_by(serial_number=serial_number).first()
        if existing_device:
            flash('Un appareil avec ce numéro de série existe déjà.', 'danger')
            return redirect(url_for('add_device'))

        new_device = Device(
            name=name,
            type=type,
            serial_number=serial_number,
            status=status,
            assigned_to=assigned_to,
            service=service,
            department=department,
            mac_address=mac_address,
            notes=notes
        )
        db.session.add(new_device)
        db.session.commit()
        flash('Appareil ajouté avec succès!', 'success')
        return redirect(url_for('devices'))

    return render_template('device_form.html', device=Device())

@app.route('/edit_device/<int:device_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_device(device_id):
    device = Device.query.get_or_404(device_id)
    if request.method == 'POST':
        device.name = request.form['name']
        device.type = request.form['type']

        new_serial = request.form['serial_number']
        if new_serial != device.serial_number:
            existing_device = Device.query.filter_by(serial_number=new_serial).first()
            if existing_device:
                flash('Un appareil avec ce numéro de série existe déjà.', 'danger')
                return redirect(url_for('edit_device', device_id=device_id))

        device.serial_number = new_serial
        device.status = request.form['status']

        new_owner = request.form.get('assigned_to', '')
        if new_owner != device.assigned_to and (new_owner or device.assigned_to):
            ownership_change = OwnershipChange(
                device_id=device.id,
                previous_owner=device.assigned_to or 'Non assigné',
                new_owner=new_owner or 'Non assigné',
                change_date=datetime.now(),
                notes=request.form.get('notes', '')
            )
            db.session.add(ownership_change)

        device.assigned_to = new_owner
        device.service = request.form.get('service', '')
        device.department = request.form.get('department', '')
        device.mac_address = request.form.get('mac_address', '')
        device.notes = request.form.get('notes', '')

        db.session.commit()
        flash('Appareil mis à jour avec succès!', 'success')
        return redirect(url_for('device_details', device_id=device_id))

    return render_template('device_form.html', device=device)

@app.route('/delete_device/<int:device_id>')
@login_required
@admin_required
def delete_device(device_id):
    device = Device.query.get_or_404(device_id)
    db.session.delete(device)
    db.session.commit()
    flash('Appareil supprimé avec succès!', 'success')
    return redirect(url_for('devices'))

@app.route('/maintenance')
@login_required
def maintenance():
    maintenance_records = MaintenanceRecord.query.order_by(MaintenanceRecord.maintenance_date.desc()).all()
    return render_template('maintenance.html', maintenance_records=maintenance_records)

def generate_maintenance_reference(maintenance_date):
    year = maintenance_date.year
    month = maintenance_date.month

    count = MaintenanceRecord.query.filter(
        db.extract('year', MaintenanceRecord.maintenance_date) == year,
        db.extract('month', MaintenanceRecord.maintenance_date) == month
    ).count()

    number_in_month = count + 1
    reference = f"REF:{number_in_month:02d}/INF/{year}"
    return reference

@app.route('/add_maintenance', methods=['GET', 'POST'])
@app.route('/add_maintenance/<int:device_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def add_maintenance(device_id=None):
    if request.method == 'POST':
        try:
            device_id = int(request.form['device_id'])
            maintenance_date_str = request.form['maintenance_date']
            issue_description = request.form['issue_description']
            actions_taken = request.form.get('actions_taken', '')
            status = request.form['status']
            technician = request.form['technician']
            completion_date_str = request.form.get('completion_date', '')
            notes = request.form.get('notes', '')

            if not all([device_id, maintenance_date_str, issue_description, technician]):
                flash('Veuillez remplir tous les champs obligatoires.', 'danger')
                return redirect(url_for('add_maintenance'))

            maintenance_date = datetime.strptime(maintenance_date_str, '%Y-%m-%d').date()
            completion_date = datetime.strptime(completion_date_str, '%Y-%m-%d').date() if completion_date_str else None

            reference = generate_maintenance_reference(maintenance_date)

            new_record = MaintenanceRecord(
                device_id=device_id,
                reference=reference,
                maintenance_date=maintenance_date,
                issue_description=issue_description,
                actions_taken=actions_taken,
                status=status,
                technician=technician,
                completion_date=completion_date,
                notes=notes
            )

            db.session.add(new_record)

            device = Device.query.get_or_404(device_id)
            if status == 'en cours' and device.status != 'en maintenance':
                device.status = 'en maintenance'
            elif status == 'terminé' and device.status == 'en maintenance':
                device.status = 'actif'

            db.session.commit()
            flash('Registre de maintenance ajouté avec succès!', 'success')
            return redirect(url_for('device_details', device_id=device_id))

        except (ValueError, TypeError) as e:
            flash('Erreur de validation des données. Veuillez vérifier les champs.', 'danger')
            return redirect(url_for('add_maintenance'))

    devices = Device.query.all()
    technicians = [t[0] for t in db.session.query(MaintenanceRecord.technician).distinct().filter(MaintenanceRecord.technician != None, MaintenanceRecord.technician != '').all()]
    today = datetime.now().date().strftime('%Y-%m-%d')
    return render_template('maintenance_form.html', **locals())

@app.route('/edit_maintenance/<int:record_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_maintenance(record_id):
    record = MaintenanceRecord.query.get_or_404(record_id)
    if request.method == 'POST':
        old_status = record.status

        record.maintenance_date = datetime.strptime(request.form['maintenance_date'], '%Y-%m-%d').date()

        if record.maintenance_date != datetime.strptime(request.form['maintenance_date'], '%Y-%m-%d').date():
            record.reference = generate_maintenance_reference(record.maintenance_date)

        record.issue_description = request.form['issue_description']
        record.actions_taken = request.form.get('actions_taken', '')
        record.status = request.form['status']
        record.technician = request.form['technician']

        completion_date_str = request.form.get('completion_date', '')
        record.completion_date = datetime.strptime(completion_date_str, '%Y-%m-%d').date() if completion_date_str else None

        record.notes = request.form.get('notes', '')

        device = Device.query.get(record.device_id)
        if record.status == 'en cours' and device.status != 'en maintenance' and old_status != 'en cours':
            device.status = 'en maintenance'
        elif record.status == 'terminé' and device.status == 'en maintenance' and old_status != 'terminé':
            device.status = 'actif'

        db.session.commit()
        flash('Registre de maintenance mis à jour avec succès!', 'success')
        return redirect(url_for('device_details', device_id=record.device_id))

    devices = Device.query.all()
    technicians = [t[0] for t in db.session.query(MaintenanceRecord.technician).distinct().filter(MaintenanceRecord.technician != None, MaintenanceRecord.technician != '').all()]
    return render_template('maintenance_form.html', **locals())

@app.route('/delete_maintenance/<int:record_id>')
@login_required
@admin_required
def delete_maintenance(record_id):
    record = MaintenanceRecord.query.get_or_404(record_id)
    db.session.delete(record)
    db.session.commit()
    flash('Registre de maintenance supprimé avec succès!', 'success')
    return redirect(url_for('device_details', device_id=record.device_id))

@app.route('/export_devices_excel')
@login_required
def export_devices_excel():
    devices = Device.query.all()
    data = [{'ID': d.id, 'Nom': d.name, 'Type': d.type, 'Numéro de Série': d.serial_number, 'Statut': d.status, 'Assigné à': d.assigned_to, 'Service': d.service, 'Département': d.department, 'Adresse MAC': d.mac_address, 'Notes': d.notes} for d in devices]
    return export_to_excel(data, 'Appareils', 'appareils')

@app.route('/export_maintenance_excel')
@login_required
def export_maintenance_excel():
    records = MaintenanceRecord.query.all()
    data = [{'ID': r.id, 'Référence': r.reference or '', 'Appareil': r.device.name, 'Type d\'Appareil': r.device.type, 'Numéro de Série': r.device.serial_number, 'Date de Maintenance': r.maintenance_date.strftime('%d/%m/%Y'), 'Description du Problème': r.issue_description, 'Actions Effectuées': r.actions_taken, 'Statut': r.status, 'Technicien': r.technician, 'Date d\'Achèvement': r.completion_date.strftime('%d/%m/%Y') if r.completion_date else '', 'Notes': r.notes} for r in records]
    return export_to_excel(data, 'Maintenance', 'maintenance')

def export_to_excel(data, sheet_name, filename_prefix):
    df = pd.DataFrame(data)
    output = BytesIO()
    
    # استخدام openpyxl بدلاً من xlsxwriter
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    # ضبط عرض الأعمدة
    worksheet = writer.sheets[sheet_name]
    for idx, col in enumerate(df.columns, 1):
        worksheet.column_dimensions[chr(64 + idx)].width = 15
    
    writer.close()
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'{filename_prefix}_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

@app.route('/devices_by_assigned/<assigned_to>')
@login_required
def devices_by_assigned(assigned_to):
    devices = Device.query.filter_by(assigned_to=assigned_to).all()
    return render_template('devices.html', **locals())

@app.route('/maintenance/<int:record_id>/print')
@login_required
def print_maintenance(record_id):
    maintenance_record = MaintenanceRecord.query.get_or_404(record_id)
    return render_template('print_maintenance.html', record=maintenance_record)

@app.context_processor
def utility_processor():
    from datetime import datetime
    return {
        'now': datetime.now
    }

@app.route('/device/<int:device_id>/ownership_history')
@login_required
def ownership_history(device_id):
    device = Device.query.get_or_404(device_id)
    ownership_changes = OwnershipChange.query.filter_by(device_id=device_id).order_by(OwnershipChange.change_date.desc()).all()
    return render_template('ownership_history.html', **locals())

@app.route('/device/<int:device_id>/export_ownership_history')
@login_required
def export_ownership_history(device_id):
    device = Device.query.get_or_404(device_id)
    ownership_changes = OwnershipChange.query.filter_by(device_id=device_id).order_by(OwnershipChange.change_date.desc()).all()
    data = [{'ID': c.id, 'Date': c.change_date.strftime('%d/%m/%Y %H:%M'), 'Ancien Propriétaire': c.previous_owner, 'Nouveau Propriétaire': c.new_owner, 'Notes': c.notes} for c in ownership_changes]
    return export_to_excel(data, 'Historique Propriétaires', f'historique_proprietaires_{device.name}')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:  # في التطبيق الحقيقي، استخدم تشفير كلمة المرور
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)