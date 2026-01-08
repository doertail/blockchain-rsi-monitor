import yfinance as yf
import warnings
import datetime
import requests
import os
import sys
from io import StringIO
from dotenv import load_dotenv
from google import genai
from pathlib import Path

# 환경 변수 로드
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
# load_dotenv()

# 경고 차단
warnings.simplefilter(action='ignore', category=FutureWarning)

# ANSI 색상
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

tickers = ['BLOK', 'QQQM','TSLA', 'CRCL', 'COIN', 'ETH-USD', 'BTC-USD']

# 매수 기준 (RSI
buy_thresholds = {
    'QQQM': 40, 'BLOK': 35,'TSLA': 35, 'CRCL': 30, 'COIN': 30, 'ETH-USD': 30, 'BTC-USD': 30
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

def send_to_discord(content):
    """디스코드 웹훅으로 메시지 전송 (2000자 제한 처리 - 여러 메시지로 분할)"""
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

    if not webhook_url:
        print(f"{YELLOW}⚠️ 디스코드 웹훅 URL이 없습니다. .env를 확인하세요.{RESET}")
        return

    # 디스코드 메시지 길이 제한: 2000자
    # 긴 메시지는 여러 개로 나눠서 전송
    max_length = 1900
    chunks = []

    if len(content) <= max_length:
        chunks.append(content)
    else:
        # 줄 단위로 나눠서 청크 생성
        lines = content.split('\n')
        current_chunk = ""

        for line in lines:
            # 현재 청크에 라인을 추가했을 때 길이 초과하면
            if len(current_chunk) + len(line) + 1 > max_length:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line + '\n'
            else:
                current_chunk += line + '\n'

        # 마지막 청크 추가
        if current_chunk:
            chunks.append(current_chunk)

    # 여러 메시지로 전송
    try:
        for i, chunk in enumerate(chunks):
            payload = {
                "content": chunk,
                "username": "Sniper Bot",
                "avatar_url": "https://cdn-icons-png.flaticon.com/512/2525/2525752.png"
            }
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()

        print(f"\n{GREEN}✅ 디스코드 전송 완료 ({len(chunks)}개 메시지).{RESET}")
    except Exception as e:
        print(f"\n{RED}❌ 디스코드 전송 실패: {e}{RESET}")

def scan_market():
    """시장 스캔을 수행하고 결과를 반환 (MA120 추가 버전)"""
    # 출력 캡처 시작
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    print(f"\nExecution Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 105) # 표 너비 조정
    # 헤더에 Trend(MA120) 추가
    print(f"{'Ticker':<10} | {'Price':<10} | {'RSI':<15} | {'Trend (MA120)':<20} | {'Support(3M)':<20} | {'Signal'}")
    print("-" * 105)

    market_data = []

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # 중요: 120일 이동평균을 계산하려면 최소 6개월 이상의 데이터가 필요함 -> 1y로 변경
            df = stock.history(period="1y")

            if df.empty or len(df) < 120:
                print(f"{ticker:<10} | {'N/A':<10} | Data Not Sufficient (Need >120 days)")
                continue

            # RSI 계산
            delta = df['Close'].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=13, adjust=False).mean()
            ema_down = down.ewm(com=13, adjust=False).mean()
            rs = ema_up / ema_down
            df['RSI'] = 100 - (100 / (1 + rs))

            # MA120 (120일 이동평균선) 계산
            df['MA120'] = df['Close'].rolling(window=120).mean()

            current_price = float(df['Close'].iloc[-1])
            current_rsi = float(df['RSI'].iloc[-1])
            current_ma120 = float(df['MA120'].iloc[-1])
            lowest_price = float(df['Close'][-90:].min()) # 최근 3개월 저점 (슬라이싱으로 조정)

            # 신호 및 상태
            signal = get_signal(ticker, current_rsi)
            support_msg = get_support_status(current_price, lowest_price)

            # RSI 색상
            rsi_color = get_rsi_color(ticker, current_rsi)
            rsi_display = f"{rsi_color}{current_rsi:<15.2f}{RESET}"

            # MA120 상태 판별 (Trend)
            if current_price >= current_ma120:
                trend_msg = f"{GREEN}Bullish (Above){RESET}"
                ma_gap = f"(+{((current_price - current_ma120)/current_ma120)*100:.1f}%)"
            else:
                trend_msg = f"{RED}Bearish (Below){RESET}"
                ma_gap = f"({((current_price - current_ma120)/current_ma120)*100:.1f}%)"
            
            trend_display = f"{trend_msg} {ma_gap}"

            print(f"{ticker:<10} | {current_price:<10.2f} | {rsi_display} | {trend_display:<30} | {support_msg:<20} | {signal}")

            # 구조화된 데이터 저장 (Gemini 전송용)
            market_data.append({
                'ticker': ticker,
                'price': current_price,
                'rsi': current_rsi,
                'ma120': current_ma120,
                'trend': 'Bullish' if current_price >= current_ma120 else 'Bearish',
                'trend_gap': ((current_price - current_ma120)/current_ma120)*100,
                'signal': signal.replace(GREEN, '').replace(YELLOW, '').replace(RED, '').replace(BLUE, '').replace(RESET, '').strip()
            })

        except Exception as e:
            print(f"{ticker:<10} | Error: {e}")

    print("-" * 105)

    # 출력 캡처 종료
    sys.stdout = old_stdout
    output = captured_output.getvalue()

    return output, market_data

def analyze_with_gemini(scan_output, market_data):
    """Gemini API를 사용하여 시장 분석 (Trend Filter 적용 버전)"""
    api_key = os.getenv('GEMINI_API_KEY')

    if not api_key:
        print("\n⚠️ GEMINI_API_KEY가 .env 파일에 설정되지 않았습니다.")
        return

    try:
        # Gemini API 클라이언트 생성
        client = genai.Client(api_key=api_key)

        # 전략 컨텍스트 정의 (환경 변수에서 포트폴리오 로드)
        portfolio_crcl = os.getenv('PORTFOLIO_CRCL', '0')
        portfolio_tsla = os.getenv('PORTFOLIO_TSLA', '0')
        portfolio_blok = os.getenv('PORTFOLIO_BLOK', '0')
        portfolio_qqqm = os.getenv('PORTFOLIO_QQQM', '0')
        portfolio_coin = os.getenv('PORTFOLIO_COIN', '0')
        portfolio_tlt = os.getenv('PORTFOLIO_TLT', '0')
        portfolio_cash = os.getenv('PORTFOLIO_CASH', '0')
        auto_invest_tsla = os.getenv('AUTO_INVEST_TSLA', '10')
        auto_invest_qqqm = os.getenv('AUTO_INVEST_QQQM', '20')
        my_persona = os.getenv('MY_PERSONA')

        strategy_context = f"""
        [사용자 페르소나]
        {my_persona}
        
        [투자 전략: The Sniper v2.0 (Trend Filtering)]
        1. 핵심 로직 (Logic Gate):
           - 조건 A (Price > MA120): '상승 추세'. RSI 과매도(30)는 강력한 매수 기회(Buy the Dip).
           - 조건 B (Price < MA120): '하락 추세'. RSI 과매도(30)는 '지하실 입구'일 가능성 높음. 보수적 접근 필수.

        2. 포트폴리오 상태:
           - CRCL: {portfolio_crcl}
           - TSLA: {portfolio_tsla} + 매일 {auto_invest_tsla}$ 적립
           - BLOK: {portfolio_blok}
           - QQQM: {portfolio_qqqm} + 매일 {auto_invest_qqqm}$ 적립
           - COIN: {portfolio_coin}$ 보유 (가격 정찰)
           - TLT: {portfolio_tlt} (안전자산)
           - 현금: {portfolio_cash}달러
        """

        # 분석 요청 프롬프트 (데이터 구조 반영)
        prompt = f"""
        당신은 세계적인 인지도를 가진 금융 전문가입니다.
        사용자의 자산을 지키는 '냉철한 리스크 관리 알고리즘'처럼 말해주십시오.
        단순히 RSI가 낮다고 매수를 외치지 말고, **'추세(Trend)'를 먼저 확인하고 판결을 내리십시오.**

        [입력 데이터]
        {market_data}
        (참고: 'trend_gap'은 현재가가 120일 이평선 대비 몇 % 위치에 있는지를 의미함. 마이너스면 하락 추세.)

        [분석 지침 및 출력 형식]

        **1. Tone & Manner:**
        - 사용자가 하락장에서 섣불리 매수 버튼을 누르려 할 때, 뼈 때리는 팩트로 제압할 것.
        - 형식적 인사 생략. 바로 본론 진입.

        **2. Report Structure:**

        **[System Status: Market Trend Check]**
        - 현재 시장이 'Bullish(상승장)'인지 'Bearish(하락장)'인지, 특히 QQQM(지수)과 개별 종목의 괴리를 한 문장으로 진단.

        **[Portfolio P&L Analysis]** ⚠️ 중요
        - **반드시** 포트폴리오 상태에 명시된 '평균 매수가'와 현재가를 비교하여 손익률(%)을 계산할 것.
        - 각 보유 종목별로:
          * 평균 매수가 vs 현재가 비교
          * 손익률 (%) 명시
          * 물린 종목(-손실)은 추가 매수 시 물타기 위험 경고
          * 수익 중인 종목(+수익)은 익절 타이밍 검토
        - 예시: "TSLA: 평균 444.15$ → 현재 431.41$ (-2.9% 손실). 추가 매수는 물타기 위험."

        **[Debugging & Action Plan]**
        - 각 종목별로 아래 로직을 적용하여 구체적 행동 지시.
        - **손익 상태를 반드시 고려**하여 판단할 것.

        * **Case 1: Bullish (Above MA120) + RSI Low** → "시스템 정상. 적극 매수(Aggressive Buy) 승인."
        * **Case 2: Bearish (Below MA120) + RSI Low** → "경고(Warning). 떨어지는 칼날임. RSI가 30이라도 매수 보류. 반등 시그널(양봉) 대기."
        * **Case 3: Deep Bearish (Below -10% from MA120)** → "시스템 위험. 지금 들어가면 물림. 관망(Wait)이 최선의 방어."
        * **Case 4: Ambiguous (RSI 40~60)** → "노이즈 구간. 리소스 낭비하지 말고 대기."
        * **Case 5: 손실 중(-) + Bearish** → "물타기 금지. 손절 라인 점검 필요."

        **[Final Compile]**
        - 오늘 밤 사용자가 실행해야 할 단 하나의 명령(Command)을 출력.
        - 예: "QQQM 적립만 수행하고, 코인 관련주는 앱 삭제하고 쳐다보지 마라."

        ---
        [전략 컨텍스트]
        {strategy_context}
        """

        print("\n" + "="*80)
        print("🤖 Gemini AI (Trend Filtered) 기술적 분석 중...")
        print("="*80 + "\n")

        # Failover Logic
        analysis_text = None
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=prompt
            )
            analysis_text = response.text
            print(f"{GREEN}✓ Gemini 2.0 모델 사용{RESET}\n")

        except Exception as e:
            print(f"{YELLOW}⚠️ Gemini 2.0 오류, 1.5로 전환: {e}{RESET}")
            try:
                response = client.models.generate_content(
                    model='gemini-flash-latest',
                    contents=prompt
                )
                analysis_text = response.text
                print(f"{GREEN}✓ Gemini 1.5 모델 사용{RESET}\n")
            except Exception as e2:
                print(f"{RED}❌ 분석 실패: {e2}{RESET}")
                return

        if not analysis_text: return

        print(analysis_text)
        print("\n" + "="*80)

        # 디스코드 전송
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        discord_msg = f"## 📡 Sniper Report v2.0 (Trend Check) [{now}]\n"
        discord_msg += "```\n"
        discord_msg += scan_output
        discord_msg += "```\n"
        discord_msg += analysis_text

        print("📨 디스코드 전송 중...")
        send_to_discord(discord_msg)

    except Exception as e:
        print(f"\n{RED}❌ 오류 발생: {e}{RESET}")
# 메인 실행
if __name__ == "__main__":
    # 시장 스캔 실행
    scan_output, market_data = scan_market()

    # 스캔 결과 출력
    print(scan_output)

    # Gemini로 분석
    analyze_with_gemini(scan_output, market_data)