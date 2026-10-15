# Proposta de evolução — Calendário de salas

> **Proposta histórica.** As seções abaixo preservam hipóteses e decisões da fase de desenho, inclusive situações e funcionalidades que mudaram. O sistema atual usa somente **Reservado, Confirmado e Cancelado**; o empreendimento dos 99 espaços/configurações já foi classificado. Não use este texto como instrução de operação ou deploy. Consulte o [README](../README.md) e a [atualização dos status](ATUALIZACAO-STATUS-2026-10-15.md).

Data: 7 de outubro de 2026.
Estado: decisões atualizadas e implementação local disponível em Flask + PostgreSQL. O diagnóstico abaixo registra a base anterior; consulte `IMPLEMENTACAO.md` para o que foi entregue e verificado. Classificação dos resorts e homologação física permanecem pendentes.

## 1. Objetivo e requisitos recebidos

Disponibilizar um calendário provisório de bloqueio de salas e espaços de eventos para Costa do Sauípe e Rio Quente Resorts, cobrindo 2026, 2027 e 2028. As equipes Comercial MICE e Operacional devem conseguir consultar e atualizar as informações com facilidade. Foi recebido o PDF `LISTA DE SALAS E ESPAÇOS CS & RQ.pdf`, com duas páginas e 125 linhas codificadas. Ele mistura espaços, combinações, variantes de uso e serviços; não é um cadastro de 125 salas independentes. A análise está em `ANALISE-LISTA-SALAS.md`, e a transcrição estruturada está em `catalogo-salas-preliminar.json`.

A expressão “provisório” descreve a duração da solução, não a situação de cada bloqueio. A existência de negociações concorrentes foi confirmada separadamente pelo solicitante; foi aprovada a ordem de entrada com promoção manual e sem expiração automática.

O Opera Cloud é o contexto da necessidade. A solicitação não inclui integração, sincronização nem importação futura automática para esse sistema.

Regras confirmadas pelo solicitante em 7 de outubro de 2026:

- Os bloqueios são por **dia inteiro**.
- **Cada equipe altera apenas os próprios bloqueios**. Proposta de aplicação: Comercial MICE e Operacional consultam a agenda comum; a propriedade é da equipe, não apenas da pessoa que criou o registro. O escopo de acesso por empreendimento ainda será definido.
- **Pode haver mais de uma negociação para a mesma sala no mesmo período**, mediante opções com prioridade ou lista de espera. A ordem é de entrada; a promoção é manual pelo responsável da fila, sem reordenação arbitrária.
- **O servidor da solução será desenvolvido em Python com Flask**, seguindo a orientação do time e a escolha discutida com o solicitante. A interface existente permanece em HTML, CSS e JavaScript; o banco escolhido é PostgreSQL. O login corporativo será via Microsoft Entra ID, com identidades sincronizadas do Active Directory; contas individuais locais sustentam apenas o piloto atual.

- Situações aprovadas: Pendente de validação, Em espera, Em opção prioritária, Confirmado e Cancelado. Opção e confirmado ocupam; as demais não.
- Reservas com múltiplos espaços são concedidas juntas, incluindo montagem e desmontagem. Não há concessão parcial ou promoção automática.

O solicitante informou que não sabe separar os códigos por resort e pediu uma solução que evite conflitos e confusões. A decisão de arquitetura é manter um catálogo único e uma categoria visível “Empreendimento a identificar”, sem atribuir o resort por nomes, cores ou posição no PDF. A classificação poderá ser feita posteriormente sem duplicar espaços ou recriar solicitações.

## 2. Diagnóstico do projeto existente

O projeto é um painel genérico em HTML, CSS e JavaScript, com um servidor Node.js que entrega arquivos apenas no computador local. O armazenamento usa `localStorage`, e o acesso usa uma conta demonstrativa compartilhada.

