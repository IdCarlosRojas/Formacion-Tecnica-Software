import os
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from flask_migrate import Migrate
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager, get_jwt
from datetime import datetime, time
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename
from functools import wraps

# Importar desde models.py
from config import Config
from models import db, Usuario, Cliente, Veterinario, Mascota, Producto, Cita, Notificacion, HistorialClinico, Vacuna, Factura, FacturaProducto

app = Flask(__name__) 
app.config.from_object(Config) 
CORS(app) 

UPLOAD_FOLDER = os.path.join(app.instance_path, 'uploads', 'pets')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

# --- Decorador de Roles ---
def role_required(roles):
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            claims = get_jwt()
            user_rol = claims.get('rol', 'cliente') 
            if user_rol not in roles:
                return jsonify(msg="Acceso no autorizado para este rol"), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

# --- Callbacks de JWT ---
@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    return Usuario.query.get(identity)

@jwt.additional_claims_loader
def add_claims_to_access_token(identity): 
    usuario = Usuario.query.get(identity)
    if usuario:
        return {"rol": usuario.rol}
    else:
        return {"rol": "unknown"}

# --- Métodos de Diccionario (Se mantienen) ---
def veterinario_to_dict(self):
    return {
        "id": self.id, 
        "nombre": self.nombre, 
        "especialidad": self.especialidad,
        "usuario_id": self.usuario_id,
        "correo": self.usuario.correo if self.usuario else "N/A"
    }
Veterinario.to_dict = veterinario_to_dict

def vacuna_to_dict(self):
    return { 
        "id": self.id, 
        "nombre": self.nombre, 
        "fecha_aplicacion": self.fecha_aplicacion.isoformat() if self.fecha_aplicacion else None, 
        "fecha_proxima": self.fecha_proxima.isoformat() if self.fecha_proxima else None 
    }
Vacuna.to_dict = vacuna_to_dict

def historial_to_dict_completo(self):
    mascota_nombre = self.mascota.nombre if self.mascota else "Mascota Eliminada"
    return { 
        "id": self.id, 
        "fecha_registro": self.fecha_registro.isoformat() if self.fecha_registro else None, 
        "diagnostico": self.diagnostico, 
        "tratamiento": self.tratamiento, 
        "mascota_id": self.mascota_id,
        "mascota_nombre": mascota_nombre, 
        "vacunas": [v.to_dict() for v in self.vacunas] 
    }
HistorialClinico.to_dict_completo = historial_to_dict_completo

# --- Rutas de Frontend ---
@app.route('/')
def serve_index():
    return render_template('index.html')

@app.route('/admin')
def serve_admin():
    return render_template('admin.html')

@app.route('/api/uploads/pets/<path:filename>')
def serve_pet_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# --- Rutas de API ---

