# Consulta PCASP

Aplicação local para consultar contas do PCASP/TCEMG a partir da descrição de bens. A primeira versão usa busca por palavras relacionadas e apresenta contas candidatas para conferência humana.

## Abrir no VS Code

Abra a pasta `PROJETO_PCASP_2026` no VS Code. O interpretador do ambiente `.venv` está indicado em `.vscode/settings.json`.

Para iniciar no PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python run.py
```

O navegador abrirá em `http://127.0.0.1:8765`. Para encerrar, pressione `Ctrl+C` no terminal.

## Importar outra planilha

Use **Atualizar tabela PCASP** dentro da aplicação. A importação lê a primeira aba da planilha `.xlsx`, valida as colunas `CONTA`, `TÍTULO` e `FUNÇÃO` e substitui a base local somente depois de validar e importar as contas. O limite atual é 20 MB. A planilha base está em `data/PCASP_TCEMG-2026_v12.2.xlsx`; os dados de consulta são mantidos em `data/pcasp.sqlite3`.

## Módulos

- `app/xlsx_reader.py`: leitura de `.xlsx` sem dependências externas.
- `app/pcasp.py`: validação, importação, persistência SQLite e busca.
- `app/server.py`: servidor local e rotas HTTP.
- `app/web/`: interface e estilos.
- `app/config.py`: caminhos, host, porta e limite de upload.

O servidor escuta na rede local e mostra no terminal o endereço IP para os outros computadores. No computador principal, use `http://127.0.0.1:8765`. Nos demais, use o endereço `http://<IPv4-do-computador-principal>:8765` mostrado no terminal. O computador principal precisa permanecer ligado e conectado à mesma rede.

Se o Firewall do Windows bloquear conexões, abra o PowerShell como administrador e crie uma regra limitada à rede privada e à sub-rede local:

```powershell
New-NetFirewallRule -DisplayName "Consulta PCASP (rede local)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -Profile Private -RemoteAddress LocalSubnet
```

Os demais computadores podem consultar e comparar contas. A importação de planilhas fica disponível apenas no computador principal; abra o sistema nele por `127.0.0.1` para atualizar a tabela.

## Limites desta versão

As sugestões são ordenadas por coincidência de palavras no título e na função da conta. O filtro móvel/imóvel prioriza contas cujo texto menciona esse tipo, mas não exclui outras contas. O sistema não confirma se uma classificação está correta e não substitui a análise contábil.
