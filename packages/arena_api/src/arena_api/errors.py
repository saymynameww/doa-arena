"""异常类型定义。"""


class ArenaError(Exception):
    """竞技场基础异常。"""

    pass


class PluginError(ArenaError):
    """插件相关错误。"""

    pass


class ConfigError(ArenaError):
    """配置错误。"""

    pass


class ValidationError(ArenaError):
    """验证错误。"""

    pass
