# Agenda de espaços — Costa do Sauípe & Rio Quente

Calendário provisório de salas, com bloqueios por dia inteiro entre 01/01/2026 e 31/12/2028. Flask entrega a interface e uma API autenticada; PostgreSQL é a fonte oficial. A aplicação é executada pelo Waitress, sem servidor Node.js.

O piloto funciona localmente. A implantação compartilhada para as equipes ainda depende do ambiente e da integração com o login corporativo. As relações enviadas em 08/10/2026 identificam espaços da **Costa do Sauípe** e do **Rio Quente**; as composições físicas continuam **a validar**. A identificação do empreendimento não equivale à homologação do inventário.

O código já inclui a integração de login via Microsoft Entra ID, sessões revogáveis com token opaco e registros de acesso. O piloto local continua usando contas locais até receber os dados de registro da aplicação no tenant corporativo; a entrada real pelo Entra ID ainda não foi homologada. O desenho e a situação detalhada estão em [docs/AUTENTICACAO-E-LOGS.md](docs/AUTENTICACAO-E-LOGS.md).

Após esta atualização, reinicie a aplicação se ela já estiver aberta. As sessões antigas em cookie assinado não são convertidas; cada pessoa precisa entrar novamente. O banco local já recebeu a migração, precedida pelo backup `instance/backups/pre-auth-2026-10-13.dump`.

## Executar neste computador

O ambiente Python e o banco local já foram preparados. Na pasta `painel`, caso o PostgreSQL local esteja parado:

```sh
pg_ctl -D instance/postgres -l instance/postgres.log -o '-h 127.0.0.1 -p 55432 -k /private/tmp' start
```

Inicie a aplicação:

```sh
.venv/bin/python serve.py
```

Acesse **http://127.0.0.1:4174**. Se a agenda já estiver aberta, não é necessário iniciar outro servidor. `Ctrl+C` encerra a aplicação; o banco permanece ativo. Para encerrar o banco dedicado, use `pg_ctl -D instance/postgres stop` quando não houver usuários conectados.

O primeiro acesso cria a conta individual de administração. Escolha uma senha de 15 a 128 caracteres. Frases-senha, espaços e caracteres Unicode são aceitos; não há exigência de misturar tipos de caracteres. O piloto rejeita uma lista local inicial de senhas óbvias e a própria identificação do usuário; uma checagem ampla de credenciais vazadas depende de integração futura com serviço ou lista corporativa. A primeira conta administra cadastros, pessoas e fila; isso não permite editar/cancelar solicitações de outra equipe. Não existe `admin/admin123` na aplicação nova. Senhas já cadastradas continuam válidas no login até que seus titulares as alterem; a nova regra se aplica à criação e à troca de senha.

## Preparar outra instalação

Requisitos validados neste piloto: Python 3.12 e 3.13, PostgreSQL 14.18 já existente na máquina e ferramentas `pg_dump`/`pg_restore`. O time deve definir a versão suportada do PostgreSQL para implantação. Dependências diretas fixadas: Flask 3.1.3, psycopg 3.3.6, Waitress 3.0.2.

### Instalar com Poetry

O projeto pode usar Poetry 2 para gerenciar dependências. O arquivo `poetry.lock` fixa as versões resolvidas; o modo sem pacote instala somente as dependências, pois esta agenda é executada diretamente com `serve.py`. Instale o Poetry e, na pasta `painel`, com Python 3.13 disponível:

```sh
export POETRY_VIRTUALENVS_IN_PROJECT=false
export POETRY_VIRTUALENVS_PATH="$PWD/instance/poetry-envs"
poetry env use python3.13
poetry sync
poetry run python -m pytest tests_python -q
poetry run python serve.py
```

As duas variáveis mantêm o ambiente do Poetry separado do `.venv` preexistente. Neste computador, o executável do Poetry está em `instance/poetry-cli/bin/poetry`; use esse caminho no lugar de `poetry` se ele não estiver no `PATH`. Para os comandos administrativos, use `poetry run flask --app calendar_app <comando>`. O ambiente de desenvolvimento local que já usa `.venv` pode continuar com `pip`; mantenha as versões de `requirements*.txt` e `pyproject.toml` alinhadas ao atualizar dependências.

### Instalar com pip

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Crie um banco PostgreSQL dedicado e ajuste `DATABASE_URL` no `.env`. A aplicação não cria um serviço de banco corporativo. O papel do banco precisa executar as migrações iniciais; em implantação, separe o papel de migração do papel de execução conforme a política da equipe.

