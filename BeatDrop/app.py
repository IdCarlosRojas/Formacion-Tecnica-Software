import os
import random
import uuid # Importado para generar tokens
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename 
from datetime import datetime, date
from functools import wraps
from sqlalchemy import or_, Text

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = 'clave-secreta-de-beatdrop-muy-segura'

db_path = os.path.join(app.instance_path, 'beatdrop.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav', 'zip'} 

try:
    os.makedirs(app.instance_path)
except OSError:
    pass
try:
    os.makedirs(os.path.join(UPLOAD_FOLDER, 'covers'))
    os.makedirs(os.path.join(UPLOAD_FOLDER, 'pfp')) 
    os.makedirs(os.path.join(UPLOAD_FOLDER, 'audio'))
    os.makedirs(os.path.join(UPLOAD_FOLDER, 'cursos'))
except OSError:
    pass

db = SQLAlchemy(app)

def get_float_from_form(form_field, default=0.0):
    value = request.form.get(form_field)
    if value is None or value == '':
        return default
    try:
        return float(value)
    except ValueError:
        return default

def remove_file(filename, subfolder):
    if filename:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error al eliminar archivo {file_path}: {e}")

def replace_file(file_key, object_id, old_filename, subfolder, prefix='file'):
    file = request.files.get(file_key)
    
    if file and file.filename != '' and allowed_file(file.filename):
        if old_filename and not old_filename.startswith('http') and old_filename != 'default.mp3':
            remove_file(old_filename, subfolder)
        
        filename = f"{prefix}_{object_id}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], subfolder, filename))
        return filename
    
    return old_filename

class Usuario(db.Model):
    __tablename__ = 'USUARIO'
    UsuarioId = db.Column(db.Integer, primary_key=True)
    Nombre = db.Column(db.String(100), nullable=False)
    NombreUsuario = db.Column(db.String(50), unique=True, nullable=False)
    Email = db.Column(db.String(100), unique=True, nullable=False)
    Contrasena = db.Column(db.String(255), nullable=False)
    Rol = db.Column(db.String(20), nullable=False, default='productor')
    Bio = db.Column(db.Text, nullable=True)
    foto_perfil_url = db.Column(db.String(255), default='default_pfp.png')
    beats = db.relationship('Beat', backref='artista_ref', lazy='dynamic')
    favoritos = db.relationship('Favorito', backref='usuario_ref', lazy='dynamic')
    compras = db.relationship('Compra', backref='comprador_ref', lazy='dynamic')
    inscripciones = db.relationship('Inscripcion', backref='estudiante_ref', lazy='dynamic')
    
    samples = db.relationship('Sample', backref='artista_ref', lazy='dynamic')
    sample_contratos = db.relationship('SampleContrato', backref='comprador_ref', lazy='dynamic')

    seguidos = db.relationship(
        'Seguidor',
        foreign_keys='Seguidor.seguidor_id',
        backref='seguidor', lazy='dynamic'
    )
    seguidores = db.relationship(
        'Seguidor',
        foreign_keys='Seguidor.seguido_id',
        backref='seguido', lazy='dynamic'
    )
    def set_password(self, password):
        self.Contrasena = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.Contrasena, password)
    def esta_siguiendo(self, usuario):
        return self.seguidos.filter_by(seguido_id=usuario.UsuarioId).count() > 0
    def seguir(self, usuario):
        if not self.esta_siguiendo(usuario):
            s = Seguidor(seguidor_id=self.UsuarioId, seguido_id=usuario.UsuarioId)
            db.session.add(s)
    def dejar_de_seguir(self, usuario):
        s = self.seguidos.filter_by(seguido_id=usuario.UsuarioId).first()
        if s:
            db.session.delete(s)

