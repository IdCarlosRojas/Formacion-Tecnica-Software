from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)

# Configuración de la base de datos
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'digitalfood.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'clave_secreta_digitalfood_2025'

db = SQLAlchemy(app)

# --- MAPA DE CATEGORÍAS ---
CATEGORIAS_DISPLAY = {
    'entradas': '🍤 Entradas',
    'platos_fuertes': '🍖 Platos Fuertes',
    'bebidas': '🥤 Bebidas',
    'postres': '🍰 Postres'
}

# MODELOS 
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    rol = db.Column(db.String(20), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    precio = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    stock = db.Column(db.Integer, default=0)
    estado = db.Column(db.String(20), default='disponible')

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mesa = db.Column(db.String(10), nullable=False)
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, en_preparacion, listo, completado
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float, default=0.0)
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    usuario = db.relationship('User', backref='pedidos')
    detalles = db.relationship('DetallePedido', backref='pedido', cascade='all, delete-orphan')

class DetallePedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'))
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'))
    cantidad = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    
    producto = db.relationship('Producto', backref='detalles_pedido')

# RUTAS DE AUTENTICACIÓN
@app.route('/')
def index():
    if 'user_id' in session:
        if session['rol'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session['rol'] == 'mesero':
            return redirect(url_for('mesero_dashboard'))
        elif session['rol'] == 'cocinero':
            return redirect(url_for('cocinero_dashboard'))
    
    # Asumimos que tienes un 'index.html' o 'landing_page.html'
    # Si la página de inicio se llama diferente, cambia 'index.html' aquí
    return render_template('index.html') 

@app.route('/login', methods=['GET', 'POST'])
def login():
    
    if request.method == 'POST':
        password = request.form['password']
        user = User.query.filter_by(username='admin').first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['rol'] = user.rol
            session['nombre'] = user.nombre
            flash('Inicio de sesión de administrador exitoso.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Contraseña de administrador incorrecta.', 'danger')
            return render_template('login.html')

    rol_solicitado = request.args.get('rol')
    if rol_solicitado == 'mesero':
        user = User.query.filter_by(username='mesero').first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['rol'] = user.rol
            session['nombre'] = user.nombre
            flash(f'Inicio de sesión como {user.nombre} exitoso.', 'success')
            return redirect(url_for('mesero_dashboard'))
        else:
            flash('Error: El usuario por defecto "mesero" no existe.', 'danger')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('index'))