| Componente existente | Como aproveitar | Mudança necessária |
| --- | --- | --- |
| Layout, navegação e responsividade | Preservar a base visual e os componentes | Representar os dois resorts e priorizar a agenda |
| Formulários, diálogos e mensagens | Adaptar para criar, alterar e cancelar bloqueios | Campos e regras específicos de ocupação |
| Tabela, busca e filtros | Oferecer uma visão de lista complementar | Filtrar pelo período de ocupação, e não pela criação do registro |
| Relatórios, CSV e impressão | Reutilizar a apresentação e o tratamento seguro de CSV | Relatórios por resort, sala, período e situação |
| Validações e testes | Aproveitar utilitários de interface e cenários de teste pertinentes | Implementar e testar no servidor Python a integridade dos intervalos, permissões e concorrência |
| Colunas configuráveis | Manter apenas se houver necessidade de campos complementares | Proteger os campos essenciais; usuário não pode excluir sala ou período |
| `storage.js` | Aproveitar a separação da persistência | Migrar para chamadas assíncronas a um serviço central |
| `server.mjs` | Usar o comportamento atual como referência para manter a interface acessível | Substituir o servidor Node.js por aplicação Python com Flask, serviço de dados autenticado e hospedagem compartilhada |

O painel atual não possui calendário, cadastro estruturado de salas, detecção de sobreposição, usuários reais ou histórico completo de alterações. A detecção de mudanças entre abas do mesmo navegador não resolve concorrência entre equipes.

## 3. Experiência proposta

Tela principal com seletor de empreendimento (“Todos”, “Costa do Sauípe”, “Rio Quente” e “A identificar”), ano e mês; pesquisa de espaço; filtros de situação; ação “Novo bloqueio”. A visão principal será uma grade mensal: espaços nas linhas e dias nas colunas, com os nomes dos espaços e o cabeçalho das datas fixos durante a rolagem. Bloqueios de vários dias aparecem como faixas contínuas. Exibir os itens pendentes em “Todos” e “A identificar”, com rótulo textual; não incluí-los silenciosamente nos resultados de um resort específico.

Selecionar um período abre o formulário; selecionar um bloqueio abre seus detalhes e as ações permitidas. Cor e texto identificam as situações. Em telas pequenas, uma lista por data e sala oferece consulta mais simples. O formulário usa apenas datas, sem campos de horário ou turno. A grade destaca a ocupação prioritária ou confirmada e indica quantas opções em espera intersectam aquele período; abrir o detalhe mostra a lista e as equipes responsáveis.

Os anos de 2026, 2027 e 2028 devem estar acessíveis por navegação, sem construir três calendários isolados. Uma visão anual resumida é uma evolução opcional, não condição para a primeira versão. Deve ser possível localizar salas livres para um intervalo informado.

## 4. Dados e regras propostas

Entidades principais:

- **Empreendimento:** identificador e nome oficial.
- **Espaço/recurso físico:** identificador permanente independente do resort, empreendimento inicialmente opcional, nome original, localização, situação ativa/inativa e estado de validação física. A mudança de empreendimento preserva o identificador.
- **Configuração e composição:** nome da configuração, recursos físicos necessários e estado de validação do vínculo. Diferenciar composições explícitas, intervalos ambíguos e escolhas de módulos ainda não determinados.
- **Item de origem:** documento, código, página e descrição original; permite rastrear serviços e variantes sem convertê-los em espaços independentes.
- **Bloqueio/solicitação:** identificação do evento ou motivo, equipe proprietária, responsável, situação, prioridade ou instante de entrada na fila, observações, autoria, datas de criação/alteração e versão do registro.
- **Alocação/fase:** vínculo entre bloqueio, configuração escolhida, recursos físicos e intervalo de ocupação. Permite que um mesmo evento ocupe vários espaços e tenha períodos de montagem, evento e desmontagem, conforme regra a confirmar.
- **Usuário e acesso:** identidade individual, equipe, empreendimentos permitidos e permissões.
- **Histórico:** autor, instante, ação e valores alterados, inclusive cancelamento, mudança de situação e mudança de prioridade.

Campos comerciais como cliente, código de proposta e prazo de opção são candidatos, não requisitos confirmados. A fonte fornece medidas e capacidades por montagem: preservá-las como referência, sem recalcular ou presumir valores ausentes. As colunas de preços e reajustes não entram automaticamente no escopo do calendário.

Regras recomendadas, sujeitas à validação operacional:

