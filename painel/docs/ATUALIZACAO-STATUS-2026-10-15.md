# Atualização das situações de solicitação — 15/10/2026

Este documento descreve o comportamento **vigente** da agenda. A proposta e o relatório de implementação inicial em `docs/` registram decisões de etapas anteriores; quando citam pendência, espera ou opção prioritária como situações de reserva, prevalecem as regras abaixo e o [README](../README.md).

## Situações visíveis e efeito operacional

| Situação | Código na API/banco | Ocupa espaço? | Uso |
| --- | --- | --- | --- |
| Reservado | `reserved` | Não | Registra a solicitação e sua ordem na fila. Pode ser criado mesmo quando a composição física ainda não foi validada. Não garante disponibilidade futura. |
| Confirmado | `confirmed` | Sim | Bloqueia os dias e recursos de **todas** as alocações da solicitação, após revalidar disponibilidade e ordem da fila. |
| Cancelado | `cancelled` | Não | Libera as ocupações, conserva a solicitação e seu histórico. Para negociar novamente, crie outra solicitação. |

O filtro **Todas** consulta as três situações; não é uma quarta situação gravada. “A validar” identifica uma **composição física** pendente de homologação. Uma configuração pode estar a validar e ter solicitação Reservada ou, por exceção operada pelo responsável da fila, Confirmada. “Livre” e “sem ocupação efetiva” são resultados calculados da consulta de disponibilidade.

As fases **Montagem, Evento e Desmontagem** também não são situações. São períodos de uma mesma solicitação e todos são verificados juntos. As datas exibidas incluem o último dia; o banco armazena o limite final exclusivo em `allocations.end_exclusive`.

## Fluxo de trabalho e conflito

1. Uma pessoa cria a solicitação como **Reservado** e escolhe um ou mais espaços, fases e períodos. O servidor define equipe, autoria e posição na fila. A solicitação não grava linhas em `occupations`.
2. O servidor recusa criar ou mover uma reserva para espaço e período que já tenham confirmação conflitante. Reservas criadas antes de uma confirmação continuam registradas na fila; elas não são promovidas automaticamente.
3. Quem possui `can_schedule` pode confirmar uma solicitação Reservada, inclusive de outra equipe dentro de seu escopo. Nesse momento o servidor revalida todos os períodos, a ordem da fila e os conflitos. A transação confirma o conjunto inteiro ou não altera nada. O responsável da fila não ganha permissão para editar ou cancelar o evento de outra equipe.
4. A confirmação grava ocupação por recurso físico e dia em `occupations`. A chave `(resource_id, day)` impede duplicidade. Quando há uma única composição física validada, ela é aplicada na confirmação; se houver várias opções, a escolha deve constar da solicitação. A configuração confirmada sem topologia validada bloqueia a **configuração exata** no período, mas a detecção de conflito com outras configurações depende da futura validação física.
5. A equipe proprietária pode cancelar com motivo. O bloqueio é liberado e a trilha permanece; a fila não confirma outra solicitação automaticamente. O código atual também permite à equipe proprietária voltar uma confirmação para Reservado, liberando a ocupação. Essa regra ainda requer decisão operacional antes da implantação compartilhada.

A edição de espaços, fases ou datas de uma solicitação Reservada atribui nova posição na fila. Alterar apenas textos preserva a posição. Uma pessoa sem `can_schedule` não pode manter Confirmado enquanto altera alocações. O formulário e a API usam `version` para recusar gravação sobre uma edição mais recente.

## Onde as situações aparecem

- **Calendário:** a lista pode ser filtrada por situação, mas o filtro não oculta ocupações confirmadas da grade. Indicadores de pedidos Reservados não equivalem a bloqueio.
- **Solicitações & fila:** os três status e Todas filtram registros por ordem de entrada. O detalhe mostra histórico e ações permitidas.
- **Salas & espaços:** o filtro de situação mostra configurações com pelo menos uma solicitação correspondente no intervalo da agenda. A coluna de validação física é independente.
- **Relatórios e CSV:** os filtros por período, empreendimento, situação e pesquisa usam os mesmos códigos; o período considera qualquer alocação que o intersecte.
- **Consultar disponibilidade:** pedidos Reservados aparecem separados dos períodos Confirmados. Cancelados não ocupam o espaço. A consulta não cria nem confirma uma solicitação.

## Migração de instalações existentes

A migração `calendar_app/migrations/004_three_booking_statuses.sql` é aplicada depois das migrações `001` a `003` e registrada em `public.schema_migrations`. Ela altera o domínio de `bookings.status` e converte os registros existentes:

| Situação anterior | Nova situação | Ocupação existente |
| --- | --- | --- |
| `pending` | `reserved` | Sem bloqueio |
| `waiting` | `reserved` | Sem bloqueio |
| `option` | `confirmed` | **Mantida** |
| `confirmed` | `confirmed` | Mantida |
| `cancelled` | `cancelled` | Continua sem bloqueio |

A migração também atualiza o campo `status` das respostas JSON em `idempotency`, impedindo que o reenvio de uma criação antiga devolva um nome retirado. Ela **não reescreve** eventos já gravados em `audit`; esses eventos continuam representando o que ocorreu naquele momento. A migração não cria nem apaga ocupações. Instalações novas já nascem com o domínio atualizado após a sequência completa.

Antes de atualizar uma base existente, faça backup e teste a atualização **em uma cópia**. Na stack Compose atual, `docker/run.py` aplica migrações ao iniciar a nova imagem; subir a imagem é, portanto, uma alteração de banco. Depois da atualização, confira `public.schema_migrations`, a distribuição de status e as ocupações das confirmações antigas. Uma reversão de imagem não desfaz a migração: use o plano de restauração documentado no [README](../README.md#backup-e-recuperação).

Consulta de conferência no PostgreSQL, após a migração:

```sql
SELECT version FROM public.schema_migrations ORDER BY version;
SELECT status, count(*) FROM public.bookings GROUP BY status ORDER BY status;
SELECT count(*) AS ocupacoes FROM public.occupations;
```

Compare a última contagem com a cópia anterior à atualização. Confira também um caso que era `option`: deve estar Confirmado e ainda bloquear os mesmos recursos e dias.

## Verificação executada

Em 15/10/2026, passaram **58 testes Python** com PostgreSQL e **16 testes JavaScript**. A suíte cobre migração, transições, conflitos, ocupação, fila, permissões e filtros. Em uma prévia visual descartável, foi criada uma solicitação Reservada para Bahia 1, confirmada, recusada outra reserva conflitante, cancelada a confirmação e criada nova reserva no mesmo período. A consulta de disponibilidade e os filtros em Solicitações & fila, Relatórios e Salas & espaços refletiram cada estado. O esquema fictício foi removido ao encerrar a prévia.

Essa verificação não homologa a composição física do catálogo, o login no tenant Entra ID real, a carga esperada nem a implantação no servidor Linux da equipe. Esses aceites continuam descritos no README.
