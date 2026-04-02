# app.py (COMPLETAMENTE ACTUALIZADO - RUTA DE LIMPIEZA AÑADIDA)

import os
from flask import (Flask, render_template, request, redirect, url_for, 
                   flash, session, jsonify, abort, send_from_directory, g)
                   
from models import (db, bcrypt, User, Rutina, Progreso, Clase, Reserva, 
                    Ejercicio, RutinaEjercicio, SetPlaneado, Entrenamiento, 
                    EntrenamientoDetalle, Mensaje, Membresia, Pago) 
from functools import wraps
import json
from datetime import datetime, time, timedelta
from sqlalchemy.sql import func
from wtforms.fields import PasswordField 
from wtforms.validators import Optional 
from werkzeug.utils import secure_filename
from collections import OrderedDict
import random
from sqlalchemy import exc # ¡Importante!

# --- CONFIGURACIÓN DE LA APP ---
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui_muy_segura'
db_path = os.path.join(basedir, 'instance', 'activetrack.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db.init_app(app)
bcrypt.init_app(app)


# --- DECORADORES DE AUTORIZACIÓN (Sin cambios) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión para ver esta página.', 'danger')
            return redirect(url_for('index'))
        
        if not hasattr(g, 'user'):
            g.user = User.query.get(session['user_id'])
            if g.user:
                session['username'] = g.user.Nombre
                session['is_admin'] = (g.user.TipoUsuario == 'admin')
                session['is_instructor'] = (g.user.TipoUsuario == 'instructor')
                
                membresia = Membresia.query.filter_by(UsuarioId=session['user_id']).first()
                if membresia and membresia.Estado == 'activa' and membresia.FechaFin >= datetime.utcnow().date():
                    g.membresia_activa = True
                else:
                    g.membresia_activa = False
            else:
                session.clear()
                flash('Error de sesión. Por favor, inicia sesión de nuevo.', 'danger')
                return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def membership_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.membresia_activa and not session.get('is_admin'):
            flash('Necesitas una membresía activa para acceder a esta función.', 'warning')
            return redirect(url_for('membresia'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Acceso denegado. Debes ser administrador.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def instructor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_instructor') and not session.get('is_admin'):
            flash('Acceso denegado. Debes ser instructor o admin.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# --- (Funciones auxiliares sin cambios) ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def group_exercises(exercises):
    grouped = OrderedDict()
    for ej in exercises:
        group = ej.GrupoMuscular or 'Otros'
        if group not in grouped:
            grouped[group] = []
        grouped[group].append(ej)
    return grouped

# --- RUTAS DE AUTENTICACIÓN (Sin cambios) ---
@app.route('/')
def inicio():
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_dashboard'))
        if session.get('is_instructor'):
            return redirect(url_for('instructor_clases'))
        return redirect(url_for('dashboard'))
    return render_template('Inicio.html')

@app.route('/login-page')
def index():
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_dashboard'))
        if session.get('is_instructor'):
            return redirect(url_for('instructor_clases'))
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    correo = request.form['username']
    password = request.form['password']
    user = User.query.filter_by(Correo=correo).first()
    
    if user and user.check_password(password):
        session['user_id'] = user.UsuarioId
        session['username'] = user.Nombre
        
        if user.TipoUsuario == 'admin':
            session['is_admin'] = True
            session['is_instructor'] = False
            flash('Bienvenido, Administrador.', 'success')
            return redirect(url_for('admin_dashboard'))
            
        elif user.TipoUsuario == 'instructor':
            session['is_admin'] = False
            session['is_instructor'] = True
            flash('Bienvenido, Instructor.', 'success')
            return redirect(url_for('instructor_clases'))
            
        else: 
            session['is_admin'] = False
            session['is_instructor'] = False
            flash('Inicio de sesión exitoso.', 'success')
            return redirect(url_for('dashboard'))
    else:
        flash('Correo o contraseña incorrectos.', 'danger')
        return redirect(url_for('index'))

@app.route('/register', methods=['POST'])
def register():
    nombre = request.form['fullname']
    correo = request.form['email']
    password = request.form['password']
    
    terms_agreed = request.form.get('terms')
    if not terms_agreed:
        flash('Debes aceptar la Política de Tratamiento de Datos para registrarte.', 'danger')
        return redirect(url_for('index'))
    
    existing_user = User.query.filter_by(Correo=correo).first()
    if existing_user:
        flash('El correo electrónico ya está registrado.', 'warning')
        return redirect(url_for('index'))
        
    new_user = User(Nombre=nombre, Correo=correo)
    new_user.set_password(password)
    
    try:
        db.session.add(new_user)
        db.session.commit()
        membresia_prueba = Membresia(
            UsuarioId=new_user.UsuarioId,
            Tipo='Plan de Prueba',
            FechaInicio=datetime.utcnow().date(),
            FechaFin=datetime.utcnow().date() + timedelta(days=7),
            Estado='activa'
        )
        db.session.add(membresia_prueba)
        db.session.commit()
        
        flash('¡Cuenta creada con éxito! Tienes 7 días de prueba gratis.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar la cuenta: {e}', 'danger')
        
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('index'))

# --- (Rutas de Usuario /dashboard a /membresia/cancelar sin cambios) ---
@app.route('/dashboard')
@login_required
@membership_required 
def dashboard():
    user_id = session['user_id']
    dias_activo_count = Entrenamiento.query.filter_by(UsuarioId=user_id).count()
    
    ultimo_entrenamiento = Entrenamiento.query.filter_by(UsuarioId=user_id).order_by(Entrenamiento.Fecha.desc()).first()
    ultimo_volumen = 0
    if ultimo_entrenamiento and ultimo_entrenamiento.TotalVolume:
        ultimo_volumen = float(ultimo_entrenamiento.TotalVolume)
        
    return render_template('dashboard.html', 
                           username=session['username'], 
                           dias_activo=dias_activo_count, 
                           ultimo_volumen=ultimo_volumen)

@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    user = db.session.get(User, g.user.UsuarioId) 
    if not user:
        abort(404)

    if request.method == 'POST':
        user.Nombre = request.form.get('nombre')
        user.Edad = request.form.get('edad') or None
        user.Height = request.form.get('height') or None
        user.Goal = request.form.get('goal')
        
        new_weight_str = request.form.get('currentWeight')
        if new_weight_str:
            try:
                new_weight = float(new_weight_str)
                if new_weight != user.CurrentWeight:
                    user.CurrentWeight = new_weight
                    nuevo_progreso = Progreso(
                        UsuarioId=user.UsuarioId, 
                        Peso=new_weight,
                        FechaRegistro=datetime.utcnow().date()
                    )
                    db.session.add(nuevo_progreso)
                    flash('Nuevo peso registrado en tu progreso.', 'info')
            except ValueError:
                flash('El peso ingresado no es válido.', 'danger')
        
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"user_{user.UsuarioId}.{ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                user.ProfilePic = filename

        try:
            db.session.commit()
            flash('Perfil actualizado exitosamente.', 'success')
            session['username'] = user.Nombre
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el perfil: {e}', 'danger')
            
        return redirect(url_for('perfil'))

    pic_filename = user.ProfilePic or 'default.jpg'
    if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], pic_filename)):
        profile_pic_url = url_for('static', filename='img/default.jpg') 
    else:
        profile_pic_url = url_for('static', filename=f'uploads/{pic_filename}')

    return render_template('perfil.html', user=user, profile_pic_url=profile_pic_url)