class Seguidor(db.Model):
    __tablename__ = 'SEGUIDOR'
    id = db.Column(db.Integer, primary_key=True)
    seguidor_id = db.Column(db.Integer, db.ForeignKey('USUARIO.UsuarioId'))
    seguido_id = db.Column(db.Integer, db.ForeignKey('USUARIO.UsuarioId'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Beat(db.Model):
    __tablename__ = 'BEAT'
    BeatId = db.Column(db.Integer, primary_key=True)
    Nombre = db.Column(db.String(100), nullable=False)
    Genero = db.Column(db.String(50), nullable=False)
    Bpm = db.Column(db.Integer)
    FechaSubida = db.Column(db.Date, nullable=False, default=date.today)
    cover_url = db.Column(db.String(255))
    UsuarioId = db.Column(db.Integer, db.ForeignKey('USUARIO.UsuarioId'), nullable=False)
    licencias = db.relationship('Licencia', backref='beat_ref', lazy='dynamic')
    favoritos = db.relationship('Favorito', backref='beat_ref', lazy='dynamic')
    
    monetizado = db.Column(db.Boolean, default=True, nullable=False)
    patente_disponible = db.Column(db.Boolean, default=False, nullable=False)
    copyright_token = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

    audio_preview_url = db.Column(db.String(255), nullable=False) 
    file_mp3_url = db.Column(db.String(255), nullable=True)
    file_wav_url = db.Column(db.String(255), nullable=True)
    file_stems_url = db.Column(db.String(255), nullable=True)
    file_patente_url = db.Column(db.String(255), nullable=True)

    dnda_registro = db.Column(db.String(100), nullable=True)

    @property
    def precio_base(self):
        if not self.monetizado:
            return None
        
        lic_mp3 = self.licencias.filter_by(Tipo='Licencia MP3').first()
        if lic_mp3:
            return lic_mp3.Precio
        
        lic_wav = self.licencias.filter_by(Tipo='Licencia WAV').first()
        if lic_wav:
            return lic_wav.Precio
            
        lic_stems = self.licencias.filter_by(Tipo='Pistas (Stems)').first()
        if lic_stems:
            return lic_stems.Precio

        return 0.00

class Favorito(db.Model):
    __tablename__ = 'FAVORITO'
    FavoritoId = db.Column(db.Integer, primary_key=True)
    FechaFavorito = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    UsuarioId = db.Column(db.Integer, db.ForeignKey('USUARIO.UsuarioId'), nullable=False)
    BeatId = db.Column(db.Integer, db.ForeignKey('BEAT.BeatId'), nullable=False)

class Licencia(db.Model):
    __tablename__ = 'LICENCIA'
    LicenciaId = db.Column(db.Integer, primary_key=True)
    BeatId = db.Column(db.Integer, db.ForeignKey('BEAT.BeatId'), nullable=False)
    Tipo = db.Column(db.String(50), nullable=False) 
    Precio = db.Column(db.DECIMAL(10, 2), nullable=False)
    Descripcion = db.Column(db.String(255))

class Compra(db.Model):
    __tablename__ = 'COMPRA'
    CompraId = db.Column(db.Integer, primary_key=True)
    UsuarioId = db.Column(db.Integer, db.ForeignKey('USUARIO.UsuarioId'), nullable=False)
    LicenciaId = db.Column(db.Integer, db.ForeignKey('LICENCIA.LicenciaId'), nullable=False)
    FechaCompra = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    PrecioPagado = db.Column(db.DECIMAL(10, 2), nullable=False)
    licencia_info = db.relationship('Licencia')

class Curso(db.Model):
    __tablename__ = 'CURSO'
    CursoId = db.Column(db.Integer, primary_key=True)
    Titulo = db.Column(db.String(150), nullable=False)
    Descripcion = db.Column(db.Text, nullable=False)
    Precio = db.Column(db.DECIMAL(10, 2), nullable=False)
    Instructor = db.Column(db.String(100))
    ImagenUrl = db.Column(db.String(255))
    Categoria = db.Column(db.String(50))
    inscripciones = db.relationship('Inscripcion', backref='curso_ref', lazy='dynamic')

class Inscripcion(db.Model):
    __tablename__ = 'INSCRIPCION'
    InscripcionId = db.Column(db.Integer, primary_key=True)
    UsuarioId = db.Column(db.Integer, db.ForeignKey('USUARIO.UsuarioId'), nullable=False)
    CursoId = db.Column(db.Integer, db.ForeignKey('CURSO.CursoId'), nullable=False)
    FechaInscripcion = db.Column(db.DateTime, default=datetime.utcnow)

class Sample(db.Model):
    __tablename__ = 'SAMPLE'
    SampleId = db.Column(db.Integer, primary_key=True)
    Nombre = db.Column(db.String(100), nullable=False)
    FechaSubida = db.Column(db.Date, nullable=False, default=date.today)
    audio_preview_url = db.Column(db.String(255), nullable=False)
    UsuarioId = db.Column(db.Integer, db.ForeignKey('USUARIO.UsuarioId'), nullable=False)
    dnda_registro = db.Column(db.String(100), nullable=True)
    licencias = db.relationship('SampleLicense', backref='sample_ref', lazy='dynamic')
    
    file_sample_url = db.Column(db.String(255), nullable=True) 

class SampleLicense(db.Model):
    __tablename__ = 'SAMPLE_LICENSE'
    SampleLicenseId = db.Column(db.Integer, primary_key=True)
    SampleId = db.Column(db.Integer, db.ForeignKey('SAMPLE.SampleId'), nullable=False)
    Tipo = db.Column(db.String(50), nullable=False) 
    porcentaje_regalias = db.Column(db.Integer, nullable=True, default=0) 
    descripcion = db.Column(db.String(255))

class SampleContrato(db.Model):
    __tablename__ = 'SAMPLE_CONTRATO'
    ContratoId = db.Column(db.Integer, primary_key=True)
    SampleLicenseId = db.Column(db.Integer, db.ForeignKey('SAMPLE_LICENSE.SampleLicenseId'), nullable=False)
    UsuarioId = db.Column(db.Integer, db.ForeignKey('USUARIO.UsuarioId'), nullable=False) 
    FechaContrato = db.Column(db.DateTime, default=datetime.utcnow)
    licencia_info = db.relationship('SampleLicense')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión para ver esta página.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    @login_required 
    def decorated_function(*args, **kwargs):
        if session.get('rol') != 'admin':
            flash('No tienes permiso para acceder a esta página.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.context_processor
def inject_globals():
    cart_items = session.get('cart', [])
    favoritos_ids = set()
    if 'user_id' in session:
        favs = Favorito.query.filter_by(UsuarioId=session['user_id']).all()
        favoritos_ids = {f.BeatId for f in favs}
    
    return dict(cart_count=len(cart_items), favoritos_ids=favoritos_ids)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = Usuario.query.filter_by(Email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.UsuarioId
            session['username'] = user.NombreUsuario
            session['rol'] = user.Rol 
            session['cart'] = [] 
            flash('Inicio de sesión exitoso.', 'success')
            if user.Rol == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        else:
            flash('Correo o contraseña incorrectos.', 'danger')
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if 'user_id' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        
        if 'terminos' not in request.form:
            flash('Debes aceptar los Términos y Condiciones para registrarte.', 'danger')
            return render_template('registro.html')

        nombre = request.form['nombre'] 
        correo = request.form['correo']
        usuario = request.form['usuario']
        if Usuario.query.filter_by(Email=correo).first():
            flash('El correo electrónico ya está registrado.', 'danger')
        elif Usuario.query.filter_by(NombreUsuario=usuario).first():
            flash('El nombre de usuario ya existe.', 'danger')
        else:
            nuevo_usuario = Usuario(
                Nombre=nombre, 
                NombreUsuario=usuario, 
                Email=correo, 
                Rol='productor',
                Bio='¡Hola! Soy nuevo en BeatDrop.'
            )
            nuevo_usuario.set_password(request.form['contraseña'])
            try:
                db.session.add(nuevo_usuario); db.session.commit()
                flash('Cuenta creada con éxito. Ahora puedes iniciar sesión.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback(); flash(f'Error al crear la cuenta: {e}', 'danger')
    return render_template('registro.html')
            
@app.route('/logout')
@login_required
def logout():
    session.clear() 
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user_id' not in session: 
        return render_template('landing.html')
    
    beats = Beat.query.order_by(Beat.FechaSubida.desc()).limit(12).all()
    return render_template('index.html', beats=beats)

@app.route('/perfil/<string:username>')
@login_required
def perfil(username):
    user = Usuario.query.filter_by(NombreUsuario=username).first_or_404()
    mis_beats = user.beats.order_by(Beat.FechaSubida.desc()).all()
    current_user = Usuario.query.get(session['user_id'])
    is_following = current_user.esta_siguiendo(user)
    stats = {
        'beats_publicados': user.beats.count(),
        'seguidores': user.seguidores.count(),
        'siguiendo': user.seguidos.count()
    }
    return render_template('perfil.html', usuario=user, beats=mis_beats, stats=stats, is_following=is_following)

@app.route('/mi_perfil')
@login_required
def mi_perfil():
    return redirect(url_for('perfil', username=session['username']))

@app.route('/perfil/edit', methods=['GET', 'POST'])
@login_required
def edit_perfil():
    user = Usuario.query.get_or_404(session['user_id'])
    if request.method == 'POST':
        new_username = request.form['username']
        new_email = request.form['email']
        if new_username != user.NombreUsuario and Usuario.query.filter_by(NombreUsuario=new_username).first():
            flash('Ese nombre de usuario ya existe.', 'danger')
            return render_template('edit_perfil.html', usuario=user)
        if new_email != user.Email and Usuario.query.filter_by(Email=new_email).first():
            flash('Ese correo electrónico ya está en uso.', 'danger')
            return render_template('edit_perfil.html', usuario=user)
            
        user.Nombre = request.form['nombre']
        user.NombreUsuario = new_username
        user.Email = new_email
        user.Bio = request.form['bio']
        
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = f"pfp_{user.UsuarioId}_{secure_filename(file.filename)}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'pfp', filename)
                file.save(save_path)
                user.foto_perfil_url = filename
        
        try:
            db.session.commit()
            session['username'] = user.NombreUsuario
            flash('Perfil actualizado con éxito.', 'success')
            return redirect(url_for('perfil', username=user.NombreUsuario))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el perfil: {e}', 'danger')
            
    return render_template('edit_perfil.html', usuario=user)

@app.route('/subir', methods=['GET', 'POST'])
@login_required
def subir_beat():
    if request.method == 'POST':
        
        try:
            nombre = request.form['nombre']
            genero = request.form['genero']
            bpm = request.form['bpm']
            
            monetizado = 'monetizado' in request.form
            patente_disponible = 'patente_disponible' in request.form
            
            precio_mp3_val = get_float_from_form('precio_mp3')
            precio_wav_val = get_float_from_form('precio_wav')
            precio_stems_val = get_float_from_form('precio_stems')
            precio_patente_val = get_float_from_form('precio_patente')
            
            dnda_registro = request.form.get('dnda_registro')
            if 'declaracion_autoria' not in request.form:
                flash('Debes declarar que eres el autor de la obra.', 'danger')
                return redirect(request.url)

        except KeyError:
            flash('Faltan campos en el formulario.', 'danger')
            return redirect(request.url)
        
        if 'audio_preview' not in request.files or request.files['audio_preview'].filename == '':
            flash('Debes subir un archivo de audio para la "Preview".', 'danger')
            return redirect(request.url)
        if 'cover' not in request.files or request.files['cover'].filename == '':
            flash('Falta el archivo de portada.', 'danger')
            return redirect(request.url)
            
        cover_file = request.files['cover']
        preview_file = request.files['audio_preview']

        if cover_file and allowed_file(cover_file.filename) and preview_file and allowed_file(preview_file.filename):
            
            try:
                nuevo_beat = Beat(
                    Nombre=nombre,
                    Genero=genero,
                    Bpm=int(bpm),
                    cover_url="temp", 
                    audio_preview_url="temp",
                    UsuarioId=session['user_id'], 
                    monetizado=monetizado,
                    patente_disponible=patente_disponible,
                    dnda_registro=dnda_registro 
                )
                db.session.add(nuevo_beat)
                db.session.commit() 
            except Exception as e:
                db.session.rollback()
                flash(f'Error al crear el beat: {e}', 'danger')
                return redirect(request.url)

            try:
                beat_id = nuevo_beat.BeatId
                
                cover_filename = f"cover_{beat_id}_{secure_filename(cover_file.filename)}"
                preview_filename = f"preview_{beat_id}_{secure_filename(preview_file.filename)}"
                cover_file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'covers', cover_filename))
                preview_file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'audio', preview_filename))
                
                nuevo_beat.cover_url = cover_filename
                nuevo_beat.audio_preview_url = preview_filename
                
                file_mp3 = replace_file('file_mp3', beat_id, None, 'audio', prefix=f"file_mp3_{beat_id}")
                file_wav = replace_file('file_wav', beat_id, None, 'audio', prefix=f"file_wav_{beat_id}")
                file_stems = replace_file('file_stems', beat_id, None, 'audio', prefix=f"file_stems_{beat_id}")
                file_patente = replace_file('file_patente', beat_id, None, 'audio', prefix=f"file_patente_{beat_id}")
                
                nuevo_beat.file_mp3_url = file_mp3
                nuevo_beat.file_wav_url = file_wav
                nuevo_beat.file_stems_url = file_stems
                nuevo_beat.file_patente_url = file_patente

                licencias_a_crear = []
                if monetizado:
                    if precio_mp3_val > 0 and file_mp3:
                        lic_mp3 = Licencia(BeatId=beat_id, Tipo='Licencia MP3', Precio=precio_mp3_val, Descripcion='Entrega de beat en alta calidad MP3.')
                        licencias_a_crear.append(lic_mp3)
                    if precio_wav_val > 0 and file_wav:
                        lic_wav = Licencia(BeatId=beat_id, Tipo='Licencia WAV', Precio=precio_wav_val, Descripcion='Entrega de beat en alta calidad WAV.')
                        licencias_a_crear.append(lic_wav)
                    if precio_stems_val > 0 and file_stems:
                        lic_stems = Licencia(BeatId=beat_id, Tipo='Pistas (Stems)', Precio=precio_stems_val, Descripcion='Entrega de pistas separadas (stems) en WAV.')
                        licencias_a_crear.append(lic_stems)

                if patente_disponible:
                    if precio_patente_val > 0 and file_patente:
                        lic_patente = Licencia(BeatId=beat_id, Tipo='Licencia Exclusiva', Precio=precio_patente_val, Descripcion='Derechos exclusivos de uso. El beat será retirado de la venta.')
                        licencias_a_crear.append(lic_patente)
                
                if licencias_a_crear:
                    db.session.add_all(licencias_a_crear)
                
                db.session.commit()
                
                flash('¡Beat subido con éxito!', 'success')
                return redirect(url_for('perfil', username=session['username']))
                
            except Exception as e:
                db.session.rollback()
                db.session.delete(nuevo_beat)
                db.session.commit()
                flash(f'Error al guardar archivos: {e}', 'danger')
                return redirect(request.url)
        else:
            flash('Archivos no permitidos (portada o preview).', 'danger')
    return render_template('subir_beat.html')

@app.route('/explorar')
@login_required
def explorar():
    productores = Usuario.query.filter(Usuario.UsuarioId != session['user_id'], Usuario.Rol == 'productor').order_by(Usuario.NombreUsuario).all()
    return render_template('explorar.html', productores=productores)

@app.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id):
    user_a_seguir = Usuario.query.get_or_404(user_id)
    current_user = Usuario.query.get(session['user_id'])
    if user_a_seguir == current_user:
        flash('No puedes seguirte a ti mismo.', 'danger')
        return redirect(url_for('perfil', username=user_a_seguir.NombreUsuario))
    current_user.seguir(user_a_seguir)
    db.session.commit()
    flash(f'Ahora sigues a {user_a_seguir.NombreUsuario}.', 'success')
    return redirect(url_for('perfil', username=user_a_seguir.NombreUsuario))