1. Várias negociações podem se sobrepor, mas apenas uma alocação pode deter a ocupação efetiva de uma sala por dia. Uma tentativa conflitante pode ser registrada em espera, sem ser apresentada como reserva garantida. A classificação deve ser explícita no salvamento.
2. Situações candidatas: “Em opção prioritária”, “Em espera”, “Confirmado” e “Cancelado”. Proposta: opção prioritária e confirmado consomem disponibilidade; espera e cancelado não consomem. Esses nomes e efeitos ainda precisam de validação. “Livre” é disponibilidade calculada, não situação cadastrada manualmente. A ordenação inicial por data de entrada é uma proposta; não assumir essa regra como aprovada.
3. Cancelar libera a ocupação e mantém o histórico. Inativar uma sala preserva os bloqueios e o histórico anteriores.
4. Início e término precisam ser válidos. O intervalo permitido cobre de 01/01/2026 a 31/12/2028, inclusive, e aceita mudanças de mês e ano e 29/02/2028. Datas civis não devem mudar em função do fuso do computador.
5. A interface mostra a última data ocupada inclusiva; internamente pode-se usar fim exclusivo no dia seguinte. Assim, um bloqueio em 31/12/2028 pode ter fim interno em 01/01/2029 sem representar ocupação fora do escopo. Dois bloqueios que incluem o mesmo dia conflitam na ocupação efetiva.
6. Cada equipe só pode editar e cancelar solicitações próprias. Essa regra deve valer no servidor para qualquer tentativa de alteração; não basta ocultar botões. A equipe proprietária deve ser atribuída conforme a identidade autenticada, e não aceita como campo livre. Um acesso excepcional de administração depende de definição expressa.
7. Se houver montagem e desmontagem, elas também devem consumir a disponibilidade. Confirmar essa necessidade antes de fechar a regra de conflito.
8. A lista recebida contém salas combináveis. Mapear quais recursos físicos cada configuração ocupa, conforme a análise do PDF. Reservar uma configuração deve conflitar com seus componentes e com qualquer configuração que compartilhe um componente. O mesmo controle vale para a prioridade e a fila.
9. Se um evento exigir várias salas, validar e gravar todas as alocações em uma única transação. Proposta para o primeiro escopo: se não for possível obter o conjunto completo, a solicitação inteira fica em espera, sem ocupar parcialmente as salas. Essa regra requer validação com a operação.
10. Não expirar opções nem apagar bloqueios automaticamente sem regra definida pela operação.
11. Não promover uma solicitação em espera a confirmada automaticamente. Liberar uma sala exige reavaliar todo o período solicitado e, quando aplicável, todas as salas. Proposta: destacar a próxima candidata elegível para uma ação autorizada, que revalida os conflitos ao salvar.
12. A fila depende da interseção de datas e das salas solicitadas; não é uma única posição permanente por sala. Exemplo: uma solicitação de 10 a 12 e outra de 12 a 14 disputam o dia 12. Remover um concorrente não garante que todos os demais dias estejam livres. Uma reserva confirmada não deve perder ocupação por mera reordenação da fila.
13. Mudar prioridade entre equipes afeta direitos de terceiros. O responsável por essa ação e o procedimento de resolução precisam ser acordados antes de implementá-la; a permissão de editar o próprio bloqueio não autoriza passar à frente de outra equipe.
14. “Empreendimento a identificar” é uma pendência cadastral, separada da situação de uma solicitação. A regra de conflitos usa os IDs físicos globais, nunca apenas nome, resort ou a tela em que o item aparece. Um mesmo recurso não pode ser duplicado para aparecer nos dois resorts.
15. Um recurso com identidade e composição física validadas pode receber bloqueio mesmo com resort pendente, desde que o usuário tenha acesso à área comum de itens não classificados. Para os vínculos físicos ainda incertos, permitir consulta e solicitação pendente de validação; não conceder ocupação efetiva nem afirmar disponibilidade garantida. Não confundir essa pendência com uma posição de espera já elegível.
16. As 28 variantes da Arena Sauipe (códigos 90-117) devem apontar aos recursos físicos correspondentes. Montagem/evento/desmontagem e climatização não criam novas salas independentes. Não deduzir os módulos selecionados apenas pela quantidade contratada.
17. Os códigos 5 e 6 são serviços de mão de obra e não entram como espaços reserváveis. A referência “Por Turno” desses serviços não altera os bloqueios por dia inteiro.

