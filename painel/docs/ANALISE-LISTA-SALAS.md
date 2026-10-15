# Análise da lista recebida - Salas e espaços

> **Análise da fonte, preservada como histórico.** Menções a “pendente de validação”, “espera” ou “opção prioritária” como situação de solicitação descrevem o desenho anterior. O fluxo atual tem somente **Reservado, Confirmado e Cancelado**; “a validar” refere-se à composição física. Veja o [README](../README.md) e a [atualização dos status](ATUALIZACAO-STATUS-2026-10-15.md). A classificação administrativa dos 99 espaços/configurações por empreendimento já foi feita; a homologação física continua independente.

Data da análise: 7 de outubro de 2026.

Fonte: `LISTA DE SALAS E ESPAÇOS CS & RQ.pdf`, enviado pelo solicitante. As duas páginas foram lidas por extração de texto e conferidas visualmente. O arquivo original foi preservado.

Estado: análise e catálogo preliminar para revisão. Nenhum item foi importado na aplicação nem associado definitivamente a um empreendimento. A proposta permanece em Python com Flask.

## 1. O que o documento contém

O PDF tem duas páginas de uma tabela contínua, com códigos de 1 a 125: 77 linhas na primeira página e 48 na segunda. Os cabeçalhos incluem código, salões, medidas, área, pé-direito, capacidades por montagem e várias colunas de preços/reajustes. Não há datas de bloqueio, reservas, responsáveis ou legenda explícita de empreendimento.

As 125 linhas não representam 125 salas físicas independentes. A classificação preliminar é:

| Classificação da linha | Quantidade | Tratamento proposto |
| --- | ---: | --- |
| Espaço sem composição explícita no nome | 63 | Revisar contexto, resort e possíveis dependências físicas |
| Combinação ou configuração de espaços | 32 | Relacionar aos módulos físicos; não criar disponibilidade independente |
| Variante de utilização da Arena Sauipe | 28 | Associar aos recursos físicos e registrar fase/configuração de uso |
| Serviço de mão de obra | 2 | Não cadastrar como sala reservável |
| **Total de linhas da fonte** | **125** | **Quantidade de espaços físicos ainda não homologada** |

Essas categorias são uma análise dos nomes e não uma classificação oficial fornecida pela solicitante. Um nome sem composição explícita também pode compartilhar recursos com outro item.

## 2. Grupos com combinações

| Grupo identificado pelos nomes | Códigos | Linhas individuais | Combinações/configurações |
| --- | --- | ---: | ---: |
| Bahia | 7-11 | 3 | 2 |
| Santana | 15-19 | 3 | 2 |
| São Tomé | 20-24 | 3 | 2 |
| Santo Amaro | 25-29 | 3 | 2 |
| Gardênia / Canário / Aimorés / Amazonas | 31-37 | 4 | 3 |
| Ouro Preto | 40-55 | 8 | 8 |
| Gran Bahia | 56-61 | 3 | 3 |
| Porto Seguro (numeradas) | 62-67 | 3 | 3 |
| Vera Cruz | 68-70 | 2 | 1 |
| Jangada | 71-76 | 3 | 3 |
| Salas (contexto a confirmar) | 118-124 | 4 | 3 |
| **Subtotal** | | **39** | **32** |

Exemplo da regra a implementar após validar a composição: a configuração “Bahia 1 - 2” usa Bahia 1 e Bahia 2. Uma ocupação prioritária ou confirmada dessa configuração impede ocupação efetiva das duas salas nos mesmos dias; Bahia 3 pode permanecer disponível se não houver outra dependência. A checagem vale também no sentido inverso. Solicitações em espera podem concorrer por esses mesmos recursos, conforme a política já definida.

Nem toda composição está determinada pelo texto:

- **Códigos 35 e 36:** “2 Módulos (Gardênia+Canário+Aimorés+Amazonas)” e “3 Módulos (...)” não identificam quais módulos foram escolhidos. É necessário saber quais pares e trios são permitidos; não supor que qualquer combinação é válida.
- **Códigos 50-54:** “Ouro Preto 6 - 8”, “1 - 4”, “1 - 5”, “4 - 8” e “5 - 8” podem indicar intervalos inclusivos. O catálogo registra essa hipótese separadamente, sem transformá-la em composição confirmada.
- **Códigos 118-124:** “Salas 1”, “Salas 2” etc. não informam o edifício ou empreendimento. Estarem depois das linhas da Arena não confirma vínculo físico com ela.

O item **13, “Porto Seguro”**, deve continuar distinto dos itens **62-67, “Porto Seguro 1”, “Porto Seguro 2” etc.**, até esclarecer sua localização. Semelhança de nome não autoriza mesclagem.

## 3. Arena Sauipe: 28 linhas de variantes

Os códigos 90-117 variam o uso descrito da Arena:

