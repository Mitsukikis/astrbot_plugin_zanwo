import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional
from aiocqhttp import CQHttp
import aiocqhttp
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
import astrbot.api.message_components as Comp
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.filter.permission import PermissionType

logger = logging.getLogger(__name__)

CHINA_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
AUTO_LIKE_RETRY_SECONDS = 300

# 点赞成功回复
success_responses = [
    "👍{total_likes}",
    "赞了赞了",
    "点赞成功！",
    "给{username}点了{total_likes}个赞",
    "赞送出去啦！一共{total_likes}个哦！",
    "为{username}点赞成功！总共{total_likes}个！",
    "点了{total_likes}个，快查收吧！",
    "赞已送达，请注意查收~ 一共{total_likes}个！",
    "给{username}点了{total_likes}个赞，记得回赞哟！",
    "赞了{total_likes}次，看看收到没？",
    "点了{total_likes}赞，没收到可能是我被风控了",
]

# 点赞数到达上限回复
limit_responses = [
    "今天给{username}的赞已达上限",
    "赞了那么多还不够吗？",
    "{username}别太贪心哟~",
    "今天赞过啦！",
    "今天已经赞过啦~",
    "已经赞过啦~",
    "还想要赞？不给了！",
    "已经赞过啦，别再点啦！",
]

# 陌生人点赞回复
stranger_responses = [
    "不加好友不赞",
    "我和你有那么熟吗？",
    "你谁呀？",
    "你是我什么人凭啥要我赞你？",
    "不想赞你这个陌生人",
    "我不认识你，不赞！",
    "加我好友了吗就想要我赞你？",
    "滚！",
]


