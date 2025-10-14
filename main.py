#main.py
import requests
import time
import pygame
import signal
import sys
import os
import yaml

# 全局变量：每个币种的上次价格，用于计算变化率
last_prices = {}  # dict: (symbol, exchange) -> last_price
alert_channels = {}  # dict: symbol -> Channel (for alert sound, per symbol regardless of exchange)

def display_width(s):
    """计算字符串的显示宽度（汉字/全角为2，ASCII为1）"""
    return sum(2 if ord(c) > 127 else 1 for c in s)

def signal_handler(sig, frame):
    """优雅退出：停止所有声音并退出"""
    print("\n监控停止。按任意键退出...")
    if pygame.mixer.get_init():
        pygame.mixer.quit()  # 停止所有声音
    sys.exit(0)

def print_colored(text, color='red'):
    """打印彩色文本（ANSI转义码）"""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'end': '\033[0m'
    }
    print(f"{colors.get(color, '')}{text}{colors['end']}")

def print_aligned(timestamp, exchange, formatted_symbol, current_price, change_pct, is_alert=False, is_invalid=False, is_error=False):
    """打印对齐的价格信息"""
    # 定义列宽度（显示宽度）
    ts_width = 20  # 时间戳显示宽（实际字符19 +1空格）
    ex_display_width = 16  # 交易所列显示宽
    sym_width = 10  # 符号显示宽（英文为主）
    price_width = 16  # 价格列显示宽
    change_width = 10  # 变化列显示宽
    
    ex_base = exchange.upper()
    base_width = display_width(ex_base)
    pad_chars = max(0, ex_display_width - base_width)
    ex_display = ex_base + ' ' * pad_chars
    
    price_str = f"{current_price:>14.4f}"
    change_str = f"{change_pct:>+8.2f}%"
    
    if is_invalid:
        line = f"[{timestamp:<{ts_width}}] [{ex_display}] {formatted_symbol:<{sym_width}} | 价格: {price_str:<{price_width}} USDT (无效) | 变化: {change_str:<{change_width}}"
        print_colored(line, 'yellow')
    elif is_alert:
        line = f"[{timestamp:<{ts_width}}] [{ex_display}] {formatted_symbol:<{sym_width}} | 价格: {price_str:<{price_width}} USDT | 变化: {change_str:<{change_width}}"
        print_colored(line, 'red')
    elif is_error:
        error_msg = f"错误: {current_price}"  # current_price 这里是 error msg
        # 对于错误，简化对齐，使用固定宽
        line = f"[{timestamp:<{ts_width}}] [{ex_display}] {formatted_symbol:<{sym_width}} | {error_msg:<{price_width + change_width + 10}}"
        print(line)
    else:
        line = f"[{timestamp:<{ts_width}}] [{ex_display}] {formatted_symbol:<{sym_width}} | 价格: {price_str:<{price_width}} USDT | 变化: {change_str:<{change_width}}"
        print(line)

