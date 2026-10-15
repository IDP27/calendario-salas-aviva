# Verificação da primeira versão

> **Registro histórico do painel anterior.** Os totais abaixo não representam a suíte atual da agenda. Os resultados e limites vigentes estão em [Testar](../README.md#testar); a atualização de status está [documentada aqui](ATUALIZACAO-STATUS-2026-10-15.md).

Verificação realizada em 2 de outubro de 2026.

## Testes automatizados

`npm test`: **9 testes aprovados**. Cobrem preservação dos valores ao renomear/reordenar/ocultar colunas; bloqueio de tipos e opções incompatíveis; obrigatoriedade e valores zero/falso; datas inválidas; importação de JSON inválido; filtros combinados e tipados; CSV; persistência de uma base vazia; falhas de armazenamento e conflito entre abas.

A sintaxe dos módulos JavaScript e do servidor também foi verificada com `node --check`. O servidor respondeu HTTP 200.

## Verificação pelo navegador

- Login incorreto exibiu erro; login correto abriu o painel.
- Inserção de registro, recarga da página e pesquisa confirmaram persistência.
- Edição diretamente na tabela e navegação para Relatórios exibiram a confirmação de rascunho. “Salvar e continuar” preservou a alteração.
- Uma coluna numérica obrigatória solicitou valor padrão e aplicou o valor 10 aos registros existentes.
- O relatório reconheceu a nova coluna, filtrou um registro e exibiu a soma 10.
- O CSV baixado foi lido e validado: cinco colunas e somente o registro filtrado, com o valor 10.
- Renomear e subir a coluna preservou o valor do registro na posição correta.
- Exclusão da coluna e do registro temporários passou por confirmação e salvamento. A base retornou aos 12 exemplos e quatro colunas.
- Layout conferido em larguras de 390 e 1440 pixels. No celular, a página não apresentou transbordamento horizontal; a tabela tem sua própria rolagem.
- Nenhum erro ou aviso JavaScript foi capturado no console durante a verificação.

## Limites da verificação

A validação de importação e a preservação dos dados atuais foram verificadas em testes automatizados. O seletor nativo de arquivos e o fluxo completo de importação não foram exercitados no navegador. O estilo e o comando de impressão foram implementados, mas a saída PDF não foi gerada ou inspecionada nesta verificação.

Prévia visual: `painel-desktop.png`.
