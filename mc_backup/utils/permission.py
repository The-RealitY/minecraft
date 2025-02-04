from mc_backup import DISCORD_AUTH_ROLES


def check_role(ctx):
    roles = [role.id for role in ctx.author.roles]
    if not any(role_id in roles for role_id in DISCORD_AUTH_ROLES):
        return False
    return True
