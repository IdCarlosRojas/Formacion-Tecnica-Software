# app.py
import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for, flash, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from sqlalchemy import or_

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui_CAMBIAME'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- CONFIGURACIÓN DE BASE DE DATOS ---
basedir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'soul_tc_final.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELOS DE BASE DE DATOS ---
class Usuarios(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    tipoUsuario = db.Column(db.String(20), nullable=False, default='cliente') # admin, tatuador, cliente
    telefono = db.Column(db.String(50), nullable=True)
    fechaRegistro = db.Column(db.String(100), nullable=False, default=datetime.now().isoformat)

    perfil = db.relationship('TatuadorPerfil', backref='usuario', uselist=False, cascade="all, delete-orphan")
    portafolios = db.relationship('Portafolio', backref='tatuador', lazy=True, cascade="all, delete-orphan")
    citas_enviadas = db.relationship('Citas', foreign_keys='Citas.clienteId', backref='cliente', lazy=True, cascade="all, delete-orphan")
    citas_recibidas = db.relationship('Citas', foreign_keys='Citas.tatuadorId', backref='tatuador', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class TatuadorPerfil(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuarioId = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete="CASCADE"), unique=True, nullable=False)
    especialidades = db.Column(db.Text, nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    tarifas = db.Column(db.String(200), nullable=True)
    redesSociales = db.Column(db.String(200), nullable=True)
    ubicacion = db.Column(db.String(200), nullable=True)
    latitud = db.Column(db.Float, nullable=True)
    longitud = db.Column(db.Float, nullable=True)

class Portafolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tatuadorId = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete="CASCADE"), nullable=False)
    titulo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    fechaCreacion = db.Column(db.String(100), nullable=False, default=datetime.now().isoformat)
    imagenes = db.relationship('ImagenesPortafolio', backref='portafolio', lazy=True, cascade="all, delete-orphan")

class ImagenesPortafolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    portafolioId = db.Column(db.Integer, db.ForeignKey('portafolio.id', ondelete="CASCADE"), nullable=False)
    rutaImagen = db.Column(db.String(100), nullable=False)

class Citas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    clienteId = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    tatuadorId = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha = db.Column(db.String(50), nullable=False)
    hora = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    estado = db.Column(db.String(50), nullable=False, default='Pendiente') # Pendiente, Aprobada, Cancelada, Completada
    resena = db.relationship('Resenas', backref='cita', uselist=False, cascade="all, delete-orphan")

class Resenas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    citaId = db.Column(db.Integer, db.ForeignKey('citas.id', ondelete="CASCADE"), unique=True, nullable=False)
    calificacion = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.Text, nullable=True)
    fecha = db.Column(db.String(100), nullable=False, default=datetime.now().isoformat)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- RUTAS PÚBLICAS Y DE AUTENTICACIÓN ---

@app.route('/')
def index():
    if 'usuarioId' in session:
        return redirect(url_for('dashboard'))
    
    tatuadores = db.session.query(
        Usuarios, func.count(Resenas.id).label('total_resenas')
    ).join(TatuadorPerfil).join(Citas, Usuarios.id == Citas.tatuadorId).join(Resenas).filter(
        Usuarios.tipoUsuario == 'tatuador',
        Citas.estado == 'Completada'
    ).group_by(Usuarios.id).order_by(func.count(Resenas.id).desc()).limit(6).all()
    
    tatuadores_obj = [t[0] for t in tatuadores]

    return render_template('index.html', tatuadores=tatuadores_obj)

