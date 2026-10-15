# Prompt de implementação — Calendário provisório de salas

> **Arquivo histórico.** Este prompt registra requisitos da fase inicial e não define o comportamento vigente. Para os três status atuais, migração e validação, consulte o [README](../README.md) e a [atualização dos status](ATUALIZACAO-STATUS-2026-10-15.md).

Atue como engenheiro de software sênior e arquiteto responsável pela evolução do projeto existente em `painel/`.

## Objetivo

Transformar o Painel de Registros em um calendário compartilhado de bloqueio de salas e espaços de eventos para Costa do Sauípe e Rio Quente Resorts, cobrindo 2026, 2027 e 2028, usado pelas equipes Comercial MICE e Operacional enquanto a funcionalidade equivalente não estiver disponível no Opera Cloud.

Decisões já definidas: bloqueio por dia inteiro; cada equipe altera apenas os próprios bloqueios; podem existir negociações concorrentes para a mesma sala e período mediante opções com prioridade ou lista de espera; o servidor será desenvolvido em Python com Flask, substituindo Node.js e seguindo a orientação do time de desenvolvimento. Não volte a perguntar essas decisões.

Leia primeiro o código, o README, a documentação de validação, `docs/PROPOSTA-CALENDARIO-SALAS.md`, `docs/ANALISE-LISTA-SALAS.md` e `docs/catalogo-salas-preliminar.json`. Separe os requisitos recebidos das recomendações e decisões ainda em aberto. Use as respostas mais recentes do solicitante para atualizar a proposta.

## Condições antes da implementação operacional

Foi recebido e analisado o PDF `LISTA DE SALAS E ESPAÇOS CS & RQ.pdf`, com duas páginas e códigos de 1 a 125. Use a transcrição preliminar para revisão; ela não é um cadastro operacional homologado. Há 63 linhas de espaços sem composição explícita, 32 de combinações/configurações, 28 de variantes da Arena Sauipe e 2 de serviços. Não crie 125 salas independentes. Não invente nomes oficiais, capacidades ou divisões. Para prévias, identifique claramente qualquer dado fictício e isole-o da base operacional.

O solicitante não sabe atribuir os códigos aos resorts e pediu uma solução para essa ausência de informação. Implemente um catálogo único, com empreendimento opcional e uma categoria de interface “Empreendimento a identificar”. Não invente um terceiro resort real, não atribua resort por cores, nomes ou ordem das linhas e não replique um espaço nos dois empreendimentos. A classificação será progressiva e não deve impedir o desenvolvimento da solução.

Decisões posteriores confirmadas: PostgreSQL; situações Pendente de validação, Em espera, Em opção prioritária, Confirmado e Cancelado; opção e confirmado ocupam; ordem de entrada com promoção manual pelo responsável da fila; sem expiração ou promoção automática; concessão integral dos espaços incluindo montagem e desmontagem. Login corporativo ainda indefinido: implemente contas individuais locais para o piloto e documente a futura integração. Permissões de cadastro, fila e administração são separadas, com escopos configuráveis por empreendimento/área a identificar. A indicação das pessoas e a homologação física permanecem com a operação. Não repita perguntas já respondidas.

## Aproveitamento do projeto

Preserve o trabalho existente e reaproveite layout, responsividade, diálogos, busca, tabela auxiliar, CSV, impressão e utilitários pertinentes. Adapte a apresentação aos dois resorts. Mantenha HTML, CSS e JavaScript na interface; a mudança para Python se aplica ao servidor. Não imponha uma reescrita de framework de interface sem necessidade demonstrada.

Separe interface, regras de domínio e persistência. Substitua o modelo genérico de colunas livres para os campos essenciais por entidades estruturadas: empreendimento; espaço/recurso físico com identificador permanente; configuração e vínculo com recursos; item de origem; bloqueio/solicitação com equipe proprietária; alocação/fase; ocupação efetiva; usuário/permissões; histórico. Não permita excluir ou alterar livremente campos que sustentem disponibilidade e conflitos.

Preserve backups e dados anteriores. Não converta os registros demonstrativos em bloqueios. Qualquer migração de dados reais deve ter mapeamento e validação explícitos.

## Funcionalidades

1. Oferecer grade mensal com espaços nas linhas e datas nas colunas; selecionar empreendimento (“Todos”, “Costa do Sauípe”, “Rio Quente” ou “A identificar”), ano e mês; pesquisar espaço e filtrar situação. Usar textos e cores para as situações, cabeçalhos fixos e alternativa de lista em telas pequenas. Mostrar itens sem resort em “Todos” e “A identificar”, com rótulo explícito; não incluí-los silenciosamente em um resort específico.
2. Consultar salas disponíveis em um intervalo e detalhes de cada bloqueio. Exibir dias inteiros, sem formulário de horários ou turnos; mostrar a ocupação efetiva e as solicitações em espera por sala/período.
3. Criar, editar e cancelar bloqueios com evento/motivo, equipe proprietária, responsável, sala(s), datas inicial/final, situação e observações, conforme campos validados. Cada equipe edita e cancela apenas solicitações próprias. Cancelamento deve liberar a ocupação e preservar o histórico.
4. Carregar os itens extraídos da fonte para revisão com códigos, páginas e nomes preservados, identificação estável, relatório de inconsistências e proteção contra duplicação. Serviços e variantes permanecem rastreáveis, sem se tornarem salas independentes. Cadastrar áreas externas/de apoio como espaços candidatos e preservar restrições de uso descritas na fonte.
5. Exportar CSV e imprimir os bloqueios que intersectem os filtros e o período selecionados. Manter o tratamento seguro de CSV existente.
6. Oferecer revisão cadastral individual e em lote para atribuir empreendimento/localização posteriormente, com prévia das mudanças e histórico. Usar permissão cadastral específica, sem conceder por isso a edição de bloqueios de outras equipes. Alterar a classificação do recurso existente preservando seu ID, solicitações, autoria, equipe proprietária, datas, prioridade e histórico. Revalidar acesso caso as permissões dependam do resort.

