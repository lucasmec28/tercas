# Leitura NBR repetida: cache de validação bem-sucedida na sessão

## Diagnóstico e escopo exato

O teste de recuperação `test_saved_readers_do_not_reopen_sources_or_solve`
falhou em R20 e R21 pelo mesmo caminho: Word → NBR.preserved → _build →
_inventory → own.validate → _source. Portanto não é regressão introduzida
pelo adapter girt ou pelo piso v3. É conflito anterior entre o leitor de
apresentação e o revalidador completo. Remover apenas own.validate não basta:
_build também consulta geometria/fontes e pode repetir Ritz conforme a versão.

O reparo é um cache limitado de SUCESSOS previamente estabelecidos na mesma
sessão, não um novo selo persistido, autoridade de hashes ou leitor offline.
Não altera fórmula, método, versão salva, schema, seleção resistente ou
resultado da reconstrução. Não promove históricos.

## Produtor, ingresso e apresentação

1. `attach`: copia o resultado, produz o packet pelo _build existente e só
   depois registra sucesso para seu conteúdo atual. Falha não registra nada.
2. Ingresso frio: preserved executa a função antiga integral, com exatamente
   a versão salva; autentica fontes e repete aritmética/mecânica que essa
   versão já exigia. Somente sucesso pode ser reutilizado posteriormente.
3. Apresentação quente: conteúdo já validado e idêntico recebe uma cópia do
   mesmo snapshot, sem nova geometria, fonte ou solver. UI, Word e JSON
   reimportado na mesma sessão podem compartilhar esse sucesso.
4. Mudança de valor, mesmo refazendo hashes declarados, muda os bytes atuais,
   perde o sucesso anterior e volta ao ingresso completo. Falhas não entram.

Dependências reais de _build/_inventory/own.preserved: input_data completo,
input_fingerprint, schema, ue_catalog_reference_evidence completo,
load_bundle, cases completos (deliberadamente mais do que as combinações)
e packet nbr_ue_family_application completo. Campos ausentes e nulos são
diferentes. Outros resumos globais/apresentação não alimentam esse cálculo e
mantêm seus próprios validadores; não se dispensa a autenticação do panorama.

LRU16 contém somente tokens calculados dos bytesJSONnativos atuais dessas
dependências. Não guarda objetos/snapshots, identidades Python, flags do
usuário ou hashes que ele declara como chaves. Tipos exatos de JSON, chaves
string e números finitos são exigidos para hit; tuple/list e subclasses não
compartilham sucesso. Conteúdo não nativo passa ao validador antigo, não a
uma aceitação nova. Retornos são sempre cópias destacadas.

## Limite que permanece

Primeira importação em outra sessão, cache limpo/expulso ou alteração de
conteúdo ainda exige as fontes e o replay antigo. Não anunciar esse ajuste
como recuperação offline completa. Separar de vez ingresso e apresentação
fria requer um contrato mais amplo de fontes/autovalores preservados e sua
validação sem recálculo; não é solucionado por inventar um hash-selo.

Revisão independente estática confirmou as dependências também nos leitores
v1/v2. O risco de alias concorrente foi corrigido capturando uma única cópia
destacada antes de token/replay/retorno; o objeto original não é lido novamente
para decidir o que devolver. Teste simulado de mutação após captura incluído.

## QA focal

37 testes passaram em13,63s: falha original do Word sem fontes agora passa;
cache produtor/UI/Word/JSON e girt, replay frio v5, perda de hit por mutação e
rehash, aliases tuple/list, tipos não finitos, missing/null, LRU, falhas não
armazenadas, corrida após captura e regressões integração/panorama. Cache
limpo com _source bloqueado continua exigindo fonte, conforme limite declarado.
Nenhuma suíte ampla repetida. Não foram integrados o candidato de agrupamento
nem a nova política CT nesta correção.
