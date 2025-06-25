# 📦 Processamento Automático de Dados

Este repositório contém um sistema simples e automatizado para:

✔️ Obtenção diária de ficheiros de dados a partir de uma fonte externa  
✔️ Processamento local dos conteúdos obtidos  
✔️ Ajustes técnicos nos dados conforme requisitos internos  
✔️ Geração de ficheiros finais em formato comprimido (.gz)  
✔️ Publicação automática dos resultados neste repositório  

---

## ⚙️ Funcionamento

O sistema executa as seguintes etapas:

1. **Download** dos dados a partir da fonte definida no script  
2. **Validação** do ficheiro obtido  
3. **Processamento** e ajustes automáticos conforme parametrização interna  
4. **Geração** dos ficheiros finais prontos a utilizar  
5. **Commit** e **push** dos resultados de forma automatizada  

---

## 🗂️ Estrutura do Projeto

```plaintext
├── .github/
│   └── workflows/              # Automatização diária (limpeza e processamento)
├── processar.py                # Script principal de processamento
├── requirements.txt            # Dependências do Python
├── .gitignore                  # Definição dos ficheiros ignorados
├── README.md                   # Esta descrição
