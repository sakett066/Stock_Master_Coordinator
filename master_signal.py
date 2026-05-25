"""
MASTER COORDINATOR v5.0 - 8-Layer Institutional Grade Analysis
Combines: Value, Momentum, Smart Money, Wave Pattern, Volume Profile, 
          Mean Reversion, Sector Rotation, Risk Arbitrage
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

def robust_nse_fetch(symbol):
    for _ in range(2):
        try:
            from nsetools import Nse
            nse = Nse()
            q = nse.get_quote(symbol)
            if q and q.get('lastPrice') and float(q.get('lastPrice', 0)) > 0:
                intraday = q.get('intraDayHighLow', {})
                weekly = q.get('weekHighLow', {})
                return {
                    'symbol': symbol,
                    'lastPrice': float(q.get('lastPrice', 0)),
                    'open': float(q.get('open', 0)),
                    'dayHigh': float(intraday.get('max', 0)),
                    'dayLow': float(intraday.get('min', 0)),
                    'previousClose': float(q.get('previousClose', 0)),
                    'pChange': float(q.get('pChange', 0)),
                    'vwap': float(q.get('vwap', 0)) if q.get('vwap') else 0,
                    'totalTradedVolume': int(q.get('totalTradedVolume', 0)),
                    'totalBuyQuantity': int(q.get('totalBuyQuantity', 0)),
                    'totalSellQuantity': int(q.get('totalSellQuantity', 0)),
                    'deliveryQuantity': int(q.get('deliveryQuantity', 0)),
                    'weekHighLow': {'max': float(weekly.get('max', 0)), 'min': float(weekly.get('min', 0))}
                }
        except: pass
        time.sleep(1)
    
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info
        hist = ticker.history(period="5d")
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
            prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else price
            return {
                'symbol': symbol,
                'lastPrice': price,
                'open': float(hist['Open'].iloc[-1]),
                'dayHigh': float(hist['High'].iloc[-1]),
                'dayLow': float(hist['Low'].iloc[-1]),
                'previousClose': prev,
                'pChange': float(((price-prev)/prev)*100),
                'vwap': price,
                'totalTradedVolume': int(hist['Volume'].iloc[-1]),
                'totalBuyQuantity': 0, 'totalSellQuantity': 0, 'deliveryQuantity': 0,
                'weekHighLow': {'max': float(info.get('fiftyTwoWeekHigh', price*1.1)), 'min': float(info.get('fiftyTwoWeekLow', price*0.9))}
            }
    except: pass
    return None

# ============================================
# 8 ANALYSIS LAYERS
# ============================================

def layer_1_value(data):
    """Value detection - Is the stock at good price?"""
    price = data['lastPrice']
    h52 = data['weekHighLow']['max']
    l52 = data['weekHighLow']['min']
    
    if h52 == 0 or l52 == 0: return {'score': 0, 'signal': 'No data'}
    
    position = ((price - l52) / (h52 - l52)) * 100
    discount = ((h52 - price) / h52) * 100
    
    if position < 25:
        return {'score': 20, 'signal': '🔥 DEEP VALUE', 'detail': f'{discount:.0f}% below 52W high'}
    elif position < 45:
        return {'score': 15, 'signal': '💰 Good Value', 'detail': f'{discount:.0f}% below 52W high'}
    elif position < 65:
        return {'score': 10, 'signal': '📊 Fair Value', 'detail': f'{discount:.0f}% below 52W high'}
    elif position < 85:
        return {'score': 5, 'signal': '⚠️ Premium', 'detail': f'Near 52W high'}
    else:
        return {'score': 0, 'signal': '🔴 Expensive', 'detail': 'At 52W high'}

def layer_2_momentum(data):
    """Momentum detection - Is the stock moving right now?"""
    change = data['pChange']
    vwap = data['vwap']
    price = data['lastPrice']
    
    score = 0
    signals = []
    
    if 0.5 < change < 2:
        score += 10; signals.append(f"+{change:.1f}% today")
    elif 0 < change <= 0.5:
        score += 6; signals.append("Mild positive")
    elif -1 < change < 0:
        score += 4; signals.append("Slight dip")
    
    if vwap > 0 and price > vwap:
        score += 5; signals.append("Above VWAP")
    
    if data['open'] > 0 and price > data['open']:
        score += 3; signals.append("Above open")
    
    return {'score': min(20, score), 'signal': ' | '.join(signals) if signals else 'No momentum'}

def layer_3_smart_money(data):
    """Smart money detection - Are institutions buying?"""
    score = 0
    signals = []
    
    try:
        bq = data['totalBuyQuantity']
        sq = data['totalSellQuantity']
        dq = data['deliveryQuantity']
        tv = data['totalTradedVolume']
        
        if sq > 0 and bq / sq > 1.3:
            score += 8; signals.append(f"Buy pressure {bq/sq:.1f}x")
        
        if tv > 0 and dq > 0:
            dp = (dq / tv) * 100
            if dp > 60:
                score += 10; signals.append(f"Delivery {dp:.0f}%")
            elif dp > 40:
                score += 5; signals.append(f"Delivery {dp:.0f}%")
    except: pass
    
    return {'score': min(20, score), 'signal': ' | '.join(signals) if signals else 'No smart money signal'}

def layer_4_wave_position(data):
    """Elliott Wave position"""
    price = data['lastPrice']
    h52 = data['weekHighLow']['max']
    l52 = data['weekHighLow']['min']
    
    if h52 == 0 or l52 == 0: return {'score': 0, 'signal': 'No data'}
    
    fib_range = h52 - l52
    position = ((price - l52) / fib_range) * 100 if fib_range > 0 else 50
    
    if position < 23.6:
        return {'score': 18, 'signal': '🌊 Wave-1: Rally Starting', 'priority': 1}
    elif position < 50:
        return {'score': 15, 'signal': '🌊 Wave-2: Best Buy Zone', 'priority': 2}
    elif position < 78.6:
        return {'score': 10, 'signal': '🌊 Wave-3/4: Trending', 'priority': 3}
    else:
        return {'score': 3, 'signal': '🌊 Wave-5: Near Top', 'priority': 5}

def layer_5_volume_profile(data):
    """Volume analysis"""
    score = 0
    try:
        vol = data['totalTradedVolume']
        if vol > 5000000: score = 10
        elif vol > 2000000: score = 7
        elif vol > 500000: score = 4
    except: pass
    return {'score': min(10, score), 'signal': f"Volume: {data['totalTradedVolume']:,}" if data['totalTradedVolume'] > 0 else 'Low volume'}

def layer_6_mean_reversion(data):
    """Mean reversion - How far from average?"""
    price = data['lastPrice']
    h52 = data['weekHighLow']['max']
    l52 = data['weekHighLow']['min']
    
    if h52 == 0 or l52 == 0: return {'score': 0, 'signal': 'No data'}
    
    mid_52 = (h52 + l52) / 2
    deviation = ((price - mid_52) / mid_52) * 100
    
    if deviation < -20:
        return {'score': 12, 'signal': '⬇️ Oversold - Reversion UP likely'}
    elif deviation < -10:
        return {'score': 8, 'signal': '⬇️ Below mean - Room to grow'}
    elif deviation > 20:
        return {'score': 0, 'signal': '⬆️ Overbought - Reversion DOWN likely'}
    elif deviation > 10:
        return {'score': 3, 'signal': '⬆️ Above mean - Caution'}
    else:
        return {'score': 5, 'signal': '➡️ Near mean - Balanced'}

def layer_7_sector_strength(sector):
    """Sector rotation analysis"""
    sector_scores = {
        'IT': 8, 'Banking': 7, 'Pharma': 8, 'Consumer': 7,
        'Auto': 6, 'Finance': 7, 'Energy': 6, 'Others': 5
    }
    return {'score': sector_scores.get(sector, 5), 'signal': f'Sector: {sector}'}

def layer_8_risk_arbitrage(data):
    """Risk assessment"""
    price = data['lastPrice']
    h52 = data['weekHighLow']['max']
    l52 = data['weekHighLow']['min']
    
    score = 10
    warnings = []
    
    if h52 > 0 and l52 > 0:
        volatility = ((h52 - l52) / l52) * 100
        if volatility > 80:
            score -= 5; warnings.append("High volatility")
        elif volatility > 50:
            score -= 2
    
    if abs(data['pChange']) > 5:
        score -= 3; warnings.append("Extreme move today")
    
    return {'score': max(0, min(10, score)), 'signal': ' | '.join(warnings) if warnings else 'Low risk'}

# ============================================
# COMBINE ALL 8 LAYERS
# ============================================
def master_analysis(data, sector):
    """Combine all 8 layers into one SUPER SCORE"""
    
    layers = {
        '💎 Value': layer_1_value(data),
        '⚡ Momentum': layer_2_momentum(data),
        '💰 Smart Money': layer_3_smart_money(data),
        '🌊 Wave': layer_4_wave_position(data),
        '📊 Volume': layer_5_volume_profile(data),
        '🔄 Mean Rev': layer_6_mean_reversion(data),
        '🏭 Sector': layer_7_sector_strength(sector),
        '🛡️ Risk': layer_8_risk_arbitrage(data)
    }
    
    total_score = sum(l['score'] for l in layers.values())
    total_score = min(95, max(25, total_score + 20))  # Boost from +10 to +20
    
    # Determine signal (RECALIBRATED)
    active_signals = [name for name, l in layers.items() if l['score'] >= 5]  # Lowered from 8 to 5
    
    if len(active_signals) >= 7:
        signal = "🔥 MASTER SUPER SIGNAL"
        stars = "⭐⭐⭐⭐⭐"
        confidence = "VERY HIGH"
        position = "20%"
    elif len(active_signals) >= 5:
        signal = "🟢 STRONG CONSENSUS"
        stars = "⭐⭐⭐⭐"
        confidence = "HIGH"
        position = "15%"
    elif len(active_signals) >= 3:
        signal = "🔵 MODERATE"
        stars = "⭐⭐⭐"
        confidence = "MODERATE"
        position = "10%"
    elif len(active_signals) >= 1:
        signal = "🟡 WATCH"
        stars = "⭐⭐"
        confidence = "LOW"
        position = "5%"
    else:
        signal = "⚪ SKIP"
        stars = "⭐"
        confidence = "NONE"
        position = "0%"
    
    return {
        'symbol': data['symbol'],
        'sector': sector,
        'price': data['lastPrice'],
        'change': data['pChange'],
        'total_score': total_score,
        'signal': signal,
        'stars': stars,
        'confidence': confidence,
        'position': position,
        'layers': layers,
        'active_count': len(active_signals),
        'active_signals': active_signals
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
    print(f"🔥 MASTER COORDINATOR v5.0 - {now.strftime('%d-%b %I:%M %p')}")
    
    all_stocks = [(sym, sec) for sec, syms in STOCKS.items() for sym in syms]
    
    for symbol, sector in all_stocks:
        try:
            data = robust_nse_fetch(symbol)
            if not data: continue
            
            result = master_analysis(data, sector)
            results.append(result)
            
            print(f"  {symbol:15} Score:{result['total_score']:.0f} | {result['active_count']}/8 layers | {result['signal']}")
            time.sleep(0.1)
        except: pass
    
    if not results:
        send_telegram("❌ No data available.")
        return
    
    results.sort(key=lambda x: x['total_score'], reverse=True)
    
    super_signals = [r for r in results if r['active_count'] >= 6]
    strong = [r for r in results if 4 <= r['active_count'] < 6]
    
    msg = f"<b>🔥 MASTER COORDINATOR v5.0</b>\n"
    msg += f"{now.strftime('%d-%b %I:%M %p')} IST\n"
    msg += f"{'═'*35}\n\n"
    
    msg += f"<b>8-Layer Analysis Complete:</b>\n"
    msg += f"Value | Momentum | Smart Money | Wave\n"
    msg += f"Volume | Mean Rev | Sector | Risk\n\n"
    
    msg += f"<b>RESULTS:</b>\n"
    msg += f"🔥 Master Signals (6+/8): {len(super_signals)}\n"
    msg += f"🟢 Strong (4-5/8): {len(strong)}\n"
    msg += f"Total Analyzed: {len(results)}\n\n"
    
    # Show top picks
    top_picks = super_signals[:3] if super_signals else results[:5]
    
    msg += f"<b>🎯 TOP PICKS</b>\n{'═'*35}\n\n"
    
    for i, r in enumerate(top_picks, 1):
        emoji = "🔥" if r['active_count'] >= 6 else "🟢" if r['active_count'] >= 4 else "🔵"
        
        msg += f"{emoji} <b>#{i} {r['symbol']}</b> | {r['sector']} | Rs.{r['price']:.0f}\n"
        msg += f"{'─'*35}\n"
        msg += f"Score: <b>{r['total_score']:.0f}/100</b> {r['stars']}\n"
        msg += f"Signal: <b>{r['signal']}</b>\n"
        msg += f"Confidence: {r['confidence']} | Position: {r['position']}\n"
        msg += f"Layers Active: <b>{r['active_count']}/8</b>\n\n"
        
        msg += f"<b>Layer Details:</b>\n"
        for name, layer in r['layers'].items():
            if layer['score'] >= 8:
                msg += f"  ✅ {name}: {layer['signal']} ({layer['score']}pts)\n"
            elif layer['score'] >= 4:
                msg += f"  ⚠️ {name}: {layer['signal']} ({layer['score']}pts)\n"
        
        msg += f"\n<b>Active Signals:</b> {', '.join(r['active_signals'][:4])}\n\n"
    
    msg += f"{'═'*35}\n"
    msg += f"<i>8-Layer Institutional Grade Analysis</i>\n"
    msg += f"<i>6+/8 layers = Highest conviction trades</i>"
    
    send_telegram(msg)
    
    super_count = len(super_signals)
    print(f"\n✅ Sent! Master Signals: {super_count} | Strong: {len(strong)}")

if __name__ == "__main__":
    run()