@app.route('/unfollow/<int:user_id>', methods=['POST'])
@login_required
def unfollow(user_id):
    user_a_dejar_de_seguir = Usuario.query.get_or_404(user_id)
    current_user = Usuario.query.get(session['user_id'])
    current_user.dejar_de_seguir(user_a_dejar_de_seguir)
    db.session.commit()
    flash(f'Has dejado de seguir a {user_a_dejar_de_seguir.NombreUsuario}.', 'info')
    return redirect(url_for('perfil', username=user_a_dejar_de_seguir.NombreUsuario))

@app.route('/formaciones')
@login_required
def formaciones():
    cursos = Curso.query.order_by(Curso.Categoria).all()
    inscripciones = Inscripcion.query.filter_by(UsuarioId=session['user_id']).all()
    cursos_comprados_ids = {i.CursoId for i in inscripciones}
    return render_template('formaciones_lista.html', cursos=cursos, cursos_comprados_ids=cursos_comprados_ids)

@app.route('/formacion/<int:curso_id>')
@login_required
def formacion_detail(curso_id):
    curso = Curso.query.get_or_404(curso_id)
    ya_comprado = Inscripcion.query.filter_by(UsuarioId=session['user_id'], CursoId=curso.CursoId).first()
    return render_template('formacion_detail.html', curso=curso, ya_comprado=ya_comprado)

@app.route('/comprar_formacion/<int:curso_id>', methods=['POST'])
@login_required
def comprar_formacion(curso_id):
    curso = Curso.query.get_or_404(curso_id)
    ya_comprado = Inscripcion.query.filter_by(UsuarioId=session['user_id'], CursoId=curso.CursoId).first()
    if ya_comprado:
        flash('Ya tienes acceso a este curso.', 'info')
        return redirect(url_for('formacion_detail', curso_id=curso.CursoId))
    try:
        nueva_inscripcion = Inscripcion(
            UsuarioId=session['user_id'],
            CursoId=curso.CursoId
        )
        db.session.add(nueva_inscripcion)
        db.session.commit()
        flash(f'¡Inscripción a "{curso.Titulo}" exitosa!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar la inscripción: {e}', 'danger')
    return redirect(url_for('formacion_detail', curso_id=curso.CursoId))

@app.route('/guardados')
@login_required
def guardados():
    beats_guardados = db.session.query(Beat).join(Favorito).filter(Favorito.UsuarioId == session['user_id']).all()
    return render_template('Guardados.html', beats=beats_guardados)

@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '') 
    if not query:
        return redirect(url_for('index'))
    
    if query.startswith('@'):
        username_query = query[1:] 
        search_term = f"%{username_query}%"
        results = db.session.query(Beat).join(Usuario).filter(
            Usuario.NombreUsuario.ilike(search_term)
        ).all()
    else:
        search_term = f"%{query}%" 
        results = db.session.query(Beat).join(Usuario).filter(
            or_(
                Beat.Nombre.ilike(search_term),
                Beat.Genero.ilike(search_term),
                Beat.copyright_token == query 
            )
        ).all()
    
    return render_template('search_results.html', results=results, query=query)

@app.route('/beat/<int:beat_id>')
@login_required
def beat_detail(beat_id):
    beat = Beat.query.get_or_404(beat_id)
    licencias = beat.licencias.order_by(Licencia.Precio).all()
    esta_en_carrito = False
    cart = session.get('cart', [])
    for item in cart:
        if item['beat_id'] == beat.BeatId:
            esta_en_carrito = True
            break
    return render_template('beat_detail.html', beat=beat, licencias=licencias, esta_en_carrito=esta_en_carrito)

