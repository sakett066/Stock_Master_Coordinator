"""
MASTER COORDINATOR v7.0 - 11-Layer Analysis
Differentiated scoring with Price Action, Trend, Breakout layers
"""
import os
import time
import requests
import warnings
import numpy as np
from datetime import datetime

warnings.filterwarnings('ignore')
os.environ['TZ'] = 'Asia/Kolkata'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_MASTER_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_MASTER_CHAT_ID')

STOCKS = {
    'IT': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM'],
    'Banking': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'SBIN', 'AXISBANK'],
    'Pharma': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB'],
    'Consumer': ['ITC', 'HINDUNILVR', 'TITAN', 'DMART', 'TRENT'],
    'Auto': ['MARUTI', 'M&M'],
    'Finance': ['BAJFINANCE', 'BAJAJFINSV', 'CHOLAFIN'],
    'Energy': ['RELIANCE', 'POWERGRID', 'NTPC', 'ONGC', 'TATAPOWER'],
    'Others': ['LT', 'HAL', 'BEL', 'IRCTC', 'ASIANPAINT']
}

def fetch_stock_data(symbol):
    """Fetch stock data with validation"""
    data = None
    
    try:
        from nsetools import Nse
        nse = Nse()
        q = nse.get_quote(symbol)
        if q and q.get('lastPrice'):
            price = float(q.get('lastPrice', 0))
            if price > 0:
                intraday = q.get('intraDayHighLow', {})
                weekly = q.get('weekHighLow', {})
                data = {
                    'price': price,
                    'open': float(q.get('open', 0)),
                    'high': float(intraday.get('max', 0)),
                    'low': float(intraday.get('min', 0)),
                    'prev_close': float(q.get('previousClose', 0)),
                    'change_pct': float(q.get('pChange', 0)),
                    'vwap': float(q.get('vwap', 0)) if q.get('vwap') and q.get('vwap') != 'N/A' else price,
                    'volume': int(q.get('totalTradedVolume', 0)),
                    'buy_qty': int(q.get('totalBuyQuantity', 0)),
                    'sell_qty': int(q.get('totalSellQuantity', 0)),
                    'delivery_qty': int(q.get('deliveryQuantity', 0)),
                    'high_52': float(weekly.get('max', 0)),
                    'low_52': float(weekly.get('min', 0))
                }
    except:
        pass
    
    if not data or data['price'] <= 0 or data['high_52'] <= 0:
        try:
            import yfinance as yf
            ticker = yf.Ticker(f"{symbol}.NS")
            info = ticker.info
            hist = ticker.history(period="5d")
            
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
                prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else price
                
                data = {
                    'price': price,
                    'open': float(hist['Open'].iloc[-1]),
                    'high': float(hist['High'].iloc[-1]),
                    'low': float(hist['Low'].iloc[-1]),
                    'prev_close': prev,
                    'change_pct': float(((price - prev) / prev) * 100),
                    'vwap': price,
                    'volume': int(hist['Volume'].iloc[-1]) if not np.isnan(hist['Volume'].iloc[-1]) else 100000,
                    'buy_qty': 0, 'sell_qty': 0, 'delivery_qty': 0,
                    'high_52': float(info.get('fiftyTwoWeekHigh', price * 1.2)),
                    'low_52': float(info.get('fiftyTwoWeekLow', price * 0.8))
                }
        except:
            pass
    
    if data:
        if np.isnan(data.get('high_52', 0)) or data.get('high_52', 0) <= 0:
            data['high_52'] = data['price'] * 1.2
        if np.isnan(data.get('low_52', 0)) or data.get('low_52', 0) <= 0:
            data['low_52'] = data['price'] * 0.8
        if np.isnan(data.get('vwap', 0)) or data.get('vwap', 0) <= 0:
            data['vwap'] = data['price']
        if np.isnan(data.get('volume', 0)) or data.get('volume', 0) <= 0:
            data['volume'] = 100000
        return data
    
    return None

# ============================================
# 11 ANALYSIS LAYERS
# ============================================

def analyze_value(price, high_52, low_52):
    if high_52 <= 0 or low_52 <= 0:
        return {'score': 5, 'label': 'Value', 'detail': 'Limited data'}
    discount = ((high_52 - price) / high_52) * 100
    position = ((price - low_52) / (high_52 - low_52)) * 100 if (high_52 - low_52) > 0 else 50
    if position < 25 and discount > 25:
        return {'score': 10, 'label': 'Value', 'detail': f'DEEP VALUE: {discount:.0f}% off highs'}
    elif position < 40:
        return {'score': 8, 'label': 'Value', 'detail': f'Undervalued: {discount:.0f}% discount'}
    elif position < 60:
        return {'score': 6, 'label': 'Value', 'detail': 'Fair value'}
    elif position < 80:
        return {'score': 3, 'label': 'Value', 'detail': 'Approaching highs'}
    else:
        return {'score': 1, 'label': 'Value', 'detail': 'At premium'}