@app.route('/progreso')
@login_required
def progreso():
    return redirect(url_for('perfil'))

@app.route('/progreso/agregar', methods=['POST'])
@login_required
def agregar_progreso():
    user_id = session['user_id']
    peso = request.form.get('current-weight')
    grasa = request.form.get('current-fat') or None
    musculo = request.form.get('current-muscle') or None
    
    nuevo_progreso = Progreso(
        UsuarioId=user_id, 
        Peso=peso, 
        GrasaCorporal=grasa, 
        MasaMuscular=musculo,
        FechaRegistro=datetime.utcnow().date()
    )
    
    if peso:
        user = db.session.get(User, user_id)
        user.CurrentWeight = peso
        
    db.session.add(nuevo_progreso)
    db.session.commit()
    
    flash('Nueva métrica registrada.', 'success')
    return redirect(url_for('perfil'))

@app.route('/chart-data')
@login_required
def chart_data():
    user_id = session['user_id']
    
    datos_progreso = Progreso.query.filter_by(UsuarioId=user_id).order_by(Progreso.FechaRegistro.asc()).all()
    labels_peso = [p.FechaRegistro.strftime('%d/%m/%Y') for p in datos_progreso]
    data_peso = [float(p.Peso) for p in datos_progreso if p.Peso]
    
    entrenamientos = Entrenamiento.query.filter_by(UsuarioId=user_id).order_by(Entrenamiento.Fecha.asc()).all()
    labels_fuerza = [e.Fecha.strftime('%d/%m/%Y') for e in entrenamientos if e.TotalVolume is not None]
    data_fuerza = [float(e.TotalVolume) for e in entrenamientos if e.TotalVolume is not None]

    return jsonify({
        'weightChart': {'labels': labels_peso, 'data': data_peso},
        'strengthChart': {'labels': labels_fuerza, 'data': data_fuerza}
    })

@app.route('/rutinas')
@login_required
@membership_required 
def rutinas():
    user_id = session['user_id']
    mis_rutinas = Rutina.query.filter_by(UsuarioId=user_id).all()
    return render_template('rutinas.html', username=session['username'], rutinas=mis_rutinas)

@app.route('/rutinas/crear', methods=['POST'])
@login_required
@membership_required 
def crear_rutina():
    nombre_rutina = request.form['nombre_rutina']
    nueva_rutina = Rutina(UsuarioId=session['user_id'], Nombre=nombre_rutina)
    db.session.add(nueva_rutina)
    db.session.commit()
    flash(f'Rutina "{nombre_rutina}" creada.', 'success')
    return redirect(url_for('rutina_detalle', rutina_id=nueva_rutina.RutinaId))

@app.route('/rutina/<int:rutina_id>')
@login_required
@membership_required 
def rutina_detalle(rutina_id):
    rutina = Rutina.query.get_or_404(rutina_id)
    if rutina.UsuarioId != session['user_id']: abort(403)
    
    todos_ejercicios_raw = Ejercicio.query.order_by(Ejercicio.GrupoMuscular, Ejercicio.Nombre).all()
    ejercicios_agrupados = group_exercises(todos_ejercicios_raw)
    
    ejercicios_en_rutina = RutinaEjercicio.query.filter_by(RutinaId=rutina.RutinaId).order_by(RutinaEjercicio.Orden).all()
    
    return render_template('rutina_detalle.html', 
                           username=session['username'], 
                           rutina=rutina, 
                           ejercicios_agrupados=ejercicios_agrupados, 
                           ejercicios_en_rutina=ejercicios_en_rutina)

@app.route('/rutina/<int:rutina_id>/add_ejercicio', methods=['POST'])
@login_required
@membership_required 
def add_ejercicio_a_rutina(rutina_id):
    rutina = Rutina.query.get_or_404(rutina_id)
    if rutina.UsuarioId != session['user_id']: abort(403)
    ejercicio_id = request.form['ejercicio_id']
    existe = RutinaEjercicio.query.filter_by(RutinaId=rutina_id, EjercicioId=ejercicio_id).first()
    if not existe:
        nuevo_ej_en_rutina = RutinaEjercicio(RutinaId=rutina_id, EjercicioId=ejercicio_id)
        db.session.add(nuevo_ej_en_rutina)
        db.session.commit()
        flash('Ejercicio añadido a la rutina.', 'success')
    else:
        flash('Ese ejercicio ya está en la rutina.', 'warning')
    return redirect(url_for('rutina_detalle', rutina_id=rutina_id))

@app.route('/rutina_ejercicio/<int:re_id>/add_set', methods=['POST'])
@login_required
@membership_required 
def add_set_a_ejercicio(re_id):
    rutina_ejercicio = RutinaEjercicio.query.get_or_404(re_id)
    rutina = rutina_ejercicio.rutina
    if rutina.UsuarioId != session['user_id']: abort(403)
    reps = request.form['reps']
    peso = request.form['peso']
    num_series = len(rutina_ejercicio.sets_planeados) + 1
    nuevo_set = SetPlaneado(RutinaEjercicioId=re_id, SeriesNum=num_series, Reps=reps, Peso=peso)
    db.session.add(nuevo_set)
    db.session.commit()
    flash(f'Set {num_series} añadido.', 'success')
    return redirect(url_for('rutina_detalle', rutina_id=rutina.RutinaId))