# --- INICIO DE MODIFICACIÓN (Nueva ruta) ---
@app.route('/beat/<int:beat_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_beat(beat_id):
    beat = Beat.query.get_or_404(beat_id)
    
    # Seguridad: Asegurarse de que el usuario logueado es el dueño del beat
    if beat.UsuarioId != session['user_id']:
        flash('No tienes permiso para editar este beat.', 'danger')
        return redirect(url_for('perfil', username=session['username']))

    if request.method == 'POST':
        try:
            # 1. Actualizar datos simples y booleans
            beat.Nombre = request.form['nombre']
            beat.Genero = request.form['genero']
            beat.Bpm = int(request.form['bpm'])
            # El UsuarioId no se cambia
            beat.monetizado = 'monetizado' in request.form
            beat.patente_disponible = 'patente_disponible' in request.form
            beat.dnda_registro = request.form.get('dnda_registro') 
            
            # 2. Reemplazar archivos (si se subieron nuevos)
            beat.cover_url = replace_file('cover', beat.BeatId, beat.cover_url, 'covers', prefix=f"cover_{beat_id}")
            beat.audio_preview_url = replace_file('audio_preview', beat.BeatId, beat.audio_preview_url, 'audio', prefix=f"preview_{beat_id}")
            beat.file_mp3_url = replace_file('file_mp3', beat.BeatId, beat.file_mp3_url, 'audio', prefix=f"file_mp3_{beat_id}")
            beat.file_wav_url = replace_file('file_wav', beat.BeatId, beat.file_wav_url, 'audio', prefix=f"file_wav_{beat_id}")
            beat.file_stems_url = replace_file('file_stems', beat.BeatId, beat.file_stems_url, 'audio', prefix=f"file_stems_{beat_id}")
            beat.file_patente_url = replace_file('file_patente', beat.BeatId, beat.file_patente_url, 'audio', prefix=f"file_patente_{beat_id}")
            
            # 3. Borrar licencias antiguas
            Licencia.query.filter_by(BeatId=beat_id).delete()
            
            # 4. Crear nuevas licencias basadas en el formulario
            precio_mp3_val = get_float_from_form('precio_mp3')
            precio_wav_val = get_float_from_form('precio_wav')
            precio_stems_val = get_float_from_form('precio_stems')
            precio_patente_val = get_float_from_form('precio_patente')

            licencias_a_crear = []
            if beat.monetizado:
                if precio_mp3_val > 0 and beat.file_mp3_url:
                    lic_mp3 = Licencia(BeatId=beat_id, Tipo='Licencia MP3', Precio=precio_mp3_val, Descripcion='Entrega de beat en alta calidad MP3.')
                    licencias_a_crear.append(lic_mp3)
                if precio_wav_val > 0 and beat.file_wav_url:
                    lic_wav = Licencia(BeatId=beat_id, Tipo='Licencia WAV', Precio=precio_wav_val, Descripcion='Entrega de beat en alta calidad WAV.')
                    licencias_a_crear.append(lic_wav)
                if precio_stems_val > 0 and beat.file_stems_url:
                    lic_stems = Licencia(BeatId=beat_id, Tipo='Pistas (Stems)', Precio=precio_stems_val, Descripcion='Entrega de pistas separadas (stems) en WAV.')
                    licencias_a_crear.append(lic_stems)

            if beat.patente_disponible:
                if precio_patente_val > 0 and beat.file_patente_url:
                    lic_patente = Licencia(BeatId=beat_id, Tipo='Licencia Exclusiva', Precio=precio_patente_val, Descripcion='Derechos exclusivos de uso. El beat será retirado de la venta.')
                    licencias_a_crear.append(lic_patente)
            
            if licencias_a_crear:
                db.session.add_all(licencias_a_crear)

            db.session.commit()
            flash(f'Beat "{beat.Nombre}" actualizado con éxito.', 'success')
            return redirect(url_for('perfil', username=session['username']))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el beat: {e}', 'danger')
            
    # --- Lógica GET ---
    licencias_actuales = {lic.Tipo: lic.Precio for lic in beat.licencias}
    
    return render_template('edit_beat.html', beat=beat, licencias=licencias_actuales)
# --- FIN DE MODIFICACIÓN ---

@app.route('/toggle_favorito/<int:beat_id>', methods=['POST'])
@login_required
def toggle_favorito(beat_id):
    beat = Beat.query.get_or_404(beat_id)
    favorito_existente = Favorito.query.filter_by(
        UsuarioId=session['user_id'], 
        BeatId=beat.BeatId
    ).first()
    try:
        if favorito_existente:
            db.session.delete(favorito_existente)
            flash(f"'{beat.Nombre}' eliminado de Guardados.", 'info')
        else:
            nuevo_favorito = Favorito(UsuarioId=session['user_id'], BeatId=beat.BeatId)
            db.session.add(nuevo_favorito)
            flash(f"'{beat.Nombre}' guardado.", 'success')
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar la solicitud: {e}', 'danger')
    return redirect(request.referrer or url_for('index'))

@app.route('/add_to_cart/<int:beat_id>/<int:licencia_id>', methods=['POST'])
@login_required
def add_to_cart(beat_id, licencia_id):
    beat = Beat.query.get_or_404(beat_id)
    licencia = Licencia.query.get_or_404(licencia_id)
    
    if not beat.monetizado and not licencia.Tipo == 'Licencia Exclusiva':
         flash(f"Este beat no está a la venta.", 'danger')
         return redirect(url_for('beat_detail', beat_id=beat.BeatId))
    
    if not beat.patente_disponible and licencia.Tipo == 'Licencia Exclusiva':
         flash(f"Este beat no ofrece licencia exclusiva.", 'danger')
         return redirect(url_for('beat_detail', beat_id=beat.BeatId))

    cart = session.get('cart', [])
    beat_ya_en_carrito = False
    for item in cart:
        if item['beat_id'] == beat_id:
            beat_ya_en_carrito = True
            item['licencia_id'] = licencia.LicenciaId
            item['licencia_tipo'] = licencia.Tipo
            item['precio'] = float(licencia.Precio)
            flash(f"Licencia de '{beat.Nombre}' actualizada en el carrito.", 'info')
            break
    if not beat_ya_en_carrito:
        cart_item = {
            'beat_id': beat.BeatId,
            'nombre': beat.Nombre,
            'cover': beat.cover_url,
            'artista': beat.artista_ref.NombreUsuario,
            'licencia_id': licencia.LicenciaId,
            'licencia_tipo': licencia.Tipo,
            'precio': float(licencia.Precio)
        }
        cart.append(cart_item)
        flash(f"'{beat.Nombre}' añadido al carrito.", 'success')
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:beat_id>', methods=['POST'])
@login_required
def remove_from_cart(beat_id):
    cart = session.get('cart', [])
    new_cart = [item for item in cart if item['beat_id'] != beat_id]
    if len(new_cart) < len(cart):
        flash("Beat eliminado del carrito.", 'info')
    session['cart'] = new_cart
    return redirect(url_for('cart'))

@app.route('/cart')
@login_required
def cart():
    cart_items = session.get('cart', [])
    total = sum(item['precio'] for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    cart_items = session.get('cart', [])
    if not cart_items:
        flash('Tu carrito está vacío.', 'danger')
        return redirect(url_for('cart'))
        
    try:
        for item in cart_items:
            nueva_compra = Compra(
                UsuarioId=session['user_id'],
                LicenciaId=item['licencia_id'],
                PrecioPagado=item['precio']
            )
            db.session.add(nueva_compra)
            
            if item['licencia_tipo'] == 'Licencia Exclusiva':
                beat = Beat.query.get(item['beat_id'])
                if beat:
                    beat.monetizado = False
                    beat.patente_disponible = False
                    
        session['cart'] = []
        db.session.commit()
        flash('¡Compra simulada con éxito! Tus beats están en "Mis Compras".', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar la compra: {e}', 'danger')
        return redirect(url_for('cart'))
        
    return redirect(url_for('mis_compras'))

@app.route('/mis_compras')
@login_required
def mis_compras():
    # 1. Obtener compras de BEATS
    compras_beats = db.session.query(Beat, Licencia, Compra)\
        .join(Licencia, Compra.LicenciaId == Licencia.LicenciaId)\
        .join(Beat, Licencia.BeatId == Beat.BeatId)\
        .filter(Compra.UsuarioId == session['user_id'])\
        .order_by(Compra.FechaCompra.desc())\
        .all()
    
    # 2. Obtener licencias de SAMPLES
    compras_samples = db.session.query(Sample, SampleLicense, SampleContrato)\
        .join(SampleLicense, SampleContrato.SampleLicenseId == SampleLicense.SampleLicenseId)\
        .join(Sample, SampleLicense.SampleId == Sample.SampleId)\
        .filter(SampleContrato.UsuarioId == session['user_id'])\
        .order_by(SampleContrato.FechaContrato.desc())\
        .all()
        
    return render_template('mis_compras.html', compras_beats=compras_beats, compras_samples=compras_samples)

@app.route('/terminos')
def terminos():
    return render_template('terminos.html')

@app.route('/dnda-info')
@login_required
def dnda_info():
    return render_template('dnda_info.html')

@app.route('/mis_ventas')
@login_required
def mis_ventas():
    # 1. Obtener ventas de BEATS
    ventas_beats = db.session.query(Compra, Licencia, Beat, Usuario)\
        .join(Licencia, Compra.LicenciaId == Licencia.LicenciaId)\
        .join(Beat, Licencia.BeatId == Beat.BeatId)\
        .join(Usuario, Compra.UsuarioId == Usuario.UsuarioId)\
        .filter(Beat.UsuarioId == session['user_id'])\
        .order_by(Compra.FechaCompra.desc())\
        .all()
        
    # 2. Obtener licencias de SAMPLES
    ventas_samples = db.session.query(SampleContrato, SampleLicense, Sample, Usuario)\
        .join(SampleLicense, SampleContrato.SampleLicenseId == SampleLicense.SampleLicenseId)\
        .join(Sample, SampleLicense.SampleId == Sample.SampleId)\
        .join(Usuario, SampleContrato.UsuarioId == Usuario.UsuarioId)\
        .filter(Sample.UsuarioId == session['user_id'])\
        .order_by(SampleContrato.FechaContrato.desc())\
        .all()

    return render_template('mis_ventas.html', ventas_beats=ventas_beats, ventas_samples=ventas_samples)

@app.route('/explorar_samples')
@login_required
def explorar_samples():
    samples = Sample.query.order_by(Sample.FechaSubida.desc()).all()
    return render_template('explorar_samples.html', samples=samples)

@app.route('/subir_sample', methods=['GET', 'POST'])
@login_required
def subir_sample():
    if request.method == 'POST':
        try:
            nombre = request.form['nombre']
            tipo_licencia = request.form['tipo_licencia']
            porcentaje = 0
            
            if tipo_licencia == 'Regalías':
                porcentaje_str = request.form.get('porcentaje_regalias', '0')
                if porcentaje_str.isdigit():
                    porcentaje = int(porcentaje_str)
                if not (0 < porcentaje <= 100):
                    flash('El porcentaje de regalías debe estar entre 1 y 100.', 'danger')
                    return redirect(request.url)
            
            dnda_registro = request.form.get('dnda_registro')
            if 'declaracion_autoria' not in request.form:
                flash('Debes declarar que eres el autor del sample.', 'danger')
                return redirect(request.url)

            if 'audio_preview' not in request.files or request.files['audio_preview'].filename == '':
                flash('Debes subir un archivo de audio para el sample (Preview).', 'danger')
                return redirect(request.url)
            
            audio_file = request.files['audio_preview']
            download_file = request.files.get('file_sample')

            if audio_file and allowed_file(audio_file.filename):
                
                nuevo_sample = Sample(
                    Nombre=nombre,
                    audio_preview_url="temp",
                    UsuarioId=session['user_id'],
                    dnda_registro=dnda_registro
                )
                db.session.add(nuevo_sample)
                db.session.commit()

                sample_id = nuevo_sample.SampleId
                
                audio_filename = f"sample_preview_{sample_id}_{secure_filename(audio_file.filename)}"
                audio_file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'audio', audio_filename))
                nuevo_sample.audio_preview_url = audio_filename
                
                if download_file and download_file.filename != '' and allowed_file(download_file.filename):
                    download_filename = f"sample_file_{sample_id}_{secure_filename(download_file.filename)}"
                    download_file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'audio', download_filename))
                    nuevo_sample.file_sample_url = download_filename
                
                desc = "Uso gratuito con atribución." if tipo_licencia == 'Gratuita' else f"Split de regalías del {porcentaje}% para el productor."
                
                nueva_licencia = SampleLicense(
                    SampleId=sample_id,
                    Tipo=tipo_licencia,
                    porcentaje_regalias=porcentaje,
                    descripcion=desc
                )
                db.session.add(nueva_licencia)
                db.session.commit()
                
                flash('¡Sample subido con éxito!', 'success')
                return redirect(url_for('explorar_samples'))

            else:
                flash('Archivo de audio (preview) no permitido.', 'danger')

        except Exception as e:
            db.session.rollback()
            flash(f'Error al subir el sample: {e}', 'danger')
            return redirect(request.url)
            
    return render_template('subir_sample.html')

