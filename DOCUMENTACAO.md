# Consulta PCASP — guia de uso e manutenção

## Conteúdo

1. [Visão geral](#1-visão-geral)
2. [Requisitos e arquivos](#2-requisitos-e-arquivos)
3. [Iniciar e encerrar](#3-iniciar-e-encerrar)
4. [Consultar contas PCASP](#4-consultar-contas-pcasp)
5. [Comparar o inventário com o relatório PCASP](#5-comparar-o-inventário-com-o-relatório-pcasp)
6. [Revisar e aprovar sugestões por bem](#6-revisar-e-aprovar-sugestões-por-bem)
7. [Atualizar a tabela PCASP](#7-atualizar-a-tabela-pcasp)
8. [Acesso pela rede local](#8-acesso-pela-rede-local)
9. [Como as sugestões são calculadas](#9-como-as-sugestões-são-calculadas)
10. [Limites e cuidados](#10-limites-e-cuidados)
11. [Passo a passo do funcionamento](#11-passo-a-passo-do-funcionamento)
12. [Estrutura do projeto](#12-estrutura-do-projeto)

## 1. Visão geral

O **Consulta PCASP** ajuda a pesquisar contas do Plano de Contas Aplicado ao Setor Público do TCEMG e a organizar uma análise documentada de bens patrimoniais para embasar uma futura mudança no sistema principal SH3/Siap. A busca e as sugestões comparam palavras da descrição com códigos, títulos e funções das contas. A aplicação não se conecta ao SH3/Siap nem altera seu cadastro.

O sistema não confirma que uma conta está errada nem substitui a análise contábil. A pessoa responsável confere os dados e decide se aprova cada sugestão.

## 2. Requisitos e arquivos

- Windows;
- Python 3.12 ou compatível;
- navegador;
- VS Code opcional.

A aplicação usa a biblioteca padrão do Python; não exige instalar dependências externas nem acessar a internet para funcionar.

Arquivos principais:

- `data/PCASP_TCEMG-2026_v12.2.xlsx`: planilha PCASP inicial;
- `data/pcasp.sqlite3`: banco de consulta criado/preenchido na primeira execução;
- `.venv/`: ambiente Python do projeto;
- `run.py`: ponto de entrada;
- `README.md`: instruções rápidas.

## 3. Iniciar e encerrar

Abra o PowerShell na pasta do projeto e execute:

```powershell
.\.venv\Scripts\python.exe run.py
```

O navegador abre em:

```text
http://127.0.0.1:8765
```

Na primeira execução, a aplicação carrega a planilha inicial para o banco local. Mantenha a janela do terminal aberta enquanto usar o sistema. Para encerrar, volte ao terminal e pressione **Ctrl+C**.

No VS Code, também é possível iniciar pelo menu **Executar e Depurar**, usando **Consulta PCASP (local)**.

## 4. Consultar contas PCASP

1. Digite a descrição do bem, por exemplo `computador portátil`, `cadeira de escritório` ou `terreno`.
2. Se souber, escolha **Móvel** ou **Imóvel** para priorizar resultados; **Não sei** não aplica essa prioridade.
3. Clique em **Buscar contas**.
4. Confira código, título, função, natureza do saldo, situação, motivo da correspondência e atributos disponíveis.
5. Use **Carregar mais sugestões** para ver resultados seguintes. É possível comparar até três contas na tela.

A busca apresenta candidatas ordenadas pela correspondência textual. Cabe à pessoa usuária conferir os dados da conta antes de escolher.

## 5. Comparar o inventário com o relatório PCASP

O TXT usado aqui é o **relatório PCASP - Inventário Ativo**, com saldos e movimentações. Ele é diferente da tabela PCASP de referência: essa tabela é Excel `.xlsx` e é carregada na seção **Atualizar tabela PCASP**. A comparação de saldos é opcional.

Na seção **Comparar inventário com relatório PCASP**, selecione:

- o CSV **Localizar Bens**, que contém as colunas `Conta Bem` e `Valor Atual`;
- o TXT **PCASP - Inventário Ativo**, que contém código, descrição, valores anteriores, débitos, créditos e saldo final.

A aplicação soma `Valor Atual` por `Conta Bem` e compara o resultado com `Saldo Final` por código de conta. A tabela destaca diferenças e contas sem correspondência para facilitar a conferência.

Uma diferença é um alerta, não uma conclusão de erro. Confira período, critérios contábeis e composição dos saldos antes de tomar qualquer decisão. Esta comparação não altera os arquivos.

## 6. Revisar e aprovar sugestões por bem

Na seção **Quais bens e contas devo conferir?**, carregue o CSV **Localizar Bens** e a relação completa **Localizar Plano de Contas.csv** exportada do SH3/Siap. A primeira lista os bens; a segunda informa quais contas existem no sistema. Sem a relação do SH3, a análise não é iniciada.

Os campos mostram os nomes esperados dos arquivos: `Localizar Bens.csv` para o inventário, `Localizar Plano de Contas.csv` para conferir o cadastro do SH3, `relatorio pcasp.txt` para o relatório de saldos e `PCASP_TCEMG-2026_v12.2.xlsx` como referência inicial da tabela de contas. O nome real do arquivo selecionado também é mostrado pelo navegador.

As contas candidatas vêm da tabela PCASP de referência `.xlsx` já carregada no sistema. **Não é necessário ter uma tabela PCASP em TXT** para receber essas sugestões. O TXT só é usado na comparação de saldos descrita na seção anterior.

### Conferir cada indicação

1. Filtre a lista por descrição, plaqueta ou conta.
2. Clique em **Analisar** no bem desejado.
3. Confira a plaqueta, descrição e características disponíveis no CSV, como produto, tipo, modelo, classificação, data, valores, vida útil, setor e contas relacionadas.
4. Compare a conta atual com as candidatas. Para cada candidata, veja título, função, natureza do saldo, situação, atributos, motivo da sugestão e se ela está cadastrada no SH3.
5. Selecione uma candidata marcada **Cadastrada no SH3/Siap** e clique em **Aprovar conta selecionada**. Para manter a conta atual, clique em **Não aprovar**.

Candidatas PCASP ausentes da relação são mostradas como **Não cadastrada no SH3/Siap**. Elas servem para indicar uma possível solicitação de inclusão à SH3, mas não podem ser aprovadas nem exportadas. A tela também informa quando a conta atual não tem correspondência na relação do SH3.

O sistema orienta a localizar o bem pela **plaqueta** e conferir o campo **Conta Bem** no cadastro patrimonial. Ele não conhece os nomes dos menus internos do SH3/Siap e não altera esses sistemas.

### Baixar as alterações aprovadas

Depois de revisar as indicações, há dois arquivos que podem ser baixados:

- **Baixar cópia com aprovadas:** cria um novo CSV com as contas aprovadas aplicadas à coluna `Conta Bem`; os demais bens ficam como estavam no arquivo recebido.
- **Baixar resumo Excel:** cria um comparativo com código PCASP, descrição, total antes das aprovações, total depois e variação por conta, somando `Valor Atual`. A aba **Itens alterados** detalha os bens aprovados, com plaqueta, código, descrição, conta anterior, conta nova e valor individual.

Antes do resumo, o sistema cruza `Conta Bem` com `Código`, `Conta Patrimonial Estadual` e `Conta Patrimonial` do arquivo do SH3. Assim, um código interno como `00713` é convertido para a conta patrimonial correspondente. As contas aprovadas também precisam estar na relação SH3. Bens cuja `Conta Bem` não tenha correspondência válida são excluídos dos totais; o resumo ainda é gerado para as demais contas. A tela informa quantos bens foram excluídos e a planilha lista plaqueta, conta informada e valor não somado ao final, para conferência.

Quando um bem muda de conta, seu valor sai do total da conta anterior e entra no total da nova conta. O bem é contado uma única vez na conta final. Sem aprovações, os totais antes e depois serão iguais. A planilha inclui título, cabeçalho destacado, valores em moeda, filtro na tabela, primeira linha de dados congelada e total geral.

**O CSV original nunca é sobrescrito.** A aplicação grava as decisões aprovadas ou mantidas no banco local para recuperar seu trabalho quando o inventário for carregado novamente. Ela não altera o SH3/Siap. A cópia e o comparativo documentam a análise e podem embasar uma futura mudança, a ser avaliada e executada separadamente no sistema principal.

As decisões são salvas no banco local `data/pcasp.sqlite3`, identificadas pelo código e pela plaqueta do bem. Ao carregar novamente o inventário, decisões que ainda correspondem aos dados são restauradas. No fluxo previsto, o inventário atualizado apenas acrescenta bens e preserva os registros existentes: as decisões anteriores continuam associadas a esses bens, enquanto cada bem novo aparece sem decisão para análise individual. O CSV é processado em memória e não fica armazenado pela aplicação.

Use **Limpar arquivos e análises** para remover os arquivos selecionados e os resultados da tela. Isso mantém as decisões salvas. Use **Apagar decisões salvas** para remover permanentemente as aprovações e decisões de manter conta gravadas no banco local. A tabela PCASP carregada não é apagada por esses botões.

## 7. Atualizar a tabela PCASP

Na seção **Atualizar tabela PCASP**, selecione um arquivo `.xlsx`. A primeira aba deve conter as colunas `CONTA`, `TÍTULO` e `FUNÇÃO`. `STATUS`, natureza do saldo e outros campos são usados quando presentes. O tamanho máximo é 20 MB.

Depois da validação, a nova planilha substitui a tabela PCASP carregada no banco local. Para voltar à referência inicial, importe `data/PCASP_TCEMG-2026_v12.2.xlsx`.

A importação da tabela só fica disponível no computador que hospeda a aplicação.

## 8. Acesso pela rede local

Ao iniciar, o terminal informa o IPv4 do computador principal. Em outro dispositivo conectado à mesma rede privada, abra:

```text
http://<IPv4-do-computador-principal>:8765
```

Substitua o trecho entre `<` e `>` pelo endereço mostrado no terminal. O computador principal precisa permanecer ligado, conectado à rede e com a aplicação aberta. Os outros dispositivos podem usar a consulta de contas; a análise de arquivos e a atualização da tabela ficam no computador principal.

Se o Firewall do Windows bloquear o acesso, abra o PowerShell como administrador e crie uma regra limitada à rede privada local:

```powershell
New-NetFirewallRule -DisplayName "Consulta PCASP (rede local)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -Profile Private -RemoteAddress LocalSubnet
```

O endereço atual usa HTTP e foi preparado para a rede local. Acesso por outras redes exige hospedagem, HTTPS e controle de acesso adequados; não encaminhe a porta `8765` diretamente para a internet.

## 9. Como as sugestões são calculadas

A aplicação normaliza maiúsculas e acentos e compara os termos da descrição com o código, título e função das contas. Há equivalências simples para alguns termos, como `computador` com `equipamento`, `processamento` e `dados`, ou `cadeira` com `mobiliário` e `móveis`.

Na análise dos bens, as candidatas são encontradas por correspondência textual entre a descrição e o título/função PCASP. Depois, cada código é comparado com `Conta Patrimonial Estadual` e `Conta Patrimonial` da relação SH3, incluindo a conversão de códigos internos da coluna `Código`. Candidatas cadastradas no SH3 aparecem primeiro e podem ser aprovadas; as ausentes são identificadas, mas não podem ser aprovadas nem exportadas. Isso orienta a conferência e não é uma validação contábil.

## 10. Limites e cuidados

- Descrições curtas, genéricas ou incompletas podem produzir sugestões fracas ou nenhuma sugestão.
- Uma conta candidata pode ser inadequada mesmo quando compartilha palavras com a descrição.
- Diferenças entre o CSV e o TXT podem decorrer de datas-base, critérios contábeis ou composição dos saldos.
- A análise de arquivos e a aprovação estão restritas ao computador principal e a envios de até 20 MB.
- Credor e responsável não são exibidos na tela de revisão; as características patrimoniais relevantes e o setor podem aparecer nos detalhes.
- A aplicação não altera diretamente o cadastro patrimonial. Ela conserva a decisão atual de cada bem, sem registrar versões anteriores dessa decisão.

## 11. Passo a passo do funcionamento

Este roteiro cobre uma rodada completa de conferência. Os arquivos de entrada são relatórios exportados do SH3/Siap; o sistema não se conecta diretamente ao SH3.

1. **Inicie o sistema** no computador principal pelo PowerShell, dentro da pasta do projeto: `\.venv\Scripts\python.exe run.py`. Mantenha o terminal aberto e acesse `http://127.0.0.1:8765`.
2. **Confira a referência PCASP.** A planilha `.xlsx` carregada alimenta as consultas e sugestões. Atualize-a somente se tiver uma versão de referência que deseja usar.
3. **Exporte relatórios atualizados do SH3/Siap.** Baixe `Localizar Bens.csv` e `Localizar Plano de Contas.csv`. A relação de contas é necessária para a revisão e para converter códigos internos em contas patrimoniais.
4. **Carregue os dois CSVs** na área de revisão e clique em **Analisar bens**. O sistema sugere contas da tabela PCASP e informa se cada candidata consta na relação do SH3.
5. **Examine cada bem** pela plaqueta, descrição, características e conta atual. Aprove apenas candidata identificada como cadastrada no SH3; sugestões ausentes servem para consulta à SH3. Se não aprovar, a conta atual permanece.
6. **Baixe os resultados antes de sair:** a cópia CSV aplica somente as mudanças aprovadas; o Excel agrupa os valores por conta final. Confira ambos. O original não é sobrescrito e nada é gravado no SH3 automaticamente.
7. **Para uma nova rodada**, baixe novamente do SH3/Siap o `Localizar Bens.csv` e o `Localizar Plano de Contas.csv` mais recentes e use esses arquivos. Se o inventário apenas incluir bens novos e mantiver os registros existentes, as decisões salvas serão retomadas pelos códigos e plaquetas; os novos bens entram sem decisão e precisam ser analisados. A cópia aprovada e o comparativo servem para documentar e embasar a futura mudança. Eles não atualizam o SH3/Siap.
8. **Opcional — comparar saldos:** envie `Localizar Bens.csv` e `relatorio pcasp.txt` na área de comparação. A conferência agrupa `Valor Atual` por `Conta Bem` e compara com `Saldo Final`. Use códigos compatíveis entre os arquivos; diferenças pedem análise, não significam automaticamente erro.
9. **Ao terminar ou iniciar outra análise**, use **Limpar arquivos e análises**. Isso remove arquivos da sessão e resultados da tela, mas mantém as decisões salvas e a tabela PCASP carregada.

As decisões aprovadas e de manter a conta são gravadas no banco local e recuperadas quando o mesmo bem aparece em uma nova análise. O CSV original continua sendo carregado a cada sessão e nunca é sobrescrito.

## 12. Estrutura do projeto

```text
PROJETO_PCASP_2026/
├── app/
│   ├── config.py             Caminhos, host, porta e limite de upload
│   ├── pcasp.py              Importação, persistência, busca e comparação de contas
│   ├── reconciliation.py     Sugestões, análise, cópia aprovada e resumo por conta
│   ├── server.py             Servidor HTTP e rotas da aplicação
│   ├── xlsx_reader.py        Leitura da planilha .xlsx
│   └── web/
│       ├── app.js            Busca, revisão, aprovação e interações da tela
│       ├── index.html        Estrutura da página
│       └── style.css         Estilos
├── data/                     Planilha PCASP e banco SQLite local
├── .venv/                    Ambiente virtual Python
├── README.md                 Guia rápido
├── DOCUMENTACAO.md           Manual em Markdown
├── DOCUMENTACAO.html         Manual para abrir no navegador
└── run.py                    Inicialização
```
