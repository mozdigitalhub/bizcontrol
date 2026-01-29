# BizControl — UI/UX Design System & Visual Patterns

## 1) Objetivo

Este documento define o **Design System oficial do BizControl**.  
Todas as páginas, componentes e fluxos da aplicação **DEVEM** seguir este padrão para garantir consistência visual, usabilidade e escalabilidade.

Este ficheiro é a **fonte única de verdade** para UI/UX do BizControl.

---

## 2) Princípios de Design (MUST)

1. Clareza acima de estética
2. Consistência absoluta entre páginas
3. Baixa carga cognitiva
4. Mobile-first, desktop-optimized
5. Feedback visual imediato para qualquer ação

---

## 3) Sistema de Cores

### 3.1 Cores Primárias (Brand)

Usadas para ações principais, estados ativos e CTA.

- Primary 600 (default): `#2563EB`
- Primary 700 (hover): `#1D4ED8`
- Primary 500 (soft): `#3B82F6`

### 3.2 Cores Secundárias

Usadas para suporte visual e ações secundárias.

- Secondary 600: `#0F766E`
- Secondary 500: `#14B8A6`

### 3.3 Cores Semânticas

- Success: `#16A34A`
- Warning: `#F59E0B`
- Danger: `#DC2626`
- Info: `#0284C7`

## 3.4 Contraste e Legibilidade (MUST)

A UI do BizControl deve garantir **legibilidade perfeita** em botões, badges e elementos com fundo colorido.

### Regras obrigatórias

1. **Texto em superfícies coloridas fortes (Primary/Secondary/Danger/Warning/Info) deve ser branco** (`#FFFFFF`).
2. Se for necessário usar texto escuro, então o fundo deve ser uma versão “soft” (muito clara) da cor.
3. Chips/Badges nunca podem ter texto com a mesma “família” de cor do fundo (ex.: azul sobre azul).
4. **Evitar texto pequeno em botões e badges**: mínimo 12px, preferencial 14px.
5. Estados “Disabled” devem manter contraste suficiente (texto nunca pode ficar quase invisível).

### Tokens recomendados (para padronizar)

- On Primary (texto em primary): `#FFFFFF`
- On Secondary: `#FFFFFF`
- On Danger: `#FFFFFF`
- On Warning: `#111827` (warning é claro; se usar warning forte, então `#FFFFFF`)
- On Info: `#FFFFFF`

---

## 4) Cores Neutras (Base UI)

- App background: `#F8FAFC`
- Card background: `#FFFFFF`
- Border light: `#E5E7EB`
- Text primary: `#0F172A`
- Text secondary: `#475569`
- Disabled: `#94A3B8`

❌ Nenhuma cor fora desta paleta pode ser usada sem aprovação.

---

## 5) Tipografia

### 5.1 Fonte

- Fonte principal: **Inter**
- Fallback: system-ui, sans-serif

### 5.2 Escala tipográfica

| Uso           | Tamanho | Peso |
| ------------- | ------- | ---- |
| Page title    | 24–28px | 600  |
| Section title | 18–20px | 600  |
| Card title    | 16px    | 600  |
| Body text     | 14px    | 400  |
| Helper / hint | 12px    | 400  |

❌ Nunca usar texto abaixo de 12px  
❌ Nunca misturar fontes

---

## 6) Botões (CRÍTICO)

### 6.1 Primary Button

- Background: Primary 600
- Texto: branco
- Hover: Primary 700
- Uso: ação principal da tela

Exemplos:

- Salvar
- Confirmar
- Criar Venda
- Finalizar Sessão

Regras:

- Máximo **1 botão primary por tela**
- Nunca usar para ações destrutivas

---

### 6.2 Secondary Button

- Background: branco
- Border: Primary 600
- Texto: Primary 600
- Uso: ações alternativas

---

### 6.3 Danger Button

- Background: Danger
- Texto: branco
- Uso exclusivo para ações destrutivas

Exemplos:

- Apagar
- Cancelar Venda
- Remover Produto

---

### 6.4 Regras gerais de botões

- Ícones sempre à esquerda do texto
- Botão disabled deve parecer claramente inativo
- Texto do botão deve ser claro (nunca “OK” ou “Sim”)

### 6.5 Legibilidade em Botões (MUST)

- Botões Primary/Secondary solid/Danger/Info/Sucesso com fundo forte **DEVEM** ter texto `#FFFFFF`.
- Se o botão tiver fundo branco (outline/ghost), o texto deve usar Primary 600 e manter contraste.
- Evitar “texto cinza claro” em botões com fundo claro.

---

## 7) Formulários & Inputs

