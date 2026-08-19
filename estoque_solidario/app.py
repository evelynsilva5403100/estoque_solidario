import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from modelos import db, login_manager, Item, Usuario, Pedido
from auxiliares import limpar_itens_vencidos

# Importa os Blueprints
from routes.auth import auth_bp
from routes.doacoes import doacoes_bp
from routes.pedidos import pedidos_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui' #protege a sessão dos usuários contra a adulteração

# Configuração do Banco de Dados SQLite: defini onde o arquivo banco.db é criado
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'banco.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Pasta para upload(para armazenar fotos dos produtos/itens,tradando possíveis conflitos) de imagens (Com tratamento seguro para evitar conflitos no Windows)
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
upload_folder = app.config['UPLOAD_FOLDER']
if not os.path.exists(upload_folder):
    os.makedirs(upload_folder)
elif not os.path.isdir(upload_folder):
    os.remove(upload_folder)
    os.makedirs(upload_folder)

# Inicializa as extensões(do banco de dados(SQLAlchemy) e do flask(Flask-login))
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'

# Registra os Blueprints (Adicionado url_prefix para o blueprint de pedidos)
app.register_blueprint(auth_bp)
app.register_blueprint(doacoes_bp)
app.register_blueprint(pedidos_bp, url_prefix='/pedidos')

# Garante que as tabelas(que definimos em modelos.py) sejam criadas ao iniciar
with app.app_context():
    db.create_all()

# Context processor(Varáveis globais para os templates)
@app.context_processor
def inject_globals():
    total_pedidos = 0
    if current_user.is_authenticated and getattr(current_user, 'tipo', '') == 'mercado':
        total_pedidos = Pedido.query.filter_by(doador_id=current_user.id, status='Aguardando Retirada').count()

    def dias_restantes(data_validade):
        if not data_validade or data_validade == 'Não se aplica':
            return 999
        try:
            validade = datetime.strptime(data_validade, '%Y-%m-%d').date()
            hoje = datetime.now().date()
            return (validade - hoje).days
        except Exception:
            return 999

    return dict(
        contagem_novos_pedidos=total_pedidos,
        dias_restantes=dias_restantes
    )

# Rotas principais
@app.route('/', endpoint='index')
@app.route('/home', endpoint='home')
def index():
    # Executa a limpeza automática dos itens vencidos
    limpar_itens_vencidos()

    hoje = datetime.now().date()
    hoje_str = hoje.strftime('%Y-%m-%d')

    busca = request.args.get('busca', '')

    # Filtra apenas itens que NÃO estão vencidos
    query = Item.query.filter(
        (Item.validade >= hoje_str) | 
        (Item.validade == 'Não se aplica') | 
        (Item.validade == None) |
        (Item.categoria != 'Alimento')
    )

    if busca:
        query = query.filter(
            (Item.nome.ilike(f'%{busca}%')) | 
            (Item.cidade.ilike(f'%{busca}%'))
        )
    
    itens = query.all()

    # Processa as datas e dias restantes para cada item de forma dinâmica
    for item in itens:
        if item.validade and item.validade != 'Não se aplica':
            try:
                if isinstance(item.validade, str):
                    data_val = datetime.strptime(item.validade, '%Y-%m-%d').date()
                else:
                    data_val = item.validade
                
                item.dias_restantes = (data_val - hoje).days
                item.validade_formatada = data_val.strftime('%d/%m/%Y')
            except Exception:
                item.dias_restantes = 999
                item.validade_formatada = item.validade
        else:
            item.dias_restantes = 999
            item.validade_formatada = None

    # Calcula os pedidos pendentes ou aguardando retirada do mercado logado para o menu
    contagem_novos_pedidos = 0
    if current_user.is_authenticated and getattr(current_user, 'tipo', '') == 'mercado':
        contagem_novos_pedidos = Pedido.query.join(Item).filter(
            Item.usuario_id == current_user.id,
            Pedido.status.in_(['Pendente', 'Aguardando Retirada'])
        ).count()

    return render_template('index.html', itens=itens, contagem_novos_pedidos=contagem_novos_pedidos)

@app.route('/sobre')
def sobre():
    return render_template('sobre.html')

@app.route('/perfil')
@login_required
def perfil():
    return render_template('perfil.html')

@app.route('/atualizar_dados', methods=['POST'])
@login_required
def atualizar_dados():
    current_user.nome = request.form.get('nome_real') or current_user.nome
    current_user.telefone = request.form.get('telefone') or current_user.telefone
    current_user.cidade = request.form.get('cidade') or current_user.cidade
    current_user.bairro = request.form.get('bairro') or current_user.bairro

    db.session.commit()
    flash('Dados atualizados com sucesso!', 'success')
    return redirect(url_for('perfil'))

if __name__ == '__main__':
    app.run(debug=True)
