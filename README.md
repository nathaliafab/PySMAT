# PySMAT

Ferramenta para identificação de conflitos semânticos em cenários de merge para projetos Python.


## Estrutura do Projeto

O PySMAT trabalha com 4 versões de arquivos Python:
- `python_files/base.py` - Versão base do código
- `python_files/left.py` - Versão do branch esquerdo
- `python_files/right.py` - Versão do branch direito  
- `python_files/merge.py` - Versão merged

A ferramenta gera testes automaticamente usando [IA (Gemini)](https://ai.google.dev/gemini-api/docs/models) ou [Pynguin](https://pynguin.readthedocs.io/latest/) e executa esses testes nas 4 versões para detectar conflitos semânticos.


## 🐋 Executando com Docker Compose

Este guia explica como executar o PySMAT em um ambiente containerizado usando **Docker Compose**. Isso garante um ambiente consistente com Python 3.11, independentemente do seu sistema operacional.

## 1. Pré-requisitos

Instale o Docker no seu sistema:

* **Docker Desktop** (Recomendado para Windows e Mac): [Download aqui](https://docs.docker.com/desktop/)
* **Docker Engine** (Para Linux): [Guia de Instalação](https://docs.docker.com/engine/install/)

## 2. Configuração

Antes de executar o container, você precisa ajustar o arquivo de configuração (`nimrod/tests/env-config.json`). Aponte o caminho `input_smat` para a localização dentro do container. Se estiver na pasta raiz:

```json
"input_path": "/app/input-smat.json",
```

Além disso, certifique-se de que o caminho para os arquivos python em `input_smat` esteja correto e aponte para a localização dentro do container. Por exemplo:

```json
"scenarioFiles": {
    "base": "/app/python_files/base.py",
    "left": "/app/python_files/left.py",
    "right": "/app/python_files/right.py",
    "merge": "/app/python_files/merge.py"
},
```

Configure também a chave da API do Gemini em `api_params` (campo `api-key`).
  - Se não tiver uma chave, crie [acessando esse url com sua conta Google](https://aistudio.google.com/u/1/api-keys).

## 3. Executando o Container

Navegue até a raiz do projeto e execute o seguinte comando de acordo com seu SO:

### Linux & macOS (Terminal)

O seguinte comando passa seus IDs de usuário e grupo para evitar problemas de permissão com arquivos gerados:

```bash
USER_ID=$(id -u) GROUP_ID=$(id -g) docker compose run --rm --build pysmat
```

### Windows (PowerShell)

No PowerShell, as variáveis são tratadas de forma diferente:

```powershell
$env:USER_ID=1000; $env:GROUP_ID=1000; docker compose run --rm --build pysmat
```

*Nota: No Windows, os UIDs/GIDs padrão 1000 geralmente são suficientes para o Docker Desktop.*


## 4. Uso Dentro do Container

Uma vez que o comando termine, você estará dentro do shell Ubuntu em `/app`. Você pode executar testes ou iniciar uma análise:

```bash
# Verifique se o volume está montado corretamente
ls

# Execute a ferramenta
python3 run_experiment.py
```


## Solução de Problemas

* **Permissão Negada**: No Linux, verifique se `USER_ID` e `GROUP_ID` correspondem à saída do comando `id` no seu terminal host.
* **Mudanças de Arquivos**: Como usamos volumes, qualquer mudança de código feita na sua máquina host será instantaneamente refletida dentro do container.
