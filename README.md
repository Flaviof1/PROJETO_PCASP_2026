# Consulta PCASP

Aplicação local para consultar contas PCASP/TCEMG e organizar uma análise documentada de bens patrimoniais, com o objetivo de embasar uma futura mudança no sistema principal SH3/Siap. As sugestões são baseadas em correspondência de palavras e precisam de análise humana. A aplicação não se conecta ao SH3/Siap nem altera seu cadastro.

## Início rápido

No PowerShell, abra a pasta do projeto e execute:

```powershell
.\.venv\Scripts\python.exe run.py
```

A aplicação abre em `http://127.0.0.1:8765`. Deixe o terminal aberto enquanto usar o sistema; para encerrar, pressione `Ctrl+C`.

## O que o sistema faz

- **Consultar uma conta:** informe a descrição de um bem e confira contas candidatas, função, natureza do saldo e atributos disponíveis.
- **Tabela PCASP de referência:** é uma planilha Excel `.xlsx`, importada com as colunas `CONTA`, `TÍTULO` e `FUNÇÃO` na primeira aba. Essa tabela fornece as contas para consulta e as sugestões de revisão.
- **Comparar relatórios:** opcionalmente, envie o CSV `Localizar Bens` e o TXT `PCASP - Inventário Ativo`. O TXT é o relatório contábil de saldos; o sistema compara a soma de `Valor Atual` por `Conta Bem` com o `Saldo Final` e indica diferenças para conferência.
- **Revisar sugestões por bem:** envie o CSV do inventário e `Localizar Plano de Contas.csv` do SH3/Siap. As candidatas são confrontadas com o PCASP e marcadas como cadastradas ou ausentes no SH3. Somente contas cadastradas podem ser aprovadas e exportadas; contas ausentes são sinalizadas para consulta à SH3.
- **Gerar comparativo Excel por conta:** compare os totais antes e depois das aprovações e a variação. A aba **Itens alterados** mostra o valor de cada bem aprovado, plaqueta, código, descrição, conta anterior e conta nova. Bens sem correspondência ficam fora dos totais finais e são listados no arquivo para conferência.
- **Limpar arquivos e análises:** remove os CSV/TXT escolhidos e os resultados da tela, mantendo as decisões salvas no banco local. **Apagar decisões salvas** remove essas decisões permanentemente. A tabela PCASP carregada é mantida.

## Aprovação e preservação do original

As sugestões por bem são apenas indicações para análise; não confirmam erro contábil. As decisões aprovadas ou de manter a conta ficam no banco local e são recuperadas quando o bem aparece em uma nova análise com o mesmo código e plaqueta e os dados atuais continuam compatíveis. No fluxo previsto, o inventário atualizado acrescenta bens sem alterar os registros existentes: as decisões antigas são mantidas e os bens novos entram sem decisão, para análise individual. Os arquivos CSV continuam sendo processados em memória.

Ao baixar, o sistema cria uma cópia de trabalho do CSV com as contas aprovadas e um comparativo dos totais antes e depois. Esses arquivos registram a análise e podem embasar a futura mudança no sistema principal. **O arquivo de origem não é sobrescrito, e o sistema não altera diretamente o SH3/Siap.**

Os arquivos são processados em memória e não são armazenados pela aplicação. O limite total de envio é 20 MB. A análise e a importação ficam disponíveis apenas no computador que hospeda o sistema.

## Passo a passo de uma revisão

1. Inicie a aplicação com `.\.venv\Scripts\python.exe run.py` e mantenha o terminal aberto.
2. Confirme que a tabela PCASP está carregada. Se precisar atualizá-la, importe a planilha `.xlsx` na seção **Atualizar tabela PCASP**.
3. Na revisão de bens, selecione o `Localizar Bens.csv` mais recente baixado do SH3/Siap e a relação completa `Localizar Plano de Contas.csv` atualizada. Se o arquivo apenas acrescentar bens e preservar os registros existentes, as decisões salvas desses bens serão recuperadas; os novos bens começarão sem decisão.
4. Clique em **Analisar bens**. As candidatas aparecem como cadastradas ou ausentes no SH3. Ausentes podem ser indicadas para consulta à SH3, mas não podem ser aprovadas.
5. Abra cada bem, confira plaqueta, características, conta atual e candidata. Aprove apenas a conta marcada **Cadastrada no SH3/Siap**; rejeitar mantém a conta atual.
6. Baixe a **cópia com aprovadas** e o **comparativo Excel** para registrar as decisões e fundamentar a futura mudança. Esses arquivos não atualizam o sistema principal e não substituem o inventário de entrada.
7. Em cada nova rodada, baixe novamente do SH3/Siap o `Localizar Bens.csv` mais recente e também a relação `Localizar Plano de Contas.csv` atualizada. Quando o inventário apenas incluir novos bens, as decisões dos registros preservados serão retomadas e os novos aparecerão para análise. O comparativo e a cópia gerada servem como documentação e apoio à avaliação da futura mudança; não atualizam o SH3/Siap.
8. Use **Limpar arquivos e análises** para começar uma revisão limpa. Esse botão mantém a tabela PCASP carregada.

O arquivo original nunca é sobrescrito e a aplicação não grava diretamente no SH3/Siap. As decisões ficam salvas no banco local; a cópia e o comparativo servem como documentação para avaliar uma futura mudança.

## Acesso pela rede local

O terminal mostra o endereço IPv4 do computador principal. Em outro dispositivo conectado à mesma rede privada, acesse `http://<IPv4-do-computador-principal>:8765`. O computador principal deve permanecer ligado e com a aplicação aberta.

Se necessário, no PowerShell como administrador, permita a porta `8765` na rede privada local:

```powershell
New-NetFirewallRule -DisplayName "Consulta PCASP (rede local)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -Profile Private -RemoteAddress LocalSubnet
```

O acesso pela internet ou por outras redes ainda requer uma configuração de hospedagem e segurança apropriada.

## Documentação completa

Consulte [DOCUMENTACAO.md](DOCUMENTACAO.md) ou abra [DOCUMENTACAO.html](DOCUMENTACAO.html) no navegador.