@register(
    "astrbot_plugin_zanwo",
    "Futureppo",
    "发送 赞我 自动点赞",
    "1.1.0",
    "https://github.com/Mitsukikis/astrbot_plugin_zanwo",
)
class zanwo(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.success_responses: list[str] = success_responses
        self._scheduler_task: Optional[asyncio.Task] = None

        # 群聊白名单
        self.white_list_groups: list[str] = config.get("white_list_groups", [])
        # 订阅点赞的用户ID列表
        self.subscribed_users: list[str] = config.get("subscribed_users", [])
        # 点赞日期
        self.zanwo_date: Optional[str] = config.get("zanwo_date", None)
        # 每个 QQ 机器人最后一次完成自动点赞的日期
        self.auto_like_state: dict[str, str] = self._load_auto_like_state()

    def _load_auto_like_state(self) -> dict[str, str]:
        raw_state = self.config.get("auto_like_state", "{}")
        if isinstance(raw_state, dict):
            return {str(key): str(value) for key, value in raw_state.items()}
        if not isinstance(raw_state, str) or not raw_state.strip():
            return {}
        try:
            state = json.loads(raw_state)
        except (TypeError, ValueError):
            logger.warning("自动点赞状态无法解析，将重新记录")
            return {}
        if not isinstance(state, dict):
            return {}
        return {str(key): str(value) for key, value in state.items()}

    def _is_group_allowed(self, event: AiocqhttpMessageEvent) -> bool:
        group_id = event.get_group_id()
        if group_id and self.white_list_groups:
            return str(group_id) in self.white_list_groups
        return True

    async def _run_like(
        self, event: AiocqhttpMessageEvent, target_ids: list[str]
    ) -> Optional[str]:
        if not self._is_group_allowed(event):
            return None
        if not target_ids:
            return None
        return await self._like(event.bot, target_ids)

    def _save_auto_like_state(self, all_completed_date: Optional[str] = None) -> None:
        self.config["auto_like_state"] = json.dumps(
            self.auto_like_state,
            ensure_ascii=False,
            sort_keys=True,
        )
        if all_completed_date:
            self.zanwo_date = all_completed_date
            self.config["zanwo_date"] = all_completed_date
        self.config.save_config()

    def _get_qq_platforms(self) -> list:
        platform_manager = getattr(self.context, "platform_manager", None)
        if platform_manager is None:
            return []
        platforms = getattr(platform_manager, "platform_insts", [])
        return [
            platform
            for platform in platforms
            if getattr(platform.meta(), "name", "") == "aiocqhttp"
        ]

    async def _trigger_auto_like_for_all_bots(self) -> bool:
        """让每个在线的 OneBot QQ 机器人给全部订阅用户点赞。"""
        subscribed_users = list(dict.fromkeys(map(str, self.subscribed_users)))
        if not subscribed_users:
            return True

        today = datetime.now(CHINA_TZ).date().isoformat()
        qq_platforms = self._get_qq_platforms()
        if not qq_platforms:
            logger.warning("自动点赞等待中：当前没有可用的 OneBot QQ 平台")
            return False

        pending_platforms = [
            platform
            for platform in qq_platforms
            if self.auto_like_state.get(str(platform.meta().id)) != today
        ]
        if not pending_platforms:
            return True

        logger.info(
            "开始执行每日自动点赞：机器人=%d，订阅用户=%d，日期=%s",
            len(pending_platforms),
            len(subscribed_users),
            today,
        )
        for platform in pending_platforms:
            platform_id = str(platform.meta().id)
            try:
                client = platform.get_client()
                result = await self._like(client, subscribed_users)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("QQ 平台 %s 自动点赞失败，5 分钟后重试", platform_id)
                continue

            self.auto_like_state[platform_id] = today
            self._save_auto_like_state()
            logger.info(
                "QQ 平台 %s 自动点赞完成：用户=%d，结果=%s",
                platform_id,
                len(subscribed_users),
                result.replace("\n", "；"),
            )

        all_completed = all(
            self.auto_like_state.get(str(platform.meta().id)) == today
            for platform in qq_platforms
        )
        if all_completed:
            self._save_auto_like_state(all_completed_date=today)
            logger.info("每日自动点赞全部完成：日期=%s", today)
        return all_completed

    @staticmethod
    def _seconds_until_next_midnight() -> float:
        now = datetime.now(CHINA_TZ)
        tomorrow = (now + timedelta(days=1)).date()
        next_run = datetime.combine(tomorrow, datetime.min.time(), tzinfo=CHINA_TZ)
        return max(1.0, (next_run - now).total_seconds())

    async def _auto_like_scheduler_loop(self) -> None:
        # 启动时先等待平台适配器就绪；若当天漏跑，会立即补跑一次。
        await asyncio.sleep(10)
        while True:
            completed = False
            try:
                completed = await self._trigger_auto_like_for_all_bots()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("每日自动点赞调度异常")

            wait_seconds = (
                self._seconds_until_next_midnight()
                if completed
                else AUTO_LIKE_RETRY_SECONDS
            )
            await asyncio.sleep(wait_seconds)

    async def initialize(self) -> None:
        if self._scheduler_task and not self._scheduler_task.done():
            return
        self._scheduler_task = asyncio.create_task(
            self._auto_like_scheduler_loop(),
            name="zanwo_daily_auto_like",
        )
        logger.info("每日自动点赞调度器已启动：Asia/Shanghai 00:00")

    async def terminate(self) -> None:
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        self._scheduler_task = None
        logger.info("每日自动点赞调度器已停止")

    async def _like(self, client: CQHttp, ids: list[str]) -> str:
        """
        点赞的核心逻辑
        :param client: CQHttp客户端
        :param ids: 用户ID列表
        """
        replys = []
        for id in ids:
            total_likes = 0
            error_reply = "点赞失败"
            try:
                username = (await client.get_stranger_info(user_id=int(id))).get(
                    "nickname", "未知用户"
                )
            except aiocqhttp.exceptions.ActionFailed:
                username = str(id)
            for _ in range(5):
                try:
                    await client.send_like(user_id=int(id), times=10)  # 点赞10次
                    total_likes += 10
                except aiocqhttp.exceptions.ActionFailed as e:
                    error_message = str(e)
                    if "已达" in error_message:
                        error_reply = random.choice(limit_responses)
                    elif "权限" in error_message:
                        error_reply = "你设了权限不许陌生人赞你"
                    else:
                        error_reply = random.choice(stranger_responses)
                    break

            reply = random.choice(self.success_responses) if total_likes > 0 else error_reply

            # 检查 reply 中是否包含占位符，并根据需要进行替换
            if "{username}" in reply:
                reply = reply.replace("{username}", username)
            if "{total_likes}" in reply:
                reply = reply.replace("{total_likes}", str(total_likes))

            replys.append(reply)

        return "\n".join(replys).strip()

    @staticmethod
    def get_ats(event: AiocqhttpMessageEvent) -> list[str]:
        """获取被at者们的id列表"""
        messages = event.get_messages()
        self_id = event.get_self_id()
        return [
            str(seg.qq)
            for seg in messages
            if (isinstance(seg, Comp.At) and str(seg.qq) != self_id)
        ]

    @filter.regex(r"^赞.*")
    async def like_me(self, event: AiocqhttpMessageEvent):
        """给用户点赞"""
        target_ids = []
        if event.message_str == "赞我":
            target_ids.append(event.get_sender_id())
        if not target_ids:
            target_ids = self.get_ats(event)
        result = await self._run_like(event, target_ids)
        if not result:
            return
        yield event.plain_result(result)

    @filter.llm_tool(name="like_qq_profile")
    async def like_qq_profile(self, event: AiocqhttpMessageEvent, target: str = "self"):
        """给 QQ 名片点赞。

        Args:
            target(string): 点赞目标，可填 self、me、我，或明确的 QQ 号。未明确提供时默认给当前发言者点赞。
        """
        normalized_target = target.strip().lower() if target else "self"
        if normalized_target in {"", "self", "me", "我", "自己", "我自己"}:
            target_ids = [event.get_sender_id()]
        elif target.strip().isdigit():
            target_ids = [target.strip()]
        else:
            return "只能给当前发言者点赞，或给明确提供的 QQ 号点赞。"

        result = await self._run_like(event, target_ids)
        if not result:
            return "当前会话不允许使用点赞功能。"
        return result

    @filter.command("订阅点赞")
    async def subscribe_like(self, event: AiocqhttpMessageEvent):
        """订阅点赞"""
        sender_id = event.get_sender_id()
        event.session_id
        if sender_id in self.subscribed_users:
            yield event.plain_result("你已经订阅点赞了哦~")
            return
        self.subscribed_users.append(sender_id)
        self.config["subscribed_users"] = self.subscribed_users
        self.config.save_config()
        yield event.plain_result("订阅成功！我将每天自动为你点赞")

    @filter.command("取消订阅点赞")
    async def unsubscribe_like(self, event: AiocqhttpMessageEvent):
        """取消订阅点赞"""
        sender_id = event.get_sender_id()
        if sender_id not in self.subscribed_users:
            yield event.plain_result("你还没有订阅点赞哦~")
            return
        self.subscribed_users.remove(sender_id)
        self.config["subscribed_users"] = self.subscribed_users
        self.config.save_config()
        yield event.plain_result("已取消订阅！我将不再自动给你点赞")

    @filter.command("订阅点赞列表")
    async def like_list(self, event: AiocqhttpMessageEvent):
        """查看订阅点赞的用户ID列表"""

        if not self.subscribed_users:
            yield event.plain_result("当前没有订阅点赞的用户哦~")
            return
        users_str = "\n".join(self.subscribed_users).strip()
        yield event.plain_result(f"当前订阅点赞的用户ID列表：\n{users_str}")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("谁赞了bot", alias={"谁赞了你"})
    async def get_profile_like(self, event: AiocqhttpMessageEvent):
        """获取bot自身点赞列表"""
        client = event.bot
        data = await client.get_profile_like()
        reply = ""
        user_infos = data.get("favoriteInfo", {}).get("userInfos", [])
        for user in user_infos:
            if (
                "nick" in user
                and user["nick"]
                and "count" in user
                and user["count"] > 0
            ):
                reply += f"\n【{user['nick']}】赞了我{user['count']}次"
        if not reply:
            reply = "暂无有效的点赞信息"
        url = await self.text_to_image(reply)
        yield event.image_result(url)
