import os
from flask import Blueprint, current_app, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from modelos import db, Usuario, Item, Pedido

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST']) 
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email') or request.form.get('username')
        senha = request.form.get('senha')

        usuario = Usuario.query.filter((Usuario.email == email) | (Usuario.username == email)).first()

        if usuario and check_password_hash(usuario.senha, senha):
            login_user(usuario)
            flash(f'Bem-vindo(a) de volta, {usuario.nome or usuario.username}!', 'success')

            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)

            if usuario.tipo == 'mercado':
                return redirect(url_for('doacoes.minhas_doacoes'))
            else:
                return redirect(url_for('doacoes.listar_doacoes'))
        else:
            flash('Usuário/E-mail ou senha incorretos.', 'danger')

    return render_template('login.html')


@auth_bp.route('/registro', methods=['GET', 'POST'], endpoint='registro')
@auth_bp.route('/cadastrar', methods=['GET', 'POST'], endpoint='cadastrar')
def registro():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        nome = request.form.get('nome') or request.form.get('nome_real')
        email = request.form.get('email')
        username = request.form.get('username') or email
        senha = request.form.get('senha')
        tipo = request.form.get('tipo', 'ong')
        telefone = request.form.get('telefone')
        cidade = request.form.get('cidade')
        bairro = request.form.get('bairro')

        if not email or not senha:
            flash('Preencha os campos obrigatórios (E-mail e Senha).', 'warning')
            return redirect(request.referrer or url_for('auth.registro'))

        usuario_existente = Usuario.query.filter((Usuario.email == email) | (Usuario.username == username)).first()
        if usuario_existente:
            flash('Este e-mail ou nome de usuário já está cadastrado.', 'warning')
            return redirect(request.referrer or url_for('auth.registro'))

        senha_hash = generate_password_hash(senha)
        novo_usuario = Usuario(
            nome=nome,
            username=username,
            email=email,
            senha=senha_hash,
            tipo=tipo,
            telefone=telefone,
            cidade=cidade,
            bairro=bairro
        )

        db.session.add(novo_usuario)
        db.session.commit()

        flash('Conta criada com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('registro.html')


# ==========================================
# FLUXO DE RECUPERAÇÃO DE SENHA POR TELEFONE
# ==========================================

@auth_bp.route('/esqueci-senha', methods=['GET', 'POST'])
def esqueci_senha():
    if request.method == 'POST':
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        
        usuario = Usuario.query.filter_by(email=email, telefone=telefone).first()
        
        if usuario:
            session['usuario_recuperacao_id'] = usuario.id
            flash('Dados confirmados! Digite sua nova senha.', 'success')
            return redirect(url_for('auth.redefinir_sem_token'))
        else:
            flash('E-mail ou telefone incorretos ou não encontrados.', 'danger')
            
    return render_template('esqueci_senha.html')


@auth_bp.route('/redefinir-senha-direto', methods=['GET', 'POST'])
def redefinir_sem_token():
    usuario_id = session.get('usuario_recuperacao_id')
    
    if not usuario_id:
        flash('Sessão expirada ou acesso inválido. Refaça o processo.', 'warning')
        return redirect(url_for('auth.esqueci_senha'))
        
    usuario = Usuario.query.get_or_404(usuario_id)
    
    if request.method == 'POST':
        nova_senha = request.form.get('nova_senha')
        usuario.senha = generate_password_hash(nova_senha)
        db.session.commit()
        
        session.pop('usuario_recuperacao_id', None)
        
        flash('Sua senha foi alterada com sucesso! Faça login com a nova senha.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('recuperar.html')


@auth_bp.route('/alterar_senha', methods=['POST'])
@login_required
def alterar_senha():
    senha_atual = request.form.get('senha_atual')
    nova_senha = request.form.get('nova_senha')

    if not check_password_hash(current_user.senha, senha_atual):
        flash('A senha atual está incorreta.', 'danger')
        return redirect(url_for('perfil'))

    if not nova_senha or len(nova_senha) < 6:
        flash('A nova senha deve ter pelo menos 6 caracteres.', 'warning')
        return redirect(url_for('perfil'))

    current_user.senha = generate_password_hash(nova_senha)
    db.session.commit()
    
    flash('Senha alterada com sucesso!', 'success')
    return redirect(url_for('perfil'))


@auth_bp.route('/excluir_perfil', methods=['POST'])
@login_required
def excluir_perfil():
    usuario = Usuario.query.get(current_user.id)
    if usuario:
        # Remove os itens do usuário e pedidos associados para evitar conflito de chave estrangeira
        Item.query.filter_by(usuario_id=usuario.id).delete()
        Pedido.query.filter((Pedido.ong_id == usuario.id) | (Pedido.doador_id == usuario.id)).delete()
        
        db.session.delete(usuario)
        db.session.commit()
        
    logout_user()
    flash('Sua conta foi permanentemente excluída.', 'info')
    return redirect(url_for('index'))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('index'))