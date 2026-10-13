# Etapa 4 — autenticação, tokens e registros de acesso

## Ponto de partida do piloto

Antes desta etapa, o piloto usava contas locais e senhas com hash. O Flask enviava uma sessão assinada em cookie com duração configurada de oito horas; a aplicação verificava o usuário ativo e sua versão em cada requisição, usava token CSRF para alterações e limitava tentativas de login por origem e usuário. Logout limpava o cookie do navegador. A tabela `audit` no PostgreSQL registrava alterações de solicitações, catálogo, usuários e senha; `login_attempts` guardava apenas contadores temporários para limitação de tentativas. Faltavam trilha persistente de sucessos, falhas e encerramentos de login e revogação individual de sessões no servidor.

**Decisão para produção:** o login será corporativo, via Microsoft Entra ID, com identidades sincronizadas a partir do Active Directory. A sincronização do AD e a verificação de senhas pertencem à infraestrutura corporativa; a agenda não receberá nem armazenará a senha do colaborador.

As sessões locais usam, por padrão provisório, oito horas de duração absoluta e 60 minutos de inatividade. Os dois limites são configuráveis no ambiente; a equipe deve aprovar seus valores para produção.

## Fluxo corporativo e sessão local

1. **Entrada corporativa:** registrar a agenda como aplicação web no tenant corporativo do Microsoft Entra ID. Redirecionar o navegador para o login Microsoft usando OpenID Connect e fluxo de código de autorização com PKCE. A aplicação não apresenta campo de senha corporativa, não consulta o AD por LDAP e não sincroniza hashes de senha.
2. **Validação do retorno:** conferir `state`, `nonce`, código de uso único e resposta do provedor. Validar assinatura, emissor, público, tenant e validade do token de identidade. Identificar a pessoa pelo par estável `tid` + `oid`, sem usar e-mail ou nome de usuário como chave permanente. Rejeitar identidades de outro tenant e contas não autorizadas para a agenda.
3. **Vínculo e permissões:** associar `tid` + `oid` a um usuário da agenda, preservando IDs e histórico dos registros existentes. Definir com a equipe se o acesso inicial será concedido por atribuição à aplicação, grupo corporativo ou aprovação administrativa. Escopo por empreendimento e responsabilidades de cadastro/fila continuam verificados no servidor. O retorno do Entra ID não concede automaticamente privilégio administrativo.
4. **Criação da sessão:** após autenticação e autorização, gerar um token opaco e aleatório, independente da senha e dos tokens do Entra ID. Enviá-lo somente em cookie `HttpOnly`, `Secure` e `SameSite`, com escopo restrito à aplicação. Guardar no PostgreSQL apenas o verificador criptográfico do token, associado a usuário, criação, último uso, vencimento absoluto, vencimento por inatividade e estado de revogação. Não usar `localStorage`, URL ou log para transportar o token.
5. **Validação de cada requisição:** conferir o token de sessão local com o verificador, os dois prazos, a revogação, a conta ativa, a versão de acesso, o escopo e a permissão da ação. Manter a proteção CSRF nas operações que alteram dados. O cliente recebe `401` para sessão ausente ou vencida e `403` para ação sem autorização.
6. **Saída e revogação:** logout revoga a sessão local no banco e expira o cookie. Confirmar com a equipe se a saída também deve encerrar a sessão de SSO no Entra ID; encerrar apenas a sessão local não encerra necessariamente o login corporativo no navegador. Desativação ou alteração de acesso na agenda revogam as sessões afetadas conforme a política definida. Uma função administrativa poderá encerrar sessões de um usuário sem apagar o histórico.
7. **Limpeza e migração:** remover sessões e contadores vencidos em rotina programada, preservando os eventos de segurança pelo prazo de retenção aprovado. Após a homologação do login corporativo, desativar os endpoints de login e troca de senha locais em produção. Tratar o eventual acesso administrativo de emergência por política explícita da equipe de segurança.

Para a interface web atual, o cookie de sessão com token opaco atende ao fluxo. O token de identidade do Entra ID serve para comprovar o login no retorno do provedor; ele não substitui a sessão local e não deve ser exposto ao JavaScript da página. JWT ou refresh token próprios da agenda só devem ser especificados se surgir um cliente externo ou integração que exija esse formato; nesse caso, documentar público, escopos, emissão, rotação e revogação antes de implementar.

## Proteção contra injeção nas integrações

As consultas PostgreSQL atuais usam parâmetros separados do texto SQL para valores recebidos da interface (`execute(..., valores)`). Os nomes de esquema variáveis são compostos com `psycopg.sql.Identifier`. Preservar esse padrão em todas as tabelas e buscas novas de sessões, eventos e identidade: nunca concatenar ou interpolar usuário, filtro, data, identificador, grupo ou campo de log em uma instrução SQL. Identificadores SQL dinâmicos, inclusive colunas de ordenação, exigem lista fixa de opções permitidas e composição com `Identifier`. Validação de formato e tamanho complementa a parametrização, mas não a substitui.

