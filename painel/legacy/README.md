# Painel de Registros

Mockup funcional e local em HTML5, CSS3 e JavaScript puro, sem dependências externas. O servidor Node.js apenas entrega os arquivos estáticos; as funções e os dados ficam no navegador.

## Executar

Com Node.js 20 ou superior instalado, abra um terminal nesta pasta e execute:

```sh
npm start
```

Abra **http://127.0.0.1:4173**. Para encerrar, use `Ctrl+C` no terminal. Não é necessário executar `npm install`. Use sempre o mesmo endereço, porta e perfil de navegador para acessar os mesmos dados. Não abra o HTML diretamente com `file://`, porque o projeto usa módulos JavaScript.

Alternativa com Python 3: `python3 -m http.server 4173 --bind 127.0.0.1 --directory dist`.

**Login de demonstração:** usuário `admin`, senha `admin123`.

## Operação

- **Inserir registro:** abre o formulário com todos os campos configurados, inclusive colunas ocultas. Salvar valida e grava; Cancelar permite descartar o formulário.
- **Visualizar / Editar / Excluir:** ações disponíveis na última coluna da tabela. A exclusão exige confirmação e fica em rascunho até clicar em **Salvar alterações**.
- **Editar tabela:** permite editar diretamente nas células. Use **Salvar alterações** para persistir ou **Cancelar → Descartar** para restaurar o último estado salvo.
- **Alterações pendentes:** a troca entre Painel e Relatórios, a saída e a abertura de novos formulários oferecem salvar, descartar ou continuar editando. Ao fechar/recarregar a aba, o navegador mostra seu aviso nativo, quando permitido.
- **Pesquisa e filtros:** pesquisa sem distinção de acentos, condições combinadas com “E”, intervalo de criação, ordenação e paginação. Ordenação e tamanho da página fazem parte das preferências salvas.
- **Gerenciar colunas:** expanda uma coluna para alterar nome, tipo, largura, obrigatoriedade, visibilidade, opções ou posição. Todas as alterações ficam no formulário até **Salvar configuração**. Excluir remove seus valores ao salvar. É preciso manter ao menos uma coluna visível.
- **Nova coluna obrigatória:** preencha o valor padrão solicitado para os registros existentes. Alterações de tipo não convertem nem apagam valores incompatíveis: o salvamento é bloqueado. Corrija os dados/opções ou use uma nova coluna.
- **Relatórios:** escolha colunas, aplique filtros e selecione campos numéricos para somar. A prévia inclui todos os resultados filtrados, sem a paginação do painel. Exporte CSV ou use **Imprimir / PDF**, escolhendo “Salvar como PDF” na janela do navegador.
- **Backup:** exporte o JSON pelo menu lateral. A importação valida todo o arquivo antes de pedir confirmação para substituir a base. Importações inválidas mantêm os dados atuais.

## Dados e JSON

O `localStorage` armazena `version`, `columns`, `records` e `preferences`. As colunas têm identificadores estáveis; os registros associam valores a esses identificadores. Renomear, reordenar e ocultar preserva essa associação. Registros incluem ID, data de criação e última atualização.

Exemplo mínimo válido:

```json
{
  "version": 1,
  "columns": [
    { "id": "name", "name": "Nome", "type": "text", "required": true, "hidden": false, "width": 270, "options": [] }
  ],
  "records": [
    {
      "id": "row_example",
      "createdAt": "2026-10-01T12:00:00.000Z",
      "updatedAt": "2026-10-01T12:00:00.000Z",
      "values": { "name": "Meu primeiro registro" }
    }
  ],
  "preferences": { "pageSize": 10, "sortColumn": "createdAt", "sortDirection": "desc" }
}
```

Tipos: `text`, `longtext`, `number`, `date` (AAAA-MM-DD), `select` e `boolean`. Ausência de valor pode ser representada por `null`. Valores numéricos e booleanos usam os tipos nativos do JSON. Uma seleção exige opções não vazias e únicas.

Os 12 exemplos iniciais só são criados se a chave de armazenamento não existir. Uma base vazia salva continua vazia. A chave interna `prisma.workspace.v1` é mantida para compatibilidade com a primeira prévia; ela não é uma biblioteca ou serviço externo.

## Arquivos

```text
dist/index.html       Documento e diálogos
dist/styles.css       Interface, responsividade e impressão
dist/assets/rio-quente-logo.png  Logo fornecido, usado na interface e na aba
dist/js/app.js        Interface e fluxos de interação
dist/js/model.js      Modelo, validações, consulta e CSV
dist/js/storage.js    Camada de persistência e sessão demonstrativa
server.mjs            Servidor estático restrito ao computador local
tests/model.test.mjs  Testes de integridade e persistência
```

## Validação

Execute `npm test` para verificar preservação dos valores ao mudar o esquema, obrigatoriedade, validações de tipos e importação, filtros, exportação CSV, persistência vazia, falhas de armazenamento e conflitos entre abas.

## Limitações do mockup

- O login é **demonstrativo**: as credenciais estão no código e não protegem os dados contra acesso local. Não há autenticação de produção, servidor de dados ou múltiplos usuários.
- Os dados pertencem ao navegador e à origem local. Limpar o armazenamento do site remove a base. Faça backups JSON; não há gravação automática em arquivo, nuvem ou sincronização entre dispositivos.
- O armazenamento depende da cota do navegador, normalmente poucos MB. Há limites de 100 colunas, 50.000 registros e arquivos de importação de 10 MB; a cota pode ser atingida antes. A prévia de relatórios e a impressão são indicadas para bases pequenas.
- Uma gravação bloqueada preserva o rascunho. Conflitos entre abas são detectados antes de salvar; exporte o rascunho e recarregue para usar os dados mais recentes. Não há edição colaborativa.
- O CSV usa UTF-8 com BOM e ponto e vírgula, e neutraliza textos que possam ser interpretados como fórmulas. As somas usam a aritmética nativa do JavaScript; não substituem cálculos financeiros de precisão decimal.
- Um backup de rascunho com campos inválidos precisará ser corrigido antes da reimportação.

Para evoluir para arquivos JSON gravados diretamente no computador ou banco de dados, substitua a camada `storage.js` por chamadas a um backend local e implemente autenticação no servidor.