# 1. AUTENTICACIÓN
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    correo = data.get('email')
    password = data.get('password')
    nombre = data.get('name', 'Usuario') + ' ' + data.get('lastname', '')

    if not correo or not password:
        return jsonify({"msg": "Correo y contraseña son requeridos"}), 400
    
    if Usuario.query.filter_by(correo=correo).first():
        return jsonify({"msg": "El correo ya está registrado"}), 400

    try:
        nuevo_usuario = Usuario(correo=correo, rol='cliente')
        nuevo_usuario.set_password(password)
        db.session.add(nuevo_usuario)
        db.session.flush() 
        nuevo_cliente = Cliente(nombre=nombre.strip(), telefono=data.get('phone'), usuario_id=nuevo_usuario.id)
        db.session.add(nuevo_cliente)
        db.session.commit()
        return jsonify({"msg": "Usuario registrado exitosamente"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": f"Error al registrar: {str(e)}"}), 500


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    identifier = data.get('identifier') # Correo
    password = data.get('password')

    usuario = Usuario.query.filter_by(correo=identifier).first()
    
    if not usuario or not usuario.check_password(password):
        return jsonify({"msg": "Credenciales incorrectas"}), 401
        
    # Convertimos el ID a string
    access_token = create_access_token(identity=str(usuario.id)) 
    
    return jsonify(access_token=access_token), 200

# 2. PERFIL (Rutas de Cliente)
def get_cliente_from_jwt():
    usuario_id = get_jwt_identity() # Ya es string
    usuario = Usuario.query.get(int(usuario_id)) # Convertir a int para buscar
    if not usuario or not usuario.cliente:
        raise Exception("Perfil de cliente no encontrado")
    return usuario.cliente

@app.route('/api/profile', methods=['GET', 'PUT'])
@jwt_required()
@role_required(roles=['cliente']) 
def profile():
    try:
        cliente = get_cliente_from_jwt()
    except Exception as e:
        return jsonify({"msg": str(e)}), 404
        
    if request.method == 'PUT':
        data = request.json
        cliente.nombre = data.get('nombre', cliente.nombre)
        cliente.telefono = data.get('telefono', cliente.telefono)
        try:
            db.session.commit()
            return jsonify({"msg": "Perfil actualizado", "cliente": cliente.to_dict()}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"msg": f"Error al actualizar: {str(e)}"}), 500

    profile_data = cliente.to_dict()
    profile_data['wallet'] = 500000 
    profile_data['coins'] = 1100
    return jsonify(profile_data), 200

# 3. PRODUCTOS (Ruta pública)
@app.route('/api/products', methods=['GET'])
def get_products():
    productos = Producto.query.all()
    return jsonify([p.to_dict() for p in productos]), 200

# 4. MASCOTAS (Rutas de Cliente)
@app.route('/api/mascotas', methods=['GET', 'POST'])
@jwt_required()
@role_required(roles=['cliente'])
def handle_mascotas():
    try:
        cliente = get_cliente_from_jwt()
    except Exception as e:
        return jsonify({"msg": str(e)}), 404
    
    if request.method == 'POST':
        data = request.json
        nueva_mascota = Mascota(nombre=data.get('nombre'), especie=data.get('especie'), raza=data.get('raza'), edad=data.get('edad'), genero=data.get('genero'), cliente_id=cliente.id)
        try:
            db.session.add(nueva_mascota)
            db.session.flush() 
            historial = HistorialClinico(mascota_id=nueva_mascota.id)
            db.session.add(historial)
            db.session.commit()
            return jsonify(nueva_mascota.to_dict()), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"msg": f"Error al registrar mascota: {str(e)}"}), 500
    mascotas = Mascota.query.filter_by(cliente_id=cliente.id).all()
    return jsonify([m.to_dict() for m in mascotas]), 200

@app.route('/api/mascotas/<int:mascota_id>/upload', methods=['POST'])
@jwt_required()
@role_required(roles=['cliente'])
def upload_pet_photo(mascota_id):
    try:
        cliente = get_cliente_from_jwt()
    except Exception as e:
        return jsonify({"msg": str(e)}), 404
    
    mascota = Mascota.query.get_or_404(mascota_id)
    if mascota.cliente_id != cliente.id:
        return jsonify(msg="No tienes permiso para editar esta mascota"), 403
        
    if 'photo' not in request.files:
        return jsonify(msg="No se encontró el archivo 'photo'"), 400
        
    file = request.files['photo']
    
    if file.filename == '':
        return jsonify(msg="No se seleccionó ningún archivo"), 400
        
    if file:
        try:
            filename = secure_filename(file.filename)
            _, ext = os.path.splitext(filename)
            unique_filename = f"pet_{mascota.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            mascota.imagen_url = f"/api/uploads/pets/{unique_filename}"
            db.session.commit()
            
            return jsonify(msg="Foto actualizada", new_url=mascota.imagen_url), 200
        
        except Exception as e:
            db.session.rollback()
            return jsonify(msg=f"Error al guardar el archivo: {str(e)}"), 500
            
    return jsonify(msg="Error desconocido al subir archivo"), 500