```sh
.venv/bin/flask --app calendar_app init-db
.venv/bin/flask --app calendar_app import-catalog docs/catalogo-salas-preliminar.json --preview
.venv/bin/flask --app calendar_app import-catalog docs/catalogo-salas-preliminar.json
.venv/bin/python serve.py
```

`init-db` aplica apenas migrações ainda não registradas. A importação é transacional e repetível sem duplicar itens ou substituir revisões já feitas. O auxiliar `scripts/prepare_local.py` é exclusivo do banco local chamado `calendario`.

### Relação revisada da Costa do Sauípe

O arquivo `docs/classificacao-costa-sauipe-2026-10-08.json` registra os códigos da fonte associados à lista enviada pelo usuário e às confirmações posteriores de Bahia 1–2 e das quatro configurações de São Tomé. Há 114 linhas da fonte que representam 90 configurações da agenda, pois 28 variantes da Arena compartilham quatro configurações. Os serviços 5 e 6 continuam fora da agenda. A classificação é auditada e preserva IDs, localização, solicitações e validação física. Pode ser repetida sem duplicar alterações.

```sh
.venv/bin/flask --app calendar_app classify-reviewed docs/classificacao-costa-sauipe-2026-10-08.json
.venv/bin/flask --app calendar_app backup-db instance/backups/antes-classificacao-sauipe.dump
.venv/bin/flask --app calendar_app classify-reviewed docs/classificacao-costa-sauipe-2026-10-08.json --apply
```

Sem `--apply`, o comando apenas mostra uma prévia. Ele recusa classificar parcialmente uma configuração compartilhada, como a Arena, ou mover para Sauípe um item já atribuído ao Rio Quente. Após a aplicação da relação de Sauípe, nove configurações da relação do Rio Quente aguardam classificação. As quatro configurações de São Tomé foram confirmadas para Sauípe por mensagem posterior; a segunda linha escrita como “São Tomé 1–2” no texto inicial descrevia 1–2–3. “Santa Amaro” foi associado ao nome original “Santo Amaro”, preservado no catálogo.

### Relação revisada do Rio Quente

O arquivo `docs/classificacao-rio-quente-2026-10-08.json` identifica Gardênia, Canário, Aimorés, Amazonas, três configurações de união do grupo, Jubarte e Maremoto: nove configurações no total. Execute após a classificação da Costa do Sauípe. Os códigos omitidos na segunda relação só são aceitos quando já têm empreendimento, evitando deixar itens sem destino por engano.

```sh
.venv/bin/flask --app calendar_app classify-reviewed docs/classificacao-rio-quente-2026-10-08.json
.venv/bin/flask --app calendar_app backup-db instance/backups/antes-classificacao-rio-quente.dump
.venv/bin/flask --app calendar_app classify-reviewed docs/classificacao-rio-quente-2026-10-08.json --apply
```

Depois das duas relações, são 90 configurações da Costa do Sauípe e nove do Rio Quente; todas têm empreendimento. As composições físicas de São Tomé e dos conjuntos de dois e três módulos do Rio Quente continuam sem validação operacional. A classificação do empreendimento, sozinha, não libera bloqueios efetivos.

Configuração:

| Variável | Uso |
| --- | --- |
| `DATABASE_URL` | Conexão PostgreSQL; mantenha credenciais fora do Git |
| `CALENDAR_PORT` | Porta local, padrão 4174 |
| `CALENDAR_SECRET_KEY` | Chave persistente de sessão; sem essa variável, usa `instance/secret-key` |
| `CALENDAR_SECURE_COOKIES` | `1` sob HTTPS; `0` no HTTP local |
| `CALENDAR_ALLOW_LOCAL_SETUP` | `1` permite primeiro acesso pelo loopback; use `0` após criar a conta e antes de expor por proxy |
| `CALENDAR_AUTH_MODE` | `local` no piloto ou `entra` para login corporativo |
| `CALENDAR_AUTH_SESSION_HOURS`, `CALENDAR_AUTH_IDLE_MINUTES` | Prazo absoluto e limite de inatividade da sessão; padrões provisórios de 8 horas e 60 minutos |
| `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET` | Registro da aplicação web no tenant Microsoft Entra ID |
| `ENTRA_REDIRECT_URI` | URL HTTPS registrada no Entra ID, terminada em `/api/entra/callback` |

