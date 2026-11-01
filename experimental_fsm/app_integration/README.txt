INTEGRAÇÃO EXPERIMENTAL ISOLADA — 2026-11-01

Entrega: adapter.py + panel.py, incluídos no pacote FSM separado. Nenhum arquivo do repositório produtivo lucasmec28/tercas foi editado. Não foi publicado nem transferido ao catálogo.

Uso futuro em cópia de homologação:
- preservar o pacote inteiro em namespace próprio;
- importar <pacote>.app_integration.panel.render e chamar render(st,namespace='fsm_laboratorio');
- não conectar retorno a Ml/Mdist, resistência ou aprovação do app;
- alternativamente executar `streamlit run app_integration/panel.py` na raiz deste pacote.
Dependências numéricas já usadas: numpy/scipy. Streamlit1.65 existente em connections_audit/test_dependencies foi reutilizado via PYTHONPATH; não foi instalado nada.

Interface: U/Ue com h,b,enrijecedor,t; eixos geométricos X horizontal/Y vertical; sinal do momento; E,nu,malha e intervalo de meias ondas. Calcula assinatura amostral e mostra a primeira forma própria em um ponto selecionado. Desenho: seção original tracejada/forma modal laranja, normalizada arbitrariamente, não flecha ELS. Inputs/resultados apresentados com duas casas, precisão interna preservada.

Modos: classificação permanece explicitamente pendente. Detectar um vale amostral NÃO o transforma em crítico local/distorcional. O painel não escreve/verifica resistência, nem adiciona verificação normativa. Estudos já classificados para geometrias exatas continuam no registro experimental separado, não extrapolados a geometrias livres.

Rastreabilidade/proteções: snapshot do pedido, hash dos inputs e implementação, limites operacionais, resíduos numéricos. Alterar seção/material/sinal/implementação exige recálculo antes de exportar ou desenhar. Falha no cálculo limpa resultado anterior. Namespaces dos widgets e estado são explícitos. Sem recalcular assinatura somente por mudar a visualização.

Verificado: 10 testes do adapter +4 testes de lógica de painel com API simulada, import como pacote e compilação. Revisor independente encontrou import absoluto, widgets sem namespace e pedido de conferir versão de implementação; corrigidos com testes. Termo meia onda longitudinal adotado.
ATUALIZAÇÃO16:43UTC: oito testes REAIS Streamlit1.65 AppTest passaram após correção de isolamento de imports; dois testes adicionais confirmam ausência de colisão com core do hospedeiro e ausência de mutação global sys.path. São testes do runtime, não pixels de navegador. Browser Chromium foi tentado e bloqueado por socket() Operation not permitted/crashpad do ambiente; não contornado. Servidorlocal encerrado. CSS/layout visual e integração no app produtivo permanecem não verificados. Não alegar disponibilidade no site.

Próximo passo condicionado: colocar este módulo apenas na cópia autorizada, executar testes Streamlit reais e revisão visual, mantendo saída fora do dimensionamento até classificação e qualificação pertinentes. Nenhum reboot necessário por esta entrega offline.

Imports standalone agora carregam pacote privado _lro_fsm_experimental_engine, sem depender de core global do hospedeiro. Integração completa por namespace continua preferível.