## Tratamento dos itens recebidos

- Códigos 5 e 6: mão de obra; excluir de espaços reserváveis. “Por Turno” nesses serviços não muda os bloqueios por dia inteiro.
- Combinações como “Bahia 1 - 2”: verificar ocupação e fila contra os recursos componentes, nos dois sentidos. Homologar a composição antes de conceder ocupação efetiva.
- Códigos 35/36: dois/três módulos entre Gardênia, Canário, Aimorés e Amazonas exigem seleção de conjunto permitido; a quantidade não determina os módulos.
- Códigos 50-54: intervalos Ouro Preto são hipóteses de composição, não vínculos confirmados. Não expandi-los automaticamente para ocupação.
- Códigos 90-117: variantes de Arena por módulos/foyer, fase e climatização precisam apontar aos recursos físicos correspondentes, evitando disponibilidade duplicada. Confirmar identificação dos módulos, combinações possíveis e relação com foyer.
- Códigos 118-124: não inferir localização das “Salas” numeradas pela proximidade das linhas da Arena.
- Não mesclar “Porto Seguro” (13) com “Porto Seguro 1” e demais numeradas (62-67) por semelhança de nome.
- Preserve as observações de Jubarte, Maremoto e Brinquedoteca sobre restrições de montagem. Não converter capacidades ausentes em zero nem somar capacidades das partes para deduzir configurações.
- Preços e reajustes do PDF não são funcionalidades solicitadas para o calendário.

Separe pendência de empreendimento, validação física e situação da solicitação. Um recurso com identidade/composição validadas pode receber bloqueio mesmo com resort pendente, por usuário autorizado à área comum. Para recursos/configurações ainda fisicamente indefinidos, permitir apenas consulta e solicitação “Pendente de validação”, sem garantir ocupação ou atribuir automaticamente posição elegível na fila. Não exibir uma grade vazia desses itens como prova de disponibilidade.

Os conflitos e a prioridade usam IDs físicos globais, independentemente do filtro ou do resort. A classificação posterior não muda essa lógica. Alterar composições ou mesclar possíveis duplicados exige revisão transacional das ocupações existentes; não tratar essas ações como simples mudança de resort.

## Arquitetura e integridade

Substitua o servidor Node.js por uma aplicação central em Python com Flask, API HTTP com respostas JSON, banco relacional e autenticação real. Flask já é a escolha de framework. Alinhe versões suportadas, banco, infraestrutura e identidade ao padrão do time de desenvolvimento, registrando as escolhas. Não contrate serviços ou publique um ambiente como parte implícita deste prompt.

O `server.mjs` atual apenas entrega arquivos estáticos. Não existe um backend de dados em Node.js para tradução automática: implemente no servidor Python as regras de disponibilidade, fila, acesso e persistência. Trocar apenas o servidor estático, mantendo `localStorage` como base oficial, não atende ao uso compartilhado.

Organize o backend Python em módulos de domínio, API e persistência, com dependências declaradas, configuração por ambiente, migrações de banco e testes. Adapte `storage.js` para chamadas assíncronas à API e ajuste os fluxos de interface para aguardar respostas e tratar carregamento, falhas e conflitos. Preserve a apresentação dos arquivos estáticos durante essa transição.

Use o padrão de fábrica de aplicação (`create_app`) e `Blueprints` para organizar as rotas Flask. Mantenha as regras de acesso, fila e ocupação em serviços testáveis, separados das rotas e da persistência. Sirva a interface existente e a API preferencialmente na mesma origem. Não é necessário converter a interface atual em templates. Se a autenticação usar cookies de sessão, inclua proteção contra CSRF nas operações de alteração. Escolha os componentes de banco e autenticação conforme o padrão da equipe; Flask sozinho não entrega essas funcionalidades completas.

Atualize a documentação de execução e implantação para Python e retire a dependência do servidor Node.js após validar a substituição. Node.js pode permanecer apenas como ferramenta de desenvolvimento para os testes JavaScript existentes, se pertinente; a aplicação operacional não deve exigir um servidor Node.js. Não use um servidor estático de desenvolvimento como substituto da aplicação operacional autenticada.