| Configuração descrita | Códigos | Quantidade de linhas |
| --- | --- | ---: |
| 3 módulos | 90-97 | 8 |
| 2 módulos | 98-105 | 8 |
| 1 módulo | 106-111 | 6 |
| Apenas foyer | 112-117 | 6 |

As descrições diferenciam montagem, evento, desmontagem e situações de ar-condicionado. Essas características não devem gerar espaços independentes por linha: mudar a climatização não torna o mesmo espaço livre para outro evento.

Para o calendário, a proposta é separar:

1. O recurso físico: módulos identificados e foyer, com suas dependências confirmadas.
2. A configuração escolhida: conjunto específico dos módulos, não apenas uma quantidade.
3. O período diário de cada fase: montagem, evento e desmontagem, caso a operação adote esse controle.
4. Informações complementares de utilização, como climatização, apenas se necessárias ao uso operacional.

A fonte não informa a identificação física de cada módulo, as combinações permitidas ou se o foyer pode ser usado independentemente durante um evento na Arena. Não criar nomes oficiais de módulos nem conceder disponibilidade com essas relações indefinidas.

O formulário pode pedir os períodos de cada fase e calcular a união dos dias ocupados. Fases do mesmo bloqueio que usem o mesmo recurso no mesmo dia devem resultar em uma única ocupação física, não duas reservas. Alterar ou cancelar uma fase não pode liberar um dia ainda ocupado por outra fase do mesmo bloqueio. Essa proposta deve ser validada com a operação.

## 4. Outros espaços e serviços

Além dos 39 itens individuais dos grupos, há 24 linhas de espaços sem composição explícita: Espaço Circo da Villa; Restaurante La Villa; Restaurante Benditos Frutos; Restaurante Baea; Ilhéus; Porto Seguro; São Vicente; Foyer das Colunas; Jubarte; Maremoto; Brinquedoteca; Teatro da Vila Nova; Ala Mar - Piscina; Ala Água - Piscina; Ala Terra - Piscina; Ala Sol - Piscina; Pousadas - Piscina; Premium - Piscina; Gramado Sol / Mar; Gramado Água; Pousada da Torre; Coqueiral; Terreno Odebrech; Quermesse.

A proposta de cadastro deve abranger **salas e espaços de eventos**, pois a fonte inclui restaurantes, piscinas e áreas externas. A operação confirmará se todos esses itens são bloqueáveis e suas dependências. Preservar a grafia da fonte até eventual correção expressa, inclusive “Terreno Odebrech”, “Arena Sauipe” e “Salas 1 -2”.

Jubarte, Maremoto e Brinquedoteca contêm a observação: “Deposito / Secretaria / Credenc. / etc. Não comporta montagem tipo auditório, escolar etc.” Preservar essa restrição nos detalhes. Não preencher capacidades inexistentes nem tratar dados ausentes como zero.

Os códigos 5 e 6 são “Mão de Obra (Por Turno)” e “Mão de Obra Especializada Barnabe (Por Turno)”. Eles permanecem rastreáveis na transcrição, mas devem ser excluídos do cadastro de espaços. A referência a turno descreve o serviço e não muda a regra de bloqueio diário confirmada pelo solicitante.

Os valores comerciais e IGP-M fazem parte da tabela recebida, mas não tornam preços, orçamento ou reajuste requisitos do calendário. O catálogo preliminar não incorporou essas colunas. Áreas e capacidades foram preservadas como texto de referência, sem somas ou conversões automáticas; não se deve deduzir a capacidade de uma combinação pela soma das partes.

## 5. Separação entre os resorts

O nome do arquivo contém “CS & RQ”, mas as páginas não têm coluna de resort, títulos separadores ou legenda que atribua cada código à Costa do Sauípe ou ao Rio Quente. Há cores diferentes em algumas famílias; elas não têm significado declarado e não devem ser usadas para inferir empreendimento.

O solicitante informou que não tem essa separação e pediu uma solução sem conflitos ou confusões. Por isso, todos os campos de empreendimento no catálogo preliminar permanecem sem atribuição, com a categoria de interface **“Empreendimento a identificar”**. A leitura do PDF, por si só, não comprova que o inventário dos dois resorts está completo.

### Solução para avançar sem presumir o resort

