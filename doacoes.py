import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from datetime import datetime

# Importa o banco e as tabelas
from modelos import db, Item

# Importa as funções auxiliares
from auxiliares import salvar_imagem, limpar_itens_vencidos

# Cria o Blueprint do módulo de doações
doacoes_bp = Blueprint('doacoes', __name__)


@doacoes_bp.route('/doar', methods=['GET', 'POST'], endpoint='doar')
@doacoes_bp.route('/cadastrar_doacao', methods=['GET', 'POST'], endpoint='cadastrar_doacao')
@login_required
def doar():
    # Verifica estritamente se o usuário logado é do tipo 'mercado'
    tipo_usuario = getattr(current_user, 'tipo', '')
    if tipo_usuario != 'mercado':
        flash('Apenas estabelecimentos doadores (tipo mercado) podem cadastrar novos itens.', 'info')
        return redirect(url_for('index'))

    if request.method == 'POST':
        nome = request.form.get('nome')
        try:
            qtd = int(request.form.get('qtd', 1))
        except ValueError:
            qtd = 1

        categoria = request.form.get('categoria')
        unidade = request.form.get('unidade', 'unidade')
        validade = request.form.get('validade')
        cidade = request.form.get('cidade')
        bairro = request.form.get('bairro')
        rua_numero = request.form.get('rua_numero')
        contato = request.form.get('contato', getattr(current_user, 'telefone', ''))

        imagem_filename = 'sem-foto.png'
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and file.filename != '':
                imagem_filename = salvar_imagem(file)

        novo_item = Item(
            nome=nome,
            qtd=qtd,
            categoria=categoria,
            unidade=unidade,
            validade=validade,
            cidade=cidade,
            bairro=bairro,
            rua_numero=rua_numero,
            contato=contato,
            imagem=imagem_filename,
            usuario_id=current_user.id
        )

        db.session.add(novo_item)
        db.session.commit()

        flash('Item cadastrado com sucesso no estoque!', 'success')
        return redirect(url_for('doacoes.minhas_doacoes'))

    # Verifica se o utilizador passou a categoria na URL (ex: ?categoria=Alimento)
    categoria = request.args.get('categoria')

    # Se NÃO passou a categoria, mostra a tela de escolha com os cartões
    if not categoria:
        return render_template('escolher_categoria.html')

    # Se PASSOU a categoria, abre o formulário de preenchimento
    return render_template('portal_doar.html', item=None)


@doacoes_bp.route('/receber', endpoint='portal_receber')
@doacoes_bp.route('/doacoes', endpoint='listar_doacoes')
@login_required
def listar_doacoes():
    """Exibe o portal de doações usando o template portal_receber.html ocultando itens vencidos."""
    
    # Impede estritamente que estabelecimentos doadores (mercados) acessem o portal de recebimento
    tipo_usuario = getattr(current_user, 'tipo', '')
    if tipo_usuario == 'mercado':
        flash('Acesso restrito. Estabelecimentos doadores não podem solicitar suprimentos.', 'info')
        return redirect(url_for('index'))

    limpar_itens_vencidos()

    hoje = datetime.now().date()
    hoje_str = hoje.strftime('%Y-%m-%d')

    busca = request.args.get('busca', '')

    # Filtra apenas itens válidos (não vencidos) para o portal de recebimento
    query = Item.query.filter(
        (Item.validade >= hoje_str) | 
        (Item.validade == 'Não se aplica') | 
        (Item.validade == None) |
        (Item.categoria != 'Alimento')
    )

    if busca:
        query = query.filter(
            (Item.nome.ilike(f'%{busca}%')) | 
            (Item.cidade.ilike(f'%{busca}%')) |
            (Item.bairro.ilike(f'%{busca}%'))
        )
    
    itens = query.all()

    # Processa datas e dias restantes para o portal_receber funcionar redondo
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

    return render_template('portal_receber.html', itens=itens)


@doacoes_bp.route('/minhas_doacoes', endpoint='meus_itens')
@doacoes_bp.route('/meus_itens', endpoint='minhas_doacoes')
@login_required
def minhas_doacoes():
    """Exibe a lista de itens do doador usando o template meus_itens.html."""
    if getattr(current_user, 'tipo', '') != 'mercado':
        flash('Acesso restrito a estabelecimentos doadores.', 'info')
        return redirect(url_for('index'))

    limpar_itens_vencidos()
    itens = Item.query.filter_by(usuario_id=current_user.id).all()
    
    return render_template('meus_itens.html', itens=itens)


@doacoes_bp.route('/editar/<int:item_id>', methods=['GET', 'POST'], endpoint='editar')
@doacoes_bp.route('/editar_doacao/<int:item_id>', methods=['GET', 'POST'], endpoint='editar_doacao')
@login_required
def editar(item_id):
    item = Item.query.get_or_404(item_id)

    if item.usuario_id != current_user.id:
        flash('Você não tem permissão para editar este item.', 'danger')
        return redirect(url_for('doacoes.minhas_doacoes'))

    if request.method == 'POST':
        item.nome = request.form.get('nome')
        try:
            item.qtd = int(request.form.get('qtd', item.qtd))
        except ValueError:
            pass

        item.categoria = request.form.get('categoria')
        item.unidade = request.form.get('unidade')
        item.validade = request.form.get('validade')
        item.cidade = request.form.get('cidade')
        item.bairro = request.form.get('bairro')
        item.rua_numero = request.form.get('rua_numero')
        item.contato = request.form.get('contato')

        if 'imagem' in request.files and request.files['imagem'].filename != '':
            if item.imagem and item.imagem != 'sem-foto.png':
                caminho_antigo = os.path.join(current_app.config['UPLOAD_FOLDER'], item.imagem)
                if os.path.exists(caminho_antigo):
                    try:
                        os.remove(caminho_antigo)
                    except OSError:
                        pass

            item.imagem = salvar_imagem(request.files['imagem'])

        db.session.commit()
        flash('Item atualizado com sucesso!', 'success')
        return redirect(url_for('doacoes.minhas_doacoes'))

    return render_template('portal_doar.html', item=item)


@doacoes_bp.route('/excluir/<int:item_id>', methods=['POST'], endpoint='excluir')
@doacoes_bp.route('/deletar_doacao/<int:item_id>', methods=['POST'], endpoint='deletar_doacao')
@doacoes_bp.route('/deletar/<int:item_id>', methods=['POST'], endpoint='deletar')
@login_required
def excluir(item_id):
    item = Item.query.get_or_404(item_id)

    if item.usuario_id != current_user.id:
        flash('Você não tem permissão para excluir este item.', 'danger')
        return redirect(url_for('doacoes.minhas_doacoes'))

    if item.imagem and item.imagem != 'sem-foto.png':
        caminho_imagem = os.path.join(current_app.config['UPLOAD_FOLDER'], item.imagem)
        if os.path.exists(caminho_imagem):
            try:
                os.remove(caminho_imagem)
            except OSError:
                pass

    db.session.delete(item)
    db.session.commit()

    flash('Item removido com sucesso!', 'success')
    return redirect(url_for('doacoes.minhas_doacoes'))