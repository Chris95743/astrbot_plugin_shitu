from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Image as MsgImage
import aiohttp
import asyncio
import base64
import re
from io import BytesIO
from PIL import Image as PILImage


@register("astrbot_plugin_shitu", "shenx", "动漫/Gal/二游图片识别插件", "2.3.1", "https://github.com/shenxgan")
class AnimeTracePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.api_url = "https://api.animetrace.com/v1/search"
        self.waiting_sessions = {}  # 简单的会话管理
        self.timeout_tasks = {}  # 存储超时任务

    async def initialize(self):
        logger.info("动漫/Gal/二游识别插件已加载")

    @filter.command("动漫识别", "动漫图片识别")
    async def anime_search(self, event: AstrMessageEvent, args=None):
        """使用pre_stable模型进行动漫图片识别"""
        return await self.handle_image_recognition(event, "pre_stable")

    @filter.command("gal识别", "GalGame图片识别")
    async def gal_search(self, event: AstrMessageEvent, args=None):
        """使用full_game_model_kira模型进行GalGame图片识别"""
        return await self.handle_image_recognition(event, "full_game_model_kira")

    @filter.command("通用识别", "动漫/Gal/二游图片识别")
    async def trace_search(self, event: AstrMessageEvent, args=None):
        """使用animetrace_high_beta模型进行通用图片识别"""
        return await self.handle_image_recognition(event, "animetrace_high_beta")

    @filter.command("头像动漫识别")
    async def avatar_anime_search(self, event: AstrMessageEvent, args=None):
        """识别QQ用户头像（动漫模型）"""
        return await self.handle_avatar_recognition(event, "pre_stable")

    @filter.command("头像gal识别")
    async def avatar_gal_search(self, event: AstrMessageEvent, args=None):
        """识别QQ用户头像（GalGame模型）"""
        return await self.handle_avatar_recognition(event, "full_game_model_kira")

    @filter.command("头像识别")
    async def avatar_trace_search(self, event: AstrMessageEvent, args=None):
        """识别QQ用户头像（通用模型）"""
        return await self.handle_avatar_recognition(event, "animetrace_high_beta")

    async def handle_image_recognition(self, event: AstrMessageEvent, model: str):
        """简化的图片识别处理"""
        user_id = event.get_sender_id()

        # 检查当前消息是否包含图片
        image_url = await self.extract_image_from_event(event)
        if image_url:
            await self.process_image_recognition(event, image_url, model)
            return

        # 如果没有图片，设置等待状态
        self.waiting_sessions[user_id] = {
            "model": model,
            "timestamp": asyncio.get_event_loop().time(),
            "event": event,  # 保存事件对象用于超时消息发送
        }

        # 创建30秒超时任务
        if user_id in self.timeout_tasks:
            self.timeout_tasks[user_id].cancel()  # 取消之前的超时任务

        timeout_task = asyncio.create_task(self.timeout_check(user_id))
        self.timeout_tasks[user_id] = timeout_task

        await event.send(event.plain_result("📷 请发送要识别的图片（30秒内有效）"))
        logger.info(f"用户 {user_id} 进入等待图片状态，等待30秒")

    async def handle_avatar_recognition(self, event: AstrMessageEvent, model: str):
        """处理QQ头像识别"""
        try:
            # 调试日志
            logger.info(f"头像识别命令被触发 - 模型: {model}")
            logger.info(f"消息详情: {event.get_messages()}")

            # 提取被@的用户或手动输入的QQ号
            mentioned_user_id = await self.extract_mentioned_user(event)
            logger.info(f"提取到的用户ID: {mentioned_user_id}")

            if not mentioned_user_id:
                # 如果没有@任何人，默认使用发送者自己的头像
                mentioned_user_id = event.get_sender_id()
                logger.info(f"未找到被@用户，使用发送者自己的ID: {mentioned_user_id}")
                await event.send(event.plain_result("📸 识别您自己的头像..."))
            else:
                # 检查是否是手动输入的QQ号（通过正则匹配确认）
                messages = event.get_messages()
                full_text = ""
                for msg in messages:
                    if hasattr(msg, "text"):
                        full_text += str(msg.text)
                    elif hasattr(msg, "type") and msg.type == "Plain":
                        full_text += str(msg)

                import re
                qq_match = re.search(r"头像(?:动漫|gal)?识别\s*(\d{5,12})", full_text)
                if qq_match and qq_match.group(1) == mentioned_user_id:
                    logger.info(f"识别到手动输入的QQ号: {mentioned_user_id}")
                    await event.send(event.plain_result(f"📸 识别QQ号 {mentioned_user_id} 的头像..."))

            # 获取头像URL
            avatar_url = f"https://q.qlogo.cn/headimg_dl?dst_uin={mentioned_user_id}&spec=640"
            logger.info(f"获取用户头像: {mentioned_user_id}")

            # 标记此事件已被处理，避免消息监听器重复处理
            event._avatar_command_processed = True

            # 识别头像
            await self.process_image_recognition(event, avatar_url, model)

        except Exception as e:
            logger.error(f"头像识别失败: {str(e)}")
            await event.send(event.plain_result(f"❌ 头像识别失败: {str(e)}"))

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息，处理等待中的图片识别请求和特殊格式的头像识别命令"""
        user_id = event.get_sender_id()

        # 检查特殊格式的头像识别命令（消息中包含@但命令可能被遗漏的情况）
        messages = event.get_messages()
        full_text = ""

        logger.info(f"on_message收到消息，消息列表: {messages}")

        for msg in messages:
            logger.info(f"处理消息组件: type={getattr(msg, 'type', '无type')}, text={getattr(msg, 'text', '无text')}, 完整对象: {msg}")

            if hasattr(msg, "text"):
                full_text += str(msg.text)
            elif hasattr(msg, "type") and msg.type == "Plain":
                full_text += str(msg)

        logger.info(f"提取的完整文本: '{full_text}'")

        # 只有当标准命令处理器未处理时才检查
        if not hasattr(event, "_avatar_command_processed"):
            avatar_patterns = [
                (r"头像动漫识别", "pre_stable"),
                (r"头像gal识别", "full_game_model_kira"),
                (r"头像识别", "animetrace_high_beta"),
            ]

            for pattern, model in avatar_patterns:
                if re.search(pattern, full_text):
                    logger.info(f"通过on_message检测到头像识别命令: {pattern}")
                    # 标记为已处理，避免重复
                    event._avatar_command_processed = True
                    await self.handle_avatar_recognition(event, model)
                    return  # 处理完后直接返回，避免重复处理

        # 检查用户是否在等待图片识别
        if user_id not in self.waiting_sessions:
            return

        session = self.waiting_sessions[user_id]

        # 检查是否超时（30秒）
        current_time = asyncio.get_event_loop().time()
        if current_time - session["timestamp"] > 30:
            return  # 超时检查由定时任务处理，这里直接返回

        # 提取图片
        image_url = await self.extract_image_from_event(event)
        if not image_url:
            return  # 不是图片消息，继续等待

        # 找到图片，开始识别
        del self.waiting_sessions[user_id]  # 清除等待状态
        if user_id in self.timeout_tasks:
            self.timeout_tasks[user_id].cancel()  # 取消超时任务
            del self.timeout_tasks[user_id]
        await self.process_image_recognition(event, image_url, session["model"])

    async def process_image_recognition(
        self, event: AstrMessageEvent, image_url: str, model: str
    ):
        """处理图片识别"""
        try:
            # 首先尝试直接使用URL调用API（更高效）
            results = await self.call_animetrace_api_with_url(image_url, model)

            # 如果URL方式失败，再回退到下载图片方式
            if not results or not results.get("data"):
                logger.info("URL识别方式未返回结果，尝试下载图片识别...")
                img_data = await self.download_and_process_image(image_url)
                results = await self.call_animetrace_api(img_data, model)

            # 格式化并发送结果
            response = self.format_results(results, model)
            try:
                await event.send(event.plain_result(response))
            except Exception as send_error:
                logger.warning(f"发送识别结果失败: {send_error}")
                # 如果发送失败，记录日志但不抛出异常

        except Exception as e:
            logger.error(f"识别失败: {str(e)}")
            try:
                await event.send(event.plain_result(f"❌ 识别失败: {str(e)}"))
            except Exception as send_error:
                logger.warning(f"发送错误消息失败: {send_error}")
                # 如果错误消息也发送失败，记录日志但不抛出异常

    async def extract_mentioned_user(self, event: AstrMessageEvent) -> str:
        """从事件中提取被@的用户QQ号或手动输入的QQ号"""
        messages = event.get_messages()
        logger.info(f"开始提取被@用户或手动QQ号，消息列表: {messages}")

        # 首先检查是否有手动输入的QQ号
        full_text = ""
        for msg in messages:
            if hasattr(msg, "text"):
                full_text += str(msg.text)
            elif hasattr(msg, "type") and msg.type == "Plain":
                full_text += str(msg)

        logger.info(f"提取的完整文本: '{full_text}'")

        # 匹配手动输入QQ号的格式：头像识别 12345678910 或 头像识别12345678910
        import re
        qq_match = re.search(r"头像(?:动漫|gal)?识别\s*(\d{5,12})", full_text)
        if qq_match:
            qq_number = qq_match.group(1)
            logger.info(f"找到手动输入的QQ号: {qq_number}")
            return qq_number

        for msg in messages:
            logger.info(f"检查消息组件: type={getattr(msg, 'type', '无type')}, qq={getattr(msg, 'qq', '无qq')}, user_id={getattr(msg, 'user_id', '无user_id')}, text={getattr(msg, 'text', '无text')}")

            # 检查是否有@提及
            if hasattr(msg, "type") and msg.type == "At":
                # QQ平台的@消息
                if hasattr(msg, "qq"):
                    logger.info(f"找到At组件，qq: {msg.qq}")
                    return str(msg.qq)
                if hasattr(msg, "user_id"):
                    logger.info(f"找到At组件，user_id: {msg.user_id}")
                    return str(msg.user_id)

            # 检查文本中的@格式
            if hasattr(msg, "text"):
                text = str(msg.text)
                logger.info(f"检查文本消息: {text}")
                # 匹配 [CQ:at,qq=123456] 格式
                at_match = re.search(r"\[CQ:at,qq=(\d+)\]", text)
                if at_match:
                    logger.info(f"找到CQ码@格式: {at_match.group(1)}")
                    return at_match.group(1)

                # 匹配 @用户名 格式（需要平台支持）
                # 有些平台会直接解析为At组件，这里作为备选

        logger.info("未找到被@的用户或手动输入的QQ号")
        return None

    async def extract_image_from_event(self, event: AstrMessageEvent) -> str:
        """从事件中提取图片URL"""
        messages = event.get_messages()

        for msg in messages:
            # 标准图片组件
            if isinstance(msg, MsgImage):
                if hasattr(msg, "url") and msg.url:
                    return msg.url.strip()
                if hasattr(msg, "file") and msg.file:
                    # 从file字段提取URL - 处理微信格式
                    file_content = str(msg.file)
                    if "http" in file_content:
                        import re

                        # 提取URL并移除反引号
                        urls = re.findall(r"https?://[^\s\`\']+", file_content)
                        if urls:
                            return urls[0].strip("`'")

            # QQ官方平台特殊处理
            if hasattr(msg, "type") and msg.type == "Plain":
                text = str(msg.text) if hasattr(msg, "text") else str(msg)
                if "attachmentType=" in text and "image" in text:
                    # 这是QQ官方的图片消息格式，需要后续消息处理
                    continue

        return None

    async def download_and_process_image(self, image_url: str) -> str:
        """下载并处理图片"""
        logger.info(f"下载图片: {image_url[:100]}...")

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    raise Exception(f"图片下载失败: HTTP {response.status}")
                img_data = await response.read()

        # 处理图片
        img = PILImage.open(BytesIO(img_data))

        # 调整大小（最大1024px）
        if max(img.size) > 1024:
            ratio = 1024 / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, PILImage.LANCZOS)

        # 转换为JPEG并编码为base64
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        base64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")

        logger.info(f"图片处理完成，大小: {len(base64_data)} 字符")
        return base64_data

    async def call_animetrace_api(self, img_base64: str, model: str) -> dict:
        """使用base64调用AnimeTrace API"""
        payload = {"base64": img_base64, "is_multi": 1, "model": model, "ai_detect": 0}

        model_name_map = {
            "pre_stable": "动漫识别模型",
            "full_game_model_kira": "GalGame识别模型",
            "animetrace_high_beta": "通用识别模型"
        }
        logger.info(f"调用API - 模型: {model_name_map.get(model, model)} (base64方式)")

        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_url, data=payload, timeout=30) as response:
                if response.status != 200:
                    await response.text()
                    raise Exception(f"API错误: HTTP {response.status}")

                result = await response.json()
                logger.info(f"API返回: {len(result.get('data', []))} 个结果")
                return result

    async def call_animetrace_api_with_url(self, image_url: str, model: str) -> dict:
        """使用URL直接调用AnimeTrace API"""
        payload = {"url": image_url, "is_multi": 1, "model": model, "ai_detect": 0}

        model_name_map = {
            "pre_stable": "动漫识别模型",
            "full_game_model_kira": "GalGame识别模型",
            "animetrace_high_beta": "通用识别模型"
        }
        logger.info(f"调用API - 模型: {model_name_map.get(model, model)} (URL方式)")

        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_url, data=payload, timeout=30) as response:
                if response.status != 200:
                    # 如果URL方式失败，返回空结果让上层逻辑回退到base64方式
                    if response.status == 422:
                        logger.info("URL识别失败，准备回退到base64方式")
                        return {"data": []}
                    raise Exception(f"API错误: HTTP {response.status}")

                result = await response.json()
                logger.info(f"API返回: {len(result.get('data', []))} 个结果")
                return result

    def format_results(self, data: dict, model: str) -> str:
        """格式化识别结果"""
        if not data.get("data") or not data["data"]:
            return "🔍 未找到匹配的信息"

        first_result = data["data"][0]
        characters = first_result.get("character", [])

        if not characters:
            return "🔍 未识别到具体角色信息"

        model_name_map = {
            "pre_stable": "动漫识别",
            "full_game_model_kira": "GalGame识别",
            "animetrace_high_beta": "通用识别"
        }
        emoji_map = {
            "pre_stable": "🎌",
            "full_game_model_kira": "🎮",
            "animetrace_high_beta": "🔍"
        }
        model_name = model_name_map.get(model, "图片识别")
        emoji = emoji_map.get(model, "🔍")

        lines = [f"**{emoji} {model_name}结果**", "=" * 20]

        # 显示前5个结果
        for i, char in enumerate(characters[:5]):
            name = char.get("character", "未知角色")
            work = char.get("work", "未知作品")
            lines.append(f"{i + 1}. **{name}** - 《{work}》")

        if len(characters) > 5:
            lines.append(f"\n> 共 {len(characters)} 个结果，显示前5项")

        lines.append("\n💡 数据来源: AnimeTrace，仅供参考")

        return "\n".join(lines)

    async def timeout_check(self, user_id: str):
        """30秒超时检查"""
        try:
            await asyncio.sleep(30)  # 等待30秒
            if user_id in self.waiting_sessions:
                # 30秒后仍然在等待，发送超时消息
                session = self.waiting_sessions[user_id]
                event = session["event"]
                del self.waiting_sessions[user_id]
                del self.timeout_tasks[user_id]
                try:
                    await event.send(event.plain_result("⏰ 识别请求已超时，请重新发送命令"))
                    logger.info(f"用户 {user_id} 的图片识别请求已超时")
                except Exception as send_error:
                    logger.warning(f"发送超时消息失败: {send_error}")
                    # 如果发送超时消息失败，记录日志但不影响清理操作
        except asyncio.CancelledError:
            # 任务被取消，说明用户已经发送了图片
            pass
        except Exception as e:
            logger.error(f"超时检查任务异常: {str(e)}")

    async def terminate(self):
        logger.info("动漫/Gal/二游识别插件已卸载")
        # 取消所有超时任务
        for task in self.timeout_tasks.values():
            task.cancel()
        self.timeout_tasks.clear()