### Ativar o login corporativo

Peça à equipe de identidade o **Tenant ID**, **Client ID**, segredo do aplicativo e registro da URL de retorno da agenda como aplicação web. Configure `CALENDAR_AUTH_MODE=entra`, `CALENDAR_SECURE_COOKIES=1`, `CALENDAR_ALLOW_LOCAL_SETUP=0` e as quatro variáveis `ENTRA_*` no ambiente do servidor, sob HTTPS. Execute `init-db` antes de ativar o novo código na base existente. A aplicação recusa iniciar esse modo se faltar configuração ou HTTPS.

Em uma base nova, vincule a primeira pessoa administradora pelo Object ID do Entra ID:

```sh
.venv/bin/flask --app calendar_app init-db
.venv/bin/flask --app calendar_app bootstrap-entra --username pessoa@empresa.com --name "Nome da pessoa" --team commercial --object-id UUID-DA-PESSOA
```

Em uma base que já tem usuários do piloto, vincule cada registro existente para preservar seu ID e histórico:

```sh
.venv/bin/flask --app calendar_app link-entra --username usuario-existente --object-id UUID-DA-PESSOA
```

No modo corporativo, o login e a troca de senha locais ficam desativados. A administração pode cadastrar novas pessoas com o Object ID do Entra ID, equipe, empreendimento e responsabilidades. Apenas identidades vinculadas e ativas acessam a agenda; o retorno do provedor não concede permissão automaticamente. `auth_sessions` guarda somente hash do verificador do token, `auth_events` guarda os eventos de acesso e `audit` mantém o histórico de alterações. Administradores consultam os 300 eventos de acesso mais recentes em `GET /api/audit/auth`; a limpeza de sessões e contadores vencidos pode ser agendada com `flask --app calendar_app prune-auth`. O prazo de retenção de `auth_events` depende da política da organização.

Não sobrescreva um `.env` existente. Proteja o arquivo e `instance/secret-key`, com leitura restrita ao usuário do serviço. Variáveis já definidas no processo têm precedência sobre `.env`.

## Operar a agenda

1. Em **Salas & espaços**, consulte nomes, códigos da fonte e observações. As 125 linhas do PDF geram 99 espaços/configurações para revisão e 63 candidatos a recursos físicos. Os dois serviços ficam fora da agenda. As 28 variantes da Arena ficam rastreáveis sob quatro configurações, sem disponibilidade independente por fase ou climatização.
2. Use **Validar composição** somente após confirmação da operação. A sugestão extraída do nome não é homologação. Para Arena, cadastre os módulos físicos identificados e depois vincule os conjuntos permitidos. Configurações sem validação aceitam solicitações pendentes e confirmações feitas pelo responsável da fila. Nestas confirmações, o bloqueio garante exclusividade da configuração escolhida; conflitos com outras configurações combinadas dependem da validação física.
3. Para atribuir resort e localização, selecione um ou mais itens e clique em **Classificar seleção**. A tela mostra os itens que serão alterados. Registre a referência da classificação. Os IDs, as solicitações e o histórico são preservados.
4. Em **Nova solicitação**, informe evento/motivo, responsável, espaços, fases e datas. Inclua montagem e desmontagem como períodos. A equipe proprietária vem da conta. A data final é inclusiva; a aplicação aceita 29/02/2028 e passagens entre meses/anos.
5. Uma solicitação em espera entra na fila por ordem de entrada. O responsável da fila concede manualmente a opção prioritária após verificar o conjunto inteiro. Ele também pode confirmar a reserva na tela da solicitação ou marcar **Confirmar reserva e bloquear o espaço** ao salvar uma solicitação da própria equipe. A confirmação bloqueia todos os espaços e dias da solicitação de forma atômica: se algum já estiver reservado, nada é confirmado. **Consultar disponibilidade** mostra as datas das solicitações e dos bloqueios, distinguindo pendências de reservas confirmadas e indicando ocupações de configurações compartilhadas.
6. Apenas o responsável da fila confirma bloqueios. A equipe proprietária pode editar os dados do seu registro e cancelar com motivo; alterações de espaço ou período já confirmados exigem o responsável da fila. O cancelamento libera a ocupação e mantém histórico. A fila não avança nem expira automaticamente.

