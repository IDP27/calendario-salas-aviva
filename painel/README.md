# Agenda de espaços — Costa do Sauípe & Rio Quente

Calendário provisório de salas, com bloqueios por dia inteiro entre 01/01/2026 e 31/12/2028. Flask entrega a interface e uma API autenticada; PostgreSQL é a fonte oficial. A aplicação é executada pelo Waitress, sem servidor Node.js.

O piloto funciona localmente. A implantação compartilhada para as equipes ainda depende do ambiente e do login corporativo definidos pelo time. As salas recebidas permanecem **a identificar e a validar**; a carga inicial não equivale à homologação do inventário.

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

O primeiro acesso cria a conta individual de administração. Escolha uma senha de pelo menos 12 caracteres. A primeira conta administra cadastros, pessoas e fila; isso não permite editar/cancelar solicitações de outra equipe. Não existe `admin/admin123` na aplicação nova.

## Preparar outra instalação

Requisitos validados neste piloto: Python 3.12, PostgreSQL 14.18 já existente na máquina e ferramentas `pg_dump`/`pg_restore`. O time deve definir a versão suportada do PostgreSQL para implantação. Dependências diretas fixadas: Flask 3.1.3, psycopg 3.3.6, Waitress 3.0.2.

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

Configuração:

| Variável | Uso |
| --- | --- |
| `DATABASE_URL` | Conexão PostgreSQL; mantenha credenciais fora do Git |
| `CALENDAR_PORT` | Porta local, padrão 4174 |
| `CALENDAR_SECRET_KEY` | Chave persistente de sessão; sem essa variável, usa `instance/secret-key` |
| `CALENDAR_SECURE_COOKIES` | `1` sob HTTPS; `0` no HTTP local |
| `CALENDAR_ALLOW_LOCAL_SETUP` | `1` permite primeiro acesso pelo loopback; use `0` após criar a conta e antes de expor por proxy |

Não sobrescreva um `.env` existente. Proteja o arquivo e `instance/secret-key`, com leitura restrita ao usuário do serviço. Variáveis já definidas no processo têm precedência sobre `.env`.

## Operar a agenda

1. Em **Salas & espaços**, consulte nomes, códigos da fonte e observações. As 125 linhas do PDF geram 99 espaços/configurações para revisão e 63 candidatos a recursos físicos. Os dois serviços ficam fora da agenda. As 28 variantes da Arena ficam rastreáveis sob quatro configurações, sem disponibilidade independente por fase ou climatização.
2. Use **Validar composição** somente após confirmação da operação. A sugestão extraída do nome não é homologação. Para Arena, cadastre os módulos físicos identificados e depois vincule os conjuntos permitidos. Configurações sem validação aceitam apenas pendências.
3. Para atribuir resort e localização, selecione um ou mais itens e clique em **Classificar seleção**. A tela mostra os itens que serão alterados. Registre a referência da classificação. Os IDs, as solicitações e o histórico são preservados.
4. Em **Nova solicitação**, informe evento/motivo, responsável, espaços, fases e datas. Inclua montagem e desmontagem como períodos. A equipe proprietária vem da conta. A data final é inclusiva; a aplicação aceita 29/02/2028 e passagens entre meses/anos.
5. Uma solicitação em espera entra na fila por ordem de entrada. O responsável da fila concede manualmente a opção prioritária após verificar o conjunto inteiro. Se alguma sala/dia estiver ocupado, nenhuma parte é concedida.
6. A própria equipe pode confirmar uma opção, editar seus registros e cancelar com motivo. O cancelamento libera a ocupação e mantém histórico. A fila não avança nem expira automaticamente.

| Situação | Ocupa recursos? | Observação |
| --- | --- | --- |
| Pendente de validação | Não | Admite composição ainda desconhecida; não tem prioridade elegível |
| Em espera | Não | Requer composição validada e conjunto físico escolhido |
| Em opção prioritária | Sim | Concessão manual por responsável da fila |
| Confirmado | Sim | Confirmação da opção pela equipe proprietária |
| Cancelado | Não | Histórico preservado; nova negociação exige nova solicitação |

A prioridade é relativa à interseção de recursos e dias. Uma solicitação anterior com conjunto integralmente disponível impede ultrapassagem; uma anterior impedida por ocupação em outra parte do conjunto permanece em espera. Alterar espaços/datas/fases de uma espera ou voltar à espera gera nova ordem de entrada. Alterar apenas o texto preserva a ordem. Expansões de uma opção/confirmado revalidam conflitos e prioridade nos novos dias/recursos.

A categoria **Empreendimento a identificar** representa um valor ainda não informado, não um terceiro resort. Um espaço fisicamente homologado pode receber ocupação nessa categoria por quem tenha acesso a ela. Os conflitos usam recursos físicos globais, mesmo após uma classificação posterior.

Na grade, hachura significa **a validar**, ponto indica ocupação efetiva e o contador mostra solicitações pendentes/em espera. A lista apresenta a situação por texto e cor. O filtro de situação filtra solicitações; ele nunca esconde ocupações físicas para fazer um dia parecer livre. O celular abre em lista. A atualização consulta o servidor a cada 20 segundos quando nenhum formulário/campo está em edição; também há **Atualizar agenda**. Falhas de conexão são sinalizadas.

## Pessoas e responsabilidades

Em **Pessoas & acessos**, a administração cria contas individuais, seleciona a equipe e define o escopo: Costa do Sauípe, Rio Quente e/ou área a identificar. Pode desativar contas e ajustar responsabilidades. Uma alteração de acesso encerra a validade das sessões anteriores. A equipe da conta não é um campo livre de edição de bloqueios.

- Usuário comum: consulta seu escopo e altera solicitações da própria equipe.
- Responsável cadastral: classifica espaços, revisa composições e importa a lista. Isso não concede edição de outra equipe.
- Responsável da fila: concede a opção prioritária às solicitações elegíveis no seu escopo, inclusive de outra equipe. Não pode editar o evento nem cancelar essa outra equipe.
- Administração de acessos: administra contas e escopos. Não altera o próprio acesso pela tela.

Os nomes das pessoas responsáveis por cadastro e fila devem ser designados pela operação. O login corporativo continua indefinido: o piloto usa contas locais reais, senhas com hash, sessões e proteção CSRF. Não há SSO nem recuperação de senha por e-mail.

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
