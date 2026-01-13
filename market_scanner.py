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

        # 전략 컨텍스트 정의 (업데이트됨: Buffer Logic 추가)
        strategy_context = f"""
        [사용자 페르소나]
        - CS 전공 창업가. '감'을 혐오하고 '데이터'와 '논리'만 믿음.
        - 효율 극대화: 잦은 매매(Noise Trading)를 혐오함. 확실한 구간(High Conviction)에서만 격발.

        [투자 전략: The Sniper v2.1 (Hysteresis Filter)]
        1. 핵심 로직 (Logic Gate with Buffer):
           - Strong Bull (Gap > +3%): 상승 추세 확정. RSI 과매도(30)는 강력한 매수 기회.
           - Neutral / Gray Zone (-3% <= Gap <= +3%): 추세 보류 구간. 섣불리 팔거나 사지 않음. '관망(Hold)'이 원칙.
           - Bearish (Gap < -3%): 하락 추세 진입. 보수적 대응.
           - Deep Bearish (Gap < -10%): 폭락 추세. 절대 매수 금지.

        2. 포트폴리오 상태 (자산 현황):
           - CRCL: {portfolio_crcl}
           - TSLA: {portfolio_tsla} + 매일 {auto_invest_tsla}$ 적립
           - BLOK: {portfolio_blok}
           - QQQM: {portfolio_qqqm} + 매일 {auto_invest_qqqm}$ 적립
           - COIN: {portfolio_coin}$ 보유
           - TLT: {portfolio_tlt}
           - 현금: {portfolio_cash}달러
        """

        # 분석 요청 프롬프트
        prompt = f"""
        당신은 사용자의 자산을 방어하는 '냉철한 리스크 관리 알고리즘'입니다.
        단순한 수치 비교가 아닌, **'추세의 강도'와 '버퍼(Buffer)'를 고려하여 판결을 내리십시오.**

        [입력 데이터]
        {market_data}
        (참고: 'trend_gap'은 현재가가 120일 이평선 대비 위치(%)임.)

        [분석 지침 및 출력 형식]

        **1. Tone & Manner:**
        - 감정을 배제하고, 개발자스러운 용어(Latency, Buffer, Exception, Overflow)를 사용하여 명료하게 보고할 것.
        - 0.xx% 단위의 미세한 등락에 일희일비하지 말 것.

        **2. Report Structure:**

        **[System Status: Market Trend Check]**
        - 시장을 'Bullish(상승)', 'Neutral(보합/테스트)', 'Bearish(하락)' 세 가지로 분류하여 진단.
        - 특히 QQQM(시장 지수)과 개별 섹터 간의 괴리(Decoupling)를 지적할 것.

        **[Portfolio P&L Analysis]**
        - 각 보유 종목의 '평균단가'와 '현재가'를 비교하여 실시간 손익을 진단할 것.
        - **손실 중인 종목(-)**: 추세가 하락세(Bearish)라면 "물타기(Averaging Down) 절대 금지" 경고.
        - **수익 중인 종목(+)**: 추세가 꺾이지 않았다면(Gray Zone 포함) "수익 달리기(Let Profits Run)" 지시.

        **[Debugging & Action Plan] (Logic Gate 적용)**
        각 종목별로 아래 **수정된 로직**을 엄격히 적용하여 행동 지시:

        * **Case 1: Strong Bull (Gap > +3%) + RSI Low(≤30)**
          → "시스템 정상. 적극 매수(Aggressive Buy) 승인."
        * **Case 2: Gray Zone (-3% ≤ Gap ≤ +3%)**
          → **"Hold (관망)."** 이 구간은 추세가 붕괴된 것이 아니라 지지선을 테스트하는 구간임. 
          → 보유자는 함부로 팔지 말고, 미보유자는 함부로 사지 말 것. (BLOK이 여기에 해당하면 절대 매도 신호 주지 말 것)
        * **Case 3: Confirmed Bearish (Gap < -3%)**
          → "경고(Warning). 추세 붕괴됨. 리스크 관리 모드 진입."
          → 수익 중이면 익절 고민, 손실 중이면 추가 매수 금지.
        * **Case 4: Deep Bearish (Gap < -10%)**
          → "시스템 위험(Critical). 지하실 진입. 매수 버튼 비활성화."

        **[Final Compile]**
        - 오늘 밤 사용자가 실행해야 할 단 하나의 행동 지침(Action Item)을 한 문장으로 요약.
        - 예: "BLOK은 지지선 테스트 중이니 홀딩하고, CRCL 같은 하락 추세 종목은 쳐다보지 마라."

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