| Situação | Ocupa recursos? | Observação |
| --- | --- | --- |
| Pendente de validação | Não | Admite composição ainda desconhecida; não tem prioridade elegível |
| Em espera | Não | Requer composição validada e conjunto físico escolhido |
| Em opção prioritária | Sim | Concessão manual por responsável da fila |
| Confirmado | Sim | Confirmação da opção pela equipe proprietária |
| Cancelado | Não | Histórico preservado; nova negociação exige nova solicitação |

A prioridade é relativa à interseção de recursos e dias. Uma solicitação anterior com conjunto integralmente disponível impede ultrapassagem; uma anterior impedida por ocupação em outra parte do conjunto permanece em espera. Alterar espaços/datas/fases de uma espera ou voltar à espera gera nova ordem de entrada. Alterar apenas o texto preserva a ordem. Expansões de uma opção/confirmado revalidam conflitos e prioridade nos novos dias/recursos.

Os filtros exibem **Todos**, **Costa do Sauípe** e **Rio Quente**. A categoria provisória de identificação foi retirada da interface após a classificação dos 99 espaços/configurações. O valor vazio permanece apenas como estado interno para uma eventual importação futura; um responsável cadastral precisa atribuir um dos dois empreendimentos antes de criar novos recursos ou alterar a classificação pela aplicação. Os conflitos continuam usando recursos físicos globais.

Na grade, hachura significa **a validar**, ponto indica ocupação efetiva e o contador mostra solicitações pendentes/em espera. A lista apresenta a situação por texto e cor. O filtro de situação filtra solicitações; ele nunca esconde ocupações físicas para fazer um dia parecer livre. O celular abre em lista. A atualização consulta o servidor a cada 20 segundos quando nenhum formulário/campo está em edição; também há **Atualizar agenda**. Falhas de conexão são sinalizadas.

**Consultar disponibilidade** mostra separadamente a ocupação efetiva e a quantidade de solicitações pendentes ou em espera que intersectam o período. Uma solicitação pendente, como a de uma configuração ainda não validada, fica visível na consulta, mas não aparece como bloqueio confirmado. Somente a opção prioritária e a confirmação ocupam recursos físicos.

## Pessoas e responsabilidades

Em **Pessoas & acessos**, a administração cria contas individuais, seleciona a equipe e define o escopo: Costa do Sauípe e/ou Rio Quente. Pode desativar contas e ajustar responsabilidades. Uma alteração de acesso encerra a validade das sessões anteriores. A equipe da conta não é um campo livre de edição de bloqueios.

- Usuário comum: consulta seu escopo e altera solicitações da própria equipe.
- Responsável cadastral: classifica espaços, revisa composições e importa a lista. Isso não concede edição de outra equipe.
- Responsável da fila: concede a opção prioritária às solicitações elegíveis no seu escopo, inclusive de outra equipe. Não pode editar o evento nem cancelar essa outra equipe.
- Administração de acessos: administra contas e escopos. Não altera o próprio acesso pela tela.

Os nomes das pessoas responsáveis por cadastro e fila devem ser designados pela operação. O piloto ainda usa contas locais reais, senhas com hash, sessões revogáveis e proteção CSRF. O modo Entra ID depende da configuração e homologação com o tenant corporativo; recuperação de senha continua a cargo da identidade corporativa.

Criação administrativa por terminal, com senha solicitada sem exibição:

```sh
.venv/bin/flask --app calendar_app create-user --admin
```

## Relatórios

Selecione empreendimento, situação, pesquisa e período em **Relatórios**. São incluídas as alocações que intersectam os filtros e as datas. O CSV usa UTF-8 com BOM, ponto e vírgula e neutralização de fórmulas. **Imprimir / PDF** prepara o relatório e abre a impressão do navegador; escolha salvar como PDF. CSV é uma consulta legível, não um backup completo.

## Backup e recuperação

Use ferramentas PostgreSQL compatíveis com a versão do servidor, disponíveis no PATH. O backup inclui cadastros, contas com hashes, solicitações, ocupações, histórico e migrações do esquema da aplicação. Não inclui arquivos, papéis globais do PostgreSQL ou configuração de infraestrutura. Guarde separadamente o código, `.env` e a chave de sessão em local protegido. Defina retenção e cópia externa com o time antes do uso compartilhado; não há agendamento automático nesta entrega.

```sh
.venv/bin/flask --app calendar_app backup-db instance/backups/calendario-2026-10-07.dump
```

