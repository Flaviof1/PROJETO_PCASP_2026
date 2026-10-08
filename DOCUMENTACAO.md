# Documentação do sistema Consulta PCASP

## 1. Visão geral

O **Consulta PCASP** é uma aplicação local para apoiar a consulta de contas do Plano de Contas Aplicado ao Setor Público (PCASP) do TCEMG. A pessoa informa a descrição de um bem móvel ou imóvel e recebe contas candidatas encontradas por palavras relacionadas ao título e à função das contas.

As sugestões servem como apoio à consulta. A pessoa responsável deve conferir o título, a função, a natureza do saldo e os demais atributos antes de decidir a classificação.

O computador principal executa a aplicação e outros computadores da mesma rede privada podem abrir a consulta pelo navegador. O acesso não exige hospedagem nem publicação na internet. O computador principal precisa permanecer ligado.

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

O terminal também mostra o endereço com o IPv4 do computador principal para os demais dispositivos da rede. Mantenha-o aberto enquanto usa a aplicação. Para encerrar, pressione **Ctrl+C**.

Se o Firewall do Windows bloquear o acesso, abra o PowerShell como administrador e execute uma regra limitada à rede privada e à sub-rede local:

```powershell
New-NetFirewallRule -DisplayName "Consulta PCASP (rede local)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -Profile Private -RemoteAddress LocalSubnet
```

No outro computador, abra `http://<IPv4-do-computador-principal>:8765`, substituindo o trecho entre sinais de menor e maior pelo endereço mostrado no terminal. Os computadores precisam estar na mesma rede privada. No computador principal, use `127.0.0.1` para importar planilhas; os demais dispositivos podem consultar e comparar contas, mas não substituir a tabela PCASP.

Também é possível iniciar pelo menu **Executar e Depurar** do VS Code, selecionando **Consulta PCASP (local)**.

## 6. Consultar uma conta

1. Digite uma descrição do bem no campo **Descrição do bem**. Exemplos: `computador portátil`, `cadeira de escritório` ou `terreno`.
2. Opcionalmente, selecione **Móvel** ou **Imóvel** para priorizar contas cujo texto menciona esse tipo. A opção **Não sei** deixa a busca sem essa priorização.
3. Clique em **Buscar contas**.
4. Confira as contas candidatas. A busca exibe 15 resultados por vez; use **Carregar mais sugestões** para avançar. Cada resultado pode mostrar:
   - código da conta;
   - título;
   - função;
   - natureza do saldo e situação, quando preenchidas;
   - motivo pelo qual apareceu na busca;
   - hierarquia PCASP com os títulos das contas superiores;
   - atributos e outras informações da planilha, quando disponíveis.
5. Se necessário, tente outra descrição ou retire a priorização do tipo.

Use **Adicionar à comparação** para selecionar até três contas. A barra de comparação permite retirar contas selecionadas ou abrir uma tabela lado a lado com código, título, hierarquia, função, situação, natureza do saldo e atributos disponíveis.

## 7. Atualizar a tabela PCASP

Na seção **Atualizar tabela PCASP**, selecione uma planilha Excel `.xlsx`. A aplicação lê a primeira aba e procura as colunas `CONTA`, `TÍTULO` e `FUNÇÃO`. A coluna `STATUS` e outros campos são usados quando estão presentes.

O limite atual de upload é 20 MB. Uma planilha aceita substitui a tabela carregada anteriormente depois que a leitura e a validação são concluídas. Caso o arquivo não tenha o formato esperado, a interface apresenta uma mensagem de erro.

Para usar novamente a versão inicial, importe a planilha `data/PCASP_TCEMG-2026_v12.2.xlsx`.

## 8. Como as sugestões são formadas

A busca normaliza maiúsculas e acentos e compara os termos digitados com o código, o título e a função das contas. Cada sugestão mostra os motivos textuais da correspondência. Alguns termos comuns de bens têm equivalências de busca, como `computador` e `notebook` relacionados a `equipamento`, `processamento` e `dados`, ou `cadeira` e `mesa` relacionados a `mobiliário` e `móveis`.

Os resultados são ordenados por coincidências textuais. A opção móvel/imóvel dá prioridade a contas cujo título ou função contém referências a esse tipo, mas não exclui automaticamente as demais contas. O sistema não compreende o contexto completo da aquisição nem confirma se uma conta é correta.

## 9. Limites e próximos passos possíveis

- A busca é lexical e depende dos termos existentes na descrição e na tabela; ela pode não encontrar uma conta adequada quando há pouca coincidência de palavras.
- A interface não registra o bem cadastrado nem a decisão final de classificação.
- Ainda não existe análise de uma planilha com bens já cadastrados.
- A função de importação da planilha está restrita ao computador principal; os demais dispositivos têm acesso de consulta.
- O limite de arquivo de 20 MB pode ser ajustado se houver necessidade de importar planilhas maiores.

Uma evolução possível é permitir importar uma planilha de bens existentes e apontar registros que mereçam revisão, mantendo as recomendações como alertas para conferência humana.