## 5. Arquitetura recomendada

Navegadores das equipes → interface existente em HTML/CSS/JavaScript adaptada → serviço central em Python com Flask → banco relacional compartilhado.

Python com Flask é a escolha definida para o servidor, alinhada ao time de desenvolvimento. As versões suportadas e o banco relacional serão escolhidos conforme o ambiente da equipe. A interface continuará executando JavaScript no navegador e passará a consultar e gravar dados por uma API HTTP com respostas JSON. Não é necessário converter a interface para Python ou reescrevê-la em templates.

Organizar o Flask com uma função de criação da aplicação (`create_app`) e módulos de rotas (`Blueprints`) para acesso, salas, bloqueios e relatórios. Manter regras de negócio e transações fora das rotas, em serviços testáveis. Esse desenho permite separar configuração de desenvolvimento, testes e operação; segue o padrão de [fábricas de aplicação documentado pelo Flask](https://flask.palletsprojects.com/en/stable/patterns/appfactories/).

Flask fornece a base web; integração com banco, autenticação e validações serão implementadas com componentes compatíveis com o time, pois não são uma solução pronta de calendário incluída no framework. Essa separação é coerente com o [modelo extensível do Flask](https://flask.palletsprojects.com/en/stable/design/). A política de edição por equipe e a integridade da fila continuam sendo responsabilidade da aplicação e do banco.

Hoje, o Node.js apenas entrega os arquivos estáticos; não existe um serviço de dados em Node.js a ser traduzido. A evolução substituirá essa entrega por uma configuração compatível com a aplicação Python e implementará as regras operacionais e a persistência no servidor. Apenas trocar o servidor estático por um servidor Python não cria autenticação real nem compartilhamento de dados.

Uma aplicação única, com módulos separados para salas, bloqueios, disponibilidade, acesso e histórico, é suficiente para o escopo inicial. Não há justificativa identificada para microserviços ou uma troca obrigatória de framework de interface.

Na implementação, criar o projeto Python com dependências declaradas, configuração por ambiente, migrações do banco e testes das regras de negócio. Adaptar `storage.js` para a API e os fluxos da interface para operações assíncronas, com tratamento de carregamento, falha e conflito. Atualizar as instruções de execução e implantação para Python e retirar a dependência do servidor Node.js quando a substituição estiver validada. Os testes JavaScript existentes podem continuar como ferramenta de desenvolvimento; eles não substituem os testes do servidor Python nem tornam Node.js uma exigência do servidor operacional.

O banco central será a fonte oficial. `localStorage` pode guardar preferências de visualização, mas não determinar a disponibilidade compartilhada. Criar, alterar e cancelar devem ser operações individuais; o padrão atual de enviar e substituir a base inteira precisa ser abandonado para o uso por equipes.

O servidor verificará permissões, intervalos, elegibilidade na fila e conflitos em cada gravação. A checagem de disponibilidade e a escrita devem ser atômicas, com restrição de banco ou bloqueio transacional por recurso. Duas pessoas tentando obter ocupação efetiva para a mesma sala ao mesmo tempo não podem conseguir gravar duas ocupações incompatíveis; registrar outra solicitação em espera é permitido e deve ser informado claramente. O bloqueio de recursos deve considerar também eventuais divisões físicas.

Como a granularidade é diária, uma opção simples de implementação é materializar as ocupações efetivas por recurso físico e data, com unicidade no banco. Solicitações em espera ficam registradas sem consumir essas ocupações. Entrada na prioridade, confirmação, alteração de datas e cancelamento atualizam essas ocupações e o histórico na mesma transação. Esta é uma proposta técnica a validar na escolha do banco.

Alterações em registros já modificados por outra pessoa devem ser recusadas com informação clara e possibilidade de recarregar os dados; nunca sobrescritas silenciosamente. A interface deve mostrar a atualização dos dados e consultar novamente ao recuperar o foco e após gravações; a frequência de atualização será definida para o piloto. Falhas de conexão não podem ser apresentadas como salvamento concluído ou disponibilidade atual garantida.

O ambiente de uso precisará de endereço compartilhado, HTTPS, autenticação real e backup com restauração verificada. A infraestrutura e o mecanismo de identidade devem respeitar o ambiente disponível da empresa; ainda não foram escolhidos. Consulta, edição e administração são permissões candidatas, com escopo por empreendimento a confirmar.

Para disponibilizar a aplicação às equipes, usar um servidor WSGI de produção compatível com o ambiente, com depuração desativada; o servidor de desenvolvimento do Flask fica restrito ao desenvolvimento. Essa orientação também vale para uso interno, conforme a [documentação de implantação do Flask](https://flask.palletsprojects.com/en/stable/deploying/).

## 6. Cadastro recebido, classificação progressiva e preservação do trabalho atual

O PDF foi conferido nas duas páginas. A classificação preliminar contém 63 linhas de espaços sem composição explícita, 32 de combinações/configurações, 28 de variantes da Arena e 2 de serviços. Esses totais descrevem linhas da fonte, não inventário físico homologado. O catálogo preserva os nomes e códigos; empreendimento e componentes confirmados permanecem sem atribuição.

Implementar uma tela de revisão cadastral com código de origem, nome, grupo, tipo e pendências. As duas equipes autorizadas consultam o mesmo conjunto não classificado; a criação de solicitações continua vinculada à equipe autenticada. Um responsável cadastral poderá atribuir empreendimento e localização, individualmente ou em lote, com prévia dos itens atingidos e histórico de autoria/data. Esse papel cadastral não concede automaticamente permissão para editar bloqueios de outra equipe.

A classificação altera os metadados do recurso existente. Ela não cria cópia, apaga histórico, muda a equipe proprietária, datas, prioridade ou situação dos bloqueios. Preservar a referência permanente em todas as solicitações e exibi-las sob a nova classificação. Registrar no histórico a mudança de classificação e permitir corrigir erros pelo mesmo procedimento.

Revalidar permissões ao classificar um recurso caso o escopo de acesso dependa do resort. Não ampliar automaticamente o acesso a informações de eventos. A consulta comum dos itens sem resort deve mostrar apenas informações operacionais autorizadas. Em filtros de resort, informar a existência de itens ainda não classificados para não sugerir cobertura completa do inventário.

Mudanças de composição física ou fusões de possíveis duplicados são diferentes de atribuir resort: elas afetam conflitos e exigem revisão das ocupações existentes em transação, com rejeição de inconsistências. Não mesclar nomes parecidos automaticamente, como “Porto Seguro” (13) e “Porto Seguro 1” (62). Não inferir resort pelas cores ou pelo posicionamento das linhas.

A primeira carga deve ter prévia e relatório de inconsistências, identificadores estáveis e proteção contra duplicação ao repetir a importação. Importar a relação oficial de salas não significa importar bloqueios, salvo se os arquivos também contiverem esses dados.

Preservar o painel atual e seus backups. Os 12 registros de demonstração não devem ser convertidos em reservas. Qualquer dado real existente exige mapeamento explícito antes de uma migração. Uma restauração de backup da base compartilhada deve ser uma operação administrativa, não a substituição irrestrita oferecida hoje pelo mockup.

## 7. Etapas e critérios de conclusão

**Etapa 1 — Fechar o escopo:** revisar o catálogo extraído do PDF e suas composições, preparar a classificação progressiva sem resort presumido e detalhar situações, fila, montagem/desmontagem e acesso. Já estão definidos o bloqueio diário, a edição por equipe proprietária e as negociações concorrentes. Entrega: catálogo revisável, distinção entre itens aptos e pendentes de validação física e regras acordadas; classificar todos os resorts não é pré-requisito para desenvolver a solução.

**Etapa 2 — Validar a experiência:** adaptar a identidade para os dois empreendimentos e montar a grade, a consulta e o formulário. Dados de demonstração devem estar identificados. Entrega: fluxo navegável para avaliação; uma prévia local ainda não é a versão operacional compartilhada.

**Etapa 3 — Viabilizar uso compartilhado:** serviço central em Python com Flask, banco, contas individuais, regras de integridade, importação oficial, histórico e atualização de dados. Substituir o servidor Node.js, conectar a interface à API e atualizar as instruções de execução. Entrega: alterações visíveis em sessões independentes, respeitando permissões e sem dupla ocupação, sem depender de Node.js no servidor operacional.

**Etapa 4 — Integrar login corporativo e registros de acesso:** usar o Microsoft Entra ID, alimentado pelas identidades do Active Directory corporativo, para autenticação; validar a resposta no servidor e criar sessão própria com token opaco e revogação. Vincular a identidade corporativa às permissões da agenda e registrar eventos de acesso estruturados. Separar esses eventos do histórico de alterações de negócio e definir acesso, retenção e destino dos logs de aplicação. Entrega: acesso corporativo validado, sessões revogáveis e decisões de acesso rastreáveis, sem armazenar senhas ou tokens em claro. Detalhes e critérios em [AUTENTICACAO-E-LOGS.md](AUTENTICACAO-E-LOGS.md).

**Etapa 5 — Realizar piloto e entrega:** validar com representantes das duas equipes, testar exportação e impressão, verificar backup/restauração, exercitar os fluxos de autenticação e auditoria e orientar o uso. Entrega: operação aprovada com dados oficiais e rotina de suporte definida.

Critérios de aceitação essenciais:

- Consultar os dois resorts e qualquer data do intervalo 2026–2028, incluindo 29/02/2028.
- Exibir corretamente ocupações que atravessam mês e ano e períodos parcialmente visíveis na consulta.
- Criar, editar e cancelar respeitando a política de acesso acordada.
- Impedir duas ocupações efetivas nas criações, edições e promoções, inclusive com duas requisições simultâneas; permitir negociações em espera sobrepostas.
- Impedir que uma equipe altere bloqueios da outra, inclusive por chamada direta ao servidor.
- Exibir a espera e a prioridade claramente; não promover automaticamente após cancelamento nem deslocar uma reserva confirmada por reordenação.
- Reavaliar o período completo ao promover uma opção, incluindo sobreposições parciais com outras solicitações.
- Em múltiplas salas, não deixar ocupações parciais quando o conjunto não puder ser concedido, conforme a regra que for acordada.
- Mostrar em outro navegador uma alteração já salva no serviço central.
- Preservar autoria e histórico ao cancelar; não transformar rascunho em ocupação oficial.
- Exportar os bloqueios que intersectam o período consultado, com campos e situação coerentes com a tela.
- Importar as salas sem duplicação ou perda de nomes; manter os dados diante de arquivo inválido.
- Preservar um único recurso e todas as solicitações ao atribuir ou corrigir seu resort; conflito e prioridade não dependem dessa classificação.
- Exibir “A identificar” separadamente dos dois resorts; não apresentar itens ainda não classificados como cobertura confirmada de um resort.
- Impedir ocupação efetiva em configurações fisicamente indefinidas, mas permitir solicitação claramente pendente de validação.
- Impedir conflitos entre configurações e seus componentes; variantes da Arena não podem gerar disponibilidade duplicada e serviços não podem aparecer como salas.
- Validar permissões no servidor e comprovar restauração de backup antes do uso operacional.

Ficam fora do escopo inicial: integração com Opera Cloud, financeiro, contratos, pagamento, CRM completo, reservas recorrentes, notificações automáticas e migração automática para outro sistema. Qualquer necessidade dessas deve ser tratada separadamente.

## 8. Pendências para adoção pelas equipes

- Homologar identidades, composições e dependências físicas, especialmente Ouro Preto, conjuntos Gardênia, módulos/foyer da Arena e Salas numeradas.
- Classificar os resorts progressivamente e revisar a cobertura do inventário.
- Designar pessoas responsáveis pela fila e pelo cadastro; configurar os escopos de cada conta. A aplicação oferece essas permissões separadamente.
- Definir hospedagem, operação do PostgreSQL, número de usuários e configuração do aplicativo no Microsoft Entra ID. O banco PostgreSQL, o Flask e o provedor de login corporativo já estão confirmados.

A implementação não depende de identificar todos os resorts para aceitar solicitações. Conceder ocupação efetiva exige homologação física do item. O piloto local não foi publicado como serviço compartilhado.