# 5. CITAS (Ruta de Cliente)
@app.route('/api/citas', methods=['GET', 'POST'])
@jwt_required()
@role_required(roles=['cliente'])
def handle_citas_cliente():
    try:
        cliente = get_cliente_from_jwt()
    except Exception as e:
        return jsonify({"msg": str(e)}), 404
    
    if request.method == 'POST':
        data = request.json
        try:
            fecha = datetime.fromisoformat(data.get('fecha')).date()
            hora = time.fromisoformat(data.get('hora'))
        except (ValueError, TypeError):
            return jsonify({"msg": "Formato de fecha u hora inválido"}), 400
        mascota = Mascota.query.filter_by(id=data.get('mascota_id'), cliente_id=cliente.id).first()
        if not mascota:
            return jsonify({"msg": "Mascota no encontrada o no te pertenece"}), 404
        nueva_cita = Cita(fecha=fecha, hora=hora, motivo=data.get('motivo'), cliente_id=cliente.id, mascota_id=data.get('mascota_id'), veterinario_id=data.get('veterinario_id'), estado='Pendiente')
        db.session.add(nueva_cita)
        notif = Notificacion(mensaje=f"Tu solicitud de cita para {mascota.nombre} el {fecha} ha sido recibida.", tipo="Cita", cliente_id=cliente.id)
        db.session.add(notif)
        db.session.commit()
        return jsonify(nueva_cita.to_dict()), 201
    citas = Cita.query.filter_by(cliente_id=cliente.id).order_by(Cita.fecha.desc(), Cita.hora.desc()).all()
    return jsonify([c.to_dict() for c in citas]), 200

# 6. VETERINARIOS (Ruta para Clientes)
@app.route('/api/veterinarios', methods=['GET'])
@jwt_required()
@role_required(roles=['cliente'])
def get_veterinarios():
    vets = Veterinario.query.all()
    # Usamos el to_dict definido arriba
    return jsonify([v.to_dict() for v in vets]), 200

# 7. NOTIFICACIONES (Ruta de Cliente)
@app.route('/api/notificaciones', methods=['GET'])
@jwt_required()
@role_required(roles=['cliente'])
def get_notificaciones():
    try:
        cliente = get_cliente_from_jwt()
    except Exception as e:
        return jsonify({"msg": str(e)}), 404
    notificaciones = Notificacion.query.filter_by(cliente_id=cliente.id, leida=False).order_by(Notificacion.fecha_envio.desc()).all()
    return jsonify([{ "id": n.id, "mensaje": n.mensaje, "fecha": n.fecha_envio.isoformat(), "tipo": n.tipo } for n in notificaciones]), 200

# 8. HISTORIAL (Ruta de Cliente)
@app.route('/api/mascotas/<int:mascota_id>/historial', methods=['GET'])
@jwt_required()
@role_required(roles=['cliente'])
def get_historial_mascota(mascota_id):
    try:
        cliente = get_cliente_from_jwt()
    except Exception as e:
        return jsonify({"msg": str(e)}), 404
    mascota = Mascota.query.get_or_404(mascota_id)
    if mascota.cliente_id != cliente.id:
        return jsonify({"msg": "Acceso no autorizado"}), 403
    historial = mascota.historial_clinico
    if not historial:
        historial = HistorialClinico(mascota_id=mascota.id, diagnostico="Sin historial registrado.", tratamiento="Sin historial registrado.")
        db.session.add(historial)
        db.session.commit()
    return jsonify(historial.to_dict_completo()), 200


# ===============================================
# --- INICIO DE RUTAS DE ADMIN ---
# ===============================================