1. Manter um único cadastro com IDs permanentes, nomes e códigos de origem. O resort é uma classificação opcional, não parte da identidade usada para checar conflitos. “A identificar” é uma categoria de consulta e não um terceiro resort real.
2. Disponibilizar filtros “Todos”, “Costa do Sauípe”, “Rio Quente” e “A identificar”. Itens pendentes aparecem nos dois filtros gerais apropriados, nunca como pertencentes aos dois resorts. Mostrar o total pendente para que uma pesquisa por resort não pareça conter o inventário completo.
3. Permitir consulta compartilhada pelas equipes autorizadas e registro de solicitações com equipe proprietária. A mesma solicitação continua sendo um único registro em qualquer visualização.
4. Separar falta de resort de incerteza física. Espaços fisicamente identificados e com relações de composição validadas podem receber bloqueio mesmo sem resort, por usuário autorizado à área comum. Onde a identidade/composição ainda é incerta, registrar apenas **“Pendente de validação”**, sem ocupação garantida e sem promoção automática. Uma grade vazia desses itens não significa disponibilidade confirmada.
5. Criar revisão cadastral individual ou em lote. Quando houver informação confiável, um responsável atribui o resort ao mesmo espaço, com prévia e histórico. Os bloqueios mantêm ID, datas, equipe, prioridade e histórico. A permissão cadastral não autoriza editar bloqueios de outra equipe.
6. Revalidar acesso quando a classificação afetar o escopo por resort. Não expor informações de eventos além do permitido. Alterar composição física ou unir possíveis duplicados é uma operação distinta, que exige reavaliar conflitos existentes.

Com esse desenho, a classificação incompleta fica visível e corrigível, sem fabricar uma separação nem duplicar a disponibilidade. A revisão dos resorts pode ocorrer progressivamente; a revisão dos recursos físicos continua necessária para garantir ocupações efetivas.

## 6. Ajuste do modelo em Flask

O modelo deve distinguir `Empreendimento`, `Espaço/Recurso físico`, `Configuração`, `Configuração-Recurso`, `Bloqueio/Solicitação`, `Alocação/Fase`, `Ocupação diária`, `Equipe/Usuário` e `Histórico`. O vínculo de empreendimento do recurso pode começar vazio; o ID físico é permanente e global. Atribuir resort não recria a entidade nem seus bloqueios.

Manter também o vínculo de origem: documento, código e página da linha recebida. Uma configuração pode ter várias linhas de referência comercial, e uma linha genérica pode exigir escolha posterior de um conjunto físico validado. O código da fonte não substitui o identificador de recurso físico.

No serviço de disponibilidade, converter a configuração escolhida em seus recursos físicos antes de verificar conflito, prioridade ou elegibilidade na fila. Garantir unicidade de ocupação efetiva por recurso/dia no banco, dentro da mesma transação de gravação. Composição, fase e climatização não podem permitir contornar esse controle.

As relações de composição devem ser homologadas antes de liberar ocupações nos itens afetados. É possível avançar com interface, catálogo para revisão, classificação “A identificar”, solicitações pendentes e demais regras independentes. A falta de resort, isoladamente, não impede uma ocupação de recurso fisicamente validado e autorizado.

## 7. Arquivos produzidos e validação

- `catalogo-salas-preliminar.json`: transcrição estruturada de todos os 125 códigos/nomes; página de origem; dados técnicos como texto; classificação preliminar; pendências; componentes candidatos separados dos confirmados. Inclui identificação SHA-256 do arquivo de origem.
- `PROPOSTA-CALENDARIO-SALAS.md`: arquitetura atualizada com a distinção entre espaços, configurações e variantes.
- `PROMPT-IMPLEMENTACAO-CALENDARIO.md`: instruções atualizadas para usar o material recebido sem tratar cada linha como uma sala independente.

Verificações realizadas: leitura das duas páginas, inspeção visual, sequência integral dos códigos 1-125 sem duplicação, nomes não vazios e conferência dos totais por classificação. Os nomes foram extraídos pela posição das colunas para evitar juntar códigos aos nomes ou capacidades umas às outras. Essa verificação confirma a transcrição e a análise; não homologa as associações físicas nem substitui a validação da solicitante.

Critérios adicionais para a futura implementação:

- Reservar uma combinação conflita com seus componentes e com outras combinações que usem qualquer um deles, inclusive na promoção de uma opção em espera.
- Configurações fisicamente disjuntas permanecem independentes, se a operação confirmar essa possibilidade.
- Variantes de climatização ou fase não criam disponibilidade duplicada do mesmo recurso.
- Uma solicitação com composição indefinida não recebe ocupação efetiva.
- Linhas de serviço nunca aparecem como salas disponíveis.
- Capacidade por montagem, restrições e nomes homônimos são preservados sem inferência silenciosa.
- Atribuir ou corrigir o resort preserva IDs, bloqueios, equipe proprietária e histórico; não elimina conflitos nem duplica disponibilidade.
- Pendência cadastral não é confundida com fila de espera ou reserva confirmada.

## 8. Pendências prioritárias

1. Disponibilizar a categoria “Empreendimento a identificar” e definir quem fará a revisão progressiva de localização e cobertura dos resorts quando a informação estiver disponível; não exigir essa informação do solicitante para iniciar o desenvolvimento.
2. Homologar as composições, os intervalos Ouro Preto, os pares/trios de Gardênia e a identificação e independência dos módulos/foyer da Arena e das “Salas” numeradas.
3. Confirmar se montagem/desmontagem bloqueiam dias próprios e se todos os espaços externos/de apoio entram no calendário.
4. Definir ordem de prioridade, autoridade para mudar posições, condições de promoção e prazo de opção.
