import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
from modelos import db, Item, Pedido

# Extensões de imagem permitidas para upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    """Verifica se o arquivo enviado é uma imagem válida (png, jpg, jpeg)."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def salvar_imagem(file):
    """
    Salva a imagem enviada na pasta de uploads com um nome único.
    Retorna o nome do arquivo salvo ou 'sem-foto.png' em caso de erro/vazio.
    """
    if file and file.filename != '' and allowed_file(file.filename):
        nome_seguro = secure_filename(file.filename)
        # Gera um nome único usando UUID para evitar conflitos de nomes iguais
        extensao = nome_seguro.rsplit('.', 1)[1].lower()
        nome_unico = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{extensao}"
        
        caminho_completo = os.path.join(current_app.config['UPLOAD_FOLDER'], nome_unico)
        file.save(caminho_completo)
        return nome_unico
    
    return 'sem-foto.png'

def dias_restantes(data_validade_str):
    """
    Calcula quantos dias faltam para o vencimento de um item.
    Retorna 999 se não for perecível ou se houver erro de conversão.
    """
    if not data_validade_str or data_validade_str in ['Não se aplica', '']:
        return 999
    try:
        data_validade = datetime.strptime(data_validade_str, "%Y-%m-%d").date()
        hoje = datetime.today().date()
        return (data_validade - hoje).days
    except ValueError:
        return 999

def limpar_itens_vencidos():
    """Remove do banco os alimentos que já passaram da data de validade de forma segura."""
    try:
        hoje = datetime.today().date()
        
        # Filtra apenas itens da categoria Alimento que possuem validade cadastrada
        alimentos = Item.query.filter(
            Item.categoria == 'Alimento',
            Item.validade.isnot(None),
            Item.validade != 'Não se aplica'
        ).all()
        
        deletados = False

        for item in alimentos:
            try:
                data_validade = datetime.strptime(item.validade, "%Y-%m-%d").date()
                if data_validade < hoje:
                    # Desvincula pedidos associados para não quebrar a chave estrangeira
                    pedidos_vinculados = Pedido.query.filter_by(item_id=item.id).all()
                    for p in pedidos_vinculados:
                        p.item_id = None

                    # Se o item tiver imagem cadastrada e não for a padrão, remove do disco
                    if hasattr(item, 'imagem') and item.imagem and item.imagem != 'sem-foto.png':
                        caminho_imagem = os.path.join(current_app.config['UPLOAD_FOLDER'], item.imagem)
                        if os.path.exists(caminho_imagem):
                            try:
                                os.remove(caminho_imagem)
                            except OSError:
                                pass # Ignora se o arquivo já tiver sido removido
                    
                    # Apaga o item do banco de dados
                    db.session.delete(item)
                    deletados = True
            except ValueError:
                continue
                
        if deletados:
            db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"Aviso ao limpar itens vencidos: {e}")