@app.route('/rutinas/explorar')
@login_required
@membership_required 
def explorar_rutinas():
    return render_template('explorar_rutinas.html')

@app.route('/rutinas/eliminar/<int:rutina_id>', methods=['GET'])
@login_required
@membership_required 
def eliminar_rutina(rutina_id):
    rutina = Rutina.query.get_or_404(rutina_id)
    if rutina.UsuarioId != session['user_id']:
        flash('No tienes permiso para eliminar esta rutina.', 'danger')
        abort(403)
    try:
        db.session.delete(rutina)
        db.session.commit()
        flash(f'Rutina "{rutina.Nombre}" eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la rutina: {e}', 'danger')
    return redirect(url_for('rutinas'))

@app.route('/rutinas/entrenamiento_vacio')
@login_required
@membership_required 
def entrenamiento_vacio():
    todos_ejercicios_raw = Ejercicio.query.order_by(Ejercicio.GrupoMuscular, Ejercicio.Nombre).all()
    ejercicios_agrupados = group_exercises(todos_ejercicios_raw)
    
    return render_template('entrenamiento_vacio.html', 
                           ejercicios_agrupados=ejercicios_agrupados)

@app.route('/rutinas/empezar/<int:rutina_id>')
@login_required
@membership_required 
def empezar_rutina(rutina_id):
    rutina = Rutina.query.get_or_404(rutina_id)
    if rutina.UsuarioId != session['user_id']:
        abort(403)
    ejercicios_en_rutina = RutinaEjercicio.query.filter_by(RutinaId=rutina.RutinaId).order_by(RutinaEjercicio.Orden).all()
    return render_template('entrenamiento_en_curso.html', rutina=rutina, ejercicios_en_rutina=ejercicios_en_rutina)