# DASHBOARDS
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'rol' not in session or session['rol'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    total_pedidos = Pedido.query.count()
    pedidos_pendientes = Pedido.query.filter_by(estado='pendiente').count()
    total_productos = Producto.query.count()
    
    return render_template('admin_dashboard.html', 
                         total_pedidos=total_pedidos,
                         pedidos_pendientes=pedidos_pendientes,
                         total_productos=total_productos)

@app.route('/mesero/dashboard')
def mesero_dashboard():
    if 'rol' not in session or session['rol'] != 'mesero':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    productos_agrupados = []
    for cat_key, cat_display in CATEGORIAS_DISPLAY.items():
        productos = Producto.query.filter(
            Producto.stock > 0, 
            Producto.estado == 'disponible',
            Producto.categoria == cat_key
        ).all()
        if productos:
            productos_agrupados.append({'nombre': cat_display, 'productos': productos})

    pedidos_activos = Pedido.query.filter(
        Pedido.estado.in_(['pendiente', 'en_preparacion', 'listo'])
    ).all()
    
    return render_template('mesero_dashboard.html', 
                         productos_agrupados=productos_agrupados,
                         pedidos_activos=pedidos_activos)

@app.route('/cocinero/dashboard')
def cocinero_dashboard():
    if 'rol' not in session or session['rol'] != 'cocinero':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    pedidos_pendientes = Pedido.query.filter_by(estado='pendiente').all()
    pedidos_preparacion = Pedido.query.filter_by(estado='en_preparacion').all()
    
    return render_template('cocinero_dashboard.html',
                         pedidos_pendientes=pedidos_pendientes,
                         pedidos_preparacion=pedidos_preparacion)

# ===============================
# ===== SECCIÓN ADMIN (CRUDs) =====
# ===============================

# ===== CRUD PRODUCTOS (Admin) =====
@app.route('/admin/productos')
def listar_productos():
    if 'rol' not in session or session['rol'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    productos = Producto.query.all()
    return render_template('productos.html', productos=productos)

@app.route('/admin/productos/crear', methods=['GET', 'POST'])
def crear_producto():
    if 'rol' not in session or session['rol'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            nuevo_producto = Producto(
                nombre=request.form['nombre'],
                descripcion=request.form['descripcion'],
                precio=float(request.form['precio']),
                categoria=request.form['categoria'],
                stock=int(request.form['stock']),
                estado=request.form.get('estado', 'disponible')
            )
            db.session.add(nuevo_producto)
            db.session.commit()
            flash('Producto creado con éxito.', 'success')
            return redirect(url_for('listar_productos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el producto: {str(e)}', 'danger')
    return render_template('crear_producto.html')

@app.route('/admin/productos/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    if 'rol' not in session or session['rol'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    producto = Producto.query.get_or_404(id)
    if request.method == 'POST':
        try:
            producto.nombre = request.form['nombre']
            producto.descripcion = request.form['descripcion']
            producto.precio = float(request.form['precio'])
            producto.categoria = request.form['categoria']
            producto.stock = int(request.form['stock'])
            producto.estado = request.form['estado']
            db.session.commit()
            flash('Producto actualizado con éxito.', 'success')
            return redirect(url_for('listar_productos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el producto: {str(e)}', 'danger')
    return render_template('editar_producto.html', producto=producto)

@app.route('/admin/productos/eliminar/<int:id>', methods=['POST'])
def eliminar_producto(id):
    if 'rol' not in session or session['rol'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    try:
        producto = Producto.query.get_or_404(id)
        db.session.delete(producto)
        db.session.commit()
        flash(f'Producto "{producto.nombre}" eliminado con éxito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el producto: {str(e)}. (Es posible que esté asociado a un pedido existente)', 'danger')
    return redirect(url_for('listar_productos'))

# ===== CRUD USUARIOS (Admin) =====
@app.route('/admin/usuarios')
def listar_usuarios():
    if 'rol' not in session or session['rol'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    usuarios = User.query.all()
    return render_template('usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/crear', methods=['GET', 'POST'])
def crear_usuario():
    if 'rol' not in session or session['rol'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            nombre = request.form['nombre']
            username = request.form['username']
            password = request.form['password']
            rol = request.form['rol']
            if User.query.filter_by(username=username).first():
                flash('El nombre de usuario ya existe.', 'danger')
                return render_template('crear_usuario.html')
            nuevo_usuario = User(nombre=nombre, username=username, rol=rol)
            nuevo_usuario.set_password(password)
            db.session.add(nuevo_usuario)
            db.session.commit()
            flash('Usuario creado con éxito.', 'success')
            return redirect(url_for('listar_usuarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el usuario: {str(e)}', 'danger')
    return render_template('crear_usuario.html')

@app.route('/admin/usuarios/editar/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    if 'rol' not in session or session['rol'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    usuario = User.query.get_or_404(id)
    if request.method == 'POST':
        try:
            usuario.nombre = request.form['nombre']
            usuario.username = request.form['username']
            if usuario.id != 1:
                usuario.rol = request.form['rol']
            password = request.form['password']
            if password:
                usuario.set_password(password)
            db.session.commit()
            flash('Usuario actualizado con éxito.', 'success')
            return redirect(url_for('listar_usuarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el usuario: {str(e)}', 'danger')
    return render_template('editar_usuario.html', usuario=usuario)

@app.route('/admin/usuarios/eliminar/<int:id>', methods=['POST'])
def eliminar_usuario(id):
    if 'rol' not in session or session['rol'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    usuario = User.query.get_or_404(id)
    if usuario.id == 1 or usuario.username == 'admin':
        flash('No se puede eliminar al administrador principal.', 'danger')
        return redirect(url_for('listar_usuarios'))
    try:
        db.session.delete(usuario)
        db.session.commit()
        flash(f'Usuario "{usuario.nombre}" eliminado con éxito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el usuario: {str(e)}', 'danger')
    return redirect(url_for('listar_usuarios'))

@app.route('/admin/pedidos')
def listar_pedidos():
    if 'rol' not in session or session['rol'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    pedidos = Pedido.query.all()
    return render_template('pedidos.html', pedidos=pedidos)
    
# ===== REPORTES (Admin) =====
@app.route('/admin/reportes')
def ver_reportes():
    if 'rol' not in session or session['rol'] != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    total_ventas = db.session.query(db.func.sum(Pedido.total)).filter(Pedido.estado == 'completado').scalar() or 0.0
    pedidos_completados = Pedido.query.filter_by(estado='completado').count()
    
    return render_template('reportes.html',
                         total_ventas=total_ventas,
                         pedidos_completados=pedidos_completados,
                         total_pedidos=Pedido.query.count())
# ==================================

# GESTIÓN DE PEDIDOS (Mesero y Cocinero)

@app.route('/pedido/<int:id>/completar', methods=['POST'])
def marcar_pedido_completado(id):
    if 'rol' not in session or session['rol'] not in ['admin', 'mesero']:
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
        
    pedido = Pedido.query.get_or_404(id)
    
    try:
        pedido.estado = 'completado'
        db.session.commit()
        flash(f'Pedido de la Mesa {pedido.mesa} marcado como completado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al completar el pedido: {str(e)}', 'danger')

    if session['rol'] == 'admin':
        return redirect(url_for('listar_pedidos'))
    else:
        return redirect(url_for('mesero_dashboard'))

@app.route('/mesero/nuevo-pedido', methods=['GET', 'POST'])
def nuevo_pedido():
    if 'rol' not in session or session['rol'] != 'mesero':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            nuevo_pedido = Pedido(
                mesa=request.form['mesa'],
                usuario_id=session['user_id'],
                total=0.0
            )
            db.session.add(nuevo_pedido)
            db.session.flush()
            
            total_pedido = 0
            productos_ids = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            
            for i, producto_id in enumerate(productos_ids):
                if cantidades[i] and int(cantidades[i]) > 0:
                    producto = Producto.query.get(int(producto_id))
                    cantidad = int(cantidades[i])
                    
                    if producto.stock < cantidad:
                         flash(f'Error: Stock insuficiente para {producto.nombre}. Solo quedan {producto.stock}.', 'danger')
                         raise Exception("Stock insuficiente")
                    
                    producto.stock -= cantidad

                    subtotal = producto.precio * cantidad
                    
                    detalle = DetallePedido(
                        pedido_id=nuevo_pedido.id,
                        producto_id=producto.id,
                        cantidad=cantidad,
                        subtotal=subtotal
                    )
                    db.session.add(detalle)
                    total_pedido += subtotal
            
            if total_pedido == 0:
                db.session.rollback()
                flash('No se puede crear un pedido sin productos.', 'danger')
                return redirect(url_for('nuevo_pedido'))

            nuevo_pedido.total = total_pedido
            db.session.commit()
            flash('Pedido creado con éxito y enviado a cocina.', 'success')
            return redirect(url_for('mesero_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            if "Stock insuficiente" not in str(e):
                flash(f'Error al crear el pedido: {str(e)}', 'danger')
            return redirect(url_for('nuevo_pedido'))
    
    productos_agrupados = []
    for cat_key, cat_display in CATEGORIAS_DISPLAY.items():
        productos = Producto.query.filter(
            Producto.stock > 0, 
            Producto.estado == 'disponible',
            Producto.categoria == cat_key
        ).all()
        if productos:
            productos_agrupados.append({'nombre': cat_display, 'productos': productos})

    return render_template('nuevo_pedido.html', 
                         productos_agrupados=productos_agrupados)

@app.route('/cocinero/pedido/<int:id>/estado', methods=['POST'])
def cambiar_estado_pedido(id):
    if 'rol' not in session or session['rol'] != 'cocinero':
        flash('No autorizado', 'danger')
        return redirect(url_for('login'))
    
    pedido = Pedido.query.get_or_404(id)
    nuevo_estado = request.form.get('estado')
    
    if nuevo_estado in ['en_preparacion', 'listo']:
        pedido.estado = nuevo_estado
        db.session.commit()
        flash(f'Pedido mesa {pedido.mesa} marcado como {nuevo_estado}', 'success')
    
    return redirect(url_for('cocinero_dashboard'))

# ===== ¡SECCIÓN DE DATOS DE EJEMPLO ACTUALIZADA! =====
def crear_datos_ejemplo():
    # Menú extraído del PDF "Menú indu.pdf"
    productos_ejemplo = [
        # === ENTRADAS ===
        {'nombre': 'Steak Bites', 'descripcion': 'Trozos de lomo de res termino medio sobre salsa teriyaki y tomates rostizados.', 'precio': 25500, 'categoria': 'entradas', 'stock': 20},
        {'nombre': 'Tofu Nachos', 'descripcion': 'Tortillas de trigo fritas, cebollas encurtidas, jalapeños, guacamole, sour cream y tofu.', 'precio': 20600, 'categoria': 'entradas', 'stock': 20},
        {'nombre': 'Hummus Artesanal', 'descripcion': 'Puré de garbanzo rustico con especias y pan masa madre.', 'precio': 11500, 'categoria': 'entradas', 'stock': 20},
        {'nombre': 'Ceviche de Pescado', 'descripcion': 'Trozos de pescado marinados en limón y naranja, cebolla ocañera y pan masa madre.', 'precio': 23000, 'categoria': 'entradas', 'stock': 20},
        {'nombre': 'Tataki de Atún', 'descripcion': 'Finas laminas de atún fresco sellado, encostrado en ajonjolí con wasabi y salsa soya.', 'precio': 34300, 'categoria': 'entradas', 'stock': 20},
        {'nombre': 'Crema de Tomate Rostizados', 'descripcion': 'Gratinado con queso fresco y acompañado de pan masa madre.', 'precio': 14000, 'categoria': 'entradas', 'stock': 20},
        {'nombre': 'Sopa Mulligatawny', 'descripcion': 'Sopa anglo india con vegetales frescos, lenteja y curry especiado.', 'precio': 18000, 'categoria': 'entradas', 'stock': 20}, # Precio inferido

        # === PLATOS FUERTES (Clásicos, Indú, Ensaladas, Vegetarianos, Paleo, Keto) ===
        {'nombre': 'Cordero Tikka Masala', 'descripcion': 'Pierna de cordero marinados en yogurt y especias, cocinados en salsa de tomates, jengibre y garam masala.', 'precio': 22000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Palak Paneer (Tofu)', 'descripcion': 'Cubos de tofu guisados en crema aterciopelada de espinacas y especias suaves.', 'precio': 25000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Murgh Makhani (Pollo)', 'descripcion': 'Pollo marinado tandoori, estofado en salsa cremosa de tomate, mantequilla y especias.', 'precio': 19000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Ensalada Argentina', 'descripcion': 'Lomo de res parrillado sobre lechugas mixtas, chorizo, queso, aceitunas y chimichurri.', 'precio': 32000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Salmon Enchilado Salad', 'descripcion': 'Salmón parrillado con cayena, sobre lechugas mixtas, frutos secos, jalapeños y quinoa.', 'precio': 38500, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Teriyaki Pollo', 'descripcion': 'Salsa teriyaki y vegetales al wok con arroz blanco y ensalada.', 'precio': 24000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Teriyaki Lomo de Res', 'descripcion': 'Salsa teriyaki y vegetales al wok con arroz blanco y ensalada.', 'precio': 32000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Teriyaki Tofu', 'descripcion': 'Salsa teriyaki y vegetales al wok con arroz blanco y ensalada.', 'precio': 24000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'The Baby Beef', 'descripcion': '200gr de Baby Beef parrillada con sal del Himalaya, espuma de pimienta rosada y bastones de camote.', 'precio': 38000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Arroz Mediterraneo Pot', 'descripcion': 'Arroz estofado con camarones, calamares, mejillones y tilapia a la plancha.', 'precio': 48000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Thai Buddha Pot (Res)', 'descripcion': 'Tallarines de arroz salteado al wok con vegetales, raíces chinas y salsa tonkatsu.', 'precio': 35000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Thai Buddha Pot (Pollo)', 'descripcion': 'Tallarines de arroz salteado al wok con vegetales, raíces chinas y salsa tonkatsu.', 'precio': 23000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Fettuccine Espinaca Rose', 'descripcion': 'Pasta artesanal con vegetales, salsa cremosa de tomates, aceitunas y queso semimaduro.', 'precio': 32000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Tropical Pork Ribs', 'descripcion': '250gr de Costilla de cerdo horneada con gel de corozo agridulce, sobre puré de papa rústico.', 'precio': 30600, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Sopa Miso (Vegetariana)', 'descripcion': 'Clásica sopa vegetariana con tallarines, vegetales frescos, hongos de temporada y tofu.', 'precio': 26000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Veggie Pot', 'descripcion': 'Arroz frito al wok con quinoa, vegetales frescos, brócoli, maíz tostado, semillas y tofu.', 'precio': 22000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Raviolis di Zucca', 'descripcion': 'Rellenos de ahuyama, bañados en salsa Lemon beurre blanc y pan artesanal.', 'precio': 26000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Cazuela de Garbanzos', 'descripcion': 'Estofado de garbanzos en salsa curry, papas, seitan frito, aguacate y arroz integral.', 'precio': 28000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Ternera a la Miel (Paleo)', 'descripcion': 'Filete de ternera rostizada y glaseada con miel, arroz paleo, espinacas y guacamole.', 'precio': 27000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Bowl de Pollo y Semillas (Paleo)', 'descripcion': 'Pollo salteado al wok con vegetales frescos, frutos secos, semillas y ensalada.', 'precio': 28000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Cheddar Chicken (Keto)', 'descripcion': 'Pechuga de pollo con piel asada en salsa de queso cheddar y tocineta, con guatila.', 'precio': 28000, 'categoria': 'platos_fuertes', 'stock': 15},
        {'nombre': 'Tilapia al Ghee (Keto)', 'descripcion': 'Filete de tilapia parrillada bañada con mantequilla ghee, espinacas, aguacate y huevo.', 'precio': 44000, 'categoria': 'platos_fuertes', 'stock': 15},

        # === BEBIDAS (Inferidas y del menú anterior) ===
        {'nombre': 'Pisco Sour', 'descripcion': 'Coctel tradicional peruano.', 'precio': 15000, 'categoria': 'bebidas', 'stock': 30},
        {'nombre': 'Jugo Natural (Agua)', 'descripcion': 'Jugo de fruta fresca de temporada en agua.', 'precio': 8000, 'categoria': 'bebidas', 'stock': 30},
        {'nombre': 'Jugo Natural (Leche)', 'descripcion': 'Jugo de fruta fresca de temporada en leche.', 'precio': 9000, 'categoria': 'bebidas', 'stock': 30},
        {'nombre': 'Limonada Natural', 'descripcion': 'Limonada fresca hecha en casa.', 'precio': 7000, 'categoria': 'bebidas', 'stock': 30},
        {'nombre': 'Gaseosa (Personal)', 'descripcion': 'Bebida carbonatada personal (Coca-Cola, Sprite, etc.).', 'precio': 5000, 'categoria': 'bebidas', 'stock': 30},
        {'nombre': 'Aromática', 'descripcion': 'Infusión de hierbas frescas.', 'precio': 6000, 'categoria': 'bebidas', 'stock': 30},
        {'nombre': 'Panelada', 'descripcion': 'Bebida de panela tradicional fría.', 'precio': 6000, 'categoria': 'bebidas', 'stock': 30},

        # === POSTRES (Inferidos y del menú anterior) ===
        {'nombre': 'Suspiro Limeño', 'descripcion': 'Postre tradicional de manjarblanco y merengue.', 'precio': 12000, 'categoria': 'postres', 'stock': 10},
        {'nombre': 'Torta de Chocolate', 'descripcion': 'Porción de torta de chocolate húmeda con fudge.', 'precio': 14000, 'categoria': 'postres', 'stock': 10},
        {'nombre': 'Cheesecake de Frutos Rojos', 'descripcion': 'Cremoso cheesecake con salsa de frutos rojos.', 'precio': 15000, 'categoria': 'postres', 'stock': 10},
    ]
    
    for prod_data in productos_ejemplo:
        if not Producto.query.filter_by(nombre=prod_data['nombre']).first():
            producto = Producto(**prod_data)
            db.session.add(producto)
    
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        usuarios_default = [
            {'username': 'admin', 'rol': 'admin', 'nombre': 'Administrador Principal'},
            {'username': 'mesero', 'rol': 'mesero', 'nombre': 'Mesero Ejemplo'},
            {'username': 'cocinero', 'rol': 'cocinero', 'nombre': 'Chef Ejemplo'}
        ]
        
        for user_data in usuarios_default:
            if not User.query.filter_by(username=user_data['username']).first():
                usuario = User(**user_data)
                usuario.set_password(user_data['username'] + '123')
                db.session.add(usuario)
        
        db.session.commit()
        
        # Llama a la función para poblar con el menú profesional
        crear_datos_ejemplo() 
        
        print("✅ Base de datos inicializada con datos de ejemplo")
        print("👤 Usuarios creados: admin, mesero, cocinero (Pass: [user]123)")
        print("🍽️ Menú profesional cargado en la base de datos.")
    
    app.run(debug=True, host='0.0.0.0', port=5000)