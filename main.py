import requests
import time
import pygame
import signal
import sys
import os
import yaml  # 新增：YAML支持

# 全局变量：上次价格，用于计算变化率；警报状态
last_price = None
high_alerted = False  # 高价警报是否已触发
low_alerted = False   # 低价警报是否已触发

def signal_handler(sig, frame):
    """优雅退出：停止音乐并退出"""
    print("\n监控停止。按任意键退出...")
    if pygame.mixer.get_init():
        pygame.mixer.music.stop()
    sys.exit(0)

def get_binance_price(symbol):
    """
    使用官方API获取价格。
    :param symbol: 币种符号，如 'ACTUSDT'
    :return: (价格float, 错误消息) 或 (None, None) 如果成功
    """
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}  # 模拟浏览器
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            price = float(data.get('price', 0))
            return price, None
        else:
            return None, f"请求失败，状态码: {response.status_code}"
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
    """加载YAML配置文件，回退到默认/输入"""
    config_file = 'config.yaml'
    default_config = {
        'symbol': 'ACTUSDT',
        'alert_price': 97500.0,
        'low_alert_price': 0,
        'interval': 1,
        'music_file': 'music.mp3'
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                print(f"✅ 从 {config_file} 加载配置成功。")
                # 合并默认值，确保所有键存在
                for key, value in default_config.items():
                    config.setdefault(key, value)
                return config
        except Exception as e:
            print(f"⚠️ 加载 {config_file} 失败: {e}，使用命令行输入。")
    
    print(f"ℹ️ 未找到 {config_file}，请通过命令行输入配置。")
    # 回退到命令行输入
    config = {}
    config['symbol'] = input("请输入币种符号 (默认 ACTUSDT): ").strip().upper() or 'ACTUSDT'
    try:
        config['alert_price'] = float(input("请输入高价报警阈值 (默认 97500.0，设0禁用): ") or 97500.0)
    except ValueError:
        config['alert_price'] = 97500.0
    try:
        config['low_alert_price'] = float(input("请输入低价报警阈值 (默认 0，设0禁用): ") or 0)
    except ValueError:
        config['low_alert_price'] = 0
    config['interval'] = int(input("请输入监控间隔 (秒，默认 1): ") or 1)
    config['music_file'] = input("请输入音乐文件路径 (默认 music.mp3): ").strip() or 'music.mp3'
    
    return config

def main():
    # 加载配置
    config = load_config()

    symbol = config['symbol']
    alert_price = config['alert_price']
    low_alert_price = config['low_alert_price']
    interval = config['interval']
    music_file = config['music_file']

    # 初始化pygame并检查音乐文件
    try:
        pygame.mixer.init()
        if not os.path.exists(music_file):
            print(f"⚠️ 警告: 音乐文件 '{music_file}' 不存在，警报将静音。")
            music_file = None
        else:
            pygame.mixer.music.load(music_file)
            print(f"音乐文件加载成功: {music_file}")
    except Exception as e:
        print(f"pygame初始化失败: {e}，警报功能禁用。")
        music_file = None

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)

    print(f"\n开始监控 {format_symbol(symbol)}，高阈值: {alert_price}，低阈值: {low_alert_price}，间隔: {interval}s。按 Ctrl+C 停止。")
    print("-" * 70)

    global last_price, high_alerted, low_alerted
    while True:
        current_price, error = get_binance_price(symbol)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        if error:
            print(f"[{timestamp}] 错误: {error}")
        else:
            formatted_symbol = format_symbol(symbol)
            change_pct = ((current_price - last_price) / last_price * 100) if last_price else 0
            print(f"[{timestamp}] {formatted_symbol} | 价格: {current_price:.4f} USDT | 变化: {change_pct:+.2f}%")

            # 高价警报
            if alert_price > 0 and current_price > alert_price and not high_alerted and music_file and not pygame.mixer.music.get_busy():
                print(f"⚠️ 高价警报！{formatted_symbol} 价格 {current_price:.4f} > {alert_price}！播放音乐...")
                pygame.mixer.music.play(loops=0)  # 播放一次
                high_alerted = True  # 标记已报警，防止连续触发

            # 低价警报
            if low_alert_price > 0 and current_price < low_alert_price and not low_alerted and music_file and not pygame.mixer.music.get_busy():
                print(f"⚠️ 低价警报！{formatted_symbol} 价格 {current_price:.4f} < {low_alert_price}！播放音乐...")
                pygame.mixer.music.play(loops=0)  # 播放一次
                low_alerted = True  # 标记已报警，防止连续触发

            # 重置警报状态：如果价格回落（高价后低于阈值）或反弹（低价后高于阈值），重置标志
            if current_price <= alert_price:
                high_alerted = False
            if current_price >= low_alert_price:
                low_alerted = False

            last_price = current_price

        time.sleep(interval)

if __name__ == "__main__":
    main()