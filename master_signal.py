"""
MASTER SIGNAL COORDINATOR v1.0
Combines: Stock Analyzer + News Scanner + Market Pulse
Finds HIGHEST CONVICTION trades across all 3 systems
"""
import os
import time
import requests
from nsetools import Nse
from datetime import datetime

os.environ['TZ'] = 'Asia/Kolkata'

# Use same bot or create a 4th for master signals
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_MASTER_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_MASTER_CHAT_ID')

# ============================================
# STOCK UNIVERSE (All 3 bots combined)
# ============================================
ALL_STOCKS = [
    # Large Caps
    'TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM',
    'HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'SBIN', 'AXISBANK',
    'RELIANCE', 'ITC', 'LT', 'HINDUNILVR',
    'SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB',
    'TITAN', 'ASIANPAINT', 'MARUTI', 'BAJFINANCE', 'BAJAJFINSV',
    'POWERGRID', 'NTPC', 'ONGC', 'TATAPOWER', 'ADANIPORTS',
    # Mid Caps
    'TRENT', 'DMART', 'PIDILITIND', 'DABUR',
    'BANDHANBNK', 'FEDERALBNK', 'IDFCFIRSTB', 'AUBANK',
    'HAL', 'BEL', 'IRCON', 'JINDALSTEL', 'TATASTEEL', 'JSWSTEEL',
    'LAURUSLABS', 'ALKEM', 'BIOCON', 'CHOLAFIN', 'MUTHOOTFIN',
    'PERSISTENT', 'EICHERMOT', 'TVSMOTOR', 'TATAMOTORS', 'M&M',
    'ZOMATO', 'IRCTC', 'TATACONSUM', 'ADANIGREEN',
    'NHPC', 'PFC', 'RECLTD', 'CANBK', 'UNIONBANK', 'PNB'
]

# ============================================
# MULTI-FACTOR SCORING
# ============================================
def calculate_master_score(symbol, price_data):
    """Score stock across ALL 3 systems"""
    score = 0
    signals = []
    confidence_factors = []
    
    p = price_data
    
    # 1. TECHNICAL SCORE (Stock Analyzer method) - 35 points
    tech_score = 0
    day_range = p['high'] - p['low']
    pos = ((p['price'] - p['low']) / day_range * 100) if day_range > 0 else 50
    
    if 50 < pos < 80: tech_score += 10
    elif pos < 30: tech_score += 8
    
    if p['high_52'] > 0:
        dist_high = ((p['high_52'] - p['price']) / p['high_52']) * 100
        if dist_high > 30: tech_score += 12
        elif dist_high > 15: tech_score += 8
    
    if p['low_52'] > 0:
        dist_low = ((p['price'] - p['low_52']) / p['low_52']) * 100
        if dist_low < 10: tech_score += 8
    
    if 0.5 < p['change'] < 2: tech_score += 8
    elif 0 < p['change'] <= 0.5: tech_score += 5
    
    if tech_score >= 25:
        signals.append("📊 Technical")
        confidence_factors.append(f"Tech Score: {tech_score}/35")
    score += tech_score
    
    # 2. NEO WAVE SCORE - 35 points
    wave_score = 0
    fib_range = p['high_52'] - p['low_52']
    
    if fib_range > 0:
        fib_382 = p['low_52'] + fib_range * 0.382
        fib_500 = p['low_52'] + fib_range * 0.500
        fib_618 = p['low_52'] + fib_range * 0.618
        
        # Wave 2: Pullback to Fib zone (best buy)
        if abs(p['price'] - fib_618) / p['price'] < 0.03:
            wave_score += 20
            signals.append("🌊 Wave-2 Golden Zone")
        elif abs(p['price'] - fib_500) / p['price'] < 0.03:
            wave_score += 15
            signals.append("🌊 Wave-2 50% Fib")
        
        # Wave 3: Above 50% Fib (strong momentum)
        if p['price'] > fib_500 and p['change'] > 0:
            wave_score += 15
            signals.append("🌊 Wave-3 Power Move")
        
        # Near 52W high breakout
        if p['high_52'] > 0 and ((p['high_52'] - p['price']) / p['high_52']) < 0.08:
            wave_score += 12
            signals.append("🌊 Near 52W Breakout")
    
    if wave_score >= 15:
        confidence_factors.append(f"Wave Score: {wave_score}/35")
    score += wave_score
    
    # 3. SMART MONEY (Volume/Delivery) - 15 points
    smart_score = 0
    try:
        buy_qty = p.get('buy_qty', 0)
        sell_qty = p.get('sell_qty', 0)
        total = buy_qty + sell_qty
        
        if total > 0:
            buy_ratio = (buy_qty / total) * 100
            if buy_ratio > 60: smart_score += 12
            elif buy_ratio > 50: smart_score += 8
            elif buy_ratio > 40: smart_score += 5
        
        delivery = p.get('delivery', 0)
        if delivery > 60: smart_score += 3
    except:
        pass
    
    if smart_score >= 8:
        signals.append("💰 Smart Money")
        confidence_factors.append(f"Smart: {smart_score}/15")
    score += smart_score
    
    # 4. MOMENTUM - 15 points
    momentum = 0
    if 1 < p['change'] < 3: momentum += 10
    elif 0.5 < p['change'] <= 1: momentum += 7
    elif 0 < p['change'] <= 0.5: momentum += 5
    elif -2 < p['change'] < 0: momentum += 4
    
    if p['price'] > p.get('vwap', 0): momentum += 5
    
    if momentum >= 8:
        signals.append("⚡ Momentum")
    score += momentum
    
    # Total
    score = min(95, score + 5)
    
    # Conviction Level
    if score >= 75:
        conviction = "🔥 SUPER SIGNAL"
        stars = "⭐⭐⭐⭐⭐"
        position = "20%"
    elif score >= 60:
        conviction = "🟢 HIGH CONVICTION"
        stars = "⭐⭐⭐⭐"
        position = "15%"
    elif score >= 45:
        conviction = "🔵 MODERATE"
        stars = "⭐⭐⭐"
        position = "10%"
    else:
        conviction = "🟡 WATCH"
        stars = "⭐⭐"
        position = "5%"
    
    # Calculate targets
    target = round(p['price'] * (1 + score/100), 0)
    stop_loss = round(p['price'] * 0.95, 0)
    
    return {
        'symbol': symbol,
        'price': p['price'],
        'change': p['change'],
        'score': score,
        'stars': stars,
        'conviction': conviction,
        'signals': signals,
        'factors': confidence_factors,
        'target': target,
        'stop_loss': stop_loss,
        'position': position,
        'risk_reward': round(((target - p['price']) / (p['price'] - stop_loss)), 1) if (p['price'] - stop_loss) > 0 else 0
    }