@app.route('/registro', methods=['GET','POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        contraseña = request.form['contraseña']
        tipo = request.form['tipo']
        telefono = request.form.get('telefono')
        
        user_exists = Usuarios.query.filter_by(email=email).first()
        if user_exists:
            flash('El correo ya está registrado', 'error')
            return redirect(url_for('registro'))
            
        nuevo_usuario = Usuarios(
            nombre=nombre,
            email=email,
            tipoUsuario=tipo,
            telefono=telefono
        )
        nuevo_usuario.set_password(contraseña)
        
        try:
            db.session.add(nuevo_usuario)
            db.session.commit()
            
            if nuevo_usuario.tipoUsuario == 'tatuador':
                nuevo_perfil = TatuadorPerfil(usuarioId=nuevo_usuario.id)
                db.session.add(nuevo_perfil)
                db.session.commit()
                
            flash('¡Registro exitoso! Por favor, inicia sesión.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la cuenta: {e}', 'danger')
            
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email = request.form['email']
        contraseña = request.form['contraseña']
        user = Usuarios.query.filter_by(email=email).first()
        
        if user and user.check_password(contraseña):
            session['usuarioId'] = user.id
            session['nombre'] = user.nombre
            session['tipoUsuario'] = user.tipoUsuario
            flash(f'¡Bienvenido de nuevo, {user.nombre}!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Credenciales inválidas.', 'danger')
    
    demo_clients = Usuarios.query.filter(
        Usuarios.tipoUsuario=='cliente', 
        Usuarios.email.like('%@test.com')
    ).limit(5).all()
    
    demo_tattooers = Usuarios.query.filter(
        Usuarios.tipoUsuario=='tatuador', 
        Usuarios.email.like('%@test.com')
    ).limit(5).all()

    return render_template('login.html', 
                           demo_clients=demo_clients, 
                           demo_tattooers=demo_tattooers)

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

@app.route('/buscar')
def buscar():
    query_especialidad = request.args.get('q', '')
    query_ubicacion = request.args.get('loc', '')

    query = TatuadorPerfil.query.join(Usuarios).filter(Usuarios.tipoUsuario == 'tatuador')

    if query_especialidad:
        search_term = f"%{query_especialidad.lower()}%"
        query = query.filter(TatuadorPerfil.especialidades.ilike(search_term))

    if query_ubicacion:
        search_term = f"%{query_ubicacion.lower()}%"
        query = query.filter(TatuadorPerfil.ubicacion.ilike(search_term))

    tatuadores_con_perfil = query.all()

    map_data = []
    for perfil in tatuadores_con_perfil:
        if perfil.latitud and perfil.longitud:
            map_data.append({
                "lat": perfil.latitud,
                "lon": perfil.longitud,
                "nombre": perfil.usuario.nombre,
                "url": url_for('perfil_tatuador', id=perfil.usuarioId),
                "especialidades": perfil.especialidades or "Artista"
            })

    return render_template('buscar.html', 
                           tatuadores=tatuadores_con_perfil, 
                           map_data=json.dumps(map_data),
                           query_especialidad=query_especialidad,
                           query_ubicacion=query_ubicacion)

@app.route('/dashboard')
def dashboard():
    if 'usuarioId' not in session:
        return redirect(url_for('login'))
    
    tipo = session['tipoUsuario']
    if tipo == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif tipo == 'tatuador':
        return redirect(url_for('artista_dashboard'))
    else:
        return redirect(url_for('dashboard_cliente'))

@app.route('/dashboard_cliente')
def dashboard_cliente():
    if 'tipoUsuario' not in session or session['tipoUsuario'] != 'cliente':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    usuario = Usuarios.query.get(session['usuarioId'])
    citas = Citas.query.filter_by(clienteId=session['usuarioId']).order_by(Citas.fecha.desc()).all()
    
    tatuadores = TatuadorPerfil.query.join(Usuarios).filter(Usuarios.tipoUsuario == 'tatuador').all()
    recomendados = []

    for perfil in tatuadores:
        citas_ids = [c.id for c in Citas.query.filter_by(tatuadorId=perfil.usuarioId, estado='Completada').all()]
        num_reviews = len(citas_ids)
        avg_rating = 0
        
        if num_reviews > 0:
            avg_rating = db.session.query(func.avg(Resenas.calificacion)).filter(Resenas.citaId.in_(citas_ids)).scalar() or 0
        
        num_portfolio = len(perfil.usuario.portafolios)
        score = (avg_rating * 2) + (num_reviews * 1) + (num_portfolio * 0.5)
        
        if score > 0:
             recomendados.append((perfil, score, avg_rating, num_reviews))

    recomendados.sort(key=lambda x: x[1], reverse=True)
    recomendados_top_5 = recomendados[:5]
    
    return render_template('dashboard_cliente.html', 
                           usuario=usuario, 
                           citas=citas, 
                           recomendados=recomendados_top_5)

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'tipoUsuario' not in session or session['tipoUsuario'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    total_usuarios = Usuarios.query.count()
    total_tatuadores = Usuarios.query.filter_by(tipoUsuario='tatuador').count()
    total_citas = Citas.query.count()
    total_resenas = Resenas.query.count()
    
    return render_template('admin_dashboard.html',
                           total_usuarios=total_usuarios,
                           total_tatuadores=total_tatuadores,
                           total_citas=total_citas,
                           total_resenas=total_resenas)

@app.route('/admin/usuarios')
def gestionar_usuarios():
    if 'tipoUsuario' not in session or session['tipoUsuario'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    usuarios = Usuarios.query.order_by(Usuarios.id.desc()).all()
    return render_template('gestionar_usuarios.html', usuarios=usuarios)

@app.route('/admin/usuario/rol', methods=['POST'])
def cambiar_rol_usuario():
    if 'tipoUsuario' not in session or session['tipoUsuario'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
        
    usuario_id = request.form.get('usuario_id')
    nuevo_rol = request.form.get('tipoUsuario')
    
    usuario = Usuarios.query.get(usuario_id)
    if usuario and nuevo_rol in ['cliente', 'tatuador', 'admin']:
        if nuevo_rol == 'tatuador' and not usuario.perfil:
            nuevo_perfil = TatuadorPerfil(usuarioId=usuario.id)
            db.session.add(nuevo_perfil)
            
        usuario.tipoUsuario = nuevo_rol
        db.session.commit()
        flash(f'Rol de {usuario.nombre} actualizado a {nuevo_rol}.', 'success')
    else:
        flash('Error al actualizar el rol.', 'danger')
        
    return redirect(url_for('gestionar_usuarios'))

@app.route('/admin/citas')
def gestionar_citas_admin():
    if 'tipoUsuario' not in session or session['tipoUsuario'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    citas = Citas.query.order_by(Citas.id.desc()).all()
    return render_template('gestionar_citas_admin.html', citas=citas)

@app.route('/artista_dashboard')
def artista_dashboard():
    if 'tipoUsuario' not in session or session['tipoUsuario'] != 'tatuador':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    usuario = Usuarios.query.get(session['usuarioId'])
    perfil = TatuadorPerfil.query.filter_by(usuarioId=session['usuarioId']).first()
    if not perfil:
        perfil = TatuadorPerfil(usuarioId=session['usuarioId'])
    
    citas = Citas.query.filter_by(tatuadorId=session['usuarioId']).order_by(Citas.fecha.desc()).all()
    citas_pendientes = [c for c in citas if c.estado == 'Pendiente']
    citas_aprobadas = [c for c in citas if c.estado == 'Aprobada']

    return render_template('artista_dashboard.html', 
                           usuario=usuario, 
                           perfil=perfil, 
                           citas=citas, 
                           citas_pendientes=citas_pendientes,
                           citas_aprobadas=citas_aprobadas)

@app.route('/crear_perfil', methods=['POST'])
def crear_perfil():
    if 'tipoUsuario' not in session or session['tipoUsuario'] != 'tatuador':
        return redirect(url_for('login'))
    
    perfil = TatuadorPerfil.query.filter_by(usuarioId=session['usuarioId']).first()
    if not perfil:
        perfil = TatuadorPerfil(usuarioId=session['usuarioId'])
        db.session.add(perfil)
    
    perfil.especialidades = request.form.get('especialidades')
    perfil.descripcion = request.form.get('descripcion')
    perfil.tarifas = request.form.get('tarifas')
    perfil.redesSociales = request.form.get('redesSociales')
    perfil.ubicacion = request.form.get('ubicacion')
    
    try:
        perfil.latitud = float(request.form.get('latitud')) if request.form.get('latitud') else None
        perfil.longitud = float(request.form.get('longitud')) if request.form.get('longitud') else None
    except ValueError:
        flash('Las coordenadas deben ser números (ej. 4.6097, -74.0817)', 'danger')
        return redirect(url_for('artista_dashboard'))
    
    try:
        db.session.commit()
        flash('Perfil actualizado con éxito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar el perfil: {e}', 'danger')
        
    return redirect(url_for('artista_dashboard'))

@app.route('/nuevo_portafolio', methods=['GET', 'POST'])
def nuevo_portafolio():
    if 'tipoUsuario' not in session or session['tipoUsuario'] != 'tatuador':
        return redirect(url_for('login'))
    if request.method == 'POST':
        titulo = request.form['titulo']
        descripcion = request.form.get('descripcion')
        nuevo_item = Portafolio(tatuadorId=session['usuarioId'], titulo=titulo, descripcion=descripcion)
        db.session.add(nuevo_item)
        try: db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el item: {e}', 'danger')
            return redirect(url_for('nuevo_portafolio'))
        files = request.files.getlist('imagenes')
        if not files or files[0].filename == '':
            flash('Debes subir al menos una imagen.', 'warning')
            db.session.delete(nuevo_item)
            db.session.commit()
            return redirect(url_for('nuevo_portafolio'))
        for f in files:
            if f and allowed_file(f.filename):
                filename = secure_filename(f.filename)
                filename = f"{int(datetime.now().timestamp())}_{filename}"
                path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                try:
                    f.save(path)
                    nueva_imagen = ImagenesPortafolio(portafolioId=nuevo_item.id, rutaImagen=filename)
                    db.session.add(nueva_imagen)
                except Exception as e:
                    flash(f'Error al guardar la imagen {f.filename}: {e}', 'danger')
        db.session.commit()
        flash('¡Nuevo trabajo añadido al portafolio!', 'success')
        return redirect(url_for('artista_dashboard'))
    return render_template('nuevo_portafolio.html')

@app.route('/tatuador/<int:id>')
def perfil_tatuador(id):
    tatuador = Usuarios.query.get_or_404(id)
    if tatuador.tipoUsuario != 'tatuador':
        flash('Usuario no es un tatuador.', 'error')
        return redirect(url_for('index'))
        
    perfil = TatuadorPerfil.query.filter_by(usuarioId=id).first()
    portafolios = Portafolio.query.filter_by(tatuadorId=id).order_by(Portafolio.id.desc()).all()
    citas_completadas_ids = [c.id for c in Citas.query.filter_by(tatuadorId=id, estado='Completada').all()]
    resenas = Resenas.query.filter(Resenas.citaId.in_(citas_completadas_ids)).order_by(Resenas.fecha.desc()).all()
    avg_rating = 0
    if resenas:
        avg_rating = db.session.query(func.avg(Resenas.calificacion)).filter(Resenas.citaId.in_(citas_completadas_ids)).scalar()
        avg_rating = round(avg_rating, 1)

    return render_template('perfil_tatuador.html', 
                           tatuador=tatuador, 
                           perfil=perfil, 
                           portafolios=portafolios,
                           resenas=resenas,
                           avg_rating=avg_rating)

@app.route('/solicitar_cita/<int:tatuador_id>', methods=['GET'])
def solicitar_cita(tatuador_id):
    if 'usuarioId' not in session:
        flash('Debes iniciar sesión como cliente para pedir una cita.', 'info')
        return redirect(url_for('login'))
    tatuador = Usuarios.query.get_or_404(tatuador_id)
    return render_template('solicitar_cita.html', tatuador=tatuador)

@app.route('/crear_cita', methods=['POST'])
def crear_cita():
    if 'usuarioId' not in session:
        return redirect(url_for('login'))
    nueva_cita = Citas(
        clienteId=session['usuarioId'],
        tatuadorId=request.form.get('tatuador_id'),
        fecha=request.form.get('fecha'),
        hora=request.form.get('hora'),
        descripcion=request.form.get('descripcion'),
        estado='Pendiente'
    )
    try:
        db.session.add(nueva_cita)
        db.session.commit()
        flash('¡Solicitud de cita enviada!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al enviar la solicitud: {e}', 'danger')
    return redirect(url_for('dashboard_cliente'))

@app.route('/cita/aprobar/<int:cita_id>', methods=['POST'])
def aprobar_cita(cita_id):
    if 'tipoUsuario' not in session or session['tipoUsuario'] != 'tatuador':
        return redirect(url_for('login'))
    cita = Citas.query.get_or_404(cita_id)
    if cita.tatuadorId != session['usuarioId']:
        return redirect(url_for('artista_dashboard'))
    cita.estado = 'Aprobada'
    db.session.commit()
    flash('Cita aprobada con éxito.', 'success')
    return redirect(url_for('artista_dashboard'))

@app.route('/cita/cancelar/<int:cita_id>', methods=['POST'])
def cancelar_cita(cita_id):
    if 'tipoUsuario' not in session or session['tipoUsuario'] != 'tatuador':
        return redirect(url_for('login'))
    cita = Citas.query.get_or_404(cita_id)
    if cita.tatuadorId != session['usuarioId']:
        return redirect(url_for('artista_dashboard'))
    cita.estado = 'Cancelada'
    db.session.commit()
    flash('Cita cancelada.', 'info')
    return redirect(url_for('artista_dashboard'))

@app.route('/cita/completar/<int:cita_id>', methods=['POST'])
def marcar_completada(cita_id):
    if 'tipoUsuario' not in session or session['tipoUsuario'] != 'tatuador':
        return redirect(url_for('login'))
    cita = Citas.query.get_or_404(cita_id)
    if cita.tatuadorId != session['usuarioId']:
        return redirect(url_for('artista_dashboard'))
    cita.estado = 'Completada'
    db.session.commit()
    flash('Cita marcada como completada. El cliente ya puede dejar una reseña.', 'success')
    return redirect(url_for('artista_dashboard'))

@app.route('/dejar_resena/<int:cita_id>', methods=['GET', 'POST'])
def dejar_resena(cita_id):
    if 'tipoUsuario' not in session or session['tipoUsuario'] != 'cliente':
        return redirect(url_for('login'))
    cita = Citas.query.get_or_404(cita_id)
    if cita.clienteId != session['usuarioId'] or cita.estado != 'Completada' or cita.resena:
        flash('No puedes reseñar esta cita.', 'warning')
        return redirect(url_for('dashboard_cliente'))
    if request.method == 'POST':
        nueva_resena = Resenas(
            citaId=cita.id,
            calificacion=request.form.get('calificacion'),
            comentario=request.form.get('comentario')
        )
        db.session.add(nueva_resena)
        db.session.commit()
        flash('¡Gracias por tu reseña!', 'success')
        return redirect(url_for('dashboard_cliente'))
    return render_template('dejar_resena.html', cita=cita)

@app.route('/api/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- FUNCIÓN DE DATOS DE PRUEBA (Actualizada con nuevas contraseñas) ---
def create_test_data():
    print("Verificando si se necesitan datos de prueba...")
    if Usuarios.query.filter(Usuarios.email.like('%@test.com')).count() > 0:
        print("Los datos de prueba ya existen.")
        return

    print("Creando datos de prueba...")
    
    # --- 5 Clientes ---
    clientes = [
        Usuarios(nombre='Camila Rojas', email='camila@test.com', tipoUsuario='cliente'),
        Usuarios(nombre='David Peña', email='david@test.com', tipoUsuario='cliente'),
        Usuarios(nombre='Sofia Luna', email='sofia@test.com', tipoUsuario='cliente'),
        Usuarios(nombre='Mateo Torres', email='mateo@test.com', tipoUsuario='cliente'),
        Usuarios(nombre='Laura Gómez', email='laura@test.com', tipoUsuario='cliente')
    ]
    for c in clientes:
        c.set_password('cliente123') # <-- NUEVA CONTRASEÑA
        db.session.add(c)
    
    # --- 5 Tatuadores ---
    tatuadores_data = [
        {'nombre': 'Esteban Arte', 'email': 'esteban@test.com', 'especialidades': 'Realismo, Blackwork', 'ubicacion': 'Chapinero, Bogotá', 'lat': 4.6300, 'lon': -74.0620},
        {'nombre': 'Ana Ink', 'email': 'ana@test.com', 'especialidades': 'Neotradicional, Acuarela', 'ubicacion': 'Usaquén, Bogotá', 'lat': 4.7000, 'lon': -74.0300},
        {'nombre': 'Carlos Sombra', 'email': 'carlos@test.com', 'especialidades': 'Blackwork, Geométrico', 'ubicacion': 'Teusaquillo, Bogotá', 'lat': 4.6350, 'lon': -74.0780},
        {'nombre': 'Valeria Fineline', 'email': 'valeria@test.com', 'especialidades': 'Fine Line, Minimalista', 'ubicacion': 'La Candelaria, Bogotá', 'lat': 4.5950, 'lon': -74.0750},
        {'nombre': 'Miguel Angel', 'email': 'miguel@test.com', 'especialidades': 'Japonés, Tradicional', 'ubicacion': 'Suba, Bogotá', 'lat': 4.7500, 'lon': -74.0900}
    ]
    
    tatuadores = []
    for data in tatuadores_data:
        t = Usuarios(nombre=data['nombre'], email=data['email'], tipoUsuario='tatuador')
        t.set_password('tatuador123') # <-- NUEVA CONTRASEÑA
        tatuadores.append(t)
        db.session.add(t)
    
    db.session.commit() 

    # --- Perfiles de Tatuadores ---
    for i, t in enumerate(tatuadores):
        data = tatuadores_data[i]
        perfil = TatuadorPerfil(
            usuarioId=t.id,
            especialidades=data['especialidades'],
            descripcion=f'Artista con más de {i+3} años de experiencia. Apasionado por el arte y la tinta. Mi estudio es un espacio seguro y profesional.',
            tarifas=f'${150 + i*50}.000 COP / hora',
            redesSociales=f'@__{t.nombre.split()[0].lower()}_ink',
            ubicacion=data['ubicacion'],
            latitud=data['lat'],
            longitud=data['lon']
        )
        db.session.add(perfil)
        
        p1 = Portafolio(tatuadorId=t.id, titulo=f'Pieza de {data["especialidades"].split(",")[0]}', descripcion='Trabajo realizado en 5 horas.')
        p2 = Portafolio(tatuadorId=t.id, titulo='Diseño de Manga', descripcion='Diseño personalizado para cliente.')
        db.session.add_all([p1, p2])

    db.session.commit()
    
    # --- Citas y Reseñas ---
    cita1 = Citas(clienteId=clientes[0].id, tatuadorId=tatuadores[0].id, fecha='2025-10-01', hora='14:00', descripcion='Tigre realista', estado='Completada')
    db.session.add(cita1)
    db.session.commit()
    resena1 = Resenas(citaId=cita1.id, calificacion=5, comentario='¡Esteban es un artista increíble! El mejor tatuaje que tengo.')
    db.session.add(resena1)
    
    cita2 = Citas(clienteId=clientes[1].id, tatuadorId=tatuadores[0].id, fecha='2025-10-05', hora='10:00', descripcion='Rosa blackwork', estado='Completada')
    db.session.add(cita2)
    db.session.commit()
    resena2 = Resenas(citaId=cita2.id, calificacion=4, comentario='Muy profesional, aunque la espera fue larga.')
    db.session.add(resena2)
    
    cita3 = Citas(clienteId=clientes[2].id, tatuadorId=tatuadores[1].id, fecha='2025-10-10', hora='15:00', descripcion='Acuarela abstracta', estado='Completada')
    db.session.add(cita3)
    db.session.commit()
    resena3 = Resenas(citaId=cita3.id, calificacion=5, comentario='Ana capturó mi idea perfectamente. ¡La amo!')
    db.session.add(resena3)
    
    cita4 = Citas(clienteId=clientes[3].id, tatuadorId=tatuadores[0].id, fecha='2025-11-20', hora='11:00', descripcion='Diseño geométrico', estado='Aprobada')
    db.session.add(cita4)
    
    cita5 = Citas(clienteId=clientes[4].id, tatuadorId=tatuadores[1].id, fecha='2025-11-25', hora='16:00', descripcion='Minimalista', estado='Pendiente')
    db.session.add(cita5)
    
    db.session.commit()
    print("Datos de prueba creados exitosamente.")


# --- INICIO DE LA APP (Lógica de arranque corregida) ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Bloque 1: Crear Admin (si no existe)
        if not Usuarios.query.filter_by(email='admin@soul.tc').first():
            print("Creando usuario admin por defecto...")
            admin_user = Usuarios(
                nombre='Admin',
                email='admin@soul.tc',
                tipoUsuario='admin'
            )
            admin_user.set_password('admin123') # Contraseña de Admin
            db.session.add(admin_user)
            db.session.commit()
            print("Usuario 'admin@soul.tc' creado con contraseña 'admin123'.")
        
        # Bloque 2: Crear Datos de Prueba (se llama siempre, pero tiene un chequeo interno)
        create_test_data() 
            
    app.run(debug=True)