### 7.1 Inputs padrão

- Altura: 40px
- Border radius: 8px
- Border: 1px solid Border light
- Focus: border Primary 600 + shadow leve

### 7.2 Estados obrigatórios

- Normal
- Focus
- Error (border Danger + texto explicativo)
- Disabled

### 7.3 Labels & mensagens

- Label sempre acima do campo
- Campos obrigatórios com `*`
- Mensagem de erro clara e específica

❌ Placeholder não substitui label  
❌ Mensagens genéricas (“Erro”) são proibidas

## 7.4 Inputs com Ícone Interno (MUST)

Todos os campos de formulário (input/select/search) **DEVEM** ter um ícone dentro do próprio campo, à esquerda (leading icon).

### Estrutura visual

- Ícone fica dentro do input (não fora)
- Ícone alinhado verticalmente ao centro
- Ícone com cor neutra (Text secondary)
- O texto do input deve ter padding-left suficiente para não colidir com o ícone

### Regras

1. O ícone deve estar dentro da borda do input.
2. O input deve ter `padding-left` aumentado (ex.: 40–44px).
3. O ícone não deve capturar cliques (pointer-events: none).
4. Em erro, o ícone pode ficar Danger (opcional), mas sem exagero.

---

## 8) Tabelas (Listagens)

### 8.1 Estrutura

- Header fixo
- Zebra rows
- Hover highlight
- Paginação no rodapé

### 8.2 Conteúdo

- Texto à esquerda
- Valores monetários à direita
- Datas em formato consistente

### 8.3 Ações

- Coluna de ações sempre à direita
- Preferir ícones com tooltip
- Ações destrutivas em vermelho

## 8.4 Badges / Chips (Status Pills)

Badges são usados para estados como: Rascunho, Não paga, Paga, Cancelada, Em atraso, etc.

### Padrões

1. **Solid Badge** (fundo forte):
   - Fundo: Primary/Success/Danger/Info
   - Texto: `#FFFFFF`
   - Border radius: 9999px (pill)
   - Padding: 6px 10px
   - Font: 12–14px, peso 600

2. **Soft Badge** (fundo claro):
   - Fundo: versão clara (10–15% opacidade) da cor
   - Texto: cor forte correspondente (Primary 700 / Success 700 / Danger 700)
   - Usar quando o layout já tiver muito “peso” visual

### Regras

- Nunca usar texto azul em fundo azul forte.
- Nunca usar fundo forte com texto escuro.
- Badges devem ser consistentes em toda a aplicação.

---

## 9) Cards & Dashboards

### 9.1 Card padrão

- Background branco
- Border radius: 12px
- Shadow leve
- Padding: 16–20px

### 9.2 KPI Cards

- Valor em destaque
- Label pequeno
- Ícone discreto
- Cor semântica apenas no ícone ou detalhe lateral

❌ Nunca usar múltiplas cores fortes no mesmo card

---

## 10) Layout & Espaçamento

### 10.1 Grid

- Desktop: 12 colunas
- Mobile: 1 coluna

### 10.2 Espaçamento

- Base: 4px
- Usar múltiplos de: 8 / 16 / 24 / 32

---

## 11) Feedback & Estados

### 11.1 Loading

- Preferir skeleton loaders
- Spinner apenas em ações pontuais

### 11.2 Toasts & Alerts

- Posição: canto superior direito
- Auto-close: 3–5 segundos
- Cor semântica adequada

---

## 12) Modais & Diálogos

- Overlay escuro
- Largura controlada
- Ação principal à direita
- Cancelar à esquerda

❌ Evitar formulários longos em modal  
❌ Modal não deve ter scroll infinito

---

## 13) Ícones

- Biblioteca única (ex: Lucide ou Heroicons)
- Tamanho padrão: 20–24px
- Cor neutra por default

---

## 14) Dark Patterns (PROIBIDOS)

- Ações destrutivas sem confirmação
- Botões enganosos
- Confirmações escondidas
- Texto ambíguo

---

## 15) Checklist UI (MUST)

- [ ] Apenas cores do design system
- [ ] Botões seguem os tipos definidos
- [ ] Tipografia consistente
- [ ] Inputs com estados claros
- [ ] Feedback visual para ações
- [ ] Responsivo
- [ ] Nenhuma nova cor ou componente sem aprovação

---

## 16) Prompt obrigatório para Codex (UI)

Read and strictly follow:
docs/design/ui-design-system.md

Rules:

- Do not introduce new colors or components
- Reuse existing button, form, table, and card patterns
- Maintain visual and interaction consistency across pages

Output:

- List UI components used
- Confirm compliance with the design system