@app.route('/sample/<int:sample_id>')
@login_required
def sample_detail(sample_id):
    sample = Sample.query.get_or_404(sample_id)
    licencias = sample.licencias.all()
    contrato_usuario = None
    
    if licencias:
        licencia_ids = [lic.SampleLicenseId for lic in licencias]
        contrato_usuario = SampleContrato.query.filter(
            SampleContrato.SampleLicenseId.in_(licencia_ids),
            SampleContrato.UsuarioId == session['user_id']
        ).first()
            
    return render_template('sample_detail.html', sample=sample, licencias=licencias, contrato_usuario=contrato_usuario)

@app.route('/sample/usar/<int:license_id>', methods=['POST'])
@login_required
def usar_sample(license_id):
    licencia = SampleLicense.query.get_or_404(license_id)
    
    contrato_existente = SampleContrato.query.filter_by(
        SampleLicenseId=license_id,
        UsuarioId=session['user_id']
    ).first()
    
    if contrato_existente:
        flash('Ya has generado un contrato para este sample.', 'info')
        return redirect(url_for('sample_detail', sample_id=licencia.SampleId))

    try:
        nuevo_contrato = SampleContrato(
            SampleLicenseId=license_id,
            UsuarioId=session['user_id']
        )
        db.session.add(nuevo_contrato)
        db.session.commit()
        flash('¡Contrato generado! El sample está disponible en "Mis Compras".', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al generar el contrato: {e}', 'danger')
        
    return redirect(url_for('sample_detail', sample_id=licencia.SampleId))

@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/admin/users')
@admin_required
def admin_users():
    users = Usuario.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/new', methods=['GET', 'POST'])
@admin_required
def admin_new_user():
    if request.method == 'POST':
        nombre = request.form['nombre'] 
        correo = request.form['correo']
        usuario = request.form['usuario']
        rol = request.form['rol']
        bio = request.form['bio']
        
        if Usuario.query.filter_by(Email=correo).first():
            flash('El correo electrónico ya está registrado.', 'danger')
        elif Usuario.query.filter_by(NombreUsuario=usuario).first():
            flash('El nombre de usuario ya existe.', 'danger')
        else:
            nuevo_usuario = Usuario(
                Nombre=nombre, 
                NombreUsuario=usuario, 
                Email=correo, 
                Rol=rol,
                Bio=bio
            )
            nuevo_usuario.set_password(request.form['contraseña'])
            try:
                db.session.add(nuevo_usuario); db.session.commit()
                flash(f'Usuario {usuario} creado con éxito.', 'success')
                return redirect(url_for('admin_users'))
            except Exception as e:
                db.session.rollback(); flash(f'Error al crear la cuenta: {e}', 'danger')
                
    return render_template('admin_new_user.html')

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    user = Usuario.query.get_or_404(user_id)
    
    if request.method == 'POST':
        
        new_username = request.form['username']
        new_email = request.form['email']
        
        if new_username != user.NombreUsuario and Usuario.query.filter_by(NombreUsuario=new_username).first():
            flash('Ese nombre de usuario ya existe.', 'danger')
            return render_template('admin_edit_user.html', user=user)
        
        if new_email != user.Email and Usuario.query.filter_by(Email=new_email).first():
            flash('Ese correo electrónico ya está en uso.', 'danger')
            return render_template('admin_edit_user.html', user=user)
        
        
        user.Nombre = request.form['nombre']
        user.NombreUsuario = new_username
        user.Email = new_email
        user.Rol = request.form['rol']
        user.Bio = request.form['bio']
        
        try:
            db.session.commit()
            flash(f'Usuario {user.NombreUsuario} actualizado con éxito.', 'success')
            return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el usuario: {e}', 'danger')
            
    return render_template('admin_edit_user.html', user=user)


@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = Usuario.query.get_or_404(user_id)
    if user.Rol == 'admin':
        flash('No puedes eliminar a otro administrador.', 'danger')
        return redirect(url_for('admin_users'))
    
    try:
        
        if user.beats.count() > 0 or user.samples.count() > 0:
             flash(f'Error: No se puede eliminar {user.NombreUsuario} porque tiene beats o samples asociados. Bórralos primero.', 'danger')
             return redirect(url_for('admin_users'))

        
        Favorito.query.filter_by(UsuarioId=user_id).delete()
        Compra.query.filter_by(UsuarioId=user_id).delete()
        Inscripcion.query.filter_by(UsuarioId=user_id).delete()
        Seguidor.query.filter_by(seguidor_id=user_id).delete()
        Seguidor.query.filter_by(seguido_id=user_id).delete()
        SampleContrato.query.filter_by(UsuarioId=user_id).delete()
        
        db.session.delete(user)
        db.session.commit()
        flash(f'Usuario {user.NombreUsuario} eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar usuario: {e}', 'danger')
        
    return redirect(url_for('admin_users'))

@app.route('/admin/beats')
@admin_required
def admin_beats():
    beats = Beat.query.order_by(Beat.FechaSubida.desc()).all()
    return render_template('admin_beats.html', beats=beats)

@app.route('/admin/beats/new', methods=['GET', 'POST'])
@admin_required
def admin_new_beat():
    if request.method == 'POST':
        try:
            nombre = request.form['nombre']
            genero = request.form['genero']
            bpm = request.form['bpm']
            productor_id = request.form['productor_id'] 
            
            monetizado = 'monetizado' in request.form
            patente_disponible = 'patente_disponible' in request.form
            
            precio_mp3_val = get_float_from_form('precio_mp3')
            precio_wav_val = get_float_from_form('precio_wav')
            precio_stems_val = get_float_from_form('precio_stems')
            precio_patente_val = get_float_from_form('precio_patente')
            
            dnda_registro = request.form.get('dnda_registro') 
        
        except KeyError:
            flash('Faltan campos en el formulario.', 'danger')
            return redirect(request.url)
        
        if 'audio_preview' not in request.files or request.files['audio_preview'].filename == '':
            flash('Debes subir un archivo de audio para la "Preview".', 'danger')
            return redirect(request.url)
        if 'cover' not in request.files or request.files['cover'].filename == '':
            flash('Falta el archivo de portada.', 'danger')
            return redirect(request.url)
            
        cover_file = request.files['cover']
        preview_file = request.files['audio_preview']

        if cover_file and allowed_file(cover_file.filename) and preview_file and allowed_file(preview_file.filename):
            
            try:
                nuevo_beat = Beat(
                    Nombre=nombre,
                    Genero=genero,
                    Bpm=int(bpm),
                    cover_url="temp", 
                    audio_preview_url="temp",
                    UsuarioId=productor_id, 
                    monetizado=monetizado,
                    patente_disponible=patente_disponible,
                    dnda_registro=dnda_registro 
                )
                db.session.add(nuevo_beat)
                db.session.commit() 
            except Exception as e:
                db.session.rollback()
                flash(f'Error al crear el beat: {e}', 'danger')
                return redirect(request.url)

            try:
                beat_id = nuevo_beat.BeatId
                
                cover_filename = f"cover_{beat_id}_{secure_filename(cover_file.filename)}"
                preview_filename = f"preview_{beat_id}_{secure_filename(preview_file.filename)}"
                cover_file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'covers', cover_filename))
                preview_file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'audio', preview_filename))
                
                nuevo_beat.cover_url = cover_filename
                nuevo_beat.audio_preview_url = preview_filename
                
                file_mp3 = replace_file('file_mp3', beat_id, None, 'audio', prefix=f"file_mp3_{beat_id}")
                file_wav = replace_file('file_wav', beat_id, None, 'audio', prefix=f"file_wav_{beat_id}")
                file_stems = replace_file('file_stems', beat_id, None, 'audio', prefix=f"file_stems_{beat_id}")
                file_patente = replace_file('file_patente', beat_id, None, 'audio', prefix=f"file_patente_{beat_id}")
                
                nuevo_beat.file_mp3_url = file_mp3
                nuevo_beat.file_wav_url = file_wav
                nuevo_beat.file_stems_url = file_stems
                nuevo_beat.file_patente_url = file_patente

                licencias_a_crear = []
                if monetizado:
                    if precio_mp3_val > 0 and file_mp3:
                        lic_mp3 = Licencia(BeatId=beat_id, Tipo='Licencia MP3', Precio=precio_mp3_val, Descripcion='Entrega de beat en alta calidad MP3.')
                        licencias_a_crear.append(lic_mp3)
                    if precio_wav_val > 0 and file_wav:
                        lic_wav = Licencia(BeatId=beat_id, Tipo='Licencia WAV', Precio=precio_wav_val, Descripcion='Entrega de beat en alta calidad WAV.')
                        licencias_a_crear.append(lic_wav)
                    if precio_stems_val > 0 and file_stems:
                        lic_stems = Licencia(BeatId=beat_id, Tipo='Pistas (Stems)', Precio=precio_stems_val, Descripcion='Entrega de pistas separadas (stems) en WAV.')
                        licencias_a_crear.append(lic_stems)

                if patente_disponible:
                    if precio_patente_val > 0 and file_patente:
                        lic_patente = Licencia(BeatId=beat_id, Tipo='Licencia Exclusiva', Precio=precio_patente_val, Descripcion='Derechos exclusivos de uso. El beat será retirado de la venta.')
                        licencias_a_crear.append(lic_patente)
                
                if licencias_a_crear:
                    db.session.add_all(licencias_a_crear)
                
                db.session.commit()
                
                flash('¡Beat subido con éxito por Admin!', 'success')
                return redirect(url_for('admin_beats'))
                
            except Exception as e:
                db.session.rollback()
                db.session.delete(nuevo_beat)
                db.session.commit()
                flash(f'Error al guardar archivos: {e}', 'danger')
                return redirect(request.url)
        else:
            flash('Archivos no permitidos (portada o preview).', 'danger')
            
    productores = Usuario.query.filter_by(Rol='productor').all()
    return render_template('admin_new_beat.html', productores=productores)

