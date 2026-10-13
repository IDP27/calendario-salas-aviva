# Implementação e validação — 7 de outubro de 2026

Foi implementado um piloto local em Python/Flask com PostgreSQL, mantendo HTML, CSS e JavaScript na interface. O servidor estático Node foi retirado do caminho operacional. O painel anterior, seus arquivos e seus nove testes foram preservados em `legacy/` e `tests/`; não houve conversão de exemplos em bloqueios.

## Decisões incorporadas

| Decisão do solicitante | Implementação |
| --- | --- |
| Calendário 2026–2028 por dia inteiro | Grade mensal e lista, datas civis inclusivas, ano bissexto e passagem de ano |
| Cada equipe altera somente seus bloqueios | Propriedade determinada pela conta e validada no servidor |
| Negociações concorrentes | Pendências, espera, opção prioritária, confirmação e cancelamento |
| Ordem de entrada e promoção manual | Responsabilidade específica de fila, sem promoção/expiração automática |
| Todas as salas juntas, com montagem/desmontagem | Alocações por fase, união dos dias e concessão integral em transação |
| Flask e PostgreSQL | Fábrica Flask, Blueprints, psycopg, migrações versionadas e Waitress |
| Login corporativo ainda indefinido | Contas individuais locais para o piloto, com responsabilidades e escopos configuráveis |
| Resorts desconhecidos | Cadastro único e categoria “Empreendimento a identificar”, sem atribuição presumida |

## Catálogo

A fonte preserva 125 códigos e os nomes originais, em duas páginas. São 63 candidatos a espaços individuais, 32 combinações/configurações, 28 variantes de Arena agrupadas em quatro configurações e dois serviços não reserváveis: total de 99 configurações para revisão, sem criar 125 salas independentes.

O catálogo operacional inicial permanece sem resort atribuído e sem composição homologada. Uma pessoa com responsabilidade cadastral deve validar identidade e composição com a operação. Só então uma configuração pode entrar em espera elegível ou receber ocupação; o resort pode continuar pendente se a conta tiver acesso à categoria comum.

A revisão em lote preserva identidade e histórico. Ouro Preto, pares/trios Gardênia, Arena e Salas numeradas continuam sem inferências automáticas. Observações de Jubarte, Maremoto e Brinquedoteca foram preservadas. A interface permite cadastrar recursos físicos identificados para os módulos da Arena; não deduz esses nomes a partir do PDF.

## Integridade e acesso

A restrição única de ocupação por recurso/data impede ocupações duplicadas. Uma transação serializa mutações do piloto e engloba a checagem de conflitos, a prioridade, todas as salas/fases e o histórico. Edições usam versão do registro; repetição de criação usa chave de idempotência.

Permissões cadastrais, responsabilidade pela fila e administração de contas são distintas. Um responsável de fila pode conceder opção para outra equipe conforme a ordem elegível, mas não editar nem cancelar o evento dela. Escopo é reavaliado após classificação e sessões são invalidadas quando o acesso muda. A revogação também é verificada depois de obter o bloqueio de escrita.

A fonte oficial é o PostgreSQL. O navegador não salva a base de bloqueios no localStorage. Consultas independentes recebem dados do mesmo servidor. A interface atualiza a cada 20 segundos quando não há edição ativa, ao recuperar foco e pelo comando Atualizar. O calendário mostra ocupação física mesmo quando o filtro seleciona outra situação.

## Verificações executadas

**36 testes Python aprovados**, com PostgreSQL real e esquemas de teste isolados. Cobertura:

- importação integral, repetida e inválida; exclusão de serviços; nomes parecidos separados; Arena agrupada; ausência de capacidade não transformada em zero;
- composição indefinida restrita a pendência; combinação contra componente nos dois sentidos; espera visível nos componentes;
- fila por entrada, concessão manual, cancelamento sem promoção automática e solicitação com várias salas sem gravação parcial;
- duas promoções concorrentes para a mesma ocupação; edição com conflito preservando dados anteriores; controle de versão e criação idempotente;
- limites 2026–2028, 29/02/2028, interseção de períodos e união de fases sobrepostas;
- classificação mantendo IDs e ocupações, revalidação de escopo, composição não alterada sob solicitações vigentes;
- edição por equipe, responsabilidade cadastral independente, revogação de acesso, autenticação, CSRF e proteção de caminhos estáticos;
- CSV com neutralização de fórmulas, filtro por período e persistência entre sessões independentes;
- backup real e restauração em banco vazio: comparação de contagens de usuários, catálogo, recursos, itens de origem, bloqueios, alocações, ocupações e histórico; recusa de sobrescrita e restauração sobre dados existentes;
- restauração do esquema padrão `public`, preservando sua criação inicial pelo PostgreSQL.

**9 testes JavaScript do painel anterior aprovados.** Sintaxe do JavaScript novo e compilação dos módulos Python também verificadas.

No navegador, usando exclusivamente o esquema isolado com aviso de dados fictícios:

- acesso individual, abertura da grade e da lista;
- solicitação para Bahia 1–2, promoção manual, confirmação, edição e cancelamento com motivo;
- ocupação refletida em Bahia 1 e Bahia 2;
- pesquisa e consulta em duas sessões com contas distintas: Operação vê a atualização do Comercial e não recebe ações de edição/cancelamento;
- relatório e download CSV, arquivo lido com cabeçalho e alocação confirmada corretos;
- tela de celular em 390 px, com lista e sem transbordamento horizontal do documento;
- console consultado sem erros ou avisos nos fluxos verificados.

O botão de impressão foi acionado e o conteúdo do relatório é preparado; **a saída final em PDF não foi gerada nem inspecionada**, pois a janela nativa de impressão não pôde ser validada pela ferramenta. A importação pelo seletor de arquivos e a criação de contas pela interface não foram exercitadas de ponta a ponta no navegador; as regras correspondentes foram testadas na API. Os testes visuais não representam homologação do inventário.

Imagem de verificação: `calendario-teste-desktop.jpg`. Ocupações e validações mostradas nela são fictícias.

## Para adoção operacional

Ainda dependem do time e da operação:

1. Homologar identidades e composições antes de conceder ocupações reais.
2. Designar responsáveis de cadastro/fila e configurar usuários/escopos; classificar resorts progressivamente.
3. Definir servidor compartilhado, versão PostgreSQL, HTTPS, integração com Microsoft Entra ID e identidades do Active Directory, monitoramento e política de backups/retenção.
4. Executar homologação com usuários das duas equipes e verificar impressão no navegador adotado.

O piloto local usa Waitress com depuração desligada e escuta apenas o computador local. Não foi publicado um serviço compartilhado. Não foram feitos testes de carga, integração corporativa ou integração com Opera Cloud. Mudanças de composição sob reservas vigentes e fusões de recursos são recusadas; exigem uma migração revisada, sem alteração silenciosa de ocupações.

As instruções de execução, administração, backup e recuperação estão em `../README.md`. Referências consultadas: [fábricas Flask](https://flask.palletsprojects.com/en/stable/patterns/appfactories/), [implantação Flask](https://flask.palletsprojects.com/en/stable/deploying/) e [pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html).
