# models.py (COMPLETAMENTE ACTUALIZADO - CORRECCIÓN DE BORRADO)
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sqlalchemy.sql import func
from sqlalchemy import Table, Column, Integer, ForeignKey
from datetime import datetime 

db = SQLAlchemy()
bcrypt = Bcrypt()

# --- TABLA DE USUARIOS (MODIFICADA) ---
class User(db.Model):
    __tablename__ = 'USUARIOS'
    UsuarioId = db.Column(db.Integer, primary_key=True)
    Nombre = db.Column(db.String(100), nullable=False)
    Correo = db.Column(db.String(100), unique=True, nullable=False)
    Contrasena = db.Column(db.String(255), nullable=False)
    TipoUsuario = db.Column(db.Enum('regular', 'admin', 'instructor'), nullable=False, default='regular')
    Edad = db.Column(db.Integer)
    ProfilePic = db.Column(db.String(100), nullable=True, default='default.jpg')
    Height = db.Column(db.Numeric(5, 2), nullable=True) 
    CurrentWeight = db.Column(db.Numeric(5, 2), nullable=True) 
    Goal = db.Column(db.String(200), nullable=True)

    # --- ¡¡¡RELACIONES MODIFICADAS CON CASCADA!!! ---
    reservas = db.relationship('Reserva', back_populates='usuario', cascade="all, delete-orphan")
    rutinas = db.relationship('Rutina', back_populates='usuario', cascade="all, delete-orphan")
    progresos = db.relationship('Progreso', back_populates='usuario', cascade="all, delete-orphan")
    membresia = db.relationship('Membresia', back_populates='usuario', uselist=False, cascade="all, delete-orphan")
    pagos = db.relationship('Pago', back_populates='usuario', cascade="all, delete-orphan")
    entrenamientos = db.relationship('Entrenamiento', back_populates='usuario', cascade="all, delete-orphan")
    
    mensajes_enviados = db.relationship('Mensaje', foreign_keys='Mensaje.RemitenteId', back_populates='remitente', cascade="all, delete-orphan")
    mensajes_recibidos = db.relationship('Mensaje', foreign_keys='Mensaje.DestinatarioId', back_populates='destinatario', cascade="all, delete-orphan")
    
    def set_password(self, password):
        self.Contrasena = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.Contrasena, password)
    
    def get_total_workouts(self):
        return len(self.entrenamientos)
    def get_followers_count(self):
        return 0
    def get_following_count(self):
        return 0

# --- (El resto de los modelos no necesitan cambios) ---
class Ejercicio(db.Model):
    __tablename__ = 'EJERCICIOS'
    EjercicioId = db.Column(db.Integer, primary_key=True)
    Nombre = db.Column(db.String(100), nullable=False, unique=True)
    GrupoMuscular = db.Column(db.String(50)) 

class Rutina(db.Model):
    __tablename__ = 'RUTINAS'
    RutinaId = db.Column(db.Integer, primary_key=True)
    UsuarioId = db.Column(db.Integer, db.ForeignKey('USUARIOS.UsuarioId'), nullable=False)
    Nombre = db.Column(db.String(100), nullable=False, default="Nueva Rutina")
    
    usuario = db.relationship('User', back_populates='rutinas')
    ejercicios_en_rutina = db.relationship('RutinaEjercicio', back_populates='rutina', cascade="all, delete-orphan")

class RutinaEjercicio(db.Model):
    __tablename__ = 'RUTINA_EJERCICIO'
    RutinaEjercicioId = db.Column(db.Integer, primary_key=True)
    RutinaId = db.Column(db.Integer, db.ForeignKey('RUTINAS.RutinaId'), nullable=False)
    EjercicioId = db.Column(db.Integer, db.ForeignKey('EJERCICIOS.EjercicioId'), nullable=False)
    Orden = db.Column(db.Integer, default=0)
    
    rutina = db.relationship('Rutina', back_populates='ejercicios_en_rutina')
    ejercicio = db.relationship('Ejercicio')
    sets_planeados = db.relationship('SetPlaneado', back_populates='rutina_ejercicio', cascade="all, delete-orphan")

class SetPlaneado(db.Model):
    __tablename__ = 'SETS_PLANEADOS'
    SetId = db.Column(db.Integer, primary_key=True)
    RutinaEjercicioId = db.Column(db.Integer, db.ForeignKey('RUTINA_EJERCICIO.RutinaEjercicioId'), nullable=False)
    SeriesNum = db.Column(db.Integer, default=1)
    Reps = db.Column(db.Integer)
    Peso = db.Column(db.Numeric(5, 2))
    
    rutina_ejercicio = db.relationship('RutinaEjercicio', back_populates='sets_planeados')


