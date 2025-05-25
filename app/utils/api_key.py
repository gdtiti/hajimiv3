import random
import re
import os
import logging
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from app.utils.logging import format_log_message
import app.config.settings as settings
logger = logging.getLogger("my_logger")

class APIKeyManager:
    def __init__(self):
        self.api_keys = re.findall(
            r"AIzaSy[a-zA-Z0-9_-]{33}", settings.GEMINI_API_KEYS)
        # 加载更多 GEMINI_API_KEYS
        for i in range(1, 99):
            if keys := os.environ.get(f"GEMINI_API_KEYS_{i}", ""):
                self.api_keys += re.findall(r"AIzaSy[a-zA-Z0-9_-]{33}", keys)
            else:
                break

        # 加载并处理API端点配置
        self.api_endpoints = settings.GEMINI_API_ENDPOINTS.split(',') if ',' in settings.GEMINI_API_ENDPOINTS else [settings.GEMINI_API_ENDPOINTS]
        
        self.key_stack = [] # 初始化密钥栈
        self._reset_key_stack() # 初始化时创建随机密钥栈
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.lock = asyncio.Lock() # Added lock

    def _reset_key_stack(self):
        """创建并随机化密钥栈"""
        shuffled_keys = self.api_keys[:]  # 创建 api_keys 的副本以避免直接修改原列表
        random.shuffle(shuffled_keys)
        self.key_stack = shuffled_keys

    async def get_available_key(self):
        """从栈顶获取密钥，若栈空则重新生成
        
        实现负载均衡：
        1. 维护一个随机排序的栈存储apikey
        2. 每次调用从栈顶取出一个key返回
        3. 栈空时重新随机生成栈
        4. 确保异步和并发安全
        """
        async with self.lock:
            # 如果栈为空，重新生成
            if not self.key_stack:
                self._reset_key_stack()
            
            # 从栈顶取出key
            if self.key_stack:
                return self.key_stack.pop()
            
            # 如果没有可用的API密钥，记录错误
            if not self.api_keys:
                log_msg = format_log_message('ERROR', "没有配置任何 API 密钥！")
                logger.error(log_msg)
            log_msg = format_log_message('ERROR', "没有可用的API密钥！")
            logger.error(log_msg)
            return None

    async def get_random_endpoint(self):
        """从配置的端点列表中随机选择一个端点"""
        return random.choice(self.api_endpoints)

    def show_all_keys(self):
        log_msg = format_log_message('INFO', f"当前可用API key个数: {len(self.api_keys)} ")
        logger.info(log_msg)
        for i, api_key in enumerate(self.api_keys):
            log_msg = format_log_message('INFO', f"API Key{i}: {api_key[:8]}...{api_key[-3:]}")
            logger.info(log_msg)

    def show_all_endpoints(self):
        """显示所有配置的API端点"""
        log_msg = format_log_message('INFO', f"当前配置的API端点个数: {len(self.api_endpoints)} ")
        logger.info(log_msg)
        for i, endpoint in enumerate(self.api_endpoints):
            log_msg = format_log_message('INFO', f"端点{i}: {endpoint}")
            logger.info(log_msg)

    # def blacklist_key(self, key):
    #     log_msg = format_log_message('WARNING', f"{key[:8]} → 暂时禁用 {self.api_key_blacklist_duration} 秒")
    #     logger.warning(log_msg)
    #     self.api_key_blacklist.add(key)
    #     self.scheduler.add_job(lambda: self.api_key_blacklist.discard(key), 'date',
    #                            run_date=datetime.now() + timedelta(seconds=self.api_key_blacklist_duration))

async def test_api_key(api_key: str) -> bool:
    """
    测试 API 密钥是否有效。
    """
    try:
        import httpx
        api_manager = APIKeyManager()
        endpoint = await api_manager.get_random_endpoint()
        url = f"{endpoint}/v1beta/models?key={api_key}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return True
    except Exception:
        return False
