from __future__ import annotations


def multi_position_enabled(mode: dict | None) -> bool:
    mode = mode or {}
    return (
        str(mode.get("positionMode", "")).lower() == "long_short_mode"
        and str(mode.get("multiPosition", "false")).lower() == "true"
    )


def ensure_multi_position(bot):
    """Ensure the bot is in Hedge + Multi-Position mode without a UI button.

    PAPER mode is always treated as multi-position. For DEMO/LIVE, the bot
    checks BloFin when it is armed and automatically requests the required
    account mode if it is not already active. BloFin may reject the change if
    positions/orders are open; that exchange error is surfaced to the user.
    """
    if bot.cfg.environment == "paper":
        bot.position_mode = {"positionMode": "long_short_mode", "multiPosition": "true"}
        return bot.position_mode

    bot.margin_mode = bot.client.get_margin_mode()
    bot.position_mode = bot.client.get_position_mode()
    if multi_position_enabled(bot.position_mode):
        return bot.position_mode

    try:
        bot.enable_multi_position_mode()
    except Exception as exc:
        raise RuntimeError(
            "Multi-Position mode is automatic, but BloFin could not enable Hedge + "
            "Multi-Position mode. Close open positions/orders and arm the bot again. "
            f"Exchange response: {exc}"
        ) from exc

    bot.position_mode = bot.client.get_position_mode()
    if not multi_position_enabled(bot.position_mode):
        raise RuntimeError(
            "BloFin did not confirm Hedge + Multi-Position mode after the automatic change."
        )
    return bot.position_mode
