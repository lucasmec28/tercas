"""Fixed application idealization; no inferred physical property of a project."""
import copy
from .presentation import fmt

VERSION = 'cladding_actions_only_20261103_r1'
FIELD = 'model_domain'
ORIGIN = 'Domínio definido pelo usuário em 03/11/2026'
TEXT = ('Hipótese fixa do modelo: não há contato da telha/painel com o perfil nem ligação '
        'de qualquer mesa a painel. A telha contribui somente com as ações declaradas: '
        'peso, área de obstrução ao vento e recepção de sobrecarga quando aplicável à cobertura. '
        'Não fornece travamento, apoio, contenção ou rigidez ao perfil.')
LIMIT = ('Esta é a idealização de cálculo do app, não comprovação da condição física externa. '
         'Não define caminho de transferência das forças, não altera comprimentos efetivos '
         'ou linhas de aplicação das cargas e não implica torção nula. Sem aprovação global.')
CONFLICT = ('Fora do domínio adotado: as entradas declaram ligação de mesa a painel ou outra '
            'condição física incompatível com a idealização sem contato/ligação. A declaração '
            'foi preservada; a conclusão dependente permanece pendente e exige análise própria '
            'do caso. Mdist da seção isolada não resolve o conflito.')
HISTORICAL = ('RESULTADO ANTERIOR SEM DOMÍNIO REGISTRADO: esta exportação não recalcula o '
              'resultado nem aplica retroativamente a hipótese fixa sem contato/ligação a painel. '
              'As entradas e os valores históricos foram preservados; recalcule para registrar '
              'o domínio atualmente adotado.')


def evidence(data):
    """Optional version token; omitted legacy tokens are valid, without mutation."""
    if FIELD in data and data[FIELD] != VERSION:
        raise ValueError('model_domain incompatível com o domínio atual do app; a entrada não foi convertida. Preserve o arquivo e confira sua origem.')
    declared=data.get('u_panel_condition')
    if 'u_panel_condition' in data:
        if (not isinstance(declared,dict) or declared.get('condition') not in
            ('not_declared','no_flange_panel','top_panel_other_free','bottom_panel_other_free','other_specific_analysis')):
            raise ValueError('Declaração física de painel inválida; não foi convertida em ausência de painel.')
    conflict=explicit_panel_conflict(data)
    return dict(version=VERSION,text=TEXT,origin=ORIGIN,limit=LIMIT,
                status='outside_fixed_model_domain' if conflict else 'fixed_model_domain',
                input_token_present=FIELD in data,physical_declaration=copy.deepcopy(declared),
                physical_conditions_verified=False,conflict=CONFLICT if conflict else None)


def export_inputs(data):
    """Record the intended calculation domain on an export COPY, not in state."""
    evidence(data)
    out=copy.deepcopy(data);out[FIELD]=VERSION
    return out


def plain_u_distortional(domain):
    """9.3 exemption is conditional on the fixed model, never a panel credit."""
    if domain['conflict']:
        return dict(status='not_evaluated',MRd_Nmm=None,reason=domain['conflict'],
                    source='NBR 14762:2010 §9.3 / §9.8.2.3',model_domain=copy.deepcopy(domain))
    return dict(status='not_applicable',MRd_Nmm=None,
                source='NBR 14762:2010 §9.3, p32 (PDF38)',model_domain=copy.deepcopy(domain),
                reason='U simples dispensado de distorção em §9.3 no domínio adotado, sem ligação '
                       'de mesa a painel. A exceção de mesa tracionada ligada a painel não integra '
                       'esta idealização; não se usa Tabela 14 para esta dispensa.')


def report(doc,result):
    """Serialize recorded evidence only: old results are not re-qualified."""
    record=result.get('model_domain_evidence')
    if record is None:
        doc.add_paragraph(HISTORICAL)
        if explicit_panel_conflict(result.get('input_data',{})):doc.add_paragraph(CONFLICT)
        return
    doc.add_paragraph(record['text'])
    doc.add_paragraph('Origem da hipótese: '+record['origin']+'. Versão do domínio: '+record['version']+'. '+record['limit'])
    if record.get('conflict'):doc.add_paragraph(record['conflict'])


def explicit_panel_conflict(data):
    declared=data.get('u_panel_condition')
    return isinstance(declared,dict) and declared.get('condition') in (
        'top_panel_other_free','bottom_panel_other_free','other_specific_analysis')


def historical_rows(result,records):
    """Only conflicting old conclusions become pending; keep original intact.

    No structural recalculation, no new pendency for normal legacy inputs that
    omit the token, and no promotion of a retained conflicting D/biaxial result.
    """
    if 'model_domain_evidence' in result or not explicit_panel_conflict(result.get('input_data',{})):
        return records
    out=copy.deepcopy(records)
    for row in out:
        if row.get('Verificação') not in ('Distorcional','Flexão biaxial'):continue
        old_index=row.get('Índice')
        previous=' Situação histórica: '+str(row.get('Situação'))+'; índice histórico: '+('não disponível' if old_index is None else fmt(old_index))+'. '
        row.update(Situação='Fora do domínio — histórico pendente',Índice=None,
                   Observação=CONFLICT+' Resultado histórico não recalculado.'+previous+str(row.get('Observação','')))
    return out


def historical_inclination(result,record):
    """Show loads, not stale resistant conclusions, for a conflicting history.

    Original numerical evidence remains intact in the exported result JSON.
    """
    if 'model_domain_evidence' in result or not explicit_panel_conflict(result.get('input_data',{})):
        return record
    out=copy.deepcopy(record)
    def mark(item):
        if not isinstance(item,dict):return
        if 'states' in item:
            item['resistance_status']=('Conclusão resistente histórica pendente: fora do domínio adotado. '
                'As solicitações abaixo são históricas, não recalculadas. Resistências e interação '
                'anteriores não são revalidadas; os valores originais estão preservados no JSON do resultado.')
            for key in ('weak_axis_capacities','biaxial','strong_capacity_Nmm'):item.pop(key,None)
        else:
            for value in item.values():mark(value)
    mark(out)
    return out
