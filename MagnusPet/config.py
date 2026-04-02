# config.py
import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = 'una-clave-secreta-muy-fuerte-aqui' # ¡Cámbiala!
    
    # Asegúrate de que la carpeta 'instance' exista
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'instance', 'magnus_pet.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuración de JWT
    JWT_SECRET_KEY = 'una-clave-jwt-tambien-muy-fuerte' # ¡Cámbiala!