# --- ADMIN: CITAS ---
@app.route('/api/admin/citas', methods=['GET'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def get_all_citas():
    citas = Cita.query.order_by(Cita.fecha.desc(), Cita.hora.desc()).all()
    return jsonify([c.to_dict() for c in citas]), 200

# NUEVO: Ruta para crear cita desde el admin
@app.route('/api/admin/citas', methods=['POST'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def create_cita_admin():
    data = request.json
    try:
        fecha = datetime.fromisoformat(data.get('fecha')).date()
        hora = time.fromisoformat(data.get('hora'))
        cliente_id = int(data.get('cliente_id'))
        mascota_id = int(data.get('mascota_id'))
        
        # Validar que la mascota pertenezca al cliente
        mascota = Mascota.query.get(mascota_id)
        if not mascota or mascota.cliente_id != cliente_id:
            return jsonify(msg="La mascota no pertenece al cliente seleccionado"), 404
            
        nueva_cita = Cita(
            fecha=fecha, 
            hora=hora, 
            motivo=data.get('motivo'), 
            cliente_id=cliente_id, 
            mascota_id=mascota_id, 
            veterinario_id=data.get('veterinario_id') or None, 
            estado='Programada' # El admin la crea como programada
        )
        db.session.add(nueva_cita)
        # Enviar notificación al cliente
        notif = Notificacion(
            mensaje=f"Se ha programado una nueva cita para {mascota.nombre} el {fecha}.", 
            tipo="CitaConfirmada", 
            cliente_id=cliente_id
        )
        db.session.add(notif)
        db.session.commit()
        return jsonify(nueva_cita.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al crear cita: {str(e)}"), 500


@app.route('/api/admin/citas/<int:cita_id>/approve', methods=['PUT'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def approve_cita(cita_id):
    cita = Cita.query.get_or_404(cita_id)
    cita.estado = 'Programada'
    notif = Notificacion(mensaje=f"¡Cita Aprobada! Tu cita para {cita.mascota.nombre} el {cita.fecha} ha sido programada.", tipo="CitaConfirmada", cliente_id=cita.cliente_id)
    db.session.add(notif)
    db.session.commit()
    return jsonify(cita.to_dict()), 200

@app.route('/api/admin/citas/<int:cita_id>/reject', methods=['PUT'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def reject_cita(cita_id):
    cita = Cita.query.get_or_404(cita_id)
    cita.estado = 'Rechazada'
    notif = Notificacion(mensaje=f"Cita Rechazada. Tu solicitud de cita para {cita.mascota.nombre} el {cita.fecha} fue rechazada.", tipo="CitaRechazada", cliente_id=cita.cliente_id)
    db.session.add(notif)
    db.session.commit()
    return jsonify(cita.to_dict()), 200

@app.route('/api/admin/citas/<int:cita_id>', methods=['DELETE'])
@jwt_required()
@role_required(roles=['admin']) 
def delete_cita(cita_id):
    cita = Cita.query.get_or_404(cita_id)
    try:
        db.session.delete(cita)
        db.session.commit()
        return jsonify({"msg": "Cita eliminada"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": f"Error al eliminar: {str(e)}"}), 500

# --- ADMIN: PRODUCTOS ---
@app.route('/api/admin/productos', methods=['POST'])
@jwt_required()
@role_required(roles=['admin'])
def create_producto():
    data = request.json
    try:
        nuevo = Producto(
            nombre=data.get('nombre'),
            descripcion=data.get('descripcion'),
            precio=float(data.get('precio')),
            cantidad_stock=int(data.get('stock')),
            imagen_url=data.get('imagen_url')
        )
        db.session.add(nuevo)
        db.session.commit()
        return jsonify(nuevo.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al crear producto: {str(e)}"), 500

@app.route('/api/admin/productos/<int:producto_id>', methods=['PUT'])
@jwt_required()
@role_required(roles=['admin'])
def update_producto(producto_id):
    prod = Producto.query.get_or_404(producto_id)
    data = request.json
    try:
        prod.nombre = data.get('nombre', prod.nombre)
        prod.descripcion = data.get('descripcion', prod.descripcion)
        prod.precio = float(data.get('precio', prod.precio))
        prod.cantidad_stock = int(data.get('stock', prod.cantidad_stock))
        prod.imagen_url = data.get('imagen_url', prod.imagen_url)
        db.session.commit()
        return jsonify(prod.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al actualizar producto: {str(e)}"), 500

@app.route('/api/admin/productos/<int:producto_id>', methods=['DELETE'])
@jwt_required()
@role_required(roles=['admin'])
def delete_producto(producto_id):
    prod = Producto.query.get_or_404(producto_id)
    try:
        db.session.delete(prod)
        db.session.commit()
        return jsonify(msg="Producto eliminado"), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al eliminar producto: {str(e)}"), 500

# --- ADMIN: USUARIOS ---
@app.route('/api/admin/usuarios', methods=['GET'])
@jwt_required()
@role_required(roles=['admin'])
def get_all_usuarios():
    try:
        usuarios = Usuario.query.all()
        results = []
        for u in usuarios:
            nombre = "N/A"
            if u.cliente:
                nombre = u.cliente.nombre
            elif u.veterinario:
                nombre = u.veterinario.nombre
            elif u.rol == 'admin':
                nombre = "Administrador"
            
            results.append({
                "id": u.id,
                "correo": u.correo,
                "rol": u.rol,
                "nombre": nombre
            })
        return jsonify(results), 200
    except Exception as e:
        return jsonify(msg=f"Error al cargar usuarios: {str(e)}"), 500

@app.route('/api/admin/usuarios/<int:usuario_id>', methods=['PUT'])
@jwt_required()
@role_required(roles=['admin'])
def update_usuario(usuario_id):
    user = Usuario.query.get_or_404(usuario_id)
    data = request.json
    try:
        user.rol = data.get('rol', user.rol)
        if user.cliente:
            user.cliente.nombre = data.get('nombre', user.cliente.nombre)
        elif user.veterinario:
            user.veterinario.nombre = data.get('nombre', user.veterinario.nombre)
        
        db.session.commit()
        return jsonify(msg="Usuario actualizado"), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al actualizar usuario: {str(e)}"), 500

@app.route('/api/admin/usuarios/<int:usuario_id>', methods=['DELETE'])
@jwt_required()
@role_required(roles=['admin'])
def delete_usuario(usuario_id):
    user = Usuario.query.get_or_404(usuario_id)
    if user.rol == 'admin':
        return jsonify(msg="No se puede eliminar a un administrador"), 403
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify(msg="Usuario eliminado"), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al eliminar usuario: {str(e)}"), 500

# --- ADMIN: MASCOTAS ---
@app.route('/api/admin/mascotas', methods=['GET'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def get_all_mascotas():
    try:
        mascotas = Mascota.query.all()
        results = []
        for m in mascotas:
            results.append({
                "id": m.id,
                "nombre": m.nombre,
                "especie": m.especie,
                "raza": m.raza,
                "edad": m.edad,
                "genero": m.genero,
                "cliente_nombre": m.cliente.nombre if m.cliente else "N/A",
                "cliente_id": m.cliente_id
            })
        return jsonify(results), 200
    except Exception as e:
        return jsonify(msg=f"Error al cargar mascotas: {str(e)}"), 500

# NUEVO: Ruta para crear mascota desde el admin
@app.route('/api/admin/mascotas', methods=['POST'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def create_mascota_admin():
    data = request.json
    cliente_id = data.get('cliente_id')
    if not cliente_id:
        return jsonify(msg="Se requiere un cliente"), 400
        
    nueva_mascota = Mascota(
        nombre=data.get('nombre'), 
        especie=data.get('especie'), 
        raza=data.get('raza'), 
        edad=data.get('edad'), 
        genero=data.get('genero'), 
        cliente_id=cliente_id
    )
    try:
        db.session.add(nueva_mascota)
        db.session.flush() 
        historial = HistorialClinico(mascota_id=nueva_mascota.id)
        db.session.add(historial)
        db.session.commit()
        return jsonify(nueva_mascota.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": f"Error al registrar mascota: {str(e)}"}), 500


@app.route('/api/admin/mascotas/<int:mascota_id>', methods=['PUT'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def update_mascota(mascota_id):
    mascota = Mascota.query.get_or_404(mascota_id)
    data = request.json
    try:
        mascota.nombre = data.get('nombre', mascota.nombre)
        mascota.especie = data.get('especie', mascota.especie)
        mascota.raza = data.get('raza', mascota.raza)
        mascota.edad = data.get('edad', mascota.edad)
        mascota.genero = data.get('genero', mascota.genero)
        db.session.commit()
        return jsonify(msg="Mascota actualizada"), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al actualizar mascota: {str(e)}"), 500

@app.route('/api/admin/mascotas/<int:mascota_id>', methods=['DELETE'])
@jwt_required()
@role_required(roles=['admin']) 
def delete_mascota(mascota_id):
    mascota = Mascota.query.get_or_404(mascota_id)
    try:
        db.session.delete(mascota)
        db.session.commit()
        return jsonify(msg="Mascota eliminada"), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al eliminar: {str(e)}"), 500

# --- ADMIN: VETERINARIOS ---
@app.route('/api/admin/veterinarios', methods=['GET'])
@jwt_required()
@role_required(roles=['admin', 'veterinario']) # Permitir a vet ver a sus colegas
def get_all_veterinarios():
    vets = Veterinario.query.all()
    return jsonify([v.to_dict() for v in vets]), 200

@app.route('/api/admin/veterinarios', methods=['POST'])
@jwt_required()
@role_required(roles=['admin'])
def create_veterinario():
    data = request.json
    correo = data.get('correo')
    password = data.get('password')
    
    if not correo or not password:
        return jsonify(msg="Correo y contraseña son requeridos para el nuevo usuario"), 400
    if Usuario.query.filter_by(correo=correo).first():
        return jsonify(msg="El correo ya está registrado"), 400
        
    try:
        nuevo_usuario = Usuario(correo=correo, rol='veterinario')
        nuevo_usuario.set_password(password)
        db.session.add(nuevo_usuario)
        db.session.flush()
        
        nuevo_vet = Veterinario(
            nombre=data.get('nombre'),
            especialidad=data.get('especialidad'),
            usuario_id=nuevo_usuario.id
        )
        db.session.add(nuevo_vet)
        db.session.commit()
        return jsonify(nuevo_vet.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al crear veterinario: {str(e)}"), 500

@app.route('/api/admin/veterinarios/<int:vet_id>', methods=['PUT'])
@jwt_required()
@role_required(roles=['admin'])
def update_veterinario(vet_id):
    vet = Veterinario.query.get_or_404(vet_id)
    data = request.json
    try:
        vet.nombre = data.get('nombre', vet.nombre)
        vet.especialidad = data.get('especialidad', vet.especialidad)
        db.session.commit()
        return jsonify(vet.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al actualizar veterinario: {str(e)}"), 500

@app.route('/api/admin/veterinarios/<int:vet_id>', methods=['DELETE'])
@jwt_required()
@role_required(roles=['admin'])
def delete_veterinario(vet_id):
    vet = Veterinario.query.get_or_404(vet_id)
    try:
        if vet.usuario:
            db.session.delete(vet.usuario)
        else:
            db.session.delete(vet)
        db.session.commit()
        return jsonify(msg="Veterinario eliminado"), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al eliminar: {str(e)}"), 500

# --- ADMIN: CLIENTES (Para los dropdowns) ---
@app.route('/api/admin/clientes', methods=['GET'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def get_all_clientes():
    try:
        clientes = Cliente.query.order_by(Cliente.nombre).all()
        return jsonify([{"id": c.id, "nombre": c.nombre} for c in clientes]), 200
    except Exception as e:
        return jsonify(msg=f"Error al cargar clientes: {str(e)}"), 500

@app.route('/api/admin/clientes/<int:cliente_id>/mascotas', methods=['GET'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def get_mascotas_for_cliente(cliente_id):
    try:
        mascotas = Mascota.query.filter_by(cliente_id=cliente_id).order_by(Mascota.nombre).all()
        return jsonify([{"id": m.id, "nombre": m.nombre} for m in mascotas]), 200
    except Exception as e:
        return jsonify(msg=f"Error al cargar mascotas: {str(e)}"), 500


# --- ADMIN: GESTIÓN DE CARNET ---
@app.route('/api/admin/mascotas/<int:mascota_id>/historial', methods=['GET'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def get_admin_historial_mascota(mascota_id):
    mascota = Mascota.query.get_or_404(mascota_id)
    historial = mascota.historial_clinico
    if not historial:
        historial = HistorialClinico(mascota_id=mascota.id, diagnostico="", tratamiento="")
        db.session.add(historial)
        db.session.commit()
    return jsonify(historial.to_dict_completo()), 200

@app.route('/api/admin/historial/<int:historial_id>', methods=['PUT'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def update_historial(historial_id):
    historial = HistorialClinico.query.get_or_404(historial_id)
    data = request.json
    try:
        historial.diagnostico = data.get('diagnostico', historial.diagnostico)
        historial.tratamiento = data.get('tratamiento', historial.tratamiento)
        db.session.commit()
        return jsonify(msg="Historial actualizado"), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al actualizar historial: {str(e)}"), 500

@app.route('/api/admin/historial/<int:historial_id>/vacuna', methods=['POST'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def add_vacuna(historial_id):
    historial = HistorialClinico.query.get_or_404(historial_id)
    data = request.json
    try:
        fecha_app = datetime.fromisoformat(data.get('fecha_aplicacion')).date()
        fecha_prox = None
        if data.get('fecha_proxima'):
            fecha_prox = datetime.fromisoformat(data.get('fecha_proxima')).date()

        nueva_vacuna = Vacuna(
            nombre=data.get('nombre'),
            fecha_aplicacion=fecha_app,
            fecha_proxima=fecha_prox,
            historial_id=historial.id
        )
        db.session.add(nueva_vacuna)
        db.session.commit()
        return jsonify(nueva_vacuna.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al añadir vacuna: {str(e)}"), 500

@app.route('/api/admin/vacuna/<int:vacuna_id>', methods=['DELETE'])
@jwt_required()
@role_required(roles=['admin', 'veterinario'])
def delete_vacuna(vacuna_id):
    vacuna = Vacuna.query.get_or_404(vacuna_id)
    try:
        db.session.delete(vacuna)
        db.session.commit()
        return jsonify(msg="Vacuna eliminada"), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Error al eliminar vacuna: {str(e)}"), 500

# ===============================================
# --- FIN DE RUTAS DE ADMIN ---
# ===============================================


# --- Seeding de la Base de Datos ---
def seed_database():
    print("Iniciando seeding de la base de datos...")
    
    if not Usuario.query.filter_by(correo='admin@magnus.pet').first():
        print("Creando usuario Admin...")
        admin_user = Usuario(correo='admin@magnus.pet', rol='admin')
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
    
    if not Veterinario.query.first():
        print("Creando usuarios Veterinarios...")
        try:
            user_vet1 = Usuario(correo="dr.canino@magnus.pet", rol="veterinario")
            user_vet1.set_password("vet123")
            db.session.add(user_vet1)
            db.session.flush()
            vet1 = Veterinario(nombre="Dr. Canino", especialidad="Medicina General", usuario_id=user_vet1.id)
            db.session.add(vet1)
            
            user_vet2 = Usuario(correo="dra.felina@magnus.pet", rol="veterinario")
            user_vet2.set_password("vet123")
            db.session.add(user_vet2)
            db.session.flush()
            vet2 = Veterinario(nombre="Dra. Felina", especialidad="Cirugía", usuario_id=user_vet2.id)
            db.session.add(vet2)
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error creando veterinarios: {e}")

    if not Producto.query.first():
        print("Poblando productos de ejemplo...")
        productos_ejemplo = [{"nombre": "Dog Chow 20kg", "descripcion": "Alimento completo para perro adulto.", "precio": 85000, "stock": 50, "img": "https://images.unsplash.com/photo-1587300003388-59208cc962cb?ixlib-rb-4.0.3&auto=format=fit=crop&w=400&q=80"},]
        for i in range(100):
            tipo = "Alimento" if i % 3 == 0 else "Juguete" if i % 3 == 1 else "Accesorio"
            animal = "Perro" if i % 2 == 0 else "Gato"
            precio = 10000 + (i * 1500)
            productos_ejemplo.append({"nombre": f"{tipo} Genérico {animal} #{i+1}", "descripcion": f"Descripción genérica para {tipo} de {animal}.", "precio": precio, "stock": 50, "img": f"https://picsum.photos/400/400?random={i}"})
        for prod in productos_ejemplo:
            db.session.add(Producto(nombre=prod['nombre'], descripcion=prod['descripcion'], precio=prod['precio'], cantidad_stock=prod['stock'], imagen_url=prod['img']))
        db.session.commit()
        print("¡Productos de ejemplo cargados!")
    
    print("Seeding finalizado.")

# --- Comandos CLI de Flask ---
def register_commands(app):
    @app.cli.command('init-db')
    def init_db_command():
        """Crea las tablas de la base de datos."""
        with app.app_context():
            db.create_all()
        print('Base de datos inicializada.')

    @app.cli.command('seed-db')
    def seed_db_command():
        """Puebla la base de datos con datos iniciales (admin, vets, productos)."""
        with app.app_context():
            seed_database()
        print('Base de datos poblada (seeded).')

# Registrar los comandos
register_commands(app)

# --- Inicializador de la App ---
if __name__ == '__main__':
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_path = os.path.join(basedir, 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
            
    app.run(debug=True, port=5000)