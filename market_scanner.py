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
BOLD = '\033[1m'

tickers = ['BLOK', 'QQQM', 'GLXY.TO', 'CRCL', 'COIN']

# 매수 기준 (RSI)
buy_thresholds = {
    'QQQM': 40, 'BLOK': 35, 'GLXY.TO': 30, 'CRCL': 30, 'COIN': 30
}

def get_signal(ticker, rsi):
    limit = buy_thresholds.get(ticker, 30)
    if rsi <= limit: return f"{GREEN}STRONG BUY{RESET}"
    elif rsi <= limit + 10: return f"{YELLOW}WATCH{RESET}"
    elif rsi >= 70: return f"{RED}STRONG SELL{RESET}"
    elif rsi >= 60: return f"{BLUE}HOLD{RESET}"
    else: return "WAIT"

def get_support_status(current_price, low_price):
    # 최근 3개월 최저가 대비 현재가가 5% 이내면 '지지선 근접'으로 판단
    diff = ((current_price - low_price) / low_price) * 100
    if diff <= 5.0:
        return f"{GREEN}Near Support (+{diff:.1f}%){RESET}"
    else:
        return f"Above Low (+{diff:.1f}%)"

print(f"\nExecution Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("-" * 80)
print(f"{'Ticker':<10} | {'Price':<10} | {'RSI':<15} | {'Support(3M)':<20} | {'Signal'}")
print("-" * 80)

for ticker in tickers:
    try:
        # 데이터 수집 (뉴스 포함을 위해 Ticker 객체 생성)
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
        lowest_price = float(df['Close'].min()) # 3개월 최저가
        
        # 신호 및 상태
        signal = get_signal(ticker, current_rsi)
        support_msg = get_support_status(current_price, lowest_price)
        
        # RSI 색상
        limit = buy_thresholds.get(ticker, 30)
        rsi_str = f"{current_rsi:.2f}"
        if current_rsi <= limit: rsi_display = f"{GREEN}{rsi_str}{RESET}"
        elif current_rsi <= limit + 10: rsi_display = f"{YELLOW}{rsi_str}{RESET}"
        elif current_rsi >= 70: rsi_display = f"{RED}{rsi_str}{RESET}"
        else: rsi_display = rsi_str

        print(f"{ticker:<10} | {current_price:<10.2f} | {rsi_display:<15} | {support_msg:<20} | {signal}")

        # ■ STRONG BUY or WATCH일 때만 뉴스 출력 (터미널 오염 방지)
        if "STRONG BUY" in signal or "WATCH" in signal:
            print(f"  ↳ {BOLD}[News Check]{RESET}")
            news_list = stock.news
            count = 0
            if news_list:
                for news in news_list[:5]: # 최신 3개만
                    title = news.get('title', 'No Title')
                    link = news.get('link', '')
                    print(f"    • {title}")
            else:
                print("    • No recent news found.")
            print("")

    except Exception as e:
        print(f"{ticker:<10} | Error: {e}")

print("-" * 80)
print("■ Strategy: Low RSI + Near Support(Low Price) = Best Entry")