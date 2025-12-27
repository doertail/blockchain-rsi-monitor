import yfinance as yf
import pandas as pd
import warnings
import datetime

# 경고 차단
warnings.simplefilter(action='ignore', category=FutureWarning)

# ANSI 색상
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

tickers = ['BLOK', 'QQQM', 'GLXY', 'CRCL', 'COIN', 'ETH-USD']

# 매수 기준 (RSI)
buy_thresholds = {
    'QQQM': 40, 'BLOK': 35, 'GLXY': 30, 'CRCL': 30, 'COIN': 30, 'ETH-USD': 30
}

def get_signal(ticker, rsi):
    limit = buy_thresholds.get(ticker, 30)
    if rsi <= limit: return f"{GREEN}STRONG BUY{RESET}"
    elif rsi <= limit + 10: return f"{YELLOW}WATCH{RESET}"
    elif rsi >= 70: return f"{RED}STRONG SELL{RESET}"
    elif rsi >= 60: return f"{BLUE}HOLD{RESET}"
    else: return "WAIT"

def get_support_status(current_price, low_price):
    diff = ((current_price - low_price) / low_price) * 100
    if diff <= 5.0:
        return f"{GREEN}Near Support (+{diff:.1f}%){RESET}"
    else:
        return f"Above Low (+{diff:.1f}%)"

def get_rsi_color(ticker, rsi):
    limit = buy_thresholds.get(ticker, 30)
    if rsi <= limit: return GREEN
    elif rsi <= limit + 10: return YELLOW
    elif rsi >= 70: return RED
    else: return RESET # 색상 없음 (기본)

print(f"\nExecution Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("-" * 80)
# 헤더 간격 조정
print(f"{'Ticker':<10} | {'Price':<10} | {'RSI':<15} | {'Support(3M)':<20} | {'Signal'}")
print("-" * 80)

for ticker in tickers:
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="3mo")
        
        if df.empty:
            print(f"{ticker:<10} | {'N/A':<10} | Data Not Found")
            continue
            
        # RSI 계산
        delta = df['Close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=13, adjust=False).mean()
        ema_down = down.ewm(com=13, adjust=False).mean()
        rs = ema_up / ema_down
        df['RSI'] = 100 - (100 / (1 + rs))
        
        current_price = float(df['Close'].iloc[-1])
        current_rsi = float(df['RSI'].iloc[-1])
        lowest_price = float(df['Close'].min())
        
        # 신호 및 상태
        signal = get_signal(ticker, current_rsi)
        support_msg = get_support_status(current_price, lowest_price)
        
        # ■ 수정: RSI 색상과 숫자 포맷팅 분리 (줄맞춤 해결 핵심)
        rsi_color = get_rsi_color(ticker, current_rsi)
        
        # 색상 코드는 문자열 길이에 포함시키지 않고, 숫자 포맷팅(<15.2f)만 적용 후 감싸기
        rsi_display = f"{rsi_color}{current_rsi:<15.2f}{RESET}"

        print(f"{ticker:<10} | {current_price:<10.2f} | {rsi_display} | {support_msg:<20} | {signal}")

    except Exception as e:
        print(f"{ticker:<10} | Error: {e}")

print("-" * 80)
print("■ Strategy: Low RSI + Near Support(Low Price) = Best Entry")