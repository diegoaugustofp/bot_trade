# Indicadores MQL5 — Trade Bot MT5

## POI_Levels.mq5

Indicador que plota linhas horizontais no gráfico do MetaTrader 5 nos exatos níveis POI (*Point of Interest*) configurados na estratégia do robô. Permite que você visualize no MT5 os mesmos suportes e resistências que o bot usa para gerar sinais de entrada.

- **Linhas verdes** → Níveis de compra (suporte)
- **Linhas vermelhas** → Níveis de venda (resistência)
- Até **10 níveis de compra** + **10 níveis de venda** por instância
- Valores `0.0` são ignorados (linha não é plotada)
- Ao remover o indicador do gráfico, todas as linhas desaparecem automaticamente

---

## Instalação

### 1. Localizar a pasta de indicadores do MT5

Abra o **MetaTrader 5** e no menu superior clique em:

```
Arquivo → Abrir pasta de dados
```

Na janela que abrir, navegue até:

```
MQL5\Indicators\
```

### 2. Copiar o arquivo

Copie o arquivo `POI_Levels.mq5` para dentro da pasta `MQL5\Indicators\`.

### 3. Compilar no MetaEditor

1. No MT5, pressione **F4** para abrir o MetaEditor
2. No painel esquerdo (Navegador), localize `Indicadores > POI_Levels`
3. Dê dois cliques para abrir o arquivo
4. Pressione **F7** (ou clique no botão **Compilar**)
5. Verifique se a compilação foi concluída sem erros

### 4. Adicionar ao gráfico

1. No MT5, no painel **Navegador** (Ctrl+N), expanda **Indicadores**
2. Localize **POI_Levels** e arraste para o gráfico desejado
3. Na janela de configuração, preencha os campos:

| Parâmetro | Descrição |
|-----------|-----------|
| `BuyLevel1` … `BuyLevel10` | Preços dos níveis de compra (suporte) |
| `SellLevel1` … `SellLevel10` | Preços dos níveis de venda (resistência) |
| `BuyColor` | Cor das linhas de compra (padrão: verde) |
| `SellColor` | Cor das linhas de venda (padrão: vermelho) |
| `LineWidth` | Espessura das linhas (1–5) |
| `LineStyle` | Estilo: sólido, tracejado, pontilhado, etc. |

4. Clique em **OK** para aplicar

---

## Dicas de uso

- Use os mesmos valores configurados no campo `poi_levels` do `bot_config.json` ou no dashboard web para garantir que o que você vê no gráfico seja exatamente o que o bot está monitorando.
- Você pode adicionar **múltiplas instâncias** do indicador no mesmo gráfico (cada uma com um conjunto diferente de níveis).
- Para atualizar os preços, basta dar dois cliques nas linhas ou acessar as propriedades do indicador no gráfico.
