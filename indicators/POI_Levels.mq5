//+------------------------------------------------------------------+
//|                                                   POI_Levels.mq5 |
//|                                     Indicador de Níveis POI      |
//|                                                                  |
//|  INSTALAÇÃO:                                                     |
//|    1. Abra o MetaEditor (F4 no MT5)                              |
//|    2. Copie este arquivo para:                                   |
//|         C:\Users\<Usuário>\AppData\Roaming\MetaQuotes\           |
//|           Terminal\<ID>\MQL5\Indicators\                         |
//|    3. No MetaEditor, abra o arquivo e pressione F7 para compilar |
//|    4. No MT5, arraste o indicador da aba "Indicadores" para o    |
//|       gráfico e preencha os preços dos níveis POI nos campos     |
//|       de entrada                                                 |
//|                                                                  |
//|  USO:                                                            |
//|    - Preencha até 10 níveis de COMPRA (buy) e 10 de VENDA (sell) |
//|    - Valores iguais a 0.0 são ignorados (não plotados)           |
//|    - Níveis de compra aparecem em VERDE, venda em VERMELHO        |
//+------------------------------------------------------------------+
#property copyright   "Trade Bot MT5"
#property link        ""
#property version     "1.00"
#property description "Plota linhas horizontais nos níveis POI (Point of Interest)"
#property description "configurados na estratégia do robô."
#property indicator_chart_window
#property indicator_plots 0

//--- Parâmetros de entrada: níveis de COMPRA (suporte)
input double BuyLevel1  = 0.0;  // Nível Compra 1
input double BuyLevel2  = 0.0;  // Nível Compra 2
input double BuyLevel3  = 0.0;  // Nível Compra 3
input double BuyLevel4  = 0.0;  // Nível Compra 4
input double BuyLevel5  = 0.0;  // Nível Compra 5
input double BuyLevel6  = 0.0;  // Nível Compra 6
input double BuyLevel7  = 0.0;  // Nível Compra 7
input double BuyLevel8  = 0.0;  // Nível Compra 8
input double BuyLevel9  = 0.0;  // Nível Compra 9
input double BuyLevel10 = 0.0;  // Nível Compra 10

//--- Parâmetros de entrada: níveis de VENDA (resistência)
input double SellLevel1  = 0.0; // Nível Venda 1
input double SellLevel2  = 0.0; // Nível Venda 2
input double SellLevel3  = 0.0; // Nível Venda 3
input double SellLevel4  = 0.0; // Nível Venda 4
input double SellLevel5  = 0.0; // Nível Venda 5
input double SellLevel6  = 0.0; // Nível Venda 6
input double SellLevel7  = 0.0; // Nível Venda 7
input double SellLevel8  = 0.0; // Nível Venda 8
input double SellLevel9  = 0.0; // Nível Venda 9
input double SellLevel10 = 0.0; // Nível Venda 10

//--- Parâmetros visuais
input color  BuyColor   = clrLime;              // Cor das linhas de Compra
input color  SellColor  = clrRed;               // Cor das linhas de Venda
input int    LineWidth  = 1;                    // Espessura das linhas
input ENUM_LINE_STYLE LineStyle = STYLE_SOLID;  // Estilo das linhas

//--- Prefixo exclusivo para nomear os objetos (evita conflito com outros indicadores)
#define PREFIX "POI_"

//+------------------------------------------------------------------+
//| Cria ou atualiza uma linha horizontal no gráfico                 |
//+------------------------------------------------------------------+
void CreateLine(const string name, const double price, const color clr)
{
   if(price == 0.0)
      return;

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   }
   else
   {
      ObjectSetDouble(0, name, OBJPROP_PRICE, price);
   }

   ObjectSetInteger(0, name, OBJPROP_COLOR,   clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE,   LineStyle);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,   LineWidth);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,  true);
   ObjectSetString( 0, name, OBJPROP_TOOLTIP, name + " = " + DoubleToString(price, _Digits));
}

//+------------------------------------------------------------------+
//| Cria todas as linhas definidas nos inputs                        |
//+------------------------------------------------------------------+
void DrawAllLines()
{
   //--- Níveis de compra
   double buyLevels[10] = {
      BuyLevel1,  BuyLevel2,  BuyLevel3,  BuyLevel4,  BuyLevel5,
      BuyLevel6,  BuyLevel7,  BuyLevel8,  BuyLevel9,  BuyLevel10
   };

   for(int i = 0; i < 10; i++)
   {
      string name = PREFIX + "BUY_" + IntegerToString(i + 1);
      if(buyLevels[i] != 0.0)
         CreateLine(name, buyLevels[i], BuyColor);
      else
         ObjectDelete(0, name);  // Remove linha se o nível foi zerado
   }

   //--- Níveis de venda
   double sellLevels[10] = {
      SellLevel1,  SellLevel2,  SellLevel3,  SellLevel4,  SellLevel5,
      SellLevel6,  SellLevel7,  SellLevel8,  SellLevel9,  SellLevel10
   };

   for(int i = 0; i < 10; i++)
   {
      string name = PREFIX + "SELL_" + IntegerToString(i + 1);
      if(sellLevels[i] != 0.0)
         CreateLine(name, sellLevels[i], SellColor);
      else
         ObjectDelete(0, name);
   }

   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Remove todos os objetos criados por este indicador               |
//+------------------------------------------------------------------+
void RemoveAllLines()
{
   for(int i = 1; i <= 10; i++)
   {
      ObjectDelete(0, PREFIX + "BUY_"  + IntegerToString(i));
      ObjectDelete(0, PREFIX + "SELL_" + IntegerToString(i));
   }
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Inicialização do indicador                                       |
//+------------------------------------------------------------------+
int OnInit()
{
   DrawAllLines();
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Finalização — remove todas as linhas ao remover o indicador      |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   RemoveAllLines();
}

//+------------------------------------------------------------------+
//| Cálculo — redesenha as linhas a cada novo candle                 |
//+------------------------------------------------------------------+
int OnCalculate(const int       rates_total,
                const int       prev_calculated,
                const datetime &time[],
                const double   &open[],
                const double   &high[],
                const double   &low[],
                const double   &close[],
                const long     &tick_volume[],
                const long     &volume[],
                const int      &spread[])
{
   if(prev_calculated == 0)
      DrawAllLines();

   return(rates_total);
}
//+------------------------------------------------------------------+
