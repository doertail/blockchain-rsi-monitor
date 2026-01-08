import yfinance as yf
import warnings
import datetime
import requests
import os
import sys
from io import StringIO
from dotenv import load_dotenv
from google import genai

# 환경 변수 로드
load_dotenv()

# 경고 차단
warnings.simplefilter(action='ignore', category=FutureWarning)

# ANSI 색상
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

tickers = ['BLOK', 'QQQM', 'GLXY', 'CRCL', 'COIN', 'ETH-USD', 'BTC-USD']

# 매수 기준 (RSI)
buy_thresholds = {
    'QQQM': 40, 'BLOK': 35, 'GLXY': 30, 'CRCL': 30, 'COIN': 30, 'ETH-USD': 30, 'BTC-USD': 30
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
    """시장 스캔을 수행하고 결과를 반환"""
    # 출력 캡처 시작
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    print(f"\nExecution Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)
    print(f"{'Ticker':<10} | {'Price':<10} | {'RSI':<15} | {'Support(3M)':<20} | {'Signal'}")
    print("-" * 80)

    # 데이터 저장용 (Gemini에 보낼 구조화된 데이터)
    market_data = []

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

            # RSI 색상과 숫자 포맷팅 분리
            rsi_color = get_rsi_color(ticker, current_rsi)
            rsi_display = f"{rsi_color}{current_rsi:<15.2f}{RESET}"

            print(f"{ticker:<10} | {current_price:<10.2f} | {rsi_display} | {support_msg:<20} | {signal}")

            # 구조화된 데이터 저장
            market_data.append({
                'ticker': ticker,
                'price': current_price,
                'rsi': current_rsi,
                'lowest_3m': lowest_price,
                'distance_from_low': ((current_price - lowest_price) / lowest_price) * 100,
                'signal': signal.replace(GREEN, '').replace(YELLOW, '').replace(RED, '').replace(BLUE, '').replace(RESET, '').strip()
            })

        except Exception as e:
            print(f"{ticker:<10} | Error: {e}")

    print("-" * 80)

    # 출력 캡처 종료
    sys.stdout = old_stdout
    output = captured_output.getvalue()

    return output, market_data

def analyze_with_gemini(scan_output, market_data):
    """Gemini API를 사용하여 시장 분석 (Failover: 2.0 -> 1.5)"""
    api_key = os.getenv('GEMINI_API_KEY')

    if not api_key:
        print("\n⚠️  GEMINI_API_KEY가 .env 파일에 설정되지 않았습니다.")
        print("📝 .env 파일에 다음과 같이 추가하세요:")
        print("   GEMINI_API_KEY=your_api_key_here")
        return

    try:
        # Gemini API 클라이언트 생성
        client = genai.Client(api_key=api_key)

        # 전략 컨텍스트 정의
        strategy_context = """
        [사용자 페르소나]
        - CS 전공 창업가, 효율과 논리 중시.
        - 감정에 휘둘리는 투자를 경멸함. '감'이 아닌 '데이터'로만 움직임.
        - 목표: 시장의 소음(Noise)을 차단하고, 확실한 신호(Signal)에만 격발.

        [투자 전략: The Sniper]
        1. 포트폴리오 구조:
           - 기초 체력(Defense): QQQM (매일 20$ 자동 적립 + 폭락 시 목돈 투입)
           - 팬심(Satellite): TSLA (매일 10$ 자동 적립)
           - 스나이핑(Offense): BLOK, GLXY, CRCL, COIN (현금 대기 -> RSI 30 이하 과매도 구간에서만 사냥)
           - 관망(Crypto Base): BTC, ETH (보유 X)
        2. 행동 강령:
           - 어중간한 구간(RSI 40~60)에서는 절대 매수 버튼을 누르지 않는다.
           - "현금도 종목이다" (Cash is a Position). 지루함을 견디는 것이 핵심 능력.
           - 상승장에 포모(FOMO)를 느끼지 말고, 하락장에 공포를 느끼지 마라.
        """

        # 분석 요청 프롬프트
        prompt = f"""
        당신은 이 시스템의 '메인 알고리즘(System Core)'이자, 사용자의 '냉철한 투자 참모'입니다.
        단순한 데이터 나열이 아니라, 사용자의 멘탈을 관리하고 행동을 통제하는 것이 목적입니다.

        [입력 데이터]
        {market_data}

        [분석 요구사항]
        1. **말투 및 톤앤매너**:
           - 증권사 리포트 같은 딱딱한 문체(~함, ~임) 지양.
           - 사용자와 대화하듯 **냉소적이고 직설적인 구어체와 명령조**를 섞어서 사용 (~해라, ~다, ~하지 마라).
           - 사용자가 감정적(지루함, 조급함)으로 흔들릴 틈을 주지 않는 단호한 태도 유지.
           - **CS 전공자/창업가 페르소나 반영**: '디버깅', '컴파일', '최적화', '노이즈', '레이턴시' 같은 용어를 적절히 비유에 활용.

        2. **형식**: 아래 섹션 구조를 따르되, 내용은 '살아있는 조언'으로 채울 것.

        ---
        **[System Log: Market Status Analysis]**
        (현재 시장 상태를 한 문장으로 요약. 예: "재미없는 횡보장. 도파민은 없다.", "폭락장은 바겐세일이다.")

        ### **1. 데이터 해독 (Decoding)**
        - **Defense (QQQM)**: 건전한지, 시스템이 잘 돌고 있는지 체크.
        - **Offense (Sniper Targets)**: RSI 수치를 근거로 "아직 멀었다" 혹은 "방아쇠에 손 올려라"라고 명확히 지시.
        - **Crypto Base**: 감정적인 추격 매수 욕구를 차단.

        ### **2. 오늘 밤 작전 명령 (Execution Order)**
        - 표 대신, **핵심 종목별로 짧고 굵은 지침**을 하달.
        - **QQQM**: 자동 매수 외 건드리지 마라.
        - **Sniper Target**: RSI 30 안 왔으면 "기다리는 게 능력이다"라고 일침.
        - **현금**: "쇼핑하지 말고 총알 아껴라"라고 경고.

        ### **3. 결론 (Final Verdict)**
        - 지금 당장 사용자가 취해야 할 행동을 한 문장으로 요약. (예: "앱 강제 종료하고 나이테듀 기획서나 써라.")
        - **System Standby** 또는 **System Offline**으로 마무리.
        ---

        [전략 컨텍스트]
        {strategy_context}
        """

        print("\n" + "="*80)
        print("🤖 Gemini AI 기술적 분석 중...")
        print("="*80 + "\n")

        # Failover Logic: 2.0 실패 시 자동으로 1.5로 전환
        analysis_text = None

        try:
            # 1순위: Gemini 2.0 (성능 좋음)
            response = client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=prompt
            )
            analysis_text = response.text
            print(f"{GREEN}✓ Gemini 2.0 모델 사용{RESET}\n")

        except Exception as e:
            print(f"{YELLOW}⚠️ Gemini 2.0 모델 오류: {e}{RESET}")
            print(f"{YELLOW}→ Gemini 1.5 모델로 전환 중...{RESET}\n")

            try:
                # 2순위: Gemini 1.5 (안정적)
                response = client.models.generate_content(
                    model='gemini-flash-latest',
                    contents=prompt
                )
                analysis_text = response.text
                print(f"{GREEN}✓ Gemini 1.5 모델 사용{RESET}\n")

            except Exception as e2:
                print(f"{RED}❌ 모든 Gemini 모델 실패: {e2}{RESET}")
                return

        # 분석 결과가 없으면 종료
        if not analysis_text:
            print(f"{RED}❌ AI 분석 결과를 받지 못했습니다.{RESET}")
            return

        # 터미널에 출력
        print(analysis_text)
        print("\n" + "="*80)

        # 디스코드로 전송
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        discord_msg = f"## 📡 Market Sniper Report [{now}]\n"
        discord_msg += "```\n"
        discord_msg += scan_output
        discord_msg += "```\n"
        discord_msg += analysis_text

        print("📨 디스코드 전송 중...")
        send_to_discord(discord_msg)

    except Exception as e:
        print(f"\n{RED}❌ 예상치 못한 오류 발생: {e}{RESET}")

# 메인 실행
if __name__ == "__main__":
    # 시장 스캔 실행
    scan_output, market_data = scan_market()

    # 스캔 결과 출력
    print(scan_output)

    # Gemini로 분석
    analyze_with_gemini(scan_output, market_data)