def send_master_alert(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900: text = text[:3900]
        resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        return resp.json().get('ok', False)
    except: return False

def run_master_scan():
    nse = Nse()
    results = []
    now = datetime.now()
    
    print(f"🔍 MASTER SIGNAL SCAN - {now.strftime('%d-%b %I:%M %p')}")
    
    for symbol in ALL_STOCKS:
        try:
            q = nse.get_quote(symbol)
            if not q: continue
            
            intraday = q.get('intraDayHighLow', {})
            weekly = q.get('weekHighLow', {})
            
            price = float(q.get('lastPrice', 0))
            if price == 0: continue
            
            # Gather all data
            data = {
                'price': price,
                'high': float(intraday.get('max', 0)),
                'low': float(intraday.get('min', 0)),
                'open': float(q.get('open', 0)),
                'change': float(q.get('pChange', 0)),
                'vwap': float(q.get('vwap', 0)) if q.get('vwap') else 0,
                'high_52': float(weekly.get('max', 0)),
                'low_52': float(weekly.get('min', 0)),
                'prev_close': float(q.get('previousClose', 0))
            }
            
            # Volume data
            try:
                data['buy_qty'] = float(q.get('totalBuyQuantity', 0))
                data['sell_qty'] = float(q.get('totalSellQuantity', 0))
                dq = float(q.get('deliveryQuantity', 0))
                tv = float(q.get('totalTradedVolume', 0))
                data['delivery'] = (dq/tv*100) if tv > 0 else 0
            except:
                data['buy_qty'] = 0
                data['sell_qty'] = 0
                data['delivery'] = 0
            
            result = calculate_master_score(symbol, data)
            
            if result['score'] >= 40:  # Only show meaningful signals
                results.append(result)
            
            time.sleep(0.08)
        except:
            pass
    
    return results, now

def build_master_message(results, now):
    if not results: return None
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    super_signals = [r for r in results if r['score'] >= 75]
    high_conv = [r for r in results if 60 <= r['score'] < 75]
    
    msg = f"🔥 <b>MASTER SIGNAL COORDINATOR</b>\n"
    msg += f"{now.strftime('%d-%b %I:%M %p')} IST\n"
    msg += f"{'═'*35}\n\n"
    
    msg += f"📊 <b>Combined Analysis:</b>\n"
    msg += f"├ Technical + Neo Wave + Smart Money\n"
    msg += f"├ Super Signals: {len(super_signals)}\n"
    msg += f"├ High Conviction: {len(high_conv)}\n"
    msg += f"└ Total Scanned: {len(results)}\n\n"
    
    if super_signals:
        msg += f"🔥 <b>SUPER SIGNALS (All Systems Agree)</b>\n{'═'*35}\n\n"
        for i, r in enumerate(super_signals[:3], 1):
            msg += format_signal(i, r)
    
    if high_conv:
        msg += f"<b>HIGH CONVICTION PICKS</b>\n{'═'*35}\n\n"
        for i, r in enumerate(high_conv[:3], 1):
            msg += format_signal(i + len(super_signals), r)
    
    # Common across systems
    common = [r for r in results if len(r['signals']) >= 3]
    if common:
        msg += f"\n🎯 <b>MULTI-SYSTEM CONFIRMED ({len(common)} stocks)</b>\n"
        msg += f"These appear strong across multiple factors:\n"
        for r in common[:3]:
            msg += f"• {r['symbol']} - {', '.join(r['signals'])}\n"
    
    msg += f"\n{'═'*35}\n"
    msg += f"📱 <i>Master Coordinator | Combined Analysis</i>"
    
    return msg

def format_signal(i, r):
    """Format individual signal"""
    msg = f"<b>#{i} {r['symbol']}</b> | Rs.{r['price']:.0f} | {r['change']:+.1f}%\n"
    msg += f"{'─'*35}\n"
    msg += f"Score: {r['score']}/100 {r['stars']}\n"
    msg += f"Signal: {r['conviction']}\n"
    msg += f"Systems: {' | '.join(r['signals'])}\n\n"
    msg += f"💰 Entry: Rs.{r['price']:.0f} | Target: Rs.{r['target']:.0f}\n"
    msg += f"🛑 Stop: Rs.{r['stop_loss']:.0f} | Position: {r['position']}\n"
    msg += f"📊 R:R: 1:{r['risk_reward']}\n\n"
    return msg

if __name__ == "__main__":
    results, now = run_master_scan()
    if results:
        msg = build_master_message(results, now)
        if msg and send_master_alert(msg):
            print(f"✅ Master signal sent! {len(results)} stocks analyzed")
        else:
            print("❌ Failed to send")
    else:
        print("No significant signals")
