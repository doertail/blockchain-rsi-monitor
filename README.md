# RSI Market Scanner

RSI(Relative Strength Index) 지표를 활용하여 주식 및 ETF의 매수/매도 신호를 실시간으로 분석하는 마켓 스캐너입니다.

## 주요 기능

- **실시간 RSI 계산**: 14일 기준 RSI 지표를 자동으로 계산
- **종목별 맞춤형 매수 기준**: 각 종목의 특성에 맞춘 동적 임계값 적용
- **색상 코드 시각화**: 터미널에서 색상으로 신호를 직관적으로 표시
- **자동 매매 신호 생성**: STRONG BUY, WATCH, HOLD, STRONG SELL 등의 액션 신호 제공

## 모니터링 종목

| Ticker | 종목명 | RSI 매수 기준 | 특징 |
|--------|--------|---------------|------|
| QQQM | Invesco NASDAQ 100 ETF | 40 | 지수형 ETF (기준 완화) |
| BLOK | Amplify Transformational Data Sharing ETF | 35 | 블록체인 섹터 ETF |
| GLXY | Galaxy Digital Holdings | 30 | 변동성 높은 개별주 |
| CRCL | Circle Internet Financial | 30 | 암호화폐 관련 개별주 |
| COIN | Coinbase Global | 30 | 암호화폐 거래소 |

## 설치 방법

### 필수 요구사항
- Python 3.7 이상
- pip 패키지 관리자

### 패키지 설치

```bash
pip install yfinance pandas
```

## 사용 방법

```bash
python market_scanner.py
```

## 출력 예시

```
Ticker     | Price      | RSI(14)    | Action Signal
-----------------------------------------------------------------
BLOK       | 45.32      | 28.45      | STRONG BUY (RSI < 35)
QQQM       | 178.90     | 42.10      | WATCH (Approaching Buy)
GLXY       | 12.50      | 55.20      | WAIT (Neutral)
CRCL       | 23.75      | 68.30      | HOLD (Bullish)
COIN       | 215.40     | 72.50      | STRONG SELL (Overbought)
-----------------------------------------------------------------
■ Strategy based on Dynamic Thresholds (QQQM:40, BLOK:35, Others:30)
Execution Time: 2025-12-18 15:30:45
```

## 신호 해석

### 매수 신호
- **STRONG BUY** (녹색): RSI가 종목별 매수 기준 이하 → 과매도 구간, 강력한 매수 신호
- **WATCH** (노란색): RSI가 매수 기준 + 10 이내 → 매수 타이밍 접근 중, 관망 필요

### 관망 신호
- **WAIT** (기본): RSI 40~60 구간 → 중립, 추가 확인 필요
- **HOLD** (파란색): RSI 60~70 구간 → 상승 추세, 보유 권장

### 매도 신호
- **STRONG SELL** (빨간색): RSI 70 이상 → 과매수 구간, 매도 고려

## RSI 지표란?

RSI(Relative Strength Index)는 모멘텀 지표로, 주가의 상승압력과 하락압력 간의 상대적인 강도를 나타냅니다.

- **계산 방식**: 14일 기준 EMA(지수이동평균) 사용
- **범위**: 0 ~ 100
- **해석**:
  - 30 이하: 과매도 (Oversold) - 저평가 가능성
  - 70 이상: 과매수 (Overbought) - 고평가 가능성

## 전략 설명

### 동적 임계값 (Dynamic Thresholds)

모든 종목에 동일한 기준을 적용하지 않고, 각 종목의 특성에 맞춘 맞춤형 전략을 사용합니다.

- **지수형 ETF (QQQM)**: 안정성이 높아 RSI 40 이하에서 매수
- **섹터 ETF (BLOK)**: 중간 변동성, RSI 35 이하 매수
- **개별주 (GLXY, CRCL, COIN)**: 높은 변동성, 더 엄격한 기준 (RSI 30 이하)

이 접근 방식은 각 자산의 변동성 특성을 반영하여 더 정교한 매매 타이밍을 제공합니다.

## 커스터마이징

### 종목 추가/변경

[market_scanner.py:16](market_scanner.py#L16)에서 `tickers` 리스트 수정:

```python
tickers = ['BLOK', 'QQQM', 'GLXY', 'CRCL', 'COIN', 'YOUR_TICKER']
```

### RSI 기준 조정

[market_scanner.py:19-25](market_scanner.py#L19-L25)에서 `buy_thresholds` 딕셔너리 수정:

```python
buy_thresholds = {
    'QQQM': 40,
    'BLOK': 35,
    'GLXY': 30,
    'YOUR_TICKER': 35  # 원하는 기준값 설정
}
```

### 데이터 기간 변경

[market_scanner.py:47](market_scanner.py#L47)에서 `period` 파라미터 수정:

```python
df = yf.download(ticker, period="6mo", interval="1d", progress=False)
```

## 주의사항

⚠️ **투자 유의사항**
- 이 도구는 투자 참고용이며, 실제 투자 결정에 대한 책임은 사용자에게 있습니다
- RSI는 여러 기술적 지표 중 하나이며, 다른 지표와 함께 종합적으로 판단해야 합니다
- 과거 데이터 기반 지표이므로 미래 수익을 보장하지 않습니다
- 변동성이 큰 암호화폐 관련 종목은 특히 주의가 필요합니다

## 기술 스택

- **Python 3.x**
- **yfinance**: Yahoo Finance API를 통한 실시간 시장 데이터 수집
- **pandas**: 데이터 처리 및 RSI 계산
- **ANSI 색상 코드**: 터미널 출력 시각화

## 라이선스

개인 사용 및 학습 목적으로 자유롭게 사용 가능합니다.

## 문의 및 기여

- 버그 리포트나 기능 제안은 이슈로 등록해주세요
- Pull Request는 언제나 환영합니다

---

**Last Updated**: 2025-12-18