Na implantação, separar a conta que aplica migrações da conta usada pela aplicação. A conta de execução deve ter apenas as permissões necessárias nas tabelas e operações da agenda. Revisar cada nova consulta e testar entradas com aspas, comentários SQL, curingas e Unicode, verificando que são tratadas como dados e não mudam a estrutura nem o alcance da consulta. Os arquivos de migração são código versionado, executado somente pelo processo administrativo.

Se a equipe escolher autenticação direta no AD local no lugar do Entra ID, acrescentar proteção específica contra **injeção LDAP**: usar uma biblioteca que escape valores de filtros conforme RFC 4515 e componentes de DN conforme RFC 4514, nunca interpolar o nome digitado em um filtro ou DN, rejeitar senha vazia e restringir a conta de consulta do diretório. Essa decisão altera o fluxo de autenticação descrito acima e precisa ser registrada antes da implementação.

## Onde ficam os registros

| Dado | Destino proposto | Conteúdo |
| --- | --- | --- |
| Sessões ativas | Nova tabela `auth_sessions` no PostgreSQL | Usuário, identificador público, hash do verificador, prazos, último uso e revogação. O token completo não é persistido. |
| Eventos de segurança da agenda | Nova tabela `auth_events` no PostgreSQL | Horário UTC, tipo de evento, resultado, usuário quando conhecido, identificador de correlação, origem tratada e motivo padronizado. Inclui início e retorno do SSO, validação aceita/recusada, logout local, expiração, revogação e acesso negado. |
| Tentativas de senha e políticas corporativas | Logs do Microsoft Entra ID, sob gestão da equipe de identidade | Falhas de senha, MFA, bloqueios e decisões de acesso condicional no provedor. A agenda registra apenas o resultado recebido ou uma falha de retorno; não inventa o motivo interno do Entra ID. |
| Alterações de negócio | Tabela `audit` existente no PostgreSQL | Quem alterou qual entidade, quando e os dados anteriores/posteriores permitidos. Continua separada dos eventos de login. |
| Falhas técnicas e operação | Log estruturado da aplicação, enviado à saída do processo e recolhido pelo ambiente de hospedagem | Erros de aplicação e banco, tempo de resposta e identificador de correlação, sem corpo de requisição, cookie, credenciais ou dados desnecessários. |

O banco compartilhado é a fonte consultável dos eventos de acesso e do histórico de negócio. A hospedagem deverá coletar os logs técnicos em destino central com acesso restrito e rotação. A escolha desse destino, o prazo de retenção de cada categoria, o tratamento de IP e os responsáveis por consulta/exportação dependem da política de segurança e privacidade da organização; devem ser definidos antes da implantação. Backups devem incluir `audit` e `auth_events` e proteger seus dados em repouso e no acesso.

## Validação da etapa

- Login corporativo válido e usuário autorizado criam uma nova sessão; conta sem vínculo ou permissão recebe acesso negado sem criar sessão.
- Retorno OIDC com `state`, `nonce`, assinatura, emissor, público, tenant ou validade incorretos é rejeitado e gera evento seguro. Uma resposta válida de outro tenant também é rejeitada.
- Token ausente, alterado, expirado ou revogado não concede acesso. Logout invalida a sessão no servidor, inclusive se o cookie antigo for reenviado.
- Usuário desativado ou com acesso alterado na agenda perde as permissões anteriores. Para desativação ou mudança de senha no diretório, testar o mecanismo e o prazo de propagação/revogação acordados com a equipe de identidade.
- Escopo e permissão são verificados para cada operação, independentemente do que a interface mostre.
- Erros de retorno, acesso negado e revogação ficam rastreáveis com horário e correlação. Falhas de senha, MFA e bloqueio corporativo são consultados nos registros do Entra ID.
- Registros e backups não contêm senha, token em claro, cookie de sessão nem cabeçalho `Authorization`.
- Testes cobrem expiração por inatividade e absoluta, sessões simultâneas, revogação, CSRF, concorrência e restauração dos registros.
- Testes de injeção comprovam que valores maliciosos nos campos de login, busca, solicitações e filtros de auditoria não modificam comandos SQL; se houver integração direta ao AD, cobrem também os filtros LDAP.

## Definições necessárias com a equipe

1. Tenant Entra ID, responsável pelo registro da aplicação, URLs de retorno, credenciais do aplicativo, grupos/atribuições autorizados e ambiente de homologação.
2. Regra de vínculo das contas existentes com `tid` + `oid`, atualização de nome/equipe/escopos e tratamento de contas desativadas no AD/Entra ID.
3. Duração absoluta, limite de inatividade, política para sessões simultâneas, revogação após mudança no diretório e comportamento de saída do SSO.
4. Destino central dos logs técnicos, acesso aos logs do Entra ID, responsáveis por consulta, alertas e prazos de retenção de sessões, eventos e histórico.
5. Tratamento de dados pessoais nos eventos de acesso e requisitos internos para exportação e descarte.

**Situação da implementação:** as tabelas, sessões com token opaco, revogação, eventos de acesso, endpoint de consulta administrativa e fluxo OIDC/PKCE do Entra ID já estão no código. O login local do piloto foi preservado em modo `local`. Os fluxos locais e o retorno corporativo simulado foram testados. A entrada real no tenant corporativo, a política de retenção e o coletor central dos logs técnicos ainda dependem da infraestrutura e da equipe de identidade.