class Entrenamiento(db.Model):
    __tablename__ = 'ENTRENAMIENTOS'
    EntrenamientoId = db.Column(db.Integer, primary_key=True)
    UsuarioId = db.Column(db.Integer, db.ForeignKey('USUARIOS.UsuarioId'), nullable=False)
    Nombre = db.Column(db.String(100))
    Fecha = db.Column(db.Date, nullable=False, default=func.current_date())
    DuracionHoras = db.Column(db.Numeric(4, 2))
    TotalVolume = db.Column(db.Numeric(10, 2), nullable=True)
    
    usuario = db.relationship('User', back_populates='entrenamientos')
    detalles = db.relationship('EntrenamientoDetalle', back_populates='entrenamiento', cascade="all, delete-orphan")

class EntrenamientoDetalle(db.Model):
    __tablename__ = 'ENTRENAMIENTO_DETALLE'
    DetalleId = db.Column(db.Integer, primary_key=True)
    EntrenamientoId = db.Column(db.Integer, db.ForeignKey('ENTRENAMIENTOS.EntrenamientoId'), nullable=False)
    EjercicioId = db.Column(db.Integer, db.ForeignKey('EJERCICIOS.EjercicioId'), nullable=False)
    SeriesNum = db.Column(db.Integer)
    Peso = db.Column(db.Numeric(5, 2))
    Reps = db.Column(db.Integer)
    
    entrenamiento = db.relationship('Entrenamiento', back_populates='detalles')
    ejercicio = db.relationship('Ejercicio')

class Progreso(db.Model):
    __tablename__ = 'PROGRESO'
    ProgresoId = db.Column(db.Integer, primary_key=True)
    UsuarioId = db.Column(db.Integer, db.ForeignKey('USUARIOS.UsuarioId'), nullable=False)
    Peso = db.Column(db.Numeric(5, 2))
    GrasaCorporal = db.Column(db.Numeric(4, 2))
    MasaMuscular = db.Column(db.Numeric(4, 2))
    FechaRegistro = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    
    usuario = db.relationship('User', back_populates='progresos')

class Clase(db.Model):
    __tablename__ = 'CLASES'
    ClaseId = db.Column(db.Integer, primary_key=True)
    NombreClase = db.Column(db.String(100), nullable=False)
    FechaHora = db.Column(db.DateTime, nullable=False)
    CupoMaximo = db.Column(db.Integer, nullable=False)
    EntrenadorId = db.Column(db.Integer, db.ForeignKey('USUARIOS.UsuarioId'), nullable=True) 
    
    reservas = db.relationship('Reserva', back_populates='clase', cascade="all, delete-orphan")
    entrenador = db.relationship('User', foreign_keys=[EntrenadorId])

class Reserva(db.Model):
    __tablename__ = 'RESERVAS'
    ReservaId = db.Column(db.Integer, primary_key=True)
    UsuarioId = db.Column(db.Integer, db.ForeignKey('USUARIOS.UsuarioId'), nullable=False)
    ClaseId = db.Column(db.Integer, db.ForeignKey('CLASES.ClaseId'), nullable=False)
    Estado = db.Column(db.Enum('confirmada', 'cancelada', 'lista_espera'), nullable=False, default='confirmada')
    FechaReserva = db.Column(db.DateTime, nullable=False, default=func.now())
    
    usuario = db.relationship('User', back_populates='reservas')
    clase = db.relationship('Clase', back_populates='reservas')

class Membresia(db.Model):
    __tablename__ = 'MEMBRESIAS'
    MembresiaId = db.Column(db.Integer, primary_key=True)
    UsuarioId = db.Column(db.Integer, db.ForeignKey('USUARIOS.UsuarioId'), unique=True, nullable=False)
    Tipo = db.Column(db.String(50), nullable=False)
    FechaInicio = db.Column(db.Date, nullable=False)
    FechaFin = db.Column(db.Date, nullable=False)
    Estado = db.Column(db.Enum('activa', 'vencida', 'cancelada'), nullable=False, default='activa')
    
    usuario = db.relationship('User', back_populates='membresia', uselist=False)

class Pago(db.Model):
    __tablename__ = 'PAGOS'
    PagoId = db.Column(db.Integer, primary_key=True)
    UsuarioId = db.Column(db.Integer, db.ForeignKey('USUARIOS.UsuarioId'), nullable=False)
    Monto = db.Column(db.Numeric(10, 2), nullable=False)
    MetodoPago = db.Column(db.String(50))
    FechaPago = db.Column(db.DateTime, nullable=False, default=func.now())
    Descripcion = db.Column(db.Text)
    
    usuario = db.relationship('User', back_populates='pagos')

class Mensaje(db.Model):
    __tablename__ = 'MENSAJES'
    MensajeId = db.Column(db.Integer, primary_key=True)
    RemitenteId = db.Column(db.Integer, db.ForeignKey('USUARIOS.UsuarioId'), nullable=False)
    DestinatarioId = db.Column(db.Integer, db.ForeignKey('USUARIOS.UsuarioId'), nullable=False)
    Mensaje = db.Column(db.Text, nullable=False)
    FechaEnvio = db.Column(db.DateTime, nullable=False, default=func.now())
    
    remitente = db.relationship('User', foreign_keys=[RemitenteId], back_populates='mensajes_enviados')
    destinatario = db.relationship('User', foreign_keys=[DestinatarioId], back_populates='mensajes_recibidos')