@app.route('/rutinas/explorar/add/<string:tipo_rutina>', methods=['POST'])
@login_required
@membership_required 
def add_rutina_predefinida(tipo_rutina):
    user_id = session['user_id']
    
    rutinas_pre = {
        'ppl_push': {'nombre': 'PPL - Empuje (Push)', 'ejercicios': ['Press de Banca (Barra)', 'Press de Hombros (Mancuerna, sentado)', 'Press de Banca Inclinado (Mancuerna)', 'Elevaciones Laterales (Mancuerna)', 'Extensiones de Tríceps (Polea Alta, cuerda)', 'Fondos en Paralelas (Dips)']},
        'ppl_pull': {'nombre': 'PPL - Tracción (Pull)', 'ejercicios': ['Dominadas (Pull-ups)', 'Remo con Barra (Pendlay)', 'Jalón al Pecho (Polea Alta)', 'Face Pulls (Polea)', 'Curl de Bíceps (Barra Recta)', 'Curl Martillo (Mancuerna)']},
        'ppl_leg': {'nombre': 'PPL - Pierna (Leg)', 'ejercicios': ['Sentadilla Trasera (Barra)', 'Peso Muerto Rumano (Barra)', 'Prensa de Piernas (Máquina)', 'Curl Femoral Acostado (Máquina)', 'Extensiones de Cuádriceps (Máquina)', 'Elevación de Talones de Pie (Máquina)']},
        'full_body': {'nombre': 'Full Body - 3 Días (Fuerza)', 'ejercicios': ['Sentadilla Trasera (Barra)', 'Press de Banca (Barra)', 'Peso Muerto (Convencional)', 'Press Militar (Barra, de pie)', 'Remo con Barra (Pendlay)']}
    }

    if tipo_rutina not in rutinas_pre:
        flash('Rutina predefinida no encontrada.', 'danger')
        return redirect(url_for('explorar_rutinas'))

    data = rutinas_pre[tipo_rutina]
    
    try:
        nueva_rutina = Rutina(UsuarioId=user_id, Nombre=data['nombre'])
        db.session.add(nueva_rutina)
        db.session.commit()

        for nombre_ejercicio in data['ejercicios']:
            ejercicio = Ejercicio.query.filter_by(Nombre=nombre_ejercicio).first()
            if ejercicio:
                re = RutinaEjercicio(RutinaId=nueva_rutina.RutinaId, EjercicioId=ejercicio.EjercicioId)
                db.session.add(re)
            
        db.session.commit()
        flash(f'Rutina "{data["nombre"]}" añadida a "Mis Rutinas".', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al añadir la rutina: {e}', 'danger')

    return redirect(url_for('rutinas'))


@app.route('/entrenamiento/guardar', methods=['POST'])
@login_required
@membership_required 
def guardar_entrenamiento():
    user_id = session['user_id']
    
    workout_data_json = request.form.get('workout_data')
    if not workout_data_json:
        flash('No se recibieron datos del entrenamiento.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))
        
    try:
        data = json.loads(workout_data_json)
        total_volume_calculado = 0
        
        nuevo_entrenamiento = Entrenamiento(
            UsuarioId=user_id,
            Nombre=data.get('nombre', 'Entrenamiento Rápido'),
            Fecha=datetime.utcnow().date(),
            DuracionHoras=data.get('duracion', 1.0)
        )
        db.session.add(nuevo_entrenamiento)
        db.session.commit() 

        for ej in data['ejercicios']:
            ejercicio_id = ej.get('id')
            ejercicio = db.session.get(Ejercicio, int(ejercicio_id))
            if not ejercicio:
                continue 

            for i, s in enumerate(ej['sets']):
                peso = float(s.get('peso', 0))
                reps = int(s.get('reps', 0))
                
                if reps > 0: 
                    total_volume_calculado += (peso * reps) 
                    
                    detalle = EntrenamientoDetalle(
                        EntrenamientoId=nuevo_entrenamiento.EntrenamientoId,
                        EjercicioId=ejercicio_id,
                        SeriesNum=i + 1,
                        Peso=peso,
                        Reps=reps
                    )
                    db.session.add(detalle)
        
        nuevo_entrenamiento.TotalVolume = total_volume_calculado
        
        db.session.commit()
        flash(f'¡Entrenamiento guardado con éxito! Volumen Total: {total_volume_calculado} kg', 'success')
        return redirect(url_for('perfil'))

    except json.JSONDecodeError:
        flash('Error al procesar los datos del entrenamiento (JSON inválido).', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al guardar el entrenamiento: {e}', 'danger')
        
    return redirect(request.referrer or url_for('rutinas'))

@app.route('/agenda')
@login_required
@membership_required 
def agenda():
    ahora = datetime.utcnow()
    clases_disponibles = db.session.query(Clase).options(
        db.joinedload(Clase.entrenador)
    ).filter(Clase.FechaHora >= ahora).order_by(Clase.FechaHora.asc()).all()
    
    mis_reservas_ids = [r.ClaseId for r in Reserva.query.filter_by(UsuarioId=session['user_id'], Estado='confirmada').all()]
    
    return render_template('agenda.html', 
                           username=session['username'], 
                           clases=clases_disponibles, 
                           mis_reservas=mis_reservas_ids)

@app.route('/agenda/reservar/<int:clase_id>', methods=['POST'])
@login_required
@membership_required 
def reservar_clase(clase_id):
    user_id = session['user_id']
    clase = Clase.query.get_or_404(clase_id)
    
    if clase.FechaHora < datetime.utcnow():
        flash('No puedes reservar una clase que ya ha pasado.', 'danger')
        return redirect(url_for('agenda'))
        
    reservas_actuales = Reserva.query.filter_by(ClaseId=clase_id, Estado='confirmada').count()
    if reservas_actuales >= clase.CupoMaximo:
        flash('Esta clase ya está llena.', 'warning')
        return redirect(url_for('agenda'))

    existe_reserva = Reserva.query.filter_by(UsuarioId=user_id, ClaseId=clase_id).first()
    if existe_reserva:
        flash('Ya estás inscrito en esta clase.', 'warning')
        return redirect(url_for('agenda'))
        
    nueva_reserva = Reserva(UsuarioId=user_id, ClaseId=clase_id)
    db.session.add(nueva_reserva)
    db.session.commit()
    flash(f'¡Reserva confirmada para {clase.NombreClase}!', 'success')
    return redirect(url_for('agenda'))

@app.route('/contacto', methods=['GET'])
@login_required
@membership_required 
def contacto():
    user_id = session['user_id']
    admin_user = User.query.filter_by(TipoUsuario='admin').first()
    if not admin_user:
        flash('No hay un administrador configurado para el chat.', 'danger')
        return redirect(url_for('dashboard'))
    admin_id = admin_user.UsuarioId
    mensajes = Mensaje.query.filter(
        ((Mensaje.RemitenteId == user_id) & (Mensaje.DestinatarioId == admin_id)) |
        ((Mensaje.RemitenteId == admin_id) & (Mensaje.DestinatarioId == user_id))
    ).order_by(Mensaje.FechaEnvio.asc()).all()
    return render_template('Contacto.html', username=session['username'], mensajes=mensajes, admin_id=admin_id)

@app.route('/contacto/send', methods=['POST'])
@login_required
@membership_required 
def enviar_mensaje_usuario():
    admin_user = User.query.filter_by(TipoUsuario='admin').first()
    nuevo_msg = Mensaje(RemitenteId=session['user_id'], DestinatarioId=admin_user.UsuarioId, Mensaje=request.form['mensaje'])
    db.session.add(nuevo_msg)
    db.session.commit()
    return redirect(url_for('contacto'))

@app.route('/membresia')
@login_required
def membresia():
    user_id = session['user_id']
    membresia_actual = Membresia.query.filter_by(UsuarioId=user_id).first()
    historial_pagos = Pago.query.filter_by(UsuarioId=user_id).order_by(Pago.FechaPago.desc()).all()
    
    return render_template('membresia.html', 
                           membresia=membresia_actual, 
                           pagos=historial_pagos)

@app.route('/membresia/pagar', methods=['POST'])
@login_required
def pagar_membresia():
    user_id = session['user_id']
    plan_tipo = request.form.get('plan')
    
    planes = {
        'gold': {'nombre': 'Plan Gold', 'monto': 150000},
        'silver': {'nombre': 'Plan Silver', 'monto': 100000}
    }
    
    if plan_tipo not in planes:
        flash('Plan seleccionado no válido.', 'danger')
        return redirect(url_for('membresia'))

    plan_info = planes[plan_tipo]
    
    try:
        nuevo_pago = Pago(
            UsuarioId=user_id,
            Monto=plan_info['monto'],
            MetodoPago='Tarjeta (Simulado)',
            Descripcion=f'Pago por {plan_info["nombre"]}'
        )
        db.session.add(nuevo_pago)
        
        membresia_actual = Membresia.query.filter_by(UsuarioId=user_id).first()
        hoy = datetime.utcnow().date()

        if not membresia_actual:
            fecha_inicio = hoy
            membresia_actual = Membresia(
                UsuarioId=user_id,
                Tipo=plan_info['nombre'],
                FechaInicio=fecha_inicio
            )
            db.session.add(membresia_actual)
        else:
            fecha_inicio = max(hoy, membresia_actual.FechaFin + timedelta(days=1))
            membresia_actual.Tipo = plan_info['nombre']
            membresia_actual.FechaInicio = fecha_inicio

        membresia_actual.FechaFin = fecha_inicio + timedelta(days=30)
        membresia_actual.Estado = 'activa'
        
        db.session.commit()
        flash(f'¡Pago exitoso! Tu {plan_info["nombre"]} está activo hasta {membresia_actual.FechaFin.strftime("%d de %B, %Y")}.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar el pago: {e}', 'danger')

    return redirect(url_for('membresia'))

@app.route('/membresia/cancelar', methods=['POST'])
@login_required
def cancelar_membresia():
    user_id = session['user_id']
    membresia_actual = Membresia.query.filter_by(UsuarioId=user_id).first()
    
    if membresia_actual and membresia_actual.Estado == 'activa':
        try:
            membresia_actual.Estado = 'cancelada'
            db.session.commit()
            flash(f'Tu {membresia_actual.Tipo} ha sido cancelado. Seguirá activo hasta {membresia_actual.FechaFin.strftime("%d de %B, %Y")}.', 'info')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al cancelar la membresía: {e}', 'danger')
    else:
        flash('No tienes una membresía activa para cancelar.', 'warning')
        
    return redirect(url_for('membresia'))


# --- ¡¡¡INICIO DE NUEVAS RUTAS DE ADMIN!!! ---

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    stats = {
        "total_users": User.query.count(),
        "active_memberships": Membresia.query.filter_by(Estado='activa').count(),
        "total_exercises": Ejercicio.query.count(),
        "total_classes": Clase.query.filter(Clase.FechaHora >= datetime.utcnow()).count()
    }
    return render_template('admin_dashboard.html', stats=stats)

# --- RUTAS CRUD PARA USUARIOS (ADMIN) ---

@app.route('/admin/users')
@login_required
@admin_required
def admin_list_users():
    users = User.query.order_by(User.UsuarioId).all()
    return render_template('admin_list_users.html', users=users)

@app.route('/admin/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(id):
    user = None
    if id != 0:
        user = User.query.get_or_404(id)

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        correo = request.form.get('correo')
        password = request.form.get('password')
        tipo_usuario = request.form.get('tipo_usuario')

        if user: # Editando
            user.Nombre = nombre
            user.Correo = correo
            user.TipoUsuario = tipo_usuario
            if password:
                user.set_password(password)
            flash(f'Usuario {user.Nombre} actualizado.', 'success')
        else: # Creando
            existing_user = User.query.filter_by(Correo=correo).first()
            if existing_user:
                flash('El correo electrónico ya está registrado.', 'warning')
                return render_template('admin_edit_user.html', user=None)
            
            new_user = User(Nombre=nombre, Correo=correo, TipoUsuario=tipo_usuario)
            new_user.set_password(password)
            db.session.add(new_user)
            flash(f'Usuario {nombre} creado.', 'success')
        
        db.session.commit()
        return redirect(url_for('admin_list_users'))

    return render_template('admin_edit_user.html', user=user)

@app.route('/admin/users/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(id):
    user = User.query.get_or_404(id)
    if user.UsuarioId == session['user_id']:
        flash('No puedes eliminarte a ti mismo.', 'danger')
        return redirect(url_for('admin_list_users'))
        
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f'Usuario {user.Nombre} eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar usuario (puede tener dependencias): {e}', 'danger')
        
    return redirect(url_for('admin_list_users'))

# --- RUTAS CRUD PARA EJERCICIOS (ADMIN) ---

@app.route('/admin/ejercicios')
@login_required
@admin_required
def admin_list_ejercicios():
    ejercicios = Ejercicio.query.order_by(Ejercicio.GrupoMuscular, Ejercicio.Nombre).all()
    return render_template('admin_list_ejercicios.html', ejercicios=ejercicios)

@app.route('/admin/ejercicios/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_ejercicio(id):
    ej = None
    if id != 0:
        ej = Ejercicio.query.get_or_404(id)

    muscle_groups = sorted([
        'Pecho', 'Espalda', 'Pierna', 'Hombro', 'Bíceps', 'Tríceps', 
        'Core', 'Glúteo', 'Pantorrilla', 'Cardio', 'Cuerpo Completo', 'Otros'
    ])

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        grupo_muscular = request.form.get('grupo_muscular')

        existing = Ejercicio.query.filter(Ejercicio.Nombre == nombre, Ejercicio.EjercicioId != id).first()
        if existing:
            flash(f'Error: Ya existe un ejercicio con el nombre "{nombre}".', 'danger')
            return render_template('admin_edit_ejercicio.html', ej=ej, muscle_groups=muscle_groups)

        if ej: 
            ej.Nombre = nombre
            ej.GrupoMuscular = grupo_muscular
            flash(f'Ejercicio "{nombre}" actualizado.', 'success')
        else: 
            new_ej = Ejercicio(Nombre=nombre, GrupoMuscular=grupo_muscular)
            db.session.add(new_ej)
            flash(f'Ejercicio "{nombre}" creado.', 'success')
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error de base de datos: {e}', 'danger')
            return render_template('admin_edit_ejercicio.html', ej=ej, muscle_groups=muscle_groups)
            
        return redirect(url_for('admin_list_ejercicios'))

    return render_template('admin_edit_ejercicio.html', ej=ej, muscle_groups=muscle_groups)

@app.route('/admin/ejercicios/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_ejercicio(id):
    ej = Ejercicio.query.get_or_404(id)
    
    in_rutina = RutinaEjercicio.query.filter_by(EjercicioId=id).first()
    in_entrenamiento = EntrenamientoDetalle.query.filter_by(EjercicioId=id).first()
    
    if in_rutina or in_entrenamiento:
        flash(f'Error: No se puede eliminar "{ej.Nombre}". Está en uso en rutinas de usuarios o entrenamientos registrados.', 'danger')
        return redirect(url_for('admin_list_ejercicios'))

    try:
        db.session.delete(ej)
        db.session.commit()
        flash(f'Ejercicio "{ej.Nombre}" eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el ejercicio: {e}', 'danger')
        
    return redirect(url_for('admin_list_ejercicios'))


# --- RUTAS CRUD PARA CLASES (INSTRUCTOR) ---

@app.route('/instructor/clases')
@login_required
@instructor_required
def instructor_clases():
    query = Clase.query
    if session.get('is_instructor') and not session.get('is_admin'):
        query = query.filter_by(EntrenadorId=session['user_id'])
    
    clases = query.order_by(Clase.FechaHora.desc()).all()
    return render_template('instructor_list_clases.html', clases=clases)

@app.route('/instructor/clases/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@instructor_required
def instructor_edit_clase(id):
    clase = None
    if id != 0:
        clase = Clase.query.get_or_404(id)
        if session.get('is_instructor') and not session.get('is_admin'):
            if clase.EntrenadorId != session['user_id']:
                flash('No tienes permiso para editar esta clase.', 'danger')
                return redirect(url_for('instructor_clases'))

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        cupo = request.form.get('cupo')
        fecha_hora_str = request.form.get('fecha_hora')
        fecha_hora = datetime.strptime(fecha_hora_str, '%Y-%m-%dT%H:%M')

        if clase: 
            clase.NombreClase = nombre
            clase.CupoMaximo = cupo
            clase.FechaHora = fecha_hora
            flash(f'Clase {clase.NombreClase} actualizada.', 'success')
        else: 
            new_clase = Clase(
                NombreClase=nombre,
                CupoMaximo=cupo,
                FechaHora=fecha_hora,
                EntrenadorId=session['user_id'] 
            )
            db.session.add(new_clase)
            flash(f'Clase {nombre} creada.', 'success')
        
        db.session.commit()
        return redirect(url_for('instructor_clases'))

    return render_template('instructor_edit_clase.html', clase=clase)

@app.route('/instructor/clases/delete/<int:id>', methods=['POST'])
@login_required
@instructor_required
def instructor_delete_clase(id):
    clase = Clase.query.get_or_404(id)
    if session.get('is_instructor') and not session.get('is_admin'):
        if clase.EntrenadorId != session['user_id']:
            flash('No tienes permiso para eliminar esta clase.', 'danger')
            return redirect(url_for('instructor_clases'))
            
    try:
        db.session.delete(clase)
        db.session.commit()
        flash(f'Clase {clase.NombreClase} eliminada.', 'success')
    except exc.IntegrityError:
        db.session.rollback()
        flash(f'Error: No se puede eliminar "{clase.NombreClase}". Ya tiene reservas de usuarios.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la clase: {e}', 'danger')
        
    return redirect(url_for('instructor_clases'))


# --- ¡¡¡NUEVA RUTA DE LIMPIEZA DE ADMIN!!! ---

@app.route('/admin/cleanup/past-classes', methods=['POST'])
@login_required
@admin_required
def admin_cleanup_past_classes():
    ahora = datetime.utcnow()
    clases_a_eliminar = Clase.query.filter(Clase.FechaHora < ahora).all()
    
    if not clases_a_eliminar:
        flash('No hay clases pasadas para eliminar.', 'info')
        return redirect(url_for('admin_dashboard'))

    borradas = 0
    errores = 0
    
    for clase in clases_a_eliminar:
        try:
            # Esto fallará si la clase tiene reservas, lo cual es bueno.
            db.session.delete(clase)
            db.session.commit()
            borradas += 1
        except exc.IntegrityError:
            db.session.rollback() # Revierte el borrado de esta clase
            errores += 1
        except Exception as e:
            db.session.rollback()
            errores += 1
            print(f"Error inesperado al borrar clase {clase.ClaseId}: {e}")

    if borradas > 0:
        flash(f'Se eliminaron {borradas} clases pasadas (sin reservas).', 'success')
    if errores > 0:
        flash(f'No se pudieron eliminar {errores} clases porque tienen reservas de usuarios (historial).', 'warning')
    
    return redirect(url_for('admin_dashboard'))


# --- RUTAS DE CHAT (Sin cambios) ---

@app.route('/admin/chat')
@login_required
@admin_required
def admin_chat_list():
    admin_id = session['user_id']
    users = User.query.filter(User.UsuarioId != admin_id, User.TipoUsuario == 'regular').order_by(User.Nombre).all()
    return render_template('admin_chat_list.html', users=users, username=session['username'])

@app.route('/admin/chat/<int:user_id>', methods=['GET'])
@login_required
@admin_required
def admin_chat_view(user_id):
    admin_id = session['user_id']
    destinatario = User.query.get_or_404(user_id)
    mensajes = Mensaje.query.filter(
        ((Mensaje.RemitenteId == user_id) & (Mensaje.DestinatarioId == admin_id)) |
        ((Mensaje.RemitenteId == admin_id) & (Mensaje.DestinatarioId == user_id))
    ).order_by(Mensaje.FechaEnvio.asc()).all()
    return render_template('admin_chat_view.html', mensajes=mensajes, destinatario=destinatario, admin_id=admin_id, username=session['username'])

@app.route('/admin/chat/send/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def enviar_mensaje_admin(user_id):
    nuevo_msg = Mensaje(RemitenteId=session['user_id'], DestinatarioId=user_id, Mensaje=request.form['mensaje'])
    db.session.add(nuevo_msg)
    db.session.commit()
    return redirect(url_for('admin_chat_view', user_id=user_id))


# --- (Funciones de inicialización sin cambios) ---
def populate_exercises():
    if Ejercicio.query.count() > 0:
        return 
    print("Poblando la base de datos con la lista de ejercicios extendida...")
    ejercicios_default = [
        Ejercicio(Nombre='Press de Banca (Barra)', GrupoMuscular='Pecho'),
        Ejercicio(Nombre='Press de Banca Inclinado (Mancuerna)', GrupoMuscular='Pecho'),
        Ejercicio(Nombre='Press de Banca Declinado (Barra)', GrupoMuscular='Pecho'),
        Ejercicio(Nombre='Aperturas con Mancuernas (Plano)', GrupoMuscular='Pecho'),
        Ejercicio(Nombre='Aperturas Inclinadas (Mancuerna)', GrupoMuscular='Pecho'),
        Ejercicio(Nombre='Flexiones (Push-ups)', GrupoMuscular='Pecho'),
        Ejercicio(Nombre='Fondos en Paralelas (Dips)', GrupoMuscular='Pecho'),
        Ejercicio(Nombre='Cruce de Poleas (Alto)', GrupoMuscular='Pecho'),
        Ejercicio(Nombre='Pec Deck (Máquina)', GrupoMuscular='Pecho'),
        Ejercicio(Nombre='Dominadas (Pull-ups)', GrupoMuscular='Espalda'),
        Ejercicio(Nombre='Dominadas (Agarre Neutro)', GrupoMuscular='Espalda'),
        Ejercicio(Nombre='Jalón al Pecho (Polea Alta)', GrupoMuscular='Espalda'),
        Ejercicio(Nombre='Remo con Barra (Pendlay)', GrupoMuscular='Espalda'),
        Ejercicio(Nombre='Remo con Mancuerna (Unilateral)', GrupoMuscular='Espalda'),
        Ejercicio(Nombre='Remo Sentado (Polea Baja)', GrupoMuscular='Espalda'),
        Ejercicio(Nombre='Remo en T (Barra T)', GrupoMuscular='Espalda'),
        Ejercicio(Nombre='Peso Muerto (Convencional)', GrupoMuscular='Espalda'),
        Ejercicio(Nombre='Hiperextensiones (Espalda Baja)', GrupoMuscular='Espalda'),
        Ejercicio(Nombre='Pullover (Polea Alta)', GrupoMuscular='Espalda'),
        Ejercicio(Nombre='Sentadilla Trasera (Barra)', GrupoMuscular='Pierna'),
        Ejercicio(Nombre='Sentadilla Frontal (Barra)', GrupoMuscular='Pierna'),
        Ejercicio(Nombre='Prensa de Piernas (Máquina)', GrupoMuscular='Pierna'),
        Ejercicio(Nombre='Sentadilla Búlgara (Mancuerna)', GrupoMuscular='Pierna'),
        Ejercicio(Nombre='Zancadas (Lunges)', GrupoMuscular='Pierna'),
        Ejercicio(Nombre='Extensiones de Cuádriceps (Máquina)', GrupoMuscular='Pierna'),
        Ejercicio(Nombre='Sentadilla Hack (Máquina)', GrupoMuscular='Pierna'),
        Ejercicio(Nombre='Peso Muerto Rumano (Mancuerna)', GrupoMuscular='Pierna'),
        Ejercicio(Nombre='Peso Muerto Rumano (Barra)', GrupoMuscular='Pierna'),
        Ejercicio(Nombre='Curl Femoral Acostado (Máquina)', GrupoMuscular='Pierna'),
        Ejercicio(Nombre='Curl Femoral Sentado (Máquina)', GrupoMuscular='Pierna'),
        Ejercicio(Nombre='Hip Thrust (Barra)', GrupoMuscular='Glúteo'),
        Ejercicio(Nombre='Patada de Glúteo (Polea)', GrupoMuscular='Glúteo'),
        Ejercicio(Nombre='Abducción de Cadera (Máquina)', GrupoMuscular='Glúteo'),
        Ejercicio(Nombre='Elevación de Talones de Pie (Máquina)', GrupoMuscular='Pantorrilla'),
        Ejercicio(Nombre='Elevación de Talones Sentado (Máquina)', GrupoMuscular='Pantorrilla'),
        Ejercicio(Nombre='Press Militar (Barra, de pie)', GrupoMuscular='Hombro'),
        Ejercicio(Nombre='Press de Hombros (Mancuerna, sentado)', GrupoMuscular='Hombro'),
        Ejercicio(Nombre='Press Arnold (Mancuerna)', GrupoMuscular='Hombro'),
        Ejercicio(Nombre='Elevaciones Laterales (Mancuerna)', GrupoMuscular='Hombro'),
        Ejercicio(Nombre='Elevaciones Laterales (Polea)', GrupoMuscular='Hombro'),
        Ejercicio(Nombre='Elevaciones Frontales (Mancuerna)', GrupoMuscular='Hombro'),
        Ejercicio(Nombre='Pájaros (Mancuerna)', GrupoMuscular='Hombro'),
        Ejercicio(Nombre='Face Pulls (Polea)', GrupoMuscular='Hombro'),
        Ejercicio(Nombre='Encogimientos (Mancuerna)', GrupoMuscular='Hombro'),
        Ejercicio(Nombre='Curl de Bíceps (Barra Recta)', GrupoMuscular='Bíceps'),
        Ejercicio(Nombre='Curl de Bíceps (Mancuerna, alterno)', GrupoMuscular='Bíceps'),
        Ejercicio(Nombre='Curl Martillo (Mancuerna)', GrupoMuscular='Bíceps'),
        Ejercicio(Nombre='Curl Predicador (Barra Z)', GrupoMuscular='Bíceps'),
        Ejercicio(Nombre='Curl Concentrado (Mancuerna)', GrupoMuscular='Bíceps'),
        Ejercicio(Nombre='Curl en Polea Baja', GrupoMuscular='Bíceps'),
        Ejercicio(Nombre='Press Francés (Barra Z)', GrupoMuscular='Tríceps'),
        Ejercicio(Nombre='Extensiones de Tríceps (Polea Alta, cuerda)', GrupoMuscular='Tríceps'),
        Ejercicio(Nombre='Extensiones de Tríceps (Polea Alta, barra V)', GrupoMuscular='Tríceps'),
        Ejercicio(Nombre='Extensión sobre la cabeza (Mancuerna)', GrupoMuscular='Tríceps'),
        Ejercicio(Nombre='Fondos entre bancos', GrupoMuscular='Tríceps'),
        Ejercicio(Nombre='Press de Banca (Agarre Cerrado)', GrupoMuscular='Tríceps'),
        Ejercicio(Nombre='Plancha (Plank)', GrupoMuscular='Core'),
        Ejercicio(Nombre='Plancha Lateral (Side Plank)', GrupoMuscular='Core'),
        Ejercicio(Nombre='Elevación de Piernas Colgado', GrupoMuscular='Core'),
        Ejercicio(Nombre='Crunch Abdominal (Suelo)', GrupoMuscular='Core'),
        Ejercicio(Nombre='Rueda Abdominal (Ab Wheel)', GrupoMuscular='Core'),
        Ejercicio(Nombre='Russian Twist (Giro Ruso)', GrupoMuscular='Core'),
        Ejercicio(Nombre='Woodchoppers (Leñador con polea)', GrupoMuscular='Core'),
        Ejercicio(Nombre='Burpees', GrupoMuscular='Cuerpo Completo'),
        Ejercicio(Nombre='Saltar la Cuerda', GrupoMuscular='Cardio'),
        Ejercicio(Nombre='Correr (Cinta)', GrupoMuscular='Cardio'),
        Ejercicio(Nombre='Bicicleta (Estática)', GrupoMuscular='Cardio'),
        Ejercicio(Nombre='Remo (Máquina)', GrupoMuscular='Cardio'),
        Ejercicio(Nombre='Sprints', GrupoMuscular='Cardio'),
    ]
    try:
        db.session.bulk_save_objects(ejercicios_default)
        db.session.commit()
        print(f"{len(ejercicios_default)} ejercicios predeterminados creados.")
    except Exception as e:
        db.session.rollback()
        print(f"Error al poblar ejercicios: {e}")

def populate_classes(instructor_ids):
    if Clase.query.count() > 0:
        return
    if not instructor_ids:
        return
    print("Poblando la base de datos con clases dinámicas...")
    nombres_clases = ["Spinning", "Yoga Flow", "Boxeo Funcional", "HIIT Total", "CrossFit WOD", "Zumba Fitness", "Pilates Mat", "Entrenamiento Funcional", "ABS Core"]
    horarios = [time(7, 0), time(8, 30), time(12, 0), time(18, 0), time(19, 30)]
    today = datetime.utcnow().date()
    clases_a_crear = []
    for i in range(10):
        dia = today + timedelta(days=i)
        horarios_del_dia = random.sample(horarios, 4)
        for hora in horarios_del_dia:
            nueva_clase = Clase(
                NombreClase=random.choice(nombres_clases),
                FechaHora=datetime.combine(dia, hora),
                CupoMaximo=random.randint(15, 25),
                EntrenadorId=random.choice(instructor_ids)
            )
            clases_a_crear.append(nueva_clase)
    try:
        db.session.bulk_save_objects(clases_a_crear)
        db.session.commit()
        print(f"{len(clases_a_crear)} clases dinámicas creadas.")
    except Exception as e:
        db.session.rollback()
        print(f"Error al poblar clases: {e}")

def create_default_instructors():
    if User.query.filter_by(TipoUsuario='instructor').count() > 0:
        return 
    print("Creando instructores por defecto...")
    instructores = [
        User(Nombre='Ana Gabriela Duque', Correo='ana.duque@activetrack.com', TipoUsuario='instructor'),
        User(Nombre='Valerie Bonilla', Correo='valerie.bonilla@activetrack.com', TipoUsuario='instructor'),
        User(Nombre='Luisa Pineda', Correo='luisa.pineda@activetrack.com', TipoUsuario='instructor')
    ]
    try:
        for inst in instructores:
            inst.set_password('instructor123')
            db.session.add(inst)
        db.session.commit()
        print("3 instructores por defecto creados.")
    except Exception as e:
        db.session.rollback()
        print(f"Error al crear instructores: {e}")

def create_default_admin():
    if not User.query.filter_by(Correo='admin@activetrack.com').first():
        print("Creando admin por defecto...")
        admin_user = User(Nombre='ActiveTrack Admin', Correo='admin@activetrack.com', TipoUsuario='admin')
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        print("Admin por defecto (admin@activetrack.com) creado con contraseña 'admin123'.")

def create_demo_user():
    if User.query.filter_by(Correo='carlos.demo@activetrack.com').first():
        print("El usuario de demostración 'Carlos Demo' ya existe.")
        return
    
    print("Creando usuario de demostración 'Carlos Demo'...")
    try:
        demo_user = User(
            Nombre='Carlos Demo',
            Correo='carlos.demo@activetrack.com',
            TipoUsuario='regular',
            Height=175,
            CurrentWeight=78.0
        )
        demo_user.set_password('demo123')
        db.session.add(demo_user)
        db.session.commit() 

        demo_membresia = Membresia(
            UsuarioId=demo_user.UsuarioId,
            Tipo='Plan Gold (Demo)',
            FechaInicio=datetime.utcnow().date() - timedelta(days=10),
            FechaFin=datetime.utcnow().date() + timedelta(days=365), 
            Estado='activa'
        )
        db.session.add(demo_membresia)
        
        today = datetime.utcnow().date()
        peso_actual = 78.0
        registros_progreso = []
        for i in range(365, 0, -3): 
            fecha_registro = today - timedelta(days=i)
            peso_actual += random.uniform(-0.5, 0.7)
            progreso = Progreso(
                UsuarioId=demo_user.UsuarioId,
                Peso=round(peso_actual, 1),
                FechaRegistro=fecha_registro
            )
            registros_progreso.append(progreso)
        db.session.bulk_save_objects(registros_progreso)
        demo_user.CurrentWeight = round(peso_actual, 1) 

        ejercicios = Ejercicio.query.all()
        if not ejercicios:
            print("No hay ejercicios para crear entrenos de demo.")
            return

        entrenamientos_demo = []
        detalles_demo = []
        for i in range(365, 0, -2): 
            if len(entrenamientos_demo) >= 150:
                break
            
            fecha_entreno = today - timedelta(days=i)
            if fecha_entreno.weekday() >= 5: 
                continue
                
            entreno = Entrenamiento(
                UsuarioId=demo_user.UsuarioId,
                Nombre=random.choice(['Día de Pecho', 'Rutina de Pierna', 'Entreno de Espalda']),
                Fecha=fecha_entreno,
                DuracionHoras=round(random.uniform(1.0, 1.75), 2),
                TotalVolume=0 
            )
            entrenamientos_demo.append(entreno)
            
        db.session.bulk_save_objects(entrenamientos_demo)
        db.session.commit() 

        all_entrenos = Entrenamiento.query.filter_by(UsuarioId=demo_user.UsuarioId).all()
        for entreno in all_entrenos:
            volumen_total_entreno = 0
            ejercicios_del_dia = random.sample(ejercicios, 4) 
            
            for ej in ejercicios_del_dia:
                for s in range(1, 4): 
                    peso = round(random.uniform(50, 100) / 2.5) * 2.5 
                    reps = random.randint(8, 12)
                    volumen_total_entreno += (peso * reps)
                    
                    detalle = EntrenamientoDetalle(
                        EntrenamientoId=entreno.EntrenamientoId,
                        EjercicioId=ej.EjercicioId,
                        SeriesNum=s,
                        Peso=peso,
                        Reps=reps
                    )
                    detalles_demo.append(detalle)
            
            entreno.TotalVolume = volumen_total_entreno 
            
        db.session.bulk_save_objects(detalles_demo)
        db.session.commit()
        
        print(f"Usuario 'Carlos Demo' creado con 1 año de historial ({len(registros_progreso)} registros de peso, {len(entrenamientos_demo)} entrenos).")
    
    except Exception as e:
        db.session.rollback()
        print(f"Error al crear usuario de demostración: {e}")

# --- INICIALIZACIÓN DE LA APP ---
if __name__ == '__main__':
    if not os.path.exists(os.path.join(basedir, 'instance')):
        os.makedirs(os.path.join(basedir, 'instance'))
    
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        
    with app.app_context():
        if not os.path.exists(db_path):
            print("Creando base de datos...")
            db.create_all()
            print("Base de datos creada.")
        
        create_default_admin()
        create_default_instructors()
        populate_exercises() 
        
        instructor_ids = [u.UsuarioId for u in User.query.filter_by(TipoUsuario='instructor').all()]
        populate_classes(instructor_ids)
        
        create_demo_user()
            
    app.run(debug=True)