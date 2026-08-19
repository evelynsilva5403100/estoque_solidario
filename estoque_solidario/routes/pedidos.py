import os
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from modelos import db, Item, Pedido, Usuario

pedidos_bp = Blueprint('pedidos', __name__)

def verificar_e_estornar_expirados():
    agora = datetime.utcnow()
    pedidos_vencidos = Pedido.query.filter(
        Pedido.status.in_(['Aguardando Retirada', 'A caminho da retirada']),
        Pedido.data_limite != None,
        Pedido.data_limite < agora
    ).all()
    
    for p in pedidos_vencidos:
        p.status = 'Expirado'
        # Devolve a quantidade para o estoque do item
        if p.item:
            p.item.qtd += p.qtd_solicitada
            
    if pedidos_vencidos:
        db.session.commit()

@pedidos_bp.route('/fazer_pedido/<int:item_id>', methods=['POST'])
@login_required
def solicitar(item_id):
    if getattr(current_user, 'tipo', '') != 'ong':
        flash('Apenas contas cadastradas como receptor podem solicitar doações.', 'danger')
        return redirect(url_for('doacoes.listar_doacoes'))

    item = Item.query.get_or_404(item_id)
    
    if item.usuario_id == current_user.id:
        flash('Você não pode solicitar seu próprio item.', 'warning')
        return redirect(url_for('doacoes.listar_doacoes'))
        
    try:
        qtd_solicitada = int(request.form.get('qtd_solicitada', 1))
    except ValueError:
        qtd_solicitada = 1

    if qtd_solicitada > item.qtd:
        flash(f'A quantidade solicitada ({qtd_solicitada}) é maior que a disponível ({item.qtd}).', 'danger')
        return redirect(url_for('doacoes.listar_doacoes'))

    # --- CÁLCULO DO PRAZO BASEADO NA VALIDADE ---
    try:
        data_val_obj = datetime.strptime(str(item.validade), '%Y-%m-%d').date()
        hoje = datetime.utcnow().date()
        dias_ate_vencer = (data_val_obj - hoje).days
        dias_prazo = max(1, min(int(dias_ate_vencer / 2), 5))
        data_limite_calc = datetime.utcnow() + timedelta(days=dias_prazo)
    except Exception:
        data_limite_calc = datetime.utcnow() + timedelta(days=3)

    # 1. ABATE A QUANTIDADE IMEDIATAMENTE DO ESTOQUE
    item.qtd -= qtd_solicitada

    novo_pedido = Pedido(
        item_id=item.id,
        ong_id=current_user.id,
        doador_id=item.usuario_id,
        qtd_solicitada=qtd_solicitada,
        status='Aguardando Retirada',
        item_nome=item.nome,
        item_unidade=item.unidade,
        item_validade=str(item.validade),
        data_limite=data_limite_calc # Salva o prazo limite calculado
    )

    db.session.add(novo_pedido)
    db.session.commit()

    flash(f'Pedido realizado com sucesso! Prazo limite para retirada: {data_limite_calc.strftime("%d/%m/%Y")}.', 'success')
    return redirect(url_for('pedidos.meus_pedidos'))


@pedidos_bp.route('/meus_pedidos', endpoint='meus_pedidos')
@pedidos_bp.route('/pedidos', endpoint='pedidos')
@login_required
def meus_pedidos():
    # Roda a verificação de prazos expirados automaticamente
    verificar_e_estornar_expirados()

    if getattr(current_user, 'tipo', '') == 'mercado':
        pedidos = Pedido.query.filter_by(doador_id=current_user.id).filter(Pedido.status.in_(['Aguardando Retirada', 'A caminho da retirada'])).all()
    else:
        pedidos = Pedido.query.filter_by(ong_id=current_user.id).filter(Pedido.status.in_(['Aguardando Retirada', 'A caminho da retirada'])).all()

    pedidos_com_info = []
    for p in pedidos:
        if current_user.tipo == 'mercado':
            alvo = db.session.get(Usuario, p.ong_id)
            nome_alvo = alvo.nome_real if alvo else "ONG Desconhecida"
            telefone_alvo = alvo.telefone if alvo else ""
            email_alvo = alvo.email if alvo else ""
        else:
            alvo = db.session.get(Usuario, p.doador_id)
            nome_alvo = alvo.nome_real if alvo else "Mercado Doador"
            telefone_alvo = alvo.telefone if alvo else ""
            email_alvo = alvo.email if alvo else ""

        validade_val = p.item_validade
        if p.item and p.item.validade:
            validade_val = p.item.validade

        pedidos_com_info.append({
            'pedido': p,
            'validade': validade_val,
            'nome_alvo': nome_alvo,
            'telefone_alvo': telefone_alvo,
            'email_alvo': email_alvo
        })

    return render_template('pedidos.html', pedidos_com_info=pedidos_com_info)


@pedidos_bp.route('/historico_pedidos', endpoint='historico_pedidos')
@login_required
def historico_pedidos():
    if getattr(current_user, 'tipo', '') == 'mercado':
        pedidos = Pedido.query.filter_by(doador_id=current_user.id).filter(Pedido.status.in_(['Concluído', 'Expirado'])).all()
    else:
        pedidos = Pedido.query.filter_by(ong_id=current_user.id).filter(Pedido.status.in_(['Concluído', 'Expirado'])).all()

    pedidos_com_info = []
    for p in pedidos:
        if current_user.tipo == 'mercado':
            alvo = db.session.get(Usuario, p.ong_id)
            nome_alvo = alvo.nome_real if alvo else "ONG Desconhecida"
            telefone_alvo = alvo.telefone if alvo else ""
            email_alvo = alvo.email if alvo else ""
        else:
            alvo = db.session.get(Usuario, p.doador_id)
            nome_alvo = alvo.nome_real if alvo else "Mercado Doador"
            telefone_alvo = alvo.telefone if alvo else ""
            email_alvo = alvo.email if alvo else ""

        validade_val = p.item_validade
        if p.item and p.item.validade:
            validade_val = p.item.validade

        pedidos_com_info.append({
            'pedido': p,
            'validade': validade_val,
            'nome_alvo': nome_alvo,
            'telefone_alvo': telefone_alvo,
            'email_alvo': email_alvo
        })

    return render_template('historico_pedidos.html', pedidos_com_info=pedidos_com_info)


@pedidos_bp.route('/ong_solicitar_retirada/<int:pedido_id>', methods=['POST'])
@login_required
def ong_solicitar_retirada(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.ong_id != current_user.id:
        flash('Permissão negada.', 'danger')
        return redirect(url_for('pedidos.meus_pedidos'))
    
    pedido.status = 'A caminho da retirada'
    db.session.commit()
    flash('Status atualizado: A caminho da retirada.', 'success')
    return redirect(url_for('pedidos.meus_pedidos'))


@pedidos_bp.route('/confirmar_retirada/<int:pedido_id>', methods=['POST'])
@login_required
def confirmar_retirada(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.doador_id != current_user.id:
        flash('Permissão negada.', 'danger')
        return redirect(url_for('pedidos.meus_pedidos'))
    
    # Como a quantidade já foi abatida no momento do pedido, aqui apenas concluímos
    pedido.status = 'Concluído'
    db.session.commit()
    flash('Pedido concluído e enviado para o histórico com sucesso!', 'success')
    return redirect(url_for('pedidos.meus_pedidos'))