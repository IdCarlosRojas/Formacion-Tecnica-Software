# models.py
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# 1. Crea la instancia de la base de datos
# app.py la importará desde aquí
db = SQLAlchemy()

# 2. Define el modelo Usuario con la lógica de contraseñas
class Usuario(db.Model):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    correo = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default='cliente')
    
    # Relaciones (Bidireccionales)
    cliente = db.relationship('Cliente', back_populates='usuario', uselist=False, cascade="all, delete-orphan")
    veterinario = db.relationship('Veterinario', back_populates='usuario', uselist=False, cascade="all, delete-orphan")

    # <<<--- ¡¡AQUÍ ESTÁ LA LÓGICA QUE FALTABA!! --- >>>
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# 3. Define el resto de tus modelos (con relaciones)
class Cliente(db.Model):
    __tablename__ = 'cliente'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.String(200))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), unique=True, nullable=False)
    
    # Relaciones
    usuario = db.relationship('Usuario', back_populates='cliente')
    mascotas = db.relationship('Mascota', back_populates='cliente', cascade="all, delete-orphan")
    citas = db.relationship('Cita', back_populates='cliente', cascade="all, delete-orphan")
    facturas = db.relationship('Factura', back_populates='cliente', cascade="all, delete-orphan")
    notificaciones = db.relationship('Notificacion', back_populates='cliente', cascade="all, delete-orphan")

    def to_dict(self):
        # El frontend (app.js) espera este formato
        return {
            "id": self.id, 
            "nombre": self.nombre, 
            "correo": self.usuario.correo if self.usuario else None, 
            "telefono": self.telefono
        }

class Veterinario(db.Model):
    __tablename__ = 'veterinario'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    especialidad = db.Column(db.String(100))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), unique=True, nullable=False)
    
    # Relaciones
    usuario = db.relationship('Usuario', back_populates='veterinario')
    citas = db.relationship('Cita', back_populates='veterinario')
    # Nota: to_dict() se añade dinámicamente en app.py, lo cual está bien.

class Mascota(db.Model):
    __tablename__ = 'mascota'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    especie = db.Column(db.String(50))
    raza = db.Column(db.String(50))
    edad = db.Column(db.Integer)
    genero = db.Column(db.String(20))
    imagen_url = db.Column(db.String(500), default='/static/pet_default.png')
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    
    # Relaciones
    cliente = db.relationship('Cliente', back_populates='mascotas')
    citas = db.relationship('Cita', back_populates='mascota', cascade="all, delete-orphan")
    historial_clinico = db.relationship('HistorialClinico', back_populates='mascota', uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        # El frontend (app.js) espera este formato
        return {
            "id": self.id, 
            "nombre": self.nombre, 
            "especie": self.especie, 
            "raza": self.raza, 
            "edad": self.edad, 
            "genero": self.genero, 
            "imagen_url": self.imagen_url, 
            "cliente_id": self.cliente_id
        }

class Cita(db.Model):
    __tablename__ = 'cita'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
    motivo = db.Column(db.String(255))
    estado = db.Column(db.String(50), default='Pendiente')
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    mascota_id = db.Column(db.Integer, db.ForeignKey('mascota.id'), nullable=False)
    veterinario_id = db.Column(db.Integer, db.ForeignKey('veterinario.id'), nullable=True)
    
    # Relaciones
    cliente = db.relationship('Cliente', back_populates='citas')
    mascota = db.relationship('Mascota', back_populates='citas')
    veterinario = db.relationship('Veterinario', back_populates='citas')

    def to_dict(self):
        # El frontend (app.js y admin.js) espera este formato
        return {
            "id": self.id,
            "fecha": self.fecha.isoformat(),
            "hora": self.hora.isoformat(),
            "motivo": self.motivo,
            "estado": self.estado,
            "cliente_id": self.cliente_id,
            "cliente_nombre": self.cliente.nombre if self.cliente else None,
            "mascota_id": self.mascota_id,
            "mascota_nombre": self.mascota.nombre if self.mascota else None,
            "veterinario_id": self.veterinario_id,
            "veterinario_nombre": self.veterinario.nombre if self.veterinario else None
        }

class Producto(db.Model):
    __tablename__ = 'producto'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    precio = db.Column(db.Float, nullable=False)
    cantidad_stock = db.Column(db.Integer, nullable=False, default=0)
    imagen_url = db.Column(db.String(500))
    
    factura_items = db.relationship('FacturaProducto', back_populates='producto')

    def to_dict(self):
        # El frontend (app.js) espera este formato
        return {
            "id": self.id, 
            "title": self.nombre, 
            "desc": self.descripcion, 
            "price": self.precio, 
            "stock": self.cantidad_stock, 
            "imagen_url": self.imagen_url
        }

class Factura(db.Model):
    __tablename__ = 'factura'
    id = db.Column(db.Integer, primary_key=True)
    fecha_factura = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    monto_total = db.Column(db.Float, nullable=False)
    metodo_pago = db.Column(db.String(50))
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    
    cliente = db.relationship('Cliente', back_populates='facturas')
    items = db.relationship('FacturaProducto', back_populates='factura', cascade="all, delete-orphan")

class FacturaProducto(db.Model):
    __tablename__ = 'factura_producto'
    factura_id = db.Column(db.Integer, db.ForeignKey('factura.id'), primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), primary_key=True)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False)
    
    factura = db.relationship('Factura', back_populates='items')
    producto = db.relationship('Producto', back_populates='factura_items')

class Notificacion(db.Model):
    __tablename__ = 'notificacion'
    id = db.Column(db.Integer, primary_key=True)
    mensaje = db.Column(db.Text, nullable=False)
    fecha_envio = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    tipo = db.Column(db.String(50))
    leida = db.Column(db.Boolean, default=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    
    cliente = db.relationship('Cliente', back_populates='notificaciones')

class HistorialClinico(db.Model):
    __tablename__ = 'historial_clinico'
    id = db.Column(db.Integer, primary_key=True)
    fecha_registro = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    diagnostico = db.Column(db.Text)
    tratamiento = db.Column(db.Text)
    mascota_id = db.Column(db.Integer, db.ForeignKey('mascota.id'), unique=True, nullable=False)
    
    mascota = db.relationship('Mascota', back_populates='historial_clinico')
    vacunas = db.relationship('Vacuna', back_populates='historial', cascade="all, delete-orphan")
    # Nota: to_dict_completo() se añade dinámicamente en app.py.

class Vacuna(db.Model):
    __tablename__ = 'vacuna'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    fecha_aplicacion = db.Column(db.Date, nullable=False)
    fecha_proxima = db.Column(db.Date, nullable=True)
    historial_id = db.Column(db.Integer, db.ForeignKey('historial_clinico.id'), nullable=False)
    
    historial = db.relationship('HistorialClinico', back_populates='vacunas')
    # Nota: to_dict() se añade dinámicamente en app.py.