Execute a aplicação operacional com servidor WSGI de produção compatível com a infraestrutura e depuração desativada; reserve o servidor de desenvolvimento do Flask para desenvolvimento local. Consulte a documentação oficial de [fábricas de aplicação](https://flask.palletsprojects.com/en/stable/patterns/appfactories/) e [implantação](https://flask.palletsprojects.com/en/stable/deploying/) ao implementar.

O banco será a fonte oficial. `localStorage` pode guardar preferências, mas não será a base compartilhada. Faça mutações por registro, substituindo o padrão de salvar toda a base. Valide permissões e dados no servidor, independentemente da interface. Determine a equipe proprietária pela identidade autenticada; não permita alterar a propriedade para contornar permissões. Edição do próprio bloqueio não autoriza passar à frente de outra equipe na fila.

Permita solicitações sobrepostas em espera, mas impeça duas ocupações efetivas do mesmo recurso no mesmo dia. Situações aprovadas: opção prioritária e confirmado ocupam; pendente, em espera e cancelado não ocupam. Não confunda registrar interesse com garantir disponibilidade.

Implemente detecção de conflito e elegibilidade de prioridade junto com a gravação em operação atômica. Verificar apenas no navegador ou fazer uma consulta separada da escrita não é suficiente. Considere as composições identificadas no documento e converta configurações homologadas em recursos físicos antes de checar disponibilidade. A unicidade de ocupações efetivas por recurso/data é uma opção de implementação. Para bloqueios com vários espaços, conceda o conjunto completo atomicamente; valide com a operação a proposta de manter a solicitação inteira em espera se houver indisponibilidade parcial.

A fila é relativa às salas e aos dias que se sobrepõem. Ao promover uma opção, revalide o período completo e todos os recursos. Não promova automaticamente após cancelamento, não transforme espera em confirmado silenciosamente nem retire a ocupação de uma reserva confirmada por reordenação. Implemente mudança de prioridade somente depois de definir quem tem autoridade para fazê-la; registre toda mudança no histórico.

Detecte edições concorrentes por versão, sem perda silenciosa de atualizações. Mantenha histórico com autoria, horário e valores alterados. Atualize a agenda a partir do servidor; indique falhas de conexão e não apresente rascunhos ou falhas como reservas concluídas. Repetir uma requisição não deve duplicar um bloqueio.

Trate 2026–2028 como intervalo configurado. Inclua 29/02/2028 e ocupações entre meses/anos. Defina claramente os limites do intervalo: exiba a data final ocupada inclusiva e use fim exclusivo no dia seguinte internamente, se essa for a convenção adotada; isso permite o último dia de 2028. Preserve datas civis independentemente do fuso do computador. Inclua dias de montagem/desmontagem conforme a regra que for acordada. Deduplicate ocupações por bloqueio/recurso/dia quando fases do mesmo bloqueio se sobrepuserem; alterar uma fase não pode liberar um dia ainda ocupado por outra.

Não introduza expiração automática, promoção automática, reordenação arbitrária ou exclusão definitiva sem regra acordada. “Provisório” descreve a solução e não determina a situação de cada reserva.

## Entrega e validação

Implemente em etapas verificáveis: catálogo/regras; experiência de calendário; persistência compartilhada e acesso; piloto operacional. Não apresente uma prévia local como solução multiusuário concluída.

Execute os testes existentes pertinentes e implemente testes do backend em Python, incluindo integração com o banco e a API. Cubra: datas-limite e ano bissexto; conflitos em criação/edição/promoção; negociações concorrentes em espera; disputa simultânea pela mesma ocupação efetiva; prioridade em intervalos parcialmente sobrepostos; gravação atômica de múltiplas salas; cancelamento e liberação sem promoção automática; versão desatualizada; impedimento de edição entre equipes e alteração indevida da propriedade; importação inválida e repetida; filtros por interseção de períodos e persistência em sessões independentes. Verifique também que a aplicação pode iniciar e atender a interface e a API sem o servidor Node.js.

Valide no navegador os fluxos centrais, a atualização entre usuários, a responsividade e os relatórios. Verifique uma restauração de backup antes do uso operacional. Documente como executar, administrar salas e acessos, fazer backup e recuperar a base.

Acrescente verificações específicas do catálogo: configuração contra componente e contra outra configuração intersectante; ausência de disponibilidade duplicada entre variantes da Arena; exclusão de serviços; distinção de nomes semelhantes; solicitação pendente sem ocupação para topologia indefinida; classificação por resort preservando IDs e bloqueios; conflitos antes/depois dessa classificação; autorização cadastral e de edição por equipe independentes; correção de classificação sem perda do histórico. Para fases sobrepostas do mesmo bloqueio, verificar a união das datas e a preservação de ocupações ainda necessárias ao alterar uma fase.

Ao concluir cada etapa, informe o que está implementado, o que foi comprovado por testes e o que depende de dados, regras ou infraestrutura. Não declare verificações que não foram realizadas.

Não implemente integração com Opera Cloud, financeiro, contratos, pagamentos, CRM, recorrência ou notificações nesta primeira versão. Mantenha identificadores estáveis e exportações legíveis para permitir uma futura avaliação de migração, sem prometer compatibilidade não verificada.
