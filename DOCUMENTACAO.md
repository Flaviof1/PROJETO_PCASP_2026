# Documentação do sistema Consulta PCASP

## 1. Visão geral

O **Consulta PCASP** é uma aplicação local para apoiar a consulta de contas do Plano de Contas Aplicado ao Setor Público (PCASP) do TCEMG. A pessoa informa a descrição de um bem móvel ou imóvel e recebe contas candidatas encontradas por palavras relacionadas ao título e à função das contas.

As sugestões servem como apoio à consulta. A pessoa responsável deve conferir o título, a função, a natureza do saldo e os demais atributos antes de decidir a classificação.

Nesta versão, a aplicação funciona neste computador e não fica disponível para outros computadores da rede. A organização modular permite evoluir o projeto, incluindo o acesso compartilhado em uma etapa futura.

## 2. Requisitos

- Windows;
- Python 3.12 ou compatível;
- VS Code (opcional, recomendado para desenvolvimento e manutenção);
- navegador instalado.

A aplicação foi estruturada para usar apenas bibliotecas incluídas no Python. Não é necessário instalar pacotes externos nem ter acesso à internet para executar o sistema.

## 3. Estrutura do projeto

```text
PROJETO_PCASP_2026/
├── .vscode/
│   ├── launch.json             Configuração para iniciar pelo VS Code
│   └── settings.json           Seleção do ambiente virtual
├── app/
│   ├── config.py               Caminhos, host, porta e limite de upload
│   ├── pcasp.py                Importação, persistência e busca das contas
│   ├── server.py               Servidor local e rotas da aplicação
│   ├── xlsx_reader.py          Leitura de planilhas .xlsx
│   └── web/
│       ├── app.js              Interações da interface
│       ├── index.html          Estrutura da página
│       └── style.css           Estilos visuais
├── data/
│   ├── PCASP_TCEMG-2026_v12.2.xlsx  Planilha de referência inicial
│   └── pcasp.sqlite3                Banco local, criado na primeira execução
├── .venv/                      Ambiente virtual Python
├── requirements.txt            Lista de dependências externas (vazia)
└── run.py                      Ponto de entrada da aplicação
```

O banco SQLite é criado localmente em `data/pcasp.sqlite3`. Essa pasta contém os dados que a aplicação prepara para a busca. A planilha Excel original permanece disponível como referência.

## 4. Preparar e abrir no VS Code

1. Abra o VS Code.
2. Selecione **Arquivo → Abrir Pasta…**.
3. Abra a pasta `PROJETO_PCASP_2026`.
4. Abra o terminal integrado em **Terminal → Novo Terminal**.

O projeto já contém o ambiente virtual `.venv`. A configuração em `.vscode/settings.json` indica ao VS Code que deve usar o Python desse ambiente.

## 5. Iniciar a aplicação

No terminal do VS Code, estando na pasta do projeto, execute:

```powershell
.\.venv\Scripts\python.exe run.py
```

Na primeira execução, o sistema carrega a planilha inicial para o banco de dados. Depois, abre a página no navegador no endereço:

```text
http://127.0.0.1:8765
```

Mantenha o terminal aberto enquanto usa a aplicação. Para encerrá-la, volte ao terminal e pressione **Ctrl+C**.

Também é possível iniciar pelo menu **Executar e Depurar** do VS Code, selecionando **Consulta PCASP (local)**.

## 6. Consultar uma conta

1. Digite uma descrição do bem no campo **Descrição do bem**. Exemplos: `computador portátil`, `cadeira de escritório` ou `terreno`.
2. Opcionalmente, selecione **Móvel** ou **Imóvel** para priorizar contas cujo texto menciona esse tipo. A opção **Não sei** deixa a busca sem essa priorização.
3. Clique em **Buscar contas**.
4. Confira as contas candidatas. Cada resultado pode mostrar:
   - código da conta;
   - título;
   - função;
   - natureza do saldo e situação, quando preenchidas;
   - atributos e outras informações da planilha, quando disponíveis.
5. Se necessário, tente outra descrição ou retire a priorização do tipo.

## 7. Atualizar a tabela PCASP

Na seção **Atualizar tabela PCASP**, selecione uma planilha Excel `.xlsx`. A aplicação lê a primeira aba e procura as colunas `CONTA`, `TÍTULO` e `FUNÇÃO`. A coluna `STATUS` e outros campos são usados quando estão presentes.

O limite atual de upload é 20 MB. Uma planilha aceita substitui a tabela carregada anteriormente depois que a leitura e a validação são concluídas. Caso o arquivo não tenha o formato esperado, a interface apresenta uma mensagem de erro.

Para usar novamente a versão inicial, importe a planilha `data/PCASP_TCEMG-2026_v12.2.xlsx`.

## 8. Como as sugestões são formadas

A busca normaliza maiúsculas e acentos e compara os termos digitados com o código, o título e a função das contas. Alguns termos comuns de bens têm equivalências de busca, como `computador` e `notebook` relacionados a `equipamento`, `processamento` e `dados`, ou `cadeira` e `mesa` relacionados a `mobiliário` e `móveis`.

Os resultados são ordenados por coincidências textuais. A opção móvel/imóvel dá prioridade a contas cujo título ou função contém referências a esse tipo, mas não exclui automaticamente as demais contas. O sistema não compreende o contexto completo da aquisição nem confirma se uma conta é correta.

## 9. Limites e próximos passos possíveis

- A busca é lexical e depende dos termos existentes na descrição e na tabela; ela pode não encontrar uma conta adequada quando há pouca coincidência de palavras.
- A interface não registra o bem cadastrado nem a decisão final de classificação.
- Ainda não existe análise de uma planilha com bens já cadastrados.
- A aplicação atende apenas o computador onde foi iniciada. Para uso compartilhado pela rede, será necessário configurar acesso e controles de segurança.
- O limite de arquivo de 20 MB pode ser ajustado se houver necessidade de importar planilhas maiores.

Uma evolução possível é permitir importar uma planilha de bens existentes e apontar registros que mereçam revisão, mantendo as recomendações como alertas para conferência humana.