def analyze_momentum(price, open_p, prev_close, vwap, change_pct):
    score = 5; signals = []
    if change_pct > 1: score += 3; signals.append(f"+{change_pct:.1f}%")
    elif change_pct > 0.3: score += 2; signals.append("Rising")
    elif change_pct > 0: score += 1; signals.append("Mild +")
    elif change_pct > -1: score += 1; signals.append("Dip opportunity")
    if vwap > 0 and price > vwap: score += 1; signals.append(">VWAP")
    if price > open_p: score += 1; signals.append(">Open")
    return {'score': min(10, score), 'label': 'Momentum', 'detail': ', '.join(signals) if signals else 'Neutral'}

def analyze_smart_money(buy_qty, sell_qty, delivery_qty, volume):
    if volume > 0 and delivery_qty > 0:
        dp = (delivery_qty / volume) * 100
        if dp > 60: return {'score': 10, 'label': 'Smart Money', 'detail': f'Strong delivery {dp:.0f}%'}
        elif dp > 45: return {'score': 8, 'label': 'Smart Money', 'detail': f'Good delivery {dp:.0f}%'}
        elif dp > 30: return {'score': 6, 'label': 'Smart Money', 'detail': f'Avg delivery {dp:.0f}%'}
    if buy_qty > 0 and sell_qty > 0:
        ratio = buy_qty / sell_qty
        if ratio > 1.5: return {'score': 9, 'label': 'Smart Money', 'detail': f'Buy pressure {ratio:.1f}x'}
        elif ratio > 1.2: return {'score': 7, 'label': 'Smart Money', 'detail': 'Mild buying'}
    return {'score': 5, 'label': 'Smart Money', 'detail': 'Neutral flow'}

def analyze_wave(price, high_52, low_52, change_pct):
    if high_52 <= 0 or low_52 <= 0: return {'score': 5, 'label': 'Wave', 'detail': 'No data'}
    fib_range = high_52 - low_52
    if fib_range <= 0: return {'score': 5, 'label': 'Wave', 'detail': 'No range'}
    position = ((price - low_52) / fib_range) * 100
    if position < 20 and change_pct > -2: return {'score': 10, 'label': 'Wave', 'detail': 'Wave 1/2: BEST ENTRY'}
    elif position < 38.2: return {'score': 8, 'label': 'Wave', 'detail': 'Wave 2: Pullback buy'}
    elif position < 61.8 and change_pct > 0: return {'score': 7, 'label': 'Wave', 'detail': 'Wave 3: Momentum'}
    elif position < 78.6: return {'score': 5, 'label': 'Wave', 'detail': 'Wave 4: Consolidation'}
    else: return {'score': 2, 'label': 'Wave', 'detail': 'Wave 5: Near top'}

def analyze_volume(volume):
    if volume > 5000000: return {'score': 10, 'label': 'Volume', 'detail': 'Very High activity'}
    elif volume > 2000000: return {'score': 8, 'label': 'Volume', 'detail': 'High volume'}
    elif volume > 500000: return {'score': 6, 'label': 'Volume', 'detail': 'Moderate'}
    elif volume > 100000: return {'score': 4, 'label': 'Volume', 'detail': 'Low volume'}
    else: return {'score': 2, 'label': 'Volume', 'detail': 'Very thin'}

def analyze_mean_reversion(price, high_52, low_52):
    if high_52 <= 0 or low_52 <= 0: return {'score': 5, 'label': 'Mean Rev', 'detail': 'No data'}
    mid = (high_52 + low_52) / 2
    deviation = ((price - mid) / mid) * 100
    if deviation < -25: return {'score': 10, 'label': 'Mean Rev', 'detail': 'Extremely Oversold'}
    elif deviation < -15: return {'score': 8, 'label': 'Mean Rev', 'detail': 'Oversold - Bounce likely'}
    elif deviation < -5: return {'score': 6, 'label': 'Mean Rev', 'detail': 'Below mean'}
    elif deviation < 5: return {'score': 5, 'label': 'Mean Rev', 'detail': 'At mean'}
    elif deviation < 15: return {'score': 3, 'label': 'Mean Rev', 'detail': 'Above mean'}
    else: return {'score': 1, 'label': 'Mean Rev', 'detail': 'Overbought'}

