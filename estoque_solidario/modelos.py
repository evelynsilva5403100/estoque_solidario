from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

# TABELA DE USUÁRIOS
class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=True)
    username = db.Column(db.String(50), unique=True, nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    senha = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), default='ong')
    telefone = db.Column(db.String(20), nullable=True)
    cidade = db.Column(db.String(50), nullable=True)
    bairro = db.Column(db.String(50), nullable=True)

    @property
    def nome_real(self):
        return self.nome if self.nome else (self.username or self.email)

# TABELA DE ITENS (DOAÇÕES) 
class Item(db.Model):
    __tablename__ = 'item'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    categoria = db.Column(db.String(50), nullable=True)
    qtd = db.Column(db.Integer, default=1)
    unidade = db.Column(db.String(20), default='unidade')
    validade = db.Column(db.String(20), nullable=True)
    imagem = db.Column(db.String(200), default='sem-foto.png')
    contato = db.Column(db.String(20), nullable=True)
    
    cidade = db.Column(db.String(50), nullable=True)
    bairro = db.Column(db.String(50), nullable=True)
    rua_numero = db.Column(db.String(150), nullable=True)
    
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    usuario = db.relationship('Usuario', backref=db.backref('itens', lazy=True))

# TABELA DE PEDIDOS:
class Pedido(db.Model):
    __tablename__ = 'pedido'
    
    id = db.Column(db.Integer, primary_key=True)
    item_nome = db.Column(db.String(100), nullable=False)
    qtd_solicitada = db.Column(db.Integer, nullable=False)
    item_unidade = db.Column(db.String(20), nullable=True)
    item_validade = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(50), default='Aguardando Retirada')
    data_pedido = db.Column(db.DateTime, default=datetime.utcnow)
    data_limite = db.Column(db.DateTime, nullable=True)

    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)
    ong_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    doador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    ong = db.relationship('Usuario', foreign_keys=[ong_id], backref=db.backref('pedidos_solicitados', lazy=True))
    doador = db.relationship('Usuario', foreign_keys=[doador_id], backref=db.backref('pedidos_recebidos', lazy=True))
    item = db.relationship('Item', backref=db.backref('pedidos', lazy=True))