@app.route('/admin/beats/edit/<int:beat_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_beat(beat_id):
    beat = Beat.query.get_or_404(beat_id)
    
    if request.method == 'POST':
        try:
            beat.Nombre = request.form['nombre']
            beat.Genero = request.form['genero']
            beat.Bpm = int(request.form['bpm'])
            beat.UsuarioId = request.form['productor_id']
            beat.monetizado = 'monetizado' in request.form
            beat.patente_disponible = 'patente_disponible' in request.form
            beat.dnda_registro = request.form.get('dnda_registro') 
            
            beat.cover_url = replace_file('cover', beat.BeatId, beat.cover_url, 'covers', prefix=f"cover_{beat_id}")
            beat.audio_preview_url = replace_file('audio_preview', beat.BeatId, beat.audio_preview_url, 'audio', prefix=f"preview_{beat_id}")
            beat.file_mp3_url = replace_file('file_mp3', beat.BeatId, beat.file_mp3_url, 'audio', prefix=f"file_mp3_{beat_id}")
            beat.file_wav_url = replace_file('file_wav', beat.BeatId, beat.file_wav_url, 'audio', prefix=f"file_wav_{beat_id}")
            beat.file_stems_url = replace_file('file_stems', beat.BeatId, beat.file_stems_url, 'audio', prefix=f"file_stems_{beat_id}")
            beat.file_patente_url = replace_file('file_patente', beat.BeatId, beat.file_patente_url, 'audio', prefix=f"file_patente_{beat_id}")
            
            Licencia.query.filter_by(BeatId=beat_id).delete()
            
            precio_mp3_val = get_float_from_form('precio_mp3')
            precio_wav_val = get_float_from_form('precio_wav')
            precio_stems_val = get_float_from_form('precio_stems')
            precio_patente_val = get_float_from_form('precio_patente')

            licencias_a_crear = []
            if beat.monetizado:
                if precio_mp3_val > 0 and beat.file_mp3_url:
                    lic_mp3 = Licencia(BeatId=beat_id, Tipo='Licencia MP3', Precio=precio_mp3_val, Descripcion='Entrega de beat en alta calidad MP3.')
                    licencias_a_crear.append(lic_mp3)
                if precio_wav_val > 0 and beat.file_wav_url:
                    lic_wav = Licencia(BeatId=beat_id, Tipo='Licencia WAV', Precio=precio_wav_val, Descripcion='Entrega de beat en alta calidad WAV.')
                    licencias_a_crear.append(lic_wav)
                if precio_stems_val > 0 and beat.file_stems_url:
                    lic_stems = Licencia(BeatId=beat_id, Tipo='Pistas (Stems)', Precio=precio_stems_val, Descripcion='Entrega de pistas separadas (stems) en WAV.')
                    licencias_a_crear.append(lic_stems)

            if beat.patente_disponible:
                if precio_patente_val > 0 and beat.file_patente_url:
                    lic_patente = Licencia(BeatId=beat_id, Tipo='Licencia Exclusiva', Precio=precio_patente_val, Descripcion='Derechos exclusivos de uso. El beat será retirado de la venta.')
                    licencias_a_crear.append(lic_patente)
            
            if licencias_a_crear:
                db.session.add_all(licencias_a_crear)

            db.session.commit()
            flash(f'Beat "{beat.Nombre}" actualizado con éxito.', 'success')
            return redirect(url_for('admin_beats'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el beat: {e}', 'danger')
            
    productores = Usuario.query.filter_by(Rol='productor').all()
    licencias_actuales = {lic.Tipo: lic.Precio for lic in beat.licencias}
    
    return render_template('admin_edit_beat.html', beat=beat, productores=productores, licencias=licencias_actuales)

@app.route('/admin/beats/delete/<int:beat_id>', methods=['POST'])
@admin_required
def admin_delete_beat(beat_id):
    beat = Beat.query.get_or_404(beat_id)
    
    try:
        if beat.cover_url and not beat.cover_url.startswith('http'):
            remove_file(beat.cover_url, 'covers')
        
        remove_file(beat.audio_preview_url, 'audio')
        remove_file(beat.file_mp3_url, 'audio')
        remove_file(beat.file_wav_url, 'audio')
        remove_file(beat.file_stems_url, 'audio')
        remove_file(beat.file_patente_url, 'audio')

        licencias = Licencia.query.filter_by(BeatId=beat_id).all()
        if licencias:
            licencia_ids = [lic.LicenciaId for lic in licencias]
            Compra.query.filter(Compra.LicenciaId.in_(licencia_ids)).delete(synchronize_session=False)
            Licencia.query.filter_by(BeatId=beat_id).delete()
        
        Favorito.query.filter_by(BeatId=beat_id).delete()
        
        db.session.delete(beat)
        db.session.commit()
        flash(f'Beat "{beat.Nombre}" y todos sus datos asociados han sido eliminados.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el beat: {e}', 'danger')
        
    return redirect(url_for('admin_beats'))

@app.route('/admin/samples')
@admin_required
def admin_samples():
    samples = Sample.query.order_by(Sample.FechaSubida.desc()).all()
    return render_template('admin_samples.html', samples=samples)

@app.route('/admin/samples/new', methods=['GET', 'POST'])
@admin_required
def admin_new_sample():
    if request.method == 'POST':
        try:
            nombre = request.form['nombre']
            productor_id = request.form['productor_id']
            tipo_licencia = request.form['tipo_licencia']
            porcentaje = 0
            
            if tipo_licencia == 'Regalías':
                porcentaje_str = request.form.get('porcentaje_regalias', '0')
                if porcentaje_str.isdigit():
                    porcentaje = int(porcentaje_str)
                if not (0 < porcentaje <= 100):
                    flash('El porcentaje de regalías debe estar entre 1 y 100.', 'danger')
                    return redirect(request.url)
            
            dnda_registro = request.form.get('dnda_registro')

            if 'audio_preview' not in request.files or request.files['audio_preview'].filename == '':
                flash('Debes subir un archivo de audio para el sample (Preview).', 'danger')
                return redirect(request.url)
            
            audio_file = request.files['audio_preview']
            download_file = request.files.get('file_sample')

            if audio_file and allowed_file(audio_file.filename):
                
                nuevo_sample = Sample(
                    Nombre=nombre,
                    audio_preview_url="temp",
                    UsuarioId=productor_id,
                    dnda_registro=dnda_registro
                )
                db.session.add(nuevo_sample)
                db.session.commit()

                sample_id = nuevo_sample.SampleId
                
                audio_filename = f"sample_preview_{sample_id}_{secure_filename(audio_file.filename)}"
                audio_file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'audio', audio_filename))
                nuevo_sample.audio_preview_url = audio_filename
                
                if download_file and download_file.filename != '' and allowed_file(download_file.filename):
                    download_filename = f"sample_file_{sample_id}_{secure_filename(download_file.filename)}"
                    download_file.save(os.path.join(app.config['UPLOAD_FOLDER'], 'audio', download_filename))
                    nuevo_sample.file_sample_url = download_filename
                
                desc = "Uso gratuito con atribución." if tipo_licencia == 'Gratuita' else f"Split de regalías del {porcentaje}% para el productor."
                
                nueva_licencia = SampleLicense(
                    SampleId=sample_id,
                    Tipo=tipo_licencia,
                    porcentaje_regalias=porcentaje,
                    descripcion=desc
                )
                db.session.add(nueva_licencia)
                db.session.commit()
                
                flash('¡Sample subido por Admin con éxito!', 'success')
                return redirect(url_for('admin_samples'))

            else:
                flash('Archivo de audio (preview) no permitido.', 'danger')

        except Exception as e:
            db.session.rollback()
            flash(f'Error al subir el sample: {e}', 'danger')
            return redirect(request.url)
            
    productores = Usuario.query.filter_by(Rol='productor').all()
    return render_template('admin_new_sample.html', productores=productores)

@app.route('/admin/samples/edit/<int:sample_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_sample(sample_id):
    sample = Sample.query.get_or_404(sample_id)
    licencia = sample.licencias.first() 
    
    if request.method == 'POST':
        try:
            sample.Nombre = request.form['nombre']
            sample.UsuarioId = request.form['productor_id']
            sample.dnda_registro = request.form.get('dnda_registro')
            
            tipo_licencia = request.form['tipo_licencia']
            porcentaje = 0
            if tipo_licencia == 'Regalías':
                porcentaje_str = request.form.get('porcentaje_regalias', '0')
                if porcentaje_str.isdigit():
                    porcentaje = int(porcentaje_str)
                if not (0 < porcentaje <= 100):
                    flash('El porcentaje de regalías debe estar entre 1 y 100.', 'danger')
                    return redirect(request.url)
            
            sample.audio_preview_url = replace_file('audio_preview', sample.SampleId, sample.audio_preview_url, 'audio', prefix=f"sample_preview_{sample.SampleId}")
            sample.file_sample_url = replace_file('file_sample', sample.SampleId, sample.file_sample_url, 'audio', prefix=f"sample_file_{sample.SampleId}")

            if licencia:
                licencia.Tipo = tipo_licencia
                licencia.porcentaje_regalias = porcentaje
                licencia.descripcion = "Uso gratuito con atribución." if tipo_licencia == 'Gratuita' else f"Split de regalías del {porcentaje}% para el productor."
            else:
                desc = "Uso gratuito con atribución." if tipo_licencia == 'Gratuita' else f"Split de regalías del {porcentaje}% para el productor."
                nueva_licencia = SampleLicense(
                    SampleId=sample_id,
                    Tipo=tipo_licencia,
                    porcentaje_regalias=porcentaje,
                    descripcion=desc
                )
                db.session.add(nueva_licencia)
            
            db.session.commit()
            flash(f'Sample "{sample.Nombre}" actualizado con éxito.', 'success')
            return redirect(url_for('admin_samples'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el sample: {e}', 'danger')
            
    productores = Usuario.query.filter_by(Rol='productor').all()
    return render_template('admin_edit_sample.html', sample=sample, licencia=licencia, productores=productores)

@app.route('/admin/samples/delete/<int:sample_id>', methods=['POST'])
@admin_required
def admin_delete_sample(sample_id):
    sample = Sample.query.get_or_404(sample_id)
    
    try:
        remove_file(sample.audio_preview_url, 'audio')
        remove_file(sample.file_sample_url, 'audio')

        licencias = SampleLicense.query.filter_by(SampleId=sample_id).all()
        if licencias:
            licencia_ids = [lic.SampleLicenseId for lic in licencias]
            SampleContrato.query.filter(SampleContrato.SampleLicenseId.in_(licencia_ids)).delete(synchronize_session=False)
            SampleLicense.query.filter_by(SampleId=sample_id).delete()
        
        db.session.delete(sample)
        db.session.commit()
        flash(f'Sample "{sample.Nombre}" y todos sus datos asociados han sido eliminados.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el sample: {e}', 'danger')
        
    return redirect(url_for('admin_samples'))

@app.route('/admin/cursos')
@admin_required
def admin_cursos():
    cursos = Curso.query.order_by(Curso.Titulo).all()
    return render_template('admin_cursos.html', cursos=cursos)

@app.route('/admin/cursos/new', methods=['GET', 'POST'])
@admin_required
def admin_new_curso():
    if request.method == 'POST':
        try:
            titulo = request.form['titulo']
            descripcion = request.form['descripcion']
            precio = float(request.form['precio'])
            instructor = request.form['instructor']
            categoria = request.form['categoria']
            
            if 'imagen' not in request.files or request.files['imagen'].filename == '':
                flash('Debes subir un archivo de imagen.', 'danger')
                return redirect(request.url)

            file = request.files['imagen']
            
            if file and allowed_file(file.filename):
                filename = f"curso_{secure_filename(titulo)}_{secure_filename(file.filename)}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'cursos', filename)
                file.save(save_path)
                
                db_path = f"uploads/cursos/{filename}"
                
                nuevo_curso = Curso(
                    Titulo=titulo,
                    Descripcion=descripcion,
                    Precio=precio,
                    Instructor=instructor,
                    Categoria=categoria,
                    ImagenUrl=db_path
                )
                db.session.add(nuevo_curso)
                db.session.commit()
                flash(f'Curso "{titulo}" creado con éxito.', 'success')
                return redirect(url_for('admin_cursos'))
            else:
                flash('Archivo de imagen no permitido.', 'danger')

        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el curso: {e}', 'danger')
            
    return render_template('admin_new_curso.html')

@app.route('/admin/cursos/edit/<int:curso_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_curso(curso_id):
    curso = Curso.query.get_or_404(curso_id)
    
    if request.method == 'POST':
        try:
            curso.Titulo = request.form['titulo']
            curso.Descripcion = request.form['descripcion']
            curso.Precio = float(request.form['precio'])
            curso.Instructor = request.form['instructor']
            curso.Categoria = request.form['categoria']
            
            if 'imagen' in request.files and request.files['imagen'].filename != '':
                file = request.files['imagen']
                if allowed_file(file.filename):
                    if curso.ImagenUrl:
                        old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], '..', curso.ImagenUrl)
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                            
                    filename = f"curso_{secure_filename(curso.Titulo)}_{secure_filename(file.filename)}"
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'cursos', filename)
                    file.save(save_path)
                    curso.ImagenUrl = f"uploads/cursos/{filename}"
            
            db.session.commit()
            flash(f'Curso "{curso.Titulo}" actualizado con éxito.', 'success')
            return redirect(url_for('admin_cursos'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el curso: {e}', 'danger')
            
    return render_template('admin_edit_curso.html', curso=curso)

@app.route('/admin/cursos/delete/<int:curso_id>', methods=['POST'])
@admin_required
def admin_delete_curso(curso_id):
    curso = Curso.query.get_or_404(curso_id)
    
    try:
        Inscripcion.query.filter_by(CursoId=curso_id).delete()
        
        if curso.ImagenUrl:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], '..', curso.ImagenUrl)
            if os.path.exists(image_path):
                os.remove(image_path)
                
        db.session.delete(curso)
        db.session.commit()
        flash(f'Curso "{curso.Titulo}" y sus datos asociados han sido eliminados.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el curso: {e}', 'danger')
        
    return redirect(url_for('admin_cursos'))


GENRE_IMAGES = {
    "Trap": "https://images.unsplash.com/photo-1593113646773-463f18f8f26c?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
    "Lo-fi": "https://images.unsplash.com/photo-1541701494587-cb58502866ab?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
    "Rap": "https://images.unsplash.com/photo-1506157786151-b8491531f063?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
    "Drill": "https://images.unsplash.com/photo-1516962322319-f3a7436b70c1?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
    "Boom Bap": "https://images.unsplash.com/photo-1588075592465-3d5f134e7b8c?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
    "R&B": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
    "Chillhop": "https://images.unsplash.com/photo-1509343256512-d77a5cb3791b?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80",
    "Reggaeton": "https://images.unsplash.com/photo-1581454045585-1d63c9c69c6f?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&q=80"
}
def inicializar_base_de_datos():
    with app.app_context():
        db.create_all()
        if Usuario.query.count() == 0:
            admin_user = Usuario(Nombre='Admin User', NombreUsuario='admin', Email='admin@beatdrop.com', Rol='admin', Bio='El administrador de BeatDrop.')
            admin_user.set_password('admin123')
            julian_user = Usuario(Nombre='Julián Moreno', NombreUsuario='julianmoreno', Email='julian@beatdrop.com', Rol='productor', Bio='Productor de beats de Trap y Lo-fi.')
            julian_user.set_password('12345')
            natalia_user = Usuario(Nombre='Natalia Rojas', NombreUsuario='nataliarojas', Email='natalia@beatdrop.com', Rol='productor', Bio='Productora de R&B y Soul.')
            natalia_user.set_password('12345')
            alejandro_user = Usuario(Nombre='Alejandro Jaramillo', NombreUsuario='ajaramillo', Email='alejandro@beatdrop.com', Rol='productor', Bio='Especialista en ritmos latinos y Reggaeton.')
            alejandro_user.set_password('12345')
            db.session.add_all([admin_user, julian_user, natalia_user, alejandro_user])
            db.session.commit()
            admin_user.seguir(julian_user)
            julian_user.seguir(admin_user)
            natalia_user.seguir(julian_user)
            alejandro_user.seguir(admin_user)
            db.session.commit()
        if Beat.query.count() < 10: 
            print("Poblando la base de datos con beats...")
            nombres_1 = ["Vibras", "Eco", "Ritmo", "Sonido", "Pulso", "Noche", "Calle", "Aura", "Sueño", "Luz"]
            nombres_2 = ["Urbano", "Nocturno", "Digital", "Perdido", "Eterno", "Dorado", "Fresco", "Místico", "Solar", "Lunar"]
            generos = list(GENRE_IMAGES.keys())
            productores = [Usuario.query.get(2), Usuario.query.get(3), Usuario.query.get(4)] 
            all_new_beats = []
            for i in range(50):
                genero_elegido = random.choice(generos)
                precio_base = round(random.uniform(19.99, 49.99), 2)
                
                es_monetizado = random.choice([True, True, False])
                es_patente = random.choice([True, False])
                
                nuevo_beat = Beat(
                    Nombre=f"{random.choice(nombres_1)} {random.choice(nombres_2)}",
                    Genero=genero_elegido,
                    Bpm=random.randint(80, 160),
                    cover_url=GENRE_IMAGES[genero_elegido],
                    UsuarioId=random.choice(productores).UsuarioId,
                    monetizado=es_monetizado,
                    patente_disponible=es_patente,
                    audio_preview_url="default.mp3", 
                    file_mp3_url="default.mp3" if es_monetizado else None, 
                    file_wav_url="default.mp3" if es_monetizado else None,
                    file_stems_url="default.mp3" if es_monetizado else None,
                    file_patente_url="default.mp3" if es_patente else None,
                    dnda_registro=f"10-{random.randint(100, 999)}-{random.randint(100, 999)}" if random.choice([True, False]) else None
                )
                db.session.add(nuevo_beat)
                db.session.flush()
                
                licencias_a_crear = []
                if es_monetizado:
                    lic_mp3 = Licencia(BeatId=nuevo_beat.BeatId, Tipo='Licencia MP3', Precio=precio_base, Descripcion='Entrega de beat en alta calidad MP3.')
                    lic_wav = Licencia(BeatId=nuevo_beat.BeatId, Tipo='Licencia WAV', Precio=round(precio_base * 1.5, 2), Descripcion='Entrega de beat en alta calidad WAV.')
                    lic_stems = Licencia(BeatId=nuevo_beat.BeatId, Tipo='Pistas (Stems)', Precio=round(precio_base * 3, 2), Descripcion='Entrega de pistas separadas (stems) en WAV.')
                    licencias_a_crear.extend([lic_mp3, lic_wav, lic_stems])
                
                if es_patente:
                    lic_patente = Licencia(BeatId=nuevo_beat.BeatId, Tipo='Licencia Exclusiva', Precio=round(precio_base * 10), Descripcion='Derechos exclusivos de uso. El beat será retirado de la venta.')
                    licencias_a_crear.append(lic_patente)
                
                if licencias_a_crear:
                    db.session.add_all(licencias_a_crear)
            db.session.commit()
        if Curso.query.count() == 0:
            print("Poblando la base de datos con cursos...")
            cursos_data = [
                ('Introducción a FL Studio', 'Aprende desde cero a usar FL Studio.', 29.99, 'admin', 'uploads/cursos/fl_studio.jpg', 'Producción'),
                ('Teoría Musical para Productores', 'Entiende escalas, acordes y melodías.', 49.99, 'julianmoreno', 'uploads/cursos/teoria.jpg', 'Teoría'),
                ('Mezcla y Mastering Básico', 'Los fundamentos de una mezcla limpia.', 79.99, 'admin', 'uploads/cursos/mezcla.jpg', 'Mezcla'),
                ('Creación de Melodías Lo-fi', 'Técnicas para crear melodías nostálgicas.', 39.99, 'julianmoreno', 'uploads/cursos/lofi.jpg', 'Producción'),
                ('Diseño de Sonido (Serum)', 'Crea tus propios sonidos con Serum.', 59.99, 'admin', 'uploads/cursos/serum.jpg', 'Diseño Sonoro'),
                ('Ableton Live de Cero a Pro', 'Domina Ableton Live para producción.', 89.99, 'ajaramillo', 'uploads/cursos/ableton.jpg', 'Producción'),
                ('Ritmos de Boom Bap Clásico', 'Aprende a programar baterías de Boom Bap.', 49.99, 'ajaramillo', 'uploads/cursos/boombap.jpg', 'Producción'),
                ('Marketing Musical 101', 'Vende tus beats y crece tu marca.', 29.99, 'admin', 'uploads/cursos/marketing.jpg', 'Industria'),
                ('Composición de Acordes R&B', 'Progresiones de acordes avanzadas.', 59.99, 'nataliarojas', 'uploads/cursos/rb.jpg', 'Teoría'),
                ('Técnicas de Sampling', 'El arte de samplear discos de vinilo.', 49.99, 'nataliarojas', 'uploads/cursos/sampling.jpg', 'Producción'),
                ('Producción de Trap Moderno', 'Crea 808s potentes y melodías de Trap.', 59.99, 'julianmoreno', 'uploads/cursos/trap.jpg', 'Producción'),
                ('Mastering con Ozone', 'Técnicas avanzadas de mastering.', 79.99, 'admin', 'uploads/cursos/ozone.jpg', 'Mezcla'),
                ('Grabación de Voces', 'Cómo grabar y editar voces en casa.', 39.99, 'admin', 'uploads/cursos/voces.jpg', 'Ingeniería'),
                ('Producción de Reggaeton', 'Crea ritmos de Reggaeton (Dem-bow).', 49.99, 'ajaramillo', 'uploads/cursos/reggaeton.jpg', 'Producción'),
                ('Síntesis FM (Ableton Operator)', 'Diseño sonoro con sínteis FM.', 59.99, 'admin', 'uploads/cursos/fm.jpg', 'Diseño Sonoro'),
                ('Estructura de Canciones', 'Aprende a arreglar tus beats.', 29.99, 'julianmoreno', 'uploads/cursos/estructura.jpg', 'Teoría'),
                ('Negocios de la Música', 'Licencias, contratos y regalías.', 99.99, 'admin', 'uploads/cursos/negocios.jpg', 'Industria'),
                ('Producción de Drill', 'Bajos deslizantes y baterías de Drill.', 59.99, 'julianmoreno', 'uploads/cursos/drill.jpg', 'Producción'),
                ('Mezcla de Voces (Hip Hop)', 'Técnicas para mezclar voces de Rap.', 69.99, 'nataliarojas', 'uploads/cursos/mezcla_voces.jpg', 'Mezcla'),
                ('Creación de Efectos (FX)', 'Diseña tus propios risers, sweeps y FX.', 39.99, 'admin', 'uploads/cursos/fx.jpg', 'Diseño Sonoro'),
            ]
            cursos_obj = []
            for c in cursos_data:
                cursos_obj.append(Curso(
                    Titulo=c[0], Descripcion=c[1], Precio=c[2], Instructor=c[3], ImagenUrl=c[4], Categoria=c[5]
                ))
            db.session.add_all(cursos_obj)
            db.session.commit()
            
        if Sample.query.count() == 0:
            print("Poblando la base de datos con samples...")
            productores = [Usuario.query.get(2), Usuario.query.get(3), Usuario.query.get(4)]
            sample_nombres = ["Drums Lo-fi", "Guitarra Triste", "Melodía R&B", "Voz 80s"]
            for i in range(10):
                tipo_lic = random.choice(['Gratuita', 'Regalías'])
                porcentaje = 50 if tipo_lic == 'Regalías' else 0
                desc = "Uso gratuito con atribución." if tipo_lic == 'Gratuita' else f"Split de regalías del {porcentaje}% para el productor."

                nuevo_sample = Sample(
                    Nombre=f"{random.choice(sample_nombres)} #{i+1}",
                    audio_preview_url="default.mp3",
                    file_sample_url="default.mp3", # <-- Añadido archivo de descarga
                    UsuarioId=random.choice(productores).UsuarioId,
                    dnda_registro=f"10-{random.randint(100, 999)}-{random.randint(100, 999)}" if random.choice([True, False]) else None
                )
                db.session.add(nuevo_sample)
                db.session.flush()

                nueva_licencia = SampleLicense(
                    SampleId=nuevo_sample.SampleId,
                    Tipo=tipo_lic,
                    porcentaje_regalias=porcentaje,
                    descripcion=desc
                )
                db.session.add(nueva_licencia)
            db.session.commit()
            
        print('Base de datos lista.')

if __name__ == '__main__':
    inicializar_base_de_datos()
    app.run(debug=True, host='0.0.0.0', port=5000)