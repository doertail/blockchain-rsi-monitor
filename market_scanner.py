import yfinance as yf
import pandas as pd
import warnings
import datetime

# 경고 메시지 차단
warnings.simplefilter(action='ignore', category=FutureWarning)

# ANSI 색상 코드
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

tickers = ['BLOK', 'QQQM', 'GLXY', 'CRCL', 'COIN']

# ■ 핵심 수정: 종목별 맞춤형 매수 기준 (Threshold Tuning)
buy_thresholds = {
    'QQQM': 40,      # 지수형 ETF는 기준을 널널하게 (40 이하 매수 고려)
    'BLOK': 35,      # 섹터 ETF는 중간 정도
    'GLXY': 30,   # 변동성 큰 개별주는 엄격하게 (30 이하)
    'CRCL': 30,       # 개별주 표준
    'COIN': 30
}

def get_signal(ticker, rsi):
    # 해당 티커의 매수 기준 가져오기 (없으면 기본값 30)
    limit = buy_thresholds.get(ticker, 30)
    
    if rsi <= limit:
        return f"{GREEN}STRONG BUY (RSI < {limit}){RESET}"
    elif rsi <= limit + 10: # 매수 기준 + 10 범위는 관망
        return f"{YELLOW}WATCH (Approaching Buy){RESET}"
    elif rsi >= 70:
        return f"{RED}STRONG SELL (Overbought){RESET}"
    elif rsi >= 60:
        return f"{BLUE}HOLD (Bullish){RESET}"
    else:
        return "WAIT (Neutral)"

print(f"\n{'Ticker':<10} | {'Price':<10} | {'RSI(14)':<10} | {'Action Signal'}")
print("-" * 65)

for ticker in tickers:
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        
        if df.empty:
            print(f"{ticker:<10} | {'N/A':<10} | {'N/A':<10} | Data Not Found")
            continue
            
        delta = df['Close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rs = ema_up / ema_down
        
        df['RSI'] = 100 - (100 / (1 + rs))
        
        current_price = float(df['Close'].iloc[-1])
        current_rsi = float(df['RSI'].iloc[-1])
        
        # ■ 수정: 함수 호출 시 ticker 전달
        signal = get_signal(ticker, current_rsi)
        
        rsi_str = f"{current_rsi:.2f}"
        limit = buy_thresholds.get(ticker, 30)

        # 색상 로직도 기준에 맞춰 동적으로 변경
        if current_rsi <= limit: rsi_display = f"{GREEN}{rsi_str}{RESET}"
        elif current_rsi <= limit + 10: rsi_display = f"{YELLOW}{rsi_str}{RESET}"
        elif current_rsi >= 70: rsi_display = f"{RED}{rsi_str}{RESET}"
        else: rsi_display = rsi_str

        print(f"{ticker:<10} | {current_price:<10.2f} | {rsi_display:<19} | {signal}")

    except Exception as e:
        print(f"{ticker:<10} | Error: {e}")

print("-" * 65)
print("■ Strategy based on Dynamic Thresholds (QQQM:40, BLOK:35, Others:30)")
print(f"Execution Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")