def analyze_sector(sector):
    scores = {'IT': 8, 'Banking': 7, 'Pharma': 8, 'Consumer': 7, 'Auto': 6, 'Finance': 7, 'Energy': 6, 'Others': 5}
    return {'score': scores.get(sector, 5), 'label': 'Sector', 'detail': sector}

def analyze_risk(price, high_52, low_52, change_pct):
    score = 10
    if high_52 > 0 and low_52 > 0:
        vol = ((high_52 - low_52) / low_52) * 100
        if vol > 80: score -= 4
        elif vol > 50: score -= 2
    if abs(change_pct) > 5: score -= 3
    elif abs(change_pct) > 3: score -= 1
    if score >= 8: return {'score': score, 'label': 'Risk', 'detail': 'Low Risk'}
    elif score >= 5: return {'score': score, 'label': 'Risk', 'detail': 'Moderate Risk'}
    else: return {'score': max(1, score), 'label': 'Risk', 'detail': 'High Risk'}

def analyze_price_action(price, open_p, high, low, prev_close):
    score = 5
    if price > open_p: score += 2
    if high > low and ((price - low) / (high - low)) > 0.6: score += 2
    if price > prev_close: score += 1
    if score >= 8: return {'score': score, 'label': 'Price Action', 'detail': 'Bullish, strong close'}
    elif score >= 6: return {'score': score, 'label': 'Price Action', 'detail': 'Moderately bullish'}
    else: return {'score': score, 'label': 'Price Action', 'detail': 'Weak'}

def analyze_trend_strength(price, high_52, low_52, change_pct):
    if high_52 <= 0 or low_52 <= 0: return {'score': 5, 'label': 'Trend', 'detail': 'No data'}
    position = ((price - low_52) / (high_52 - low_52)) * 100
    if position > 60 and change_pct > 0.5: return {'score': 9, 'label': 'Trend', 'detail': 'Strong uptrend'}
    elif position < 40 and change_pct > 0: return {'score': 8, 'label': 'Trend', 'detail': 'New uptrend emerging'}
    elif position < 30 and change_pct < 0: return {'score': 3, 'label': 'Trend', 'detail': 'Downtrend - wait'}
    elif 40 <= position <= 60: return {'score': 5, 'label': 'Trend', 'detail': 'Sideways'}
    else: return {'score': 5, 'label': 'Trend', 'detail': 'Mixed'}

def analyze_volatility_breakout(price, high_52, low_52, volume):
    if high_52 <= 0 or low_52 <= 0: return {'score': 5, 'label': 'Breakout', 'detail': 'No data'}
    range_52 = high_52 - low_52
    volatility = (range_52 / low_52) * 100
    if volatility > 50 and volume > 2000000: return {'score': 9, 'label': 'Breakout', 'detail': 'High volatility breakout likely'}
    elif volatility > 30 and volume > 1000000: return {'score': 7, 'label': 'Breakout', 'detail': 'Breakout potential'}
    elif volatility < 20: return {'score': 4, 'label': 'Breakout', 'detail': 'Low volatility'}
    else: return {'score': 5, 'label': 'Breakout', 'detail': 'Normal'}

