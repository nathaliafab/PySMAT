# PySMAT

Ferramenta para identificação de conflitos semânticos em cenários de merge para projetos Python.

## Instruções rápidas

- Clone o repositório.
- Instale Python 3.8+ (se não estiver instalado):

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip
python3 --version  # Para verificar
```
- Instale as dependências do `requirements.txt`:

```bash
pip install -r SMAT/requirements.txt
```

- Altere o arquivo de configuração [`/SMAT/nimrod/tests/env-config.json`](/SMAT/nimrod/tests/env-config.json): 
  - Atualize o campo `input_path` com o [caminho do arquivo de cenários](/input-smat.json)
  - Configure a chave da API do Gemini em `api_params` (campo `api-key`)
  - Se não tiver uma chave, crie [acessando esse url com sua conta Google](https://aistudio.google.com/u/1/api-keys)

- Em [`input-smat.json`](input-smat.json), verifique os caminhos em `scenarioFiles` que apontam para os arquivos Python nas versões base, left, right e merge.

- Para rodar o experimento use:

```bash
python3 run_experiment.py
```

## Estrutura do Projeto

O PySMAT trabalha com 4 versões de arquivos Python:
- `python_files/base.py` - Versão base do código
- `python_files/left.py` - Versão do branch esquerdo
- `python_files/right.py` - Versão do branch direito  
- `python_files/merge.py` - Versão merged

A ferramenta gera testes automaticamente usando IA (Gemini) e executa esses testes nas 4 versões para detectar conflitos semânticos.