def get_price(exchange, symbol):
    """
    使用指定交易所API获取价格。
    :param exchange: 交易所名称，如 'binance'
    :param symbol: 币种符号，如 'BTCUSDT'
    :return: (价格float, 错误消息) 或 (None, None) 如果成功
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        if exchange == '币安':
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                price = float(data.get('price', 0))
                return price, None
            else:
                return None, f"请求失败，状态码: {response.status_code}"
        
        elif exchange == 'okx':
            formatted_sym = symbol[:-4] + '-' + symbol[-4:]
            url = f"https://www.okx.com/api/v5/market/ticker?instId={formatted_sym}"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    price = float(data['data'][0].get('last', 0))
                    return price, None
                else:
                    return None, "无数据"
            else:
                return None, f"请求失败，状态码: {response.status_code}"
        
        elif exchange == '芝麻开门':
            formatted_sym = symbol[:-4] + '_' + symbol[-4:]
            url = f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={formatted_sym}"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    price = float(data[0].get('last', 0))
                    return price, None
                else:
                    return None, "无数据"
            else:
                return None, f"请求失败，状态码: {response.status_code}"
        
        elif exchange == 'bitget':
            url = f"https://api.bitget.com/api/v2/spot/market/tickers?symbol={symbol}"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    # 修复：Bitget 字段是 'lastPr'，不是 'lastPrice'
                    price = float(data['data'][0].get('lastPr', 0))
                    return price, None
                else:
                    return None, "无数据"
            else:
                return None, f"请求失败，状态码: {response.status_code}"
        
        elif exchange == '库币kucoin':
            formatted_sym = symbol[:-4] + '-' + symbol[-4:]
            url = f"https://api.kucoin.com/api/v1/market/stats?symbol={formatted_sym}"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    price = float(data['data'].get('last', 0))
                    return price, None
                else:
                    return None, "无数据"
            else:
                return None, f"请求失败，状态码: {response.status_code}"
        
        elif exchange == '抹茶mexc':
            url = f"https://api.mexc.com/api/v3/ticker/price?symbol={symbol}"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                price = float(data.get('price', 0))
                return price, None
            else:
                return None, f"请求失败，状态码: {response.status_code}"
        
        elif exchange == '火币huobi':
            formatted_sym = symbol.lower()
            url = f"https://api.huobi.pro/market/detail/merged?symbol={formatted_sym}"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('tick'):
                    price = float(data['tick'].get('close', 0))
                    return price, None
                else:
                    return None, "无数据"
            else:
                return None, f"请求失败，状态码: {response.status_code}"
        
        elif exchange == 'bybit':
            url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('result', {}).get('list') and len(data['result']['list']) > 0:
                    price = float(data['result']['list'][0].get('lastPrice', 0))
                    return price, None
                else:
                    return None, "无数据"
            else:
                return None, f"请求失败，状态码: {response.status_code}"
        
        else:
            return None, f"不支持的交易所: {exchange}"
    
    except Exception as e:
        return None, f"网络/解析错误: {str(e)}"

def format_symbol(symbol):
    """格式化符号为 BASE/QUOTE"""
    if len(symbol) > 3:
        base = symbol[:-4]
        quote = symbol[-4:]
        return f"{base}/{quote}"
    return symbol

def load_config():
    """加载YAML配置文件，回退到默认"""
    config_file = 'config.yaml'
    default_single = {
        'symbol': 'BTCUSDT',
        'alert_price': 97500.0,
        'low_alert_price': 0
    }
    default_config = {
        'symbols': [default_single],
        'interval': 1,
        'music_file': 'music.mp3',
        'price_gap_threshold': 1.0  # 默认价格差距阈值 1%
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                print(f"✅ 从 {config_file} 加载配置成功。")
                # 如果是旧格式（有'symbol'键），包装成symbols列表
                if 'symbol' in config:
                    single = {k: config[k] for k in ['symbol', 'alert_price', 'low_alert_price'] if k in config}
                    config['symbols'] = [single]
                # 合并默认值，确保所有键存在
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                for sym_config in config['symbols']:
                    for k, v in {'alert_price': 97500.0, 'low_alert_price': 0}.items():
                        sym_config.setdefault(k, v)
                config.setdefault('price_gap_threshold', 1.0)
                return config
        except Exception as e:
            print(f"⚠️ 加载 {config_file} 失败: {e}，使用默认配置。")
    
    print(f"ℹ️ 未找到 {config_file}，使用默认配置。")
    return default_config

def select_mode_and_exchanges():
    """选择模式并选择交易所"""
    exchanges_list = ['币安', 'okx', '芝麻开门', 'bitget', '库币kucoin', '抹茶mexc', '火币huobi', 'bybit']
    print("\n请选择模式:")
    print("1. 交易所价格警报模式")
    print("2. 多个交易所比价模式")
    while True:
        try:
            mode = int(input("请输入模式序号 (1 或 2): "))
            if mode == 1:
                print("\n请选择单个交易所:")
                for i, ex in enumerate(exchanges_list, 1):
                    print(f"{i}. {ex.upper()}")
                while True:
                    try:
                        choice = int(input("请输入序号 (1-8): "))
                        if 1 <= choice <= 8:
                            return [exchanges_list[choice - 1]]
                        else:
                            print("无效序号，请重新输入。")
                    except ValueError:
                        print("请输入有效数字。")
            elif mode == 2:
                print("\n请选择多个交易所:")
                for i, ex in enumerate(exchanges_list, 1):
                    print(f"{i}. {ex.upper()}")
                while True:
                    choice_str = input("请输入序号，以逗号间隔 (e.g. 1,3,5): ").strip()
                    if not choice_str:
                        print("请输入至少一个序号。")
                        continue
                    indices = [int(i.strip()) for i in choice_str.split(',') if i.strip().isdigit()]
                    if not indices:
                        print("无效输入，请重新输入。")
                        continue
                    valid_indices = [idx for idx in indices if 1 <= idx <= 8]
                    if len(valid_indices) != len(indices):
                        print("有些序号无效，请重新输入。")
                        continue
                    selected = [exchanges_list[idx - 1] for idx in valid_indices]
                    if len(selected) < 2:  # 多个模式至少2个交易所
                        print("多个模式需至少选择2个交易所。")
                        continue
                    return selected
            else:
                print("无效模式，请输入 1 或 2。")
        except ValueError:
            print("请输入有效数字。")

def main():
    # 加载配置（无输入）
    config = load_config()

    # 启动时选择模式和交易所
    exchanges = select_mode_and_exchanges()
    config['exchanges'] = exchanges

    symbols_configs = config['symbols']
    interval = config['interval']
    music_file = config['music_file']
    price_gap_threshold = config.get('price_gap_threshold', 1.0)
    is_multi_exchange = len(exchanges) > 1

    # 初始化pygame并检查音乐文件（使用Sound以支持不同币种叠加，但同币种不叠加）
    alert_sound = None
    try:
        pygame.mixer.init()
        if not os.path.exists(music_file):
            print(f"⚠️ 警告: 音乐文件 '{music_file}' 不存在，警报将静音。")
            music_file = None
        else:
            alert_sound = pygame.mixer.Sound(music_file)
            print(f"警报声音加载成功: {music_file} (Sound模式，支持不同币种叠加，同币种顺序播放)")
    except Exception as e:
        print(f"pygame初始化失败: {e}，警报功能禁用。")
        music_file = None

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)

    if is_multi_exchange:
        print(f"\n开始监控多个交易所比价报警 {', '.join([e.upper() for e in exchanges])} {len(symbols_configs)} 个币种，价格差距阈值: {price_gap_threshold}%，间隔: {interval}s。按 Ctrl+C 停止。")
    else:
        print(f"\n开始监控单个交易所价格报警 {exchanges[0].upper()} {len(symbols_configs)} 个币种，高/低阈值如配置，间隔: {interval}s。按 Ctrl+C 停止。")
    for sc in symbols_configs:
        sym = sc['symbol']
        if not is_multi_exchange:
            print(f"  - {format_symbol(sym)}: 高 {sc['alert_price']}, 低 {sc['low_alert_price']}")
    print("-" * 70)

    # 定义 ex_display_width 用于 gap_alert 打印（与 print_aligned 一致）
    ex_display_width = 16

    global last_prices, alert_channels
    while True:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        for sc in symbols_configs:
            symbol = sc['symbol']
            formatted_symbol = format_symbol(symbol)
            if not is_multi_exchange:
                # 单个交易所模式
                exchange = exchanges[0]
                alert_price = sc['alert_price']
                low_alert_price = sc['low_alert_price']
                current_price, error = get_price(exchange, symbol)
                key = (symbol, exchange)

                if error:
                    print_aligned(timestamp, exchange, formatted_symbol, error, 0, is_error=True)
                else:
                    last_price = last_prices.get(key, None)
                    change_pct = ((current_price - last_price) / last_price * 100) if last_price else 0

                    # 检查是否触发报警
                    is_high_alert = alert_price > 0 and current_price > alert_price
                    is_low_alert = low_alert_price > 0 and current_price < low_alert_price
                    is_alert = is_high_alert or is_low_alert
                    print_aligned(timestamp, exchange, formatted_symbol, current_price, change_pct, is_alert=is_alert)

                    # 获取该币种的channel
                    channel = alert_channels.get(symbol)

                    # 高价警报
                    if is_high_alert and alert_sound:
                        if channel is None or not channel.get_busy():
                            print_colored(f"⚠️ 高价警报！[{exchange.upper()}] {formatted_symbol} 价格 {current_price:.4f} > {alert_price}！播放声音...", 'red')
                            channel = alert_sound.play()
                            alert_channels[symbol] = channel

                    # 低价警报
                    if is_low_alert and alert_sound:
                        if channel is None or not channel.get_busy():
                            print_colored(f"⚠️ 低价警报！[{exchange.upper()}] {formatted_symbol} 价格 {current_price:.4f} < {low_alert_price}！播放声音...", 'red')
                            channel = alert_sound.play()
                            alert_channels[symbol] = channel

                    last_prices[key] = current_price
            else:
                # 多个交易所模式：比价报警
                prices = {}
                errors = {}
                invalid_prices = {}  # 记录无效价格
                for exchange in exchanges:
                    current_price, error = get_price(exchange, symbol)
                    if error:
                        errors[exchange] = error
                    elif current_price > 0:  # 有效价格
                        prices[exchange] = current_price
                    else:  # 价格 <=0，无效
                        invalid_prices[exchange] = current_price
                        key = (symbol, exchange)
                        last_price = last_prices.get(key, None)
                        change_pct = ((current_price - last_price) / last_price * 100) if last_price else 0
                        print_aligned(timestamp, exchange, formatted_symbol, current_price, change_pct, is_invalid=True)
                    if not error:  # 无论有效无效，都更新 last_price
                        key = (symbol, exchange)
                        last_prices[key] = current_price

                # 处理错误（使用对齐）
                for exchange, error in errors.items():
                    print_aligned(timestamp, exchange, formatted_symbol, error, 0, is_error=True)

                # 打印有效价格（使用对齐函数）
                for exchange, price in prices.items():
                    key = (symbol, exchange)
                    last_price = last_prices.get(key, None)
                    change_pct = ((price - last_price) / last_price * 100) if last_price else 0
                    print_aligned(timestamp, exchange, formatted_symbol, price, change_pct)

                # 如果有效价格 >=2，计算差距
                if len(prices) >= 2:
                    min_p = min(prices.values())
                    max_p = max(prices.values())
                    gap_pct = ((max_p - min_p) / min_p) * 100  # 修复：min_p 现在 >0，无除零风险
                    is_gap_alert = gap_pct >= price_gap_threshold

                    if is_gap_alert:
                        print_colored(f"⚠️ 价格差距报警！{formatted_symbol} 差距 {gap_pct:.2f}% >= {price_gap_threshold}%", 'red')
                        # 突出打印价格（使用对齐，基于显示宽）
                        for exchange, price in prices.items():
                            ex_base = exchange.upper()
                            base_width = display_width(ex_base)
                            pad_chars = max(0, ex_display_width - base_width)
                            ex_display = ex_base + ' ' * pad_chars
                            print_colored(f"  [{ex_display}] {price:>14.4f} USDT", 'yellow')

                        # 播放声音
                        channel = alert_channels.get(symbol)
                        if alert_sound and (channel is None or not channel.get_busy()):
                            print_colored(f"播放声音报警...", 'red')
                            channel = alert_sound.play()
                            alert_channels[symbol] = channel
                else:
                    if len(prices) < 2:
                        print_colored(f"⚠️ {formatted_symbol} 有效价格不足 ({len(prices)}/ {len(exchanges)})，跳过比价报警。", 'yellow')

        time.sleep(interval)

if __name__ == "__main__":
    main()