# ============================================
# MASTER ANALYSIS
# ============================================
def analyze_stock(symbol, sector):
    data = fetch_stock_data(symbol)
    if not data or data['price'] <= 0:
        return None
    
    layers = {
        'Value': analyze_value(data['price'], data['high_52'], data['low_52']),
        'Momentum': analyze_momentum(data['price'], data['open'], data['prev_close'], data['vwap'], data['change_pct']),
        'Smart Money': analyze_smart_money(data['buy_qty'], data['sell_qty'], data['delivery_qty'], data['volume']),
        'Wave': analyze_wave(data['price'], data['high_52'], data['low_52'], data['change_pct']),
        'Volume': analyze_volume(data['volume']),
        'Mean Rev': analyze_mean_reversion(data['price'], data['high_52'], data['low_52']),
        'Sector': analyze_sector(sector),
        'Risk': analyze_risk(data['price'], data['high_52'], data['low_52'], data['change_pct']),
        'Price Action': analyze_price_action(data['price'], data['open'], data['high'], data['low'], data['prev_close']),
        'Trend': analyze_trend_strength(data['price'], data['high_52'], data['low_52'], data['change_pct']),
        'Breakout': analyze_volatility_breakout(data['price'], data['high_52'], data['low_52'], data['volume'])
    }
    
    total = sum(l['score'] for l in layers.values())
    total = min(95, max(20, total))
    
    active = [name for name, l in layers.items() if l['score'] >= 6]
    
    if len(active) >= 9:
        signal, stars, conf, pos = "SUPER SIGNAL", "⭐⭐⭐⭐⭐", "VERY HIGH", "20%"
    elif len(active) >= 7:
        signal, stars, conf, pos = "STRONG BUY", "⭐⭐⭐⭐", "HIGH", "15%"
    elif len(active) >= 5:
        signal, stars, conf, pos = "BUY", "⭐⭐⭐", "MODERATE", "10%"
    elif len(active) >= 3:
        signal, stars, conf, pos = "WATCH", "⭐⭐", "LOW", "5%"
    else:
        signal, stars, conf, pos = "SKIP", "⭐", "NONE", "0%"
    
    return {
        'symbol': symbol, 'sector': sector, 'price': data['price'],
        'change': data['change_pct'], 'score': total, 'stars': stars,
        'signal': signal, 'confidence': conf, 'position': pos,
        'layers': layers, 'active': len(active), 'active_names': active
    }

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900: text = text[:3900]
        resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        return resp.json().get('ok', False)
    except: return False

def run():
    results = []
    now = datetime.now()
    print(f"MASTER COORDINATOR v7.0 - {now.strftime('%d-%b %I:%M %p')}")
    
    all_stocks = [(sym, sec) for sec, syms in STOCKS.items() for sym in syms]
    
    for symbol, sector in all_stocks:
        result = analyze_stock(symbol, sector)
        if result:
            results.append(result)
            print(f"  {symbol:15} Rs.{result['price']:>8.0f} | Score:{result['score']:>3} | {result['active']}/11 | {result['signal']}")
        else:
            print(f"  {symbol:15} ❌ No data")
        time.sleep(0.15)
    
    if not results:
        send_telegram("No data available.")
        return
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    super_sig = [r for r in results if r['active'] >= 9]
    strong = [r for r in results if 7 <= r['active'] < 9]
    buy = [r for r in results if 5 <= r['active'] < 7]
    
    msg = f"<b>MASTER COORDINATOR v7.0</b>\n"
    msg += f"{now.strftime('%d-%b %I:%M %p')} IST\n"
    msg += f"{'═'*35}\n\n"
    
    msg += f"<b>11-Layer Analysis:</b>\nValue | Momentum | Smart Money | Wave | Volume | Mean Rev | Sector | Risk | Price Action | Trend | Breakout\n\n"
    
    msg += f"<b>RESULTS:</b>\n"
    msg += f"Super Signals (9-11 layers): {len(super_sig)}\n"
    msg += f"Strong Buy (7-8 layers): {len(strong)}\n"
    msg += f"Buy (5-6 layers): {len(buy)}\n"
    msg += f"Total: {len(results)} stocks\n\n"
    
    top = super_sig[:3] if super_sig else (strong[:3] if strong else results[:5])
    
    msg += f"<b>TOP PICKS</b>\n{'═'*35}\n\n"
    
    for i, r in enumerate(top, 1):
        emoji = "🔥" if r['active'] >= 9 else "🟢" if r['active'] >= 7 else "🔵"
        
        msg += f"{emoji} <b>#{i} {r['symbol']}</b> | {r['sector']} | Rs.{r['price']:.0f}\n"
        msg += f"{'─'*35}\n"
        msg += f"Score: <b>{r['score']}/100</b> {r['stars']}\n"
        msg += f"Signal: <b>{r['signal']}</b> | {r['confidence']}\n"
        msg += f"Position: {r['position']} | Layers: {r['active']}/11\n\n"
        
        msg += f"<b>Layer Details:</b>\n"
        for name, layer in r['layers'].items():
            bar = "█" * layer['score'] + "░" * (10 - layer['score'])
            emoji_l = "✅" if layer['score'] >= 6 else "⬜"
            msg += f"  {emoji_l} {bar} {name}: {layer['detail']}\n"
        msg += f"\n"
    
    msg += f"{'═'*35}\n"
    msg += f"<i>11-Layer Institutional Grade Analysis</i>\n"
    msg += f"<i>9+/11 layers = Highest conviction trades</i>"
    
    send_telegram(msg)
    print(f"\n✅ Sent! Super:{len(super_sig)} Strong:{len(strong)} Buy:{len(buy)}")

if __name__ == "__main__":
    run()