O comando recusa sobrescrever arquivos existentes. O arquivo é criado com permissões restritas. Faça backup antes de migrações.

Para recuperar, o administrador cria **outro banco vazio**, configura `RESTORE_DATABASE_URL` com a conexão desse destino no ambiente do terminal e executa:

```sh
.venv/bin/flask --app calendar_app restore-db instance/backups/calendario-2026-10-07.dump
```

A restauração usa uma única transação e recusa banco que já contenha tabelas de aplicação. Confira contagens, histórico e ocupações no destino. Só depois interrompa a aplicação, troque `DATABASE_URL` e reinicie. Preserve a origem até encerrar a validação. O teste automatizado realiza backup e restauração reais em bancos temporários, incluindo proteção contra sobrescrita.

## Testar

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests_python -q --tb=short
node --test tests/model.test.mjs
node --check dist/js/calendar.js
```

Os testes Python criam esquemas isolados por teste no `TEST_DATABASE_URL` ou, na ausência dele, no `DATABASE_URL`. Os testes de recuperação criam e removem bancos temporários com prefixo de teste, exigindo `CREATEDB`; execute-os em ambiente de desenvolvimento. Não há SQLite. Node é usado apenas para verificar JavaScript e os nove testes preservados do painel anterior.

Para uma prévia visual descartável, `scripts/qa_preview.py` cria um esquema separado, disponibiliza a porta 4175 apenas no loopback e exibe aviso de dados fictícios. As contas e validações de teste nunca são inseridas no esquema operacional. O script limpa seu próprio esquema ao ser encerrado normalmente. Não use essa prévia como ambiente de equipe.

## Estrutura e preservação

- `calendar_app/`: fábrica Flask, autenticação, regras cadastrais e de bloqueios, API, persistência e comandos administrativos.
- `calendar_app/migrations/`: migrações PostgreSQL versionadas.
- `dist/`: interface adaptada, estilos originais reaproveitados e comunicação assíncrona com a API.
- `docs/`: proposta, análise da fonte, catálogo preliminar e relatório de implementação.
- `tests_python/`: testes de integração com banco e API.
- `legacy/`: cópia preservada do painel anterior, incluindo seu servidor estático e instruções históricas.

O painel antigo pode ser consultado em `/legacy/`. Os dados `localStorage` pertencem à origem e ao perfil do navegador: a nova porta não copia os dados da antiga. Para recuperar uma base antiga, execute `node legacy/server.mjs` na porta original e exporte o JSON pelo próprio painel. Não importe exemplos como reservas. Uma migração real exige mapeamento e validação explícitos.

## Implantação compartilhada

A aplicação usa `create_app`, Blueprints e Waitress com depuração desativada, seguindo a documentação oficial de [fábricas Flask](https://flask.palletsprojects.com/en/stable/patterns/appfactories/) e [implantação WSGI](https://flask.palletsprojects.com/en/stable/deploying/). `serve.py` escuta apenas `127.0.0.1`. Para uso pelas equipes, o time deve provisionar servidor, PostgreSQL, HTTPS/proxy, chave persistente, monitoramento e backup, além de definir a identidade corporativa. Desabilite o primeiro acesso por navegador antes de disponibilizar via proxy.

As mutações são serializadas por transação no piloto; a chave única recurso/dia também impede dupla ocupação no banco. Isso favorece integridade para uma agenda pequena. Volume e desempenho em produção não foram medidos. Não há implantação pública nem integração com Opera Cloud nesta entrega.

## Identidade visual Aviva — 8 de outubro de 2026

O logo e o fundo fornecidos pelo solicitante estão em `dist/assets/aviva-logo.png` e `dist/assets/aviva-background.jpg`, preservados integralmente. O tema em `dist/aviva.css` aplica azul-petróleo, ciano, verde, lima e laranja ao acesso, menu, botões e indicadores, com superfícies brancas para formulários e calendário. As cores são baseadas nas imagens recebidas; não foi fornecido um manual de marca. O tema fica separado dos estilos de estrutura para facilitar manutenção.

Logo com proporção original, leitura em computador/celular, ausência de transbordamento horizontal e carregamento dos arquivos conferidos no navegador. A agenda foi inspecionada no ambiente de teste isolado; esta atualização é apenas visual. Prévias: `docs/aviva-login-desktop.jpg`, `docs/aviva-login-mobile.jpg` e `docs/aviva-calendar-desktop.jpg`.
