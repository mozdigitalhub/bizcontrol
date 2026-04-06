# Importar Stock (Excel)

## Formato do ficheiro
- Cada folha do Excel representa uma **categoria**.
- O nome da folha vira o nome da categoria (trim).

### Cabecalho obrigatorio (linha 1)
1. **Descrição do Item**
2. **Un.**
3. **PREÇO DE COMPRA** (opcional)
4. **PREÇO DE VENDA** (obrigatorio)
5. **ENTRADA** (obrigatorio)

## Regras
- "Descrição do Item" identifica o produto (case-insensitive, trim).
- SKU e gerado automaticamente: `slug + hash curto`.
- Se o produto existir:
  - Atualiza unidade, preco de venda e custo (quando informado).
  - Ajusta stock via movimento (delta).
- Se nao existir:
  - Cria produto e movimento de entrada.

## Acesso
- Menu: **Produtos & Stock ? Importar Stock (Excel)**
- Requer permissao: `catalog.add_product`.
