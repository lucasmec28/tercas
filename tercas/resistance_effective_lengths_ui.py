"""Saved weak-length presentation, without live inputs or recalculation."""
from .report_audit import technical_number


def saved_length_note(evidence):
    section = evidence.get('source_section') or {}
    weak = section.get('weak_positive_reference') or {}
    domain = weak.get('domain') or {}
    lengths = domain.get('resistance_effective_lengths')
    if not lengths:
        return None
    return ('Comprimentos na resistência fraca (Anexo E): Lx='+
            technical_number(domain['Lx_used_mm'])+' mm; Lz='+
            technical_number(domain['Lz_used_mm'])+' mm. Vão físico L='+
            technical_number(domain['physical_span_mm'])+' mm, preservado nas solicitações, flechas e Vlasov. '+
            'Origem/hipótese declarada: '+lengths['origin']+'. '+
            'A componente forte com altura continua usando o vão inteiro, não estes comprimentos efetivos. '+
            'Nenhum apoio intermediário foi criado.')
